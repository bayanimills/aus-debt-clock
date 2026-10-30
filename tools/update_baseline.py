#!/usr/bin/env python3
"""Regenerate data/baseline.json from AOFM's published AGS-on-issue figure.

Primary source: the AOFM home page, which prints "Australian Government
Securities on issue ... billion ... Face value as at <date>", updated each
Friday. Fallback: the Data Hub "Executive Summary" XLSX, row "Total AUD Main
Funding Instruments", which lags to month end. This script:

  1. fetches the home page and parses the weekly total and its as-at date;
  2. on failure, scrapes the Data Hub for the current XLSX link and reads it;
  3. computes the accrual rate from data/budget.json;
  4. writes data/baseline.json only if the content changed.

aofm.gov.au sometimes stalls python-requests; fetches fall back to curl.

Exit 0 on success, 1 on any failure. Never writes a partial file.
"""
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

import requests
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "data" / "budget.json"
OUT = ROOT / "data" / "baseline.json"

DATA_HUB = "https://www.aofm.gov.au/data-hub"
FALLBACK_XLSX = ("https://www.aofm.gov.au/sites/default/files/2025-06-06/"
                 "portfolio_aggregate_-_executive_summary_-_dealt.xlsx")
ROW_LABEL = "total aud main funding instruments"
# aofm.gov.au (Akamai) stalls non-browser user agents; a browser string gets through.
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}


def fetch(url, timeout=60):
    """GET bytes via requests, falling back to curl (aofm.gov.au stalls requests at times)."""
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"requests failed for {url} ({e}); trying curl")
    import subprocess
    out = subprocess.run(["curl", "-sSL", "--max-time", str(timeout), "-A", UA["User-Agent"], url],
                         capture_output=True, check=True)
    return out.stdout


HOME = "https://www.aofm.gov.au/"
HOME_RE = re.compile(
    r"Australian Government Securities on issue\*?\s*([\d,]+\.?\d*)\s*billion.*?"
    r"Face value as at (\d{1,2} \w+ \d{4})", re.S)


def read_weekly_print():
    """(value_aud, as_at_date) from the AOFM home page weekly print."""
    import html as _html
    page = fetch(HOME, 45).decode("utf-8", "replace")
    text = re.sub(r"<[^>]+>", " ", page)
    text = re.sub(r"\s+", " ", _html.unescape(text))
    m = HOME_RE.search(text)
    if not m:
        raise ValueError("weekly print not found on the home page")
    value = float(m.group(1).replace(",", "")) * 1e9
    as_at = dt.datetime.strptime(m.group(2), "%d %B %Y").date()
    return value, as_at


def find_xlsx_url():
    try:
        html = fetch(DATA_HUB, 45).decode("utf-8", "replace")
    except Exception as e:
        print(f"data hub fetch failed ({e}); using fallback URL")
        return FALLBACK_XLSX
    m = re.search(r'href="([^"]*portfolio_aggregate[^"]*executive_summary[^"]*\.xlsx)"', html, re.I)
    if not m:
        print("no executive-summary link on the data hub; using fallback URL")
        return FALLBACK_XLSX
    url = m.group(1)
    if url.startswith("/"):
        url = "https://www.aofm.gov.au" + url
    return url


def parse_header_date(cell):
    if isinstance(cell, (dt.datetime, dt.date)):
        return dt.date(cell.year, cell.month, cell.day)
    s = str(cell).strip()
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date header: {cell!r}")


def read_total(xlsx_bytes):
    wb = load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    # The label sits in column D (A-C are merged category cells), so match any cell.
    target = label_col = None
    for r in rows:
        for i, c in enumerate(r):
            if isinstance(c, str) and ROW_LABEL in c.strip().lower():
                target, label_col = r, i
                break
        if target is not None:
            break
    if target is None:
        raise ValueError(f"row '{ROW_LABEL}' not found")
    # right-most numeric cell to the right of the label
    col = None
    for i in range(len(target) - 1, label_col, -1):
        if isinstance(target[i], (int, float)):
            col = i
            break
    if col is None:
        raise ValueError("no numeric value on the total row")
    value = abs(float(target[col]))
    # header: nearest row above with a date in that column
    as_at = None
    for r in rows:
        if r is target:
            break
        if col < len(r) and r[col] is not None:
            try:
                as_at = parse_header_date(r[col])
            except ValueError:
                continue
    if as_at is None:
        raise ValueError("no date header above the value column")
    return value, as_at


def rate_from_budget(b):
    start = dt.date.fromisoformat(b["fy_start"])
    end = dt.date.fromisoformat(b["fy_end"])
    seconds = (end - start).total_seconds()
    return (float(b["gross_debt_end_bn"]) - float(b["gross_debt_start_bn"])) * 1e9 / seconds


def main():
    budget = json.loads(BUDGET.read_text())
    try:
        value, as_at = read_weekly_print()
        url = HOME
        source = "AOFM home page weekly print, face value of AGS on issue"
        print(f"weekly print: ${value:,.0f} as at {as_at}")
    except Exception as e:
        print(f"weekly print unavailable ({e}); falling back to the executive-summary XLSX")
        url = find_xlsx_url()
        print("xlsx:", url)
        value, as_at = read_total(fetch(url, 90))
        source = "AOFM Executive Summary XLSX, row 'Total AUD Main Funding Instruments' (dealt basis)"
    if not (5e11 < value < 5e12):
        raise ValueError(f"total {value:,.0f} outside sanity range")
    rate = rate_from_budget(budget)
    out = {
        "baseline_aud": int(round(value)),
        "as_at": as_at.isoformat(),
        "rate_aud_per_s": round(rate, 3),
        "rate_source": (f"{budget['source']} {budget['fy_label']}: "
                        f"${budget['gross_debt_start_bn']}bn -> ${budget['gross_debt_end_bn']}bn"),
        "baseline_source": source,
        "baseline_url": url,
        "generated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    text = json.dumps(out, indent=2) + "\n"
    if OUT.exists():
        old = json.loads(OUT.read_text())
        same = all(old.get(k) == out[k] for k in out if k != "generated")
        if same:
            print(f"unchanged: ${value:,.0f} as at {as_at}")
            return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: ${value:,.0f} as at {as_at}, rate ${rate:,.2f}/s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("FAILED:", e, file=sys.stderr)
        sys.exit(1)
