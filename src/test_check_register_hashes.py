"""src/check_register_hashes.py: the PC check that every source_file a register names hashes to its source_sha256.

The filings are not in this repository, so no test compares the committed registers with them (a test that skipped
without them would be no test); this holds the check's own logic, on synthetic files, and that it covers both registers
and is not in the manifest.

Run:  python -m pytest src/test_check_register_hashes.py -q
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import check_register_hashes as CH  # noqa: E402


def _register(tmp_path, name, source, sha):
    path = tmp_path / name
    path.write_text(json.dumps({"_purpose": "x", "1_2020": {"source_file": source, "source_sha256": sha},
                                "2_2020": {"quote": "an entry without a source is not checked"}}), encoding="utf-8")
    return path


def test_a_matching_file_is_ok_and_a_wrong_hash_or_a_missing_file_is_named(tmp_path):
    (tmp_path / "f").mkdir()
    good = tmp_path / "f" / "a.pdf"
    good.write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    ok = _register(tmp_path, "ok.json", "a.pdf", sha)
    assert CH.check(tmp_path / "f", [ok]) == [("ok.json", "1_2020", "ok", CH.check(tmp_path / "f", [ok])[0][3])]
    bad = _register(tmp_path, "bad.json", "a.pdf", "0" * 64)
    assert CH.check(tmp_path / "f", [bad])[0][2] == "mismatch"
    gone = _register(tmp_path, "gone.json", "b.pdf", sha)
    row = CH.check(tmp_path / "f", [gone])[0]
    assert row[2] == "missing" and "b.pdf" in row[3]


def test_main_exits_nonzero_on_a_mismatch_or_a_missing_file_and_zero_otherwise(tmp_path, monkeypatch, capsys):
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.pdf").write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    good = _register(tmp_path, "good.json", "a.pdf", sha)
    monkeypatch.setattr(CH, "REGISTERS", (good,))
    assert CH.main([str(tmp_path / "f")]) == 0
    assert "1 source files checked" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", (_register(tmp_path, "bad.json", "a.pdf", "1" * 64),))
    assert CH.main([str(tmp_path / "f")]) == 1 and "MISMATCH" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", (_register(tmp_path, "gone.json", "zzz.pdf", sha),))
    assert CH.main([str(tmp_path / "f")]) == 1 and "MISSING" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", ())
    assert CH.main([str(tmp_path / "f")]) == 1, "no entries checked is not a pass"


def test_it_covers_both_registers_and_is_not_in_the_manifest():
    names = {p.name for p in CH.REGISTERS}
    assert names == {"composition_page_readings.json", "eligibility_from_filing.json"}
    counts = {p.name: len(CH.entries(p)) for p in CH.REGISTERS}
    assert counts == {"composition_page_readings.json": 76, "eligibility_from_filing.json": 3}
    import reproduce
    assert "check_register_hashes.py" not in [s for s, _stage, _m in reproduce.STEPS]
