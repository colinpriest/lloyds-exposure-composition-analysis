"""Fetch GBP/USD spot exchange rates from the Federal Reserve H.10 statistical release.

Source
------
  https://www.federalreserve.gov/releases/h10/hist/dat00_uk.htm

This is the Fed's H.10 "Foreign Exchange Rates" historical data page for the United
Kingdom: business-day spot rates, quoted as **US dollars per 1 pound sterling**
(the UK series is one of the few H.10 series quoted USD-per-unit). Historically these
are the noon buying rates in New York for cable transfers certified by the Federal
Reserve Bank of New York. Coverage: 3 Jan 2000 to present. Holidays/weekends are
absent or marked "ND".

Rate selection rule (documented in docs/fx-conversion.md)
---------------------------------------------------------
Lloyd's syndicate annual accounts have a 31 December reporting date. For reporting
year Y we use the LAST PUBLISHED business-day rate ON OR BEFORE 31 December Y
("reporting-date spot rate"). The exact date used is recorded per year.

Writes fx_rates_h10.json:
  - metadata (source URL, retrieval timestamp, series definition, selection rule)
  - the full daily series (date -> USD per GBP) for audit/reproducibility
  - year_end_rates: {year: {date_used, usd_per_gbp}} for 2013-2025 where available

Usage:  python src/fetch_h10_rates.py
"""
import io, json, re, sys, datetime, urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUT = SCRIPT_DIR / "model" / "fx_rates_h10.json"
URL = "https://www.federalreserve.gov/releases/h10/hist/dat00_uk.htm"
# The release runs to the present, so a file that stored everything changed with
# every fetch and the run report could not validate against its own commit (round
# 53). The stored series ends at a fixed date that covers every year-end pick the
# analysis uses (2013-2025); the bound is recorded in the file.
SERIES_END = "2025-12-31"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def fetch_html():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_series(html):
    """Parse Date/Rate <td> cell pairs into {iso_date: usd_per_gbp}."""
    cells = re.findall(r"<t[dh][^>]*>([^<]*)</t[dh]>", html)
    series = {}
    i = 0
    while i < len(cells) - 1:
        d = cells[i].strip()
        m = re.fullmatch(r"(\d{1,2})-([A-Z]{3})-(\d{2,4})", d)
        if m:
            v = cells[i + 1].strip()
            day, mon, yy = int(m.group(1)), MONTHS.get(m.group(2)), int(m.group(3))
            if mon and v and v != "ND":
                year = yy + 2000 if yy < 100 else yy
                try:
                    series[datetime.date(year, mon, day).isoformat()] = float(v)
                except ValueError:
                    pass
            i += 2
        else:
            i += 1
    return series


def year_end_picks(series, years):
    picks = {}
    dates = sorted(series)
    for y in years:
        cutoff = f"{y}-12-31"
        elig = [d for d in dates if d <= cutoff and d >= f"{y}-12-01"]
        if elig:
            d = elig[-1]
            picks[str(y)] = {"date_used": d, "usd_per_gbp": series[d]}
    return picks


def check_picks(picks, series):
    """What is wrong with `picks` under the selection rule, [] when nothing is.

    Each year's date must be the last published date on or before 31 December of that year (and in that
    December), a weekday, and its rate the series' rate on that date. The rule was stated here and in
    docs/fx-conversion.md and tested nowhere until the review of 29 September 2026 (test upgrade 4);
    src/test_fx_rate_selection.py runs this on the committed file and on planted errors.
    """
    problems = []
    dates = sorted(series)
    for y, p in sorted(picks.items()):
        december = [d for d in dates if f"{y}-12-01" <= d <= f"{y}-12-31"]
        if not december:
            problems.append(f"{y}: the series has no December rate, yet {p['date_used']} was picked")
            continue
        if p["date_used"] != december[-1]:
            problems.append(f"{y}: {p['date_used']} is not the last published rate on or before 31 December "
                            f"({december[-1]})")
        if datetime.date.fromisoformat(p["date_used"]).weekday() >= 5:
            problems.append(f"{y}: {p['date_used']} is a weekend, not a business day")
        if series.get(p["date_used"]) != p["usd_per_gbp"]:
            problems.append(f"{y}: {p['usd_per_gbp']} is not the series' rate on {p['date_used']}")
    return problems


def main():
    print(f"Fetching {URL}")
    html = fetch_html()
    series = parse_series(html)
    print(f"parsed {len(series)} daily observations "
          f"({min(series)} .. {max(series)})")
    series = {d: v for d, v in series.items() if d <= SERIES_END}
    picks = year_end_picks(series, range(2013, 2026))
    problems = check_picks(picks, series)
    if problems:
        raise SystemExit("the year-end picks break the selection rule:\n  " + "\n  ".join(problems))
    out = {
        "source": {
            "name": ("Federal Reserve H.10 Foreign Exchange Rates, historical data, "
                     "United Kingdom"),
            "url": URL,
            "series_end": SERIES_END,
            "series": ("Spot exchange rate, United Kingdom pound, quoted as US dollars "
                       "per 1 pound sterling; business-day (noon buying rates in New York "
                       "for cable transfers, as certified by the FRBNY)"),
            "retrieved_utc": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds"),
        },
        "selection_rule": ("Reporting-date spot rate: last published business-day rate on "
                           "or before 31 December of the reporting year (Lloyd's annual "
                           "accounts report at 31 December). Conversion: GBP = USD / rate."),
        "year_end_rates": picks,
        "n_daily_observations": len(series),
        "daily_series": series,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    for y, p in picks.items():
        print(f"  {y}: {p['usd_per_gbp']:.4f} USD/GBP  (rate date {p['date_used']})")


if __name__ == "__main__":
    sys.exit(main())
