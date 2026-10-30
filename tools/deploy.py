#!/usr/bin/env python3
"""Copy firmware + bundled baseline to the device and reset it.

  python tools/deploy.py COM9             # deploy and reset
  python tools/deploy.py COM9 --no-reset
  python tools/deploy.py COM9 --repl      # deploy then drop into the REPL
  python tools/deploy.py COM9 --refresh   # baseline.json + clock only, then reset

The board comes from firmware/config.py (BOARD). secrets.py is copied only to
a board with WiFi, and only if it exists locally (it is git-ignored).

Every deploy also stamps the device with UTC from this machine: the RTC, and
last_epoch in cache.json, which is what the firmware resumes from after a
reset or power loss (mpremote's soft reset does not run main.py, so the RTC
alone would not survive into the clock). The cached display value is dropped
so a newer, lower baseline is not held up by an old figure. The LCD board has
no radio, so --refresh over USB is how it gets a new baseline and the time.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FW = ROOT / "firmware"
COMMON = ["font.py", "debtclock.py", "net.py", "config.py", "display.py", "motion.py", "main.py"]
DRIVERS = {"pico2w_oled": ["ssd1305.py"], "rp2350b_lcd": ["st7789.py"]}


def mp(port, *args):
    cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
    print("+", " ".join(cmd[4:]))
    subprocess.run(cmd, check=True)


def board():
    m = re.search(r'^BOARD\s*=\s*"([^"]+)"', (FW / "config.py").read_text(), re.M)
    if not m or m.group(1) not in DRIVERS:
        raise SystemExit("config.py: BOARD must be one of %s" % ", ".join(DRIVERS))
    return m.group(1)


STAMP = """import json, machine, time
machine.RTC().datetime(%r)
try:
    s = json.load(open("cache.json"))
except Exception:
    s = {}
s.pop("last_value", None)
s["last_epoch"] = time.time()
json.dump(s, open("cache.json", "w"))
print("clock", time.localtime())
"""


def set_clock(port):
    t = time.gmtime()
    mp(port, "exec", STAMP % ((t.tm_year, t.tm_mon, t.tm_mday, t.tm_wday,
                               t.tm_hour, t.tm_min, t.tm_sec, 0),))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    port = sys.argv[1]
    flags = set(sys.argv[2:])
    b = board()
    if "--refresh" not in flags:
        for f in DRIVERS[b] + COMMON:
            mp(port, "cp", str(FW / f), f":{f}")
        if b == "pico2w_oled" and (FW / "secrets.py").exists():
            mp(port, "cp", str(FW / "secrets.py"), ":secrets.py")
        elif b == "pico2w_oled":
            print("note: firmware/secrets.py absent; device will run without WiFi sync")
    mp(port, "cp", str(ROOT / "data" / "baseline.json"), ":baseline.json")
    set_clock(port)
    if "--no-reset" not in flags:
        mp(port, "reset")
    if "--repl" in flags:
        mp(port, "repl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
