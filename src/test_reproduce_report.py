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
    with io.open(p, encoding="utf-8") as _fh:
        rep = json.load(_fh)
    if rep.get("schema", 1) < 4:
        pytest.skip("report predates schema 4, the whole-tree input attestation "
                    "(recorded pass pending)")
    if rep.get("worktree_dirty_src") is not False:
        # validate_report rejects it outright, so the relationship checks below
        # cannot be exercised on it; reproduce.py --check reports the same state.
        pytest.skip("the committed run report is from a dirty source tree "
                    "(clean rerun pending)")
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
    # whichever the record holds, the opposite disagrees with its script set
    rep = copy.deepcopy(_report())
    rep["partial"] = not rep["partial"]
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("partial" in m for m in msgs)


def _partial_variant(rep, tmp_path, monkeypatch):
    """A stage-only record derived from the committed one. Since round 51 the
    committed report covers the whole manifest, so the partial-coverage path of
    --verify is exercised on this variant: its command names the first stage, its
    scripts and outputs are that stage's, its flag says partial, and every hash is
    the committed one, so validate_report accepts it."""
    var = copy.deepcopy(rep)
    stage = rp.STEPS[0][1]
    scripts = [s for s, st, _ in rp.STEPS if st == stage]
    var["command"] = "reproduce.py --only " + stage
    var["scripts"] = {s: rep["scripts"][s] for s in scripts}
    keep = {rel for s in scripts for rel in rp.OUTPUTS.get(s, ())}
    var["outputs"] = {rel: v for rel, v in rep["outputs"].items() if rel in keep}
    var["partial"] = True
    path = tmp_path / "partial-report.json"
    path.write_text(json.dumps(var), encoding="utf-8")
    monkeypatch.setattr(rp, "REPORT", str(path))
    ok, msgs = rp.validate_report(var)
    assert ok, msgs
    return var


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


def test_evidence_archives_match_their_manifests():
    """An evidence archive is exempt from needing a producer only file by file: each
    file its MANIFEST.json lists must be tracked and hold the bytes it hashes."""
    assert rp.EVIDENCE_ARCHIVES, "no evidence archive declared"
    assert rp.check_evidence_archives() == []


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
    with io.open(lock, encoding="utf-8") as _fh:
        entries = [line.strip() for line in _fh
                   if line.strip() and not line.lstrip().startswith("#")]
    assert len(entries) < 100
    assert all(Requirement(entry) for entry in entries)


# ---------------------------------------------------------------------------
# What --verify PRINTS. A claim about the verifier's output is only true if the
# output says it; validating a `partial` field internally is not the same thing.
# ---------------------------------------------------------------------------

def test_clean_clone_verify_states_partial_coverage(monkeypatch, capsys, tmp_path):
    """The no-local-stamp path: a clean clone must be told the coverage, not just
    handed PASS. This is the exact false green review found. The committed record
    is complete since round 51, so the partial wording is checked on a stage-only
    variant of it."""
    rep = _report()
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    _partial_variant(rep, tmp_path, monkeypatch)
    ok = rp.verify()
    out = capsys.readouterr().out
    assert ok, out
    assert "manifest scripts recorded as run" in out
    assert "of %d manifest scripts" % len(rp.STEPS) in out
    assert "PARTIAL" in out
    assert "not evidence of reproduction" in out
    assert "verify: PASS (PARTIAL run)" in out


def test_clean_clone_verify_states_complete_coverage_of_the_record(monkeypatch, capsys):
    """On the committed record itself the census must match the record's coverage:
    a complete record is announced as such and never marked partial, a partial
    one is marked partial."""
    rep = _report()
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    ok = rp.verify()
    out = capsys.readouterr().out
    assert ok, out
    n = len(rep["scripts"])
    assert "verify: %d of %d manifest scripts" % (n, len(rp.STEPS)) in out
    if rep["partial"]:
        assert "verify: PASS (PARTIAL run)" in out
    else:
        assert n == len(rp.STEPS)
        assert "PARTIAL" not in out
        assert "not evidence of reproduction" not in out
        assert "verify: PASS\n" in out


def test_clean_clone_verify_names_the_script_counts(monkeypatch, capsys, tmp_path):
    """The numbers must be real, not a fixed sentence: recorded vs manifest. Run on
    the stage-only variant, where the two counts differ."""
    rep = _partial_variant(_report(), tmp_path, monkeypatch)
    monkeypatch.setattr(rp, "STAMP", os.path.join(HERE, "no-such-stamp.json"))
    rp.verify()
    out = capsys.readouterr().out
    n = len(rep["scripts"])
    assert 0 < n < len(rp.STEPS)
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
    with io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8") as _fh:
        rec = json.load(_fh)
    rec["collected"] = rec["collected"] + 7
    p = tmp_path / "stale.json"
    with io.open(str(p), "w", encoding="utf-8") as _fh:
        _fh.write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    msgs = rp.check_test_counts()
    assert any("rerun" in m for m in msgs), msgs


def test_a_readme_count_disagreeing_with_the_record_is_caught(monkeypatch, tmp_path):
    with io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8") as _fh:
        rec = json.load(_fh)
    rec["passed"] = rec["passed"] + 1
    p = tmp_path / "wrong.json"
    with io.open(str(p), "w", encoding="utf-8") as _fh:
        _fh.write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    msgs = rp.check_test_counts()
    assert any("README says" in m for m in msgs), msgs


def test_a_failing_recorded_run_is_not_accepted(monkeypatch, tmp_path):
    with io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8") as _fh:
        rec = json.load(_fh)
    rec["failed"] = 1
    p = tmp_path / "failed.json"
    with io.open(str(p), "w", encoding="utf-8") as _fh:
        _fh.write(json.dumps(rec))
    # an absolute path: os.path.join(HERE, abs) returns the absolute one, and
    # pytest's tmp_path is on another drive on Windows
    monkeypatch.setattr(rp, "TESTS_RECORD", str(p))
    assert any("failing test" in m for m in rp.check_test_counts())


def test_no_test_count_is_typed_outside_the_record():
    """Every stated count in the README must be one the record wrote."""
    with io.open(os.path.join(HERE, "tests-run-report.json"),
                            encoding="utf-8") as _fh:
        rec = json.load(_fh)
    with io.open(os.path.join(HERE, "README.md"), encoding="utf-8") as _fh:
        text = _fh.read()
    stated = re.findall(r"(\d+) passed, (\d+) skipped", text)
    assert stated, "the README no longer states the suite result at all"
    for p, s in stated:
        assert (int(p), int(s)) == (rec["passed"], rec["skipped"])


# --- T01 (frozen review, 21 September 2026): the whole tree's inputs are attested -------------
def _repo(tmp_path):
    """A disposable git repository: a source file, an extraction record, a declared output."""
    import subprocess
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "pdf_extraction").mkdir()
    (root / "results").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pdf_extraction" / "rec.json").write_text('{"pyd": 1}\n', encoding="utf-8")
    (root / "results" / "out.json").write_text('{"v": 1}\n', encoding="utf-8")

    def git(*args):
        subprocess.run(["git", "-C", str(root)] + list(args), check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    git("config", "core.autocrlf", "false")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return root, git, ["results/out.json"]


def test_a_changed_input_outside_src_makes_the_tree_dirty(tmp_path):
    """The review's probe: an input changed outside src left worktree_dirty_src False."""
    root, _git, outs = _repo(tmp_path)
    assert rp.capture_inputs(str(root), outs)["clean_before"] is True
    (root / "pdf_extraction" / "rec.json").write_text('{"pyd": 2}\n', encoding="utf-8")
    state = rp.capture_inputs(str(root), outs)
    assert state["clean_before"] is False
    assert "pdf_extraction/rec.json" in state["dirty_before"]


def test_an_untracked_new_input_makes_the_tree_dirty(tmp_path):
    root, _git, outs = _repo(tmp_path)
    (root / "pdf_extraction" / "new.json").write_text("{}\n", encoding="utf-8")
    assert rp.capture_inputs(str(root), outs)["clean_before"] is False


def test_an_input_changed_during_the_run_is_caught(tmp_path):
    root, _git, outs = _repo(tmp_path)
    before = rp.capture_inputs(str(root), outs)
    (root / "pdf_extraction" / "rec.json").write_text('{"pyd": 2}\n', encoding="utf-8")
    after = rp.check_inputs_after(before, str(root))
    assert after["unchanged_after"] is False
    assert any("pdf_extraction/rec.json" in p for p in after["changed_after"])


def test_a_commit_made_during_the_run_is_caught(tmp_path):
    root, git, outs = _repo(tmp_path)
    before = rp.capture_inputs(str(root), outs)
    (root / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    git("commit", "-q", "-am", "mid-run")
    after = rp.check_inputs_after(before, str(root))
    assert after["unchanged_after"] is False
    assert any("HEAD moved" in p for p in after["changed_after"])


def test_a_declared_output_may_change(tmp_path):
    root, _git, outs = _repo(tmp_path)
    before = rp.capture_inputs(str(root), outs)
    (root / "results" / "out.json").write_text('{"v": 2}\n', encoding="utf-8")
    assert rp.check_inputs_after(before, str(root))["unchanged_after"] is True


def test_the_digest_moves_with_an_input_and_not_with_an_output(tmp_path):
    root, git, outs = _repo(tmp_path)
    d0 = rp.capture_inputs(str(root), outs)["inputs_sha256"]
    (root / "results" / "out.json").write_text('{"v": 2}\n', encoding="utf-8")
    git("commit", "-q", "-am", "an output")
    assert rp.capture_inputs(str(root), outs)["inputs_sha256"] == d0
    (root / "pdf_extraction" / "rec.json").write_text('{"pyd": 2}\n', encoding="utf-8")
    git("commit", "-q", "-am", "an input")
    assert rp.capture_inputs(str(root), outs)["inputs_sha256"] != d0


def test_the_manifest_writes_are_declared():
    """R221: every tracked file under the vignette folders and the paper pack is a declared output. Undeclared, the
    whole-tree attestation read them as inputs, and a recorded pass on a clean tree found 23 of them changed within its
    first minutes (their workbooks record when they were written)."""
    import subprocess
    declared = set(rp.declared_outputs())
    out = subprocess.run(["git", "-C", HERE, "ls-files", "vignettes/vignette-1/", "vignettes/vignette-2/",
                          "paper_pack/"], capture_output=True, text=True, check=True).stdout.split("\n")
    tracked = [p for p in out if p]
    assert tracked, "no tracked vignette or paper-pack file: the test has nothing to hold"
    missing = sorted(p for p in tracked if p not in declared)
    assert not missing, "tracked files the manifest writes but no step declares: %s" % missing[:20]


def _workbook(core, sheet, when):
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in (("[Content_Types].xml", b"<Types/>"), ("docProps/core.xml", core),
                           ("xl/worksheets/sheet1.xml", sheet)):
            info = zipfile.ZipInfo(name, date_time=when)
            z.writestr(info, body)
    return buf.getvalue()


def test_a_workbooks_write_time_is_not_its_content():
    a = _workbook(b"<created>2026-09-22T04:11:28Z</created>", b"<v>0.278</v>", (2026, 9, 22, 14, 11, 28))
    b = _workbook(b"<created>2026-09-22T04:50:41Z</created>", b"<v>0.278</v>", (2026, 9, 22, 14, 50, 40))
    c = _workbook(b"<created>2026-09-22T04:50:41Z</created>", b"<v>0.279</v>", (2026, 9, 22, 14, 50, 40))
    assert a != b
    assert rp.output_bytes_for_hash("v/x.xlsx", a) == rp.output_bytes_for_hash("v/x.xlsx", b)
    assert rp.output_bytes_for_hash("v/x.xlsx", b) != rp.output_bytes_for_hash("v/x.xlsx", c)


def test_the_vignette_metadata_run_record_is_volatile():
    base = {"run_id": "r", "random_seed": 42, "git_commit_or_hash": "f65f14e",
            "execution_timestamp_utc": "2026-09-22T04:11:29Z"}
    moved = dict(base, git_commit_or_hash="5c9a35b", execution_timestamp_utc="2026-09-22T04:50:43Z")
    other = dict(moved, random_seed=43)
    h = lambda d: rp.canonical_json_sha256(json.dumps(d).encode("utf-8"))
    assert h(base) == h(moved)
    assert h(moved) != h(other)


def test_a_report_older_than_the_attestation_is_rejected():
    ok, msgs = rp.validate_report({"schema": 3, "worktree_dirty_src": False})
    assert not ok and "predates the whole-tree input attestation" in msgs[0]


def test_a_report_without_the_attestation_is_rejected():
    ok, msgs = rp.validate_report({"schema": 4, "worktree_dirty_src": False})
    assert not ok and "no input attestation" in msgs[0]


def test_a_report_from_an_unclean_start_is_rejected():
    rep = {"schema": 4, "worktree_dirty_src": False,
           "inputs": {"clean_before": False, "dirty_before": ["pdf_extraction/x.json"],
                      "unchanged_after": True}}
    ok, msgs = rp.validate_report(rep)
    assert not ok and "not clean when the recorded run began" in msgs[0]


def test_a_report_with_a_mid_run_change_is_rejected():
    rep = {"schema": 4, "worktree_dirty_src": False,
           "inputs": {"clean_before": True, "unchanged_after": False,
                      "changed_after": ["input differs from HEAD after the run: data/x.csv"]}}
    ok, msgs = rp.validate_report(rep)
    assert not ok and "changed during the recorded run" in msgs[0]


def test_a_forged_inputs_digest_is_rejected():
    """The digest is recomputed from the recorded commit, not taken on trust."""
    head = rp._git(HERE, "rev-parse", "HEAD").stdout.strip()
    rep = {"schema": 4, "worktree_dirty_src": False, "commit": head,
           "inputs": {"clean_before": True, "unchanged_after": True, "head_before": head,
                      "inputs_sha256": "0" * 64, "n_inputs": 1,
                      "outputs_excluded": rp.declared_outputs()}}
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("inputs digest" in m for m in msgs)


@pytest.mark.parametrize("mutation", ["add_source", "remove_output", "duplicate_output"])
def test_report_rejects_altered_exclusions_even_with_recomputed_digest(mutation):
    """A self-consistent digest must not let the report choose its own inputs."""
    rep = copy.deepcopy(_report())
    excluded = rep["inputs"]["outputs_excluded"]
    if mutation == "add_source":
        assert "src/run_analysis.py" not in excluded
        excluded.append("src/run_analysis.py")
        excluded.sort()
    elif mutation == "remove_output":
        excluded.pop(0)
    else:
        excluded.insert(0, excluded[0])
    rep["inputs"]["inputs_sha256"], rep["inputs"]["n_inputs"] = rp.inputs_digest(
        HERE, rep["commit"], excluded)
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("excluded outputs differ" in m for m in msgs)


@pytest.mark.parametrize("command", ["", " ", "\t\n"])
def test_report_rejects_empty_command(command):
    rep = copy.deepcopy(_report())
    rep["command"] = command
    ok, msgs = rp.validate_report(rep)
    assert not ok and any("command must identify" in m for m in msgs)


def test_historical_and_current_manifest_output_sets_are_read_from_git():
    rep = _report()
    historical = rp.recorded_declared_outputs(HERE, rep["commit"])
    assert historical == rep["inputs"]["outputs_excluded"]
    head = rp._git(HERE, "rev-parse", "HEAD").stdout.strip()
    assert rp.recorded_declared_outputs(HERE, head) == rp.declared_outputs()


def test_partial_report_uses_recorded_manifest_not_current_unrun_outputs(tmp_path, monkeypatch):
    rep = _partial_variant(_report(), tmp_path, monkeypatch)
    outputs = dict(rp.OUTPUTS)
    outputs["later-unrun.py"] = ("results/later-output.json",)
    monkeypatch.setattr(rp, "OUTPUTS", outputs)
    assert "results/later-output.json" not in rep["inputs"]["outputs_excluded"]
    ok, msgs = rp.validate_report(rep)
    assert ok, msgs


@pytest.mark.parametrize("source", [
    'OUTPUTS = __import__("pathlib").Path(SENTINEL).touch()\nALWAYS_WRITTEN = ()\n',
    'OUTPUTS = {"x": ("x.json",)}\nOUTPUTS = get_outputs()\nALWAYS_WRITTEN = ()\n',
    'OUTPUTS = {"x": ("x.json",)}\nif True:\n OUTPUTS = {}\nALWAYS_WRITTEN = ()\n',
    'OUTPUTS = {"x": ("x.json",)}\nOUTPUTS.clear()\nALWAYS_WRITTEN = ()\n',
    'OUTPUTS = {"x": ("x.json",)}\nREF = OUTPUTS\nREF.clear()\nALWAYS_WRITTEN = ()\n',
])
def test_recorded_manifest_parser_fails_closed_without_executing(source, tmp_path, monkeypatch):
    from types import SimpleNamespace
    sentinel = tmp_path / "must-not-exist"
    monkeypatch.setattr(rp, "_git", lambda *args: SimpleNamespace(
        returncode=0, stdout='SENTINEL = %r\n' % str(sentinel) + source))
    with pytest.raises(ValueError):
        rp.recorded_declared_outputs(str(tmp_path), "a" * 40)
    assert not sentinel.exists()


def test_partial_verifier_detects_changed_unrun_vignette_and_untracked_output(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rp, "read_stamp", lambda: {"ran": ["dummy.py"], "failed": [], "manifest_size": 2})
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1), ("other.py", "b", 1)])
    monkeypatch.setattr(rp, "REPORT", str(tmp_path / "no-report.json"))
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",),
                                        "other.py": ("vignettes/vignette-1/summary_snippet.md",)})
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert rp.verify()
    for changed in ("vignettes/vignette-1/summary_snippet.md", "results/new-output.json"):
        monkeypatch.setattr(rp, "changed_paths", lambda root, path=changed: [path])
        assert not rp.verify()
        assert changed in capsys.readouterr().out


@pytest.mark.parametrize("partial", [False, True], ids=["full", "partial"])
def test_local_run_report_is_validated_without_being_misclassified_as_a_script_output(
        monkeypatch, tmp_path, capsys, partial):
    """A run writes its own report; that must not hide invalid reports or other outputs."""
    report = tmp_path / "reproduce-run-report.json"
    report.write_text('{"marker": 42}\n', encoding="utf-8")
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "read_stamp", lambda: {
        "ran": ["dummy.py"], "failed": [], "manifest_size": 2 if partial else 1})
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1), ("other.py", "b", 1)] if partial
                        else [("dummy.py", "a", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",),
                                        "other.py": ("vignettes/vignette-1/summary_snippet.md",)})
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    seen = []
    monkeypatch.setattr(rp, "validate_report", lambda record: (seen.append(record) or True, []))
    monkeypatch.setattr(rp, "changed_paths", lambda root: ["reproduce-run-report.json"])
    assert rp.verify()
    assert seen == [{"marker": 42}]

    # Other changed or untracked generated outputs must continue to fail.
    monkeypatch.setattr(rp, "changed_paths", lambda root: ["reproduce-run-report.json",
                                                           "results/new-output.json"])
    assert not rp.verify()
    assert "results/new-output.json" in capsys.readouterr().out

    # A valid-looking but historically invalid report remains a failed check.
    monkeypatch.setattr(rp, "changed_paths", lambda root: ["reproduce-run-report.json"])
    monkeypatch.setattr(rp, "validate_report", lambda record: (False, ["bad attestation"]))
    assert not rp.verify()
    assert "bad attestation" in capsys.readouterr().out

    # An unreadable or deleted changed report must not disappear from the check.
    report.write_text("not json", encoding="utf-8")
    assert not rp.verify()
    assert "reproduce-run-report.json" in capsys.readouterr().out
    report.unlink()
    assert not rp.verify()
    assert "reproduce-run-report.json" in capsys.readouterr().out


@pytest.mark.parametrize("with_stamp", [False, True], ids=["committed", "local"])
@pytest.mark.parametrize("contents", [
    "{}", "[]", "null", "false", "0", '""', "[1]", '"text"',
    '{"schema": "not-an-integer"}', "not json", "NaN", "Infinity", "-Infinity",
    '{"schema": 4, "unexpected": NaN}', "[" * 1200 + "0" + "]" * 1200,
])
def test_verify_rejects_invalid_or_unreadable_present_reports_even_if_not_marked_changed(
        monkeypatch, tmp_path, with_stamp, contents):
    """A parseable falsey value must never bypass report validation."""
    report = tmp_path / "report.json"
    report.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "read_stamp", lambda: {
        "ran": ["dummy.py"], "failed": [], "manifest_size": 1} if with_stamp else None)
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",)})
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert not rp.verify()

    # A directory cannot be read as a report, including when a local stamp exists.
    monkeypatch.setattr(rp, "REPORT", str(tmp_path))
    assert not rp.verify()


@pytest.mark.parametrize("with_stamp", [False, True], ids=["committed", "local"])
@pytest.mark.parametrize("field,value", [
    ("inputs", None), ("inputs", "not-an-object"),
    ("inputs", {"clean_before": True, "unchanged_after": True, "outputs_excluded": 7}),
    ("scripts", None), ("scripts", ["dummy.py"]),
    ("outputs", None), ("outputs", ["results/known.json"]),
    ("commit", None), ("commit", []), ("commit", 42),
])
def test_verify_rejects_malformed_nested_report_fields_without_raising(
        monkeypatch, tmp_path, with_stamp, field, value, capsys):
    """Broken nested objects and commit types must not become errors or a PASS."""
    commit = "1234567890abcdef1234567890abcdef12345678"
    environment = {name: "installed" for name in rp.REQUIRED}
    environment["python"] = rp.SUPPORTED_PYTHON
    report = {
        "schema": 4, "worktree_dirty_src": False, "commit": commit,
        "inputs": {"clean_before": True, "unchanged_after": True,
                   "head_before": commit, "outputs_excluded": [],
                   "inputs_sha256": "digest", "n_inputs": 0},
        "manifest_size": 1, "command": "reproduce.py",
        "scripts": {"dummy.py": {"status": "ok"}}, "outputs": {}, "partial": False,
        "environment": environment, "python": rp.SUPPORTED_PYTHON,
        "platform": "test", "finished_utc": "2026-10-31T00:00:00Z",
        "volatile_json_fields_excluded_by_verify": list(rp.VOLATILE),
    }
    report[field] = value
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(rp, "REPORT", str(path))
    monkeypatch.setattr(rp, "read_stamp", lambda: {
        "ran": ["dummy.py"], "failed": [], "manifest_size": 1} if with_stamp else None)
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "test", "dummy")])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ()})
    monkeypatch.setattr(rp, "inputs_digest", lambda *args: ("digest", 0))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert not rp.verify()
    assert "FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("with_stamp", [False, True], ids=["committed", "local"])
def test_verify_still_accepts_valid_report_after_validation(monkeypatch, tmp_path, with_stamp):
    report = tmp_path / "report.json"
    content = {"scripts": {"dummy.py": {"status": "ok"}}}
    report.write_text(json.dumps(content), encoding="utf-8")
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "read_stamp", lambda: {
        "ran": ["dummy.py"], "failed": [], "manifest_size": 1} if with_stamp else None)
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",)})
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: ["reproduce-run-report.json"])
    seen = []
    monkeypatch.setattr(rp, "validate_report", lambda value: (seen.append(value) or True, []))
    assert rp.verify()
    assert seen == [content]


def test_verify_missing_report_distinguishes_local_stamp_from_deleted_output(monkeypatch, tmp_path):
    """Legacy local stamps can verify without a report, but a deleted tracked report cannot."""
    monkeypatch.setattr(rp, "REPORT", str(tmp_path / "missing.json"))
    monkeypatch.setattr(rp, "read_stamp", lambda: {"ran": ["dummy.py"], "failed": [], "manifest_size": 1})
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",)})
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert rp.verify()
    monkeypatch.setattr(rp, "changed_paths", lambda root: ["reproduce-run-report.json"])
    assert not rp.verify()
    monkeypatch.setattr(rp, "read_stamp", lambda: None)
    assert not rp.verify()


@pytest.mark.parametrize("stamp", [
    {"ran": ["dummy.py"], "failed": ["other.py"], "manifest_size": 2},
    {"ran": ["dummy.py"], "failed": None, "manifest_size": 2},
    {"ran": ["dummy.py"], "manifest_size": 2},
    {"ran": [], "failed": [], "manifest_size": 2},
    {"ran": "dummy.py", "failed": [], "manifest_size": 2},
    {"ran": [None], "failed": [], "manifest_size": 2},
    {"ran": ["dummy.py", "dummy.py"], "failed": [], "manifest_size": 2},
    {"ran": ["unknown.py", "other-unknown.py"], "failed": [], "manifest_size": 2},
    {"ran": ["dummy.py"], "failed": [], "manifest_size": 1},
    {"ran": ["dummy.py"], "failed": [], "manifest_size": True},
    {"ran": ["dummy.py"], "failed": []},
])
def test_local_stamp_rejects_failed_or_impossible_coverage(stamp, monkeypatch, tmp_path, capsys):
    """Failed runs and fabricated coverage cannot turn a valid old report into a PASS."""
    p = tmp_path / ".reproduce-run.json"
    p.write_text(json.dumps(stamp), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text('{"previous": "valid"}', encoding="utf-8")
    monkeypatch.setattr(rp, "STAMP", str(p))
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1), ("other.py", "b", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",), "other.py": ()})
    monkeypatch.setattr(rp, "validate_report", lambda report: (True, []))
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert not rp.verify()
    assert "invalid local run stamp" in capsys.readouterr().out


@pytest.mark.parametrize("contents", ["", "[]", "null", "false", '"text"', "NaN", "{not-json"])
def test_present_unreadable_stamp_does_not_fall_back_to_previous_report(
        contents, monkeypatch, tmp_path, capsys):
    stamp = tmp_path / ".reproduce-run.json"
    stamp.write_text(contents, encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text('{"previous": "valid"}', encoding="utf-8")
    monkeypatch.setattr(rp, "STAMP", str(stamp))
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "validate_report", lambda report: (True, []))
    assert not rp.verify()
    assert "invalid local run stamp" in capsys.readouterr().out


def test_dangling_stamp_link_is_unreadable_not_absent(monkeypatch, tmp_path):
    stamp = tmp_path / ".reproduce-run.json"
    monkeypatch.setattr(rp, "STAMP", str(stamp))
    assert rp.read_stamp() is None
    # Some Windows accounts cannot create symlinks; simulate the directory
    # entry while using a genuinely missing file for the open failure.
    monkeypatch.setattr(rp.os.path, "lexists", lambda path: path == str(stamp))
    assert "_read_error" in rp.read_stamp()


def test_valid_partial_local_stamp_can_coexist_with_older_full_report(monkeypatch, tmp_path, capsys):
    stamp = tmp_path / ".reproduce-run.json"
    stamp.write_text(json.dumps({"ran": ["dummy.py"], "failed": [], "manifest_size": 2}),
                     encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text('{"scripts": {"dummy.py": {}, "other.py": {}}}', encoding="utf-8")
    monkeypatch.setattr(rp, "STAMP", str(stamp))
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1), ("other.py", "b", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/known.json",), "other.py": ()})
    monkeypatch.setattr(rp, "validate_report", lambda report: (True, []))
    monkeypatch.setattr(rp, "output_matches", lambda rel: ("byte-identical", ""))
    monkeypatch.setattr(rp, "changed_paths", lambda root: [])
    assert rp.verify()
    assert "PASS (PARTIAL run)" in capsys.readouterr().out


@pytest.mark.parametrize("ran", [["dummy.py"], ["other.py", "dummy.py"]])
def test_local_stamp_rejects_incomplete_stage_or_reordered_full_run(ran, monkeypatch):
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "same-stage", 1),
                                     ("other.py", "same-stage", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ("results/a.json",),
                                        "other.py": ("results/b.json",)})
    problems = rp.validate_stamp({"ran": ran, "failed": [], "manifest_size": 2})
    assert any("full run or one complete stage" in item for item in problems)


def test_local_stamp_rejects_script_without_declared_outputs(monkeypatch):
    monkeypatch.setattr(rp, "STEPS", [("dummy.py", "a", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"dummy.py": ()})
    assert any("without declared outputs" in x for x in rp.validate_stamp(
        {"ran": ["dummy.py"], "failed": [], "manifest_size": 1}))


def test_current_manifest_accepts_full_and_each_stage_local_stamp():
    """Actual full and partial invocations remain valid after the integrity checks."""
    full = [script for script, _, _ in rp.STEPS]
    stages = {stage for _, stage, _ in rp.STEPS}
    runs = [full] + [[script for script, group, _ in rp.STEPS if group == stage]
                     for stage in stages]
    for ran in runs:
        assert rp.validate_stamp({"ran": ran, "failed": [], "manifest_size": len(full)}) == []


def test_review_evidence_requires_its_exact_tracked_content_and_does_not_exempt_the_directory(tmp_path, monkeypatch):
    import hashlib
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    folder = tmp_path / "results" / "review_evidence"
    folder.mkdir(parents=True)
    allowed = folder / "verified.json"
    allowed.write_bytes(b'{"record": 1}\r\n')
    subprocess.run(["git", "-C", str(tmp_path), "add", "results/review_evidence/verified.json"], check=True)
    rel = "results/review_evidence/verified.json"
    digest = hashlib.sha256(b'{"record": 1}\n').hexdigest()
    monkeypatch.setattr(rp, "HERE", str(tmp_path))
    monkeypatch.setattr(rp, "REVIEW_EVIDENCE_SHA256", {rel: digest})
    assert rp.check_review_evidence_contract() == []
    allowed.write_bytes(b'{"record": 2}\n')
    assert any("differs from its recorded hash" in e for e in rp.check_review_evidence_contract())
    allowed.write_bytes(b'{"record": 1}\n')
    extra = folder / "unlisted.json"
    extra.write_text("{}\n", encoding="utf8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "results/review_evidence/unlisted.json"], check=True)
    monkeypatch.setattr(rp, "STEPS", [])
    monkeypatch.setattr(rp, "OUTPUTS", {})
    monkeypatch.setattr(rp, "TARGETED_PRODUCERS", {})
    monkeypatch.setattr(rp, "TARGETED_RUN_EVIDENCE", {})
    monkeypatch.setattr(rp, "EVIDENCE_ARCHIVES", ())
    assert any("unlisted.json has no manifest producer" in e for e in rp.check_manifest_completeness())
    allowed.unlink()
    assert any("unreadable" in e for e in rp.check_review_evidence_contract())


def _setup_interruption_probe(monkeypatch, tmp_path):
    """A previously successful local run and the actual new-run control flow."""
    stamp = tmp_path / ".reproduce-run.json"
    report = tmp_path / "reproduce-run-report.json"
    monkeypatch.setattr(rp, "STAMP", str(stamp))
    monkeypatch.setattr(rp, "REPORT", str(report))
    monkeypatch.setattr(rp, "STEPS", [("sample.py", "checks", 1)])
    monkeypatch.setattr(rp, "OUTPUTS", {"sample.py": ("results/not-a-real-output.json",)})
    monkeypatch.setattr(rp, "REQUIRED", ())
    monkeypatch.setattr(rp.sys, "argv", ["reproduce.py"])
    monkeypatch.setattr(rp, "check_environment", lambda: True)
    for name in ("check_manifest_completeness", "check_environment_lock",
                 "check_readme_counts", "check_test_counts"):
        monkeypatch.setattr(rp, name, lambda: [])
    monkeypatch.setattr(rp, "capture_inputs", lambda: {"outputs_excluded": []})
    monkeypatch.setattr(rp, "check_inputs_after", lambda before: before)
    rp.write_stamp(["sample.py"], [])
    report.write_text("old report\n", encoding="utf-8")
    assert rp.validate_stamp(rp.read_stamp()) == []
    return stamp, report


def test_interrupted_run_invalidates_previous_success(monkeypatch, tmp_path):
    _, report = _setup_interruption_probe(monkeypatch, tmp_path)

    def interrupt(_steps):
        raise KeyboardInterrupt

    monkeypatch.setattr(rp, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        rp.main()
    assert report.read_text(encoding="utf-8") == "old report\n"
    assert rp.validate_stamp(rp.read_stamp())
    assert not rp.verify()  # An old valid report cannot rescue the local run.


def test_report_write_interruption_keeps_old_report_and_fails_closed(monkeypatch, tmp_path):
    _, report = _setup_interruption_probe(monkeypatch, tmp_path)
    monkeypatch.setattr(rp, "run", lambda _steps: [])
    replace = rp.os.replace

    def interrupt_report(src, dst):
        if os.path.abspath(dst) == os.path.abspath(report):
            raise OSError("interrupted report replacement")
        return replace(src, dst)

    monkeypatch.setattr(rp.os, "replace", interrupt_report)
    with pytest.raises(OSError, match="interrupted report"):
        rp.main()
    assert report.read_text(encoding="utf-8") == "old report\n"
    assert rp.validate_stamp(rp.read_stamp())
    assert not rp.verify()


def test_success_stamp_is_published_only_after_complete_report(monkeypatch, tmp_path):
    stamp, report = _setup_interruption_probe(monkeypatch, tmp_path)
    monkeypatch.setattr(rp, "run", lambda _steps: [])
    monkeypatch.setattr(rp, "verify", lambda: True)
    original_write = rp._atomic_write_json
    writes = []

    def observe(path, value):
        if os.path.abspath(path) == os.path.abspath(stamp) and not value["failed"]:
            assert json.loads(report.read_text(encoding="utf-8"))["scripts"] == {
                "sample.py": {"status": "ok"}}
        writes.append(os.path.basename(path))
        original_write(path, value)

    monkeypatch.setattr(rp, "_atomic_write_json", observe)
    assert rp.main() == 0
    assert writes == [stamp.name, report.name, stamp.name]
    assert rp.validate_stamp(rp.read_stamp()) == []
