#!/usr/bin/env python3
"""The error-rate propagation, re-run on the current fit (src/error_rate_propagation.py).

The extraction error-rate study simulated its unfound errors onto Vignette 1's VaR99.5 once, on a 685-record
fit, and the manuscript said it ran on the final fit (review of 29 September 2026, M-3). The manifest step
now re-runs it on the fit in the tree. These tests hold it to the study (its constants, read from the
archive's own script; its inputs, read from the archive), to itself (seeded, and a pool with nothing unread
cannot move), and to the headline it perturbs: it refuses unless that is vignette_uncertainty's own centre
under the same operator, and it records the fit it ran on.

Run:  python -m pytest src/test_error_rate_propagation.py -q
"""
import ast
import io
import json
import os

import numpy as np
import pytest

import error_rate_propagation as E
import transfer_operator as TO
import vignette_uncertainty as vu

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_SCRIPT = os.path.join(HERE, "results", "extraction_error_rate", "scripts", "error_rate_propagation.py")


def _module_constants(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def test_the_constants_are_the_studys_own():
    if not os.path.exists(ARCHIVE_SCRIPT):
        pytest.skip("results/extraction_error_rate/scripts/error_rate_propagation.py not present in this checkout")
    study = _module_constants(ARCHIVE_SCRIPT)
    assert (study["SEED"], study["M"], study["MATERIAL"]) == (E.SEED, E.M, E.MATERIAL)


def test_the_inputs_are_the_archives():
    inp = E.inputs()
    assert (inp["errors"], inp["adjudicable"]) == (8, 162), "the third sample's A_sampled record"
    assert len(inp["shifts"]) == len(inp["confirmed"]) > 0 and np.all(np.isfinite(inp["shifts"]))
    assert inp["read"] and all(s.startswith("syndicate_") for s in inp["read"])


@pytest.fixture(scope="module")
def pool():
    S, R, H, synd, year = vu.load_pool()
    draws, ref, hlo, hce = vu.load_draws()
    ritc = vu.load_ritc(synd, year)
    v1, _o, _n = vu.load_targets()
    thbar = TO.params({p: float(draws[p].mean()) for p in draws}, TO.HEADLINE)
    return S, R, H, ritc, thbar, (ref, hlo, hce), v1


def test_the_simulation_is_seeded(pool):
    S, R, H, ritc, thbar, cfg, v1 = pool
    unread = np.arange(0, len(S), 2)
    shifts = np.array([0.05, -0.02, 0.1])
    a = E.propagate(S, R, H, ritc, thbar, cfg, v1, unread, shifts, 8.5, 154.5, m=12, seed=3)
    b = E.propagate(S, R, H, ritc, thbar, cfg, v1, unread, shifts, 8.5, 154.5, m=12, seed=3)
    c = E.propagate(S, R, H, ritc, thbar, cfg, v1, unread, shifts, 8.5, 154.5, m=12, seed=4)
    assert a == b and a != c


def test_with_every_record_read_nothing_moves(pool):
    S, R, H, ritc, thbar, cfg, v1 = pool
    out = E.propagate(S, R, H, ritc, thbar, cfg, v1, np.array([], int), np.array([0.05]), 8.5, 154.5, m=10, seed=1)
    for setting in ("p_from_posterior", "p_at_posterior_97_5"):
        assert out[setting]["K"]["mean"] == 0.0
        for mm in E.MODELS:
            assert out[setting][mm]["P_abs_relative_change_gt_5pct"] == 0.0
            assert out[setting][mm]["change"]["median"] == 0.0


def test_the_base_is_the_headline_centre(pool):
    S, R, H, ritc, thbar, cfg, v1 = pool
    out = E.propagate(S, R, H, ritc, thbar, cfg, v1, np.array([0, 1]), np.array([0.05]), 8.5, 154.5, m=2, seed=1)
    assert out["V1_VaR995"] == vu.var_q(vu.transfer(S, R, H, v1, thbar, cfg, ritc), 0.995)
    assert thbar["gamma"] == 0.0


# ------------------------------------------------------------------ main(), small ------
@pytest.fixture
def small_main(monkeypatch, tmp_path):
    """main() with 5 replicates, writing to tmp_path and checking against a vignette record written there."""
    real = E.propagate
    monkeypatch.setattr(E, "propagate", lambda *a, **k: real(*a, **dict(k, m=5)))
    monkeypatch.setattr(E, "OUT", tmp_path / "error_rate_propagation_results.json")
    monkeypatch.setattr(vu, "B", 8)
    record, _prim, _centres = vu.compute()
    vu_path = tmp_path / "vignette_uncertainty_results.json"

    def write_vu(rec):
        vu_path.write_text(json.dumps(rec), encoding="utf-8")
        monkeypatch.setattr(E, "VU", vu_path)

    return record, write_vu, E.OUT


def test_main_writes_both_operators_and_the_fit_it_ran_on(small_main):
    record, write_vu, out = small_main
    write_vu(record)
    assert E.main() == 0
    res = json.load(io.open(str(out), encoding="utf-8"))
    assert (res["operator"], res["operator_role"]) == ("size_only", "headline")
    assert res["overlay_sensitivity"]["operator"] == "overlay"
    assert res["V1_VaR995"] == record["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
    assert res["fit"]["n_working_sample"] == len(vu.load_pool()[0])
    import subprocess
    head = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True)
    assert res["fit"]["analysis_commit"] == ((head.stdout.strip() or None) if head.returncode == 0 else None)
    assert isinstance(res["fit"]["tree_dirty_src_model_results"], bool)
    pm = res["per_model"]
    assert set(pm["P_abs_relative_change_gt_5pct"]) == set(E.MODELS)
    assert len(pm["shift_model_relative_change"]["interval_95"]) == 2


@pytest.mark.parametrize("plant", ["wrong_centre", "no_operator"])
def test_main_refuses_a_headline_that_is_not_the_vignette_records(small_main, plant):
    record, write_vu, out = small_main
    rec = json.loads(json.dumps(record))
    if plant == "wrong_centre":
        rec["centres_full_pool_posterior_mean"]["V1_adj"]["v995"] += 1e-6
    else:
        del rec["operator"]
    write_vu(rec)
    with pytest.raises(SystemExit):
        E.main()
    assert not out.exists()


def test_the_recorded_run_is_on_the_current_fit():
    """DEFERRED-TO-REFIT: results/error_rate_propagation_results.json is written by the recorded pass."""
    path = os.path.join(HERE, "results", "error_rate_propagation_results.json")
    if not os.path.exists(path):
        pytest.skip("results/error_rate_propagation_results.json not present in this checkout")
    res = json.load(io.open(path, encoding="utf-8"))
    head = json.load(io.open(os.path.join(HERE, "results", "vignette_uncertainty_results.json"), encoding="utf-8"))
    assert res["operator"] == head["operator"] == TO.HEADLINE
    assert res["V1_VaR995"] == head["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
    assert res["fit"]["n_working_sample"] == head["meta"]["n_donors"]
    assert (res["replicates"], res["seed"], res["materiality_line_relative"]) == (E.M, E.SEED, E.MATERIAL)
