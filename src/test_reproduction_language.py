#!/usr/bin/env python3
"""Reproduction claims must not exceed the recorded coverage.

Round 43 of the paper review found the manuscript promising "full
reproducibility" while the committed run record says the demonstrated clean run
is PARTIAL (a subset of the manifest), and this repository's own README and
reproduce.py docstring saying everything downstream "reproduces"/"is
reproducible here" without distinguishing what is RE-RUNNABLE (the whole
manifest) from what has been DEMONSTRATED (the recorded partial run).

The rule is keyed to the committed record, not to a phrase list alone: while
reproduce-run-report.json says partial, every downstream-reproduction claim in
the current-facing reproduction documents must carry the runnable-vs-
demonstrated distinction, and no document may claim full or complete
reproduction. docs/paper-pack.md's narrow "the event-group construction is
fully reproducible" (a determinism statement about one pooling rule) is out of
scope, as are the declared archives.

Run:  python -m pytest src/test_reproduction_language.py -q
"""
import io
import json
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# the current-facing documents that describe reproducing this project
REPRO_DOCS = ("README.md", "reproduce.py", "docs/data-provenance.md")

# round 48: "everything downstream is reproducible from the committed JSON" is a
# full-reproduction headline in all but name
FULL_CLAIM = re.compile(r"full(?:y)?[ -]reproduc|complete(?:ly)? reproduc|"
                        r"results can be reproduced|is reproducible from", re.I)
DOWNSTREAM_CLAIM = re.compile(
    r"everything downstream[^.!?]*(?:reproduc|re-?runnable)", re.I)
SCOPE_WORDS = re.compile(r"re-?runnable|partial|demonstrat|coverage|"
                         r"not been run end to end", re.I)


def _read(rel):
    return io.open(os.path.join(HERE, rel), encoding="utf-8").read()


def _record():
    return json.load(io.open(os.path.join(HERE, "reproduce-run-report.json"),
                             encoding="utf-8"))


def unscoped_reproduction_claims(text):
    """Sentences claiming full or undistinguished downstream reproduction."""
    flat = " ".join(text.split())
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", flat):
        if FULL_CLAIM.search(sent):
            out.append(sent.strip())
        elif DOWNSTREAM_CLAIM.search(sent) and not SCOPE_WORDS.search(sent):
            out.append(sent.strip())
    return out


def test_the_committed_record_is_partial_and_says_so():
    rec = _record()
    assert rec["partial"] is True
    assert len(rec["scripts"]) < rec["manifest_size"]


@pytest.mark.parametrize("rel", REPRO_DOCS)
def test_no_reproduction_claim_exceeds_the_record(rel):
    assert unscoped_reproduction_claims(_read(rel)) == []


ROUND43_DEFECTS = (
    # reproduce.py docstring, before the fix
    "Everything downstream of that file is reproducible here.",
    # README, before the fix
    "its output is committed as `model/exposure_results.json` and everything "
    "downstream of that file reproduces from this checkout.",
    # the manuscript footnote, before the fix
    "Public filing also lets us deposit the extraction and analysis code for "
    "full reproducibility, with no need to mask commercially sensitive figures.",
)


@pytest.mark.parametrize("bad", ROUND43_DEFECTS)
def test_helper_fires_on_the_round43_wordings(bad):
    assert unscoped_reproduction_claims(bad), bad


def test_helper_accepts_the_scoped_wordings():
    good = ("Everything downstream of that file is re-runnable from this "
            "checkout through the manifest; what has been demonstrated is the "
            "recorded partial clean run (--verify prints its exact coverage).")
    assert unscoped_reproduction_claims(good) == []


def test_the_round48_provenance_headline_fires():
    """docs/data-provenance.md said everything downstream is reproducible from the
    committed JSON, with no scope; the corrected sentence carries it."""
    bad = ("The raw PDFs are deliberately not committed; everything downstream is "
           "reproducible from the committed JSON.")
    assert unscoped_reproduction_claims(bad)
    good = ("everything downstream is re-runnable from the committed JSON, and what "
            "has been demonstrated is the recorded partial clean run.")
    assert unscoped_reproduction_claims(good) == []
