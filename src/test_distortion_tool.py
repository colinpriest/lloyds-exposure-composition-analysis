#!/usr/bin/env python3
"""Tests for the transfer tool's own JavaScript, run under node.

Two defects lived in this file for two months and no test could see them, because
nothing in the suite executed the tool's code: the README promised a target RITC status
the interface never offered, and the two-factor Shapley applied the tail map inside both
counterfactuals while using the untransformed pool as its baseline, so the tail-regime
effect was divided silently between "composition" and "reserve size".

So these tests extract the shipped functions from the TEMPLATE -- not the generated
HTML, which regeneration would overwrite -- run them under node, and compare against an
independent Python reference. They cover:

  * all four source/target regime combinations, against scipy's Student-t;
  * Shapley efficiency, null players, order invariance and the zero-tail case;
  * agreement between the JavaScript decomposition and the Python reference;
  * that the generated tool carries the same code as the template.

Round 36 added the artifact itself to the tested surface, after the committed
distortion_tool.html was found still embedding the formula the generator had stopped
emitting, and the five-bar waterfall was found reading a four-value tooltip array:

  * the committed generated HTML must equal (template + inlined Chart.js + the data
    line), and its EMBEDDED_DATA metadata must equal what the generator source emits;
  * the displayed prose (opening note, About, help bullets) must describe the
    selectable target regime and the three-player decomposition, not the superseded
    clean-target/two-factor tool;
  * one five-entry structure must drive the waterfall's labels, plotted segments and
    tooltips, and the tooltip callback is invoked for every (dataset, bar) index.

Run:  python -m pytest src/test_distortion_tool.py -q
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

import numpy as np
import pytest

import pool_quantile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "assets", "_distortion_tool_template.html")
GENERATED = os.path.join(HERE, "distortion_tool.html")

NODE = shutil.which("node")
NEEDED = ("_gammaln", "_betacf", "_betai", "studentTcdf", "studentTinv", "donorNu", "targetNu",
          "regimeMapSeverity", "shapley3", "activeGamma", "activeModeLabel", "sigmaSys",
          "sizeLambda", "transferLambda", "hhi", "hellinger")


def _read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def extract_function(js, name):
    """The source of a top-level `function name(...) {...}`, by brace matching."""
    m = re.search(r"^function %s\s*\(" % re.escape(name), js, re.M)
    assert m, "function %s not found in the template" % name
    i = js.index("{", m.end() - 1)
    depth, j = 0, i
    while j < len(js):
        if js[j] == "{":
            depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0:
                return js[m.start():j + 1]
        j += 1
    raise AssertionError("unbalanced braces in %s" % name)


def extract_const(js, name):
    """The source of a top-level `const name = {...};`, so a table is not retyped in the test."""
    m = re.search(r"^const %s = \{.*?\n\};" % re.escape(name), js, re.S | re.M)
    assert m, "const %s not found in the template" % name
    return m.group(0)


def harness(body, data=None, extra=(), mode="overlay"):
    """Run `body` under node with the tool's functions and a stub DATA in scope.

    `mode` is the operator mode GAMMA_MODE is set to. It defaults to "overlay", the FITTED gamma,
    because the comparisons in this file are against Python references that use MODEL's gamma --
    not because that is the tool's default, which is the size-only operator and which
    TestOperatorMode pins separately.
    """
    if NODE is None:
        pytest.skip("node is not available")
    js = _read(TEMPLATE)
    src = "\n\n".join([extract_const(js, "GAMMA_MODES")]
                      + [extract_function(js, n) for n in NEEDED + tuple(extra)])
    stub = json.dumps(data or {})
    prog = ("const DATA = " + stub + ";\nlet GAMMA_MODE = " + json.dumps(mode) + ";\n"
            + src + "\n" + body + "\n")
    r = subprocess.run([NODE, "-e", prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


MODEL = {"pooling_model": {"k": 0.606, "gamma": 0.243, "sd_undiv": 0.0207,
                           "sd_div": 0.058, "nu_clean": 2.43, "nu_ritc": 1.55,
                           "reference_size": 500.0, "hhi_floor": 0.01,
                           "hhi_ceil": 1.0}}


# ----------------------------------------------------------------- the operator ------
class TestTargetRegime:
    """Finding 1: nu_t is a choice, and all four combinations must work."""

    def test_the_template_offers_a_target_regime_selector(self):
        html = _read(TEMPLATE)
        assert 'id="targetRegime"' in html
        for value in ('value="clean"', 'value="ritc"', 'value="preserve"'):
            assert value in html, value

    def test_the_de_ritc_only_helper_is_gone(self):
        """The old function hard-coded nu_t = nu_clean; keeping it would leave a second
        path that ignores the selector."""
        assert "function deRitcSeverity" not in _read(TEMPLATE)

    @pytest.mark.parametrize("is_ritc,regime,nu_s,nu_t", [
        (False, "clean", 2.43, 2.43),
        (True, "clean", 1.55, 2.43),
        (False, "ritc", 2.43, 1.55),
        (True, "ritc", 1.55, 1.55),
        (True, "preserve", 1.55, 1.55),
        (False, "preserve", 2.43, 2.43),
    ])
    def test_the_regime_indices_are_selected_correctly(self, is_ritc, regime, nu_s, nu_t):
        out = harness(
            "console.log(JSON.stringify({s: donorNu(%s), t: targetNu('%s', %s)}))"
            % (str(is_ritc).lower(), regime, str(is_ritc).lower()), MODEL)
        assert abs(out["s"] - nu_s) < 1e-9
        assert abs(out["t"] - nu_t) < 1e-9

    @pytest.mark.parametrize("nu_s,nu_t", [(2.43, 2.43), (1.55, 2.43),
                                           (2.43, 1.55), (1.55, 1.55)])
    def test_the_quantile_map_matches_scipy(self, nu_s, nu_t):
        """All four source/target combinations against an independent reference."""
        from scipy import stats
        sigma = 0.08
        xs = [-0.30, -0.05, 0.0, 0.02, 0.11, 0.45]
        got = harness(
            "const out = [%s].map(x => regimeMapSeverity(x, %r, %r, %r));"
            "console.log(JSON.stringify(out))"
            % (", ".join(repr(x) for x in xs), sigma, nu_s, nu_t), MODEL)
        for x, g in zip(xs, got):
            if nu_s == nu_t:
                assert abs(g - x) < 1e-12, (x, g)
                continue
            u = stats.t.cdf(x / sigma, df=nu_s)
            want = stats.t.ppf(min(max(u, 1e-12), 1 - 1e-12), df=nu_t) * sigma
            assert abs(g - want) < 2e-4, (x, g, want)

    @pytest.mark.parametrize("nu_s,nu_t", [(2.43, 2.43), (1.55, 2.43),
                                           (2.43, 1.55), (1.55, 1.55)])
    def test_zero_is_an_exact_fixed_point_of_the_quantile_map(self, nu_s, nu_t):
        """Round 47 T1: the CDF/PPF round trip returned ~-1e-9 for zero, which a
        loose tolerance could not see. Exact equality, all four combinations."""
        out = harness(
            "console.log(JSON.stringify([regimeMapSeverity(0, 0.08, %r, %r), "
            "Object.is(regimeMapSeverity(0, 0.08, %r, %r), 0)]))"
            % (nu_s, nu_t, nu_s, nu_t), MODEL)
        assert out[0] == 0 and out[1] is True, out

    @pytest.mark.parametrize("regime", ["clean", "ritc", "preserve"])
    @pytest.mark.parametrize("is_ritc", [False, True])
    def test_zero_is_a_fixed_point_under_every_selectable_target(self, regime, is_ritc):
        out = harness(
            "const s = donorNu(%s), t = targetNu('%s', %s);"
            "console.log(JSON.stringify(regimeMapSeverity(0, 0.08, s, t)))"
            % (str(is_ritc).lower(), regime, str(is_ritc).lower()), MODEL)
        assert out == 0

    @pytest.mark.parametrize("nu_s,nu_t", [(1.55, 2.43), (2.43, 1.55)])
    def test_the_quantile_map_preserves_sign(self, nu_s, nu_t):
        xs = [-0.45, -0.02, 0.0, 0.02, 0.45]
        got = harness(
            "const out = [%s].map(x => Math.sign(regimeMapSeverity(x, 0.08, %r, %r)));"
            "console.log(JSON.stringify(out))"
            % (", ".join(repr(x) for x in xs), nu_s, nu_t), MODEL)
        assert got == [-1, -1, 0, 1, 1], got

    def test_mapping_to_a_heavier_tail_widens_the_extremes(self):
        """clean -> RITC must push the tail out, the mirror of de-RITC-ing."""
        got = harness(
            "console.log(JSON.stringify([regimeMapSeverity(0.45, 0.08, 2.43, 1.55),"
            " regimeMapSeverity(0.45, 0.08, 1.55, 2.43)]))", MODEL)
        assert got[0] > 0.45, got
        assert got[1] < 0.45, got

    def test_the_generated_tool_carries_the_same_operator(self):
        if not os.path.exists(GENERATED):
            pytest.skip("distortion_tool.html not generated in this checkout")
        gen = _read(GENERATED)
        assert 'id="targetRegime"' in gen, "the generated tool predates the selector"
        assert "function regimeMapSeverity" in gen
        assert "function deRitcSeverity" not in gen


# ----------------------------------------------------------------- the decomposition -
def shapley3_reference(v):
    """Independent Python reference: bit 1 tail, bit 2 size, bit 4 concentration."""
    from itertools import permutations
    factors = [1, 2, 4]
    total = {f: 0.0 for f in factors}
    for order in permutations(factors):
        mask = 0
        for f in order:
            total[f] += v[mask | f] - v[mask]
            mask |= f
    n = 6.0
    return {"tail": total[1] / n, "size": total[2] / n, "conc": total[4] / n}


class TestThreeFactorShapley:
    """Finding 2: tail regime is its own factor, over all eight coalitions."""

    def test_the_two_factor_formula_is_gone(self):
        html = _read(TEMPLATE)
        assert "function shapley3" in html
        assert "statsAdj.var995 - statsSizeOnly.var995" not in html, \
            "the contaminated two-factor formula is still here"

    def _random_v(self, seed):
        rng = np.random.default_rng(seed)
        return {m: float(rng.normal()) for m in range(8)}

    def test_it_agrees_with_the_python_reference(self):
        for seed in (1, 2, 3, 17):
            v = self._random_v(seed)
            got = harness("console.log(JSON.stringify(shapley3(%s)))"
                          % json.dumps({str(k): val for k, val in v.items()}))
            want = shapley3_reference(v)
            for key in ("tail", "size", "conc"):
                assert abs(got[key] - want[key]) < 1e-12, (seed, key, got, want)

    def test_efficiency(self):
        """The three contributions must sum EXACTLY to target minus raw."""
        for seed in (5, 6, 7):
            v = self._random_v(seed)
            got = harness("console.log(JSON.stringify(shapley3(%s)))"
                          % json.dumps({str(k): val for k, val in v.items()}))
            assert abs(sum(got.values()) - (v[7] - v[0])) < 1e-12, (seed, got)

    def test_null_player(self):
        """A factor that changes nothing gets exactly zero."""
        base = {0: 0.0, 2: 0.4, 4: -0.1, 6: 0.25}
        v = dict(base)
        for m, val in base.items():
            v[m | 1] = val                      # the tail factor does nothing
        got = harness("console.log(JSON.stringify(shapley3(%s)))"
                      % json.dumps({str(k): val for k, val in v.items()}))
        assert abs(got["tail"]) < 1e-12, got

    def test_order_invariance(self):
        """Averaging over the six orderings is what the closed form must equal."""
        v = self._random_v(11)
        got = harness("console.log(JSON.stringify(shapley3(%s)))"
                      % json.dumps({str(k): val for k, val in v.items()}))
        want = shapley3_reference(v)
        assert max(abs(got[k] - want[k]) for k in want) < 1e-12

    def test_additivity_over_two_statistics(self):
        v1, v2 = self._random_v(21), self._random_v(22)
        vsum = {m: v1[m] + v2[m] for m in range(8)}
        outs = []
        for v in (v1, v2, vsum):
            outs.append(harness("console.log(JSON.stringify(shapley3(%s)))"
                                % json.dumps({str(k): val for k, val in v.items()})))
        for key in ("tail", "size", "conc"):
            assert abs(outs[0][key] + outs[1][key] - outs[2][key]) < 1e-12, key


class TestEndToEndDecomposition:
    """The pool-level decomposition, on a synthetic donor set, against Python."""

    DONORS = [
        {"syndicate": "A", "year": 2020, "opening_reserves_gbp_m": 120.0,
         "s_raw_a": 0.31, "hhi": 0.30, "weights": [0.5, 0.5], "ritc": True,
         "direction": "strengthening", "pyd_gbp_m": 37.0, "lob_severity": None},
        {"syndicate": "B", "year": 2021, "opening_reserves_gbp_m": 900.0,
         "s_raw_a": -0.05, "hhi": 0.18, "weights": [0.4, 0.6], "ritc": False,
         "direction": "release", "pyd_gbp_m": -45.0, "lob_severity": None},
        {"syndicate": "C", "year": 2019, "opening_reserves_gbp_m": 340.0,
         "s_raw_a": 0.12, "hhi": 0.25, "weights": [0.55, 0.45], "ritc": True,
         "direction": "strengthening", "pyd_gbp_m": 41.0, "lob_severity": None},
        {"syndicate": "D", "year": 2022, "opening_reserves_gbp_m": 610.0,
         "s_raw_a": 0.02, "hhi": 0.21, "weights": [0.45, 0.55], "ritc": False,
         "direction": "strengthening", "pyd_gbp_m": 12.0, "lob_severity": None},
    ]

    def _coalitions(self, regime):
        data = dict(MODEL, donors=self.DONORS, lob_names=["X", "Y"])
        js = _read(TEMPLATE)
        body = (
            "const tw = [0.5, 0.5], tSize = 500;\n"
            + extract_function(js, "computeDistributions")
            + "\nconst out = computeDistributions(tw, tSize, '%s')"
              ".map(d => ({s: d.syndicate, c: d.coalition, nuS: d.nuSrc,"
              " nuT: d.nuTgt, raw: d.sRaw}));"
              "console.log(JSON.stringify(out));" % regime)
        return harness(body, data)

    def test_the_tail_coalition_is_the_identity_under_preserve(self):
        for row in self._coalitions("preserve"):
            assert abs(row["c"]["1"] - row["raw"]) < 1e-12, row["s"]
            assert abs(row["c"]["7"] - row["c"]["6"]) < 1e-9, row["s"]

    def test_a_clean_target_maps_only_the_ritc_donors(self):
        rows = {r["s"]: r for r in self._coalitions("clean")}
        assert abs(rows["B"]["c"]["1"] - rows["B"]["raw"]) < 1e-12
        assert abs(rows["A"]["c"]["1"] - rows["A"]["raw"]) > 1e-6

    def test_an_ritc_target_maps_only_the_clean_donors(self):
        rows = {r["s"]: r for r in self._coalitions("ritc")}
        assert abs(rows["A"]["c"]["1"] - rows["A"]["raw"]) < 1e-12
        assert abs(rows["B"]["c"]["1"] - rows["B"]["raw"]) > 1e-9

    def test_the_pool_decomposition_is_exact_for_every_regime(self):
        """Efficiency at the pool level, which is what the tool displays."""
        for regime in ("clean", "ritc", "preserve"):
            rows = self._coalitions(regime)
            v = {}
            for mask in range(8):
                vals = sorted(r["c"][str(mask)] for r in rows)
                v[mask] = pool_quantile.var_q(vals, 0.995)
            sh = shapley3_reference(v)
            assert abs(sum(sh.values()) - (v[7] - v[0])) < 1e-9, regime
            if regime == "preserve":
                assert abs(sh["tail"]) < 1e-12, "the tail factor must vanish here"


class TestPoolQuantile:
    """The tool reads a VaR by the analysis's rule, the inverse CDF of the pool (frozen review of
    21 September 2026, M04); it interpolated between order statistics (type 7) before."""

    def test_the_tool_and_the_analysis_read_the_same_quantile(self):
        rng = np.random.default_rng(5)
        pools = [[float(v) for v in np.round(rng.standard_t(4, n), 2)] for n in (1, 2, 7, 60, 691)]
        levels = (1, 75, 99, 99.5)
        body = ("const pools = %s; const ps = %s;"
                "console.log(JSON.stringify(pools.map(a => ps.map(p => percentile(a, p)))));"
                % (json.dumps(pools), json.dumps(list(levels))))
        got = harness(body, extra=("percentile",))
        for a, row in zip(pools, got):
            for p, v in zip(levels, row):
                assert v == pool_quantile.var_q(a, p / 100.0), (len(a), p, v)


# ------------------------------------------------------- the waterfall (round 36) ----
class TestWaterfall:
    """Round 36, T2: the five-bar waterfall kept a four-value tooltip array, so the
    tail bar showed the concentration value and the target bar showed `undefined`.
    One structure must drive labels, plotted segments and tooltip values, and a test
    must invoke the tooltip path for every bar."""

    # raw + tail + size + conc = adj, so the stub also satisfies efficiency
    STUB = {"statsRaw": {"var995": 0.86}, "tailEffect995": -0.12,
            "sizeEffect995": -0.23, "mixEffect995": -0.05,
            "statsAdj": {"var995": 0.46}}

    EXTRA = ("fmt", "fmtPct", "waterfallBars", "waterfallTooltip")

    def _bars(self):
        return harness("const r = %s;\nconsole.log(JSON.stringify(waterfallBars(r)))"
                       % json.dumps(self.STUB), MODEL, extra=self.EXTRA)

    def test_one_structure_with_five_named_bars(self):
        bars = self._bars()
        assert [b["label"] for b in bars] == [
            "Raw VaR99.5", "Tail-regime effect", "Reserve-size effect",
            "Concentration effect", "Target-basis VaR99.5"]

    def test_the_tooltip_shows_each_bars_own_quantity(self):
        """Invoke the shipped tooltip callback for every (dataset, bar) index."""
        body = (
            "const r = %s;\nconst bars = waterfallBars(r);\n"
            "const out = [];\n"
            "for (const ds of [0, 1]) for (let i = 0; i < bars.length; i++)"
            " out.push(waterfallTooltip(bars, {datasetIndex: ds, dataIndex: i}));\n"
            "console.log(JSON.stringify(out));" % json.dumps(self.STUB))
        got = harness(body, MODEL, extra=self.EXTRA)
        assert got[:5] == ["", "", "", "", ""], "the base dataset must stay silent"
        assert got[5:] == ["86.00%", "-12.00%", "-23.00%", "-5.00%", "46.00%"], got[5:]

    def test_the_bars_stack_to_the_target(self):
        bars = self._bars()
        effects = [b["tooltip"] for b in bars if b["kind"] == "effect"]
        assert len(effects) == 3
        assert abs(bars[0]["tooltip"] + sum(effects) - bars[-1]["tooltip"]) < 1e-12
        running = bars[0]["tooltip"]
        for b in bars[1:-1]:
            lo, hi = sorted((running, running + b["tooltip"]))
            assert abs(b["base"] - lo) < 1e-12 and abs(b["value"] - (hi - lo)) < 1e-12
            running += b["tooltip"]

    def test_the_renderer_consumes_the_structure(self):
        """Labels, plotted values and tooltips must all come from waterfallBars, with
        no second parallel array left to drift."""
        js = _read(TEMPLATE)
        render = extract_function(js, "renderWaterfall")
        assert "waterfallBars(" in render
        assert "waterfallTooltip(" in render
        assert "bars.map(b => b.label)" in render
        assert "bars.map(b => b.base)" in render
        assert "bars.map(b => b.value)" in render
        assert "const vals" not in render, "a parallel tooltip array is back"

    def test_the_generated_tool_carries_the_same_waterfall(self):
        if not os.path.exists(GENERATED):
            pytest.skip("distortion_tool.html not generated in this checkout")
        js, gen = _read(TEMPLATE), _read(GENERATED)
        for name in ("waterfallBars", "waterfallTooltip", "renderWaterfall"):
            assert extract_function(js, name) == extract_function(gen, name), name


# ------------------------------------- the shipped artifact vs its sources (round 36)
def _generator_meta():
    """The formula/decomposition strings generate_distortion_tool embeds, read from
    the generator's SOURCE, so an edited generator with a stale committed artifact is
    a failure rather than a surprise."""
    import ast
    src = _read(os.path.join(HERE, "src", "run_analysis.py"))
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "generate_distortion_tool")
    out = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value in ("formula", "decomposition")
                        and isinstance(v, ast.Constant)):
                    out[k.value] = v.value
    assert set(out) == {"formula", "decomposition"}, out.keys()
    return out


def _embedded_data():
    gen = _read(GENERATED)
    m = re.search(r"^\s*const EMBEDDED_DATA = (\{.*\});\s*$", gen, re.M)
    assert m, "no EMBEDDED_DATA line in the generated tool"
    return json.loads(m.group(1))


class TestShippedArtifactMatchesItsSources:
    """Round 36, T1 root cause: the committed distortion_tool.html embedded the
    formula `nu_t=nu_clean (de-RITC)` that the generator had already stopped
    emitting -- the generator was edited without the shipped artifact being
    regenerated, and nothing read the artifact back. These tests reverse the
    construction, so ANY drift between template, generator and committed file fails."""

    CHART_MARKER = "<script>/* Chart.js v4.5.1 — inlined for offline use */</script>"

    def test_the_committed_tool_is_the_template_plus_the_data_line(self):
        if not os.path.exists(GENERATED):
            pytest.skip("distortion_tool.html not generated in this checkout")
        gen, tpl = _read(GENERATED), _read(TEMPLATE)
        chart = _read(os.path.join(HERE, "assets", "chart.umd.min.js"))
        inlined = self.CHART_MARKER.replace("</script>", "\n%s\n</script>" % chart)
        assert inlined in gen, "Chart.js is not inlined the way the generator inlines it"
        gen = gen.replace(inlined, self.CHART_MARKER)
        lines = gen.split("\n")
        hits = [i for i, ln in enumerate(lines)
                if ln.strip().startswith("const EMBEDDED_DATA = {")]
        assert len(hits) == 1, "expected exactly one embedded-data line"
        indent = lines[hits[0]][:len(lines[hits[0]]) - len(lines[hits[0]].lstrip())]
        lines[hits[0]] = indent + "// __EMBEDDED_DATA_PLACEHOLDER__"
        assert "\n".join(lines) == tpl, (
            "the committed distortion_tool.html is not the current template plus "
            "data: regenerate it (python src/run_analysis.py)")

    def test_the_embedded_metadata_is_what_the_generator_now_emits(self):
        if not os.path.exists(GENERATED):
            pytest.skip("distortion_tool.html not generated in this checkout")
        meta = _generator_meta()
        pm = _embedded_data()["pooling_model"]
        assert pm.get("formula") == meta["formula"]
        assert pm.get("decomposition") == meta["decomposition"]

    def test_the_embedded_formula_describes_the_selector_not_a_fixed_target(self):
        if not os.path.exists(GENERATED):
            pytest.skip("distortion_tool.html not generated in this checkout")
        pm = _embedded_data()["pooling_model"]
        assert "user-selected target regime" in pm["formula"]
        assert "nu_t=nu_clean" not in pm["formula"]
        assert "three-factor" in pm["decomposition"]
        assert "eight coalitions" in pm["decomposition"]

    def test_the_generator_docstring_describes_the_current_tool(self):
        import ast
        src = _read(os.path.join(HERE, "src", "run_analysis.py"))
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "generate_distortion_tool")
        doc = ast.get_docstring(fn) or ""
        assert "user-selected target regime" in doc
        assert "three players" in doc
        assert "the tool de-RITCs" not in doc, "the docstring still describes the old tool"


# ----------------------------------------------- the displayed prose (round 36, T1) --
def _prose_paths():
    paths = [("template", TEMPLATE)]
    if os.path.exists(GENERATED):
        paths.append(("generated", GENERATED))
    return paths


class TestDisplayedProse:
    """The selector worked but the tool still DESCRIBED the superseded clean-target,
    two-factor version in its note and help. The prose a reader sees is part of the
    shipped artifact; test the specific display sections, not word presence."""

    @pytest.mark.parametrize("which,path", _prose_paths())
    def test_the_help_describes_three_players_over_eight_coalitions(self, which, path):
        html = _read(path)
        a = html.index("<h4>Interpreting the tabs</h4>")
        b = html.index("<h4>Donor eligibility</h4>")
        help_txt = html[a:b]
        for needed in ("Three-player Shapley", "tail-regime", "concentration",
                       "eight coalitions", "sum exactly"):
            assert needed in help_txt, (which, needed)
        for stale in ("two intermediate counterfactuals",
                      "composition and reserve-size components",
                      "composition-transferred"):
            assert stale not in help_txt, (which, stale)
        assert "coalitions (tail regime only" in help_txt, \
            "the Statistics bullet no longer matches the five displayed rows"

    @pytest.mark.parametrize("which,path", _prose_paths())
    def test_the_opening_note_owns_the_tail_regime_step(self, which, path):
        html = _read(path)
        a = html.index('<div class="disclaimer">')
        b = html.index("</div>", a)
        note = html[a:b]
        assert "tail-regime quantile map" in note, which
        assert "not a tail-fitting or capital-setting method" in note, which
        assert "not a tail model or capital-setting" not in note, \
            "the unqualified 'not a tail model' claim is back"

    @pytest.mark.parametrize("which,path", _prose_paths())
    def test_the_about_section_describes_the_selectable_target(self, which, path):
        html = _read(path)
        a = html.index("<h4>What the tool does</h4>")
        b = html.index("<h4>What the tool does not do</h4>")
        about = html[a:b]
        assert "<em>selected</em> target regime" in about, which
        assert "RITC-affected" in about, which
        assert "preserves each donor" in about, which
        assert "clean-composition tail" not in about, \
            "the About text still says every donor is mapped to the clean tail"

    @pytest.mark.parametrize("which,path", _prose_paths())
    def test_every_de_ritc_mention_is_tied_to_the_selector(self, which, path):
        """de-RITC survives only as the NAME of the clean-target special case; any
        bare use would again describe a fixed-target tool."""
        html = _read(path)
        for m in re.finditer(r"de-RITC", html, re.I):
            window = html[max(0, m.start() - 300):m.end() + 300]
            assert ("default" in window or "selected" in window
                    or "selector" in window), (which, window[:120])


class TestReadmeDescribesTheTool:
    """The README is a shipped description too: it must promise the interface the
    tool has (round 35's finding) and the decomposition the tool computes (round
    36's), with the tail-model disclaimer qualified rather than absolute."""

    def _readme(self):
        return _read(os.path.join(HERE, "README.md"))

    def test_the_promise_matches_the_selector(self):
        md = self._readme()
        assert "target tail regime" in md
        assert "RITC-affected" in md
        assert "preserve" in md

    def test_the_decomposition_is_described_as_three_player(self):
        md = self._readme()
        assert md.count("three-player Shapley") >= 2, \
            "both tool descriptions must name the three-player decomposition"
        for phrase in ("tail regime", "concentration"):
            assert phrase in md

    def test_the_tail_model_disclaimer_is_qualified(self):
        md = self._readme()
        assert "not a tail model" not in md, \
            "the tool applies a fitted tail-regime transform; say 'tail-fitting'"
        assert "not a tail-fitting or capital-setting" in md


class TestGeneratedOperatorDescriptions:
    """Round 39, finding 3: after the target-regime selector shipped, two GENERATED
    artifacts kept describing clean-target de-RITC as the operator itself -- the
    data audit and the combined-model table. Their generators are the fix surface.
    These tests read the generator sources AND the generated artifacts, requiring
    all three target cases to be described and every de-RITC mention conditioned
    on the target choice -- not merely a permitted phrase somewhere."""

    SOURCES = ("src/generate_data_audit.py", "src/run_analysis.py")
    GENERATED = ("docs/appendix-data-audit.md",
                 "paper_pack/table20_combined_model.tex")

    @pytest.mark.parametrize("rel", SOURCES + GENERATED)
    def test_all_three_target_cases_are_described(self, rel):
        path = os.path.join(HERE, *rel.split("/"))
        if not os.path.exists(path):
            pytest.skip("%s not present in this checkout" % rel)
        s = _read(path)
        assert re.search(r"clean target[^.]{0,80}de-RITCs", s, re.I | re.S), \
            (rel, "the clean-target case is not described")
        assert re.search(r"RITC-affected target[^.]{0,120}(heavier|clean donors)",
                         s, re.I | re.S), (rel, "the RITC-target case is missing")
        assert re.search(r"preserv\w+[^.]{0,120}identity", s, re.I | re.S), \
            (rel, "the preserve-regime case is missing")

    @pytest.mark.parametrize("rel", GENERATED)
    def test_every_de_ritc_mention_is_conditioned_on_the_target(self, rel):
        path = os.path.join(HERE, *rel.split("/"))
        if not os.path.exists(path):
            pytest.skip("%s not present in this checkout" % rel)
        s = _read(path)
        assert "de-RITC" in s, (rel, "expected the operator description here")
        for m in re.finditer(r"de-RITC", s, re.I):
            win = s[max(0, m.start() - 350):m.end() + 350]
            assert re.search(r"clean target|selected|target regime|identity|"
                             r"nu_s\s*=\s*nu_t|\\nu_s\s*=\s*\\nu_t", win, re.I), \
                (rel, win[:140])
# --------------------------------------------------------------- the operator mode ------
#: the pool-level functions the end-to-end mode tests need on top of NEEDED
EXTRA_POOL = ("computeDistributions", "percentile")


def _big_harness(body, data, mode, extra=()):
    """harness() for a program too long for a command line: 685 donors of embedded data.

    Windows caps a command line well below the size of the real donor pool, so the program goes to a
    temporary file. Everything else matches harness(), including taking the tool's own functions and
    its own GAMMA_MODES table out of the template rather than restating either here.
    """
    if NODE is None:
        pytest.skip("node is not available")
    js = _read(TEMPLATE)
    src = "\n\n".join([extract_const(js, "GAMMA_MODES")]
                      + [extract_function(js, n) for n in NEEDED + tuple(extra)])
    prog = ("const DATA = " + json.dumps(data) + ";\nlet GAMMA_MODE = " + json.dumps(mode) + ";\n"
            + src + "\n" + body + "\n")
    fd, path = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    try:
        io.open(path, "w", encoding="utf-8").write(prog)
        r = subprocess.run([NODE, path], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[-2000:]
        return json.loads(r.stdout)
    finally:
        os.unlink(path)


def _weights_with_hhi(n, target):
    """Weights over n lines with Herfindahl index `target`: one line at w, the rest equal."""
    lo, hi = 1.0 / n, 1.0
    for _ in range(200):
        w = 0.5 * (lo + hi)
        if w ** 2 + (1 - w) ** 2 / (n - 1) < target:
            lo = w
        else:
            hi = w
    w = 0.5 * (lo + hi)
    return [w] + [(1 - w) / (n - 1)] * (n - 1)


def _recorded_gamma0():
    """The analysis's own gamma=0 vignette record, which the tool's default must reproduce."""
    path = os.path.join(HERE, "results", "check_gamma0_vignette_results.json")
    if not os.path.exists(path):
        pytest.skip("check_gamma0_vignette_results.json not present in this checkout")
    return json.load(io.open(path, encoding="utf-8"))


def _v1_target():
    path = os.path.join(HERE, "results", "vignette1_diagnostics_results.json")
    if not os.path.exists(path):
        pytest.skip("vignette1_diagnostics_results.json not present in this checkout")
    v1 = json.load(io.open(path, encoding="utf-8"))["V1_target"]
    return float(v1[0]), float(v1[1])


class TestOperatorMode:
    """T01: the paper's default operator is gamma = 0, and the tool must be able to apply it.

    The frozen review of 25 September 2026 found the tool could not: sigmaSys always used the fitted
    gamma, and the tool's "size only" coalition -- each donor's own H held, fitted gamma retained --
    is a different operator that gives a different number. So these tests check that the default is
    reachable, that it is the default, that it is applied on both sides of the transfer, and that it
    is not confused with that coalition.
    """

    def test_the_template_offers_an_operator_mode_selector(self):
        html = _read(TEMPLATE)
        assert 'id="gammaMode"' in html, "no operator-mode selector in the template"
        assert 'value="size_only" selected' in html, \
            "the size-only operator must be the SELECTED option: it is the paper's default"
        assert 'value="overlay"' in html, "the fitted overlay must remain available"

    def test_the_default_mode_is_the_size_only_operator(self):
        """The module-level default, not only the markup: a reader who never touches the selector,
        and any code path that computes before compute() reads it, must get gamma = 0."""
        js = _read(TEMPLATE)
        m = re.search(r"^let GAMMA_MODE = '([a-z_]+)';", js, re.M)
        assert m, "GAMMA_MODE is not declared at the top level of the template"
        assert m.group(1) == "size_only", m.group(1)

    @pytest.mark.parametrize("mode,expected", [("size_only", 0.0), ("overlay", MODEL["pooling_model"]["gamma"])])
    def test_active_gamma_follows_the_mode(self, mode, expected):
        out = harness("console.log(JSON.stringify({g: activeGamma()}))", MODEL, mode=mode)
        assert out["g"] == pytest.approx(expected, abs=1e-12)

    def test_the_default_scale_does_not_depend_on_concentration(self):
        """What makes it the size-only operator: sigma is a function of R alone."""
        out = harness(
            "console.log(JSON.stringify({a: sigmaSys(500, 0.05), b: sigmaSys(500, 0.5),"
            " c: sigmaSys(2000, 0.05), d: sigmaSys(2000, 0.5)}))", MODEL, mode="size_only")
        assert out["a"] == out["b"], "sigma moved with H at gamma = 0"
        assert out["c"] == out["d"], "sigma moved with H at gamma = 0"
        assert out["a"] != out["c"], "sigma must still move with size"

    def test_the_overlay_scale_does_depend_on_concentration(self):
        out = harness("console.log(JSON.stringify({a: sigmaSys(500, 0.05), b: sigmaSys(500, 0.5)}))",
                      MODEL, mode="overlay")
        assert out["a"] != out["b"], "the overlay must carry the concentration term"

    def test_both_transfer_multipliers_are_one_at_the_default_when_only_H_differs(self):
        """gamma = 0 throughout: the concentration channel of the transfer is exactly null, so a
        pure change of concentration moves nothing."""
        out = harness(
            "console.log(JSON.stringify({conc: transferLambda(500, 0.4, 500, 0.1),"
            " size: sizeLambda(500, 500, 0.1)}))", MODEL, mode="size_only")
        assert out["conc"] == 1.0
        assert out["size"] == 1.0

    def test_the_tool_reproduces_the_analysis_own_two_operators(self):
        """The check that matters: the shipped JavaScript, on the shipped donor pool, at the
        recorded Vignette 1 target, must give the analysis's own recorded VaRs under both modes.

        The reference values are read from results/check_gamma0_vignette_results.json -- computed in
        Python by a separate implementation -- so this is agreement between two implementations and
        not a constant restated in a test.
        """
        data = _embedded_data()
        rec = _recorded_gamma0()
        size, hhi_target = _v1_target()
        weights = _weights_with_hhi(len(data["donors"][0]["weights"]), hhi_target)
        body = ("const donors = computeDistributions(%s, %s, 'clean');\n"
                "const p7 = donors.map(d => d.coalition[7]);\n"
                "const p3 = donors.map(d => d.coalition[3]);\n"
                "console.log(JSON.stringify({v995: percentile(p7, 99.5), v99: percentile(p7, 99.0),"
                " coalition995: percentile(p3, 99.5), gamma: activeGamma()}));"
                % (json.dumps(weights), size))
        got = {m: _big_harness(body, data, m, extra=EXTRA_POOL) for m in ("overlay", "size_only")}
        assert got["overlay"]["v995"] == pytest.approx(
            rec["full_operator"]["centre"]["V1_v995"], abs=5e-7)
        assert got["overlay"]["v99"] == pytest.approx(
            rec["full_operator"]["centre"]["V1_v99"], abs=5e-7)
        assert got["size_only"]["v995"] == pytest.approx(
            rec["size_only_gamma0"]["centre"]["V1_v995"], abs=5e-7), \
            "the tool's size-only mode does not reproduce the paper's gamma=0 sensitivity"
        assert got["size_only"]["v99"] == pytest.approx(
            rec["size_only_gamma0"]["centre"]["V1_v99"], abs=5e-7)

    def test_the_size_only_coalition_is_not_the_size_only_operator(self):
        """The confusion T01 is about, pinned so that relabelling the coalition cannot pass for a fix.

        Under the overlay the coalition holds each donor's own H and keeps the fitted gamma, so it is
        a third number, different from both modes' target bases. Under the default it coincides with
        the target basis, because there is no concentration channel left to hold.
        """
        data = _embedded_data()
        rec = _recorded_gamma0()
        size, hhi_target = _v1_target()
        weights = _weights_with_hhi(len(data["donors"][0]["weights"]), hhi_target)
        body = ("const donors = computeDistributions(%s, %s, 'clean');\n"
                "console.log(JSON.stringify({basis: percentile(donors.map(d => d.coalition[7]), 99.5),"
                " coalition: percentile(donors.map(d => d.coalition[3]), 99.5)}));"
                % (json.dumps(weights), size))
        overlay = _big_harness(body, data, "overlay", extra=EXTRA_POOL)
        default = _big_harness(body, data, "size_only", extra=EXTRA_POOL)
        assert overlay["coalition"] != pytest.approx(
            rec["size_only_gamma0"]["centre"]["V1_v995"], abs=1e-4), \
            "the overlay's size-only coalition must not be mistaken for the gamma=0 operator"
        assert overlay["coalition"] != pytest.approx(overlay["basis"], abs=1e-9)
        assert default["coalition"] == pytest.approx(default["basis"], abs=1e-12), \
            "at gamma = 0 the coalition and the target basis are the same operator"

    def test_the_results_record_which_operator_produced_them(self):
        """A number without its mode is not reproducible, so the provenance panel carries it."""
        html = _read(TEMPLATE)
        assert "gammaMode: GAMMA_MODE" in html and "gammaInForce: activeGamma()" in html, \
            "RESULT must carry the mode it was computed under"
        assert "'Operator mode'" in html or '"Operator mode"' in html, \
            "the provenance grid must display the operator mode"
        assert "activeModeLabel()" in html, "the displayed mode must come from the mode table"

    def test_the_about_text_states_the_default_and_warns_about_the_coalition(self):
        html = _read(TEMPLATE)
        flat = " ".join(html.split())
        assert re.search(r"size-only.{0,80}default", flat, re.I), \
            "the About text must say which operator is the default"
        assert re.search(r"optional overlay", flat, re.I), "the overlay must be described as optional"
        assert re.search(r"coalition.{0,240}not</em>.{0,40}&gamma;.{0,24}0 operator", flat, re.I), \
            "the About text must warn that the size-only coalition is not the gamma=0 operator"
