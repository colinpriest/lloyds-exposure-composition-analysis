r"""Every file the analysis opens is opened by a with statement, so it is closed when the block ends.

Until 18 October 2026, 377 calls in 143 files opened a file without closing it: `io.open(p, "w", ...).write(text)`,
`io.open(p).read()`, `json.load(io.open(p))`, `json.dump(obj, io.open(p, "w"))`, `csv.DictReader(io.open(p))` and a
loop over `enumerate(io.open(p))`. CPython's reference counting happens to close such a file at once, but nothing
in the language says so, and a write left open can lose its tail on another interpreter or under a debugger. Each is
now `with io.open(...) as f:` with the call's own mode, encoding and newline unchanged.

The check is an AST scan of src/*.py and the root *.py: every call to open, io.open, codecs.open or <path>.open must
be the context expression of a with item. Two exemptions, each named: run_analysis._open_w returns an open file to
its callers, which open it in a with statement (checked here too); and .open on PyMuPDF, zipfile, tarfile,
webbrowser or PIL's Image is not a file open (the PyMuPDF documents are closed explicitly).

Run:  python -m pytest src/test_no_unclosed_open.py -q
"""
import ast
import io
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: receivers whose .open(...) is not a file open
NOT_FILES = ("fitz", "zipfile", "tarfile", "webbrowser", "Image")
#: (file, function) that return an open file to a caller's with statement
RETURNS_OPEN = {("src/run_analysis.py", "_open_w")}


def _is_open(call):
    f = call.func
    if isinstance(f, ast.Name):
        return f.id == "open"
    if isinstance(f, ast.Attribute) and f.attr == "open":
        return not (isinstance(f.value, ast.Name) and f.value.id in NOT_FILES)
    return False


def _sources(root=HERE):
    src = os.path.join(root, "src")
    out = ["src/" + f for f in sorted(os.listdir(src)) if f.endswith(".py")]
    return out + [f for f in sorted(os.listdir(root)) if f.endswith(".py")]


def unclosed_opens(root=HERE):
    """(sites, n_with): every open call that is not a with item and not exempt, as "path:line: source", and the
    number of open calls that are with items."""
    sites, n_with = [], 0
    for rel in _sources(root):
        with io.open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            text = fh.read()
        tree = ast.parse(text, rel)
        with_items = {id(it.context_expr) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))
                      for it in n.items}
        returns_open = set()
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (rel, fn.name) in RETURNS_OPEN:
                returns_open |= {id(r.value) for r in ast.walk(fn) if isinstance(r, ast.Return) and r.value is not None}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_open(node)):
                continue
            if id(node) in with_items:
                n_with += 1
            elif id(node) not in returns_open:
                sites.append("%s:%d: %s" % (rel, node.lineno, (ast.get_source_segment(text, node) or "")[:80]))
    return sites, n_with


def test_every_open_is_a_with_item():
    sites, n_with = unclosed_opens()
    # the scan reads the tree: several hundred opens, all in with statements
    assert n_with > 300, n_with
    assert not sites, "%d open call(s) not in a with statement, e.g. %s" % (len(sites), sites[:10])


def test_the_open_helper_is_used_in_with_statements_only():
    """run_analysis._open_w's file is closed by its caller: every call of it is a with item."""
    with io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    with_items = {id(it.context_expr) for n in ast.walk(tree) if isinstance(n, ast.With) for it in n.items}
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_open_w"]
    assert calls and all(id(c) in with_items for c in calls)
