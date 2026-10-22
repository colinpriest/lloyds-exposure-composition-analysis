#!/usr/bin/env python3
"""The size-banded donor benchmark (check_size_banded_benchmark.py).

  * the band: donors whose own reserves lie within [lo x R_target, hi x R_target], both ends included;
  * the legs: the band's raw severities, the same without the assumed-business donors, and the band transferred by the
    headline operator, each read by pool_quantile.var_q;
  * the honest counts: which order statistic each VaR reads, the donors expected beyond it, and the plain reading
    ("readable", "thin", "no estimate");
  * the operator's own figures are check_gamma0_vignette.py's record, or nothing is written;
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_size_banded_benchmark.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import check_size_banded_benchmark as SB
import transfer_operator as TO
from pool_quantile import var_q
from vignette_uncertainty import load_pool, load_ritc, load_targets, transfer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = (500.0, 0.01, 1.0)
TH = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.05, "nu_clean": 4.0, "nu_ritc": 6.0}


def _text(path):
    with io.open(path, encoding="utf-8") as _fh:
        return _fh.read()


def test_the_band_includes_both_ends():
    R = np.array([249.9, 250.0, 500.0, 1000.0, 1000.1])
    assert SB.band_mask(R, 500.0, (0.5, 2.0)).tolist() == [False, True, True, True, False]
    assert SB.BANDS[SB.PRIMARY_BAND] == (0.5, 2.0) and SB.BANDS["x0.667_to_x1.5"] == (1.0 / 1.5, 1.5)


@pytest.mark.parametrize("n,alpha,word,k", [(200, 0.995, "thin", 2), (199, 0.995, "no estimate", 1),
                                            (1000, 0.99, "readable", 11), (999, 0.99, "thin", 10),
                                            (294, 0.995, "thin", 2), (192, 0.995, "no estimate", 1)])
def test_the_plain_reading_of_a_bands_var(n, alpha, word, k):
    r = SB.reading(n, alpha)
    assert r["reading"].startswith(word) and r["k_from_top"] == k and r["n"] == n
    assert r["expected_beyond"] == pytest.approx(n * (1 - alpha))
    # the k-th largest is what var_q reads from n distinct values
    a = np.arange(n, dtype=float)
    assert var_q(a, alpha) == a[n - k]


def test_ordinals():
    assert [SB.ordinal(k) for k in (1, 2, 3, 4, 11, 12, 13, 21, 22, 103)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "103rd"]


def test_the_legs_of_one_band():
    rng = np.random.default_rng(5)
    S = rng.normal(0, 0.06, 40)
    R = np.exp(rng.normal(np.log(500), 0.9, 40))
    H = rng.uniform(0.1, 0.5, 40)
    ritc = np.zeros(40, bool)
    ritc[[1, 5, 9]] = True
    m = SB.band_mask(R, 500.0, (0.5, 2.0))
    lg = SB.legs(S, R, H, ritc, (500.0, 0.17), TH, CFG, m)
    assert np.array_equal(lg["band_raw"], S[m]) and np.array_equal(lg["band_raw_clean"], S[m & ~ritc])
    assert np.array_equal(lg["band_operator"], transfer(S[m], R[m], H[m], (500.0, 0.17), TH, CFG, ritc[m]))


@pytest.fixture(scope="module")
def small():
    return SB.compute(b=20)


def test_the_operators_figures_are_check_gamma0_vignettes_and_both_operators_are_stamped(small):
    o = small
    assert (o["operator"], o["operator_role"]) == ("size_only", "headline")
    assert (o["overlay_sensitivity"]["operator"], o["overlay_sensitivity"]["operator_role"]) == ("overlay", "sensitivity")
    rec = json.loads(_text(os.path.join(HERE, "results", "check_gamma0_vignette_results.json")))[TO.HEADLINE]["centre"]
    v1 = o["by_band"][SB.PRIMARY_BAND]["targets"]["V1"]["operator_full_pool"]["var"]
    assert (v1["0.99"], v1["0.995"]) == (rec["V1_v99"], rec["V1_v995"])
    assert o["by_band"][SB.PRIMARY_BAND]["V2_change_995"]["operator_full_pool"]["centre"] == rec["V2_d995"]


def test_the_counts_and_quantiles_are_the_pools(small):
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    targets = dict(zip(("V1", "V2_old", "V2_new"), load_targets()))
    for bname, band in SB.BANDS.items():
        for t, tg in targets.items():
            row = small["by_band"][bname]["targets"][t]
            m = SB.band_mask(R, tg[0], band)
            assert row["n_donors"] == int(m.sum()) and row["n_syndicates"] == len(set(synd[m].tolist()))
            assert row["n_assumed_business"] == int(ritc[m].sum())
            for a in SB.LEVELS:
                key = "%g" % a
                assert row["band_raw"]["var"][key] == var_q(S[m], a)
                assert row["band_raw"]["counts"][key] == SB.reading(int(m.sum()), a)
                rel = row["relative_to_operator_full_pool"]["band_raw"][key]
                assert rel == pytest.approx(row["band_raw"]["var"][key] / row["operator_full_pool"]["var"][key] - 1)
                iv = row["band_raw"]["resampling_interval"][key]
                assert iv["n_replicates"] + row["replicates_with_an_empty_band"] <= 20


def test_a_departure_from_the_vignette_record_is_refused(tmp_path, monkeypatch):
    rec = json.loads(_text(os.path.join(HERE, "results", "check_gamma0_vignette_results.json")))
    rec[TO.HEADLINE]["centre"]["V1_v995"] += 1e-9
    p = tmp_path / "g0.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(SB, "GAMMA0", p)
    with pytest.raises(SystemExit):
        SB.compute(b=2)


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT)
def test_the_record_reads_the_published_pool_and_says_where_the_band_is_too_thin():
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    with io.open(os.path.join(HERE, "results", "check_size_banded_benchmark_results.json"), encoding="utf-8") as _fh:
        rec = json.load(_fh)
    S = load_pool()[0]
    assert rec["pool"]["n_donors"] == len(S) and rec["primary_band"] == SB.PRIMARY_BAND
    for bname, blk in rec["by_band"].items():
        for t, row in blk["targets"].items():
            for leg in SB.LEGS:
                for key, c in row[leg]["counts"].items():
                    if c["n"]:
                        assert c["reading"].startswith(("readable", "thin", "no estimate")), (bname, t, leg, key)
                        assert ("no estimate" in c["reading"]) == (c["expected_beyond"] < SB.NO_ESTIMATE_BEYOND)
    import reproduce
    assert "runtime_seconds" not in reproduce._strip_volatile(rec)
