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

Run:  python -m pytest src/test_distortion_tool.py -q
"""
import io
import json
import os
import re
import shutil
import subprocess

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "assets", "_distortion_tool_template.html")
GENERATED = os.path.join(HERE, "distortion_tool.html")

NODE = shutil.which("node")
NEEDED = ("_gammaln", "_betacf", "_betai", "studentTcdf", "studentTinv", "donorNu", "targetNu",
          "regimeMapSeverity", "shapley3", "sigmaSys", "sizeLambda", "transferLambda",
          "hhi", "hellinger")


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


def harness(body, data=None):
    """Run `body` under node with the tool's functions and a stub DATA in scope."""
    if NODE is None:
        pytest.skip("node is not available")
    js = _read(TEMPLATE)
    src = "\n\n".join(extract_function(js, n) for n in NEEDED)
    stub = json.dumps(data or {})
    prog = ("const DATA = " + stub + ";\n" + src + "\n" + body + "\n")
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
                v[mask] = float(np.percentile(vals, 99.5, method="linear"))
            sh = shapley3_reference(v)
            assert abs(sum(sh.values()) - (v[7] - v[0])) < 1e-9, regime
            if regime == "preserve":
                assert abs(sh["tail"]) < 1e-12, "the tail factor must vanish here"
