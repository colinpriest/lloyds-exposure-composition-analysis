r"""The headline with and without Vignette 1's most adverse donor (check_donor_influence.py; the author's decision of
1 October 2026).

The in-sample run-off measurement found the headline's upper tail resting on one record, 1991/2020, a part-year
run-off year the rule keeps. The script finds the pool's most adverse donor at the published posterior mean, refits
without it, and reruns the published vignette estimator on the pool without it. These tests drive it with the
refit replaced by the published draws and a small bootstrap, and check the committed record against the published
headline. One test runs the estimator on the published draws at the published bootstrap size (about 22 seconds)
and holds it to the committed vignette record.

Run:  python -m pytest src/test_donor_influence.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import check_donor_influence as CDI
import run_analysis as ra
import vignette_uncertainty as VU

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "results", "check_donor_influence_results.json")


def test_the_most_adverse_donor_is_the_largest_transferred_severity():
    assert CDI.most_adverse(["a", "b", "c"], np.array([0.1, 0.5, -0.2])) == ("b", 1)
    with pytest.raises(SystemExit, match="tie"):
        CDI.most_adverse(["a", "b", "c"], np.array([0.5, 0.5, -0.2]))


@pytest.fixture
def quick(monkeypatch, tmp_path):
    """main() in seconds: a 40-replicate bootstrap, the refit replaced by the published draws, the published headline
    read through the same estimator, and a corpus-wide run-off register that reads the donor as part-year."""
    monkeypatch.setattr(VU, "B", 40)
    monkeypatch.setattr(CDI, "OUT", tmp_path / "out.json")
    cal = json.load(io.open(str(CDI.CALIBRATION), encoding="utf-8"))
    draws = VU.load_draws()[0]
    keys, _S, transferred = CDI.transferred_pool()
    donor, _i = CDI.most_adverse(keys, transferred)
    syndicate, year = donor.split("_")
    register = tmp_path / "runoff_corpus_register.json"
    register.write_text(json.dumps([{"stem": "syndicate_%s" % donor, "syndicate": int(syndicate), "year": int(year),
                                     "category": "PART", "runoff_from": "6 November 2020"}]), encoding="utf-8")
    monkeypatch.setattr(ra, "RUNOFF_CORPUS_REGISTER", register)
    calls = []

    def fake_fit(S, R, H, yr, ritc, scale=None):
        calls.append(len(S))
        means = {p: float(cal[p]) * (scale.get(p, 1.0) if scale else 1.0) for p in CDI.PARAMS}
        params = {p: {"mean": means[p]} for p in CDI.PARAMS}
        return (means, params, {"max_rhat": 1.0, "min_ess_bulk": 1000.0, "divergences": 0}, dict(draws),
                {"P_nu_ritc_lt_nu_clean": 0.5})

    reference = CDI.vignettes(np.ones(len(keys), bool), draws)
    monkeypatch.setattr(CDI, "published", lambda: ({p: float(cal[p]) for p in CDI.PARAMS}, reference))
    return {"fit": fake_fit, "calls": calls, "donor": donor, "n": len(keys), "reference": reference}


def test_the_record_carries_both_sides_without_the_donor(quick, tmp_path):
    assert CDI.main(fit=quick["fit"]) == 0
    out = json.load(io.open(str(tmp_path / "out.json"), encoding="utf-8"))
    assert quick["calls"] == [quick["n"], quick["n"] - 1], "the full sample, then the sample without the donor"
    assert out["donor"]["key"] == quick["donor"] and out["donor"]["rank"] == 1
    assert out["donor"]["runoff_reading"]["category"] == "PART"
    assert (out["fits"]["with"]["n"], out["fits"]["without"]["n"]) == (quick["n"], quick["n"] - 1)
    assert out["fits"]["with"]["V1_VaR995"] == quick["reference"]["V1_VaR995"]
    change = out["changes"]["V1_VaR995_posterior_mean"]
    assert change["change"] == pytest.approx(change["without"] - change["with"])
    assert out["fits"]["without"]["V1_VaR995"]["centre"] < out["fits"]["with"]["V1_VaR995"]["centre"]
    # the headline at the top, the overlay labelled beside each side (test_operator_binding's rule for every output)
    assert out["operator"] == "size_only"
    for side in ("with", "without"):
        overlay = out["fits"][side]["overlay_sensitivity"]
        assert (overlay["operator"], overlay["operator_role"]) == ("overlay", "sensitivity")
    assert out["fits"]["with"]["overlay_sensitivity"]["V1_VaR995_centre"] == pytest.approx(
        CDI.published_overlay()["V1_VaR995_centre"], abs=CDI.REPRODUCE_TOL)
    assert (out["fits"]["without"]["overlay_sensitivity"]["V1_VaR995_centre"]
            < out["fits"]["with"]["overlay_sensitivity"]["V1_VaR995_centre"])
    _intervals_are_named_as_the_estimator_names_them(out)


def _intervals_are_named_as_the_estimator_names_them(out):
    """The vignette estimator's interval is equal-tailed (a Bayesian bootstrap's 2.5% and 97.5% points), and
    vignette_uncertainty.py writes its ends "lo" and "hi". The record wrote them "hdi_2.5"/"hdi_97.5", and the
    manuscript's audit refuses an HDI-named key for an equal-tailed interval (round 62, fourth cycle)."""
    for side in ("with", "without"):
        for name in ("V1_VaR995", "V2_change995"):
            assert set(out["fits"][side][name]) == {"centre", "posterior_mean", "lo", "hi"}, (side, name)
    assert {"V1_VaR995_lo", "V1_VaR995_hi", "V2_change995_lo", "V2_change995_hi"} <= set(out["changes"])
    assert not [k for k in out["changes"] if "hdi" in k]
    assert "equal-tailed 2.5-97.5%" in out["vignette_estimator"]["interval"]


def test_the_script_writes_no_hdi_named_key():
    """The manuscript's audit (gate S) refuses a script that writes an HDI-named key without computing an HDI
    (az.hdi, hdi_prob or az.summary in the same source). The refit's parameter HDIs come from fx_sensitivity's
    az.summary and pass through under their own names; this script computes no HDI, so it names none."""
    import re
    text = io.open(os.path.join(HERE, "src", "check_donor_influence.py"), encoding="utf-8").read()
    assert not re.search(r"[\"']hdi[_0-9.]*[\"']\s*:", text)
    assert not re.search(r"[\"']hdi[_0-9.]*[\"']\s*[,)]", text)


def test_a_refit_that_does_not_reproduce_the_calibration_is_refused(quick):
    with pytest.raises(SystemExit, match="does not reproduce the published calibration"):
        CDI.main(fit=lambda *a: quick["fit"](*a, scale={"k": 1.001}))


def test_vignettes_that_do_not_reproduce_the_published_ones_are_refused(quick, monkeypatch):
    cal, reference = CDI.published()
    moved = json.loads(json.dumps(reference))
    moved["V1_VaR995"]["posterior_mean"] += 1e-6
    monkeypatch.setattr(CDI, "published", lambda: (cal, moved))
    with pytest.raises(SystemExit, match="not the published ones"):
        CDI.main(fit=quick["fit"])


def test_overlay_centres_that_do_not_reproduce_the_published_ones_are_refused(quick, monkeypatch):
    moved = dict(CDI.published_overlay())
    moved["V2_change995_centre"] += 1e-6
    monkeypatch.setattr(CDI, "published_overlay", lambda: moved)
    with pytest.raises(SystemExit, match="overlay centres .* not the published ones"):
        CDI.main(fit=quick["fit"])


def test_the_estimator_on_the_published_draws_reproduces_the_published_headline():
    """The record's "with" side is the published headline, so the estimator on the full pool and the published
    draws, at the published bootstrap size (about 22 seconds, no refit), must give the V1 and V2 figures of
    results/vignette_uncertainty_results.json and the overlay's two centres exactly. The quick fixture takes its
    `published` from CDI.vignettes itself, so it compares the estimator with itself: a wrong operator, truncated
    draws or swapped interval ends pass every other test here, and the script's own check runs only in the
    recorded pass, after a refit (review of 1 October 2026, finding 3)."""
    draws = VU.load_draws()[0]
    keys, _S, _transferred = CDI.transferred_pool()
    everyone = np.ones(len(keys), bool)
    _means, published = CDI.published()
    ours = CDI.vignettes(everyone, draws)
    for name in published:
        for stat in published[name]:
            assert ours[name][stat] == pytest.approx(published[name][stat], abs=CDI.REPRODUCE_TOL), (name, stat)
    overlay = CDI.overlay_centres(everyone, draws)
    for name, centre in CDI.published_overlay().items():
        assert overlay[name] == pytest.approx(centre, abs=CDI.REPRODUCE_TOL), name


def test_the_recorded_run_is_the_published_headline_less_its_most_adverse_donor():
    """DEFERRED-TO-REFIT: results/check_donor_influence_results.json is written by the recorded pass."""
    if not os.path.exists(OUT):
        pytest.skip("results/check_donor_influence_results.json not present in this checkout")
    out = json.load(io.open(OUT, encoding="utf-8"))
    keys, _S, transferred = CDI.transferred_pool()
    donor, _i = CDI.most_adverse(keys, transferred)
    assert out["donor"]["key"] == donor
    # the author's statement names it: a change of donor must be seen before the manuscript repeats it
    assert donor == "1991_2020"
    means, vignettes = CDI.published()
    for p in CDI.PARAMS:
        assert out["fits"]["with"]["means"][p] == pytest.approx(means[p], abs=CDI.REPRODUCE_TOL), p
    for name in vignettes:
        for stat in vignettes[name]:
            assert out["fits"]["with"][name][stat] == pytest.approx(vignettes[name][stat], abs=CDI.REPRODUCE_TOL)
    assert out["fits"]["without"]["n"] == out["fits"]["with"]["n"] - 1 == len(keys) - 1
    assert out["fits"]["with"]["diagnostics"]["divergences"] == out["fits"]["without"]["diagnostics"]["divergences"] == 0
    # the rule keeps it: its filing's run-off began during the year
    assert out["donor"]["runoff_reading"]["category"] == "PART"
    _intervals_are_named_as_the_estimator_names_them(out)
