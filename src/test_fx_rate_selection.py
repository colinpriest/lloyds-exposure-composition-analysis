#!/usr/bin/env python3
"""The FX date rule, at each level where it is decided.

Rule (fetch_h10_rates.py, docs/fx-conversion.md): a USD-presented report for reporting year Y is converted
at the last published H.10 business-day rate on or before 31 December Y. The review of 29 September 2026
(test upgrade 4) found the rule stated and never tested, so a pick one business day late, a weekend date
or a rate from the wrong day would all have passed. These tests hold it on synthetic series (weekend,
holiday gap, a rate after the year end, a December with no rate), on the committed rate file, and on
every converted record in the model sample.

Run:  python -m pytest src/test_fx_rate_selection.py -q
"""
import datetime
import io
import json
import os

import pytest

import fetch_h10_rates as fx

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(rel):
    path = os.path.join(HERE, rel)
    if not os.path.exists(path):
        pytest.skip("%s not present in this checkout" % rel)
    return json.load(io.open(path, encoding="utf-8"))


# ------------------------------------------------------------ year_end_picks on known series ------
def test_a_weekend_year_end_takes_the_friday_before():
    # 31 December 2016 was a Saturday
    series = {"2016-12-29": 1.22, "2016-12-30": 1.2337, "2017-01-03": 1.2290}
    assert fx.year_end_picks(series, [2016]) == {"2016": {"date_used": "2016-12-30", "usd_per_gbp": 1.2337}}


def test_a_holiday_gap_takes_the_last_published_rate():
    # 31 December 2021 (a Friday) published no rate ("ND")
    series = {"2021-12-28": 1.34, "2021-12-29": 1.345, "2021-12-30": 1.35, "2022-01-03": 1.349}
    assert fx.year_end_picks(series, [2021])["2021"]["date_used"] == "2021-12-30"


def test_a_rate_after_the_year_end_is_never_used():
    series = {"2019-12-13": 1.33, "2020-01-02": 1.32}
    assert fx.year_end_picks(series, [2019])["2019"] == {"date_used": "2019-12-13", "usd_per_gbp": 1.33}


def test_the_year_end_itself_is_on_or_before():
    series = {"2013-12-30": 1.65, "2013-12-31": 1.6574}
    assert fx.year_end_picks(series, [2013])["2013"]["date_used"] == "2013-12-31"


def test_a_december_without_a_rate_gets_no_pick_rather_than_a_stale_one():
    assert fx.year_end_picks({"2018-11-30": 1.27, "2019-01-02": 1.26}, [2018]) == {}


# ------------------------------------------------------------ the rule's own check ------
def _good():
    series = {"2016-12-29": 1.22, "2016-12-30": 1.2337, "2017-12-28": 1.34, "2017-12-29": 1.3529}
    return fx.year_end_picks(series, [2016, 2017]), series


def test_the_check_passes_the_rules_own_picks():
    picks, series = _good()
    assert fx.check_picks(picks, series) == []


@pytest.mark.parametrize("year,date_used,rate,problem", [
    ("2016", "2016-12-29", 1.22, "not the last published rate"),     # one business day early
    ("2016", "2017-01-03", 1.2290, "not the last published rate"),   # one business day late
    ("2016", "2016-12-31", 1.2337, "weekend"),                       # the calendar year end, a Saturday
    ("2017", "2017-12-29", 1.3530, "not the series' rate"),         # right day, retyped rate
])
def test_the_check_refuses_a_planted_wrong_pick(year, date_used, rate, problem):
    picks, series = _good()
    series = dict(series, **{"2017-01-03": 1.2290})
    picks[year] = {"date_used": date_used, "usd_per_gbp": rate}
    found = fx.check_picks(picks, series)
    assert found and any(problem in p for p in found), found


# ------------------------------------------------------------ the committed file ------
def test_the_committed_picks_follow_the_rule_and_reproduce_from_the_series():
    d = _load("model/fx_rates_h10.json")
    picks, series = d["year_end_rates"], d["daily_series"]
    assert fx.check_picks(picks, series) == []
    years = [int(y) for y in picks]
    assert fx.year_end_picks(series, years) == picks, "the file's picks are not the rule applied to its own series"
    assert years == list(range(2013, 2026)), years
    weekend_years = [y for y in years if datetime.date(y, 12, 31).weekday() >= 5]
    assert weekend_years and all(picks[str(y)]["date_used"] < "%d-12-31" % y for y in weekend_years), \
        "a year whose 31 December fell at a weekend must use an earlier business day"


def test_every_converted_record_uses_its_years_pick():
    picks = _load("model/fx_rates_h10.json")["year_end_rates"]
    obs = _load("model/exposure_results.json")["observations"]
    converted = [o for o in obs if o.get("fx_applied")]
    assert converted, "no USD-converted record: this test has lost its subject"
    for o in converted:
        pick = picks[str(o["year"])]
        assert o["report_currency"] == "USD", (o["syndicate"], o["year"])
        assert (o["fx_rate_date"], o["fx_rate_usd_per_gbp"]) == (pick["date_used"], pick["usd_per_gbp"]), \
            (o["syndicate"], o["year"])
    for o in obs:
        if not o.get("fx_applied"):
            assert o.get("fx_rate_date") is None and o.get("fx_rate_usd_per_gbp") is None, \
                (o["syndicate"], o["year"])
