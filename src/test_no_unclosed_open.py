r"""Every file the analysis opens is opened by a with statement, so it is closed when the block ends.

Until 18 October 2026, 377 calls in 143 files opened a file without closing it: `io.open(p, "w", ...).write(text)`,
`io.open(p).read()`, `json.load(io.open(p))`, `json.dump(obj, io.open(p, "w"))`, `csv.DictReader(io.open(p))` and a
loop over `enumerate(io.open(p))`. CPython's reference counting happens to close such a file at once, but nothing
in the language says so, and a write left open can lose its tail on another interpreter or under a debugger. Each is
now `with io.open(...) as f:` with the call's own mode, encoding and newline unchanged.

The check is an AST scan of every tracked .py file (git ls-files) outside the evidence archive. Each file's imports
are read first, so a name is resolved to what it imports: `import os as o` makes `o.fdopen` os.fdopen, and
`from os import open` makes `open` os.open in that file.

  * every call that opens a file -- the builtin open, io.open, io.FileIO, codecs.open, os.fdopen, builtins.open
    (each under any module alias or imported name), getattr(<module>, "<name>") of one of them, or <path>.open --
    must be the context expression of a with item, or the argument of a contextlib.closing call that is one;
  * a file-opening function may not be referenced except to call it (`_o = io.open` or `_o = getattr(io, "open")`
    would hide the calls from the rule above), nor imported by name (`from io import open as o`, `from os import
    fdopen`, `from io import FileIO`);
  * os.open is not a file open (it returns a descriptor, which os.fdopen then opens) and is not flagged, under its
    module's name, an alias of it, or `from os import open`; .open on PyMuPDF, zipfile, tarfile, webbrowser or PIL's
    Image is not a file open either (the PyMuPDF documents are closed explicitly).

What the scan cannot see: a name resolved at run time (getattr with a computed name, importlib), and a file opened in
a module that is not tracked (git ls-files reads the index, so a new script is scanned once it is added). The scan
needs a git work tree and fails, saying why, without one.

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
#: modules (or the last part of a dotted module) whose .open(...) is not a file open (os.open returns a descriptor)
NOT_FILES = ("fitz", "zipfile", "tarfile", "webbrowser", "Image", "os")
#: module attributes that open a file object
OPENERS = {("io", "open"), ("io", "FileIO"), ("codecs", "open"), ("os", "fdopen"), ("builtins", "open")}
#: the wrappers a with statement closes the file through
CLOSERS = {("contextlib", "closing")}
#: (file, function) that return an open file to a caller's with statement
RETURNS_OPEN = {("src/run_analysis.py", "_open_w")}
#: the evidence archive: the study's scripts as they ran, hashed by its MANIFEST.json, not run by the analysis
ARCHIVES = ("results/extraction_error_rate/",)


def file_imports(tree):
    """(modules, names) a module's imports bind: modules maps a local name to the module it names (`import os as o`;
    a dotted `import os.path` binds its first part), names maps a local name to (module, attribute) (`from os import
    open`). Relative imports are left out: no analysis module is an opener."""
    modules, names = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    modules[alias.asname] = alias.name
                else:
                    first = alias.name.split(".")[0]
                    modules[first] = first
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = (node.module, alias.name)
    return modules, names


def _getattr_as_attribute(node):
    """getattr(<receiver>, "<name>"[, default]) as the attribute expression <receiver>.<name>, or None."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
            and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
        return ast.Attribute(value=node.args[0], attr=node.args[1].value, ctx=ast.Load())
    return None


def resolve(node, imports):
    """(module, attribute) an expression names, as the file's imports bind it: a plain name is the builtin unless an
    import binds it; an attribute of a module alias or an imported name is that module's; (None, attr) for an
    attribute of anything else. getattr(<receiver>, "<name>") resolves as <receiver>.<name>."""
    modules, names = imports
    as_attr = _getattr_as_attribute(node)
    if as_attr is not None:
        node = as_attr
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        return ("builtins", node.id)
    if isinstance(node, ast.Attribute):
        base = node.value
        if isinstance(base, ast.Name):
            if base.id in modules:
                return (modules[base.id], node.attr)
            if base.id in names:
                return (".".join(names[base.id]), node.attr)
            return (None if base.id not in NOT_FILES else base.id, node.attr)
        return (None, node.attr)
    return (None, None)


def is_opener_ref(node, imports):
    """Whether an expression names a file-opening function: the builtin open, an OPENERS attribute under the name or
    alias the file imports it by, getattr of one, or .open on any receiver but a NOT_FILES module."""
    if not (isinstance(node, (ast.Name, ast.Attribute)) or _getattr_as_attribute(node) is not None):
        return False
    module, attr = resolve(node, imports)
    if (module, attr) in OPENERS or (module, attr) == ("builtins", "open"):
        return True
    if isinstance(node, ast.Name):
        return False
    return attr == "open" and (module is None or module.split(".")[-1] not in NOT_FILES)


def tracked_sources(root=HERE):
    """Every tracked .py file outside the evidence archive, as git ls-files names it."""
    r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--", "*.py"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    paths = [p for p in r.stdout.decode("utf-8").split("\0") if p]
    return sorted(p for p in paths if not p.startswith(ARCHIVES)), sorted(p for p in paths if p.startswith(ARCHIVES))


def unclosed_opens(root=HERE):
    """(sites, n_with, n_files): every file-opening call that is not a with item (or wrapped by a CLOSERS call that is
    one) and not exempt, every non-call reference to a file-opening function and every by-name import of one, as
    "path:line: what"; the number of file-opening calls closed by a with statement; and the number of files read."""
    sites, n_with = [], 0
    sources, _archived = tracked_sources(root)
    for rel in sources:
        with io.open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            text = fh.read()
        tree = ast.parse(text, rel)
        imports = file_imports(tree)
        with_items = {id(it.context_expr) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))
                      for it in n.items}
        # contextlib.closing(<open call>) as a with item closes the file it wraps
        closed = {id(it.context_expr.args[0]) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))
                  for it in n.items if isinstance(it.context_expr, ast.Call) and it.context_expr.args
                  and resolve(it.context_expr.func, imports) in CLOSERS}
        returns_open = set()
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (rel, fn.name) in RETURNS_OPEN:
                returns_open |= {id(r.value) for r in ast.walk(fn) if isinstance(r, ast.Return) and r.value is not None}
        call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and is_opener_ref(node.func, imports):
                if id(node) in with_items or id(node) in closed:
                    n_with += 1
                elif id(node) not in returns_open:
                    sites.append("%s:%d: unclosed %s" % (rel, node.lineno,
                                                         (ast.get_source_segment(text, node) or "")[:80]))
            elif ((isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
                   or _getattr_as_attribute(node) is not None)
                  and is_opener_ref(node, imports) and id(node) not in call_funcs):
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


#: the probes: each line ending "# flagged" must be reported, and no other line; the good files' with items are the
#: opens the scan counts as closed
BAD = ("import io, os, builtins, codecs\n"
       "import os as o\n"
       "import io as i2\n"
       "from contextlib import closing\n"
       "from io import open as op2  # flagged\n"
       "from io import FileIO  # flagged\n"
       "_o = io.open  # flagged\n"
       "_g = getattr(io, 'open')  # flagged\n"
       "def a(p):\n    return io.open(p).read()  # flagged\n"
       "def b(p):\n    return os.fdopen(os.open(p, os.O_RDONLY)).read()  # flagged\n"
       "def c(p):\n    return builtins.open(p).read()  # flagged\n"
       "def d(p):\n    return codecs.open(p).read()  # flagged\n"
       "def e(p):\n    return o.fdopen(o.open(p, o.O_RDONLY)).read()  # flagged\n"
       "def f(p):\n    return getattr(io, 'open')(p).read()  # flagged\n"
       "def g(p):\n    return io.FileIO(p).read()  # flagged\n"
       "def h(p):\n    return i2.FileIO(p).read()  # flagged\n"
       "def k(p):\n    return closing(open(p))  # flagged\n"
       "def m(p):\n    return open(p).read()  # flagged\n")
GOOD = {
    "good.py": ("import io, os\n"
                "def e(p):\n    fd = os.open(p, os.O_RDONLY)\n    os.close(fd)\n"
                "def f(p):\n    with io.open(p) as fh, os.fdopen(os.open(p, os.O_RDONLY)) as g:\n"
                "        return fh.read() + g.read()\n"),
    # `open` here is os.open, which returns a descriptor
    "os_open.py": ("from os import open, close, O_RDONLY\n"
                   "def k(p):\n    close(open(p, O_RDONLY))\n"),
    "closing.py": ("import contextlib, io, os as o\n"
                   "from contextlib import closing\n"
                   "def m(p):\n    with contextlib.closing(open(p)) as f, closing(io.open(p)) as g:\n"
                   "        return f.read() + g.read()\n"
                   "def n(p):\n    fd = o.open(p, o.O_RDONLY)\n    with o.fdopen(fd) as f:\n        return f.read()\n"),
}


def test_the_scan_catches_each_form(tmp_path):
    """The rules above, on a scratch repository: each bypass the reviews of 18 October 2026 (rev9, C9) and 21 October
    2026 (rev13, D4) found is reported -- an aliased module's fdopen, getattr of an opener, io.FileIO --, and the forms
    that are not file opens or are closed by a with statement are not: os.open imported by name, and an open wrapped in
    contextlib.closing as a with item."""
    src = tmp_path / "src"
    src.mkdir()
    files = dict(GOOD, **{"bad.py": BAD})
    for name, body in files.items():
        with io.open(str(src / name), "w", encoding="utf-8", newline="") as fh:
            fh.write(body)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add"] + ["src/" + n for n in sorted(files)], check=True)
    sites, n_with, n_files = unclosed_opens(str(tmp_path))
    found = sorted((s.split(":")[0], int(s.split(":")[1])) for s in sites)
    want = sorted(("src/bad.py", n) for n, line in enumerate(BAD.splitlines(), 1) if line.endswith("# flagged"))
    assert len(want) == 14
    assert found == want, sites
    # good.py's two, closing.py's two closing() wraps and its aliased fdopen
    assert (n_with, n_files) == (5, 4)
