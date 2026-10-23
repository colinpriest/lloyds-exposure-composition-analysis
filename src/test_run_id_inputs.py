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
calibration is loaded. Since option B (the author's decision of 10 October 2026) the run loads two calibrations, the
gamma = 0 headline and the gamma-free fit the concentration overlay reads: both are hashed, and both are left out
of the calibration-free identifier.

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

INPUTS = ((ra, "PYD_BASIS_REGISTER"), (ra, "PYD_CONFIRMED_FIGURES"), (ra, "MATURE_COHORT_FIGURES"),
          (ra, "FX_UNTRANSLATED_REGISTER"), (ra, "RESTATED_BASE_REGISTER"), (ra, "TAKEON_REGISTER"), (ra, "OPENING_RESERVES_CONFIRMED"), (ra, "TAKEON_BASE_REGISTER"), (assumed_business, "RITC_SCAN"),
          (assumed_business, "TRANSFER_REGISTER"), (ra, "RUNOFF_REGISTER"), (ra, "RUNOFF_CORPUS_REGISTER"),
          (ra, "FILING_ELIGIBILITY_REGISTER"), (ra, "COMPOSITION_PAGE_READINGS"), (ra, "CURRENCY_SCAN_FILE"))


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
    with io.open(ra.__file__, encoding="utf-8") as _fh:
        src = _fh.read()
    main = src[src.index("def main():"):]
    call = "source_hash = run_source_hash(file_paths, loaded_calibration_files())"
    assert call in main
    loaded = main.index("    load_dispersion_calibration()\n")
    assert loaded < main.index(call) < main.index("DETERMINISTIC_RUN_ID = run_id")
    assert "hash_file_contents(file_paths)" not in src
    assert "h = hashlib.sha256(hash_file_contents(source_files_for_hash(file_paths)).encode(\"ascii\"))" in src


def test_the_calibration_free_run_id_is_written_beside_the_run_id():
    """The loader pass and the outputs pass load different calibrations, so their run ids differ; the file that
    names the loader's run between them (error_rate_propagation) records the calibration-free one (the review of
    4 October 2026, finding 1). It must be derived without the calibration and written into the results."""
    with io.open(ra.__file__, encoding="utf-8") as _fh:
        src = _fh.read()
    main = src[src.index("def main():"):]
    assert "run_id_without_calibration = derive_run_id(run_source_hash(file_paths, ()), code_hash)" in main
    assert '"analysis_run_id_without_calibration": run_id_without_calibration,' in main
    assert "run_id = derive_run_id(source_hash, code_hash)" in main


@pytest.fixture
def json_inputs(inputs, tmp_path, monkeypatch):
    """The FX rates and a calibration, written as scripts write them."""
    record, _paths = inputs
    fx = tmp_path / "fx_rates_h10.json"
    fx.write_text(json.dumps({"retrieved_utc": "2026-10-01T00:00:00Z", "year_end_rates": {"2024": 1.25}}, indent=2),
                  encoding="utf-8")
    cal = tmp_path / "dispersion_calibration_ritc.json"
    cal.write_text(json.dumps({"k": 0.57, "gamma": 0.0, "gamma_prior": "fixed_0", "runtime_seconds": 31.0},
                              indent=1), encoding="utf-8")
    monkeypatch.setattr(ra, "FX_RATES_FILE", fx)
    return record, fx, cal


@pytest.fixture
def two_calibrations(json_inputs, tmp_path):
    """The headline calibration and the gamma-free one the overlay reads."""
    record, fx, cal = json_inputs
    cal_gf = tmp_path / "dispersion_calibration_ritc_gamma_free.json"
    cal_gf.write_text(json.dumps({"k": 0.59, "gamma": 0.36, "runtime_seconds": 30.0}, indent=1), encoding="utf-8")
    return record, fx, cal, cal_gf


def test_both_calibrations_are_hashed(two_calibrations):
    """Option B: the run reads the headline and the gamma-free calibration; editing either is a different run, and
    so is loading one without the other."""
    record, _fx, cal, cal_gf = two_calibrations
    both = ra.run_source_hash([str(record)], [cal, cal_gf])
    assert both != ra.run_source_hash([str(record)], [cal]), "the gamma-free calibration is not hashed"
    assert both != ra.run_source_hash([str(record)], [cal_gf]), "the headline calibration is not hashed"
    _rewrite(cal_gf, lambda o: o.update(gamma=0.37))
    after_gf = ra.run_source_hash([str(record)], [cal, cal_gf])
    assert after_gf != both, "editing the gamma-free calibration left the hash"
    _rewrite(cal, lambda o: o.update(k=0.58))
    assert ra.run_source_hash([str(record)], [cal, cal_gf]) != after_gf, "editing the headline left the hash"


def test_both_calibrations_are_left_out_of_the_calibration_free_id(two_calibrations, monkeypatch):
    """The run's own calibration paths point at these files, so a calibration-free hash that reached for either
    file by itself would move with it."""
    record, _fx, cal, cal_gf = two_calibrations
    monkeypatch.setattr(ra, "calibration_file", lambda: cal)
    monkeypatch.setattr(ra, "overlay_calibration_file", lambda: cal_gf)
    code = ra.hash_script()
    without = ra.derive_run_id(ra.run_source_hash([str(record)], ()), code)
    assert ra.run_source_hash([str(record)], ()) == ra.run_source_hash([str(record)], None)
    for path, edit in ((cal, lambda o: o.update(k=0.6)), (cal_gf, lambda o: o.update(gamma=0.5))):
        _rewrite(path, edit)
        assert ra.derive_run_id(ra.run_source_hash([str(record)], ()), code) == without, path.name
    assert ra.derive_run_id(ra.run_source_hash([str(record)], [cal, cal_gf]), code) != without


def test_the_run_hashes_the_calibrations_it_loaded(monkeypatch):
    """loaded_calibration_files names the headline and the gamma-free calibration when both are loaded, the
    headline alone when the overlay is not, and nothing when the operator is disabled (the loader pass on a stale or
    missing headline)."""
    monkeypatch.setattr(ra, "COMBINED_MODEL", {"gamma": 0.0})
    monkeypatch.setattr(ra, "COMBINED_MODEL_OVERLAY", {"gamma": 0.36})
    assert ra.loaded_calibration_files() == [ra.calibration_file(), ra.overlay_calibration_file()]
    assert ra.overlay_calibration_file().name == "dispersion_calibration_ritc_gamma_free.json"
    monkeypatch.setattr(ra, "COMBINED_MODEL_OVERLAY", None)
    assert ra.loaded_calibration_files() == [ra.calibration_file()]
    monkeypatch.setattr(ra, "COMBINED_MODEL", None)
    assert ra.loaded_calibration_files() == []


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


def test_the_calibration_free_run_id_ignores_the_calibration_and_follows_everything_else(json_inputs):
    record, fx, cal = json_inputs
    code = ra.hash_script()

    def ids():
        with_cal = ra.derive_run_id(ra.run_source_hash([str(record)], cal), code)
        without = ra.derive_run_id(ra.run_source_hash([str(record)], None), code)
        return with_cal, without

    with_cal, without = ids()
    assert with_cal != without
    _rewrite(cal, lambda o: o.update(k=0.58))
    new_with, new_without = ids()
    assert new_with != with_cal and new_without == without
    _rewrite(fx, lambda o: o["year_end_rates"].update({"2024": 1.375}))
    changed_fx = ids()[1]
    assert changed_fx != without
    # the code hash is part of the id: the same inputs under other code are another run
    assert ra.derive_run_id(ra.run_source_hash([str(record)], None), "another-code-hash") != changed_fx


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
    with io.open(ra.__file__, encoding="utf-8") as _fh:
        tree = ast.parse(_fh.read())
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
