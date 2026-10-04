"""The opening-reserve floor is stated, and each record below it is labelled for what it is (P-6).

The loader has excluded records whose opening gross claims reserves are at or below GBP 0.1m after the FX conversion
since its first commit, and the paper said "positive opening reserves". The review of 2 October 2026 found two of
the four such records positive: 2357/2016 (USD 17k) and 5183/2024 (USD 100k); 2357/2015 reads nil and 1994/2021
none. The floor is now ANALYSIS_CONFIG's (so the results bundle carries it), the ledger's reason tells the three
cases apart, and the reconciliation table's row names the floor.

Run:  python -m pytest src/test_reserve_floor.py -q
"""
import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402


def test_the_floor_is_the_loaders_stated_constant():
    assert ra.ANALYSIS_CONFIG["opening_reserve_floor_gbp_m"] == 0.1
    loader = io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8").read()
    assert 'if opening is None or opening <= ANALYSIS_CONFIG["opening_reserve_floor_gbp_m"]:' in loader
    assert "opening <= 0.1" not in loader


@pytest.mark.parametrize("opening,words", [
    (None, "no opening reserves were read"),
    (0.0, "nil opening reserves (GBP 0m)"),
    (-0.5, "nil opening reserves (GBP -0.5m)"),
    (0.0115, "opening reserves of GBP 0.0115m, positive but at or below the floor of GBP 0.1m"),
    (0.1, "opening reserves of GBP 0.1000m, positive but at or below the floor of GBP 0.1m"),
])
def test_the_reason_tells_none_nil_and_below_the_floor_apart(opening, words):
    assert ra.no_reserves_reason(opening).startswith(words)


@pytest.fixture(scope="module")
def no_reserves():
    _records, _counters, log, _files = ra.load_and_classify()
    return {e["file"]: e["reason"] for e in log if e["status"] == "NO_RESERVES"}


def test_each_committed_record_below_the_floor_carries_its_true_reason(no_reserves):
    """The review's four, read on their pages: two positive bases below the floor, one nil, one with none read."""
    assert sorted(no_reserves) == ["syndicate_1994_2021.json", "syndicate_2357_2015.json",
                                   "syndicate_2357_2016.json", "syndicate_5183_2024.json"]
    assert no_reserves["syndicate_2357_2016.json"].startswith("opening reserves of GBP 0.01")
    assert no_reserves["syndicate_5183_2024.json"].startswith("opening reserves of GBP 0.07")
    assert "positive but at or below the floor" in no_reserves["syndicate_2357_2016.json"]
    assert no_reserves["syndicate_2357_2015.json"].startswith("nil opening reserves")
    assert no_reserves["syndicate_1994_2021.json"] == "no opening reserves were read"


FLOW = {"files_retrieved": 10, "corpus": 9, "working_sample": 9,
        "files_without_dual_model_record_overlapping_audit_count": 0,
        "pre_corpus": {"excluded": 0, "skipped": 0, "incomplete_no_development_record": 0, "in_runoff": 0,
                       "no_reserves": 1},
        "to_working_sample": {"net_or_unstated_basis": 0, "takeon_not_development": 0, "unusable_severity": 0,
                              "missing_opening_reserves": 0, "missing_lob_weights": 0}}


def table39(monkeypatch, flow=FLOW):
    written = {}
    monkeypatch.setattr(ra, "_write_tex", lambda name, tex: written.update({name: tex}))
    ra._gen_table39({"disposition_flow": flow})
    return written["table39_reconciliation.tex"]


def test_the_reconciliation_row_names_the_floor(monkeypatch):
    tex = table39(monkeypatch)
    assert ("\\quad less: no reserves above \\pounds0.1m (none read, nil, or positive at or below the floor) & $-1$"
            in tex)
    monkeypatch.setitem(ra.ANALYSIS_CONFIG, "opening_reserve_floor_gbp_m", 0.25)
    assert "no reserves above \\pounds0.25m" in table39(monkeypatch)


def test_the_ledger_carries_the_loaders_reason():
    import missingness_check as MC
    got = MC.no_reserves_disposition({"file": "syndicate_2357_2016.json", "reason": ra.no_reserves_reason(0.0115)})
    assert (got[0], got[1]) == ("scientific_exclusion", "no_positive_reserve_base")
    assert got[5] == "no opening-reserve base above the floor: " + ra.no_reserves_reason(0.0115)
    with pytest.raises(AssertionError, match="without the loader's reason"):
        MC.no_reserves_disposition({"file": "syndicate_2357_2016.json"})
