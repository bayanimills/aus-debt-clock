"""Odometer motion for the LCD clock.

Digits are tiered by how often they change at the current rate. Fast digits
(over FAST_HZ changes a second: ones, tens and hundreds at $2,188/s) cannot be
read as numbers at any frame rate. With FAST_STYLE "blur" they are drawn as
the wheel would photograph: the digit strip averaged (in linear light) over
the distance it travels in one SHUTTER_MS exposure. At $2,188/s that is 0.44
of a digit for the hundreds (a streaked digit racing upward), 4.4 for the
tens (a shimmer) and the whole wheel for the ones (a steady blur). The blur is
computed per frame from per-column prefix sums of the 1x glyph strip. With
FAST_STYLE "dim" they are plain digits in LCD_DIM. Slower digits roll up like an
odometer wheel, easing out over ROLL_MS or half their change interval,
whichever is shorter. When a carry moves several at once, each place to the
left starts STAGGER_MS later so the carry visibly ripples.

Same tick()/full() interface as main.UI. Animation timing runs on ticks_ms,
not the wall clock, so an RTC re-set never jerks a roll.
"""
import framebuf
import time

import config
import debtclock as dc
import font

LEVELS = 16


class MotionUI:
    def __init__(self, disp):
        self.o = disp
        self.h = font.height()
        self.y = (disp.height - self.h) // 2
        self.num = ""
        self.rate = 0
        self.rolls = {}     # char index -> [old, new, start_ms, dur_ms]
        self.cells = {}     # glyph width -> scratch FrameBuffer for compositing
        self.blur = config.FAST_STYLE == "blur"
        if self.blur:
            self._build_strip()
        disp.fill(0)

    def _build_strip(self):
        """Prefix sums down each column of the 0..9 strip, three wheels long so
        a window never needs a wrap test."""
        from st7789 import color565
        gh = font.HEIGHT
        self.strip = 10 * gh
        self.cols = len(font._ART["0"][0])
        self.P = []
        for c in range(self.cols):
            p = [0]
            acc = 0
            for k in range(3 * self.strip):
                if font._ART[str((k // gh) % 10)][k % gh][c] == "X":
                    acc += 1
                p.append(acc)
            self.P.append(p)
        # Coverage 0..1 is linear light; encode to the panel's ~2.2 gamma.
        r, g, b = config.LCD_FG
        self.shade = []
        for i in range(LEVELS):
            f = (i / (LEVELS - 1)) ** (1 / 2.2)
            self.shade.append(color565(int(r * f), int(g * f), int(b * f)))
        self.last = {}      # char index -> window start last drawn

    def set_rate(self, rate_aud):
        self.rate = rate_aud

    def _layout(self, s):
        self.xs, self.fast, self.dur, self.place, self.smear = [], [], [], [], []
        if not self.blur:
            self.strip = 1
        x = (self.o.width - font.width(s)) // 2
        p = sum(1 for c in s if c.isdigit())
        for c in s:
            self.xs.append(x)
            if c.isdigit():
                p -= 1
                hz = self.rate / 10 ** p
                self.fast.append(hz > config.FAST_HZ)
                self.place.append(p)
                self.smear.append(max(1, min(self.strip if self.blur else 1,
                                             int(hz * config.SHUTTER_MS * font.HEIGHT // 1000))))
                self.dur.append(min(config.ROLL_MS, int(500 / hz)) if hz > 0 else config.ROLL_MS)
            else:
                self.fast.append(False)
                self.place.append(-1)
                self.smear.append(0)
                self.dur.append(0)
            x += font.advance(c)

    def _ink(self, i):
        return self.o.dim if self.fast[i] else self.o.ink

    def full(self, value):
        s = dc.format_aud(value)
        self.num = s
        self.rolls = {}
        self._layout(s)
        self.o.fill(0)
        if self.blur:
            self.last = {}
        for i, c in enumerate(s):
            if self.blur and self.fast[i]:
                self._smear(i, value)
            else:
                font.draw(self.o, c, self.xs[i], self.y, fg=self._ink(i))
        self.o.show()

    def tick(self, value):
        s = dc.format_aud(value)
        if len(s) != len(self.num):
            self.full(value)
            return
        now = time.ticks_ms()
        lo = hi = -1
        k = 0
        for i in range(len(s) - 1, -1, -1):
            if self.blur and self.fast[i]:
                if self._smear(i, value):
                    hi = i if hi < 0 else hi
                    lo = i
                continue
            if s[i] == self.num[i]:
                continue
            if self.fast[i]:
                font.draw(self.o, s[i], self.xs[i], self.y, fg=self.o.dim)
                hi = i if hi < 0 else hi
                lo = i
            else:
                r = self.rolls.get(i)
                old = r[1] if r else self.num[i]
                self.rolls[i] = [old, s[i], time.ticks_add(now, k * config.STAGGER_MS), self.dur[i]]
                k += 1
        self.num = s
        if hi >= 0:
            x1 = self.xs[hi] + font.advance(s[hi]) - 1
            self.o.show_window(self.xs[lo], x1, self.y, self.y + self.h - 1)
        for i in list(self.rolls):
            old, new, t0, dur = self.rolls[i]
            el = time.ticks_diff(now, t0)
            if el < 0:
                continue            # staggered: the old digit stays put
            if el >= dur:
                off = self.h
                del self.rolls[i]
            else:
                q = 1 - el / dur
                off = int(self.h * (1 - q * q * q))     # ease-out cubic
            self._roll(i, old, new, off)

    def _smear(self, i, value):
        """Draw fast digit i as its wheel blurred over one exposure. Returns
        False when the frame would be identical to the last one drawn."""
        p = self.place[i]
        L = self.smear[i]
        unit = 10 ** p
        top = (value % (unit * 10)) * font.HEIGHT // unit   # strip row at the cell top
        start = (top - L) % self.strip if L < self.strip else 0
        if self.last.get(i) == start:
            return False
        self.last[i] = start
        k = font.height() // font.HEIGHT
        x0, y0 = self.xs[i], self.y
        shade, fill = self.shade, self.o.fill_rect
        top_lvl = LEVELS - 1
        for c in range(self.cols):
            P = self.P[c]
            x = x0 + c * k
            for r in range(font.HEIGHT):
                a = start + r
                fill(x, y0 + r * k, k, k, shade[(P[a + L] - P[a]) * top_lvl // L])
        return True

    def _roll(self, i, old, new, off):
        """Old digit slides up and out, new one rises in from below."""
        w, g0 = font._glyph(old, self.o.ink)
        _, g1 = font._glyph(new, self.o.ink)
        cell = self.cells.get(w)
        if cell is None:
            cell = framebuf.FrameBuffer(bytearray(w * self.h * 2), w, self.h, framebuf.RGB565)
            self.cells[w] = cell
        if off < self.h:
            cell.blit(g0, 0, -off)
        cell.blit(g1, 0, self.h - off)
        x = self.xs[i]
        self.o.blit(cell, x, self.y)
        self.o.show_window(x, x + w - 1, self.y, self.y + self.h - 1)
