r"""Every tracked text file is stored with LF line endings.

The repository's rule is LF. On 16 October 2026 git stored 350 tracked files with CRLF (git ls-files --eol, i/crlf):
151 outputs of manifest scripts, which Python's text mode on Windows had written with CRLF (Path.write_text and open()
without newline, and the csv module, whose default line terminator is CRLF), and 199 files of the extraction error-rate
archive, with 10 more of mixed endings. All were renormalised; the writers now write LF (newline="", and
lineterminator="\n" for csv), so a recorded pass on Windows writes the bytes the commit holds.

The check reads git's own record of each file as stored (the index, "i/"), not the working tree, which a Windows
checkout with core.autocrlf=true converts to CRLF on purpose. Binary files ("i/-text") are not text and are not read.
Git must be available: a test that cannot run fails, it does not skip.

Run:  python -m pytest src/test_tracked_text_lf.py -q
"""
import os
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stored_line_endings(root=HERE):
    """{path: git's index line-ending class} for every tracked file (git ls-files --eol: i/lf, i/crlf, i/mixed,
    i/none or i/-text for binary)."""
    r = subprocess.run(["git", "-C", root, "ls-files", "--eol", "-z"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    out = {}
    for rec in r.stdout.decode("utf-8").split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        out[path] = meta.split()[0]
    return out


def crlf_files(root=HERE):
    """The tracked files git stores with CRLF or mixed line endings, sorted."""
    return sorted(p for p, eol in stored_line_endings(root).items() if eol in ("i/crlf", "i/mixed"))


def test_the_listing_covers_the_tree():
    eols = stored_line_endings()
    # the listing is the whole tree (a few thousand files), and reads text files as text
    assert len(eols) > 1000
    assert eols["src/run_analysis.py"] == "i/lf" and eols["data/pyd_confirmed_figures.json"] == "i/lf"


def test_the_document_rewriter_writes_lf_and_says_when_it_wrote(tmp_path):
    """build_current_results._rw: a CRLF document is written back with LF even when its edit changes nothing, and the
    return says it was written; an LF document the edit leaves alone is not written and the return says so."""
    import sys
    sys.path.insert(0, os.path.join(HERE, "src"))
    import build_current_results as bcr
    p = tmp_path / "doc.md"
    with open(str(p), "wb") as fh:
        fh.write(b"a\r\nb\r\n")
    assert bcr._rw(str(p), lambda t: t) is True
    with open(str(p), "rb") as fh:
        assert fh.read() == b"a\nb\n"
    assert bcr._rw(str(p), lambda t: t) is False
    assert bcr._rw(str(p), lambda t: t + "c\n") is True
    with open(str(p), "rb") as fh:
        assert fh.read() == b"a\nb\nc\n"


def test_no_tracked_text_file_is_stored_with_crlf():
    bad = crlf_files()
    assert not bad, "%d tracked file(s) stored with CRLF or mixed line endings, e.g. %s" % (len(bad), bad[:10])
