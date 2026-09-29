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


def test_referee_tail_block_lists_the_current_at_or_beyond_sets():
    ts = _json("results", "check_tail_support_syndicate_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 1. "):doc.index("## 2. ")]
    for stem, _ in ts["a_at_or_beyond_sets"]["VaR995"]["ranked_at_or_beyond"]:
        assert stem in sec
    assert ("%d distinct syndicates" % ts["a_at_or_beyond_sets"]["VaR99"]["n_distinct_syndicates"]) in sec
    assert ("ICC = %.3f" % ts["b_icc"]["icc"]) in sec
    assert "at or beyond" in sec
    assert "exceedance" not in sec.lower()


def test_referee_currency_block_prints_tau_m_not_the_floor():
    cu = _json("results", "check_currency_entanglement_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 2. "):doc.index("## 3. ")]
    assert ("| Sterling (converted) | %.4f | %.3f |" % (cu["a_sterling"]["tau_m"], cu["a_sterling"]["k"])) in sec
    assert ("| Nominal (as-reported) | %.4f | %.3f |" % (cu["a_nominal"]["tau_m"], cu["a_nominal"]["k"])) in sec
    assert ("%+.2f" % cu["corr_mt_diff_vs_usd_share"]) in sec


def test_referee_size_only_block_matches_its_record():
    """DEFERRED-TO-REFIT: the committed record and section 5 are rewritten, keyed by operator, by the recorded pass."""
    g0 = _json("results", "check_gamma0_vignette_results.json")
    doc = _read("docs", "referee-checks.md")
    sec = " ".join(doc[doc.index("## 5. "):doc.index("## 6. ")].split())
    assert g0["headline_operator"] == "size_only"
    assert ("moves Vignette 1's VaR99.5 from %.3f to %.3f" % (g0["size_only"]["centre"]["V1_v995"],
                                                              g0["overlay"]["centre"]["V1_v995"])) in sec
    assert "Every headline vignette figure is the size-only operator's" in sec


def _g0(head="size_only"):
    """A two-operator record in check_gamma0_vignette's shape, with distinct numbers in every cell."""
    def block(mode, base):
        return {"operator": mode, "operator_role": "headline" if mode == "size_only" else "sensitivity",
                "centre": {"V1_v99": base, "V1_v995": base + 0.03, "V2_d995": base / 10},
                "intervals": {k: {"lo": v - 0.01, "hi": v + 0.01}
                              for k, v in (("V1_v99", base), ("V1_v995", base + 0.03), ("V2_d995", base / 10))}}
    so, ov = block("size_only", 0.271), block("overlay", 0.232)
    return {"headline_operator": head, "size_only": so, "overlay": ov, "gamma_posterior_mean": 0.4775,
            "overlay_relative_to_headline": {k: ov["centre"][k] / so["centre"][k] - 1.0
                                             for k in ("V1_v99", "V1_v995", "V2_d995")}}


def test_the_operator_section_is_written_headline_first_from_its_record():
    text = " ".join(bcr.referee_section_5(_g0()).split())
    assert "| V1 VaR99.5 | 0.301 [0.291, 0.311] | 0.262 [0.252, 0.272] |" in text, \
        "the size-only (headline) column must come first"
    assert "moves Vignette 1's VaR99.5 from 0.301 to 0.262 (-13.0%)" in text
    assert "Overlay ($\\gamma\\approx0.48$), sensitivity" in text


def test_the_operator_section_is_found_again_after_it_is_rewritten():
    """A scratch regeneration showed the second build could not find the section the first had written: its
    heading had changed and the pattern had not. The pattern must find the section under either heading."""
    written = "## 4. x\n\n" + bcr.referee_section_5(_g0()) + "## 6. Mean-zero boundary\n"
    assert len(re.findall(bcr.SECTION_5, written, re.S)) == 1
    assert len(re.findall(bcr.SECTION_5, _read("docs", "referee-checks.md"), re.S)) == 1


def test_the_operator_section_refuses_a_record_that_does_not_name_its_operators():
    with pytest.raises(SystemExit):
        bcr.referee_section_5(_g0(head="overlay"))
    bad = _g0()
    bad["overlay"]["operator"] = "size_only"
    with pytest.raises(SystemExit):
        bcr.referee_section_5(bad)


def test_the_count_clauses_are_the_records_and_a_stale_count_is_rewritten():
    """Review of 29 September 2026 (A-3a): three clauses had no pattern, so a refit left 794, 852 and 685 standing
    beside 795, 853 and 686. Checked on the regenerated text, so this does not wait for the recorded pass."""
    ex = _json("model", "exposure_results.json")
    mc = _json("results", "missingness_check_results.json")
    disp = mc["disposition_counts"]
    fresh = bcr.provenance_clauses(_read("docs", "data-provenance.md"), ex)
    flat = " ".join(fresh.split())
    for clause in (
            "The supported disclosure-defined target is therefore %d records." % mc["n_supported_target_population"],
            "If all %d unresolved filings were economically eligible, the broader potential target would be %d;"
            % (disp["eligibility_unresolved"], mc["n_broader_potential_target_if_all_unresolved_eligible"]),
            "The selection response is membership in the %d-record model sample." % mc["n_model_sample"],
            "a stress for the %d known eligible unavailable outcomes, and a separate broader-potential-target "
            "stress that assumes all %d unresolved cases eligible"
            % (mc["n_eligible_outcome_unavailable"], mc["n_eligibility_unresolved"])):
        assert clause in flat, clause
    for pattern in (r"(target is therefore )[0-9,]+", r"(broader potential\s+target would be )[0-9,]+",
                    r"(membership in the )[0-9,]+(-record model sample)", r"(a stress for the )[0-9,]+",
                    r"(If all )[0-9,]+( unresolved filings)"):
        planted = re.sub(pattern, lambda m: m.group(1) + "7" + (m.group(2) if m.lastindex == 2 else ""),
                         fresh, count=1)
        assert planted != fresh, pattern
        assert bcr.provenance_clauses(planted, ex) == fresh, pattern


def test_referee_vignette2_direction_is_conditional():
    sign = _json("results", "check_vignette2_sign_results.json")
    case = sign["sign_cases"]["negative_old_quantile_actual_pool"]
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("Vignette 2 is"):doc.index("---", doc.index("Vignette 2 is"))]
    assert "conditional on a positive old quantile" in sec
    assert "syndicate 318" in sec
    assert "universal reweighting identity" in sec
    assert case["change"] < 0


def test_eligible_outcome_stress_excludes_structural_records():
    src = _read("src", "generate_data_audit.py")
    assert 'by_c = miss["eligible_outcome_stress"]["by_c"]' in src
    assert "Structural stubs and scientific exclusions are not treated as missing" in src
    assert "within the augmented sample" in src


def test_data_audit_separates_operational_and_inferential_states():
    src = _read("src", "generate_data_audit.py")
    doc = _read("docs", "appendix-data-audit.md")
    assert "inferential_disposition_ledger.csv" in src and "inferential_disposition_ledger.csv" in doc
    assert "economic eligibility, disclosure availability and extraction status" in doc
    assert "supported disclosure-defined target" in doc
    assert "broader potential target" in doc
    assert "0.15-capped IPW refit" in doc
    assert "blank/failed OCR" not in src and "blank/failed OCR" not in doc
    assert "more volatile books more volatile" not in src and "more volatile books more volatile" not in doc


def test_referee_collinearity_diagnostics_do_not_claim_identification():
    src = _read("src", "build_current_results.py")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 8. "):doc.index("## 9. ")]
    for text in (src, sec):
        assert "separately identified" not in text
        assert "posterior-separable" not in text
    assert "do not establish separate identification or precision" in sec
    assert "nor that concentration improves prediction" in sec


def test_referee_serial_calibration_states_its_monte_carlo_limit():
    src = _read("src", "build_current_results.py")
    doc = _read("docs", "referee-checks.md")
    sec = doc[doc.index("## 9. "):doc.index("## Bookkeeping")]
    for text in (src, sec):
        assert "correctly sized test" not in text
    # the count is the calibration record's, not typed (it was 1/20 until round 62's records moved it to 0/20)
    tc = _json("results", "check_pyd_temporal_correlation_results.json")["g_null_calibration"]
    size = tc["rejection_counts"]["common_year_component_only"]["spearman"]["per_year_adjusted"]
    assert "**%d/%d rejections**" % (size["rejections"], tc["panels_per_design"]) in sec
    assert "far too few to establish" in sec
    assert "year-adjusted test" in sec


def test_operator_tool_names_the_current_paper_and_section():
    title = "Portfolio-aware scenario transfer of reserve movements: evidence from Lloyd's syndicates"
    for rel in ("assets/_distortion_tool_template.html", "distortion_tool.html"):
        text = _read(*rel.split("/"))
        assert title in text
        assert "Section&nbsp;3.5" in text
        assert "Section&nbsp;4" not in text
        assert "Prior-Year Reserve Movements" not in text


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
    """Mutation check: stale target size, selection median and currency move are rewritten."""
    ex = _json("model", "exposure_results.json")
    doc = _read("docs", "data-provenance.md")
    mc = _json("results", "missingness_check_results.json")
    target = "%d-record supported disclosure-defined target" % mc["n_supported_target_population"]
    median = "median size £%.1fm" % mc["model_sample_selection_by_size"]["median_size_included"]
    fx_move = re.search(r"VaR\$_\{99\.5\}\$ moves [0-9.]+%", doc).group(0)
    for old, stale in ((target, "999-record supported disclosure-defined target"),
                       (median, "median size £999.9m"),
                       (fx_move, "VaR$_{99.5}$ moves 5.0%")):
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

    refuses(lambda r: r["missingness_check_results.json"]["disposition_counts"].update(working_sample=684))
    refuses(lambda r: r["fx_sensitivity_results.json"]["fits"]["nominal (as-reported)"]["conditional_fit_summaries"]
            .update(P_nu_ritc_lt_nu_clean=0.99))


# Round 62: the rescan after extraction d9f2bdee settled the last undetermined corpus filings. The clause's words
# for some ("The other N are in the corpus: scanned filings ... both extraction models read as GBP") would have
# been printed with N = 0; with none, the clause says so, and each form is refused where the record calls for the
# other. Synthetic records, so these do not wait for a pass.
_SCAN = {"counts": {"GBP": 4, "USD": 2, "UNDETERMINED": 2}, "n_reports": 8, "undetermined": ["9_2014", "8_2015"],
         "non_gbp_usd": []}
_OBS = [{"syndicate": 1, "year": 2020, "report_currency": "GBP"},
        {"syndicate": 2, "year": 2020, "report_currency": "USD"},
        {"syndicate": 3, "year": 2021, "report_currency": "GBP"}]
_NONE_FORM = ("Corpus currencies (1,065 filings): **743 GBP / 280 USD / 42 undetermined**. None of them is in the\n"
              "929-observation dataset: they are no-model files that never enter the analysis. Other words.\n"
              "The 929-observation dataset is **682 GBP / 243 USD (26%) / 4 undetermined**. More words.")
_SOME_FORM = ("Corpus currencies (1,065 filings): **743 GBP / 280 USD / 42 undetermined**. 38 of the undetermined\n"
              "are skipped no-model files that never enter the analysis. The other 4 are in the 929-observation\n"
              "dataset: other words. The 929-observation dataset is **682 GBP / 243 USD (26%) / 4 undetermined**.")


def test_the_currency_clause_says_none_when_no_corpus_filing_is_undetermined():
    out = bcr.currency_clauses(_NONE_FORM, _SCAN, _OBS, 3)
    assert out == ("Corpus currencies (8 filings): **4 GBP / 2 USD / 2 undetermined**. None of them is in the\n"
                   "3-observation dataset: they are no-model files that never enter the analysis. Other words.\n"
                   "The 3-observation dataset is **2 GBP / 1 USD (33%) / 0 undetermined**. More words.")
    assert bcr.currency_clauses(out, _SCAN, _OBS, 3) == out


def test_the_currency_clause_counts_the_undetermined_corpus_filings_when_there_are_some():
    obs = _OBS + [{"syndicate": 9, "year": 2014, "report_currency": "UNDETERMINED"}]
    out = bcr.currency_clauses(_SOME_FORM, _SCAN, obs, 4)
    assert out == ("Corpus currencies (8 filings): **4 GBP / 2 USD / 2 undetermined**. 1 of the undetermined\n"
                   "are skipped no-model files that never enter the analysis. The other 1 are in the 4-observation\n"
                   "dataset: other words. The 4-observation dataset is **2 GBP / 1 USD (25%) / 1 undetermined**.")


def test_each_currency_clause_form_is_refused_where_the_record_calls_for_the_other():
    with pytest.raises(SystemExit, match="with undetermined filings in the corpus"):
        bcr.currency_clauses(_NONE_FORM, _SCAN, _OBS + [{"syndicate": 9, "year": 2014,
                                                         "report_currency": "UNDETERMINED"}], 4)
    with pytest.raises(SystemExit, match="with no undetermined filing in the corpus"):
        bcr.currency_clauses(_SOME_FORM, _SCAN, _OBS, 3)
    with pytest.raises(SystemExit, match="other than GBP or USD"):
        bcr.currency_clauses(_NONE_FORM, dict(_SCAN, non_gbp_usd=["7_2024"]), _OBS, 3)
    with pytest.raises(SystemExit, match="outside the corpus"):
        bcr.currency_clauses(_NONE_FORM, dict(_SCAN, undetermined=["9_2014"]), _OBS, 3)


def test_the_sensitivity_sentences_follow_the_record():
    ms = _json("results", "check_missingness_sensitivity_results.json")
    m0 = _json("model", "dispersion_calibration_ritc.json")
    lines = bcr.missingness_lines()
    sentences = bcr.sensitivity_sentences(ms, m0)
    broad = ms["eligibility_unresolved_stress"]
    for text in (" ".join(lines), " ".join(sentences)):
        assert "essentially unchanged" not in text
        assert "%.3f" % ms["fits"]["ipw_model_sample"]["k"]["mean"] in text
        assert "0.15" in text
        assert "%d" % broad["n_eligibility_unresolved"] in text
        assert "not a bound" in text
    flat_lines = " ".join(lines)
    # the stress's size is the record's (70 = 58 + 12 until round 62's records made it 57 = 45 + 12)
    assert broad["n_pseudo"] == broad["n_eligibility_unresolved"] + broad["n_known_eligible_unavailable"]
    assert "%d-record" % broad["n_pseudo"] in flat_lines
    prop = ms["propensity_model"]
    assert "%.2f--%.2f" % (
        prop["primary_diagnostics"]["weight_min"],
        prop["primary_diagnostics"]["weight_max"],
    ) in flat_lines
    assert "%.2f--%.2f" % (
        prop["uncapped_diagnostic_not_fitted"]["weight_min"],
        prop["uncapped_diagnostic_not_fitted"]["weight_max"],
    ) in flat_lines
    assert "conditional and omit propensity-model uncertainty" in flat_lines
    doc = _read("docs", "current-results.md")
    for s in sentences:
        assert s in doc, "docs/current-results.md is stale: run src/build_current_results.py"
    prov = _read("docs", "data-provenance.md")
    for line in lines:
        assert line in prov, "docs/data-provenance.md is stale: run src/build_current_results.py"
    bad = json.loads(json.dumps(ms))
    cs = sorted(bad["eligible_outcome_stress"]["by_c"], key=float)
    bad["eligible_outcome_stress"]["by_c"][cs[-1]]["nu_clean"]["mean"] = bad["eligible_outcome_stress"]["by_c"][cs[0]]["nu_clean"]["mean"]
    with pytest.raises(SystemExit):
        bcr.sensitivity_sentences(bad, m0)


def test_the_withdrawn_grouping_counts_the_unresolved_filings():
    """Round 62: the sentence typed "the 58 no-disclosure records", and the sensitivity sentence "all 58 ... the 12
    known", so both stayed 58 when the records at extraction d9f2bdee made the unresolved filings 45 (the old test
    looked for "58" in the text and passed the typed value). Both counts are now the records'."""
    assert "the 7 no-disclosure records" in bcr.withdrawn_grouping_sentence({"eligibility_unresolved": 7})
    miss = _json("results", "missingness_check_results.json")
    sentence = bcr.withdrawn_grouping_sentence(miss["disposition_counts"])
    assert "the %d no-disclosure" % miss["disposition_counts"]["eligibility_unresolved"] in sentence
    assert sentence in _read("docs", "current-results.md"), "docs/current-results.md is stale"
    ms = _json("results", "check_missingness_sensitivity_results.json")
    m0 = _json("model", "dispersion_calibration_ritc.json")
    broad = json.loads(json.dumps(ms))
    broad["eligibility_unresolved_stress"].update(n_eligibility_unresolved=7, n_known_eligible_unavailable=3,
                                                  n_pseudo=10)
    text = " ".join(bcr.sensitivity_sentences(broad, m0))
    assert "assumes all 7 eligibility-unresolved filings" in text and "the 3 known unavailable outcomes" in text
    broad["eligibility_unresolved_stress"]["n_pseudo"] = 11
    with pytest.raises(SystemExit):
        bcr.sensitivity_sentences(broad, m0)


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
