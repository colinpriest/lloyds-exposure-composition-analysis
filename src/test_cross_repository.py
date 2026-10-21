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


def test_the_record_carries_the_extraction_block():
    """Review rev14, H2: the suite reads the extraction's test_gemini.py, so the record names that checkout too."""
    with io.open(os.path.join(SRC, "record_tests.py"), encoding="utf-8") as _fh:
        src = _fh.read()
    assert '"extraction": extraction_read()}' in src


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
    """extraction_read: HEAD, whether the file read is modified, and whether it is the pinned commit's, byte for
    byte; no commit where there is no checkout."""
    (tmp_path / "test_gemini.py").write_bytes(b"pinned\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "add", ".")
    pin = _git(tmp_path, "commit", "-q", "-m", "pin")
    (tmp_path / "other.py").write_bytes(b"x\n")
    _git(tmp_path, "add", ".")
    later = _git(tmp_path, "commit", "-q", "-m", "a later commit that leaves the file read as it was")
    monkeypatch.setenv("LLOYDS_EXTRACTION_REPO", str(tmp_path))
    monkeypatch.setattr(record_tests, "extraction_pin", lambda: pin)
    got = record_tests.extraction_read()
    assert got == {"env": "LLOYDS_EXTRACTION_REPO", "path": str(tmp_path), "commit": later, "pin": pin,
                   "dirty": False, "files_at_pin": True}
    (tmp_path / "test_gemini.py").write_bytes(b"edited\n")
    assert record_tests.extraction_read()["dirty"] is True
    moved = _git(tmp_path, "commit", "-q", "-am", "the file read changes")
    got = record_tests.extraction_read()
    assert (got["commit"], got["dirty"], got["files_at_pin"]) == (moved, False, False)
    monkeypatch.setattr(record_tests, "extraction_pin", lambda: "0" * 40)
    assert record_tests.extraction_read()["files_at_pin"] is None
    monkeypatch.setenv("LLOYDS_EXTRACTION_REPO", str(tmp_path / "nowhere"))
    assert record_tests.extraction_read()["commit"] is None
