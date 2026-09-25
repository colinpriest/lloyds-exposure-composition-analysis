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


STALE = re.compile(r"n ?= ?790\b|790 syndicate|re-established|noise, not signal|fully matched"
                   # the referee note's two categorical conclusions (frozen review of 21 September 2026, D02)
                   r"|exists to capture|the only serial feature", re.I)


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


# ---------------------------------------------------------------------------
# R213 refit 3 (A9e): the provenance note's typed clauses, current-results' sensitivity sentences and its open
# questions are written from their records, and a record that no longer supports the words refuses to print them.

def test_the_corpus_and_sample_rows_are_counted_not_typed():
    ex = _json("model", "exposure_results.json")
    rows = bcr.population_rows(ex)
    cv = _json("results", "check_cv_clustered_se_results.json")
    assert rows[1] == "Modelling sample: %d syndicate-years / %d syndicates" % (cv["n"], cv["n_syndicates"])
    assert rows[0].startswith("Corpus:          %d syndicate-years / " % ex["disposition_flow"]["corpus"])
    doc = _read("docs", "data-provenance.md")
    for row in rows:
        assert row in doc, "docs/data-provenance.md is stale: run src/build_current_results.py"
    bad = json.loads(json.dumps(ex))
    bad["observations"] = bad["observations"][:-1]
    with pytest.raises(SystemExit):
        bcr.population_rows(bad)


def test_the_provenance_clauses_are_what_the_records_give():
    ex = _json("model", "exposure_results.json")
    doc = _read("docs", "data-provenance.md")
    assert bcr.provenance_clauses(doc, ex) == doc, "docs/data-provenance.md is stale: run src/build_current_results.py"


def test_a_planted_stale_clause_is_rewritten():
    """Mutation check on the test above: an older extraction's orphan count, refit 1's currency move and the old
    failure-rate clause are each rewritten from the records, not kept."""
    ex = _json("model", "exposure_results.json")
    doc = _read("docs", "data-provenance.md")
    ms = _json("results", "check_missingness_sensitivity_results.json")
    orphans = "**%d orphan filings from %d syndicates" % (ms["n_orphan_filings"], ms["n_orphan_syndicates"])
    fx_move = re.search(r"VaR\$_\{99\.5\}\$ moves [0-9.]+%", doc).group(0)
    clause = re.search(r"failures cluster in the oldest, scanned vintage \([^)]*\)", doc).group(0)
    for old, stale in ((orphans, "**37 orphan filings from 22 syndicates"),
                       (fx_move, "VaR$_{99.5}$ moves 5.0%"),
                       (clause, "failures cluster in older, scanned vintages (2014: 29%; 2018:\n18%; others 7\u201312%)")):
        assert old in doc
        planted = doc.replace(old, stale)
        assert planted != doc
        assert bcr.provenance_clauses(planted, ex) == doc, stale


def test_a_record_that_no_longer_supports_the_words_refuses_them():
    ex = _json("model", "exposure_results.json")
    doc = _read("docs", "data-provenance.md")
    recs = bcr.provenance_records()

    def refuses(mutate):
        bad = json.loads(json.dumps(recs))
        mutate(bad)
        with pytest.raises(SystemExit):
            bcr.provenance_clauses(doc, ex, bad)

    refuses(lambda r: r["missingness_check_results.json"]["D_outcome_given_size"].update(abs_S_p=0.01))
    refuses(lambda r: r["missingness_check_results.json"]["C_failure_by_year"].update({"2024": [90, 95]}))
    refuses(lambda r: r["check_missingness_sensitivity_results.json"].update(n_orphan_filings=99))
    refuses(lambda r: r["check_syndicate_random_effect_results.json"]["fits"]["random_intercept"]["sd_undiv"]
            .update(mean=0.5))
    refuses(lambda r: r["fx_sensitivity_results.json"]["fits"]["nominal (as-reported)"]["conditional_fit_summaries"]
            .update(P_nu_ritc_lt_nu_clean=0.99))


def test_the_sensitivity_sentences_follow_the_record():
    ms = _json("results", "check_missingness_sensitivity_results.json")
    m0 = _json("model", "dispersion_calibration_ritc.json")
    lines = bcr.missingness_lines()
    sentences = bcr.sensitivity_sentences(ms, m0)
    for text in (" ".join(lines), " ".join(sentences)):
        assert "essentially unchanged" not in text
        assert "%.3f" % ms["fits"]["ipw_selection_weighted"]["k"]["mean"] in text
    doc = _read("docs", "current-results.md")
    for s in sentences:
        assert s in doc, "docs/current-results.md is stale: run src/build_current_results.py"
    prov = _read("docs", "data-provenance.md")
    for line in lines:
        assert line in prov, "docs/data-provenance.md is stale: run src/build_current_results.py"
    bad = json.loads(json.dumps(ms))
    cs = sorted(bad["worst_case"]["by_c"], key=float)
    bad["worst_case"]["by_c"][cs[-1]]["nu_clean"]["mean"] = bad["worst_case"]["by_c"][cs[0]]["nu_clean"]["mean"]
    with pytest.raises(SystemExit):
        bcr.sensitivity_sentences(bad, m0)


def test_the_open_questions_follow_the_records():
    doc = _read("docs", "current-results.md")
    khalf = _json("results", "check_k_half_sensitivity_results.json")
    comp = _json("results", "compose_robust_results.json")
    lt = _json("results", "check_long_tail_share_results.json")
    assert "- " + bcr.exponent_question(khalf) in doc, "docs/current-results.md is stale"
    assert "- " + bcr.long_tail_question(comp, lt) in doc, "docs/current-results.md is stale"
    assert "is suggestive, not established" not in doc
    assert "unconstrained refit" not in doc
    bad = json.loads(json.dumps(khalf))
    bad["k_half_fit"]["diagnostics"]["divergences"] = 3
    with pytest.raises(SystemExit):
        bcr.exponent_question(bad)
    # the refusals and the orientation belong to the branch where the slope is resolved positive: they are exercised
    # on a copy whose slope is, whatever the current record's (R221: +0.22 [-0.08, +0.51], not resolved)
    pos = json.loads(json.dumps(comp))
    pos["beta_LT"]["hdi"] = [0.05, 0.5]
    bad = json.loads(json.dumps(lt))
    bad["by_syndicate"]["long_tail_minus_composition"]["bb_2.5"] = 0.5
    with pytest.raises(SystemExit):
        bcr.long_tail_question(pos, bad)
    bad = json.loads(json.dumps(lt))
    bad["by_syndicate"]["long_tail_minus_composition"]["delta_ELPD"] = 0.5
    with pytest.raises(SystemExit):
        bcr.long_tail_question(pos, bad)
    # Supplement S4's and Table 18's orientation: the model without the share against the model with it
    r = lt["by_syndicate"]["long_tail_minus_composition"]
    assert ("scores $%+.1f$ higher" % -r["delta_ELPD"]) in bcr.long_tail_question(pos, lt)
    lo, hi = comp["beta_LT"]["hdi"]
    if lo <= 0 <= hi:
        assert "- the long-tail share slope, not distinguishable from zero" in doc
    else:
        assert ("$P = %.2f$ that the model without it predicts better" % (1.0 - r["P_first_better"])) in doc
    flat = json.loads(json.dumps(comp))
    flat["beta_LT"]["hdi"] = [-0.1, 0.5]
    assert "not distinguishable from zero" in bcr.long_tail_question(flat, lt)


def test_the_referee_record_is_generated_from_its_records():
    doc = _read("docs", "referee-checks.md")
    assert bcr.referee_text(doc) == doc, "docs/referee-checks.md is stale: run src/build_current_results.py"
    assert "moved by a few thousandths" not in doc
    assert "n=678" not in doc.split("## Bookkeeping")[0], "a section still names the round-54 sample"


def test_a_planted_stale_referee_value_is_rewritten():
    """Mutation check on the test above: refit 1's by-syndicate contrast and an earlier fit's maturity table are both
    rewritten from the records, not kept."""
    doc = _read("docs", "referee-checks.md")
    recs = bcr.referee_records()
    pcv = recs["pcv"]
    now = "ΔELPD(M1 − M2) = **%+.2f, SE %.2f**" % (pcv["delta_ELPD_M1_minus_M2"], pcv["delta_SE"])
    assert now in doc
    planted = doc.replace(now, "ΔELPD(M1 − M2) = **+2.05, SE 2.09**")
    assert planted != doc and bcr.referee_text(planted, recs) == doc
    sec4 = doc[doc.index("## 4. "):doc.index("## 5. ")]
    planted = doc.replace(sec4, "## 4. Size–maturity partial confound\n\n| Base (two-regime) | **0.614** [0.526, 0.691] | — |\n\n")
    assert planted != doc and bcr.referee_text(planted, recs) == doc


def test_a_referee_record_that_no_longer_supports_its_decision_refuses():
    doc = _read("docs", "referee-checks.md")
    recs = bcr.referee_records()

    def refuses(mutate):
        bad = json.loads(json.dumps(recs))
        mutate(bad)
        with pytest.raises(SystemExit):
            bcr.referee_text(doc, bad)

    refuses(lambda r: r["pcv"].update(delta_ELPD_M1_minus_M2=10.0))
    refuses(lambda r: r["sm"]["k_plus_age"].update(k=0.70))
    refuses(lambda r: r["mz"]["b_credibly_positive"].update(share_credibly_positive=0.40))
    refuses(lambda r: r["het"]["psi_s"].update({"hdi_2.5": 0.1}))
    refuses(lambda r: r["sca"]["b_redundancy"].update(vif_logR_given_line_and_year=3.0))
    # section 9's guards after the frozen review of 25 September 2026 (M01, D01): they are on the
    # test's DIRECTION and on the evidence the section quotes, not on the finding coming out one way
    refuses(lambda r: r["tc"]["a_lag1_demeaned"]["permutation_null"].update(mean=0.1))
    refuses(lambda r: r["tc"]["a_lag1_demeaned"].pop("p_upper_positive_persistence"))
    refuses(lambda r: r["tc"]["f_conditional_on_adopted_model"].update(tests={}))
    refuses(lambda r: r["tc"]["e_demeaning_benchmark"]["counterexample_to_excluding_dynamics"]
            .update(reading=-0.5))
    refuses(lambda r: r["tc"]["e_demeaning_benchmark"]["counterexample_to_excluding_dynamics"]
            .update(variance_for_short_histories=None))
    refuses(lambda r: r["tc"]["e_demeaning_benchmark"]["heterogeneous_variance_reading"]
            .update(rho_reading_the_observed_demeaned=None))
    refuses(lambda r: r["tc"]["g_null_calibration"]["rejection_shares"]["common_year_component_only"]
            ["spearman"].update(per_year_adjusted=0.99))
    refuses(lambda r: r["tc"]["g_null_calibration"]["rejection_shares"]["within_syndicate_ar1"]
            ["spearman"].update(per_year_adjusted=0.1))
    refuses(lambda r: r["ss"]["design_a_group_calibration"]["k"].update(interpretable=False))
    refuses(lambda r: r["ss"]["design_b_adjacency"]["sd_ratio_thinned_over_random"].update(k=None))
    refuses(lambda r: r["vu"]["robustness"]["V1_adj_var995_CI_by_clustering"]
            .update(bayesian_bootstrap_primary={}))
    refuses(lambda r: r["corr"].update(k_floor=-0.1))
    refuses(lambda r: r["register"]["2015_2014"].update(basis="gross"))


def test_the_audit_prints_the_loaders_weight_floor_and_severity_cap():
    """Review D (F8): B.4 typed the floor and the cap; both are now read from the loader's record."""
    cfg = _json("model", "exposure_results.json")["analysis_config"]
    floor, cap = float(cfg["lob_weight_floor"]), float(cfg["lob_severity_cap"])
    audit = _read("docs", "appendix-data-audit.md")
    assert "floored at **%.2f (%.0f%%)**" % (floor, 100 * floor) in audit
    assert "whose value is ±%g in severity units — that is ±%.0f%% of opening" % (cap, 100 * cap) in audit
    src = _read("src", "generate_data_audit.py")
    assert "WEIGHT_FLOOR = " not in src and "±500%" not in src and "(1%)" not in src
    loader = _read("src", "run_analysis.py")
    assert 'apply_weight_floor(weights, floor=ANALYSIS_CONFIG["lob_weight_floor"])' in loader
    assert 'cap = ANALYSIS_CONFIG["lob_severity_cap"]' in loader
    assert "lob_severity[l] > 5.0" not in loader and "lob_severity[l] < -5.0" not in loader
