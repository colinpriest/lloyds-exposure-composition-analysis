#!/usr/bin/env python3
"""The donor pool (donor_pool.py): one definition for the vignettes, the tools and every producer.

The verification of 26 October 2026 (R1): vignette_uncertainty.py and three other steps read the pool out of
distortion_tool.html, which run_analysis.py rewrites at the END of a pass, so a single pass computed the headline interval on
the previous pass's pool. The pool is built from model/exposure_results.json (the loader step's output) by the function that
also builds the tool's donor fields. Held here:

  * the membership: the donors are the records with a severity, an opening reserve above zero and a concentration, in the
    order of the records; on the real loader's records this is exactly run_analysis._vig_donor_pool, and it is the working
    sample adopted_model.load_sample returns;
  * the fields: the shipped tool's precision (8, 2 and 6 decimals), the tool's field order, the assumed-business flag;
  * the pool the vignette steps use equals the shipped tool's pool, donor for donor and in order, whenever the tool and the
    loader's file are from one pass (the committed pair, and the pair a pass writes);
  * no manifest step reads the tool, so a step cannot again use the pool of the previous pass.

Run:  python -m pytest src/test_donor_pool.py -q
"""
import ast
import io
import json
import os
import re
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "src"))

import adopted_model as am  # noqa: E402
import donor_pool as DP  # noqa: E402
import vignette_uncertainty as VU  # noqa: E402
import worked_example_donor as WED  # noqa: E402

TOOL_FIELDS = ("syndicate", "year", "opening_reserves_gbp_m", "s_raw_a", "hhi", "ritc")


def tool_pool():
    with io.open(os.path.join(HERE, "distortion_tool.html"), encoding="utf-8") as fh:
        html = fh.read()
    m = re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S)
    return json.loads(m.group(1))["donors"]


def test_a_donor_has_a_severity_an_opening_reserve_above_zero_and_a_concentration():
    ok = {"syndicate": 1, "year": 2020, "s_raw_a": 0.1, "opening_reserves_gbp_m": 10.0, "hhi": 0.3}
    assert DP.is_donor(ok)
    assert not DP.is_donor({**ok, "s_raw_a": None})            # a record the loader sets aside has no severity
    assert DP.is_donor({**ok, "s_raw_a": 0.0})                  # a nil severity is a donor
    assert not DP.is_donor({**ok, "opening_reserves_gbp_m": 0.0})
    assert not DP.is_donor({**ok, "opening_reserves_gbp_m": None})
    assert not DP.is_donor({**ok, "hhi": None})
    assert not DP.is_donor({k: v for k, v in ok.items() if k != "hhi"})


def test_the_fields_are_at_the_shipped_tools_precision_in_its_order():
    o = {"syndicate": 1, "year": 2020, "s_raw_a": 0.123456785123, "opening_reserves_gbp_m": 123.4567,
         "hhi": 0.12345678}
    d = DP.donor_fields(o, ritc_keys={"1_2020"})
    assert list(d) == list(TOOL_FIELDS)
    assert d["s_raw_a"] == round(0.123456785123, 8) and d["opening_reserves_gbp_m"] == 123.46 and d["hhi"] == 0.123457
    assert d["ritc"] == 1 and DP.donor_fields(o, ritc_keys=set())["ritc"] == 0
    assert (DP.SEVERITY_DP, DP.RESERVES_DP, DP.HHI_DP) == (8, 2, 6)


def test_the_pool_is_the_donors_among_the_observations_in_their_order():
    obs = [{"syndicate": s, "year": 2020, "s_raw_a": v, "opening_reserves_gbp_m": 5.0, "hhi": 0.2}
           for s, v in ((3, 0.1), (1, None), (2, -0.2), (4, 0.3))]
    assert [d["syndicate"] for d in DP.from_observations(obs)] == [3, 2, 4]


def test_the_real_loaders_donor_membership_is_the_vignette_donor_pool_and_the_working_sample():
    import check_cohort_scope as CS
    import run_analysis as ra
    records, _working = CS.load_sensitivity(lambda: ra.load_and_classify(ra.MATURE_COHORT_OUTCOME))
    vig = [(r["syndicate"], r["year"]) for r in ra._vig_donor_pool(records)]
    mine = [(r["syndicate"], r["year"]) for r in records if DP.is_donor(r)
            and r.get("eligible_for_capital", False)]
    assert vig == mine and len(vig) > 600
    # without the eligibility flag (an observation has none) the same records are donors: nothing else carries a figure
    assert [(r["syndicate"], r["year"]) for r in records if DP.is_donor(r)] == vig


def test_the_pool_from_the_loaders_file_is_the_working_sample():
    keys = [("%s_%s" % (d["syndicate"], d["year"])) for d in DP.from_exposure_results()]
    S, R, H, yr, syn, ritc = am.load_sample()
    assert keys == ["%s_%s" % (s, y) for s, y in zip(syn.tolist(), yr.tolist())]
    assert [d["ritc"] for d in DP.from_exposure_results()] == [int(x) for x in ritc.tolist()]


def test_the_vignette_pool_is_the_donor_pool_and_the_worked_example_reads_the_same():
    S, R, H, synd, year = VU.load_pool()
    pool = DP.from_exposure_results()
    assert S.tolist() == [d["s_raw_a"] for d in pool] and R.tolist() == [d["opening_reserves_gbp_m"] for d in pool]
    assert H.tolist() == [d["hhi"] for d in pool]
    assert synd.tolist() == [d["syndicate"] for d in pool] and year.tolist() == [d["year"] for d in pool]
    assert WED.load_pool() == pool


def test_the_pool_the_steps_use_equals_the_shipped_tools_pool_donor_for_donor_and_in_order():
    """The control R1 asks for: once the tool is rewritten by the pass that wrote the loader's file, the pool the vignette
    steps use is the tool's own. (On the committed pair, from one earlier pass, they agree; after a pass they agree.)"""
    tool = tool_pool()
    mine = DP.from_exposure_results()
    assert [{k: d[k] for k in TOOL_FIELDS} for d in tool] == mine


def _manifest_sources():
    import reproduce
    out = {}
    for sc, _stage, _m in reproduce.STEPS:
        with io.open(os.path.join(HERE, "src", sc), encoding="utf-8") as fh:
            out[sc] = fh.read()
    return out


def test_no_manifest_step_other_than_the_one_that_writes_the_tool_names_or_reads_it():
    names = [sc for sc, src in _manifest_sources().items()
             if re.search(r"distortion_tool\.html|EMBEDDED_DATA", src.replace("_distortion_tool_template.html", ""))]
    assert names == ["run_analysis.py"], names


def test_the_tool_builder_takes_its_donor_fields_from_donor_pool():
    with io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "generate_distortion_tool"][0]
    calls = [getattr(c.func, "attr", None) for c in ast.walk(fn) if isinstance(c, ast.Call)]
    assert "donor_fields" in calls
    # the rounding is not retyped there
    src = ast.unparse(fn)
    assert "round(r['s_raw_a'], 8)" not in src and "round(r['opening_reserves_gbp_m'], 2)" not in src
    import run_analysis as ra
    assert DP in ra.IMPORTED_MODULES


def test_the_distortion_tool_is_not_a_committed_input_of_the_manifest():
    import reproduce
    assert "distortion_tool.html" not in reproduce.INPUTS
    assert "distortion_tool.html" in reproduce.OUTPUTS["run_analysis.py"]
