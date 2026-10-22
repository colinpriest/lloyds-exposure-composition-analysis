#!/usr/bin/env python3
"""The adopted two-regime model scored by held-out density (check_full_model_cv.py).

Each part is held to a hand computation or to the script it must agree with:

  * the held-out density: the posterior-draw average of the two-regime Student-t, with the held-out record's own
    assumed-business flag in its tail index and scale, and its year's shock; the marginal version integrates a new
    year's shock out by Gauss-Hermite quadrature, checked against numerical integration; a year the fold has not seen
    is scored marginally;
  * the folds are Table 4's (oos_validation.fold_assignment at K = 5) and the sampler is the headline's;
  * the single-regime totals must reproduce Table 4's records, and every observation is scored exactly once;
  * the contrasts are check_cv_clustered_se.contrast's, with no z-score kept;
  * the committed record (DEFERRED-TO-REFIT: written by the recorded pass).

Run:  python -m pytest src/test_full_model_cv.py -q
"""
import ast
import io
import json
import os

import numpy as np
import pytest
from scipy import integrate, stats
from scipy.special import logsumexp

import check_full_model_cv as FC
import check_cv_clustered_se as CV
import oos_validation as OV

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")


def _text(path):
    with io.open(path, encoding="utf-8") as _fh:
        return _fh.read()


def _post(d=3, n_y=2, lam=0.4, beta=0.3):
    rng = np.random.default_rng(7)
    return {"k": rng.uniform(0.55, 0.75, d), "sd_undiv": rng.uniform(0.01, 0.04, d), "sd_div": rng.uniform(0.03, 0.06, d),
            "nu_clean": rng.uniform(3, 6, d), "lambda_ritc": np.full(d, lam), "beta_ritc": np.full(d, beta),
            "tau_s": rng.uniform(0.05, 0.2, d), "s_y": rng.normal(0, 0.1, (d, n_y))}


def _by_hand(S, R, ritc, y, post):
    lp = []
    for j in range(len(post["k"])):
        nu = post["nu_clean"][j] * np.exp(-post["lambda_ritc"][j] * ritc)
        base = np.sqrt(post["sd_undiv"][j] ** 2 + post["sd_div"][j] ** 2 * (R / 500.0) ** (2 * (post["k"][j] - 1)))
        sigma = np.exp(post["s_y"][j, y] + post["beta_ritc"][j] * ritc) * base
        lp.append(stats.t.logpdf(S, df=nu, scale=sigma))
    return logsumexp(lp) - np.log(len(lp))


def test_the_held_out_density_is_the_draw_average_of_the_two_regime_student_t():
    post = _post()
    S, R, ritc, y = np.array([0.05, -0.12, 0.3]), np.array([120.0, 800.0, 450.0]), np.array([0.0, 1.0, 1.0]), [0, 1, 0]
    got = FC.two_regime_lppd(S, R, ritc, np.array(y), post)
    want = [_by_hand(S[i], R[i], ritc[i], y[i], post) for i in range(3)]
    assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


def test_the_held_out_records_flag_moves_its_tail_index_and_scale():
    post = _post(lam=0.6, beta=0.5)
    S, R, y = np.array([0.2, 0.2]), np.array([300.0, 300.0]), np.array([1, 1])
    a = FC.two_regime_lppd(S, R, np.array([0.0, 1.0]), y, post)
    assert a[0] != a[1]
    flat = dict(post, lambda_ritc=np.zeros(3), beta_ritc=np.zeros(3))
    b = FC.two_regime_lppd(S, R, np.array([0.0, 1.0]), y, flat)
    assert b[0] == pytest.approx(b[1], rel=1e-14)


def test_the_marginal_density_integrates_a_new_years_shock():
    post = _post(d=1)
    S, R, ritc = np.array([0.15]), np.array([250.0]), np.array([1.0])
    got = FC.two_regime_lppd(S, R, ritc, np.array([0]), post, marginal=True)[0]
    nu = post["nu_clean"][0] * np.exp(-post["lambda_ritc"][0])
    base = np.exp(post["beta_ritc"][0]) * np.sqrt(post["sd_undiv"][0] ** 2 + post["sd_div"][0] ** 2
                                                  * (250.0 / 500.0) ** (2 * (post["k"][0] - 1)))
    tau = post["tau_s"][0]
    dens, _err = integrate.quad(lambda s: stats.t.pdf(0.15, df=nu, scale=base * np.exp(s)) * stats.norm.pdf(s, 0, tau),
                                -12 * tau, 12 * tau)
    assert got == pytest.approx(np.log(dens), abs=1e-9)


def test_a_year_the_fold_has_not_seen_is_scored_marginally():
    post = _post()
    S, R, ritc = np.array([0.1, -0.05]), np.array([600.0, 90.0]), np.array([0.0, 0.0])
    mixed = FC.two_regime_lppd(S, R, ritc, np.array([-1, 1]), post)
    marg = FC.two_regime_lppd(S, R, ritc, np.array([1, 1]), post, marginal=True)
    cond = FC.two_regime_lppd(S, R, ritc, np.array([1, 1]), post)
    assert mixed[0] == marg[0] and mixed[1] == cond[1]


def test_the_folds_are_table_4s_and_the_sampler_is_the_headlines():
    assert FC.K == OV.K == 5
    tree = ast.parse(_text(os.path.join(SRC, "check_full_model_cv.py")))
    calls = {(getattr(n.func, "attr", None), getattr(getattr(n.func, "value", None), "id", None))
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert ("fold_assignment", "OV") in calls
    names = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "scale_block" in names
    cal = _text(os.path.join(SRC, "calibrate_dispersion_ritc.py"))
    assert "pm.sample(1500, tune=1500, chains=4, cores=SAMPLE_CORES, target_accept=0.98," in cal and "SEED = 42" in cal
    assert (FC.DRAWS, FC.TUNE, FC.CHAINS, FC.TARGET_ACCEPT, FC.FIT_SEED) == (1500, 1500, 4, 0.98, 42)


def _folds(n, k=FC.K, value=None):
    fold = np.arange(n) % k
    out = []
    for f in range(k):
        idx = np.flatnonzero(fold == f)
        lp = {m: [value.get(m, -1.0) if value else -1.0] * len(idx) for m in FC.MODELS}
        out.append({"fold": f, "test_index": idx.tolist(), "lppd": lp, "n_train": int(n - len(idx)),
                    "n_held_out": int(len(idx)), "n_held_out_syndicates": 1, "n_held_out_ritc": 0,
                    "n_held_out_in_unseen_year": 0,
                    "adopted_fit": {"diagnostics": {"divergences": 0, "max_rhat": 1.0, "min_ess_bulk": 1000.0,
                                                    "min_ess_tail": 1000.0}, "posterior_means": {}},
                    "single_regime_divergences": {}, "seconds": 0.0})
    return out


def test_every_observation_is_scored_exactly_once():
    folds = _folds(10)
    e = FC.assemble(10, folds)
    assert all(np.all(e[m] == -1.0) for m in FC.MODELS)
    twice = _folds(10)
    twice[1]["test_index"][0] = twice[0]["test_index"][0]
    with pytest.raises(SystemExit):
        FC.assemble(10, twice)
    # an observation scored twice with none left out is refused too
    extra = _folds(10)
    extra[1]["test_index"].append(extra[0]["test_index"][0])
    for m in FC.MODELS:
        extra[1]["lppd"][m].append(-1.0)
    with pytest.raises(SystemExit):
        FC.assemble(10, extra)
    bad = _folds(10)
    bad[2]["lppd"]["naive"][0] = float("nan")
    with pytest.raises(SystemExit):
        FC.assemble(10, bad)


def test_the_single_regime_totals_must_reproduce_table_4():
    oos = {"n": 10, "folds": 5, "seed": OV.SEED, "held_out_ELPD_model": 3.0, "held_out_ELPD_naive": 1.0}
    oos_size = {"held_out_ELPD": 2.0}
    ok = FC.check_reproduces({"composition": 3.0, "naive": 1.0, "size_only": 2.0}, 10, oos, oos_size)
    assert ok["computed_minus_recorded"] == {"composition": 0.0, "naive": 0.0, "size_only": 0.0}
    with pytest.raises(SystemExit):
        FC.check_reproduces({"composition": 3.0, "naive": 1.0 + 1e-3, "size_only": 2.0}, 10, oos, oos_size)
    with pytest.raises(SystemExit):
        FC.check_reproduces({"composition": 3.0, "naive": 1.0, "size_only": 2.0}, 11, oos, oos_size)


def test_the_contrast_is_table_4s_bootstrap_with_no_z_score():
    syn = np.repeat(np.arange(8), 3)
    d = np.random.default_rng(1).normal(0.2, 1.0, len(syn))
    got = FC.summarise(d, syn)
    ref = CV.contrast(d, syn)
    assert got == {k: ref[k] for k in FC.CONTRAST_KEYS}
    assert not any(k.startswith("z") for k in got) and got["bb_2.5"] < got["bb_97.5"]


def test_compute_writes_every_model_and_contrast_from_the_folds(tmp_path, monkeypatch):
    """compute() on stand-in folds: the totals, contrasts and fold summaries come from the folds as given."""
    import adopted_model as am
    S, R, H, yr, syn, ritc = am.load_sample()
    n = len(S)
    vals = {"adopted_two_regime": -0.5, "adopted_two_regime_year_shock_marginal": -0.6, "composition": -0.7,
            "size_only": -0.65, "naive": -0.9}
    folds = _folds(n, value=vals)
    oos = {"n": n, "folds": 5, "seed": OV.SEED, "held_out_ELPD_model": -0.7 * n, "held_out_ELPD_naive": -0.9 * n}
    p1, p2 = tmp_path / "oos.json", tmp_path / "oos_size.json"
    p1.write_text(json.dumps(oos), encoding="utf-8")
    p2.write_text(json.dumps({"held_out_ELPD": -0.65 * n}), encoding="utf-8")
    monkeypatch.setattr(FC, "OOS", p1)
    monkeypatch.setattr(FC, "OOS_SIZE", p2)
    out = FC.compute(workers=1, folds=folds)
    assert out["n"] == n and out["folds"] == 5
    assert out["held_out_ELPD"]["adopted_two_regime"] == pytest.approx(-0.5 * n)
    c = out["contrasts"]["adopted_two_regime__minus__naive"]
    assert c["delta_ELPD"] == pytest.approx(0.4 * n) and c["P_first_better"] == 1.0
    assert set(out["contrasts"]) == {"%s__minus__%s" % p for p in FC.PAIRS}
    assert out["fold_fits_converged"] is True and len(out["fold_fits"]) == 5
    assert "runtime_seconds" in out
    p1.write_text(json.dumps(dict(oos, held_out_ELPD_naive=-0.95 * n)), encoding="utf-8")
    with pytest.raises(SystemExit):
        FC.compute(workers=1, folds=folds)


# ------------------------------------------------------------------ the committed record (DEFERRED-TO-REFIT)
@pytest.fixture(scope="module")
def rec():
    with io.open(os.path.join(HERE, "results", "check_full_model_cv_results.json"), encoding="utf-8") as _fh:
        return json.load(_fh)


def test_the_record_is_on_the_working_sample_and_reproduces_table_4(rec):
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    import adopted_model as am
    S, R, H, yr, syn, ritc = am.load_sample()
    assert (rec["n"], rec["n_syndicates"], rec["n_ritc"], rec["folds"]) == (len(S), len(set(syn.tolist())),
                                                                            int(ritc.sum()), 5)
    oos = json.loads(_text(os.path.join(HERE, "results", "oos_validation_results.json")))
    size = json.loads(_text(os.path.join(HERE, "results", "oos_size_only_results.json")))
    tot = rec["held_out_ELPD"]
    assert abs(tot["composition"] - oos["held_out_ELPD_model"]) <= FC.REPRODUCE_TOL
    assert abs(tot["naive"] - oos["held_out_ELPD_naive"]) <= FC.REPRODUCE_TOL
    assert abs(tot["size_only"] - size["held_out_ELPD"]) <= FC.REPRODUCE_TOL
    assert sum(f["n_held_out"] for f in rec["fold_fits"]) == len(S)
    for f in rec["fold_fits"]:
        d = f["diagnostics"]
        assert d["divergences"] == 0 and d["max_rhat"] <= 1.01 and f["n_held_out_in_unseen_year"] == 0
    for key, c in rec["contrasts"].items():
        assert c["bb_2.5"] <= c["bb_mean"] <= c["bb_97.5"] and 0.0 <= c["P_first_better"] <= 1.0, key
        assert not any(k.startswith("z") for k in c), key
    a, b = rec["contrasts"]["adopted_two_regime__minus__naive"], rec["held_out_ELPD"]
    assert a["delta_ELPD"] == pytest.approx(b["adopted_two_regime"] - b["naive"])


def test_the_run_time_sits_under_the_key_the_verifier_strips(rec):
    import reproduce
    assert "runtime_seconds" in reproduce.VOLATILE
    assert "runtime_seconds" not in reproduce._strip_volatile(rec)
    assert reproduce.OUTPUTS["check_full_model_cv.py"] == ("results/check_full_model_cv_results.json",)


# ------------------------------------------------------------------ the lead contrast is the new-year (marginal) row ------
def test_a_contrast_reads_by_its_credible_interval_only():
    above = {"bb_2.5": 0.5, "bb_97.5": 3.0}
    below = {"bb_2.5": -3.0, "bb_97.5": -0.5}
    straddle = {"bb_2.5": -0.5, "bb_97.5": 3.0}
    edge = {"bb_2.5": 0.0, "bb_97.5": 3.0}
    assert "lies above zero" in FC.verdict(above) and "scores higher" in FC.verdict(above)
    assert "lies below zero" in FC.verdict(below) and "scores lower" in FC.verdict(below)
    for c in (straddle, edge):
        v = FC.verdict(c)
        assert "includes zero" in v and "not established" in v and "scores higher" not in v


def _compute_toy(tmp_path, monkeypatch, vals):
    import adopted_model as am
    S, R, H, yr, syn, ritc = am.load_sample()
    n = len(S)
    folds = _folds(n, value=vals)
    oos = {"n": n, "folds": 5, "seed": OV.SEED, "held_out_ELPD_model": vals["composition"] * n,
           "held_out_ELPD_naive": vals["naive"] * n}
    p1, p2 = tmp_path / "oos.json", tmp_path / "oos_size.json"
    p1.write_text(json.dumps(oos), encoding="utf-8")
    p2.write_text(json.dumps({"held_out_ELPD": vals["size_only"] * n}), encoding="utf-8")
    monkeypatch.setattr(FC, "OOS", p1)
    monkeypatch.setattr(FC, "OOS_SIZE", p2)
    return FC.compute(workers=1, folds=folds)


def test_the_marginal_new_year_row_leads_and_the_conditional_row_sits_beside_it_with_its_reason(tmp_path, monkeypatch):
    vals = {"adopted_two_regime": -0.5, "adopted_two_regime_year_shock_marginal": -0.72, "composition": -0.7,
            "size_only": -0.65, "naive": -0.9}
    out = _compute_toy(tmp_path, monkeypatch, vals)
    pres = out["presentation"]
    assert pres["lead"]["model"] == "adopted_two_regime_year_shock_marginal" == FC.LEAD
    assert pres["beside"]["model"] == "adopted_two_regime" == FC.CONDITIONAL
    # the contrasts lead with the marginal row, in the record and in the presentation
    assert list(out["contrasts"])[0].startswith(FC.LEAD) and list(out["contrasts"])[:3] == [
        "%s__minus__%s" % (FC.LEAD, o) for o in ("composition", "size_only", "naive")]
    assert list(pres)[:2] == ["lead", "beside"]
    n = out["n"]
    # the lead's figures are the marginal model's, the beside figures the conditional model's
    assert pres["lead"]["held_out_ELPD"] == pytest.approx(-0.72 * n)
    assert pres["beside"]["held_out_ELPD"] == pytest.approx(-0.5 * n)
    assert pres["lead"]["contrasts"]["vs_composition"]["delta_ELPD"] == pytest.approx(-0.02 * n)
    assert pres["beside"]["contrasts"]["vs_composition"]["delta_ELPD"] == pytest.approx(0.2 * n)
    assert pres["conditional_minus_marginal"]["delta_ELPD"] == pytest.approx(0.22 * n)
    # the reason the conditional row is not the lead
    why = pres["beside"]["why_it_is_not_the_lead"]
    assert "own reporting year" in why and "training syndicates" in why and "contemporaneous" in why
    assert "NEW reporting year" in pres["lead"]["scores"] and "integrated out" not in why
    # a new-year score below the comparator is not described as scoring higher
    assert "scores lower" in pres["lead"]["contrasts"]["vs_composition"]["reading"]
    assert "scores higher" in pres["beside"]["contrasts"]["vs_composition"]["reading"]


def test_no_wording_says_the_adopted_model_predicts_better_unless_the_interval_is_above_zero(tmp_path, monkeypatch):
    """With every held-out density a constant the Bayesian-bootstrap interval is a point, so a difference of zero or
    above reads by its interval; the strings the script writes never use 'predicts better' for a contrast whose
    interval includes zero, and the question no longer asks whether the model predicts better."""
    vals = {"adopted_two_regime": -0.6, "adopted_two_regime_year_shock_marginal": -0.7, "composition": -0.7,
            "size_only": -0.65, "naive": -0.9}
    out = _compute_toy(tmp_path, monkeypatch, vals)
    for text in _strings(out):
        low = text.lower()
        if "predict" in low and "better" in low:
            assert text == out["presentation"]["wording_rule"], text
    assert "predict" not in out["question"] and "predict" not in " ".join(out["models"].values())


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def test_the_script_no_longer_says_the_first_model_predicts_better():
    """The docstring, the prints and the strings carry no 'predicts better' for a posterior probability; the one place
    the phrase appears is the wording rule that forbids it."""
    src = _text(os.path.join(SRC, "check_full_model_cv.py"))
    assert src.count("predicts better") == 0 and src.count("predict better") == 1


def test_the_committed_record_leads_with_the_new_year_row_and_reads_by_the_interval(rec):
    """DEFERRED-TO-REFIT: written by the recorded pass."""
    pres = rec["presentation"]
    assert pres["lead"]["model"] == FC.LEAD and pres["beside"]["model"] == FC.CONDITIONAL
    assert list(rec["contrasts"])[0] == "%s__minus__composition" % FC.LEAD
    for blk in (pres["lead"], pres["beside"]):
        model = blk["model"]
        assert blk["held_out_ELPD"] == rec["held_out_ELPD"][model]
        for o in ("composition", "size_only", "naive"):
            c = rec["contrasts"]["%s__minus__%s" % (model, o)]
            shown = blk["contrasts"]["vs_" + o]
            assert shown["delta_ELPD"] == c["delta_ELPD"] and shown["credible_interval_95"] == [c["bb_2.5"], c["bb_97.5"]]
            assert shown["reading"] == FC.verdict(c)
            # the contrast is the difference of the two rows' held-out ELPD (whatever its sign), and the text follows the
            # interval and nothing else: higher exactly where it lies above zero, lower exactly where it lies below,
            # and "includes zero" with "not established" otherwise. The sign of the data's contrast is not asserted.
            assert c["delta_ELPD"] == pytest.approx(rec["held_out_ELPD"][model] - rec["held_out_ELPD"][o])
            assert ("scores higher" in shown["reading"]) == (c["bb_2.5"] > 0)
            assert ("scores lower" in shown["reading"]) == (c["bb_97.5"] < 0)
            assert ("includes zero" in shown["reading"] and "not established" in shown["reading"]) == (
                c["bb_2.5"] <= 0 <= c["bb_97.5"])
    # the lead row is the marginal (new reporting year) row and the conditional one sits beside it, whatever their scores
    assert pres["lead"]["model"] == FC.LEAD == "adopted_two_regime_year_shock_marginal"
    assert pres["beside"]["model"] == FC.CONDITIONAL == "adopted_two_regime"
    assert "own reporting year" in pres["beside"]["why_it_is_not_the_lead"]
    for text in _strings(rec):
        low = text.lower()
        assert not ("predicts better" in low or "predict better" in low) or text == pres["wording_rule"], text
