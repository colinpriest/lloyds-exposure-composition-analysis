#!/usr/bin/env python3
"""The prior-mass producer (check_prior_masses.py): each quoted posterior probability beside its prior mass.

Review of 29 September 2026 (M-4): P(gamma > 0.05) = 0.97 was read as evidence against a prior mass of 0.96.
These tests hold the producer to what it claims: the priors are read from the adopted model's graph (a
changed family stops it), every closed form agrees with an independent Monte Carlo draw from that prior,
the posterior masses are the draws' and the calibration's, and the reading rule (distance 0.05 or odds
factor 3) classifies the events the way the review found them. Since option B (10 October 2026) the headline has
gamma fixed at 0 in the likelihood, so P(gamma > 0.05) is read on the gamma-free model and its calibration.

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
    """The headline model: gamma fixed at 0 in the likelihood (option B, 10 October 2026)."""
    return P.prior_model()


@pytest.fixture(scope="module")
def model_gf():
    """The gamma-free model, the one P(gamma > 0.05) is read on."""
    return P.prior_model("halfnormal")


@pytest.fixture(scope="module")
def masses(model):
    return P.prior_masses(model)


@pytest.fixture(scope="module")
def masses_gf(model_gf):
    return P.prior_masses(model_gf)


def test_every_quoted_event_has_a_prior_mass(masses, masses_gf):
    """Every event on the model it is read on: P(gamma > 0.05) on the gamma-free model, the rest on the headline's,
    which has no gamma and so no P(gamma > 0.05)."""
    events = {key for key, _label, _cal in P.EVENTS}
    assert set(P.GAMMA_FREE_EVENTS) == {"gamma_gt_0.05"}
    assert set(masses) == events - set(P.GAMMA_FREE_EVENTS)
    assert set(masses_gf) == events
    assert all(0.0 <= v <= 1.0 for v in list(masses.values()) + list(masses_gf.values()))
    # the other events' priors do not depend on gamma's
    assert all(masses[k] == masses_gf[k] for k in masses)


def test_the_headline_model_has_no_gamma(model, model_gf):
    assert not P.has_gamma(model) and P.has_gamma(model_gf)
    assert "gamma_gt_0.05" not in P.calibration_prior_prob(model)
    assert "gamma_gt_0.05" in P.calibration_prior_prob(model_gf)
    assert "gamma_gt_0.05" not in P.monte_carlo_masses(model, draws=2000, seed=3)


@pytest.mark.parametrize("which", ["headline", "gamma_free"])
def test_the_closed_forms_agree_with_an_independent_draw_from_the_prior(which, model, model_gf, masses, masses_gf):
    """A second Monte Carlo, at a seed the producer does not use: a wrong parametrisation (a Gamma rate read as
    its scale, a half-normal's missing factor of two) is many standard errors out."""
    m, ms = (model, masses) if which == "headline" else (model_gf, masses_gf)
    mc = P.monte_carlo_masses(m, draws=40000, seed=7)
    assert set(mc) == set(ms)
    for key, p in ms.items():
        se = math.sqrt(max(p * (1 - p), 1e-12) / 40000)
        assert abs(mc[key] - p) <= 5 * se + 5e-4, (key, p, mc[key])


@pytest.mark.parametrize("name", ["gamma", "lambda_ritc"])
def test_a_changed_prior_family_stops_the_producer(name, model, model_gf, monkeypatch):
    real = P.prior_of

    def planted(m, n):
        fam, params = real(m, n)
        return ("StudentTRV", params) if n == name else (fam, params)

    monkeypatch.setattr(P, "prior_of", planted)
    with pytest.raises(SystemExit) as exc:
        P.prior_masses(model_gf if name == "gamma" else model)
    assert name in str(exc.value) and "re-derived" in str(exc.value)


def test_the_posterior_masses_read_gamma_only_where_the_fit_has_it():
    head = {"gamma": np.zeros(4), "nu_ritc": np.array([3.0, 1.5, 4.0, 9.0]), "nu_clean": np.full(4, 5.0),
            "sd_undiv": np.full(4, 0.03), "beta_ritc": np.array([0.2, -0.05, 0.0, -0.3]), "k": np.full(4, 0.6)}
    assert "gamma_gt_0.05" not in P.posterior_masses(head)
    free = dict(head, gamma=np.array([0.01, 0.2, 0.4, 0.06]))
    assert P.posterior_masses(free)["gamma_gt_0.05"] == 0.75
    assert P.posterior_masses(head)["nu_ritc_lt_2"] == 0.25


# ------------------------------------------------------------------ the record ------
@pytest.fixture(scope="module")
def record():
    """P.compute() reads both regenerated calibrations and their draws."""
    return P.compute()


def test_the_posterior_masses_are_each_fits_draws(record):
    """P(gamma > 0.05) on the gamma-free draws, every other event on the headline's."""
    with np.load(str(P.DRAWS)) as _z, np.load(str(P.GAMMA_FREE_DRAWS)) as _zg:
        z, zg = {key: _z[key] for key in _z.files}, {key: _zg[key] for key in _zg.files}
    assert record["events"]["nu_clean_lt_2"]["posterior"] == float((z["nu_clean"] < 2.0).mean())
    assert record["events"]["gamma_gt_0.05"]["posterior"] == float((zg["gamma"] > 0.05).mean())
    assert record["events"]["gamma_gt_0.05"]["fit"] == "gamma_free"
    assert {r["fit"] for k, r in record["events"].items() if k != "gamma_gt_0.05"} == {"headline"}
    for path, events in ((P.CALIBRATION, lambda k: k != "gamma_gt_0.05"),
                         (P.GAMMA_FREE_CALIBRATION, lambda k: k == "gamma_gt_0.05")):
        with io.open(str(path), encoding="utf-8") as _fh:
            cal = json.load(_fh)["posterior_prob"]
        for key, _label, cal_key in P.EVENTS:
            if cal_key in cal and events(key):
                assert record["events"][key]["posterior"] == pytest.approx(cal[cal_key], abs=1e-12), key


def test_the_events_read_the_way_the_review_found_them(record):
    """The readings are of each event's own fit: P(gamma > 0.05) the gamma-free fit's, every other the gamma = 0
    headline's (option B, 10 October 2026)."""
    ev = record["events"]
    # the regenerated headline refit (6 October 2026) moved two events across the rule's line: P(nu_RITC < nu_clean)
    # fell from 0.486 to 0.341 against a prior mass of 0.5, so it is now informed by the data (it was mostly the
    # prior); P(|beta_RITC| > 0.1) rose from 0.674 to 0.793 against a prior mass of 0.842, within 0.05 of it, so it is
    # now mostly the prior (it was informed). The refit's inputs moved: 88 records' composition, 15 records' prior-year
    # development and 4 records' basis tags, from the extraction imports and the stage-3 P-10 entries.
    # Option B's regeneration (0912834, committed as 5693622) moved P(|beta_RITC| > 0.1) back across the line: on the
    # gamma = 0 headline it is 0.769 against a prior mass of 0.842 (it was 0.793 on the gamma-free fit, then the
    # headline), more than 0.05 from it, so it is informed by the data again. P(nu_RITC < nu_clean) is 0.337 (0.341)
    # and stays informed; P(gamma > 0.05) is the gamma-free fit's, 0.933 against 0.960, unchanged
    # the regeneration of 13 October 2026 (465f99a, outputs e627b77: four repairs, 1218/2015 net, 4020/2017 excluded) moved
    # P(nu_RITC < 2) across the odds line: 0.0112 against a prior mass of 0.036, a Bayes factor of 0.302 (0.421 on
    # 0.0155 before), so its odds moved by a little more than a factor of 3 and it reads as informed by the data;
    # it is within 0.05 of the prior mass, so it sits at the rule's edge
    mostly_prior = {"gamma_gt_0.05"}
    informed = {"nu_clean_lt_2", "sd_undiv_gt_0.005", "nu_ritc_lt_nu_clean", "beta_ritc_abs_gt_0.1", "nu_ritc_lt_2"}
    assert {k for k, r in ev.items() if r["data_informed"]} == informed
    for k in mostly_prior:
        assert "mostly the prior" in ev[k]["reading"], k
    for k in ("k_gt_0.5", "k_lt_1"):
        assert ev[k]["prior"] == ev[k]["posterior"] == 1.0 and "by construction" in ev[k]["reading"]
    assert record["priors"]["nu_clean"]["family"] == "GammaRV"
    assert "gamma" not in record["priors"] and record["priors_gamma_free_fit"]["gamma"]["family"] == "HalfNormalRV"


# ------------------------------------------------------------------ the calibration's prior_prob ------
#: the names the manuscript's registry reads from the calibrations' prior_prob: the headline's every event but
#: P(gamma > 0.05), which the gamma-free calibration carries (option B, 10 October 2026)
REGISTRY_KEYS = {"nu_ritc_lt_nu_clean", "nu_ritc_lt_2", "nu_clean_lt_2", "sd_undiv_gt_0.005", "beta_ritc_gt_0.1_abs"}
GAMMA_FREE_REGISTRY_KEYS = REGISTRY_KEYS | {"gamma_gt_0.05"}


def _draws(path, gamma):
    with np.load(str(path)) as _npz:
        z = {key: _npz[key] for key in _npz.files}
    keys = (("gamma",) if gamma else ()) + ("nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "sd_undiv")
    return {k: z[k] for k in keys}


@pytest.mark.parametrize("which", ["headline", "gamma_free"])
def test_the_calibration_writes_each_prior_mass_beside_its_posterior(which, model, model_gf, masses, masses_gf):
    """calibrate_dispersion_ritc's event_probabilities, on each fit's committed draws: prior_prob under the registry's
    names, from this module's closed forms (one source), each beside its posterior probability. The committed draws
    must be each fit's."""
    import calibrate_dispersion_ritc as C
    if which == "headline":
        m, ms, keys, d, path = model, masses, REGISTRY_KEYS, _draws(P.DRAWS, False), P.CALIBRATION
    else:
        m, ms, keys, d, path = (model_gf, masses_gf, GAMMA_FREE_REGISTRY_KEYS, _draws(P.GAMMA_FREE_DRAWS, True),
                                P.GAMMA_FREE_CALIBRATION)
    posterior, prior = C.event_probabilities(m, d)
    assert set(prior) == keys and set(prior) <= set(posterior)
    assert prior == P.calibration_prior_prob(m)
    for key, cal_key in P.CALIBRATION_KEYS.items():
        if key in ms:
            assert prior[cal_key] == ms[key], key
    if which == "gamma_free":
        assert posterior["gamma_gt_0.05"] == float((d["gamma"] > 0.05).mean())
    assert posterior["sd_undiv_gt_0.005"] == float((d["sd_undiv"] > 0.005).mean())
    with io.open(str(path), encoding="utf-8") as _fh:
        recorded = json.load(_fh)["posterior_prob"]
    assert set(recorded) == set(posterior)
    for key, value in recorded.items():
        assert posterior[key] == value, "the posterior probabilities the calibration already recorded moved: " + key


def test_a_gamma_event_without_a_gamma_is_not_written():
    """The headline's event_probabilities never sees a gamma, and a gamma-free model's prior mass with no posterior is
    refused, so neither file can carry one half of P(gamma > 0.05)."""
    import calibrate_dispersion_ritc as C
    d = {"nu_clean": np.full(4, 5.0), "nu_ritc": np.full(4, 7.0), "lambda_ritc": np.zeros(4), "beta_ritc": np.zeros(4),
         "sd_undiv": np.full(4, 0.03)}
    with pytest.raises(SystemExit):
        C.event_probabilities(P.prior_model("halfnormal"), d)


@pytest.mark.parametrize("plant", [None, "moved", "missing", "gamma_in_headline"])
def test_the_producer_checks_the_calibrations_prior_prob(model, monkeypatch, tmp_path, plant):
    """P.compute() reads both regenerated calibrations and their draws."""
    with io.open(str(P.CALIBRATION), encoding="utf-8") as _fh:
        cal = json.load(_fh)
    cal["prior_prob"] = P.calibration_prior_prob(model)
    if plant == "moved":
        cal["prior_prob"]["nu_ritc_lt_2"] += 0.01
    elif plant == "missing":
        del cal["prior_prob"]["sd_undiv_gt_0.005"]
    elif plant == "gamma_in_headline":
        cal["prior_prob"]["gamma_gt_0.05"] = 0.96
    path = tmp_path / "dispersion_calibration_ritc.json"
    path.write_text(json.dumps(cal), encoding="utf-8")
    monkeypatch.setattr(P, "CALIBRATION", path)
    monkeypatch.setattr(P, "monte_carlo_masses", lambda m, **k: P.prior_masses(m))   # the closed forms, fast
    if plant is None:
        assert P.compute()["calibration_prior_prob_checked"] is True
    else:
        with pytest.raises(SystemExit):
            P.compute()


def test_the_recorded_calibrations_carry_the_prior_masses(record):
    """Both calibrations are rewritten by the regeneration."""
    with io.open(str(P.CALIBRATION), encoding="utf-8") as _fh:
        cal = json.load(_fh)
    assert set(cal["prior_prob"]) == REGISTRY_KEYS and REGISTRY_KEYS <= set(cal["posterior_prob"])
    assert "gamma_gt_0.05" not in cal["posterior_prob"]
    with io.open(str(P.GAMMA_FREE_CALIBRATION), encoding="utf-8") as _fh:
        gf = json.load(_fh)
    assert set(gf["prior_prob"]) == GAMMA_FREE_REGISTRY_KEYS
    for key, cal_key in P.CALIBRATION_KEYS.items():
        src = gf if key in P.GAMMA_FREE_EVENTS else cal
        assert src["prior_prob"][cal_key] == pytest.approx(record["events"][key]["prior"], abs=1e-12)
    assert record["calibration_prior_prob_checked"] is True


def test_the_recorded_file_is_what_the_producer_computes(record):
    """DEFERRED-TO-REFIT: results/check_prior_masses_results.json is written by the recorded pass."""
    path = os.path.join(HERE, "results", "check_prior_masses_results.json")
    if not os.path.exists(path):
        pytest.skip("results/check_prior_masses_results.json not present in this checkout")
    with io.open(path, encoding="utf-8") as _fh:
        rec = json.load(_fh)
    assert rec["events"].keys() == record["events"].keys()
    for key, row in record["events"].items():
        for field in ("prior", "posterior", "data_informed", "fit"):
            assert rec["events"][key][field] == row[field], (key, field)
