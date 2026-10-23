#!/usr/bin/env python3
"""Every Python file a source names exists, and every test class it names is in that file.

adopted_model.sigma_numeric's docstring said its agreement with the symbolic scale was held by a test file
that did not exist (review of 29 September 2026, A-3c). A reader who follows a citation to a missing file
learns that the claim was never checked. So this scans the analysis sources (src/*.py other than the
tests, and the repository's own top-level scripts) for every NAME.py they mention, in code, comments or
docstrings, and requires each to be a file of this repository -- or one of the few named below that belong
to another repository, or to this repository's results folders rather than src/, with where that is. A cited "file (TestClass)" must also define that class.

Run:  python -m pytest src/test_docstring_references.py -q
"""
import io
import os
import re

import pytest

SRC = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SRC)

#: files named in the sources that live outside this repository, and where
ELSEWHERE = {
    "test_gemini.py": "the extraction repository, D:\\dev\\lloyds_reserve_stress_testing "
                      "(github.com/colinpriest/lloyds-reserve-stress-testing)",
    "table_extraction.py": "the extraction repository, D:\\dev\\lloyds_reserve_stress_testing "
                           "(github.com/colinpriest/lloyds-reserve-stress-testing)",
    # a script of THIS repository that lives in the round-5 reading folder rather than in src/ or the top level (cited
    # by src/build_restated_base_excluded.py and src/build_fx_untranslated_excluded.py since the round-5 adjudication of
    # 22 to 23 October 2026); test_the_in_repository_entries_exist_where_they_are_declared checks the path
    "rebase_screen.py": "this repository, results/extraction_error_rate/mature-cohort/round5/screen/rebase_screen.py",
}

NAME = re.compile(r"(?<![\w/.\\-])(?:src/)?([A-Za-z_][A-Za-z0-9_]*\.py)\b")
CLASS_REF = re.compile(r"(test_[A-Za-z0-9_]+\.py)\s*\((Test[A-Za-z0-9_]+)\)")


def _sources():
    files = [os.path.join(SRC, f) for f in sorted(os.listdir(SRC)) if f.endswith(".py") and not f.startswith("test_")]
    files += [os.path.join(HERE, f) for f in sorted(os.listdir(HERE)) if f.endswith(".py")]
    return files


def _text(path):
    # LaTeX-escaped names (check\_ritc\_scale\_term.py) are still names
    with io.open(path, encoding="utf-8") as _fh:
        return _fh.read().replace("\\\\_", "_").replace("\\_", "_")


def _references():
    out = []
    for path in _sources():
        for i, line in enumerate(_text(path).splitlines(), 1):
            for m in NAME.finditer(line):
                out.append((os.path.relpath(path, HERE).replace("\\", "/"), i, m.group(1)))
    return out


REFS = _references()
KNOWN = set(os.listdir(SRC)) | set(os.listdir(HERE))


def test_the_scan_reads_the_sources():
    assert len(REFS) > 300, len(REFS)
    assert ("src/adopted_model.py", "test_serial_dependence_claims.py") in {(f, n) for f, _l, n in REFS}


def test_every_named_python_file_exists():
    missing = sorted({"%s:%d names %s" % (f, line, n) for f, line, n in REFS
                      if n not in KNOWN and n not in ELSEWHERE})
    assert not missing, "sources name files that are in neither this repository nor ELSEWHERE:\n  " + \
        "\n  ".join(missing)


def test_the_files_declared_elsewhere_are_really_not_here():
    for name in ELSEWHERE:
        assert name not in KNOWN, "%s is in this repository now: take it out of ELSEWHERE" % name


def test_the_in_repository_entries_exist_where_they_are_declared():
    """An ELSEWHERE entry that says 'this repository, <path>' names a file that is there, at that path."""
    here = {n: d for n, d in ELSEWHERE.items() if d.startswith("this repository, ")}
    assert "rebase_screen.py" in here
    for name, d in here.items():
        path = d[len("this repository, "):]
        assert path.endswith("/" + name), (name, path)
        assert os.path.isfile(os.path.join(HERE, *path.split("/"))), "%s is not at %s" % (name, path)


def test_every_named_test_class_is_in_its_file():
    refs = []
    for path in _sources():
        text = " ".join(_text(path).split())
        refs += [(os.path.basename(path), f, c) for f, c in CLASS_REF.findall(text)]
    assert ("adopted_model.py", "test_serial_dependence_claims.py", "TestTheNumericScaleIsTheModelsOwn") in refs
    for src, f, c in refs:
        with io.open(os.path.join(SRC, f), encoding="utf-8") as _fh:
            body = _fh.read()
        assert re.search(r"^class %s\b" % re.escape(c), body, re.M), "%s names %s (%s), which is not there" % (src, f, c)


@pytest.mark.parametrize("name", ["test_operator_binding.py", "test_figure_layout.py", "test_docstring_references.py",
                                  "test_error_rate_propagation.py", "test_skip_budget.py"])
def test_the_tests_this_review_cites_exist(name):
    assert os.path.exists(os.path.join(SRC, name))
