r"""A USD record's development basis is decided in the report's own currency (R205).

load_and_classify() converted the canonical model block to GBP before it decided the figure's
basis. pyd_basis() recognises a triangle-routed figure by comparing the recorded figure with the
route's value, and a declaration by comparing it with the amount a model quotes, all stated in
the report's currency; after conversion a USD record matched neither. 28 of 247 USD records took
the wrong basis that way, six of them inside the gross sample.

These run real records through the loader in a temporary directory: two USD records whose
figures come from a gross and a net triangle, and a GBP record as the control.
"""
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402

CASES = {
    "780_2017": ("gross", "triangle-route:gross"),   # USD, figure from a gross triangle
    "1796_2023": ("net", "triangle-route:net"),      # USD, figure from a net triangle
    "457_2016": ("gross", "triangle-route:gross"),   # GBP: no conversion, the control
}


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    d = tmp_path_factory.mktemp("records")
    for key in CASES:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    mp = pytest.MonkeyPatch()
    mp.setattr(ra, "DATA_DIR", d)
    try:
        records, _counters, _log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(CASES)
    return {"%s_%s" % (r.get("syndicate"), r.get("year")): r for r in records}


@pytest.mark.parametrize("key", sorted(CASES))
def test_the_basis_is_decided_in_the_reports_own_currency(parsed, key):
    r = parsed.get(key)
    assert r is not None, "%s did not reach the loader's records" % key
    assert (r.get("pyd_basis"), r.get("pyd_basis_source")) == CASES[key], (key, r.get("pyd_basis"), r.get("pyd_basis_source"))


def test_the_usd_figure_is_still_converted(parsed):
    """The fix moves the basis decision, not the conversion: the USD figure is in GBP."""
    r = parsed["780_2017"]
    assert r.get("fx_applied") is True
    assert abs(r["pyd_gbp_m"]) < 1.6, r["pyd_gbp_m"]
