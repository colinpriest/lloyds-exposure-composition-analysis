"""Active Lloyd's syndicates by year: the denominator of every coverage figure.

2014-2019: Lloyd's Annual Reports and SFCRs (counts only; the BoE/PRA January 2015 register lists about 101,
including run-off and RITC vehicles). 2020-2024: Lloyd's official "List of active Syndicates & Managing Agent"
spreadsheets, as data/market_active_syndicates.json holds them. That file is the per-year sheets of the extraction's
workbook syndicate_reports/Lloyds_Syndicates_2014_2024.xlsx, built from Lloyd's official files, and
src/test_market_active.py holds the two together.

Every script that states coverage reads the counts here. Typed copies of the list's counts in the coverage figure
and the systemic-share note carried Syndicate 33's omission from the list (it was missing in every year 2020-2024;
round 62, fourth cycle) where the file alone would have been corrected.
"""
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "market_active_syndicates.json"
WORKBOOK = ROOT / "syndicate_reports" / "Lloyds_Syndicates_2014_2024.xlsx"
#: active syndicates before the official lists begin (Lloyd's Annual Reports and SFCRs)
MARKET_AR = {2014: 92, 2015: 94, 2016: 99, 2017: 95, 2018: 99, 2019: 93}


def official_lists(path=None):
    """{year: set of syndicate numbers} from the official lists, 2020-2024."""
    with io.open(str(path or LIST), encoding="utf-8") as fh:
        return {int(y): set(v) for y, v in json.load(fh).items()}


def active_by_year(path=None):
    """{year: active syndicates}, 2014-2024: the annual-report counts, then the official lists' lengths."""
    out = dict(MARKET_AR)
    out.update({y: len(v) for y, v in official_lists(path).items()})
    return dict(sorted(out.items()))


def active_total(path=None):
    """Active syndicate-years over 2014-2024."""
    return sum(active_by_year(path).values())
