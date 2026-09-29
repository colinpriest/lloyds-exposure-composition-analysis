"""The tail diagnostics say what each one measures (frozen review of 21 September 2026, M05).

A constant rescaling of one group moves the |z| quantile ratios and no tail-shape statistic, so a
significant quantile ratio is extreme residual magnitude, not tail shape. These tests check both
properties on a rescaled copy of the same sample, and that the recorded results carry the label.
"""
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ritc_tail_shape as rts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sample():
    return np.random.default_rng(20260921).standard_t(4, 20000)


def test_a_rescaled_copy_moves_the_quantile_ratio_by_exactly_the_scale():
    z = _sample()
    for p in (95, 99):
        assert abs(rts.q_ratio_stat(0.6 * z, p) / rts.q_ratio_stat(z, p) - 0.6) < 1e-12


def test_a_rescaled_copy_moves_no_shape_statistic():
    z = _sample()
    assert abs(rts.hill_xi(0.6 * z) - rts.hill_xi(z)) < 1e-12
    assert abs(rts.far_spread(0.6 * z) - rts.far_spread(z)) < 1e-12
    assert abs(rts.t_nu(0.6 * z) - rts.t_nu(z)) < 0.05


def test_each_statistic_is_labelled_by_what_it_measures():
    assert rts.MEASURES["q95(|z|) ratio"] == "magnitude"
    assert rts.MEASURES["q99(|z|) ratio"] == "magnitude"
    for name in ("Student-t nu (MLE)", "GPD xi (|z| exceedances)", "Hill xi (top 15% |z|)",
                 "far spread (q99-q50)/(q90-q50)"):
        assert rts.MEASURES[name] == "shape", name


def test_the_recorded_results_carry_the_label():
    res = json.load(io.open(os.path.join(ROOT, "results", "ritc_tail_shape_results.json"),
                            encoding="utf-8"))
    for pop in res.values():
        for name, r in pop["tests"].items():
            assert r.get("measures") == rts.MEASURES[name], (name, r.get("measures"))


# ---- the Student-t nu's clip is reported as a bound (review of 29 September 2026, A-3d) ----
def test_a_clipped_nu_is_named_as_the_bound_it_sits_on():
    assert rts.nu_bound(rts.NU_CLIP[0]) == "lower" and rts.nu_bound(rts.NU_CLIP[1]) == "upper"
    assert rts.nu_bound(3.7) is None and rts.nu_bound(float("nan")) is None and rts.nu_bound(None) is None


def test_the_mle_reaches_each_clip_on_data_that_push_it_there():
    rng = np.random.default_rng(3)
    heavy, light = rts.t_nu(rng.standard_t(0.6, 400)), rts.t_nu(rng.standard_normal(4000))
    assert (heavy, light) == rts.NU_CLIP, "the MLE is clipped: the recorded value is the bound itself"
    assert rts.nu_bound(heavy) == "lower" and rts.nu_bound(light) == "upper"
    assert rts.nu_bound(rts.t_nu(rng.standard_t(4, 4000))) is None


def test_the_contrast_records_each_groups_bound_and_how_often_the_bootstrap_hit_one():
    rng = np.random.default_rng(5)
    z = np.concatenate([rng.standard_t(0.6, 300), rng.standard_normal(600)])
    ritc = np.r_[np.ones(300, bool), np.zeros(600, bool)]
    cluster = np.arange(900) // 3
    r = rts.cluster_contrast(z, cluster, ritc, rts.t_nu, "diff", np.random.default_rng(1), n=20,
                             bound_fn=rts.nu_bound)
    assert (r["ritc_at_bound"], r["clean_at_bound"]) == ("lower", "upper")
    assert 0 < r["n_boot_at_bound"] <= 20
    plain = rts.cluster_contrast(z, cluster, ritc, rts.hill_xi, "diff", np.random.default_rng(1), n=20)
    assert "ritc_at_bound" not in plain, "only the clipped statistic carries a bound"


def test_the_recorded_t_rows_say_where_the_clip_is():
    """DEFERRED-TO-REFIT: every Student-t row of the recorded result names the clip and each group's bound."""
    path = os.path.join(ROOT, "results", "ritc_tail_shape_results.json")
    d = json.load(io.open(path, encoding="utf-8"))
    rows = [blk["tests"]["Student-t nu (MLE)"] for blk in d.values()
            if isinstance(blk, dict) and "Student-t nu (MLE)" in blk.get("tests", {})]
    assert rows, "no Student-t row in the recorded result"
    for r in rows:
        assert r["clip"] == list(rts.NU_CLIP) and "n_boot_at_bound" in r
        for grp in ("ritc", "clean"):
            assert r[grp + "_at_bound"] == rts.nu_bound(r[grp]), (grp, r[grp], r[grp + "_at_bound"])
