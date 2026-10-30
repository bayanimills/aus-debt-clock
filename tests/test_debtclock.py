import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))

import debtclock as dc  # noqa: E402

FY_SECONDS = 365 * 86400
U = dc.UAUD
BASE = 1_002_841_620_000          # AOFM 31 Aug 2026
AS_AT = 1_787_000_000             # arbitrary epoch seconds near 2026
RATE = dc.aud_to_uaud(2187.976)   # micro-AUD/s


def test_rate_from_budget_path():
    r = dc.rate_from_path(982.0, 1051.0, FY_SECONDS)
    assert 2180 < r < 2195
    assert dc.format_rate(r) == "+$2,188/s"


def test_aud_to_uaud_is_exact():
    assert dc.aud_to_uaud(2187.976) == 2_187_976_000
    assert dc.aud_to_uaud(2000) == 2_000_000_000
    assert dc.aud_to_uaud("0.5") == 500_000
    assert dc.aud_to_uaud(-1.25) == -1_250_000


def test_target_is_linear_and_exact_at_trillions():
    m = dc.Model(BASE, AS_AT, RATE)
    t0 = m.target(AS_AT * 1000)
    assert t0 == BASE * U
    # one millisecond later the target moved by rate/1000, to the micro-dollar
    assert m.target(AS_AT * 1000 + 1) - t0 == RATE // 1000
    # one second later, exactly one rate
    assert m.target(AS_AT * 1000 + 1000) - t0 == RATE


def test_clock_advances_every_frame():
    """The float32 failure mode: value frozen across 40 ms frames."""
    m = dc.Model(BASE, AS_AT, RATE)
    c = dc.Clock(m, AS_AT * 1000)
    seen = set()
    for i in range(1, 26):
        seen.add(c.value(AS_AT * 1000 + i * 40))
    assert len(seen) == 25                       # a new dollar figure every frame
    assert c.value(AS_AT * 1000 + 1000) == BASE + 2187


def test_resync_never_goes_backwards():
    m = dc.Model(BASE, AS_AT, 2000 * U)
    c = dc.Clock(m, AS_AT * 1000)
    c.value((AS_AT + 1000) * 1000)               # +2,000,000
    high = c.displayed
    m2 = dc.Model(BASE + 1_000_000, AS_AT + 1000, 2000 * U)   # AOFM says we overshot by 1,000,000
    c.resync(m2, (AS_AT + 1000) * 1000)
    assert c.displayed == high
    c.value((AS_AT + 1001) * 1000)               # quarter rate while above target
    assert c.displayed == high + 500
    c.value((AS_AT + 3000) * 1000)               # target has caught up
    assert c.displayed == m2.target((AS_AT + 3000) * 1000) // U


def test_resync_upwards_snaps():
    m = dc.Model(BASE, AS_AT, 2000 * U)
    c = dc.Clock(m, AS_AT * 1000)
    c.value((AS_AT + 10) * 1000)
    m2 = dc.Model(BASE + 5_000_000, AS_AT + 10, 2000 * U)
    c.resync(m2, (AS_AT + 10) * 1000)
    assert c.displayed == BASE + 5_000_000


def test_clock_from_cached_value():
    m = dc.Model(BASE, AS_AT, 2000 * U)
    c = dc.Clock(m, (AS_AT + 100) * 1000, start_value_aud=BASE + 9_000_000)
    assert c.displayed == BASE + 9_000_000
    c2 = dc.Clock(m, (AS_AT + 100) * 1000, start_value_aud=5)
    assert c2.displayed == m.target((AS_AT + 100) * 1000) // U


def test_negative_dt_is_ignored():
    m = dc.Model(BASE, AS_AT, 2000 * U)
    c = dc.Clock(m, (AS_AT + 100) * 1000)
    a = c.value((AS_AT + 100) * 1000)
    b = c.value((AS_AT + 90) * 1000)
    assert b == a


def test_formatting():
    assert dc.group_thousands(0) == "0"
    assert dc.group_thousands(999) == "999"
    assert dc.group_thousands(1000) == "1,000"
    assert dc.group_thousands(1002841620000) == "1,002,841,620,000"
    assert dc.format_aud(1002841620000) == "$1,002,841,620,000"
    assert dc.format_rate(-1500) == "-$1,500/s"


def test_first_diff():
    assert dc.first_diff("abc", "abc") == -1
    assert dc.first_diff("abc", "abd") == 2
    assert dc.first_diff("$1,000", "$1,001") == 5
    assert dc.first_diff("999", "1000") == 0
    assert dc.first_diff("12", "123") == 2
