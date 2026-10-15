#!/usr/bin/env python3
"""Figure 4's clean residuals in the tails, as results/goodness_of_fit_results.json records them (clean_tail).

The manuscript's Section 4.6 prints the clean residuals beyond +3 and -3, the syndicates the extremes come from, and the
tail-skew ratio (q90 - q50)/(q50 - q10) with a by-syndicate cluster-bootstrap interval (the review of 2 October 2026,
P-16). Until 15 October 2026 only the manuscript's claim registry computed them, so no analysis output held them. Here:

  * the ratio's definition, the counts beyond +/-3, and the RITC records left out, on synthetic residuals;
  * the bootstrap resamples syndicates, not records: syndicates holding identical residuals give every resample the
    full sample's ratio;
  * the record's interval equals a by-syndicate bootstrap written out here, at the record's resamples and seed;
  * the committed record is present, consistent, and equal to clean_tail on the committed inputs.

Run:  python -m pytest src/test_clean_tail.py -q
"""
import io
import json
import os

import numpy as np
import pytest
from scipy import stats

import make_paper_figures as MPF          # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(HERE, "results", "goodness_of_fit_results.json")
#: sigma = sd_undiv everywhere: sd_div = 0 removes the size term, so z = S / UNIT
UNIT = 0.5
FLAT = {"k": 0.5, "gamma": 0.0, "sd_undiv": UNIT, "sd_div": 0.0, "nu_clean": 5.0}
KEYS = {"residual", "n_clean", "nu_clean", "above_3", "below_3", "n_extremes", "expected_per_tail",
        "n_syndicates_with_extremes", "extremes_by_syndicate", "extremes_by_year", "tail_skew_ratio",
        "tail_skew_ratio_definition", "interval_95", "bootstrap"}


def _synthetic(z, syn, yr, ritc):
    z = np.asarray(z, float)
    n = len(z)
    return dict(S=z * UNIT, R=np.full(n, 100.0), H=np.full(n, 0.5), ritc=np.asarray(ritc, bool),
                syn=np.asarray(syn, int), yr=np.asarray(yr, int))


def _run(d, **kw):
    return MPF.clean_tail(d["S"], d["R"], d["H"], d["ritc"], d["syn"], d["yr"], FLAT, **kw)


def test_the_ratio_is_upper_over_lower_spread():
    x = np.arange(101.0)                  # q10 = 10, q50 = 50, q90 = 90
    assert MPF.tail_skew_ratio(x) == pytest.approx(1.0)
    y = np.where(x > 50, 50 + 2 * (x - 50), x)    # the upper half stretched twice: q90 = 130
    assert MPF.tail_skew_ratio(y) == pytest.approx((130 - 50) / (50 - 10))


def test_counts_beyond_three_leave_out_the_ritc_records():
    rng = np.random.default_rng(1)
    body = list(rng.uniform(-2, 2, 40))
    z = body + [3.5, 4.0, 5.0, -3.2] + [9.0, -9.0, 8.0]          # the last three are RITC records
    syn = [100 + i % 8 for i in range(40)] + [7, 7, 8, 9] + [7, 7, 50]
    yr = [2015 + i % 5 for i in range(40)] + [2020, 2021, 2020, 2016] + [2020, 2020, 2020]
    ritc = [False] * 44 + [True] * 3
    r = _run(_synthetic(z, syn, yr, ritc), resamples=50)
    assert set(r) == KEYS
    assert (r["n_clean"], r["above_3"], r["below_3"], r["n_extremes"]) == (44, 3, 1, 4)
    assert r["extremes_by_syndicate"] == [[7, 2], [8, 1], [9, 1]]
    assert r["n_syndicates_with_extremes"] == 3
    assert r["extremes_by_year"] == {"2016": 1, "2020": 2, "2021": 1}
    assert r["expected_per_tail"] == pytest.approx(44 * stats.t.sf(3.0, df=5.0))
    assert r["nu_clean"] == 5.0
    # the bootstrap's unit count is the clean records' syndicates: 8 in the body and 7, 8, 9; 50 is RITC only
    assert r["bootstrap"]["n_syndicates"] == 11
    zc = np.array(z[:44])
    assert r["tail_skew_ratio"] == pytest.approx(MPF.tail_skew_ratio(zc))


def test_the_bootstrap_resamples_syndicates_not_records():
    """Six syndicates holding the same skewed residuals: any draw of syndicates pools copies of one set, whose
    percentiles are the full sample's, so the interval is the point. A record-level bootstrap would spread it."""
    one = np.array([-1.5, -1.0, -0.5, -0.2, 0.0, 0.1, 0.4, 0.9, 1.8, 3.5])
    z = np.tile(one, 6)
    syn = np.repeat(np.arange(1, 7), len(one))
    d = _synthetic(z, syn, np.full(len(z), 2020), np.zeros(len(z), bool))
    r = _run(d, resamples=200)
    assert r["bootstrap"]["n_syndicates"] == 6
    assert r["interval_95"][0] == pytest.approx(r["tail_skew_ratio"], abs=1e-12)
    assert r["interval_95"][1] == pytest.approx(r["tail_skew_ratio"], abs=1e-12)


def _reference(zc, sc, resamples, seed):
    """The by-syndicate cluster bootstrap written out: the manuscript claim registry's computation (adverse_lean)."""
    rng = np.random.default_rng(seed)
    groups = {s: zc[sc == s] for s in np.unique(sc)}
    keys = np.array(list(groups))
    boot = np.empty(resamples)
    for b in range(resamples):
        pick = rng.choice(keys, size=len(keys), replace=True)
        q10, q50, q90 = np.percentile(np.concatenate([groups[k] for k in pick]), [10, 50, 90])
        boot[b] = (q90 - q50) / (q50 - q10)
    return [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def test_the_interval_is_the_written_out_bootstrap_at_the_seed():
    rng = np.random.default_rng(7)
    n = 300
    syn = rng.integers(1, 40, n)
    z = stats.t.rvs(4, size=n, random_state=rng) + 0.3 * rng.exponential(size=n)
    ritc = rng.uniform(size=n) < 0.1
    d = _synthetic(z, syn, rng.integers(2014, 2025, n), ritc)
    r = _run(d, resamples=300, seed=11)
    assert r["bootstrap"]["resamples"] == 300 and r["bootstrap"]["seed"] == 11
    assert r["interval_95"] == _reference(z[~ritc], syn[~ritc], 300, 11)
    assert r["interval_95"] != _reference(z[~ritc], syn[~ritc], 300, 12)


def test_the_paper_s_resamples_and_seed():
    """The manuscript prints 4,000 resamples; its claim registry recomputes with seed 20261006."""
    assert (MPF.CLEAN_TAIL_RESAMPLES, MPF.CLEAN_TAIL_SEED) == (4000, 20261006)


@pytest.fixture(scope="module")
def record():
    d = json.load(io.open(RECORD, encoding="utf-8"))
    assert "clean_tail" in d, "results/goodness_of_fit_results.json holds no clean_tail record"
    return d["clean_tail"]


def test_the_record_is_present_and_consistent(record):
    assert set(record) == KEYS
    assert record["n_extremes"] == record["above_3"] + record["below_3"]
    assert record["n_extremes"] == sum(c for _, c in record["extremes_by_syndicate"])
    assert record["n_extremes"] == sum(record["extremes_by_year"].values())
    assert record["n_syndicates_with_extremes"] == len(record["extremes_by_syndicate"])
    lo, hi = record["interval_95"]
    assert lo < record["tail_skew_ratio"] < hi
    b = record["bootstrap"]
    assert (b["resamples"], b["seed"]) == (MPF.CLEAN_TAIL_RESAMPLES, MPF.CLEAN_TAIL_SEED)
    assert b["percentiles"] == [2.5, 97.5] and b["kind"] == "by-syndicate cluster bootstrap"


def test_the_record_is_clean_tail_on_the_committed_inputs(record):
    S, R, H, yr, ritc, cal, _cal_gf, _corpus = MPF.load()
    syn = MPF.syndicates()
    assert len(syn) == len(S)
    assert MPF.clean_tail(S, R, H, ritc, syn, yr, cal) == record
