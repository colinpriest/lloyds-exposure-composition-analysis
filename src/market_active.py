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


def sample_overlap(keys, path=None):
    """The sample's syndicate-years set against each official list: {year: dict} for 2020-2024 only.

    `keys` is an iterable of (syndicate, year) pairs. For each year with an official list the entry holds `listed`
    (the list's length), `sample` (the sample's records that year), `in_list` (those whose syndicate is on that year's
    list: the true intersection), and `off_list` (the sample's syndicates that year that are not on it, sorted). The
    sample and the list are different populations, so `sample / listed` is a ratio, not a coverage; `in_list / listed`
    is the share of the listed syndicates the sample holds. 2014-2019 have a published count and no list, so there is
    no entry for them: whether a sample syndicate was active in those years cannot be checked."""
    by_year = {}
    for s, y in keys:
        by_year.setdefault(int(y), set()).add(int(s))
    out = {}
    for y, listed in sorted(official_lists(path).items()):
        seen = by_year.get(y, set())
        out[y] = dict(listed=len(listed), sample=len(seen), in_list=len(seen & listed),
                      off_list=sorted(seen - listed))
    return out
