"""The two sensitivity refits of stage 3 (decisions D3-2 and D3-3, 4 October 2026): their inputs, their construction
and the form of their results, without sampling (the refits run on the PC).

check_margin_sensitivity.py refits the adopted model without the syndicates that state a management margin
(data/margin_disclosure.json), against a size-matched random control. check_skew_t.py refits it with a Jones-Faddy
skew-t shock and takes the headline VaR through the same estimator, against a delta = 0 control on two seeds.

Run:  python -m pytest src/test_sensitivity_refits.py -q
"""
import io
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import adopted_model as am  # noqa: E402
import check_margin_sensitivity as CM  # noqa: E402
import check_skew_t as CK  # noqa: E402
import vignette_uncertainty as VU  # noqa: E402


# ------------------------------------------------------------------ the margin register
def _register():
    with io.open(CM.MARGINS, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_margin_register_is_the_scan_read_and_classified():
    reg = _register()
    entries = reg["entries"]
    assert len(entries) == 132 and len({e["stem"] for e in entries}) == 132
    assert {e["class"] for e in entries} <= {"held", "conditional", "contradicting", "unclear"}
    by = {c: sorted(e["stem"] for e in entries if e["class"] == c) for c in ("contradicting", "conditional")}
    assert by["contradicting"] == ["2008_2023", "2015_2017"]
    assert len(by["conditional"]) == 12 and len({s.split("_")[0] for s in by["conditional"]}) == 6
    for e in entries:
        if e["class"] == "conditional":
            assert "may be applied" in e["quote"], e["stem"]
        if e["class"] == "contradicting":
            assert "no margin" in e["quote"], e["stem"]
    assert "HTML" in reg["_purpose"] and "lower bound" in reg["_purpose"]


def test_every_damaged_or_cut_quote_is_marked_for_the_pc():
    reg = _register()
    damaged = sorted(e["stem"] for e in reg["entries"] if "�" in e["quote"])
    assert damaged == sorted(["1856_2021", "2001_2020", "4711_2021", "727_2017", "727_2018", "727_2020", "727_2021",
                              "727_2022", "727_2023"])
    for e in reg["entries"]:
        whole = e["quote_is_the_whole_sentence"]
        assert whole != e["pc_reread"], e["stem"]
        if "�" in e["quote"]:
            assert e["pc_reread"], e["stem"]
        if whole:
            assert e["quote"][0].isupper() and e["quote"].endswith("."), e["stem"]


def test_the_variants_leave_out_28_32_and_34_syndicates():
    sets = CM.margin_variants()
    assert [len(sets[k]) for k in ("held_margin", "held_or_conditional", "any_scan_hit")] == [28, 32, 34]
    assert set(sets["held_margin"]) < set(sets["held_or_conditional"]) < set(sets["any_scan_hit"])
    assert set(sets["any_scan_hit"]) - set(sets["held_or_conditional"]) == {2008, 2015}
    assert _register()["_syndicates"]["counts"] == {"held": 28, "held_or_conditional": 32, "any_hit": 34}


def test_the_control_leaves_out_as_many_records_in_each_size_decile():
    S, R, H, yr, syn, ritc = am.load_sample()
    left_out = np.isin(syn, CM.margin_variants()["held_margin"])
    masks = CM.control_masks(R, left_out, 3, np.random.default_rng(1))
    dec = CM.size_deciles(R)
    for keep in masks:
        assert (~keep).sum() == left_out.sum()
        for d in range(CM.N_DECILES):
            assert ((~keep) & (dec == d)).sum() == (left_out & (dec == d)).sum()
    assert not np.array_equal(masks[0], masks[1])


def _fake_fit(mask, label):
    rng = np.random.default_rng(int(mask.sum()))
    draws = {p: rng.normal(float(am.headline()[p]["mean"]), 0.01, 200) for p in am.SHARED}
    return {"draws": draws, "max_rhat": 1.0, "divergences": 0, "guard_rows": [{"param": "k"}]}


def test_the_margin_record_has_its_variants_controls_and_reading():
    out = CM.run(n_control=2, fit_fn=_fake_fit)
    assert set(out["variants"]) == {"held_margin", "held_or_conditional", "any_scan_hit"}
    assert len(out["controls"]) == 2 and out["control"]["n_draws"] == 2
    held = out["variants"]["held_margin"]
    assert held["n"] + held["n_left_out"] == out["n_sample"]
    assert all(c["n_left_out"] == held["n_left_out"] for c in out["controls"])
    for name in out["variants"]:
        for p in CM.REPORT:
            row = out["comparison"][name][p]
            assert set(row) == {"shift_from_headline", "variant_mean", "control_range_of_means",
                                "variant_outside_control_range"}
    assert "indication" in out["reading"] and "not proof" in out["reading"]
    assert "lower bound" not in out["reading"] or "HTML" in out["flag_is_a_lower_bound"]
    json.dumps(out)


# ------------------------------------------------------------------ the skew-t
def test_delta_zero_is_the_student_t_and_the_adopted_graph():
    """At delta = 0 the Jones-Faddy density is the Student-t exactly, so the skew-t model with delta fixed at zero
    has the adopted block's log-density on the pinned reference data (test_model_variants' graph pin)."""
    from scipy import stats
    x = np.linspace(-8, 8, 33)
    for nu in (3.3, 4.7, 9.0):
        a, b = CK.jf_ab(nu, 0.0)
        assert np.allclose(CK.jf_cdf(x, a, b), stats.t.cdf(x, nu), atol=1e-12)
        assert np.allclose(CK.jf_ppf(stats.t.cdf(x, nu), a, b), x, atol=1e-7)
        assert CK.implied_shock(nu, 0.0)["median"] == pytest.approx(0.0, abs=1e-12)
        assert CK.implied_shock(nu, 0.0)["mean"] == pytest.approx(0.0, abs=1e-12)
    ref = np.load(os.path.join(HERE, "tests_data", "adopted_block_reference.npz"))
    m = CK.build_model(ref["S"], ref["R"], ref["H"], ref["yr"], ref["ritc"], fix_delta=0.0)
    # PyMC's SkewStudentT and StudentT log-densities agree to about 1e-8 per observation at a = b = nu/2; summed
    # over the reference data that is 1.4e-6, so the pin's 1e-8 is loosened to 1e-5 (a delta of 0.01 moves it by 0.59)
    assert abs(float(m.compile_logp()(m.initial_point())) - float(ref["lp"])) < 1e-5
    assert "delta" not in [v.name for v in m.free_RVs]
    assert "delta" in [v.name for v in CK.build_model(ref["S"], ref["R"], ref["H"], ref["yr"], ref["ritc"]).free_RVs]


def test_a_positive_delta_leans_the_shock_adverse():
    shock = CK.implied_shock(4.7, 0.3)
    assert shock["a"] > shock["b"] and shock["median"] > 0 and shock["mean"] > shock["median"]
    assert CK.implied_shock(4.7, -0.3)["median"] == pytest.approx(-shock["median"])


def test_the_skewed_ritc_map_is_deritc_resid_at_delta_zero():
    z = np.array([-4.0, -1.0, 0.0, 0.5, 2.0, 6.0])
    ritc = np.array([True, True, True, False, True, True])
    th = {"nu_clean": 4.7, "nu_ritc": 3.4}
    assert np.allclose(CK.deritc_skew(z, dict(th, delta=0.0), ritc), VU.deritc_resid(z, th, ritc), atol=1e-9)
    moved = CK.deritc_skew(z, dict(th, delta=0.4), ritc)
    assert moved[3] == z[3] and not np.allclose(moved[ritc], VU.deritc_resid(z, th, ritc)[ritc])


def test_the_estimator_is_the_headlines_at_delta_zero():
    """With the published draws and delta = 0, the replicates are vignette_uncertainty's own: the same pool,
    weights, posterior indices and quantile give the published V1 and V2 VaR99.5 replicate summaries."""
    draws, *_ = VU.load_draws()
    out = CK.vignette_vars(draws)
    with io.open(os.path.join(HERE, "results", "vignette_uncertainty_results.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    for key, block in (("V1_adj_v995", rec["vignette1"]["adjusted"]["var995"]),
                       ("V2_new_v995", rec["vignette2"]["adjusted_new"]["var995"])):
        assert out[key]["mean"] == pytest.approx(block["mean"], abs=1e-12)
        assert out[key]["interval_95"] == pytest.approx([block["lo"], block["hi"]], abs=1e-12)


def _fit_record(delta_mean, ok=True):
    rng = np.random.default_rng(3)
    draws = {p: rng.normal(float(am.headline()[p]["mean"]), 0.01, 300) for p in am.SHARED}
    draws["delta"] = rng.normal(delta_mean, 0.05, 300)
    return {"draws": draws, "max_rhat": 1.0, "divergences": 0, "reproduces_headline": ok, "guard_rows": []}


def _vars(v1, v2):
    return {"V1_adj_v995": {"median": v1, "mean": v1, "interval_95": [v1, v1]},
            "V2_new_v995": {"median": v2, "mean": v2, "interval_95": [v2, v2]}}


@pytest.mark.parametrize("skew_v1,flag", [(0.30, False), (0.33, True), (0.2985, False)])
def test_the_flag_needs_a_move_beyond_5pct_and_the_control_spread(skew_v1, flag):
    out = CK.assemble(_fit_record(0.2), _vars(skew_v1, 0.275), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.297, 0.274), _vars(0.299, 0.276)])
    assert out["flag_for_decision"] is flag
    m = out["vignette_moves"]["V1_adj_v995"]
    assert m["control_seed_spread"] == pytest.approx(0.002) and m["control_mean_of_medians"] == pytest.approx(0.298)
    assert set(out["skew_fit"]["implied_shock_at_posterior_mean"]) == {"delta", "clean", "ritc"}
    assert out["controls_reproduce_the_headline"] is True
    json.dumps(out)


def test_a_large_move_inside_a_wide_control_spread_is_not_flagged():
    out = CK.assemble(_fit_record(0.2), _vars(0.33, 0.275), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.26, 0.274), _vars(0.36, 0.276)])
    assert out["flag_for_decision"] is False


def test_the_skew_record_carries_both_operator_stamps():
    """check_skew_t.py imports transfer_operator, so test_operator_binding holds its record to both stamps: the
    headline size-only figures at the top level and the overlay as the labelled sensitivity."""
    from test_operator_binding import _stamps
    out = CK.assemble(_fit_record(0.2), _vars(0.30, 0.275), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.297, 0.274), _vars(0.299, 0.276)],
                      overlay=(_vars(0.32, 0.29), [_vars(0.31, 0.28), _vars(0.312, 0.281)]))
    stamps = [s for _w, s in _stamps(out)]
    assert out["operator"] == "size_only" and out["operator_role"] == "headline"
    assert {s["operator"] for s in stamps} == {"size_only", "overlay"}
    assert out["overlay_sensitivity"]["operator_role"] == "sensitivity"
    assert out["flag_for_decision"] is False
