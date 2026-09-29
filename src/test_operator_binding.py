#!/usr/bin/env python3
"""Operator binding: every headline figure is the size-only operator's, and says so.

The review of 29 September 2026 (MAT-1) found the paper's headline vignette figures computed with the
fitted concentration overlay (gamma = 0.4775) while the paper, the README and the tool all called the
size-only operator (gamma = 0) the default. A reader who ran the tool at its defaults got 0.298 where
the paper printed 0.280, and no output said which operator produced it. These tests bind the operator
to the numbers at each level where it is decided:

  * transfer_operator itself: two modes, gamma zeroed in the retained draws (not a refit), the stamp;
  * the headline source (vignette_uncertainty) and the worked example, computed now at a small B: the
    headline block is the gamma = 0 transfer -- gamma zeroed by hand here, not through transfer_operator
    -- the overlay block the fitted one, and each block is stamped with its operator;
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
    return json.load(io.open(path, encoding="utf-8"))


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
                     lambda: TO.gamma_in_force(0.4, bad), lambda: TO.stamp(bad)):
            with pytest.raises(ValueError):
                call()

    def test_size_only_zeroes_gamma_in_every_draw_and_nothing_else(self):
        draws = {"k": np.array([0.6, 0.62, 0.58]), "gamma": np.array([0.31, 0.47, 0.66]),
                 "sd_undiv": np.array([0.02, 0.021, 0.019]), "nu_clean": np.array([2.4, 2.5, 2.3])}
        kept = {p: v.copy() for p, v in draws.items()}
        q = TO.params(draws, TO.SIZE_ONLY)
        assert q is not draws
        assert q["gamma"].shape == (3,) and np.all(q["gamma"] == 0.0) and q["gamma"].dtype == float
        for p in ("k", "sd_undiv", "nu_clean"):
            assert np.array_equal(q[p], kept[p]), "size-only must keep %s at its fitted draws (not a refit)" % p
        for p in draws:
            assert np.array_equal(draws[p], kept[p]), "the caller's draws were modified"
        over = TO.params(draws, TO.OVERLAY)
        assert over is not draws and all(np.array_equal(over[p], kept[p]) for p in draws)

    def test_posterior_means_are_handled_like_draws(self):
        mp = {"k": 0.6, "gamma": 0.4775, "sd_undiv": 0.02}
        assert TO.params(mp, TO.SIZE_ONLY) == {"k": 0.6, "gamma": 0.0, "sd_undiv": 0.02}
        assert TO.params(mp, TO.OVERLAY) == mp
        assert mp["gamma"] == 0.4775

    def test_a_parameter_set_without_gamma_is_refused(self):
        with pytest.raises(KeyError):
            TO.params({"k": 0.6}, TO.SIZE_ONLY)

    def test_gamma_in_force(self):
        assert TO.gamma_in_force(0.4775, TO.SIZE_ONLY) == 0.0
        assert TO.gamma_in_force(0.4775, TO.OVERLAY) == 0.4775

    def test_the_stamp_names_operator_role_and_construction(self):
        for mode in TO.MODES:
            s = TO.stamp(mode)
            assert set(s) == {"operator", "operator_role", "operator_construction"}
            assert s["operator"] == mode and s["operator_role"] == TO.ROLE[mode]
        head = TO.stamp(TO.HEADLINE)["operator_construction"]
        assert "set to zero in every retained posterior draw" in head and "not a refit" in head


# --------------------------------------------- the headline source, computed now ------
def _gamma_by_hand(means, gamma):
    """Posterior means with gamma replaced directly -- deliberately not through transfer_operator."""
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
        _vu, out = vu_small
        assert (out["operator"], out["operator_role"]) == ("size_only", "headline")
        ov = out["overlay_sensitivity"]
        assert (ov["operator"], ov["operator_role"]) == ("overlay", "sensitivity")
        assert "operator" not in out["meta"], "meta.operator was the formula text; it is operator_form now"

    def test_the_headline_centres_are_the_gamma_zero_transfer(self, vu_small):
        vu, out = vu_small
        S, R, H, synd, year = vu.load_pool()
        draws, ref, hlo, hce = vu.load_draws()
        ritc = vu.load_ritc(synd, year)
        v1, v2o, v2n = vu.load_targets()
        means = {p: float(v.mean()) for p, v in draws.items()}
        cfg = (ref, hlo, hce)
        for block, gamma in ((out, 0.0), (out["overlay_sensitivity"], means["gamma"])):
            th = _gamma_by_hand(means, gamma)
            a1 = vu.transfer(S, R, H, v1, th, cfg, ritc)
            d995 = (vu.var_q(vu.transfer(S, R, H, v2n, th, cfg, ritc), 0.995)
                    - vu.var_q(vu.transfer(S, R, H, v2o, th, cfg, ritc), 0.995))
            c = block["centres_full_pool_posterior_mean"]
            assert c["V1_adj"]["v995"] == pytest.approx(vu.var_q(a1, 0.995), abs=1e-12), block.get("operator")
            assert c["V1_adj"]["v99"] == pytest.approx(vu.var_q(a1, 0.99), abs=1e-12), block.get("operator")
            assert c["V2_d995"] == pytest.approx(d995, abs=1e-12), block.get("operator")
        assert means["gamma"] > 0.05
        assert out["centres_full_pool_posterior_mean"]["V1_adj"]["v995"] != pytest.approx(
            out["overlay_sensitivity"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"], abs=1e-3), \
            "the two operators must give different headlines, or these checks have no power"

    def test_the_headline_concentration_share_is_exactly_zero(self, vu_small):
        _vu, out = vu_small
        comp = out["operator_comparison"]["V1_adj_v995"]
        assert comp["headline"] == out["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
        assert comp["overlay"] == out["overlay_sensitivity"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]

    def test_the_worked_example_is_the_gamma_zero_transfer(self):
        we = _module("we_for_binding", "src/worked_example_donor.py")
        out = we.compute()
        mp, _draws = we.load_params()
        donors = we.load_pool()
        A, B = we.select_donors(donors)
        (Rq, Hq) = we.TARGET
        cfg = (mp["ref"], mp["hlo"], mp["hce"])
        assert (out["operator"], out["gamma_in_force"]) == ("size_only", 0.0)
        assert out["overlay_sensitivity"]["operator"] == "overlay"
        for key, idx in (("donorA", A), ("donorB", B)):
            d = donors[idx]
            for block, gamma in ((out, 0.0), (out["overlay_sensitivity"], mp["gamma"])):
                lam = (we.sigma(Rq, Hq, mp["k"], gamma, mp["sd_undiv"], mp["sd_div"], *cfg)
                       / we.sigma(d["opening_reserves_gbp_m"], d["hhi"], mp["k"], gamma, mp["sd_undiv"],
                                  mp["sd_div"], *cfg))
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
        io.open(path, "w", encoding="utf-8").write(prog)
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
    """The Vignette 1 target and both operators' V1 centres from the analysis's Python, computed now."""
    import check_gamma0_vignette as g0
    import vignette_uncertainty as vu
    pool = vu.load_pool()
    draws, ref, hlo, hce = vu.load_draws()
    ritc = vu.load_ritc(pool[3], pool[4])
    targets = vu.load_targets()
    centres = {m: g0.centres(m, pool, draws, (ref, hlo, hce), ritc, targets)[1] for m in TO.MODES}
    profile = json.load(io.open(os.path.join(HERE, "vignettes", "vignette-1", "target_profile.json"),
                                encoding="utf-8"))
    return {"centres": centres, "target": targets[0], "profile": profile}


class TestTheToolAtItsDefaults:
    def test_the_defaults_are_the_headline_operator_and_a_clean_target(self):
        d = tool_defaults()
        assert d["mode"] == d["mode_selected"] == TO.HEADLINE, d
        assert d["regime"] == "clean", d

    def test_the_default_preset_is_the_vignette_1_target(self, v1_reference):
        data = _embedded_data()
        got = run_tool(REPORT, data, tool_defaults())
        prof = v1_reference["profile"]
        want = [prof["lob_weights_json"].get(name, 0.0) for name in data["lob_names"]]
        assert got["tw"] == pytest.approx(want, abs=1e-12), "the default preset's mix is not Vignette 1's"
        assert (got["tSize"], got["tHhi"]) == pytest.approx(v1_reference["target"], abs=1e-12)
        assert got["tSize"] == prof["reserve_size"]

    def test_the_tool_at_its_defaults_gives_the_size_only_headline(self, v1_reference):
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
         "      html: workedExampleHtml(d, r, DATA.pooling_model)}))};\n"
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
        return data["pooling_model"], run_tool(MODAL, data, tool_defaults())

    def test_the_modal_prints_the_gamma_in_force(self, modal):
        pm, out = modal
        for mode, want in (("size_only", 0.0), ("overlay", pm["gamma"])):
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
        not -- so a modal printing one gamma while computing with another fails here."""
        pm, out = modal
        for mode, other in (("size_only", pm["gamma"]), ("overlay", 0.0)):
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
        src = io.open(os.path.join(SRC, script), encoding="utf-8").read()
        if script == "run_analysis.py" or not re.search(r"^\s*import transfer_operator\b", src, re.M):
            continue
        out += [(script, rel) for rel in rp.OUTPUTS.get(script, ()) if rel.endswith(".json")]
    return out


PRODUCERS = _operator_producers()


def test_the_producer_scan_finds_the_headline_sources():
    names = {s for s, _ in PRODUCERS}
    for s in ("vignette_uncertainty.py", "check_gamma0_vignette.py", "worked_example_donor.py",
              "gpd_var_uncertainty.py", "bayesian_gpd.py", "error_rate_propagation.py", "proxy_stress_bayes.py"):
        assert s in names, s
    assert len(PRODUCERS) >= 18, PRODUCERS


@pytest.mark.parametrize("script,rel", PRODUCERS, ids=[r for _s, r in PRODUCERS])
def test_every_recorded_operator_output_carries_both_stamps(script, rel):
    """DEFERRED-TO-REFIT: each recorded output says which figures are the headline operator's and which the overlay's."""
    rec = _json(rel)
    stamps = list(_stamps(rec))
    for where, s in stamps:
        assert s["operator"] in TO.MODES, "%s%s: operator %r is not a mode" % (rel, where, s["operator"])
        assert s.get("operator_role") == TO.ROLE[s["operator"]], (rel, where, s.get("operator_role"))
    assert any(s["operator"] == TO.HEADLINE for _w, s in stamps), \
        "%s (%s): no block says it is the headline size-only operator's" % (rel, script)
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
