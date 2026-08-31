#!/usr/bin/env python3
"""Tests binding the FX sensitivity to the adopted fit it claims to compare with.

Round 37: the manuscript's currency table printed a reduced-draw refit (k=0.608,
gamma=0.260, floor=0.0206, nu_clean=2.40) as "the adopted sterling-converted
two-regime fit" -- fx_sensitivity.py had imported proxy_stress_bayes' 2x500-draw
refitter for tractability, its stored file held point estimates only, and nothing
compared the printed row against the published calibration.

These tests make that class of drift a failure:

  * the FX script's sampling constants must equal the calibration script's own
    pm.sample call, read from calibrate_dispersion_ritc.py's AST -- one source of
    truth, so a calibration change drags the FX script with it;
  * the FX script must build on adopted_model.scale_block/load_sample and must NOT
    import the reduced-draw fitter;
  * the committed result file must record the adopted configuration, an
    in-tolerance agreement check, HDIs and diagnostics for both fits, and interval
    comparisons that pass;
  * the converted fit must equal the published calibration EXACTLY (same
    implementation, data, seed and configuration make it the same posterior).

Run:  python -m pytest src/test_fx_sensitivity.py -q
"""
import ast
import io
import json
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX_SRC = os.path.join(HERE, "src", "fx_sensitivity.py")
CAL_SRC = os.path.join(HERE, "src", "calibrate_dispersion_ritc.py")
FX_JSON = os.path.join(HERE, "results", "fx_sensitivity_results.json")
CAL_JSON = os.path.join(HERE, "model", "dispersion_calibration_ritc.json")
VU_JSON = os.path.join(HERE, "results", "vignette_uncertainty_results.json")

PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")


def _read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def _module_constants(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node.value, ast.Tuple):
                vals = [v.value for v in node.value.elts
                        if isinstance(v, ast.Constant)]
                for t in node.targets:
                    if isinstance(t, ast.Tuple) and len(t.elts) == len(vals):
                        for name, val in zip(t.elts, vals):
                            if isinstance(name, ast.Name):
                                out[name.id] = val
            elif isinstance(node.value, ast.Constant):
                for t in targets:
                    out[t] = node.value.value
    return out


def _sample_call(tree):
    """The (draws, tune, chains, target_accept, random_seed) of a pm.sample call."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "sample"):
            kw = {k.arg: k.value for k in node.keywords}
            draws = node.args[0] if node.args else kw.get("draws")
            def val(n):
                if isinstance(n, ast.Constant):
                    return n.value
                if isinstance(n, ast.Name):
                    return ("NAME", n.id)
                return None
            return {"draws": val(draws), "tune": val(kw.get("tune")),
                    "chains": val(kw.get("chains")),
                    "target_accept": val(kw.get("target_accept")),
                    "random_seed": val(kw.get("random_seed"))}
    raise AssertionError("no pm.sample call found")


class TestAdoptedConfiguration:
    def test_the_fx_constants_equal_the_calibration_scripts_call(self):
        """The adopted configuration is read from calibrate_dispersion_ritc.py's
        own AST, so this test moves if the calibration ever does."""
        cal_tree = ast.parse(_read(CAL_SRC))
        cal_call = _sample_call(cal_tree)
        cal_const = _module_constants(cal_tree)
        fx_const = _module_constants(ast.parse(_read(FX_SRC)))
        def resolve(v, consts):
            return consts.get(v[1]) if isinstance(v, tuple) else v
        assert fx_const["DRAWS"] == resolve(cal_call["draws"], cal_const)
        assert fx_const["TUNE"] == resolve(cal_call["tune"], cal_const)
        assert fx_const["CHAINS"] == resolve(cal_call["chains"], cal_const)
        assert fx_const["TARGET_ACCEPT"] == resolve(cal_call["target_accept"], cal_const)
        assert fx_const["SEED"] == resolve(cal_call["random_seed"], cal_const)

    def test_the_fx_script_uses_its_own_constants_in_its_sample_call(self):
        call = _sample_call(ast.parse(_read(FX_SRC)))
        assert call["draws"] == ("NAME", "DRAWS")
        assert call["tune"] == ("NAME", "TUNE")
        assert call["chains"] == ("NAME", "CHAINS")
        assert call["target_accept"] == ("NAME", "TARGET_ACCEPT")
        assert call["random_seed"] == ("NAME", "SEED")

    def test_the_fx_script_builds_on_the_adopted_model(self):
        tree = ast.parse(_read(FX_SRC))
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports[node.module] = {a.name for a in node.names}
        assert {"load_sample", "scale_block",
                "check_against_headline"} <= imports.get("adopted_model", set())
        assert "fit_bayes" not in imports.get("proxy_stress_bayes", set()), \
            "the reduced-draw refitter is back"


class TestCommittedFxResults:
    @pytest.fixture(scope="class")
    def fx(self):
        if not os.path.exists(FX_JSON):
            pytest.skip("fx results not present")
        return json.load(io.open(FX_JSON, encoding="utf-8"))

    @pytest.fixture(scope="class")
    def cal(self):
        return json.load(io.open(CAL_JSON, encoding="utf-8"))

    def test_the_file_records_the_adopted_sampling_configuration(self, fx):
        fx_const = _module_constants(ast.parse(_read(FX_SRC)))
        samp = fx["sampling"]
        assert samp["draws"] == fx_const["DRAWS"]
        assert samp["tune"] == fx_const["TUNE"]
        assert samp["chains"] == fx_const["CHAINS"]
        assert samp["target_accept"] == fx_const["TARGET_ACCEPT"]
        assert samp["seed"] == fx_const["SEED"]
        assert "calibrate_dispersion_ritc" in samp["same_as"]

    def test_the_agreement_check_passed_within_tolerance(self, fx):
        agree = fx["adopted_agreement"]
        assert agree["ok"] is True
        assert agree["rows"], "no per-parameter agreement rows stored"
        for row in agree["rows"]:
            assert row["gap_in_sd"] <= agree["tolerance_sd"], row

    def test_the_converted_fit_is_the_published_calibration(self, fx, cal):
        """Same implementation, data, seed and configuration: the converted fit
        must BE the adopted posterior, not an approximation to it."""
        conv = fx["fits"]["FX-converted to GBP (baseline)"]
        for p in PARAMS:
            assert abs(conv[p] - cal[p]) < 1e-9, (p, conv[p], cal[p])

    def test_both_fits_persist_intervals_and_clean_diagnostics(self, fx):
        for label, fit in fx["fits"].items():
            for p in PARAMS:
                row = fit["params"][p]
                assert row["hdi_2.5"] < row["mean"] < row["hdi_97.5"], (label, p)
                assert row["sd"] > 0
            d = fit["diagnostics"]
            assert d["max_rhat"] <= 1.02, (label, d)
            assert d["min_ess_bulk"] >= 1000, (label, d)
            assert d["divergences"] == 0, (label, d)

    def test_the_interval_comparisons_are_stored_and_pass(self, fx):
        ics = fx["interval_checks"]
        assert ics["floor"]["nominal_inside"] is True
        assert ics["V1_VaR995"]["nominal_inside"] is True
        lo, hi = ics["floor"]["interval_converted_hdi95"]
        assert lo <= ics["floor"]["nominal"] <= hi

    def test_the_v1_interval_is_the_current_vignette_interval(self, fx):
        vu = json.load(io.open(VU_JSON, encoding="utf-8"))
        want = vu["vignette1"]["adjusted"]["var995"]
        got = fx["interval_checks"]["V1_VaR995"]["interval_donor_composition"]
        assert abs(got[0] - want["lo"]) < 1e-12
        assert abs(got[1] - want["hi"]) < 1e-12
