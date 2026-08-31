"""Tests for reproduce.py's report validation and environment/manifest checks.

Every recorded fact in reproduce-run-report.json must be CONSEQUENTIAL: the previous
report recorded a commit, a dirty flag and hashes that --verify never read, so a
clean clone "verified" by comparing its own untouched outputs with its own HEAD.
Each tamper test alters one recorded fact and asserts validation fails.
"""
import copy
import importlib.util
import io
import json
import os
import re
from email.message import Message

import pytest
from packaging.requirements import Requirement

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "reproduce_mod", os.path.join(HERE, "reproduce.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def _report():
    p = os.path.join(HERE, "reproduce-run-report.json")
    if not os.path.exists(p):
        pytest.skip("no committed run report yet")
    rep = json.load(io.open(p, encoding="utf-8"))
    if rep.get("schema", 1) < 3:
        pytest.skip("report predates schema 3 (clean rerun pending)")
    return rep


def test_canonical_hash_ignores_volatile_only():
    a = rp.canonical_json_sha256(b'{"k": 1, "runtime_seconds": 5}')
    b = rp.canonical_json_sha256(b'{"runtime_seconds": 99, "k": 1}')
    c = rp.canonical_json_sha256(b'{"k": 2, "runtime_seconds": 5}')
    assert a == b
    assert a != c


def test_valid_report_passes():
    ok, msgs = rp.validate_report(_report())
    assert ok, msgs


def test_dirty_flag_is_consequential():
    rep = copy.deepcopy(_report())
    rep["worktree_dirty_src"] = True
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("DIRTY" in m for m in msgs)


def test_bogus_commit_is_rejected():
    rep = copy.deepcopy(_report())
    rep["commit"] = "0" * 40
    ok, _ = rp.validate_report(rep)
    assert not ok


def test_tampered_binary_hash_is_rejected():
    rep = copy.deepcopy(_report())
    npz = [r for r in rep["outputs"] if r.endswith(".npz")]
    if not npz:
        pytest.skip("no binary outputs in report")
    rep["outputs"][npz[0]]["sha256"] = "f" * 64
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("bytes differ" in m for m in msgs)


def test_tampered_canonical_hash_is_rejected():
    rep = copy.deepcopy(_report())
    js = [r for r in rep["outputs"] if r.endswith(".json")]
    rep["outputs"][js[0]]["canonical_sha256"] = "f" * 64
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("canonical content differs" in m for m in msgs)


def test_unknown_output_is_rejected():
    rep = copy.deepcopy(_report())
    rep["outputs"]["model/does_not_exist.npz"] = {"sha256": "0" * 64, "bytes": 1}
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("not present at recorded commit" in m for m in msgs)


def test_omitted_expected_output_is_rejected():
    rep = copy.deepcopy(_report())
    rep["outputs"].pop(next(iter(rep["outputs"])))
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("output set disagrees" in m for m in msgs)


def test_missing_script_is_rejected():
    rep = copy.deepcopy(_report())
    rep["scripts"].pop(next(iter(rep["scripts"])))
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("script set disagrees" in m for m in msgs)


def test_failed_script_is_rejected():
    rep = copy.deepcopy(_report())
    rep["scripts"][next(iter(rep["scripts"]))]["status"] = "failed"
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("not recorded successful" in m for m in msgs)


def test_unknown_script_is_rejected():
    rep = copy.deepcopy(_report())
    rep["scripts"]["unknown.py"] = {"status": "ok"}
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("unknown script" in m for m in msgs)


def test_wrong_manifest_size_is_rejected():
    rep = copy.deepcopy(_report())
    rep["manifest_size"] = 9_999
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("manifest_size" in m for m in msgs)


def test_inconsistent_partial_status_is_rejected():
    rep = copy.deepcopy(_report())
    rep["partial"] = False
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("partial" in m for m in msgs)


def test_command_and_environment_are_consequential():
    rep = copy.deepcopy(_report())
    rep["command"] = "reproduce.py --only checks"
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("script set disagrees" in m for m in msgs)

    rep = copy.deepcopy(_report())
    rep["environment"].pop("pymc")
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("material package" in m for m in msgs)


@pytest.mark.parametrize("schema", [1, 2])
def test_old_schema_reports_are_not_trusted(schema):
    ok, msgs = rp.validate_report({"schema": schema, "commit": "abc"})
    assert not ok and any("predates" in m for m in msgs)


def test_manifest_is_complete():
    assert rp.check_manifest_completeness() == []


def test_every_step_has_outputs():
    assert all(sc in rp.OUTPUTS for sc, _, _ in rp.STEPS)


def test_environment_lock_matches_running_env():
    assert rp.check_environment_lock() == []


class _FakeDistribution:
    def __init__(self, direct_url=None, version="1.0", extras=(), requires=()):
        self.direct_url = direct_url
        self.version = version
        self.requires = list(requires)
        self.metadata = Message()
        for extra in extras:
            self.metadata["Provides-Extra"] = extra

    def read_text(self, filename):
        assert filename == "direct_url.json"
        return json.dumps(self.direct_url or {})


def test_direct_archive_reference_and_hash_are_enforced():
    req = Requirement(
        "demo @ https://example.test/demo.whl#sha256=abc123")
    installed = _FakeDistribution({
        "url": "https://example.test/demo.whl",
        "archive_info": {"hashes": {"sha256": "abc123"}},
    })
    assert rp._direct_reference_error(req, installed) is None

    installed.direct_url["archive_info"]["hashes"]["sha256"] = "wrong"
    assert "hash differs" in rp._direct_reference_error(req, installed)


def test_direct_vcs_reference_and_revision_are_enforced():
    req = Requirement(
        "demo @ git+https://example.test/demo.git@0123456789abcdef")
    installed = _FakeDistribution({
        "url": "https://example.test/demo.git",
        "vcs_info": {"vcs": "git", "commit_id": "0123456789abcdef"},
    })
    assert rp._direct_reference_error(req, installed) is None

    installed.direct_url["vcs_info"]["commit_id"] = "fedcba9876543210"
    assert "revision" in rp._direct_reference_error(req, installed)


def test_requested_extras_and_their_dependencies_are_enforced():
    req = Requirement("demo[plot]==1.0")
    installed = _FakeDistribution(
        version="1.0", extras=("plot",),
        requires=('plot-lib>=2; extra == "plot"',))
    dependencies = {"plot-lib": _FakeDistribution(version="2.4")}
    getter = dependencies.__getitem__
    assert rp._extra_errors(req, installed, getter) == []

    dependencies["plot-lib"].version = "1.5"
    errors = rp._extra_errors(req, installed, getter)
    assert errors and "plot-lib>=2" in errors[0]

    missing_extra = _FakeDistribution(version="1.0")
    assert "not provided" in rp._extra_errors(req, missing_extra, getter)[0]


def test_lock_is_project_specific_and_every_entry_is_parseable():
    lock = os.path.join(HERE, "requirements.lock")
    entries = [line.strip() for line in io.open(lock, encoding="utf-8")
               if line.strip() and not line.lstrip().startswith("#")]
    assert len(entries) < 100
    assert all(Requirement(entry) for entry in entries)


# ---------------------------------------------------------------------------
# What --verify PRINTS. A claim about the verifier's output is only true if the
# output says it; validating a `partial` field internally is not the same thing.
# ---------------------------------------------------------------------------

def test_clean_clone_verify_states_partial_coverage(monkeypatch, capsys):
    """The no-local-stamp path: a clean clone must be told the coverage, not just
    handed PASS. This is the exact false green review found."""
    _report()  # skip early if there is no schema-3 report to reason about
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    ok = rp.verify()
    out = capsys.readouterr().out
    assert ok, out
    assert "manifest scripts recorded as run" in out
    assert "of %d manifest scripts" % len(rp.STEPS) in out
    assert "PARTIAL" in out
    assert "not evidence of reproduction" in out
    assert "verify: PASS (PARTIAL run)" in out


def test_clean_clone_verify_names_the_script_counts(monkeypatch, capsys):
    """The numbers must be real, not a fixed sentence: recorded vs manifest."""
    rep = _report()
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    rp.verify()
    out = capsys.readouterr().out
    n = len(rep["scripts"])
    # the "verify: " prefix matters: without it "5 of 55" is a substring of
    # "55 of 55", and a census that printed the manifest size twice passed this
    # test. Mutation testing found that; the assertion is anchored now.
    assert "verify: %d of %d manifest scripts" % (n, len(rp.STEPS)) in out
    assert "other %d script(s)" % (len(rp.STEPS) - n) in out


def test_verify_refuses_when_there_is_no_evidence_at_all(monkeypatch, capsys):
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    monkeypatch.setattr(rp, "REPORT", os.path.join(HERE, "no-such-report.json"))
    assert rp.verify() is False
    assert "nothing to verify" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The test-count record (no count is typed anywhere)
# ---------------------------------------------------------------------------

def test_test_count_record_is_current_and_matches_the_readme():
    assert rp.check_test_counts() == []


def test_a_stale_recorded_count_is_caught(monkeypatch, tmp_path):
    """A record that no longer describes the suite must fail, or it goes stale
    exactly the way the typed number did."""
    rec = json.load(io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8"))
    rec["collected"] = rec["collected"] + 7
    p = tmp_path / "stale.json"
    io.open(str(p), "w", encoding="utf-8").write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    msgs = rp.check_test_counts()
    assert any("rerun" in m for m in msgs), msgs


def test_a_readme_count_disagreeing_with_the_record_is_caught(monkeypatch, tmp_path):
    rec = json.load(io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8"))
    rec["passed"] = rec["passed"] + 1
    p = tmp_path / "wrong.json"
    io.open(str(p), "w", encoding="utf-8").write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    msgs = rp.check_test_counts()
    assert any("README says" in m for m in msgs), msgs


def test_a_failing_recorded_run_is_not_accepted(monkeypatch, tmp_path):
    rec = json.load(io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8"))
    rec["failed"] = 1
    p = tmp_path / "failed.json"
    io.open(str(p), "w", encoding="utf-8").write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    assert any("failing test" in m for m in rp.check_test_counts())


def test_no_test_count_is_typed_outside_the_record():
    """Every stated count in the README must be one the record wrote."""
    rec = json.load(io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8"))
    text = io.open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    stated = re.findall(r"(\d+) passed, (\d+) skipped", text)
    assert stated, "the README no longer states the suite result at all"
    for p, s in stated:
        assert (int(p), int(s)) == (rec["passed"], rec["skipped"])
