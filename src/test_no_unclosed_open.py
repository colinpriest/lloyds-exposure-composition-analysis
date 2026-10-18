r"""Every file the analysis opens is opened by a with statement, so it is closed when the block ends.

Until 18 October 2026, 377 calls in 143 files opened a file without closing it: `io.open(p, "w", ...).write(text)`,
`io.open(p).read()`, `json.load(io.open(p))`, `json.dump(obj, io.open(p, "w"))`, `csv.DictReader(io.open(p))` and a
loop over `enumerate(io.open(p))`. CPython's reference counting happens to close such a file at once, but nothing
in the language says so, and a write left open can lose its tail on another interpreter or under a debugger. Each is
now `with io.open(...) as f:` with the call's own mode, encoding and newline unchanged.

The check is an AST scan of every tracked .py file (git ls-files) outside the evidence archive:

  * every call that opens a file -- open, io.open, codecs.open, os.fdopen, builtins.open, or <path>.open -- must be
    the context expression of a with item;
  * a file-opening function may not be referenced except to call it (`_o = io.open` would hide the calls from the
    rule above), nor imported by name (`from io import open as o`, `from os import fdopen`);
  * os.open is not a file open (it returns a descriptor, which os.fdopen then opens) and is not flagged; .open on
    PyMuPDF, zipfile, tarfile, webbrowser or PIL's Image is not a file open either (the PyMuPDF documents are closed
    explicitly).

Two exemptions, each named. run_analysis._open_w returns an open file to its callers, which open it in a with
statement (checked here too). The evidence archive results/extraction_error_rate/ is excluded: it holds the scripts
of the error-rate study as they ran, hashed byte for byte by its MANIFEST.json, and is not code the analysis runs
(reproduce.EVIDENCE_ARCHIVES); its scripts are listed by the scan's own count, not edited.

Run:  python -m pytest src/test_no_unclosed_open.py -q
"""
import ast
import io
import os
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: receivers whose .open(...) is not a file open (os.open returns a descriptor)
NOT_FILES = ("fitz", "zipfile", "tarfile", "webbrowser", "Image", "os")
#: module attributes that open a file object
OPENERS = {("io", "open"), ("codecs", "open"), ("os", "fdopen"), ("builtins", "open")}
#: (file, function) that return an open file to a caller's with statement
RETURNS_OPEN = {("src/run_analysis.py", "_open_w")}
#: the evidence archive: the study's scripts as they ran, hashed by its MANIFEST.json, not run by the analysis
ARCHIVES = ("results/extraction_error_rate/",)


def _is_opener_ref(node):
    """Whether an expression names a file-opening function: open, or io.open, codecs.open, os.fdopen, builtins.open,
    or .open on any receiver but the NOT_FILES ones."""
    if isinstance(node, ast.Name):
        return node.id == "open"
    if isinstance(node, ast.Attribute):
        base = node.value.id if isinstance(node.value, ast.Name) else None
        if (base, node.attr) in OPENERS:
            return True
        return node.attr == "open" and base not in NOT_FILES
    return False


def tracked_sources(root=HERE):
    """Every tracked .py file outside the evidence archive, as git ls-files names it."""
    r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--", "*.py"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    paths = [p for p in r.stdout.decode("utf-8").split("\0") if p]
    return sorted(p for p in paths if not p.startswith(ARCHIVES)), sorted(p for p in paths if p.startswith(ARCHIVES))


def unclosed_opens(root=HERE):
    """(sites, n_with, n_files): every file-opening call that is not a with item and not exempt, every non-call
    reference to a file-opening function and every by-name import of one, as "path:line: what"; the number of
    file-opening calls that are with items; and the number of files read."""
    sites, n_with = [], 0
    sources, _archived = tracked_sources(root)
    for rel in sources:
        with io.open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            text = fh.read()
        tree = ast.parse(text, rel)
        with_items = {id(it.context_expr) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))
                      for it in n.items}
        returns_open = set()
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (rel, fn.name) in RETURNS_OPEN:
                returns_open |= {id(r.value) for r in ast.walk(fn) if isinstance(r, ast.Return) and r.value is not None}
        call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_opener_ref(node.func):
                if id(node) in with_items:
                    n_with += 1
                elif id(node) not in returns_open:
                    sites.append("%s:%d: unclosed %s" % (rel, node.lineno,
                                                         (ast.get_source_segment(text, node) or "")[:80]))
            elif (isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
                  and _is_opener_ref(node) and id(node) not in call_funcs):
                sites.append("%s:%d: a reference to %s that is not a call"
                             % (rel, node.lineno, ast.get_source_segment(text, node)))
            elif isinstance(node, ast.ImportFrom) and node.module in ("io", "codecs", "os", "builtins"):
                for alias in node.names:
                    if (node.module, alias.name) in OPENERS:
                        sites.append("%s:%d: from %s import %s" % (rel, node.lineno, node.module, alias.name))
    return sites, n_with, len(sources)


def test_every_open_is_a_with_item():
    sites, n_with, n_files = unclosed_opens()
    # the scan reads the tree: every tracked script, several hundred opens, all in with statements
    assert n_files > 150 and n_with > 300, (n_files, n_with)
    assert not sites, "%d open site(s) not in a with statement, e.g. %s" % (len(sites), sites[:10])


def test_the_scan_reads_every_tracked_script_but_the_archive():
    sources, archived = tracked_sources()
    assert "reproduce.py" in sources and "src/run_analysis.py" in sources and "conftest.py" in sources
    assert all(p.startswith(ARCHIVES) for p in archived) and not any(p.startswith(ARCHIVES) for p in sources)


def test_the_open_helper_is_used_in_with_statements_only():
    """run_analysis._open_w's file is closed by its caller: every call of it is a with item."""
    with io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    with_items = {id(it.context_expr) for n in ast.walk(tree) if isinstance(n, ast.With) for it in n.items}
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_open_w"]
    assert calls and all(id(c) in with_items for c in calls)


def test_the_scan_catches_each_form(tmp_path):
    """The rules above, on a scratch repository: each bypass the review of 18 October 2026 (rev9, C9) found is
    reported, and the forms that are not file opens are not."""
    src = tmp_path / "src"
    src.mkdir()
    bad = ("import io, os, builtins, codecs\n"
           "from io import open as op2\n"
           "_o = io.open\n"
           "def a(p):\n    return io.open(p).read()\n"
           "def b(p):\n    return os.fdopen(os.open(p, os.O_RDONLY)).read()\n"
           "def c(p):\n    return builtins.open(p).read()\n"
           "def d(p):\n    return codecs.open(p).read()\n")
    good = ("import io, os\n"
            "def e(p):\n    fd = os.open(p, os.O_RDONLY)\n    os.close(fd)\n"
            "def f(p):\n    with io.open(p) as fh, os.fdopen(os.open(p, os.O_RDONLY)) as g:\n"
            "        return fh.read() + g.read()\n")
    for name, body in (("bad.py", bad), ("good.py", good)):
        with io.open(str(src / name), "w", encoding="utf-8", newline="") as fh:
            fh.write(body)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "src/bad.py", "src/good.py"], check=True)
    sites, n_with, n_files = unclosed_opens(str(tmp_path))
    found = sorted((s.split(":")[0], int(s.split(":")[1])) for s in sites)
    assert found == [("src/bad.py", 2), ("src/bad.py", 3), ("src/bad.py", 5), ("src/bad.py", 7), ("src/bad.py", 9),
                     ("src/bad.py", 11)], sites
    assert (n_with, n_files) == (2, 2)
