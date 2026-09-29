#!/usr/bin/env python3
"""The skip budget: every reason the suite can skip for is declared, and a recorded run skips nothing.

Review of 29 September 2026 (A-7): the recorded "1110 passed, 14 skipped" hid 37 tests of the transfer tool
that skip wherever Node.js is absent, and 14 permanently skipping tests of removed code. src/skip_budget.py
now declares every skip reason with the environment that produces it, the root conftest.py fails a session
whose skips include an undeclared reason, and src/record_tests.py refuses to record or stamp any run that
skipped. These tests hold each of the three, statically over the suite's own sources and behaviourally in a
throwaway pytest session.

Run:  python -m pytest src/test_skip_budget.py -q
"""
import ast
import io
import os
import shutil
import subprocess
import sys

import pytest

SRC = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SRC)
sys.path.insert(0, SRC)
import skip_budget        # noqa: E402
import record_tests       # noqa: E402

SKIP_CALLS = ("pytest.skip", "pytest.mark.skip", "pytest.mark.skipif", "pytest.importorskip")


def _text(node):
    """The reason as written, with every computed part replaced by X, or None when it cannot be read."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "X" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = _text(node.left)
        return None if left is None else left.replace("%s", "X").replace("%d", "1").replace("%r", "X")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (_text(node.left) or "X") + (_text(node.right) or "X")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        base = _text(node.func.value)
        return None if base is None else base.replace("{}", "X")
    return None


def _skip_calls():
    """(file, line, reason) for every skip the suite's sources can raise."""
    files = [os.path.join(SRC, f) for f in sorted(os.listdir(SRC)) if f.startswith("test_") and f.endswith(".py")]
    files.append(os.path.join(HERE, "conftest.py"))
    out = []
    for path in files:
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and ast.unparse(node.func) in SKIP_CALLS):
                continue
            kind = ast.unparse(node.func)
            if kind == "pytest.importorskip":
                module = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else "X"
                reason = "could not import '%s': No module named '%s'" % (module, module)
            else:
                arg = next((kw.value for kw in node.keywords if kw.arg in ("reason", "msg")), None)
                if arg is None and node.args:
                    arg = node.args[1] if kind == "pytest.mark.skipif" and len(node.args) > 1 else \
                        (None if kind == "pytest.mark.skipif" else node.args[0])
                reason = _text(arg) if arg is not None else None
            out.append((os.path.basename(path), node.lineno, reason))
    return out


SKIPS = _skip_calls()


def test_the_scan_finds_the_suites_skips():
    reasons = [r for _f, _l, r in SKIPS]
    assert len(SKIPS) >= 40, len(SKIPS)
    assert "node is not available" in reasons


@pytest.mark.parametrize("fn,line,reason", SKIPS, ids=["%s:%d" % (f, n) for f, n, _r in SKIPS])
def test_every_skip_the_suite_can_give_is_declared(fn, line, reason):
    assert reason is not None, "%s:%d builds its skip reason in a way this scan cannot read; write it as a " \
                               "literal (placeholders allowed) so it can be checked against the budget" % (fn, line)
    assert skip_budget.classify(reason) is not None, \
        "%s:%d skips for %r, which src/skip_budget.py does not declare" % (fn, line, reason)


# ------------------------------------------------------------------ the budget itself ------
def test_classify_reads_pytests_prefix_and_rejects_the_unknown():
    assert skip_budget.classify("Skipped: node is not available") == "node"
    assert skip_budget.classify("node is not available") == "node"
    assert skip_budget.classify("node is not available on Tuesdays") is None
    assert skip_budget.classify("because the author said so") is None


#: skip reasons as they read at run time (real paths, either separator), one per declared family and form
RUNTIME_REASONS = {
    "results\\check_prior_masses_results.json not present in this checkout": "generated_output_absent",
    "results/check_outbound_transfer_sensitivity_results.json not present in this checkout": "generated_output_absent",
    "results\\check_pyd_temporal_correlation_results.json is not present in this checkout": "generated_output_absent",
    "distortion_tool.html not generated in this checkout": "generated_output_absent",
    "declared PDF not generated in this checkout": "generated_output_absent",
    "fx results not present": "generated_output_absent",
    "appendix C artefact not generated": "generated_output_absent",
    "ledger not written yet (rerun pending)": "generated_output_absent",
    "docs/current-results.md absent": "generated_output_absent",
    "the committed run report is from a dirty source tree (clean rerun pending)": "run_report_absent_or_pending",
    "report predates schema 4, the whole-tree input attestation (recorded pass pending)":
        "run_report_absent_or_pending",
    "no manuscript at D:\\Latex projects\\BAJ\\paper\\main.tex: set LLOYDS_PAPER_REPO to the paper repository, or "
    "this cross-repository check does not run": "manuscript_absent",
    "git check-attr is not available here: FileNotFoundError": "git_history_absent",
    "could not import 'pymc': No module named 'pymc'": "python_package_absent",
    "vignette1_diagnostics.recorded_tvar is gone; this test must be rewritten": "module_unimportable",
}

#: reasons that share the declared words but are not the declared forms: round 62's verification found that
#: "^.+ absent$" and bare substrings let any of these through in an ordinary run
LOOKALIKES = ("because the author said so absent", "the answer, frankly, absent",
              "whatever this is, not present in this checkout", "not present in this checkout but I checked",
              "results not present on Tuesdays", "a report predates schema 4, and more",
              "no committed run report yet, and the reason is long", "could not import 'pymc': it is Tuesday",
              "vignette1_diagnostics is gone", "anything at all not generated in this checkout",
              "the reason is docs/x.md absent", "docs/x.md absent, and more", "surely no committed run report yet",
              "prefix: no manuscript at X: set Y to the paper repository, or this cross-repository check does not run")


def test_each_declared_form_classifies_as_it_reads_at_run_time():
    for reason, ident in RUNTIME_REASONS.items():
        assert skip_budget.classify(reason) == ident, reason


def test_a_reason_that_only_shares_the_declared_words_is_undeclared():
    for reason in LOOKALIKES:
        assert skip_budget.classify(reason) is None, reason


def test_a_planted_undeclared_reason_is_flagged_and_nothing_else():
    assert skip_budget.undeclared(["node is not available", "because the author said so",
                                   "model/x.json not present in this checkout"]) == ["because the author said so"]


def test_a_recorded_run_may_carry_no_skip_at_all():
    assert skip_budget.recorded_run_problems({}) == []
    problems = skip_budget.recorded_run_problems({"node is not available": 37, "a reason nobody wrote down": 1})
    assert len(problems) == 2
    assert any("[node]" in p and "37" in p for p in problems)
    assert any("undeclared" in p for p in problems)


# ------------------------------------------------------------------ record_tests ------
def test_record_tests_refuses_to_record_or_stamp_a_run_that_skipped():
    assert record_tests.refuse_skips({}) is None
    assert record_tests.refuse_skips(None) is None
    with pytest.raises(SystemExit) as exc:
        record_tests.refuse_skips({"node is not available": 37})
    assert "node" in str(exc.value).lower()


def test_record_tests_itemises_the_skip_summary():
    text = ("SKIPPED [2] src/test_distortion_tool.py:93: node is not available\n"
            "SKIPPED [1] src/test_x.py:10: model/y.json not present in this checkout\n"
            "SKIPPED [3] src/test_distortion_tool.py:646: node is not available\n")
    assert record_tests.skip_reasons(text) == {"model/y.json not present in this checkout": 1,
                                               "node is not available": 5}


# ------------------------------------------------------------------ the conftest hook ------
def _session(tmp_path, reason):
    """A throwaway pytest session holding one test that skips for `reason`, under the repository's conftest."""
    (tmp_path / "src").mkdir()
    shutil.copy2(os.path.join(HERE, "conftest.py"), str(tmp_path / "conftest.py"))
    shutil.copy2(os.path.join(SRC, "skip_budget.py"), str(tmp_path / "src" / "skip_budget.py"))
    (tmp_path / "test_one.py").write_text(
        "import pytest\n\n\ndef test_one():\n    pytest.skip(%r)\n" % reason, encoding="utf-8")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                          cwd=str(tmp_path), capture_output=True, text=True)


def test_the_conftest_fails_a_session_with_an_undeclared_skip(tmp_path):
    r = _session(tmp_path, "because the author said so")
    assert r.returncode != 0, r.stdout[-800:]
    assert "UNDECLARED SKIP REASON" in r.stdout and "because the author said so" in r.stdout


def test_the_conftest_lets_a_declared_skip_through(tmp_path):
    """The control: the same session with a declared reason passes, so the failure above is the hook's."""
    r = _session(tmp_path, "node is not available")
    assert r.returncode == 0, r.stdout[-800:]
    assert "1 skipped" in r.stdout and "UNDECLARED" not in r.stdout
