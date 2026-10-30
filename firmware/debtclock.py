"""Core arithmetic for the debt clock. Pure Python, runs on CPython and MicroPython.

Model: debt(t) = baseline + rate * (t - as_at)

All arithmetic is integer. MicroPython on RP2 uses 32-bit floats, whose 24-bit
mantissa cannot hold a trillion-dollar figure to the dollar or a 1.7e9-second
timestamp to the second, let alone a millisecond. Integers are arbitrary
precision on every port, so money is carried in micro-AUD and time in
milliseconds and nothing is ever rounded until formatting.

The baseline is the last AOFM "Total AUD Main Funding Instruments" figure
(Treasury Bonds + Indexed Bonds + Notes = AGS on issue) as at the date AOFM
published it. The rate is the Budget Paper 1 gross-debt path for the current
financial year divided into seconds. Both come from data/baseline.json.

Display rule: the number never runs backwards. If a resync lands below what
is already on the panel (the extrapolation overshot), the display keeps
ticking at a quarter of the rate until the target catches up.
"""

UAUD = 1_000_000          # micro-AUD per AUD
CATCHUP_DIV = 4           # tick at rate/4 while above target


class Model:
    __slots__ = ("baseline", "as_at_ms", "rate")

    def __init__(self, baseline_aud, as_at_s, rate_uaud_per_s):
        self.baseline = int(baseline_aud)             # AUD
        self.as_at_ms = int(as_at_s) * 1000           # ms, caller's epoch
        self.rate = int(rate_uaud_per_s)              # micro-AUD per second

    def target(self, now_ms):
        """Micro-AUD at now_ms (int)."""
        return self.baseline * UAUD + self.rate * (now_ms - self.as_at_ms) // 1000

    @property
    def rate_aud(self):
        return self.rate / UAUD

    @staticmethod
    def from_dict(d, as_at_s):
        """as_at_s: the caller converts d['as_at'] to its own epoch (int seconds)."""
        return Model(d["baseline_aud"], as_at_s, aud_to_uaud(d["rate_aud_per_s"]))


def aud_to_uaud(x):
    """Float or int AUD -> int micro-AUD, via string to dodge float32 loss."""
    if isinstance(x, int):
        return x * UAUD
    s = str(x)
    if "e" in s or "E" in s:
        return int(round(float(x) * UAUD))
    whole, _, frac = s.partition(".")
    frac = (frac + "000000")[:6]
    neg = whole.startswith("-")
    v = abs(int(whole or "0")) * UAUD + int(frac)
    return -v if neg else v


class Clock:
    """Tracks the displayed value (micro-AUD) across ticks and resyncs."""

    def __init__(self, model, now_ms, start_value_aud=None):
        self.model = model
        self._now = int(now_ms)
        t = model.target(self._now)
        if start_value_aud is not None and int(start_value_aud) * UAUD > t:
            self._disp = int(start_value_aud) * UAUD
        else:
            self._disp = t

    def resync(self, model, now_ms):
        self.model = model
        self.value(now_ms)

    def value(self, now_ms):
        """Advance to now_ms and return the displayed value in whole AUD."""
        now_ms = int(now_ms)
        dt = now_ms - self._now
        if dt < 0:
            dt = 0
        self._now = now_ms
        target = self.model.target(now_ms)
        if target >= self._disp:
            self._disp = target
        else:
            self._disp += (self.model.rate // CATCHUP_DIV) * dt // 1000
            if self._disp < target:
                self._disp = target
        return self._disp // UAUD

    @property
    def displayed(self):
        return self._disp // UAUD


def group_thousands(n):
    """Integer -> '1,002,841,620,000' without locale support."""
    n = int(n)
    neg = n < 0
    s = str(-n if neg else n)
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    out = s + out
    return "-" + out if neg else out


def format_aud(value):
    return "$" + group_thousands(int(value))


def format_rate(rate_aud_per_s):
    """AUD/s -> '+$2,188/s' (or '-$..' when the path falls)."""
    r = int(round(rate_aud_per_s))
    sign = "+" if r >= 0 else "-"
    return sign + "$" + group_thousands(abs(r)) + "/s"


def rate_from_path(start_bn, end_bn, seconds):
    """Gross-debt path in AUD billions over a period -> AUD per second (float, tool side)."""
    return (float(end_bn) - float(start_bn)) * 1e9 / float(seconds)


def first_diff(a, b):
    """Index of the first character where two strings differ, or -1 if equal
    (length differences count as a difference at the shorter length)."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return -1 if len(a) == len(b) else n
