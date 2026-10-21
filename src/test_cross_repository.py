"""The README lists every test file that reads the manuscript, and the suite record names the manuscript it read.

The README said one test crosses into the manuscript; test_figure_layout.py does too (the review of 2 October 2026,
A-1), and the suite record named no manuscript commit. The list is held to the test files that read
LLOYDS_PAPER_REPO, so the next cross-repository test cannot go unlisted, and record_tests.py writes the manuscript
checkout and its commit into the record.

Run:  python -m pytest src/test_cross_repository.py -q
"""
import io
import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)
import record_tests  # noqa: E402

LIST = re.compile(r"<!-- cross-repository-tests:start -->\n(.*?)<!-- cross-repository-tests:end -->", re.S)


def reading_tests():
    """Test files whose source reads the manuscript location from the environment."""
    out = []
    for fn in sorted(os.listdir(SRC)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        with io.open(os.path.join(SRC, fn), encoding="utf-8") as _fh:
            src = _fh.read()
        if re.search(r"""os\.environ\.get\((?:"LLOYDS_PAPER_REPO"|PAPER_ENV)\)""", src) and "LLOYDS_PAPER_REPO" in src:
            out.append("src/" + fn)
    return out


def test_the_readme_lists_every_test_that_reads_the_manuscript():
    with io.open(os.path.join(HERE, "README.md"), encoding="utf-8") as _fh:
        readme = _fh.read()
    listed = re.findall(r"^- `([^`]+)`$", LIST.search(readme).group(1), re.M)
    assert listed == reading_tests()
    assert len(listed) >= 2
    words = {1: "One test file crosses", 2: "Two test files cross", 3: "Three test files cross"}
    assert words[len(listed)] in readme


def test_the_record_names_the_manuscript_checkout_and_its_commit(tmp_path, monkeypatch):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text("x", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "m"],
                   check=True)
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    monkeypatch.setenv("LLOYDS_PAPER_REPO", str(tmp_path))
    got = record_tests.manuscript_read()
    assert got == {"env": "LLOYDS_PAPER_REPO", "path": str(tmp_path), "commit": head, "dirty": False}
    (paper / "main.tex").write_text("y", encoding="utf-8")
    assert record_tests.manuscript_read()["dirty"] is True
    monkeypatch.setenv("LLOYDS_PAPER_REPO", str(tmp_path / "nowhere"))
    assert record_tests.manuscript_read()["commit"] is None


def test_the_record_carries_the_manuscript_block():
    with io.open(os.path.join(SRC, "record_tests.py"), encoding="utf-8") as _fh:
        src = _fh.read()
    assert '"manuscript": manuscript_read(),' in src


def _extraction_checkout(tmp_path, monkeypatch):
    """A scratch extraction checkout at its pin, then a later commit that leaves the file read as it was:
    (root, pin, later). LLOYDS_EXTRACTION_REPO names it, and the pin is its first commit."""
    root = tmp_path / "extraction"
    root.mkdir()
    (root / "test_gemini.py").write_bytes(b"pinned\nline two\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", ".")
    pin = _git(root, "commit", "-q", "-m", "pin")
    (root / "other.py").write_bytes(b"x\n")
    _git(root, "add", ".")
    later = _git(root, "commit", "-q", "-m", "a later commit that leaves the file read as it was")
    monkeypatch.setenv("LLOYDS_EXTRACTION_REPO", str(root))
    monkeypatch.setattr(record_tests, "extraction_pin", lambda: pin)
    return root, pin, later


def test_the_record_carries_the_extraction_block(tmp_path, monkeypatch):
    """Review rev14, H2 (rev15: run, not read): the suite reads the extraction's test_gemini.py, so the record
    build_record writes names that checkout's state, as extraction_read reads it."""
    root, pin, later = _extraction_checkout(tmp_path, monkeypatch)
    monkeypatch.setattr(record_tests, "collect_only", lambda: 0)
    rec = record_tests.build_record({"passed": 1, "skipped": 0, "failed": 0, "skip_reasons": {}})
    assert rec["extraction"] == record_tests.extraction_read()
    assert (rec["extraction"]["commit"], rec["extraction"]["pin"], rec["extraction"]["dirty"],
            rec["extraction"]["files_at_pin"]) == (later, pin, False, True)


def test_a_recorded_run_cannot_skip_the_extraction_test():
    """Without an extraction checkout its test skips (the declared extraction_absent reason), and record_tests
    refuses to record or stamp a run that skipped it: a recorded suite needs the pinned checkout."""
    reason = ("no extraction repository at D:\\dev\\lloyds_reserve_stress_testing: set LLOYDS_EXTRACTION_REPO to the "
              "extraction repository, or this cross-repository check does not run")
    with pytest.raises(SystemExit, match=r"\[extraction_absent\]"):
        record_tests.refuse_skips({reason: 1})
    out = "SKIPPED [1] src\\test_unreconciled_triangle_rule.py:214: %s\n" % reason
    assert record_tests.skip_reasons(out) == {reason: 1}


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t"] + list(args), check=True,
                   capture_output=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def test_the_extraction_pin_is_the_documented_import():
    with io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8") as _fh:
        doc = _fh.read()
    pin = record_tests.extraction_pin()
    assert re.fullmatch(r"[0-9a-f]{40}", pin) and "The current import is the extraction's commit `%s`" % pin in doc


def test_the_record_names_the_extraction_checkout_its_commit_and_its_state(tmp_path, monkeypatch):
    """extraction_read: the top level, HEAD, whether the file read differs from HEAD's blob, and whether it is the
    pinned commit's, byte for byte (line endings aside); no commit where there is no checkout."""
    root, pin, later = _extraction_checkout(tmp_path, monkeypatch)
    got = record_tests.extraction_read()
    assert record_tests._same_path(got.pop("toplevel"), str(root))
    assert got == {"env": "LLOYDS_EXTRACTION_REPO", "path": str(root), "commit": later, "pin": pin,
                   "dirty": False, "files_at_pin": True}
    # a working copy with CRLF line endings holds the same file
    (root / "test_gemini.py").write_bytes(b"pinned\r\nline two\r\n")
    got = record_tests.extraction_read()
    assert (got["dirty"], got["files_at_pin"]) == (False, True)
    (root / "test_gemini.py").write_bytes(b"edited\n")
    assert record_tests.extraction_read()["dirty"] is True
    moved = _git(root, "commit", "-q", "-am", "the file read changes")
    got = record_tests.extraction_read()
    assert (got["commit"], got["dirty"], got["files_at_pin"]) == (moved, False, False)
    monkeypatch.setattr(record_tests, "extraction_pin", lambda: "0" * 40)
    assert record_tests.extraction_read()["files_at_pin"] is None
    monkeypatch.setenv("LLOYDS_EXTRACTION_REPO", str(tmp_path / "nowhere"))
    assert record_tests.extraction_read()["commit"] is None


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_an_edit_git_status_hides_is_still_an_edit(tmp_path, monkeypatch, flag):
    """Review rev15: git status does not show an edit to a file marked assume-unchanged or skip-worktree; the file's
    own bytes are compared, so the edit is seen."""
    root, _pin, _later = _extraction_checkout(tmp_path, monkeypatch)
    _git(root, "update-index", flag, "test_gemini.py")
    (root / "test_gemini.py").write_bytes(b"pinned\nline two, edited where git status cannot see it\n")
    assert subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True,
                          text=True).stdout.strip() == ""
    got = record_tests.extraction_read()
    assert (got["dirty"], got["files_at_pin"]) == (True, False)


def test_a_folder_inside_another_repository_is_not_read_as_a_checkout(tmp_path, monkeypatch):
    """Review rev15: a folder holding test_gemini.py inside another repository is not that repository's top level;
    its files would be resolved against the other repository, so it is recorded with that top level and no commit."""
    outer = tmp_path / "outer"
    (outer / "sub").mkdir(parents=True)
    (outer / "sub" / "test_gemini.py").write_bytes(b"pinned\n")
    subprocess.run(["git", "init", "-q", str(outer)], check=True)
    _git(outer, "add", ".")
    _git(outer, "commit", "-q", "-m", "outer")
    monkeypatch.setenv("LLOYDS_EXTRACTION_REPO", str(outer / "sub"))
    got = record_tests.extraction_read()
    assert record_tests._same_path(got["toplevel"], str(outer))
    assert (got["commit"], got["dirty"], got["files_at_pin"]) == (None, None, None)
