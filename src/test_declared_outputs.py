#!/usr/bin/env python3
"""Every file a manifest step writes is declared among its OUTPUTS in reproduce.py, found from the sources.

The verification of 26 October 2026 (G1): dropping the small-book diagnosis's declaration survived every test, because no
test compared what a producer writes with what the manifest declares until its output was tracked. --verify compares the
declared outputs with the committed ones, so an undeclared output is a file no pass checks and no attestation covers.

The scan reads each step's source. A write is a call of open/io.open in a write mode, np.savez / np.savez_compressed, or
.savefig, whose path it can resolve: a literal, or a name (a module-level constant or a function default) bound to
SD / "results" / "x.json" and the like. A path it cannot resolve (an f-string, a loop variable, a suffix swap) is not
guessed. Every resolved write must be declared by the step. The scan has its own tests (a toy source, and the three
producers of 26 October 2026 by name), so it cannot go quiet by resolving nothing.

Run:  python -m pytest src/test_declared_outputs.py -q
"""
import ast
import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import reproduce  # noqa: E402

#: names that stand for the repository root in a path expression
ROOTS = {"SD", "SCRIPT_DIR", "HERE", "ROOT", "REPO"}
WRITE_FUNCS = {"savez", "savez_compressed"}


class Resolver:
    def __init__(self, tree):
        self.module = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                self.module[n.targets[0].id] = n.value
        self.local = {}

    def value(self, node, depth=0):
        """The relative posix path an expression stands for, or None."""
        if depth > 8:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ROOTS:
                return ""
            for scope in (self.local, self.module):
                if node.id in scope:
                    return self.value(scope[node.id], depth + 1)
            return None
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("str", "Path") and len(node.args) == 1:
            return self.value(node.args[0], depth + 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a, b = self.value(node.left, depth + 1), self.value(node.right, depth + 1)
            return None if a is None or b is None else a + b
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = self.value(node.left, depth + 1), self.value(node.right, depth + 1)
            if a is None or b is None:
                return None
            return (a + "/" + b).lstrip("/") if a else b
        return None


def written_paths(src):
    """The relative paths of the writes in `src` that the scan can resolve."""
    tree = ast.parse(src)
    res = Resolver(tree)
    out = set()
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    scopes = [(tree, {})]
    for fn in funcs:
        defaults = {}
        args = fn.args
        pos = args.args[len(args.args) - len(args.defaults):]
        defaults.update({a.arg: d for a, d in zip(pos, args.defaults)})
        defaults.update({a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None})
        scopes.append((fn, defaults))
    for scope, defaults in scopes:
        res.local = defaults
        body = [n for n in (scope.body if hasattr(scope, "body") else [])]
        for stmt in body:
            for node in ast.walk(stmt):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", getattr(node.func, "id", None))
                target = None
                if name == "open" and node.args:
                    mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords
                                                                          if k.arg == "mode"), None)
                    if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "w" in mode.value:
                        target = node.args[0]
                elif name in WRITE_FUNCS and node.args:
                    target = node.args[0]
                elif name == "savefig" and node.args:
                    target = node.args[0]
                if target is not None:
                    p = res.value(target)
                    if p:
                        out.add(p)
    return out


def test_the_scan_resolves_the_writes_of_a_toy_source():
    src = ('import io, numpy as np\nSD = None\nOUT = SD / "results" / "a.json"\nNPZ = SD / "results" / "a.npz"\n'
           'def f(png=SD / "paper_pack" / "p.png"):\n'
           '    with io.open(str(OUT), "w", encoding="utf-8") as fh:\n        fh.write("x")\n'
           '    np.savez_compressed(str(NPZ), a=1)\n    fig.savefig(png)\n'
           '    with open(OUT) as fh:\n        pass\n    with open(unknown, "w") as fh:\n        pass\n')
    assert written_paths(src) == {"results/a.json", "results/a.npz", "paper_pack/p.png"}


def _step_sources():
    out = {}
    for sc, _stage, _m in reproduce.STEPS:
        path = os.path.join(HERE, "src", sc)
        if os.path.exists(path):
            with io.open(path, encoding="utf-8") as fh:
                out[sc] = fh.read()
    return out


SOURCES = _step_sources()


def test_the_scan_finds_the_three_new_producers_writes():
    assert written_paths(SOURCES["check_small_book_diagnosis.py"]) == {"results/check_small_book_diagnosis_results.json"}
    assert written_paths(SOURCES["check_exclusion_influence.py"]) == {"results/check_exclusion_influence_results.json",
                                                                       "results/check_exclusion_influence_draws.npz"}
    assert written_paths(SOURCES["make_uncertainty_figure.py"]) == {
        "paper_pack/fig_uncertainty_sources.png", "paper_pack/fig_uncertainty_sources.pdf",
        "results/make_uncertainty_figure_results.json"}


def test_the_scan_finds_most_steps_writes():
    """It resolves something for the large majority of the steps that write results: not a scan that has gone quiet."""
    found = [sc for sc, src in SOURCES.items() if written_paths(src)]
    assert len(found) >= 40, len(found)


@pytest.mark.parametrize("script", sorted(SOURCES))
def test_every_resolved_write_of_a_step_is_declared(script):
    written = written_paths(SOURCES[script])
    declared = set(reproduce.OUTPUTS.get(script, ()))
    undeclared = sorted(written - declared)
    assert not undeclared, "%s writes %s, which reproduce.OUTPUTS does not declare for it" % (script, undeclared)


def test_a_dropped_declaration_is_caught(monkeypatch):
    """The review's mutation: the small-book diagnosis loses its OUTPUTS entry."""
    outputs = dict(reproduce.OUTPUTS)
    outputs.pop("check_small_book_diagnosis.py")
    monkeypatch.setattr(reproduce, "OUTPUTS", outputs)
    written = written_paths(SOURCES["check_small_book_diagnosis.py"])
    assert written - set(reproduce.OUTPUTS.get("check_small_book_diagnosis.py", ()))
