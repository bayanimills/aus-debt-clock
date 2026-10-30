"""WiFi bring-up, baseline fetch, and clock set. The radio is only on inside
sync(); everything else in the firmware runs with the CYW43 powered down.
"""
import time

_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def parse_http_date(s):
    """'Wed, 02 Sep 2026 02:00:09 GMT' -> (y, m, d, H, M, S)"""
    p = s.replace(",", " ").split()
    d, mon, y = int(p[1]), _MONTHS[p[2][:3]], int(p[3])
    hh, mm, ss = (int(x) for x in p[4].split(":"))
    return (y, mon, d, hh, mm, ss)


def parse_iso_date(s):
    """'2026-08-31' or '2026-08-31T00:00:00Z' -> (y, m, d, H, M, S)"""
    date, _, tm = s.partition("T")
    y, m, d = (int(x) for x in date.split("-"))
    hh = mm = ss = 0
    if tm:
        tm = tm.rstrip("Z")
        parts = tm.split(":")
        hh = int(parts[0])
        if len(parts) > 1:
            mm = int(parts[1])
        if len(parts) > 2:
            ss = int(float(parts[2]))
    return (y, m, d, hh, mm, ss)


def to_seconds(t6):
    """Six-tuple (UTC) -> seconds in this port's epoch."""
    y, m, d, hh, mm, ss = t6
    return time.mktime((y, m, d, hh, mm, ss, 0, 0))


def set_rtc(t6):
    import machine
    y, m, d, hh, mm, ss = t6
    wd = time.localtime(to_seconds(t6))[6]
    machine.RTC().datetime((y, m, d, wd, hh, mm, ss, 0))


def rtc_valid():
    return time.localtime()[0] >= 2025


def connect(ssid, password, timeout_s):
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                wlan.active(False)
                raise OSError("wifi timeout")
            time.sleep_ms(200)
    return wlan


def disconnect(wlan):
    try:
        wlan.disconnect()
    except Exception:
        pass
    try:
        wlan.active(False)
    except Exception:
        pass
    try:
        wlan.deinit()
    except Exception:
        pass


def fetch_baseline(url, auth_header="", timeout_s=15):
    """GET the baseline JSON. Returns (dict, http_date_string_or_None)."""
    import requests
    headers = {"User-Agent": "aus-debt-clock/0.1"}
    if auth_header:
        headers["Authorization"] = auth_header
    r = requests.get(url, headers=headers, timeout=timeout_s)
    try:
        if r.status_code != 200:
            raise OSError("HTTP %d" % r.status_code)
        data = r.json()
        date = None
        for k in r.headers:
            if k.lower() == "date":
                date = r.headers[k]
                break
    finally:
        r.close()
    for key in ("baseline_aud", "as_at", "rate_aud_per_s"):
        if key not in data:
            raise ValueError("baseline missing " + key)
    return data, date


def sync(ssid, password, url, auth_header="", wifi_timeout_s=20, http_timeout_s=15):
    """Bring WiFi up, fetch, set the RTC from the HTTP Date header, radio off.
    Returns the baseline dict. Raises on any failure; the radio is always
    shut down before the exception propagates.
    """
    wlan = None
    try:
        wlan = connect(ssid, password, wifi_timeout_s)
        data, date = fetch_baseline(url, auth_header, http_timeout_s)
        if date:
            try:
                set_rtc(parse_http_date(date))
            except Exception as e:
                print("rtc set failed:", e)
        return data
    finally:
        if wlan is not None:
            disconnect(wlan)
