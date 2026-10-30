"""Wearable AUD debt clock. Drives either board in config.BOARD:
Pico 2 W + Pico-OLED-2.23 (SSD1305 128x32), or the RP2350B 2.25in LCD (ST7789
284x76, no radio).

Layout: the number alone, $1,002,841,620,000 in 7x20 digits with 2 px commas
(123 px; 246 px at the LCD's 2x scale), centred. Sync state is logged, not drawn.

Boot: load cache (or the bundled baseline.json), try one sync, then tick.
Sync: daily where there is WiFi; otherwise tools/deploy.py --refresh over USB.
"""
import json
import time

import config
import debtclock as dc
import font
import net
from display import open_display

try:
    import secrets
except ImportError:
    secrets = None

CACHE_PATH = "cache.json"
BUNDLED_BASELINE = "baseline.json"



def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f)
    except Exception as e:
        print("save failed:", e)


def deadline(seconds):
    """Monotonic deadline in ticks_ms, unaffected by RTC re-sets. Intervals
    must stay under ~6 days for ticks_diff wraparound to hold."""
    return time.ticks_add(time.ticks_ms(), int(seconds * 1000))


def due(dl):
    return time.ticks_diff(time.ticks_ms(), dl) >= 0


class Wall:
    """Fractional wall-clock seconds from the RTC plus a ticks_ms sub-second
    fraction, re-anchored whenever the RTC second changes. Survives lightsleep
    and RTC re-sets (a re-set simply re-anchors on the next tick)."""

    def __init__(self):
        self._sec = time.time()
        self._t0 = time.ticks_ms()

    def now_ms(self):
        """Integer milliseconds. Floats are 32-bit on RP2 and cannot hold this."""
        s = time.time()
        if s != self._sec:
            self._sec = s
            self._t0 = time.ticks_ms()
            return s * 1000
        frac = time.ticks_diff(time.ticks_ms(), self._t0)
        if frac > 999:
            frac = 999
        return s * 1000 + frac


def model_from(baseline):
    as_at = net.to_seconds(net.parse_iso_date(baseline["as_at"]))
    return dc.Model.from_dict(baseline, as_at)


def as_at_label(baseline):
    y, m, d, _, _, _ = net.parse_iso_date(baseline["as_at"])
    return "%02d%s" % (d, ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL",
                           "AUG", "SEP", "OCT", "NOV", "DEC")[m - 1])


def try_sync():
    if not config.HAS_WIFI or not secrets or not getattr(secrets, "WIFI_SSID", ""):
        return None
    try:
        return net.sync(secrets.WIFI_SSID, secrets.WIFI_PASS, config.BASELINE_URL,
                        getattr(secrets, "AUTH_HEADER", ""),
                        config.WIFI_TIMEOUT_S, config.HTTP_TIMEOUT_S)
    except Exception as e:
        print("sync failed:", e)
        return None


class UI:
    def __init__(self, disp):
        self.o = disp
        self.num = ""
        self.y = (disp.height - font.height()) // 2
        self.y1 = self.y + font.height() - 1
        self.o.fill(0)

    def x(self, s):
        return (self.o.width - font.width(s)) // 2

    def full(self, value):
        self.num = dc.format_aud(value)
        self.o.fill(0)
        font.draw(self.o, self.num, self.x(self.num), self.y)
        self.o.show()

    def tick(self, value):
        s = dc.format_aud(value)
        i = dc.first_diff(self.num, s)
        if i < 0:
            return
        if len(s) != len(self.num):
            self.num = s
            self.o.fill_rect(0, self.y, self.o.width, font.height(), 0)
            font.draw(self.o, s, self.x(s), self.y)
            self.o.show()
            return
        self.num = s
        nx = self.x(s)
        x0 = nx + font.x_of(s, i)
        font.draw(self.o, s[i:], x0, self.y)
        if config.PARTIAL_UPDATE:
            self.o.show_window(x0, nx + font.width(s), self.y, self.y1)
        else:
            self.o.show()


def main(ticks=None, sync=True):
    """ticks: stop after N render ticks (bench use). sync=False skips WiFi."""
    oled = open_display()
    lcd = config.BOARD == "rp2350b_lcd"
    if lcd and config.MOTION:
        from motion import MotionUI
        ui = MotionUI(oled)
    else:
        ui = UI(oled)
    tick_ms = config.LCD_TICK_MS if lcd else config.TICK_MS
    oled.show()

    state = load_json(CACHE_PATH) or {}
    # Newest of the synced and the bundled baseline: on the radio-less board a
    # USB refresh only replaces the bundled file. ISO dates compare as strings.
    baseline = state.get("baseline")
    bundled = load_json(BUNDLED_BASELINE)
    if bundled and (not baseline or bundled["as_at"] > baseline["as_at"]):
        baseline = bundled
    mark = "?"

    # Without a valid RTC and without network we cannot know how long we were
    # off. Resume from where the display left off; the next sync corrects it.
    if not net.rtc_valid() and state.get("last_epoch"):
        net.set_rtc(time.localtime(int(state["last_epoch"]))[:6])

    fresh = try_sync() if sync else None
    if fresh:
        baseline = fresh
        state["baseline"] = fresh
        state["last_sync"] = time.time()
        mark = "*"
        next_sync = deadline(config.SYNC_INTERVAL_S)
    else:
        mark = "!" if config.HAS_WIFI and secrets and getattr(secrets, "WIFI_SSID", "") else "?"
        next_sync = deadline(config.SYNC_RETRY_S)

    if not baseline:
        oled.fill(0)
        oled.text("no baseline", 0, 0, oled.ink)
        oled.text("copy baseline.json", 0, 12, oled.ink)
        oled.show()
        return

    # The clock can never be earlier than the baseline's as-at date: with no
    # sync the RTC is 2021, and a cached epoch can predate a newer baseline.
    # Either way, the as-at date is the latest instant we know has passed.
    as_at = net.parse_iso_date(baseline["as_at"])
    if not net.rtc_valid() or time.time() < net.to_seconds(as_at):
        net.set_rtc(as_at)

    wall = Wall()
    model = model_from(baseline)
    if hasattr(ui, "set_rate"):
        ui.set_rate(model.rate_aud)
    start_value = state.get("last_value") if net.rtc_valid() else None
    clock = dc.Clock(model, wall.now_ms(), start_value)
    print("sync", mark, "rate", model.rate_aud, "as at", as_at_label(baseline))
    ui.full(clock.displayed)

    # Persist once at boot: without a radio the RTC is only set over USB, and
    # a power cut before the first periodic save would otherwise lose it.
    state["last_value"] = clock.displayed
    state["last_epoch"] = time.time()
    save_json(CACHE_PATH, state)
    next_save = deadline(config.SAVE_INTERVAL_S)
    n = 0
    while ticks is None or n < ticks:
        n += 1
        frame = time.ticks_ms()
        ui.tick(clock.value(wall.now_ms()))
        if n % 40 == 0:
            print("tick", n, ui.num)

        if due(next_save):
            state["last_value"] = clock.displayed
            state["last_epoch"] = time.time()
            save_json(CACHE_PATH, state)
            next_save = deadline(config.SAVE_INTERVAL_S)

        if due(next_sync):
            fresh = try_sync()
            if fresh:
                baseline = fresh
                state["baseline"] = fresh
                state["last_sync"] = time.time()
                model = model_from(baseline)
                if hasattr(ui, "set_rate"):
                    ui.set_rate(model.rate_aud)
                clock.resync(model, wall.now_ms())
                mark = "*"
                next_sync = deadline(config.SYNC_INTERVAL_S)
            else:
                mark = "!"
                next_sync = deadline(config.SYNC_RETRY_S)
            state["last_value"] = clock.displayed
            state["last_epoch"] = time.time()
            save_json(CACHE_PATH, state)
            print("sync", mark, "as at", as_at_label(baseline))
            ui.full(clock.displayed)

        if config.LIGHTSLEEP:
            import machine
            machine.lightsleep(tick_ms)
        else:
            # Pace to the frame period rather than sleeping a full period
            # after the drawing time.
            left = tick_ms - time.ticks_diff(time.ticks_ms(), frame)
            if left > 0:
                time.sleep_ms(left)


if __name__ == "__main__":
    main()
