#!/usr/bin/env python3
"""Every model-sample loader selects the same records.

Twenty-eight scripts load the model sample with their own copy of the filter (an outcome s_raw_a, opening
reserves, a Herfindahl index), and several add a condition of their own: a gross basis, a data-quality tag,
line weights, gross written premium. On the committed data they agree, but nothing said so, and a record
that lost its weights or its premium would silently leave some fits and not others (review of 29 September
2026, test upgrade 5).

So the scan below finds every comprehension over <data>["observations"] whose filter reads s_raw_a -- a new
loader is covered without being listed here -- and evaluates each filter, exactly as written, on the
committed exposure results. The vignette donor pool, which the vignette scripts read from the shipped
tool's embedded data rather than from the model file, is held to the same set.

Run:  python -m pytest src/test_loader_variants.py -q
"""
import ast
import io
import json
import os

import pytest

SRC = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SRC)
EXPOSURE = os.path.join(HERE, "model", "exposure_results.json")


def _is_observations(node):
    return (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
            and node.slice.value == "observations")


def _loader_filters():
    """(file, line, loop variable, [conditions]) for every filtered comprehension over observations reading s_raw_a."""
    out = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".py") or fn.startswith("test_"):
            continue
        tree = ast.parse(io.open(os.path.join(SRC, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)):
                for gen in node.generators:
                    conds = [ast.unparse(c) for c in gen.ifs]
                    if _is_observations(gen.iter) and any("s_raw_a" in c for c in conds):
                        out.append((fn, node.lineno, ast.unparse(gen.target), conds))
    return out


LOADERS = _loader_filters()


@pytest.fixture(scope="module")
def observations():
    if not os.path.exists(EXPOSURE):
        pytest.skip("model/exposure_results.json not present in this checkout")
    return json.load(io.open(EXPOSURE, encoding="utf-8"))["observations"]


@pytest.fixture(scope="module")
def sample_keys(observations):
    import adopted_model
    _S, _R, _H, yr, syn, _ritc = adopted_model.load_sample()
    return {"%s_%s" % (s, y) for s, y in zip(syn, yr)}


def test_the_scan_finds_the_loaders():
    files = {fn for fn, *_ in LOADERS}
    for fn in ("adopted_model.py", "calibrate_dispersion_ritc.py", "check_pyd_temporal_correlation.py",
               "proxy_stress_bayes.py", "check_missingness_sensitivity.py"):
        assert fn in files, fn
    assert len(LOADERS) >= 25, len(LOADERS)


def test_the_sample_is_not_trivial(sample_keys, observations):
    assert 0 < len(sample_keys) < len(observations)


@pytest.mark.parametrize("fn,line,target,conds", LOADERS, ids=["%s:%d" % (f, n) for f, n, _t, _c in LOADERS])
def test_every_loader_selects_the_model_sample(fn, line, target, conds, observations, sample_keys):
    try:
        keep = eval("lambda %s: %s" % (target, " and ".join("(%s)" % c for c in conds)),
                    {"__builtins__": {}, "int": int, "float": float, "len": len})
        keys = {"%s_%s" % (o["syndicate"], o["year"]) for o in observations if keep(o)}
    except NameError as e:
        pytest.fail("%s:%d filters on a name outside the record (%s); declare it here or use "
                    "adopted_model.load_sample()" % (fn, line, e))
    assert keys == sample_keys, "%s:%d selects %d records: %d not in the model sample, %d of it missing (%s)" % (
        fn, line, len(keys), len(keys - sample_keys), len(sample_keys - keys),
        sorted(keys ^ sample_keys)[:6])


def test_the_vignette_donor_pool_is_the_model_sample(sample_keys):
    import vignette_uncertainty as vu
    if not os.path.exists(os.path.join(HERE, "distortion_tool.html")):
        pytest.skip("distortion_tool.html not present in this checkout")
    _S, _R, _H, synd, year = vu.load_pool()
    pool = {"%s_%s" % (s, y) for s, y in zip(synd, year)}
    assert len(pool) == len(synd), "the donor pool holds a syndicate-year twice"
    assert pool == sample_keys, (len(pool), len(sample_keys), sorted(pool ^ sample_keys)[:6])
