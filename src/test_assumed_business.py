r"""The assumed-business regime is the RITC scan and the confirmed inward transfers, and nothing else.

PLAN R195 (owner's decision, 13 September 2026): a syndicate-year that accepts another
syndicate's liabilities by a confirmed loss portfolio transfer is treated like one that accepts
a reinsurance to close. `assumed_business.py` is the one place that decides it. These tests
hold the rule down on constructed files, check it on the committed files, and fail if any
script assigns the regime some other way.
"""
import ast
import io
import json
from pathlib import Path

import pytest

import assumed_business as ab

SRC = Path(__file__).resolve().parent


def _files(tmp_path, scan, records, found_by_hand=()):
    s = tmp_path / "ritc_scan.json"
    s.write_text(json.dumps(scan), encoding="utf-8")
    r = tmp_path / "register.json"
    r.write_text(json.dumps({"records": records, "found_by_hand": list(found_by_hand)}),
                 encoding="utf-8")
    return {"ritc_scan": s, "register": r}


class TestTheRule:
    SCAN = {"1_2020": {"ritc_occurred": True, "confidence": "strong"},
            "2_2020": {"ritc_occurred": True, "confidence": "weak"},
            "3_2020": {"ritc_occurred": False},
            "4_2020": {"ritc_occurred": True, "confidence": "weak"}}
    REGISTER = [{"stem": "5_2020", "verdict": "genuine", "direction": "inward"},
                {"stem": "6_2020", "verdict": "genuine", "direction": "both"},
                {"stem": "7_2020", "verdict": "genuine", "direction": "outward"},
                {"stem": "8_2020", "verdict": "not a transfer", "direction": "inward"},
                {"stem": "4_2020", "verdict": "genuine", "direction": "inward"}]

    def test_the_regime_is_ritc_and_confirmed_inward_transfers(self, tmp_path):
        got = ab.keys(**_files(tmp_path, self.SCAN, self.REGISTER))
        assert got == {"1_2020", "2_2020", "4_2020", "5_2020", "6_2020"}

    def test_each_source_is_recorded(self, tmp_path):
        src = ab.sources(**_files(tmp_path, self.SCAN, self.REGISTER))
        assert src["4_2020"] == ["ritc_weak", "transfer_inward"]
        assert src["6_2020"] == ["transfer_both"]
        assert "7_2020" not in src and "8_2020" not in src

    def test_a_confirmed_transfer_counts_as_strong_evidence(self, tmp_path):
        strong, weak = ab.strong_weak(**_files(tmp_path, self.SCAN, self.REGISTER))
        assert strong == {"1_2020", "4_2020", "5_2020", "6_2020"}
        assert weak == {"2_2020"}

    def test_a_transfer_the_scanner_missed_enters_when_confirmed_by_hand(self, tmp_path):
        """3500/2018: two loss portfolio transfers neither scanner flagged, confirmed from the
        filing. How a transfer was found does not decide whether it is one."""
        hand = [{"stem": "9_2018", "verdict": "genuine", "direction": "inward"},
                {"stem": "10_2019", "verdict": "not a transfer", "direction": "inward"}]
        src = ab.sources(**_files(tmp_path, self.SCAN, self.REGISTER, found_by_hand=hand))
        assert src["9_2018"] == ["transfer_inward"]
        assert "10_2019" not in src

    def test_a_missing_register_is_an_error_not_an_empty_set(self, tmp_path):
        f = _files(tmp_path, self.SCAN, self.REGISTER)
        f["register"] = tmp_path / "absent.json"
        with pytest.raises(FileNotFoundError):
            ab.keys(**f)


class TestTheCommittedFiles:

    def test_every_confirmed_inward_transfer_is_in_the_regime_and_nothing_else_enters(self):
        reg = json.load(io.open(str(ab.TRANSFER_REGISTER), encoding="utf-8"))
        scan = json.load(io.open(str(ab.RITC_SCAN), encoding="utf-8"))
        ritc = {k for k, v in scan.items() if isinstance(v, dict) and v.get("ritc_occurred")}
        confirmed = {r["stem"] for r in reg["records"] + reg.get("found_by_hand", [])
                     if r.get("verdict") == "genuine" and r.get("direction") in ("inward", "both")}
        assert confirmed, "the register confirms no transfer, so this test would prove nothing"
        regime = ab.keys()
        assert confirmed <= regime
        assert regime - ritc == confirmed - ritc
        assert confirmed - ritc, "no transfer-only record: the regime change is not exercised"


class TestNoScriptAssignsTheRegimeAnotherWay:

    def test_no_script_reads_the_ritc_flag_itself(self):
        """A script that read `ritc_occurred` itself would fit a different regime from the
        headline, and nothing would say so. Only assumed_business.py may."""
        offenders = []
        for p in sorted(SRC.glob("*.py")):
            if p.name == "assumed_business.py" or p.name.startswith("test_"):
                continue
            tree = ast.parse(io.open(str(p), encoding="utf-8").read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "ritc_occurred"):
                    offenders.append("%s:%d" % (p.name, node.lineno))
                if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                        and node.slice.value == "ritc_occurred"):
                    offenders.append("%s:%d" % (p.name, node.lineno))
        assert not offenders, offenders

    def test_the_check_would_see_a_direct_read(self):
        """Control: the walk above finds the construction it looks for."""
        tree = ast.parse('occ = {k for k, v in r.items() if v.get("ritc_occurred")}')
        hits = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
                and n.args and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "ritc_occurred"]
        assert len(hits) == 1
