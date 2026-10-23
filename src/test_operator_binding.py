#!/usr/bin/env python3
"""Operator binding: every headline figure is the size-only operator's, and says so.

The review of 29 September 2026 (MAT-1) found the paper's headline vignette figures computed with the
fitted concentration overlay (gamma = 0.4775) while the paper, the README and the tool all called the
size-only operator (gamma = 0) the default. A reader who ran the tool at its defaults got 0.298 where
the paper printed 0.280, and no output said which operator produced it. These tests bind the operator
to the numbers at each level where it is decided:

  * transfer_operator itself: two modes, each from its own fit (option B, 10 October 2026: the headline fit has
    gamma = 0 in the likelihood, the overlay reads the gamma-free fit), the guards that refuse the other mode's
    fit and the retired zeroing outside its one declared script, the stamp;
  * the headline source (vignette_uncertainty) and the worked example, computed now at a small B: the
    headline block is the gamma = 0 transfer at the headline fit's means and the overlay block the gamma-free
    fit's -- each fit's means read here directly, not through transfer_operator -- and each block is stamped
    with its operator;
  * the shipped tool at its own defaults under node (the Vignette 1 preset, clean target, default mode):
    it reproduces the size-only headline, and its worked-example modal prints the gamma in force;
  * the tool's About text and regime labels (review items A-2 and A-4);
  * every recorded JSON output of every manifest step that imports transfer_operator: both stamps present
    and consistent. These read committed outputs, which the recorded pass rewrites: until it has run they
    fail, by design (DEFERRED-TO-REFIT).

Run:  python -m pytest src/test_operator_binding.py -q
"""
import csv
import importlib.util
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pytest

SRC = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SRC)
sys.path.insert(0, SRC)
import transfer_operator as TO                                              # noqa: E402
from test_distortion_tool import (NEEDED, NODE, TEMPLATE, _embedded_data,   # noqa: E402
                                  _read, extract_const, extract_function)


def _module(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _json(rel):
    path = os.path.join(HERE, rel)
    if not os.path.exists(path):
        pytest.skip("%s not present in this checkout" % rel)
    with io.open(path, encoding="utf-8") as _fh:
        return json.load(_fh)


# ------------------------------------------------------------------ the module ------
class TestTheOperatorModule:
    def test_the_modes_and_their_roles(self):
        assert TO.MODES == ("size_only", "overlay")
        assert TO.HEADLINE == TO.SIZE_ONLY == "size_only"
        assert TO.SENSITIVITY == TO.OVERLAY == "overlay"
        assert TO.ROLE == {"size_only": "headline", "overlay": "sensitivity"}

    @pytest.mark.parametrize("bad", ["gamma0", "size-only", "", None, "full"])
    def test_an_unknown_mode_is_refused_everywhere(self, bad):
        for call in (lambda: TO.check(bad), lambda: TO.params({"gamma": 0.4}, bad),
                     lambda: TO.gamma_in_force(0.4, bad), lambda: TO.stamp(bad),
                     lambda: TO.load_draws(bad), lambda: TO.load_calibration(bad)):
            with pytest.raises(ValueError):
                call()

    # ---- option B (10 October 2026): each mode reads its own fit, and params() refuses the other's
    HEADLINE_DRAWS = {"k": np.array([0.6, 0.62, 0.58]), "gamma": np.zeros(3),
                      "sd_undiv": np.array([0.02, 0.021, 0.019]), "nu_clean": np.array([2.4, 2.5, 2.3])}
    GAMMA_FREE_DRAWS = {"k": np.array([0.6, 0.62, 0.58]), "gamma": np.array([0.31, 0.47, 0.66]),
                        "sd_undiv": np.array([0.02, 0.021, 0.019]), "nu_clean": np.array([2.4, 2.5, 2.3])}

    def test_size_only_takes_the_gamma_zero_fit_as_it_is(self):
        draws = {p: v.copy() for p, v in self.HEADLINE_DRAWS.items()}
        draws["gamma"] = np.zeros(3, dtype=int)            # zeros of any dtype are the gamma = 0 fit's
        q = TO.params(draws, TO.SIZE_ONLY)
        assert q is not draws
        assert q["gamma"].shape == (3,) and np.all(q["gamma"] == 0.0) and q["gamma"].dtype == float
        for p in ("k", "sd_undiv", "nu_clean"):
            assert np.array_equal(q[p], draws[p]), "size-only must keep %s at the headline fit's draws" % p
        assert draws["gamma"].dtype == int, "the caller's draws were modified"

    def test_size_only_on_the_gamma_free_fit_is_refused(self):
        """The silent mix-up option B closes: zeroing a fitted gamma is the retired construction, not the headline."""
        with pytest.raises(ValueError, match="retired construction"):
            TO.params(self.GAMMA_FREE_DRAWS, TO.SIZE_ONLY)
        partly = dict(self.HEADLINE_DRAWS, gamma=np.array([0.0, 0.0, 1e-300]))   # one non-zero draw is enough
        with pytest.raises(ValueError):
            TO.params(partly, TO.SIZE_ONLY)
        with pytest.raises(ValueError):
            TO.params({"k": 0.6, "gamma": 0.4775}, TO.SIZE_ONLY)

    def test_the_overlay_on_the_gamma_zero_fit_is_refused(self):
        with pytest.raises(ValueError, match="gamma-free fit"):
            TO.params(self.HEADLINE_DRAWS, TO.OVERLAY)
        with pytest.raises(ValueError):
            TO.params({"k": 0.6, "gamma": 0.0}, TO.OVERLAY)
        over = TO.params(self.GAMMA_FREE_DRAWS, TO.OVERLAY)
        assert over is not self.GAMMA_FREE_DRAWS
        assert all(np.array_equal(over[p], self.GAMMA_FREE_DRAWS[p]) for p in over)

    def test_posterior_means_are_handled_like_draws(self):
        assert TO.params({"k": 0.6, "gamma": 0.0, "sd_undiv": 0.02}, TO.SIZE_ONLY) == \
            {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.02}
        mp = {"k": 0.6, "gamma": 0.4775, "sd_undiv": 0.02}
        assert TO.params(mp, TO.OVERLAY) == mp
        assert mp["gamma"] == 0.4775

    def test_a_parameter_set_without_gamma_is_refused(self):
        with pytest.raises(KeyError):
            TO.params({"k": 0.6}, TO.SIZE_ONLY)

    def test_the_retired_zeroing_is_refused_from_an_undeclared_caller(self):
        with pytest.raises(ValueError, match="may not build the retired"):
            TO.params(self.GAMMA_FREE_DRAWS, TO.SIZE_ONLY, retired_zeroing=True)

    @staticmethod
    def _call_from(filename, draws, mode, **kw):
        """Call TO.params from code whose file name is `filename`: the caller check reads the calling frame."""
        ns = {"TO": TO}
        exec(compile("def call(d, m, **kw):\n    return TO.params(d, m, **kw)\n", filename, "exec"), ns)
        return ns["call"](draws, mode, **kw)

    def test_the_retired_zeroing_is_allowed_only_where_declared(self):
        declared = os.path.join(SRC, "check_gamma_free_fit.py")
        assert set(TO.RETIRED_ZEROING_DECLARED) == {"check_gamma_free_fit.py"}
        q = self._call_from(declared, self.GAMMA_FREE_DRAWS, TO.SIZE_ONLY, retired_zeroing=True)
        assert np.all(q["gamma"] == 0.0) and np.array_equal(q["k"], self.GAMMA_FREE_DRAWS["k"])
        assert np.all(self.GAMMA_FREE_DRAWS["gamma"] > 0), "the caller's draws were modified"
        with pytest.raises(ValueError, match="may not build the retired"):
            self._call_from(os.path.join(SRC, "vignette_uncertainty.py"), self.GAMMA_FREE_DRAWS, TO.SIZE_ONLY,
                            retired_zeroing=True)
        with pytest.raises(ValueError, match="not an overlay"):
            self._call_from(declared, self.GAMMA_FREE_DRAWS, TO.OVERLAY, retired_zeroing=True)
        with pytest.raises(ValueError, match="already identically 0"):
            self._call_from(declared, self.HEADLINE_DRAWS, TO.SIZE_ONLY, retired_zeroing=True)

    @staticmethod
    def _stamp_from(filename):
        """Call TO.stamp_retired from code whose file name is `filename`."""
        ns = {"TO": TO}
        exec(compile("def call():\n    return TO.stamp_retired('the retired zeroing')\n", filename, "exec"), ns)
        return ns["call"]()

    def test_a_same_named_script_elsewhere_is_refused(self, tmp_path):
        """Review rev13, D5: the caller is authorised by its resolved path in this repository's src/, not by its file
        name, so a check_gamma_free_fit.py anywhere else may neither build nor stamp the retired construction."""
        declared = os.path.join(SRC, "check_gamma_free_fit.py")
        assert self._stamp_from(declared)["operator"] == TO.RETIRED_ZEROING
        for elsewhere in (str(tmp_path / "check_gamma_free_fit.py"), os.path.join(HERE, "check_gamma_free_fit.py"),
                          os.path.join(SRC, "sub", "check_gamma_free_fit.py")):
            with pytest.raises(ValueError, match="may not build the retired"):
                self._call_from(elsewhere, self.GAMMA_FREE_DRAWS, TO.SIZE_ONLY, retired_zeroing=True)
            with pytest.raises(ValueError, match="build the retired construction"):
                self._stamp_from(elsewhere)
        # the same file reached through a path that is not normalised is the declared one
        dotted = os.path.join(SRC, "sub", "..", "check_gamma_free_fit.py")
        assert self._stamp_from(dotted)["operator"] == TO.RETIRED_ZEROING
        with pytest.raises(ValueError, match="build the retired construction"):
            self._stamp_from(os.path.join(SRC, "vignette_uncertainty.py"))

    def test_only_the_declared_scripts_ask_for_the_retired_zeroing(self):
        """A source scan, so a new caller is caught before it runs: every retired_zeroing=True is in a declared
        script, and each declared script uses it."""
        import ast
        users = set()
        for fn in sorted(os.listdir(SRC)):
            if not fn.endswith(".py") or fn.startswith("test_") or fn == "transfer_operator.py":
                continue
            with io.open(os.path.join(SRC, fn), encoding="utf-8") as _fh:
                tree = ast.parse(_fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "retired_zeroing" and \
                        not (isinstance(node.value, ast.Constant) and node.value.value is False):
                    users.add(fn)
        assert users == set(TO.RETIRED_ZEROING_DECLARED)

    def test_gamma_in_force(self):
        assert TO.gamma_in_force(0.0, TO.SIZE_ONLY) == 0.0
        assert TO.gamma_in_force(0.4775, TO.OVERLAY) == 0.4775
        with pytest.raises(ValueError):
            TO.gamma_in_force(0.4775, TO.SIZE_ONLY)
        with pytest.raises(ValueError):
            TO.gamma_in_force(0.0, TO.OVERLAY)

    def test_each_mode_names_its_own_fit(self):
        import adopted_model as am
        import calibrate_dispersion_ritc as cr
        import calibrate_dispersion_ritc_gamma_free as cg
        assert TO.SOURCE[TO.SIZE_ONLY] == (am.HEADLINE_JSON, am.HEADLINE_DRAWS) == (cr.OUT, cr.DRAWS)
        assert TO.SOURCE[TO.OVERLAY] == (am.GAMMA_FREE_JSON, am.GAMMA_FREE_DRAWS) == (cg.OUT, cg.DRAWS)

    def test_load_draws_refuses_a_file_that_is_not_the_modes_fit(self, tmp_path, monkeypatch):
        def npz(name, gamma):
            p = tmp_path / name
            np.savez(p, k=np.full(3, 0.6), gamma=gamma, sd_undiv=np.full(3, 0.02), sd_div=np.full(3, 0.05),
                     nu_clean=np.full(3, 5.0), nu_ritc=np.full(3, 7.0), reference_size=np.array([500.0]),
                     hhi_floor=np.array([0.01]), hhi_ceil=np.array([1.0]))
            return p
        zero, fitted = npz("zero.npz", np.zeros(3)), npz("fitted.npz", np.full(3, 0.3))
        monkeypatch.setattr(TO, "SOURCE", {TO.SIZE_ONLY: (None, zero), TO.OVERLAY: (None, fitted)})
        d, ref, lo, hi = TO.load_draws(TO.SIZE_ONLY)
        assert np.all(d["gamma"] == 0) and (ref, lo, hi) == (500.0, 0.01, 1.0)
        assert np.all(TO.load_draws(TO.OVERLAY)[0]["gamma"] == 0.3)
        monkeypatch.setattr(TO, "SOURCE", {TO.SIZE_ONLY: (None, fitted), TO.OVERLAY: (None, zero)})
        with pytest.raises(ValueError):
            TO.load_draws(TO.SIZE_ONLY)
        with pytest.raises(ValueError):
            TO.load_draws(TO.OVERLAY)

    def test_the_stamp_names_operator_role_and_construction(self):
        for mode in TO.MODES:
            s = TO.stamp(mode)
            assert set(s) == {"operator", "operator_role", "operator_construction"}
            assert s["operator"] == mode and s["operator_role"] == TO.ROLE[mode]
        head = TO.stamp(TO.HEADLINE)["operator_construction"]
        assert "gamma fixed at 0 in the likelihood" in head and "a refit, not a zeroing" in head
        assert "set to zero in every retained posterior draw" not in head, "the retired construction is back"
        assert "gamma-free fit" in TO.stamp(TO.OVERLAY)["operator_construction"]


# --------------------------------------------- the headline source, computed now ------
#: each mode's own fit, named here and not read from transfer_operator
HEADLINE_DRAWS = os.path.join(HERE, "model", "dispersion_posterior_draws_ritc.npz")
GAMMA_FREE_DRAWS = os.path.join(HERE, "model", "dispersion_posterior_draws_ritc_gamma_free.npz")


def _gamma_by_hand(means, gamma):
    """Posterior means with gamma set directly -- deliberately not through transfer_operator."""
    th = dict(means)
    th["gamma"] = gamma
    return th


@pytest.fixture(scope="module")
def vu_small():
    """vignette_uncertainty's whole record at B = 8 (the centres do not depend on B)."""
    vu = _module("vu_for_binding", "src/vignette_uncertainty.py")
    vu.B = 8
    out, _prim, _centres = vu.compute()
    return vu, out


class TestTheHeadlineSource:
    def test_the_record_is_stamped_headline_at_the_top_and_overlay_below(self, vu_small):
        """vu_small computes from the regenerated calibrations."""
        _vu, out = vu_small
        assert (out["operator"], out["operator_role"]) == ("size_only", "headline")
        ov = out["overlay_sensitivity"]
        assert (ov["operator"], ov["operator_role"]) == ("overlay", "sensitivity")
        assert "operator" not in out["meta"], "meta.operator was the formula text; it is operator_form now"

    def test_the_headline_centres_are_the_gamma_zero_transfer(self, vu_small):
        """Needs the regenerated calibrations, each mode's own fit."""
        vu, out = vu_small
        S, R, H, synd, year = vu.load_pool()
        ritc = vu.load_ritc(synd, year)
        v1, v2o, v2n = vu.load_targets()
        with np.load(HEADLINE_DRAWS) as _h, np.load(GAMMA_FREE_DRAWS) as _o:
            z_h, z_o = {key: _h[key] for key in _h.files}, {key: _o[key] for key in _o.files}
        means = {p: float(z_h[p].mean()) for p in TO.OPERATOR_KEYS}
        means_o = {p: float(z_o[p].mean()) for p in TO.OPERATOR_KEYS}
        assert means["gamma"] == 0.0, "the headline fit has gamma = 0 in the likelihood"
        cfg = (float(z_h["reference_size"][0]), float(z_h["hhi_floor"][0]), float(z_h["hhi_ceil"][0]))
        for block, mp, gamma in ((out, means, 0.0), (out["overlay_sensitivity"], means_o, means_o["gamma"])):
            th = _gamma_by_hand(mp, gamma)
            a1 = vu.transfer(S, R, H, v1, th, cfg, ritc)
            d995 = (vu.var_q(vu.transfer(S, R, H, v2n, th, cfg, ritc), 0.995)
                    - vu.var_q(vu.transfer(S, R, H, v2o, th, cfg, ritc), 0.995))
            c = block["centres_full_pool_posterior_mean"]
            assert c["V1_adj"]["v995"] == pytest.approx(vu.var_q(a1, 0.995), abs=1e-12), block.get("operator")
            assert c["V1_adj"]["v99"] == pytest.approx(vu.var_q(a1, 0.99), abs=1e-12), block.get("operator")
            assert c["V2_d995"] == pytest.approx(d995, abs=1e-12), block.get("operator")
        assert means_o["gamma"] > 0.05
        assert out["centres_full_pool_posterior_mean"]["V1_adj"]["v995"] != pytest.approx(
            out["overlay_sensitivity"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"], abs=1e-3), \
            "the two operators must give different headlines, or these checks have no power"

    def test_the_headline_concentration_share_is_exactly_zero(self, vu_small):
        """vu_small computes from the regenerated calibrations."""
        _vu, out = vu_small
        comp = out["operator_comparison"]["V1_adj_v995"]
        assert comp["headline"] == out["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
        assert comp["overlay"] == out["overlay_sensitivity"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]

    def test_the_worked_example_is_the_gamma_zero_transfer(self):
        """Needs the regenerated calibrations, each mode's own fit."""
        we = _module("we_for_binding", "src/worked_example_donor.py")
        out = we.compute()
        mp, _draws = we.load_params(TO.SIZE_ONLY)
        mp_o, _draws_o = we.load_params(TO.OVERLAY)
        donors = we.load_pool()
        A, B = we.select_donors(donors)
        (Rq, Hq) = we.TARGET
        cfg = (mp["ref"], mp["hlo"], mp["hce"])
        assert (out["operator"], out["gamma_in_force"]) == ("size_only", 0.0)
        assert out["overlay_sensitivity"]["operator"] == "overlay"
        assert out["overlay_sensitivity"]["params"] == mp_o and out["params"] == mp
        for key, idx in (("donorA", A), ("donorB", B)):
            d = donors[idx]
            for block, m, gamma in ((out, mp, 0.0), (out["overlay_sensitivity"], mp_o, mp_o["gamma"])):
                lam = (we.sigma(Rq, Hq, m["k"], gamma, m["sd_undiv"], m["sd_div"], *cfg)
                       / we.sigma(d["opening_reserves_gbp_m"], d["hhi"], m["k"], gamma, m["sd_undiv"],
                                  m["sd_div"], *cfg))
                assert block[key]["lambda"] == pytest.approx(lam, rel=1e-12), (key, gamma)
                assert block[key]["gamma_in_force"] == pytest.approx(gamma, abs=0)
            assert out[key]["lambda_concentration_channel"] == 1.0
        assert out["overlay_sensitivity"]["donorB"]["lambda_concentration_channel"] != pytest.approx(1.0, abs=1e-3), \
            "Donor B is the mix-mismatch illustration: under the overlay its concentration channel must move"


# ----------------------------------------------------- the tool at its own defaults ------
TOOL_FUNCTIONS = NEEDED + ("computeDistributions", "percentile", "distStats", "applyPreset",
                           "getTargetWeights", "updateWeightTotal", "currentRegime", "compute",
                           "workedExampleHtml", "fmt", "fmtPct")
RENDERERS = ("renderSummary", "renderDistributionPlot", "renderTailPlot", "renderStatsTable",
             "renderWaterfall", "renderDecompTable", "renderDonorTable", "renderMetaGrid")


def tool_defaults():
    """What a reader who opens the tool and presses Compute gets, read from the template itself."""
    html = _read(TEMPLATE)
    mode = re.search(r"^let GAMMA_MODE = '([a-z_]+)';", html, re.M).group(1)
    init = extract_function(html, "initTool")
    preset = re.search(r"applyPreset\('([a-z_]+)'\)", init).group(1)

    def selected(select_id):
        body = re.search(r'<select id="%s">(.*?)</select>' % select_id, html, re.S).group(1)
        return re.search(r'<option value="([a-z_]+)" selected>', body).group(1)

    reserve = re.search(r'id="reserveSize" value="([0-9.]+)"', html).group(1)
    return {"mode": mode, "preset": preset, "regime": selected("targetRegime"),
            "mode_selected": selected("gammaMode"), "reserve_input": reserve}


def run_tool(body, data, defaults):
    """The tool's own functions under node with a minimal document, set to `defaults`."""
    if NODE is None:
        pytest.skip("node is not available")
    js = _read(TEMPLATE)
    parts = [extract_const(js, n) for n in ("GAMMA_MODES", "PRESETS", "REGIME_LABELS")]
    parts += [extract_function(js, n) for n in TOOL_FUNCTIONS]
    parts += ["function %s() {}" % n for n in RENDERERS]
    prog = ("const DATA = " + json.dumps(data) + ";\n"
            "let GAMMA_MODE = " + json.dumps(defaults["mode"]) + ";\n"
            "let RESULT = null;\n"
            "const _els = {};\n"
            "const document = { getElementById: (id) => (_els[id] = _els[id] || {value: '', style: {},"
            " textContent: '', className: '', innerHTML: '', classList: {add() {}, remove() {}}}) };\n"
            "function alert(msg) { throw new Error('alert: ' + msg); }\n"
            + "\n\n".join(parts) + "\n"
            "document.getElementById('targetRegime').value = " + json.dumps(defaults["regime"]) + ";\n"
            "document.getElementById('gammaMode').value = " + json.dumps(defaults["mode_selected"]) + ";\n"
            "document.getElementById('reserveSize').value = " + json.dumps(defaults["reserve_input"]) + ";\n"
            "applyPreset(" + json.dumps(defaults["preset"]) + ");\n"
            + body + "\n")
    fd, path = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    try:
        with io.open(path, "w", encoding="utf-8") as _fh:
            _fh.write(prog)
        r = subprocess.run([NODE, path], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[-2000:]
        return json.loads(r.stdout)
    finally:
        os.unlink(path)


REPORT = ("compute();\n"
          "console.log(JSON.stringify({v995: RESULT.statsAdj.var995, v99: RESULT.statsAdj.var99,"
          " mode: RESULT.gammaMode, gamma: RESULT.gammaInForce, tSize: RESULT.tSize, tHhi: RESULT.tHhi,"
          " regime: RESULT.regime, tw: RESULT.tw, conc995: RESULT.shapley.var995.conc}));")


@pytest.fixture(scope="module")
def v1_reference():
    """The Vignette 1 target and both operators' V1 centres from the analysis's Python, computed now, each from its
    own fit. It needs the regenerated calibrations."""
    import check_gamma0_vignette as g0
    import vignette_uncertainty as vu
    pool = vu.load_pool()
    ritc = vu.load_ritc(pool[3], pool[4])
    targets = vu.load_targets()
    centres = {}
    for m in TO.MODES:
        draws, ref, hlo, hce = vu.load_draws(m)          # each operator from its own fit
        centres[m] = g0.centres(m, pool, draws, (ref, hlo, hce), ritc, targets)[1]
    with io.open(os.path.join(HERE, "vignettes", "vignette-1", "target_profile.json"),
                                encoding="utf-8") as _fh:
        profile = json.load(_fh)
    return {"centres": centres, "target": targets[0], "profile": profile}


class TestTheToolAtItsDefaults:
    def test_the_defaults_are_the_headline_operator_and_a_clean_target(self):
        d = tool_defaults()
        assert d["mode"] == d["mode_selected"] == TO.HEADLINE, d
        assert d["regime"] == "clean", d

    def test_the_default_preset_is_the_vignette_1_target(self, v1_reference):
        """v1_reference reads the regenerated calibrations."""
        data = _embedded_data()
        got = run_tool(REPORT, data, tool_defaults())
        prof = v1_reference["profile"]
        want = [prof["lob_weights_json"].get(name, 0.0) for name in data["lob_names"]]
        assert got["tw"] == pytest.approx(want, abs=1e-12), "the default preset's mix is not Vignette 1's"
        assert (got["tSize"], got["tHhi"]) == pytest.approx(v1_reference["target"], abs=1e-12)
        assert got["tSize"] == prof["reserve_size"]

    def test_the_tool_at_its_defaults_gives_the_size_only_headline(self, v1_reference):
        """v1_reference reads the regenerated calibrations, and the tool must embed both fits."""
        got = run_tool(REPORT, _embedded_data(), tool_defaults())
        assert got["mode"] == "size_only" and got["gamma"] == 0.0
        assert got["conc995"] == 0.0, "at gamma = 0 the concentration share of the tool's Shapley is exactly zero"
        head = v1_reference["centres"][TO.HEADLINE]
        assert got["v995"] == pytest.approx(head["V1_v995"], abs=5e-7)
        assert got["v99"] == pytest.approx(head["V1_v99"], abs=5e-7)
        assert got["v995"] != pytest.approx(v1_reference["centres"][TO.OVERLAY]["V1_v995"], abs=1e-3)

    def test_the_recorded_headline_is_what_the_tool_gives_at_its_defaults(self, v1_reference):
        """DEFERRED-TO-REFIT: the committed vignette_uncertainty record is the size-only headline."""
        rec = _json("results/vignette_uncertainty_results.json")
        assert rec.get("operator") == TO.HEADLINE, "the committed headline record is not the size-only operator's"
        got = run_tool(REPORT, _embedded_data(), tool_defaults())
        assert rec["centres_full_pool_posterior_mean"]["V1_adj"]["v995"] == pytest.approx(got["v995"], abs=5e-7)


MODAL = ("const out = {};\n"
         "for (const mode of ['size_only', 'overlay']) {\n"
         "  document.getElementById('gammaMode').value = mode;\n"
         "  compute();\n"
         "  const r = RESULT;\n"
         "  const byH = [...r.donors].filter(d => d.reserves !== r.tSize)\n"
         "    .sort((a, b) => Math.abs(Math.log(b.donorHhi / r.tHhi)) - Math.abs(Math.log(a.donorHhi / r.tHhi)));\n"
         "  const byR = [...r.donors].sort((a, b) => Math.abs(Math.log(b.reserves / r.tSize))"
         " - Math.abs(Math.log(a.reserves / r.tSize)));\n"
         "  out[mode] = {gammaInForce: r.gammaInForce, gammaMode: r.gammaMode, tSize: r.tSize, tHhi: r.tHhi,\n"
         "    donors: [byH[0], byR[0]].map(d => ({R: d.reserves, H: d.donorHhi, lam: d.lam,\n"
         "      html: workedExampleHtml(d, r, DATA[GAMMA_MODES[mode].model])}))};\n"
         "}\n"
         "console.log(JSON.stringify(out));")

GAMMA_PRINTED = re.compile("γ in force = (-?[0-9]+\\.[0-9]{4})")
LAMBDA_TOTAL = re.compile("λ<sub>total</sub> = λ<sub>size</sub> × λ<sub>conc</sub></td>"
                          "<td><strong>([0-9.]+)</strong>")


def _sigma(pm, R, H, gamma):
    lo = pm.get("hhi_floor", 0.01)
    hi = pm.get("hhi_ceil", 1.0)
    h = min(max(H, lo), hi)
    x = (max(R, 1e-9) / pm.get("reference_size", 500.0)) * (1.0 / h) ** gamma
    return math.sqrt(pm.get("sd_undiv", 0.0) ** 2 + pm.get("sd_div", 1.0) ** 2 * x ** (2.0 * (pm["k"] - 1.0)))


class TestTheWorkedExampleModal:
    """Review item A-1: Step 3 printed the fitted gamma (0.4775) beside a concentration factor of exactly 1 on the
    size-only default, whose gamma in force is 0. The modal must print the gamma the numbers used."""

    @pytest.fixture(scope="class")
    def modal(self):
        data = _embedded_data()
        return {"size_only": data["pooling_model"], "overlay": data["pooling_model_overlay"]}, \
            run_tool(MODAL, data, tool_defaults())

    def test_the_modal_prints_the_gamma_in_force(self, modal):
        """The shipped tool embeds both fits once it is regenerated."""
        pm, out = modal
        assert pm["size_only"]["gamma"] == 0.0 and pm["overlay"]["gamma"] > 0
        for mode, want in (("size_only", 0.0), ("overlay", pm["overlay"]["gamma"])):
            assert out[mode]["gammaMode"] == mode
            assert out[mode]["gammaInForce"] == pytest.approx(want, abs=0)
            for d in out[mode]["donors"]:
                printed = [float(x) for x in GAMMA_PRINTED.findall(d["html"])]
                assert len(printed) == 2, "Steps 2 and 3 must each print the gamma in force"
                assert all(p == pytest.approx(want, abs=5e-5) for p in printed), (mode, printed, want)
                note = "λ<sub>conc</sub> = 1 exactly" in d["html"]
                assert note == (mode == "size_only"), mode

    def test_the_printed_gamma_reproduces_the_printed_total_multiplier(self, modal):
        """With the printed gamma, sigma_t / sigma_d is the printed lambda_total; with the other mode's gamma it is
        not -- so a modal printing one gamma while computing with another fails here. Each mode's scale is its
        own fit's (option B). The shipped tool embeds both fits once it is regenerated."""
        models, out = modal
        for mode, other in (("size_only", models["overlay"]["gamma"]), ("overlay", 0.0)):
            pm = models[mode]
            r = out[mode]
            for d in r["donors"]:
                g = float(GAMMA_PRINTED.search(d["html"]).group(1))
                lam_printed = float(LAMBDA_TOTAL.search(d["html"]).group(1))

                def lam(gamma):
                    return _sigma(pm, r["tSize"], r["tHhi"], gamma) / _sigma(pm, d["R"], d["H"], gamma)

                slope = abs(lam(g + 1e-4) - lam(g - 1e-4)) / 2e-4
                tol = 5e-7 + slope * 5e-5 + 1e-9
                assert abs(lam(g) - lam_printed) <= tol, (mode, g, lam(g), lam_printed)
                assert abs(lam(g) - d["lam"]) <= tol
            # power: the discriminating donor must separate the two gammas by far more than the tolerance
            d = r["donors"][0]
            gap = abs(_sigma(pm, r["tSize"], r["tHhi"], other) / _sigma(pm, d["R"], d["H"], other) - d["lam"])
            assert gap > 1e-3, "the chosen donor cannot tell the two operators apart"


# ------------------------------------------------------------- the tool's prose ------
def _flat_template():
    return " ".join(_read(TEMPLATE).split())


class TestTheToolsProse:
    def test_the_floor_boundary_is_the_papers(self):
        """Size credit above about GBP1bn cannot be demonstrated; beyond about GBP5bn everything is extrapolation."""
        flat = _flat_template()
        assert re.search(r"above about &pound;1bn.{0,160}cannot be demonstrated", flat), \
            "the About text must say size credit above about GBP1bn cannot be demonstrated"
        assert re.search(r"beyond about &pound;5bn.{0,120}extrapolation", flat)
        assert "an extrapolation the data beyond about &pound;5bn do not resolve" not in flat, \
            "the superseded boundary (only beyond GBP5bn) is back"

    def test_the_regime_labels_cover_transfers_and_take_ons(self):
        html = _read(TEMPLATE)
        body = re.search(r'<select id="targetRegime">(.*?)</select>', html, re.S).group(1)
        labels = dict(re.findall(r'<option value="([a-z_]+)"[^>]*>([^<]+)</option>', body))
        assert set(labels) == {"clean", "ritc", "preserve"}
        for key in ("clean", "ritc"):
            text = labels[key].lower()
            assert "rit" in text and "transfer" in text and "take-on" in text, (key, labels[key])
        assert "no accepted" in labels["clean"].lower()
        assert "external" not in labels["clean"].lower(), "the regime is not only about external RITC"

    def test_the_about_text_says_the_preset_reproduces_the_headline(self):
        flat = _flat_template()
        assert re.search(r"Diversified &pound;500m preset is the paper&rsquo;s Vignette&nbsp;1 target and "
                         r"reproduces its headline", flat)
        assert re.search(r"size-only.{0,120}headline operator", flat, re.I)
        assert not re.search("paper(?:'|’|&rsquo;)s default", flat), \
            "the size-only operator is the paper's HEADLINE operator; 'default' described the old split"
        # round 62's verification: a code comment still said "The paper adopts the SIZE-ONLY operator as its default"
        assert not re.search(r"paper adopts[^.]{0,60}default", flat, re.I), \
            "the paper's operator is its headline operator, not a default the paper adopts"


# --------------------------------------------- every recorded operator output ------
def _stamps(node, path=""):
    if isinstance(node, dict):
        if "operator" in node:
            yield path or "<top>", node
        for k, v in node.items():
            yield from _stamps(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _stamps(v, "%s[%d]" % (path, i))


def _operator_producers():
    """(script, output) for every JSON output of every manifest step that imports transfer_operator.

    Read from the manifest and the sources, so a new producer is covered without being listed here.
    run_analysis.py is covered by name below: most of its 155 outputs carry no transferred figure."""
    rp = _module("reproduce_for_binding", "reproduce.py")
    out = []
    for step in rp.STEPS:
        script = step[0]
        with io.open(os.path.join(SRC, script), encoding="utf-8") as _fh:
            src = _fh.read()
        if script == "run_analysis.py" or not re.search(r"^\s*import transfer_operator\b", src, re.M):
            continue
        out += [(script, rel) for rel in rp.OUTPUTS.get(script, ()) if rel.endswith(".json")]
    return out


PRODUCERS = _operator_producers()


def test_the_producer_scan_finds_the_headline_sources():
    names = {s for s, _ in PRODUCERS}
    for s in ("vignette_uncertainty.py", "check_gamma0_vignette.py", "worked_example_donor.py",
              "gpd_var_uncertainty.py", "bayesian_gpd.py", "error_rate_propagation.py", "proxy_stress_bayes.py",
              "check_gamma_free_fit.py", "check_k_support.py", "check_operator_backtest.py"):
        assert s in names, s
    assert len(PRODUCERS) >= 18, PRODUCERS


#: The producers whose record carries no overlay leg, each with the reason, named exactly. The overlay applies the
#: gamma-free fit's concentration exponent; since option B (the author's decision of 10 October 2026) every refit has
#: gamma fixed at 0 in the likelihood (scale_block's default) and so has none to apply, and the decisions of that day
#: (D3) report the overlay on the full-sample gamma-free fit only. A producer of transferred stresses that refits with
#: gamma = 0 and never reads the gamma-free fit is exempt; every other keeps to the rule below (both stamps), and
#: test_the_overlay_exemption_is_exactly_the_scripts_with_no_gamma holds this list to that, from the sources.
_REFIT = ("refits the adopted model with gamma fixed at 0 in the likelihood (the headline's construction): there is "
          "no fitted concentration exponent for an overlay to apply, and the overlay is reported on the full-sample "
          "gamma-free fit only")
NO_OVERLAY_LEG = {
    "check_fx_timing.py": "the reporting-date and opening-date fits: " + _REFIT,
    "check_skew_t.py": "the skew-t fit and its delta = 0 controls: " + _REFIT,
    "check_k_half_sensitivity.py": "the k = 1/2 fit: " + _REFIT,
    "check_k_support.py": "the wider-support fits: " + _REFIT,
    "check_operator_backtest.py": "the fold refits (and the headline's means for the cheap version): " + _REFIT,
    "fx_sensitivity.py": "the converted and nominal fits: " + _REFIT,
    "check_donor_influence.py": "the fits with and without the donor: " + _REFIT,
    "check_outbound_transfer_sensitivity.py": "the retained-base fit: " + _REFIT,
    "check_cohort_scope.py": "the 672 construction's fit: " + _REFIT,
    "check_cohort_depth_sensitivity.py": "the u <= t-2 and u <= t-3 refits, through check_cohort_scope.fit: " + _REFIT,
    "check_missingness_sensitivity.py": "the unweighted and selection-weighted fits: " + _REFIT,
}

#: the functions that fit the model with gamma = 0 (scale_block's default; fx_sensitivity's adopted-configuration
#: fit, which check_donor_influence and check_outbound_transfer_sensitivity take as a default argument)
_GAMMA0_FITS = ("scale_block", "fit_adopted_config")
#: the names a producer uses to read or write the overlay's (gamma-free) fit
_OVERLAY_NAMES = ("SENSITIVITY", "OVERLAY", "MODES", "SOURCE")


def _fitting_functions(module):
    """The names of the functions defined in src/<module>.py whose own body fits the model with gamma = 0 (a call to
    one of _GAMMA0_FITS): a refit helper that another producer imports and calls, as check_cohort_scope.fit is by
    check_cohort_depth_sensitivity. Empty where the module is not a source file under src/."""
    import ast
    path = os.path.join(SRC, module + ".py")
    if not os.path.isfile(path):
        return set()
    with io.open(path, encoding="utf-8") as _fh:
        tree = ast.parse(_fh.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", getattr(sub.func, "attr", None)) in _GAMMA0_FITS:
                    names.add(node.name)
    return names


def _imported_fits(tree):
    """True where the script uses a refit helper of a source module it imports (`import M as A`, then `A.fit(...)`,
    or a name taken by `from M import fit`): the gamma = 0 refit is then the script's, done through the helper."""
    import ast
    alias, direct = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                alias[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                direct[a.asname or a.name] = (node.module, a.name)
    for f in ast.walk(tree):
        # a reference, not only a call: `fit = CS.fit if fit is None else fit` hands the helper on before it is called
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in alias:
            if f.attr in _fitting_functions(alias[f.value.id]):
                return True
        if isinstance(f, ast.Name) and f.id in direct and direct[f.id][1] in _fitting_functions(direct[f.id][0]):
            return True
    return False


def _scripts_with_no_gamma():
    """Every manifest producer under src/ that fits the model only with gamma = 0 (a scale_block call without
    gamma_prior='halfnormal', a use of fx_sensitivity.fit_adopted_config, or a call to a helper of an imported source
    module that does either) and never names the overlay (transfer_operator.SENSITIVITY, OVERLAY, MODES or SOURCE),
    found from the sources."""
    import ast
    found = set()
    for fn in sorted({s for s, _ in PRODUCERS}):
        with io.open(os.path.join(SRC, fn), encoding="utf-8") as _fh:
            tree = ast.parse(_fh.read())
        fits, free, overlay = _imported_fits(tree), False, False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in _GAMMA0_FITS:
                fits = True
            if isinstance(node, ast.Name) and node.id == "fit_adopted_config":
                fits = True
            if isinstance(node, ast.keyword) and node.arg == "gamma_prior" and not (
                    isinstance(node.value, ast.Constant) and node.value.value == "fixed_0"):
                free = True
            if (isinstance(node, ast.Attribute) and node.attr in _OVERLAY_NAMES
                    and getattr(node.value, "id", None) in ("transfer_operator", "TO")):
                overlay = True
        if fits and not free and not overlay:
            found.add(fn)
    return found


def test_a_refit_through_an_imported_helper_is_a_gamma_zero_refit():
    """The scan follows a script into the source modules it imports: check_cohort_scope.fit refits with scale_block
    (gamma = 0), so a script that hands it on or calls it is a gamma = 0 refitter; numpy's `fit`-named attribute and
    an import of a module with no such function are not."""
    import ast
    assert "fit" in _fitting_functions("check_cohort_scope")
    assert _fitting_functions("no_such_source_module") == set()
    assert _imported_fits(ast.parse("import check_cohort_scope as CS\nf = CS.fit if g is None else g\n"))
    assert _imported_fits(ast.parse("import check_cohort_scope\ncheck_cohort_scope.fit(1)\n"))
    assert _imported_fits(ast.parse("from check_cohort_scope import fit\nfit(1)\n"))
    assert not _imported_fits(ast.parse("import numpy as np\nnp.fit(1)\n"))
    assert not _imported_fits(ast.parse("import check_cohort_scope as CS\nCS.arrays(1)\n"))


def test_the_overlay_exemption_is_exactly_the_scripts_with_no_gamma():
    assert set(NO_OVERLAY_LEG) == _scripts_with_no_gamma()
    assert set(NO_OVERLAY_LEG) <= {s for s, _ in PRODUCERS}, "an exempt script must be a producer this scan reads"
    assert all(NO_OVERLAY_LEG.values())


@pytest.mark.parametrize("script,rel", PRODUCERS, ids=[r for _s, r in PRODUCERS])
def test_every_recorded_operator_output_carries_both_stamps(script, rel):
    """DEFERRED-TO-REFIT: each recorded output says which figures are the headline operator's and which the overlay's."""
    rec = _json(rel)
    stamps = list(_stamps(rec))
    for where, s in stamps:
        if s["operator"] == TO.RETIRED_ZEROING:
            # the retired construction's label: only where it is declared, and never an operator in force
            assert script in TO.RETIRED_ZEROING_DECLARED, (rel, where)
            assert s.get("operator_role") == TO.RETIRED_ROLE, (rel, where, s.get("operator_role"))
            continue
        assert s["operator"] in TO.MODES, "%s%s: operator %r is not a mode" % (rel, where, s["operator"])
        assert s.get("operator_role") == TO.ROLE[s["operator"]], (rel, where, s.get("operator_role"))
    assert any(s["operator"] == TO.HEADLINE for _w, s in stamps), \
        "%s (%s): no block says it is the headline size-only operator's" % (rel, script)
    if script in NO_OVERLAY_LEG:
        # an exact exemption: the record has no overlay block, so a stamp for one means the exemption is stale
        assert not any(s["operator"] == TO.OVERLAY for _w, s in stamps), \
            "%s (%s) carries an overlay block: take it off NO_OVERLAY_LEG" % (rel, script)
    else:
        assert any(s["operator"] == TO.OVERLAY for _w, s in stamps), \
            "%s (%s): no block labels the overlay sensitivity" % (rel, script)
    if "operator" in rec:
        assert rec["operator"] == TO.HEADLINE, "%s: the top level must be the headline" % rel


def test_the_loader_bundle_names_the_operator_of_its_stresses():
    """DEFERRED-TO-REFIT: model/exposure_results.json holds the capital, persona and tail-support stresses the
    paper-pack tables print; the bundle says they are the headline size-only operator's."""
    ex = _json("model/exposure_results.json")
    stamp = ex["transfer_operator"]
    assert (stamp["operator"], stamp["operator_role"], stamp["gamma_in_force"]) == ("size_only", "headline", 0.0)
    assert all(block in ex for block in stamp["applies_to"])


def _overlay_sigma(cal, r, h):
    """The gamma-free fit's posterior-mean scale law, written out here (sigma_theta's law, H clipped to the
    calibration's bounds), so the records below are checked against the fit and not against their own producer."""
    hc = min(max(h, cal["hhi_floor"]), cal["hhi_ceil"])
    reff = (r / cal["reference_size"]) * (1.0 / hc) ** cal["gamma"]
    return math.sqrt(cal["sd_undiv"] ** 2 + cal["sd_div"] ** 2 * reff ** (2.0 * (cal["k"] - 1.0)))


def test_the_records_gate_cd_binds_carry_their_operator():
    """DEFERRED-TO-REFIT: the manuscript's gate CD binds a registry entry to the operator stamp of the block it reads,
    and reported five entries unbound (16 October 2026) because their sources stamped nothing: the gamma-free check's
    and the k-support check's records at the top level, and no record held the overlay's 100m/2,000m ratio or its
    concentration effect at 500m. Each is now stamped, and each overlay figure is the gamma-free fit's scale law."""
    gf = _json("results/check_gamma_free_fit_results.json")
    # three constructions in one record: no stamp at its top level (review rev9, C5); each block carries its own
    assert "operator" not in gf
    assert (gf["headline_fit"]["operator"], gf["gamma_free_fit"]["operator"]) == (TO.HEADLINE, TO.OVERLAY)
    v = gf["vignettes"]
    assert (v["headline"]["operator"], v["overlay_sensitivity"]["operator"], v["retired_zeroing"]["operator"]) == (
        TO.HEADLINE, TO.OVERLAY, TO.RETIRED_ZEROING)
    assert gf["size_ratio_100_2000_size_only"]["operator"] == TO.HEADLINE
    assert gf["size_ratio_100_2000_retired_zeroing"]["operator"] == TO.RETIRED_ZEROING
    cal = _json("model/dispersion_calibration_ritc_gamma_free.json")
    ratio = gf["size_ratio_100_2000_overlay"]
    assert (ratio["operator"], ratio["H"]) == (TO.OVERLAY, 0.4)
    assert ratio["gamma_free_fit"] == pytest.approx(_overlay_sigma(cal, 100.0, 0.4) / _overlay_sigma(cal, 2000.0, 0.4),
                                                    rel=1e-12)
    assert ratio["gamma_free_fit"] < gf["size_ratio_100_2000_size_only"]["headline"]
    conc = gf["concentration_effect_500m"]
    assert (conc["operator"], conc["R_m"], conc["H_low"], conc["H_high"]) == (TO.OVERLAY, 500.0, 0.1, 0.9)
    assert conc["sigma_H_low"] == pytest.approx(_overlay_sigma(cal, 500.0, 0.1), rel=1e-12)
    assert conc["sigma_H_high"] == pytest.approx(_overlay_sigma(cal, 500.0, 0.9), rel=1e-12)
    assert conc["ratio"] == pytest.approx(conc["sigma_H_high"] / conc["sigma_H_low"], rel=1e-12) and conc["ratio"] > 1
    ks = _json("results/check_k_support_results.json")
    assert (ks["operator"], ks["operator_role"]) == (TO.HEADLINE, TO.ROLE[TO.HEADLINE])
    assert ks["vignettes"]["operator"] == TO.HEADLINE


# ------------------------------------- the manuscript registry's bindings --------
#: registry entries whose binding the manuscript must still change, each with what is wrong, named exactly: the test
#: fails if one of them binds correctly (take it off) or another binds wrongly
PENDING_MANUSCRIPT = {}
#: the checkout's gate CD module, imported once per manuscript path
_GATE_CD = {}


def _manuscript_paper():
    root = os.environ.get("LLOYDS_PAPER_REPO") or os.path.join("D:" + os.sep, "Latex projects",
                                                                "BAJ - Lloyds reserves rescaling")
    paper = os.path.join(root, "paper")
    if not os.path.exists(os.path.join(paper, "claim_registry.json")):
        pytest.skip("no manuscript at %s: set LLOYDS_PAPER_REPO to the paper repository, or this "
                    "cross-repository check does not run" % paper)
    return paper


def _manuscript_registry():
    with io.open(os.path.join(_manuscript_paper(), "claim_registry.json"), encoding="utf-8") as fh:
        return json.load(fh)


class _PaperOnPath:
    """The manuscript's paper/ folder first on sys.path while gate CD imports its own modules (repos,
    claim_registry); neither name is an analysis module's."""

    def __init__(self, paper):
        self.paper = paper

    def __enter__(self):
        sys.path.insert(0, self.paper)

    def __exit__(self, *exc):
        sys.path.remove(self.paper)


def _gate_cd():
    """(module, paper): the manuscript's paper/audit_numbers.py, imported from the checkout LLOYDS_PAPER_REPO names.
    The walk below takes gate CD's constants from it (OPERATOR_KEY, OPERATORS, RETIRED, RETIRED_WORDS, BINDABLE), so
    the two cannot hold different stamps or words, and test_the_binding_walk_is_gate_cds runs its functions."""
    paper = _manuscript_paper()
    if paper not in _GATE_CD:
        with _PaperOnPath(paper):
            spec = importlib.util.spec_from_file_location("manuscript_audit_numbers",
                                                          os.path.join(paper, "audit_numbers.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        _GATE_CD[paper] = mod
    return _GATE_CD[paper], paper


def _stamps_below(node, g):
    """The stamps gate CD can bind (g.BINDABLE) that the blocks under `node` carry, its own excluded, at any depth."""
    out = set()
    if isinstance(node, dict):
        for v in node.values():
            if isinstance(v, dict):
                if v.get(g.OPERATOR_KEY) in g.BINDABLE:
                    out.add(v[g.OPERATOR_KEY])
                out |= _stamps_below(v, g)
    return out


def _gate_cd_binding(entry, g, analysis=HERE):
    """(bound, stamp, mixed, missing) for a registry entry, walking its source's path as the manuscript's gate CD does
    (audit_numbers.source_binding), with gate CD's constants `g`:

      * a computed entry is bound through its operator_source; an entry with no json or interval source, a computed
        one with no operator_source included, is not bound (bound False);
      * the stamp starts as the file's top-level stamp, if it is one gate CD binds (BINDABLE: the two operators and
        the retired zeroing label), and at each key on the path an overlay_sensitivity block gives its own stamp, or
        "overlay"; a key with the file's declared overlay suffix gives the overlay block's stamp, or "overlay"; and a
        block carrying a BINDABLE stamp gives that stamp. A block carrying any other value under the key keeps the
        stamp it inherits;
      * mixed: the sorted stamps of the bound node's sub-blocks, when the node carries no BINDABLE stamp of its own
        and its sub-blocks carry more than one (a mixed-operator binding, review rev9 C5); else [].

    missing says which file or key on the path does not exist, or None. Gate CD stops walking there and keeps the
    stamp it holds; this test reports it for an entry that declares an operator."""
    key_ = g.OPERATOR_KEY
    src = entry.get("source", {})
    if src.get("kind") == "computed" and isinstance(entry.get("operator_source"), dict):
        src = dict(entry["operator_source"], kind="json")
    if src.get("kind") not in ("json", "interval"):
        return False, None, [], None
    try:
        with io.open(os.path.join(analysis, *src["file"].split("/")), encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception as exc:
        return True, None, [], "%s cannot be read (%s)" % (src.get("file"), type(exc).__name__)
    if not isinstance(d, dict):
        return True, None, [], "%s is not a JSON object" % src["file"]
    stamp = d.get(key_) if d.get(key_) in g.BINDABLE else None
    ov = d.get("overlay_sensitivity") if isinstance(d.get("overlay_sensitivity"), dict) else {}
    suffix = re.match(r"every key in this file ending (\w+)", str(ov.get("keys", "")))
    node, missing = d, None
    for key in src.get("path", []):
        if not isinstance(node, dict):
            missing = missing or "%s has no %r on the path %s" % (src["file"], key, src.get("path"))
            break
        if key not in node:
            missing = missing or "%s has no %r on the path %s" % (src["file"], key, src.get("path"))
        if key == "overlay_sensitivity" and isinstance(node.get(key), dict):
            stamp = node[key].get(key_) if node[key].get(key_) in g.BINDABLE else "overlay"
        elif suffix and str(key).endswith(suffix.group(1)):
            stamp = ov.get(key_) if ov.get(key_) in g.BINDABLE else "overlay"
        elif isinstance(node.get(key), dict) and node[key].get(key_) in g.BINDABLE:
            stamp = node[key][key_]
        node = node.get(key)
    mixed = []
    if isinstance(node, dict) and node.get(key_) not in g.BINDABLE:
        below = _stamps_below(node, g)
        if len(below) > 1:
            mixed = sorted(below)
    return True, stamp, mixed, missing


#: gate CD's findings, each named by the words of its message (audit_numbers.operator_binding_defects)
GATE_CD_FINDINGS = (("it must be one of", "operator-unknown"), ("which is no operator in force", "retired-words"),
                    ("names none of them as its operator_source", "computed-reads"),
                    ("a mixed-operator binding", "mixed"), ("and declares no operator", "undeclared"),
                    ("; its source is the ", "contradicts"), ("is bound to a node that carries no stamp", "unstamped-node"),
                    ("an overlay number printed without naming the overlay", "overlay-sentence"))


def _gate_cd_defects(registry, g, paper, analysis=HERE, computed=None):
    """{entry id: [finding, ...]} for every registry entry gate CD fails or reports unbound, walked as
    audit_numbers.operator_binding_defects does with its constants `g`: an operator that is none of BINDABLE or
    "none" (operator-unknown); retired_zeroing declared by an entry whose quantity lacks g.RETIRED_WORDS
    (retired-words); a computed entry whose function reads a stamped output and names none of them as its
    operator_source (computed-reads, read by gate CD's own computed_stamped_reads, since it inspects the manuscript's
    functions); a mixed-operator binding (mixed); a stamped source and no declaration (undeclared); a declaration the
    stamp contradicts, "none" included (contradicts); a declaration bound to a node with no stamp (unstamped-node);
    and a declaration with no binding gate CD can read, a computed entry with no operator_source included (unbound:
    gate CD reports it, and the manuscript's own gate test requires none). Beyond gate CD: a missing file or key on the
    path of an entry declaring an operator (missing). The check of the manuscript's sentences is not here: it reads
    the paper's prose, not the analysis's blocks."""
    out = {}
    for e in registry:
        found = out.setdefault(e["id"], [])
        declared = e.get(g.OPERATOR_KEY)
        if declared is not None and declared not in tuple(g.BINDABLE) + ("none",):
            found.append("operator-unknown")
            continue
        if declared == g.RETIRED and g.RETIRED_WORDS not in e.get("quantity", ""):
            found.append("retired-words")
            continue
        with _PaperOnPath(paper):
            reads = g.computed_stamped_reads(e, analysis, computed)
        osrc = e.get("operator_source")
        if reads and not (isinstance(osrc, dict) and osrc.get("file") in reads):
            found.append("computed-reads")
        bound, stamp, mixed, missing = _gate_cd_binding(e, g, analysis)
        if missing and declared in g.BINDABLE:
            found.append("missing")
        if mixed:
            found.append("mixed")
        elif stamp is not None and declared is None:
            found.append("undeclared")
        elif stamp is not None and declared != stamp:
            found.append("contradicts")
        elif stamp is None and declared in g.BINDABLE and bound:
            found.append("unstamped-node")
        elif stamp is None and declared in g.BINDABLE:
            found.append("unbound")
    return {k: v for k, v in out.items() if v}


def test_every_registry_binding_is_to_a_block_stamped_with_its_operator():
    """DEFERRED-TO-REFIT: each manuscript registry entry binds as gate CD requires against this checkout's records
    (_gate_cd_defects): no finding gate CD would fail or report unbound, and every file and key on a declaring entry's
    path exists. The review of 18 October 2026 (rev9, C6) found the test read two records' stamps and no binding;
    the review of 21 October 2026 (rev13, D1) found its walk weaker than gate CD's."""
    g, paper = _gate_cd()
    registry = _manuscript_registry()
    wrong = _gate_cd_defects(registry, g, paper)
    bound = [e["id"] for e in registry if e.get("operator") in g.BINDABLE and _gate_cd_binding(e, g)[1]]
    assert len(bound) > 50, len(bound)
    assert set(wrong) == set(PENDING_MANUSCRIPT), {k: v for k, v in wrong.items() if k not in PENDING_MANUSCRIPT} or \
        "an entry on PENDING_MANUSCRIPT now binds correctly: take it off (%s)" % sorted(set(PENDING_MANUSCRIPT) - set(wrong))


#: what the constructed records hold: a top-level size-only stamp with, below it, a block carrying a value that is no
#: stamp gate CD binds, a block holding two constructions, a retired block, an unstamped block and a declared
#: overlay suffix; a record stamped retired at its top level; and a record with no stamp of its own
SYNTHETIC_FILES = {
    "results/rec.json": {"operator": "size_only",
                         "odd": {"operator": "not_a_stamp", "v": 1},
                         "mix": {"h": {"operator": "size_only", "v": 1}, "o": {"operator": "overlay", "v": 2}},
                         "ret": {"operator": "retired_zeroing", "v": 3},
                         "plain": {"v": 5},
                         "overlay_sensitivity": {"operator": "overlay",
                                                 "keys": "every key in this file ending _overlay"},
                         "ratio_overlay": 0.5, "ratio": 0.6},
    "results/top_retired.json": {"operator": "retired_zeroing", "v": 6},
    "results/nostamp.json": {"v": 7},
}
WORDS = "a bridge figure of the retired zeroing construction"


def _synthetic_entry(eid, path, declared=None, quantity="a figure", file="results/rec.json", source=None, **kw):
    e = {"id": eid, "quantity": quantity, "sites": [],
         "source": source or {"kind": "json", "file": file, "path": path}}
    if declared is not None:
        e["operator"] = declared
    e.update(kw)
    return e


#: (entry, the findings expected), one or more per rule
SYNTHETIC = [
    (_synthetic_entry("child-keeps-inherited-stamp", ["odd", "v"], "size_only"), []),
    (_synthetic_entry("child-keeps-inherited-stamp-other-declared", ["odd", "v"], "overlay"), ["contradicts"]),
    (_synthetic_entry("mixed-node", ["mix"], "size_only"), ["mixed"]),
    (_synthetic_entry("one-construction-of-the-mixed-node", ["mix", "h"], "size_only"), []),
    (_synthetic_entry("retired-without-the-words", ["ret"], "retired_zeroing"), ["retired-words"]),
    (_synthetic_entry("retired-with-the-words", ["ret", "v"], "retired_zeroing", quantity=WORDS), []),
    (_synthetic_entry("retired-block-declared-headline", ["ret", "v"], "size_only"), ["contradicts"]),
    (_synthetic_entry("top-level-retired", ["v"], "retired_zeroing", quantity=WORDS,
                      file="results/top_retired.json"), []),
    (_synthetic_entry("top-level-retired-declared-headline", ["v"], "size_only", file="results/top_retired.json"),
     ["contradicts"]),
    (_synthetic_entry("computed-without-operator-source", None, "size_only",
                      source={"kind": "computed", "name": "x"}), ["unbound"]),
    (_synthetic_entry("computed-with-operator-source", None, "overlay", source={"kind": "computed", "name": "x"},
                      operator_source={"file": "results/rec.json", "path": ["mix", "o"]}), []),
    (_synthetic_entry("unstamped-node", ["v"], "size_only", file="results/nostamp.json"), ["unstamped-node"]),
    (_synthetic_entry("stamped-and-undeclared", ["plain", "v"]), ["undeclared"]),
    (_synthetic_entry("none-on-a-stamped-block", ["plain"], "none"), ["contradicts"]),
    (_synthetic_entry("unknown-operator", ["plain"], "gamma"), ["operator-unknown"]),
    (_synthetic_entry("overlay-suffix", ["ratio_overlay"], "overlay"), []),
    (_synthetic_entry("not-the-suffix", ["ratio"], "size_only"), []),
    (_synthetic_entry("overlay-block", ["overlay_sensitivity"], "overlay"), []),
    (_synthetic_entry("computed-reading-a-stamped-record-unnamed", None, "size_only",
                      source={"kind": "computed", "name": "reads"}), ["computed-reads", "unbound"]),
    (_synthetic_entry("computed-reading-a-stamped-record-named", None, "size_only",
                      source={"kind": "computed", "name": "reads"},
                      operator_source={"file": "results/rec.json", "path": ["mix", "h"]}), []),
    (_synthetic_entry("none-on-an-unstamped-node", ["v"], "none", file="results/nostamp.json"), []),
    (_synthetic_entry("none-on-a-missing-file", ["v"], "none", file="results/absent.json"), []),
    (_synthetic_entry("none-computed-without-operator-source", None, "none",
                      source={"kind": "computed", "name": "x"}), []),
    (_synthetic_entry("no-source-gate-cd-reads", None, "size_only", source={"kind": "npz_fraction", "file": "x"}),
     ["unbound"]),
    (_synthetic_entry("missing-key", ["nope"], "size_only"), ["missing"]),
    (_synthetic_entry("missing-file", ["v"], "size_only", file="results/absent.json"), ["missing", "unstamped-node"]),
]


def _reads_a_stamped_record(analysis):
    """A computed entry's function, for gate CD's computed_stamped_reads: it names a stamped output."""
    return os.path.join(analysis, "results/rec.json")


#: the computed functions the constructed entries name
SYNTHETIC_COMPUTED = {"reads": _reads_a_stamped_record}


def _synthetic_analysis(tmp_path):
    for rel, rec in SYNTHETIC_FILES.items():
        path = tmp_path.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with io.open(str(path), "w", encoding="utf-8", newline="") as fh:
            json.dump(rec, fh)
    return str(tmp_path)


def test_the_binding_walk_applies_each_gate_cd_rule(tmp_path):
    """Review rev13, D1, on constructed records: a child block carrying a value gate CD does not bind keeps the stamp
    it inherits; a node with no stamp whose blocks carry two constructions is a mixed binding; retired_zeroing is
    accepted only from an entry whose quantity holds gate CD's RETIRED_WORDS; a top-level retired stamp is read; a
    computed entry with no operator_source is reported unbound, not skipped."""
    g, paper = _gate_cd()
    analysis = _synthetic_analysis(tmp_path)
    got = _gate_cd_defects([e for e, _w in SYNTHETIC], g, paper, analysis, computed=SYNTHETIC_COMPUTED)
    want = {e["id"]: w for e, w in SYNTHETIC if w}
    assert got == want


def _gate_cd_findings(messages, unbound, ids):
    """{entry id: [finding, ...]} from gate CD's own messages and unbound list."""
    out = {}
    for msg in messages:
        owner = max((i for i in ids if msg.startswith(i) and msg[len(i):len(i) + 1] in (" ", "'", ":")), key=len,
                    default=msg)
        out.setdefault(owner, []).extend(name for words, name in GATE_CD_FINDINGS if words in msg)
    for i in unbound:
        out.setdefault(i, []).append("unbound")
    return out


#: the gate CD functions whose behaviour the walk mirrors: everything they read at module level is pinned below
GATE_CD_ROOTS = ("source_binding", "operator_binding_defects", "computed_stamped_reads")
#: every module-level name of the manuscript's paper/audit_numbers.py (at 3b48c84) that GATE_CD_ROOTS read, directly
#: or through the module's own functions they call, with its pinned form (_gate_cd_pin_form): a function by the
#: SHA-256 of its source text (line endings as LF), a compiled pattern by the SHA-256 of its pattern and flags, any
#: other value by its repr. The walk was read against exactly these (reviews rev14 H1, rev15)
GATE_CD_PIN = {
    'BINDABLE': "repr:('size_only', 'overlay', 'retired_zeroing')",
    'OPERATOR_KEY': "repr:'operator'",
    'OVERLAY_NAMES': 're:sha256:d1760e38068841b909a6ef398a1b0d75414b2ca3424a80e106726eef3e370ced',
    'RETIRED': "repr:'retired_zeroing'",
    'RETIRED_WORDS': "repr:'the retired zeroing construction'",
    '_BX_SENTENCE_END': 're:sha256:3b77cb92b50480b7ed445ac137a113e6733619eee324f34b7675c21fdfb8a580',
    '_bx_sentence': 'sha256:99eab1517ce94cefcced568f912ec4b8770f3a6cc92a3b9585262b5f7740b887',
    '_stamped_file': 'sha256:6b0b59e2ab16e702417b01cac1b0e3ab02c2c5a29635d894386df2f600260fad',
    '_stamps_below': 'sha256:a41a03be94763c59591b1c2a7b0279cda1a39df1b07fbd6c6b7224e845cc9ead',
    '_table_head': 'sha256:9f3641d00dc841f3d911a6541b088ea7f63951fa0830e2d6700b9c5ffe46216f',
    'computed_stamped_reads': 'sha256:a99896ac7653b5f712e2e14736fc11c403074c7df971b034528af72f420eaa0a',
    'operator_binding_defects': 'sha256:acb8f30851e840193694bb08ba3b1cb59be8de65318d1cfd472d9a6e8bbe8ccd',
    'source_binding': 'sha256:534cad300781068e36ee79ad5125da1028fe25bb7314a10a6dd89e727741bcc3',
}
#: the module-level names the functions read that are not pinned, each with the reason: the imported standard modules,
#: and the two default paths, which name the machine's checkouts (the walk passes the analysis root and the texts
#: explicitly, so neither default is read here)
GATE_CD_UNPINNED = {
    "io": "a standard module", "json": "a standard module", "os": "a standard module", "re": "a standard module",
    "ANALYSIS": "the default analysis path (repos.py), a machine's location; every call here passes analysis",
    "PAPER": "the manuscript's own folder, read only when texts is None; every call here passes texts",
}


def _gate_cd_pin_form(value):
    import hashlib
    import inspect
    import types
    if isinstance(value, types.FunctionType):
        return "sha256:" + hashlib.sha256(inspect.getsource(value).replace("\r\n", "\n").encode("utf-8")).hexdigest()
    if isinstance(value, re.Pattern):
        return "re:sha256:" + hashlib.sha256(ascii((value.pattern, int(value.flags))).encode("ascii")).hexdigest()
    return "repr:" + ascii(value)


def _gate_cd_reads(g):
    """{name: value} for every module-level name of gate CD's module that GATE_CD_ROOTS read, following the module's
    own functions they call (a builtin is left out)."""
    import ast
    import builtins
    import inspect
    import textwrap
    import types
    seen, todo = {}, list(GATE_CD_ROOTS)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        value = getattr(g, name)
        seen[name] = value
        if isinstance(value, types.FunctionType) and value.__module__ == g.__name__:
            tree = ast.parse(textwrap.dedent(inspect.getsource(value)))
            todo += sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                            and hasattr(g, n.id) and not hasattr(builtins, n.id)})
    return seen


def test_gate_cd_is_the_source_the_walk_mirrors():
    """The drift test below compares answers only on the cases it runs, so a new gate CD rule that fires on no case
    there would pass it (review rev14, H1). Every module-level name gate CD's binding functions read -- the functions
    themselves and those they call, the constants (BINDABLE, OPERATOR_KEY, RETIRED, RETIRED_WORDS) and the patterns
    (OVERLAY_NAMES, _BX_SENTENCE_END) -- is pinned, and the names read are exactly those pinned and those
    GATE_CD_UNPINNED names (review rev15). Any change fails here until the walk has been re-read against it and the
    pin updated."""
    g, _paper = _gate_cd()
    reads = _gate_cd_reads(g)
    got = {n: _gate_cd_pin_form(v) for n, v in reads.items() if n not in GATE_CD_UNPINNED}
    assert set(reads) == set(GATE_CD_PIN) | set(GATE_CD_UNPINNED), (
        "gate CD's binding functions now read %s and no longer read %s: re-read the walk here against them, then "
        "update GATE_CD_PIN" % (sorted(set(reads) - set(GATE_CD_PIN) - set(GATE_CD_UNPINNED)),
                                sorted((set(GATE_CD_PIN) | set(GATE_CD_UNPINNED)) - set(reads))))
    changed = sorted(n for n in got if got[n] != GATE_CD_PIN[n])
    assert not changed, (
        "gate CD's %s in %s changed: re-read the walk here (_gate_cd_binding, _gate_cd_defects, and the constructed "
        "cases in SYNTHETIC) against it, then update GATE_CD_PIN (%s)"
        % (", ".join(changed), g.__file__, {n: got[n] for n in changed}))


def test_the_binding_walk_is_gate_cds(tmp_path):
    """The walk above and gate CD give the same answers on the cases run here: the stamps this analysis writes are
    the ones gate CD binds, and gate CD's own source_binding and operator_binding_defects, imported from the
    manuscript checkout, give the walk's answers on every entry of the live registry against this checkout and on
    every constructed case (the walk's extra "missing" finding aside, and gate CD's check of the paper's sentences,
    which is given no text). A gate rule that fires on none of these cases is caught by the source pin
    (test_gate_cd_is_the_source_the_walk_mirrors), not here."""
    g, paper = _gate_cd()
    assert g.OPERATOR_KEY == "operator"
    assert tuple(g.OPERATORS) == (TO.SIZE_ONLY, TO.OVERLAY) == tuple(TO.MODES)
    assert g.RETIRED == TO.RETIRED_ZEROING and tuple(g.BINDABLE) == tuple(g.OPERATORS) + (g.RETIRED,)
    assert g.RETIRED_WORDS == "the retired zeroing construction"
    cases = [(_manuscript_registry(), HERE, None),
             ([e for e, _w in SYNTHETIC], _synthetic_analysis(tmp_path), SYNTHETIC_COMPUTED)]
    for registry, analysis, computed in cases:
        with _PaperOnPath(paper):
            for e in registry:
                assert _gate_cd_binding(e, g, analysis)[:3] == tuple(g.source_binding(e, analysis)), e["id"]
            messages, unbound = g.operator_binding_defects({}, analysis, registry, computed)
        gate = _gate_cd_findings(messages, unbound, [e["id"] for e in registry])
        mine = {k: [f for f in v if f != "missing"] for k, v in
                _gate_cd_defects(registry, g, paper, analysis, computed).items()}
        assert {k: sorted(v) for k, v in gate.items()} == {k: sorted(v) for k, v in mine.items() if v}, \
            (messages, unbound)
    # the constructed cases reach every finding the walk shares with gate CD
    assert {f for _e, w in SYNTHETIC for f in w} == ({n for _w, n in GATE_CD_FINDINGS} - {"overlay-sentence"}) | {
        "unbound", "missing"}


@pytest.mark.parametrize("v", [1, 2])
def test_the_recorded_vignette_workings_name_their_operators(v):
    """DEFERRED-TO-REFIT: run_analysis's vignette outputs -- the workings are the headline's, the mix-mismatch
    worked example is the labelled overlay illustration, and the headline decomposition has no concentration share."""
    base = "vignettes/vignette-%d/" % v
    meta = _json(base + "metadata.json")
    assert (meta["operator"], meta["concentration_exponent_gamma_in_force"]) == ("size_only", 0.0)
    assert _json(base + "worked_example_size_mismatch.json")["operator"] == "size_only"
    mix = _json(base + "worked_example_mix_mismatch.json")
    assert mix["operator"] == "overlay"
    assert mix["gamma_in_force"] == meta["concentration_exponent_gamma_fitted"] > 0
    column = "concentration_effect" if v == 1 else "concentration_change_effect"
    with io.open(os.path.join(HERE, base + "decomposition_summary.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(float(r[column]) == 0.0 for r in rows), "the headline decomposition has a concentration share"


def test_the_proxy_stress_headline_is_invariant_under_a_perturbed_index(monkeypatch):
    """proxy_stress_bayes.headline_block: the published headline (gamma = 0) transfers identically on every perturbed
    concentration index, and the difference is computed, not asserted; a gamma = 0.4 'headline' would move, which the
    operator guard refuses before it can be written."""
    import proxy_stress_bayes as PSB
    cal = {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.03, "sd_div": 0.06, "nu_clean": 5.0, "nu_ritc": 7.0}
    monkeypatch.setattr(TO, "load_calibration", lambda mode: dict(cal))
    rng = np.random.default_rng(5)
    n = 60
    S, R = rng.normal(0.0, 0.05, n), np.exp(rng.normal(np.log(300.0), 1.0, n))
    H, ritc = rng.uniform(0.1, 0.9, n), (rng.uniform(size=n) < 0.1).astype(float)
    perturbed = [rng.permutation(H), np.clip(H * 1.5, 0.01, 1.0)]
    out = PSB.headline_block(S, R, H, ritc, (300.0, 0.3), (400.0, 0.2), perturbed)
    assert (out["operator"], out["operator_role"]) == ("size_only", "headline")
    inv = out["invariance_under_perturbed_concentration"]
    assert inv["invariant"] is True and inv["max_abs_difference"] == 0.0 and inv["n_perturbed_indices"] == 2
    cal["gamma"] = 0.4
    with pytest.raises(ValueError):
        PSB.headline_block(S, R, H, ritc, (300.0, 0.3), (400.0, 0.2), perturbed)
