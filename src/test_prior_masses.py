#!/usr/bin/env python3
"""The prior-mass producer (check_prior_masses.py): each quoted posterior probability beside its prior mass.

Review of 29 September 2026 (M-4): P(gamma > 0.05) = 0.97 was read as evidence against a prior mass of 0.96.
These tests hold the producer to what it claims: the priors are read from the adopted model's graph (a
changed family stops it), every closed form agrees with an independent Monte Carlo draw from that prior,
the posterior masses are the draws' and the calibration's, and the reading rule (distance 0.05 or odds
factor 3) classifies the events the way the review found them.

Run:  python -m pytest src/test_prior_masses.py -q
"""
import io
import json
import math
import os

import numpy as np
import pytest

import check_prior_masses as P

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ the reading rule ------
@pytest.mark.parametrize("prior,post,want", [
    (0.9601, 0.9693, False),    # P(gamma > 0.05): 0.01 apart, odds x1.3 -- mostly the prior
    (0.5, 0.4607, False),       # P(nu_RITC < nu_clean)
    (0.0361, 0.0282, False),    # P(nu_RITC < 2)
    (0.0175, 0.0, True),        # P(nu_clean < 2): 0.018 apart, but the odds went to zero
    (0.8415, 0.6133, True),     # P(|beta| > 0.1): 0.23 apart
    (0.9436, 0.9998, True),     # P(sigma_undiv > 0.005): odds x300
])
def test_the_reading_rule(prior, post, want):
    assert P.informed(prior, post) is want


def test_the_bayes_factor_is_the_odds_ratio():
    assert P.bayes_factor(0.5, 0.75) == pytest.approx(3.0)
    assert P.bayes_factor(0.2, 0.2) == pytest.approx(1.0)
    assert P.bayes_factor(0.3, 1.0) == math.inf and P.bayes_factor(0.3, 0.0) == 0.0
    assert P.bayes_factor(1.0, 1.0) is None and P.bayes_factor(0.0, 0.0) is None


def test_an_odds_move_at_the_line_counts_and_just_inside_it_does_not():
    """A rare event, so the distance stays under 0.05 and only the odds rule can decide."""
    prior = 0.01
    odds = 3.0 * prior / (1 - prior)
    at = odds / (1 + odds)                                   # the posterior whose odds are exactly three times
    assert abs(at - prior) < P.INFORMED
    assert P.informed(prior, at + 1e-12) and not P.informed(prior, at - 1e-3)
    assert P.informed(prior, prior / 3.5) and not P.informed(prior, prior / 2.5)   # and downwards


# ------------------------------------------------------------------ the priors, from the graph ------
@pytest.fixture(scope="module")
def model():
    return P.prior_model()


@pytest.fixture(scope="module")
def masses(model):
    return P.prior_masses(model)


def test_every_quoted_event_has_a_prior_mass(masses):
    assert set(masses) == {key for key, _label, _cal in P.EVENTS}
    assert all(0.0 <= v <= 1.0 for v in masses.values())


def test_the_closed_forms_agree_with_an_independent_draw_from_the_prior(model, masses):
    """A second Monte Carlo, at a seed the producer does not use: a wrong parametrisation (a Gamma rate read as
    its scale, a half-normal's missing factor of two) is many standard errors out."""
    mc = P.monte_carlo_masses(model, draws=40000, seed=7)
    for key, p in masses.items():
        se = math.sqrt(max(p * (1 - p), 1e-12) / 40000)
        assert abs(mc[key] - p) <= 5 * se + 5e-4, (key, p, mc[key])


def test_a_changed_prior_family_stops_the_producer(model, monkeypatch):
    real = P.prior_of

    def planted(m, name):
        fam, params = real(m, name)
        return ("StudentTRV", params) if name == "gamma" else (fam, params)

    monkeypatch.setattr(P, "prior_of", planted)
    with pytest.raises(SystemExit) as exc:
        P.prior_masses(model)
    assert "gamma" in str(exc.value) and "re-derived" in str(exc.value)


# ------------------------------------------------------------------ the record ------
@pytest.fixture(scope="module")
def record():
    return P.compute()


def test_the_posterior_masses_are_the_adopted_draws(record):
    z = np.load(str(P.DRAWS))
    assert record["events"]["nu_clean_lt_2"]["posterior"] == float((z["nu_clean"] < 2.0).mean())
    assert record["events"]["gamma_gt_0.05"]["posterior"] == float((z["gamma"] > 0.05).mean())
    cal = json.load(io.open(str(P.CALIBRATION), encoding="utf-8"))["posterior_prob"]
    for key, _label, cal_key in P.EVENTS:
        if cal_key in cal:
            assert record["events"][key]["posterior"] == pytest.approx(cal[cal_key], abs=1e-12), key


def test_the_events_read_the_way_the_review_found_them(record):
    ev = record["events"]
    # the regenerated headline refit (6 October 2026) moved two events across the rule's line: P(nu_RITC < nu_clean)
    # fell from 0.486 to 0.341 against a prior mass of 0.5, so it is now informed by the data (it was mostly the
    # prior); P(|beta_RITC| > 0.1) rose from 0.674 to 0.793 against a prior mass of 0.842, within 0.05 of it, so it is
    # now mostly the prior (it was informed). The refit's inputs moved: 88 records' composition, 15 records' prior-year
    # development and 4 records' basis tags, from the extraction imports and the stage-3 P-10 entries
    mostly_prior = {"gamma_gt_0.05", "nu_ritc_lt_2", "beta_ritc_abs_gt_0.1"}
    informed = {"nu_clean_lt_2", "sd_undiv_gt_0.005", "nu_ritc_lt_nu_clean"}
    assert {k for k, r in ev.items() if r["data_informed"]} == informed
    for k in mostly_prior:
        assert "mostly the prior" in ev[k]["reading"], k
    for k in ("k_gt_0.5", "k_lt_1"):
        assert ev[k]["prior"] == ev[k]["posterior"] == 1.0 and "by construction" in ev[k]["reading"]
    assert record["priors"]["nu_clean"]["family"] == "GammaRV"


# ------------------------------------------------------------------ the calibration's prior_prob ------
#: the names the manuscript's registry reads from model/dispersion_calibration_ritc.json's prior_prob
REGISTRY_KEYS = {"gamma_gt_0.05", "nu_ritc_lt_nu_clean", "nu_ritc_lt_2", "nu_clean_lt_2", "sd_undiv_gt_0.005",
                 "beta_ritc_gt_0.1_abs"}


def _draws():
    z = np.load(str(P.DRAWS))
    return {k: z[k] for k in ("gamma", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "sd_undiv")}


def test_the_calibration_writes_each_prior_mass_beside_its_posterior(model, masses):
    """calibrate_dispersion_ritc's event_probabilities, on the committed draws: prior_prob under the registry's
    names, from this module's closed forms (one source), each beside its posterior probability."""
    import calibrate_dispersion_ritc as C
    posterior, prior = C.event_probabilities(model, _draws())
    assert set(prior) == REGISTRY_KEYS and set(prior) <= set(posterior)
    assert prior == P.calibration_prior_prob(model)
    for key, cal_key in P.CALIBRATION_KEYS.items():
        assert prior[cal_key] == masses[key], key
    d = _draws()
    assert posterior["gamma_gt_0.05"] == float((d["gamma"] > 0.05).mean())
    assert posterior["sd_undiv_gt_0.005"] == float((d["sd_undiv"] > 0.005).mean())
    recorded = json.load(io.open(str(P.CALIBRATION), encoding="utf-8"))["posterior_prob"]
    for key, value in recorded.items():
        assert posterior[key] == value, "the posterior probabilities the calibration already recorded moved: " + key


@pytest.mark.parametrize("plant", [None, "moved", "missing"])
def test_the_producer_checks_the_calibrations_prior_prob(model, monkeypatch, tmp_path, plant):
    cal = json.load(io.open(str(P.CALIBRATION), encoding="utf-8"))
    cal["prior_prob"] = P.calibration_prior_prob(model)
    if plant == "moved":
        cal["prior_prob"]["nu_ritc_lt_2"] += 0.01
    elif plant == "missing":
        del cal["prior_prob"]["sd_undiv_gt_0.005"]
    path = tmp_path / "dispersion_calibration_ritc.json"
    path.write_text(json.dumps(cal), encoding="utf-8")
    monkeypatch.setattr(P, "CALIBRATION", path)
    monkeypatch.setattr(P, "monte_carlo_masses", lambda m, **k: P.prior_masses(m))   # the closed forms, fast
    if plant is None:
        assert P.compute()["calibration_prior_prob_checked"] is True
    else:
        with pytest.raises(SystemExit):
            P.compute()


def test_the_recorded_calibration_carries_the_prior_masses(record):
    """DEFERRED-TO-REFIT: model/dispersion_calibration_ritc.json is rewritten by the recorded pass."""
    cal = json.load(io.open(str(P.CALIBRATION), encoding="utf-8"))
    assert set(cal["prior_prob"]) == REGISTRY_KEYS and REGISTRY_KEYS <= set(cal["posterior_prob"])
    for key, cal_key in P.CALIBRATION_KEYS.items():
        assert cal["prior_prob"][cal_key] == pytest.approx(record["events"][key]["prior"], abs=1e-12)
    assert record["calibration_prior_prob_checked"] is True


def test_the_recorded_file_is_what_the_producer_computes(record):
    """DEFERRED-TO-REFIT: results/check_prior_masses_results.json is written by the recorded pass."""
    path = os.path.join(HERE, "results", "check_prior_masses_results.json")
    if not os.path.exists(path):
        pytest.skip("results/check_prior_masses_results.json not present in this checkout")
    rec = json.load(io.open(path, encoding="utf-8"))
    assert rec["events"].keys() == record["events"].keys()
    for key, row in record["events"].items():
        for field in ("prior", "posterior", "data_informed"):
            assert rec["events"][key][field] == row[field], (key, field)
