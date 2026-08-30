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

import pytest

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
    if rep.get("schema", 1) < 2:
        pytest.skip("report predates schema 2 (clean rerun pending)")
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


def test_schema_one_reports_are_not_trusted():
    ok, msgs = rp.validate_report({"schema": 1, "commit": "abc"})
    assert not ok and any("predates" in m for m in msgs)


def test_manifest_is_complete():
    assert rp.check_manifest_completeness() == []


def test_every_step_has_outputs():
    assert all(sc in rp.OUTPUTS for sc, _, _ in rp.STEPS)


def test_environment_lock_matches_running_env():
    assert rp.check_environment_lock() == []
