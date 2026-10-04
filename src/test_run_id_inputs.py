r"""The analysis run identifier derives from every input the analysis reads, not the record files alone.

run_analysis.main() names a run by a hash of its source data and of its script. The source data were the
record files, so a run whose registers or regime inputs differed kept the same identifier, although each
changes what the analysis does with the same records: the basis register, the confirmed figures and the
take-ons (read by the loader), and the RITC scan and the confirmed transfer register (read through
assumed_business for the tail regime). Found in the review of PLAN R213's loader registers.

The review of 2 October 2026 (A-5) found the identifier still left out inputs the run reads: the currency scan, the
FX rates, the calibration and the src/ modules the script imports (a 10% change to one FX rate moved 38 openings and
left the identifier unchanged). The currency scan is hashed as raw bytes (pinned -text); the FX rates and the
calibration in reproduce.py's canonical JSON form, without the keys it calls volatile, because scripts rewrite them
on every pass; the modules with line endings normalised, as the script is; and the identifier is derived after the
calibration is loaded.

Run:  python -m pytest src/test_run_id_inputs.py -q
"""
import ast
import io
import json
import os
import sys
import types

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import assumed_business  # noqa: E402
import run_analysis as ra  # noqa: E402

INPUTS = ((ra, "PYD_BASIS_REGISTER"), (ra, "PYD_CONFIRMED_FIGURES"), (ra, "TAKEON_REGISTER"),
          (ra, "OPENING_RESERVES_CONFIRMED"), (ra, "TAKEON_BASE_REGISTER"), (assumed_business, "RITC_SCAN"),
          (assumed_business, "TRANSFER_REGISTER"), (ra, "RUNOFF_REGISTER"), (ra, "RUNOFF_CORPUS_REGISTER"),
          (ra, "FILING_ELIGIBILITY_REGISTER"), (ra, "CURRENCY_SCAN_FILE"))


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    paths = {}
    for module, name in INPUTS:
        p = tmp_path / ("%s.json" % name)
        p.write_text('{"_purpose": "test"}', encoding="utf-8")
        monkeypatch.setattr(module, name, p)
        paths[name] = p
    record = tmp_path / "syndicate_1_2020.json"
    record.write_text("{}", encoding="utf-8")
    return record, paths


def test_the_hashed_inputs_are_the_records_and_every_register_the_analysis_reads(inputs):
    record, paths = inputs
    files = ra.source_files_for_hash([str(record)])
    assert sorted(files) == sorted([str(record)] + [str(p) for p in paths.values()])


def test_editing_any_register_changes_the_source_hash(inputs):
    record, paths = inputs
    before = ra.hash_file_contents(ra.source_files_for_hash([str(record)]))
    for name, p in paths.items():
        p.write_text('{"_purpose": "edited %s"}' % name, encoding="utf-8")
        after = ra.hash_file_contents(ra.source_files_for_hash([str(record)]))
        assert after != before, name
        before = after


def test_the_run_is_named_from_those_inputs_after_the_calibration_is_loaded():
    """A helper nobody calls would pass the tests above and leave the identifier as it was; and an identifier derived
    before the calibration is loaded cannot cover it."""
    src = io.open(ra.__file__, encoding="utf-8").read()
    main = src[src.index("def main():"):]
    call = "source_hash = run_source_hash(file_paths, calibration_file() if COMBINED_MODEL is not None else None)"
    assert call in main
    loaded = main.index("    load_dispersion_calibration()\n")
    assert loaded < main.index(call) < main.index("DETERMINISTIC_RUN_ID = run_id")
    assert "hash_file_contents(file_paths)" not in src
    assert "h = hashlib.sha256(hash_file_contents(source_files_for_hash(file_paths)).encode(\"ascii\"))" in src


@pytest.fixture
def json_inputs(inputs, tmp_path, monkeypatch):
    """The FX rates and a calibration, written as scripts write them."""
    record, _paths = inputs
    fx = tmp_path / "fx_rates_h10.json"
    fx.write_text(json.dumps({"retrieved_utc": "2026-10-01T00:00:00Z", "year_end_rates": {"2024": 1.25}}, indent=2),
                  encoding="utf-8")
    cal = tmp_path / "dispersion_calibration_ritc.json"
    cal.write_text(json.dumps({"k": 0.57, "gamma": 0.2, "runtime_seconds": 31.0}, indent=1), encoding="utf-8")
    monkeypatch.setattr(ra, "FX_RATES_FILE", fx)
    return record, fx, cal


def _rewrite(path, edit):
    obj = json.loads(path.read_text(encoding="utf-8"))
    edit(obj)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def test_editing_the_fx_rates_or_the_calibration_changes_the_source_hash(json_inputs):
    record, fx, cal = json_inputs
    before = ra.run_source_hash([str(record)], cal)
    _rewrite(fx, lambda o: o["year_end_rates"].update({"2024": 1.375}))
    after_fx = ra.run_source_hash([str(record)], cal)
    assert after_fx != before
    _rewrite(cal, lambda o: o.update(k=0.58))
    assert ra.run_source_hash([str(record)], cal) != after_fx
    assert ra.run_source_hash([str(record)], None) != ra.run_source_hash([str(record)], cal)


def test_a_rewritten_retrieval_time_or_line_endings_leave_the_source_hash(json_inputs):
    """The FX fetch rewrites retrieved_utc on every pass, a calibration records its runtime, and a Windows
    checkout writes CRLF: none is a different input."""
    record, fx, cal = json_inputs
    before = ra.run_source_hash([str(record)], cal)
    _rewrite(fx, lambda o: o.update(retrieved_utc="2026-10-04T09:00:00Z"))
    _rewrite(cal, lambda o: o.update(runtime_seconds=99.0))
    for p in (fx, cal):
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert ra.run_source_hash([str(record)], cal) == before


def test_the_imported_modules_are_the_scripts_src_imports():
    tree = ast.parse(io.open(ra.__file__, encoding="utf-8").read())
    src_modules = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(HERE, "src")) if f.endswith(".py")}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names if a.name in src_modules}
        elif isinstance(node, ast.ImportFrom) and node.module in src_modules:
            imported.add(node.module)
    assert imported == {m.__name__ for m in ra.IMPORTED_MODULES}


def test_editing_an_imported_module_changes_the_code_hash_and_its_line_endings_do_not(tmp_path, monkeypatch):
    mod = tmp_path / "helper.py"
    mod.write_bytes(b"X = 1\n")
    monkeypatch.setattr(ra, "IMPORTED_MODULES", ra.IMPORTED_MODULES + (types.SimpleNamespace(__file__=str(mod)),))
    before = ra.hash_script()
    mod.write_bytes(b"X = 1\r\n")
    assert ra.hash_script() == before
    mod.write_bytes(b"X = 2\n")
    assert ra.hash_script() != before
