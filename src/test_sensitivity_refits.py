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
    # the PC rescan of 5 October 2026 (working-sample filings only; the 2024 HTML, every 2014 filing, the image-only PDFs
    # through the OCR cache, the two stage-3 entrants): 132 -> 193 entries
    assert len(entries) == 193 and len({e["stem"] for e in entries}) == 193
    assert {e["class"] for e in entries} <= {"held", "conditional", "contradicting", "unclear"}
    by = {c: sorted(e["stem"] for e in entries if e["class"] == c) for c in ("contradicting", "conditional")}
    assert by["contradicting"] == ["1301_2015", "1301_2016", "1301_2017", "1301_2018", "2008_2016", "2008_2018",
                                   "2008_2019", "2008_2023", "2015_2015", "2015_2016", "2015_2017", "2015_2018"]
    assert sum(e["class"] == "held" for e in entries) == 168 and sum(e["class"] == "unclear" for e in entries) == 1
    assert len(by["conditional"]) == 12 and len({s.split("_")[0] for s in by["conditional"]}) == 6
    for e in entries:
        if e["class"] == "conditional":
            assert "may be applied" in e["quote"], e["stem"]
        if e["class"] == "contradicting":
            assert "no margin" in e["quote"], e["stem"]
    assert "HTML" in reg["_purpose"] and "lower bound" in reg["_purpose"]


def test_every_damaged_or_cut_quote_is_marked_for_the_pc():
    reg = _register()
    # the PC re-read the nine damaged quotes and every cut snippet from the filing on 5 October 2026: every quote is now a
    # whole sentence, none carries a damaged character, none is marked for a re-read
    damaged = sorted(e["stem"] for e in reg["entries"] if "�" in e["quote"])
    assert damaged == []
    assert not any(e["pc_reread"] for e in reg["entries"])
    for e in reg["entries"]:
        whole = e["quote_is_the_whole_sentence"]
        assert whole != e["pc_reread"], e["stem"]
        if "�" in e["quote"]:
            assert e["pc_reread"], e["stem"]
        if whole:
            assert e["quote"][0].isupper() and e["quote"].endswith("."), e["stem"]


def test_the_variants_leave_out_31_35_and_37_syndicates():
    sets = CM.margin_variants()
    assert [len(sets[k]) for k in ("held_margin", "held_or_conditional", "any_scan_hit")] == [31, 35, 37]
    assert set(sets["held_margin"]) < set(sets["held_or_conditional"]) < set(sets["any_scan_hit"])
    assert set(sets["any_scan_hit"]) - set(sets["held_or_conditional"]) == {2008, 2015}
    assert _register()["_syndicates"]["counts"] == {"held": 31, "held_or_conditional": 35, "any_hit": 37}


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


def test_the_syndicate_control_leaves_out_whole_syndicates_matched_on_size_and_records():
    S, R, H, yr, syn, ritc = am.load_sample()
    for name, synds in CM.margin_variants().items():
        out = np.isin(syn, synds)
        masks, tries = CM.syndicate_control_masks(R, syn, synds, 4, np.random.default_rng(1), ritc=ritc,
                                                  ritc_tol=CM.RITC_TOLERANCE)
        assert len(masks) == 4 and tries >= 4
        keys = set()
        for keep in masks:
            gone = set(syn[~keep].tolist())
            # whole syndicates: every record of a syndicate left out is left out, none of its records is kept
            assert not gone & set(syn[keep].tolist()), name
            assert len(gone) == len(synds), name
            # drawn from the syndicates the variant keeps: none of the variant's own
            assert not gone & set(synds), name
            # within the tolerance of the variant's records left out and their share of the size proxy
            assert abs((~keep).sum() - out.sum()) <= CM.MATCH_TOLERANCE * out.sum()
            assert abs(R[~keep].sum() - R[out].sum()) <= CM.MATCH_TOLERANCE * R[out].sum()
            # and the RITC records left out within the tolerance of the variant's, so the RITC count kept is about its
            assert abs(int(ritc[~keep].sum()) - int(ritc[out].sum())) <= CM.RITC_TOLERANCE, name
            keys.add(tuple(sorted(gone)))
        assert len(keys) == 4, "the draws are distinct"


def test_the_syndicate_control_matches_the_variants_size_strata():
    S, R, H, yr, syn, ritc = am.load_sample()
    synds = CM.margin_variants()["held_or_conditional"]
    us = np.array(sorted(set(syn.tolist())))
    total = np.array([R[syn == s].sum() for s in us])
    edges = np.percentile(total, np.linspace(0, 100, CM.N_SYNDICATE_STRATA + 1))
    edges[-1] += 1e-9
    stratum = np.clip(np.digitize(total, edges) - 1, 0, CM.N_SYNDICATE_STRATA - 1)
    masks, _ = CM.syndicate_control_masks(R, syn, synds, 3, np.random.default_rng(2))
    want = np.bincount(stratum[np.isin(us, synds)], minlength=CM.N_SYNDICATE_STRATA)
    for keep in masks:
        got = np.bincount(stratum[np.isin(us, sorted(set(syn[~keep].tolist())))], minlength=CM.N_SYNDICATE_STRATA)
        assert list(got) == list(want)


def test_the_syndicate_control_refuses_an_impossible_match():
    """Fail closed: a stratum with too few unflagged syndicates, or a tolerance no draw can meet, raises rather
    than returning a control that is not matched."""
    S, R, H, yr, syn, ritc = am.load_sample()
    every = sorted(set(syn.tolist()))
    with pytest.raises(ValueError):
        CM.syndicate_control_masks(R, syn, every, 1, np.random.default_rng(1))
    with pytest.raises(RuntimeError):
        CM.syndicate_control_masks(R, syn, CM.margin_variants()["held_margin"], 1, np.random.default_rng(1),
                                   tol=0.0001, max_tries=50)


def _fake_fit(mask, label):
    import zlib
    rng = np.random.default_rng(zlib.crc32(label.encode()))
    draws = {p: rng.normal(float(am.headline()[p]["mean"]), 0.01, 200) for p in am.SHARED}
    return {"draws": draws, "max_rhat": 1.0, "divergences": 0, "guard_rows": [{"param": "k"}]}


def test_the_margin_record_has_its_variants_two_matched_controls_each_and_reading():
    """Every variant has a record-level and a whole-syndicate control (the stage-3 review, finding 3), and every
    row carries the standardised distance and the control's sd beside the min-max flag."""
    out = CM.run(n_control=3, fit_fn=_fake_fit)
    names = {"held_margin", "held_or_conditional", "any_scan_hit"}
    assert set(out["variants"]) == names and out["controls_design"]["n_draws_each"] == 3
    assert set(out["controls"]) == {"record", "syndicate"}
    for kind in ("record", "syndicate"):
        assert set(out["controls"][kind]) == names
    S, R, H, yr, syn, ritc = am.load_sample()
    for name in names:
        v = out["variants"][name]
        assert v["n"] + v["n_left_out"] == out["n_sample"]
        assert v["n_ritc_kept"] == int(ritc[~np.isin(syn, CM.margin_variants()[name])].sum())
        assert len(out["controls"]["record"][name]) == len(out["controls"]["syndicate"][name]) == 3
        assert all(c["n_left_out"] == v["n_left_out"] for c in out["controls"]["record"][name])
        for c in out["controls"]["syndicate"][name]:
            assert c["n_syndicates"] == v["n_syndicates"], "the same number of whole syndicates left out"
        m = out["controls_design"]["syndicate"]["per_variant"][name]
        assert m["accepted"] == 3 and m["tries"] >= 3 and len(m["draws_records_left_out"]) == 3
        assert all(abs(r - m["variant_ritc_left_out"]) <= CM.RITC_TOLERANCE for r in m["draws_ritc_left_out"])
        for c in out["controls"]["syndicate"][name]:
            assert abs(c["n_ritc_kept"] - v["n_ritc_kept"]) <= CM.RITC_TOLERANCE, name
        for p in CM.REPORT:
            row = out["comparison"][name][p]
            assert set(row) == {"shift_from_headline", "variant_mean", "versus_control"}
            assert set(row["versus_control"]) == {"record", "syndicate"}
            for vc in row["versus_control"].values():
                assert set(vc) == {"control_mean_of_means", "control_sd_of_means", "n_draws", "control_range_of_means",
                                   "variant_minus_control_mean", "standardised_distance",
                                   "variant_outside_control_range", "chance_outside_range_with_no_effect"}
                assert vc["standardised_distance"] == pytest.approx(
                    vc["variant_minus_control_mean"] / vc["control_sd_of_means"])
                assert vc["chance_outside_range_with_no_effect"] == pytest.approx(2 / 4)
    assert "understates" in out["controls_design"]["record"]["caveat"]
    assert "2/(n+1)" in out["controls_design"]["min_max_flag_caveat"]
    assert "indication" in out["reading"] and "not proof" in out["reading"]
    assert "lower bound" not in out["reading"] or "HTML" in out["flag_is_a_lower_bound"]
    json.dumps(out)


def test_the_control_sd_is_the_sample_sd_with_n_minus_1():
    """Pinned to numbers: the sd of the n control means divides by n - 1 (a divisor of n shrinks it by sqrt(4/5) here
    and inflates every standardised distance)."""
    sp = CM.control_spread([{"k": {"mean": m}} for m in (0.50, 0.52, 0.54, 0.56, 0.58)])["k"]
    assert sp["sd_of_means"] == pytest.approx(0.0316227766, abs=1e-9)
    assert CM.versus_control(0.60, sp)["standardised_distance"] == pytest.approx(0.06 / 0.0316227766, abs=1e-6)
    two = CM.control_spread([{"k": {"mean": 0.0}}, {"k": {"mean": 1.0}}])["k"]
    assert two["sd_of_means"] == pytest.approx(0.7071067812, abs=1e-9)


def test_the_margin_steps_manifest_estimate_covers_its_fits():
    """The step is 3 variants plus N_CONTROL draws of each of 2 controls for each (51 fits). The estimate must not fall
    back to the 25 minutes of the 11-fit version: at least 2 minutes a fit (the earlier assumption was 2.3; a tiny
    sampling fit measured 1.3 extrapolated, on a loaded machine)."""
    sys.path.insert(0, HERE)
    import reproduce
    fits = len(CM.margin_variants()) * (1 + 2 * CM.N_CONTROL)
    assert fits == 51
    minutes = {s: m for s, _stage, m in reproduce.STEPS}["check_margin_sensitivity.py"]
    assert minutes >= 2 * fits


def test_the_standardised_distance_and_the_range_flag_read_one_control():
    sp = CM.control_spread([{"k": {"mean": m}} for m in (0.50, 0.52, 0.54, 0.56, 0.58)])["k"]
    assert (sp["n_draws"], sp["mean_of_means"], sp["min"], sp["max"]) == (5, pytest.approx(0.54), 0.50, 0.58)
    inside = CM.versus_control(0.57, sp)
    assert inside["variant_outside_control_range"] is False
    assert inside["standardised_distance"] == pytest.approx(0.03 / sp["sd_of_means"])
    # a mean just outside the range is far in sd terms only if the sd is small: the distance is what to read
    outside = CM.versus_control(0.59, sp)
    assert outside["variant_outside_control_range"] is True
    assert outside["standardised_distance"] == pytest.approx(0.05 / sp["sd_of_means"])
    assert outside["chance_outside_range_with_no_effect"] == pytest.approx(2 / 6)
    one = CM.versus_control(0.6, CM.control_spread([{"k": {"mean": 0.5}}])["k"])
    assert one["standardised_distance"] is None and one["control_sd_of_means"] is None


def test_the_margin_script_writes_and_prints_every_variant(tmp_path, monkeypatch, capsys):
    """main() writes the record and prints a line for each variant, with the standardised distance beside the flag."""
    out = CM.run(n_control=2, fit_fn=_fake_fit)
    monkeypatch.setattr(CM, "run", lambda n_control: out)
    monkeypatch.setattr(CM, "OUT", tmp_path / "check_margin_sensitivity_results.json")
    assert CM.main([]) == 0
    with io.open(CM.OUT, encoding="utf-8") as fh:
        assert json.load(fh)["controls_design"]["n_draws_each"] == 2
    printed = capsys.readouterr().out
    for name in ("held_margin", "held_or_conditional", "any_scan_hit"):
        assert name in printed
    assert "record distance" in printed and "syndicate distance" in printed and "control sd" in printed
    assert " z " not in printed


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
                       ("V2_old_v995", rec["vignette2"]["adjusted_old"]["var995"]),
                       ("V2_new_v995", rec["vignette2"]["adjusted_new"]["var995"])):
        assert out[key]["mean"] == pytest.approx(block["mean"], abs=1e-12)
        assert out[key]["interval_95"] == pytest.approx([block["lo"], block["hi"]], abs=1e-12)
    # Vignette 2's sign: the share of replicates in which the VaR99.5 rises is the published one at delta = 0
    assert out["V2_change_v995"]["P_rise"] == pytest.approx(
        rec["robustness"]["P_sign_by_estimator"]["V2_rise_bayesian_bootstrap"], abs=1e-12)
    ch = rec["robustness"]["V2_change995_CI_by_clustering"]["bayesian_bootstrap_primary"]
    assert out["V2_change_v995"]["mean"] == pytest.approx(ch["mean"], abs=1e-12)


def _fit_record(delta_mean, ok=True):
    rng = np.random.default_rng(3)
    draws = {p: rng.normal(float(am.headline()[p]["mean"]), 0.01, 300) for p in am.SHARED}
    draws["delta"] = rng.normal(delta_mean, 0.05, 300)
    return {"draws": draws, "max_rhat": 1.0, "divergences": 0, "reproduces_headline": ok, "guard_rows": []}


def _vars(v1, v2, p_rise=0.9):
    return {"V1_adj_v995": {"median": v1, "mean": v1, "interval_95": [v1, v1]},
            "V2_old_v995": {"median": v2 - 0.01, "mean": v2 - 0.01, "interval_95": [v2 - 0.01, v2 - 0.01]},
            "V2_new_v995": {"median": v2, "mean": v2, "interval_95": [v2, v2]},
            "V2_change_v995": {"median": 0.01, "mean": 0.01, "interval_95": [-0.01, 0.03], "P_rise": p_rise}}


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


@pytest.mark.parametrize("bad", [0, 1])
def test_the_flag_is_not_read_when_a_control_does_not_reproduce_the_headline(bad):
    """A control that fails the headline guard is no noise floor: the flag is None and flag_valid False, never a
    False that reads as 'no move' (the review of 4 October 2026, finding 2). The move itself is still recorded."""
    controls = [_fit_record(0.0), _fit_record(0.0)]
    controls[bad] = _fit_record(0.0, ok=False)
    out = CK.assemble(_fit_record(0.2), _vars(0.33, 0.275), controls, [_vars(0.297, 0.274), _vars(0.299, 0.276)],
                      overlay=(_vars(0.33, 0.275), [_vars(0.297, 0.274), _vars(0.299, 0.276)]))
    assert out["controls_reproduce_the_headline"] is False and out["flag_valid"] is False
    assert out["flag_for_decision"] is None
    assert out["vignette_moves"]["V1_adj_v995"]["beyond_5pct_and_the_control_spread"] is None
    assert out["vignette_moves"]["V1_adj_v995"]["relative_move"] == pytest.approx(0.33 / 0.298 - 1)
    assert out["overlay_sensitivity"]["beyond_the_line_under_the_overlay"] is None
    json.dumps(out)


def test_a_valid_flag_is_a_bool_and_says_so():
    out = CK.assemble(_fit_record(0.2), _vars(0.33, 0.275), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.297, 0.274), _vars(0.299, 0.276)])
    assert out["flag_valid"] is True and out["flag_for_decision"] is True


def test_the_record_carries_vignette_2s_change_and_the_probability_it_rises():
    out = CK.assemble(_fit_record(0.2), _vars(0.30, 0.275, p_rise=0.7), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.297, 0.274, p_rise=0.9), _vars(0.299, 0.276, p_rise=0.94)])
    s2 = out["vignette2_sign"]
    assert s2["skew"]["P_rise"] == 0.7 and s2["skew"]["old_median"] == pytest.approx(0.265)
    assert s2["skew"]["new_median"] == 0.275 and s2["skew"]["change_median"] == 0.01
    assert [c["P_rise"] for c in s2["controls"]] == [0.9, 0.94]
    assert s2["control_mean_P_rise"] == pytest.approx(0.92) and s2["move_in_P_rise"] == pytest.approx(-0.22)
    assert out["flag_for_decision"] is False, "the sign is reported, not flagged"


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


def test_the_skew_script_writes_and_prints_its_record(tmp_path, monkeypatch, capsys):
    out = CK.assemble(_fit_record(0.2), _vars(0.30, 0.275), [_fit_record(0.0), _fit_record(0.0)],
                      [_vars(0.297, 0.274), _vars(0.299, 0.276)])
    monkeypatch.setattr(CK, "run", lambda: out)
    monkeypatch.setattr(CK, "OUT", tmp_path / "check_skew_t_results.json")
    assert CK.main() == 0
    with io.open(CK.OUT, encoding="utf-8") as fh:
        assert json.load(fh)["flag_for_decision"] is False
    printed = capsys.readouterr().out
    assert "V1_adj_v995" in printed and "V2_new_v995" in printed
    assert "P(rise)" in printed
