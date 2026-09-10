"""Round 55 (D03, D05, D06, D13): the public documents' generated blocks agree with the
records they are written from, and a stage that does not add up cannot be printed.

Run:  python -m pytest src/test_public_documents.py -q
"""
import io
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_current_results as bcr  # noqa: E402


def _read(*parts):
    return io.open(os.path.join(ROOT, *parts), encoding="utf-8").read()


def _json(*parts):
    return json.load(io.open(os.path.join(ROOT, *parts), encoding="utf-8"))


def test_waterfall_lines_add_up_and_refuse_a_broken_flow():
    ex = _json("model", "exposure_results.json")
    lines = bcr.waterfall_lines(ex)
    stage = next(l for l in lines if "excluded" in l and "=" in l)
    nums = [int(x) for x in re.findall(r"\d+", stage)]
    assert nums[0] - sum(nums[1:-1]) == nums[-1]
    bad = json.loads(json.dumps(ex))
    bad["disposition_flow"]["pre_corpus"]["skipped"] += 1
    with pytest.raises(SystemExit):
        bcr.waterfall_lines(bad)


def test_provenance_note_carries_the_generated_waterfall():
    ex = _json("model", "exposure_results.json")
    doc = _read("docs", "data-provenance.md")
    for line in bcr.waterfall_lines(ex):
        assert line in doc, "docs/data-provenance.md is stale: run src/build_current_results.py"


def test_referee_tail_block_lists_the_current_exceedances():
    ts = _json("results", "check_tail_support_syndicate_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 1. "):doc.index("## 2. ")]
    for stem, _ in ts["a_exceedance_sets"]["VaR995"]["ranked_exceedances"]:
        assert stem in sec
    assert ("%d distinct syndicates" % ts["a_exceedance_sets"]["VaR99"]["n_distinct_syndicates"]) in sec
    assert ("ICC = %.3f" % ts["b_icc"]["icc"]) in sec


def test_referee_currency_block_prints_tau_m_not_the_floor():
    cu = _json("results", "check_currency_entanglement_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 2. "):doc.index("## 3. ")]
    assert ("| Sterling (converted) | %.4f | %.3f |" % (cu["a_sterling"]["tau_m"], cu["a_sterling"]["k"])) in sec
    assert ("| Nominal (as-reported) | %.4f | %.3f |" % (cu["a_nominal"]["tau_m"], cu["a_nominal"]["k"])) in sec
    assert ("%+.2f" % cu["corr_mt_diff_vs_usd_share"]) in sec


def test_referee_size_only_block_matches_its_record():
    g0 = _json("results", "check_gamma0_vignette_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 5. "):doc.index("## 6. ")]
    assert ("%.3f vs %.3f" % (g0["full_operator"]["centre"]["V1_v995"],
                              g0["size_only_gamma0"]["centre"]["V1_v995"])) in sec


def test_orphan_stress_is_compared_within_its_population():
    src = _read("src", "generate_data_audit.py")
    assert "f_base = by_c[c_max], by_c[c_min]" in src or "f_orph, f_base = by_c[c_max], by_c[c_min]" in src
    assert "within the augmented sample" in src


def test_vignette_snippets_attach_components_to_their_own_contrast():
    src = _read("src", "run_analysis.py")
    assert "old-to-new profile change at VaR99.5" in src
    assert "raw-market-to-target change at VaR99.5" in src
    assert "will not match" not in src
    for vid in ("vignette-1", "vignette-2"):
        p = os.path.join(ROOT, "vignettes", vid, "summary_snippet.md")
        if not os.path.exists(p):
            pytest.skip("vignette outputs not generated")
        txt = io.open(p, encoding="utf-8").read()
        assert "will not match" not in txt, "%s is stale: rerun src/run_analysis.py" % vid
        if vid == "vignette-2":
            assert "old-to-new profile change" in txt


STALE = re.compile(r"n ?= ?790\b|790 syndicate|re-established|noise, not signal|fully matched", re.I)


def test_no_executable_description_carries_a_withdrawn_wording():
    """Round 55 (D11, B07, B08): producers' docstrings, comments and labels do not
    carry the superseded sample size or a wording the manuscript withdrew."""
    hits = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith(".py") or f.startswith("test_"):
            continue
        for i, line in enumerate(io.open(os.path.join(HERE, f), encoding="utf-8"), 1):
            if STALE.search(line):
                hits.append("%s:%d: %s" % (f, i, line.strip()[:90]))
    assert not hits, hits


def _run_report():
    q = os.path.join(ROOT, "reproduce-run-report.json")
    if not os.path.exists(q):
        pytest.skip("no manifest run report in this tree")
    return json.load(io.open(q, encoding="utf-8"))


def test_the_readme_states_the_tree_state_the_run_report_records():
    """Review B2-03: the sentence's date and its tree-state clause come from the same
    record, so the README cannot claim a clean tree for a dirty run."""
    rep = _run_report()
    text = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    m = re.search(r"was made on\s+\d{1,2} \w+ \d{4} on a source tree([^;.]*)", text)
    assert m, "the README no longer carries the manifest-run sentence"
    said_clean = "no uncommitted change" in m.group(1)
    assert said_clean != bool(rep.get("worktree_dirty_src")), m.group(0)[:160]
    assert rep["finished_utc"][:4] in text


def test_the_provenance_correction_block_is_the_disposition_flow():
    """Review B2-02: the counts on both sides of the correction are read from the
    records, not typed, so the table must equal what the generator produces now."""
    doc = os.path.join(ROOT, "docs", "data-provenance.md")
    if not os.path.exists(doc):
        pytest.skip("no provenance document in this tree")
    text = io.open(doc, encoding="utf-8").read()
    if bcr.CORRECTION_START not in text:
        pytest.skip("no correction block in this tree")
    ex = json.load(io.open(os.path.join(ROOT, "model", "exposure_results.json"),
                           encoding="utf-8"))
    block = text[text.index(bcr.CORRECTION_START):text.index(bcr.CORRECTION_END)]
    want = "\n".join(bcr.correction_lines(ex))
    assert want in block, "docs/data-provenance.md: run src/build_current_results.py"
    now = ex["disposition_flow"]
    assert "| **%d** |" % now["working_sample"] in block
    assert "| %d |" % now["corpus"] in block


def test_the_provenance_document_points_at_the_change_log():
    doc = os.path.join(ROOT, "docs", "data-provenance.md")
    if not os.path.exists(doc):
        pytest.skip("no provenance document in this tree")
    text = io.open(doc, encoding="utf-8").read()
    assert "extraction-changelog.md" in text
    audit = os.path.join(ROOT, "docs", "appendix-data-audit.md")
    if os.path.exists(audit):
        assert "extraction-changelog.md" in io.open(audit, encoding="utf-8").read()
