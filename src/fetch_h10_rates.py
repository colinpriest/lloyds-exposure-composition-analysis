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


def main():
    print(f"Fetching {URL}")
    html = fetch_html()
    series = parse_series(html)
    print(f"parsed {len(series)} daily observations "
          f"({min(series)} .. {max(series)})")
    picks = year_end_picks(series, range(2013, 2026))
    out = {
        "source": {
            "name": ("Federal Reserve H.10 Foreign Exchange Rates, historical data, "
                     "United Kingdom"),
            "url": URL,
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
