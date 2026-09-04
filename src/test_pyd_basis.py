"""The development figure's basis is explicit, enforced and machine-readable.

Round 51 of the paper review found working-sample observations dividing a
net-of-reinsurance development figure by gross opening reserves (2999/2015 and
2999/2017 from a net claims triangle, 958/2014 from net year-of-account profit
contributions), while run_analysis.py marked reliability from field availability
alone. Every observation now carries `pyd_basis` and `pyd_basis_source`; only
`gross` enters the working sample. These tests plant the three records, exercise
each face of the rule on synthetic records, and read the committed output.

Run:  python -m pytest src/test_pyd_basis.py -q
"""
import io
import json
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")
import sys  # noqa: E402
sys.path.insert(0, SRC)
import run_analysis as ra  # noqa: E402

PLANTED = ("2999_2015", "2999_2017", "958_2014")


@pytest.fixture(scope="module")
def register():
    return ra.load_pyd_basis_register()


def _block(key):
    d = json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key),
                          encoding="utf-8"))
    models = d["models"]
    cands = [(mk, m.get("prior_year_movement_confidence", 0) or 0)
             for mk, m in models.items() if m.get("prior_year_development_pct") is not None]
    ck = cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]
    return models[ck]


@pytest.mark.parametrize("key", PLANTED)
def test_the_planted_records_are_net(register, key):
    basis, source = ra.pyd_basis(_block(key), key, register)
    assert basis == "net", (key, basis, source)


def test_a_pipeline_override_carries_the_triangle_basis(register):
    gross = {"prior_year_development_gbp_m": 62.437, "_rag_triangle": {"type": "gross"},
             "data_quality_notes": "flagged as NET of reinsurance ... [RAG OVERRIDE: Model said "
                                   "PYD=-1.1, RAG triangle computed 62.437. Using RAG value.]"}
    assert ra.pyd_basis(gross, "x_2016", register) == ("gross", "triangle-override:gross")
    net = dict(gross, _rag_triangle={"type": "net"})
    assert ra.pyd_basis(net, "x_2016", register)[0] == "net"


def test_an_override_that_did_not_take_falls_through(register):
    cm = {"prior_year_development_gbp_m": -1.1, "_rag_triangle": {"type": "gross"},
          "_claims_triangle": {"type": "net"},
          "data_quality_notes": "[RAG OVERRIDE: Model said PYD=-1.1, RAG triangle computed "
                                "62.437. Using RAG value.]"}
    assert ra.pyd_basis(cm, "x_2016", register) == ("net", "net-triangle")


def test_a_net_claims_triangle_is_net_unless_the_register_says_otherwise(register):
    cm = {"prior_year_development_gbp_m": 8.277, "_claims_triangle": {"type": "net"},
          "data_quality_notes": ""}
    assert ra.pyd_basis(cm, "x_2016", register) == ("net", "net-triangle")
    assert ra.pyd_basis(cm, "1110_2016", register)[0] == "gross"


def test_a_plain_record_is_gross_stated(register):
    cm = {"prior_year_development_gbp_m": 5.0, "_claims_triangle": {"type": "gross"},
          "data_quality_notes": "Gross figure from the technical provisions note."}
    assert ra.pyd_basis(cm, "x_2016", register) == ("gross", "prompt-default-gross")


def test_the_register_quotes_its_evidence(register):
    for key, entry in register.items():
        assert entry["basis"] in ("gross", "net", "unknown"), key
        assert entry["source"] and len(entry["evidence"]) >= 20, key
        assert os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)), key


def test_the_committed_output_carries_the_basis_and_admits_only_gross():
    d = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))
    obs = d["observations"]
    assert all("pyd_basis" in o and "pyd_basis_source" in o for o in obs)
    working = [o for o in obs if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
               and o.get("hhi") is not None]
    assert all(o["pyd_basis"] == "gross" for o in working)
    keys = {"%s_%s" % (o["syndicate"], o["year"]) for o in working}
    for key in PLANTED:
        assert key not in keys, key
    excluded = [o for o in obs if o["data_quality_tag"] in ("NET_BASIS", "UNKNOWN_BASIS")]
    assert excluded, "no basis exclusions recorded"
    assert all(o["s_raw_a"] is None for o in excluded)
