"""The operator-properties check's donor pool is the calibration sample (the review of 2 October 2026, A-11).

check_operator_properties.load_vignette_pool's docstring said the calibration sample carried one syndicate-year the
donor pool did not (2015/2014); at the reviewed commit the two were the same 674 keys. This holds them equal, so the
docstring's statement is checked, and a future difference fails here before a docstring has to explain it.

Run:  python -m pytest src/test_operator_pool.py -q
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import adopted_model as am  # noqa: E402


def _keys_from_records(path):
    with open(path, encoding="utf-8") as fh:
        obs = json.load(fh)["observations"]
    return {"%s_%s" % (o["syndicate"], o["year"]) for o in obs
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}


def _pool_keys(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    m = re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S)
    return {"%s_%s" % (d["syndicate"], d["year"]) for d in json.loads(m.group(1))["donors"]}


def test_the_calibration_sample_is_the_tools_donor_pool():
    calibration = _keys_from_records(am.RESULTS)
    pool = _pool_keys(os.path.join(HERE, "distortion_tool.html"))
    assert len(pool) > 600
    assert calibration == pool, (sorted(calibration - pool)[:5], sorted(pool - calibration)[:5])


def test_the_sample_filter_here_is_load_samples():
    """The key set above is computed with load_sample's own filter; its size is load_sample's."""
    S = am.load_sample()[0]
    assert len(S) == len(_keys_from_records(am.RESULTS))
