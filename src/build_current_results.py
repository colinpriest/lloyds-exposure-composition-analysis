#!/usr/bin/env python3
"""Generate docs/current-results.md from the committed results. No prose numbers.

Round 55: the same run also writes the corpus waterfall in docs/data-provenance.md
and the generated blocks of docs/referee-checks.md (sections 1, 2 and 5) from their
result files, so those public documents cannot carry a stage that does not add up or a
donor that has left the pool.

Why this exists. `scaling_analysis_writeup.md` is a development narrative written as the
analysis evolved, and five review rounds each found conclusions in it that the manuscript
had since withdrawn. Reconciling an 8,000-line narrative by hand failed every time: a
correction would land in one passage while the summary, an appendix table cell or a
section several hundred lines away went on stating the old position. The write-up is now
archived as what it always was -- a record of how the analysis developed -- and this
document replaces it as the current-results reference.

The difference that matters is that nothing here is typed. Every figure is read from a
committed JSON at build time and printed with the file it came from, so the document
cannot drift from the results the way prose does. If a number here is wrong, the fit is
wrong; there is no third state where the document is merely out of date.

R213 (refit 3, A9e): the provenance note's remaining typed clauses (the corpus and modelling-sample rows, the
currency sensitivity, the missingness counts and failure rates, the random-intercept floor, the sample sizes) are
written here too, and a sentence whose words a record could stop supporting refuses to print when it does:
"essentially unchanged", "suggestive" and "not distinguishable from zero" had each outlived the fit it described.

Run:  python src/build_current_results.py
"""
import io
import json
import math
import os
import re
import subprocess
import assumed_business

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(HERE, "model")
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "docs", "current-results.md")


def load(*parts):
    p = os.path.join(*parts)
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None


def dig(d, path, default=None):
    cur = d
    for key in path.split("/"):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def f(x, n=3):
    return "--" if x is None else ("%.*f" % (n, x))


def exponent_question(khalf):
    """R214 (the owner's decision of 15 September 2026): theory bounds k to [1/2, 1] and the prior keeps it there, so
    the open question is where k lies inside the bracket. It is written from the k = 1/2 sensitivity's record, and a
    k = 1/2 fit that did not sample cleanly refuses it."""
    fit = (khalf or {}).get("k_half_fit") or {}
    pct = dig(khalf or {}, "vignettes/centre_pct_change/V1_v995")
    ratio = (khalf or {}).get("size_ratio_100_2000") or {}
    if pct is None or "adopted" not in ratio or "k_half" not in ratio:
        raise SystemExit("the k = 1/2 sensitivity is not recorded: the open question on k cannot be written")
    diag = fit.get("diagnostics") or {}
    if diag.get("divergences") != 0 or not diag.get("max_rhat", 9.0) <= 1.01:
        raise SystemExit("the k = 1/2 fit did not sample cleanly: its figures cannot be written")
    return ("the exact value of $k$ inside its theoretical bracket $[\\tfrac12, 1]$: fixing $k = \\tfrac12$ moves "
            "Vignette 1's VaR$_{99.5}$ by %+.1f%% and the 100m/2,000m scale ratio from %.2f to %.2f;"
            % (pct, ratio["adopted"], ratio["k_half"]))


def long_tail_question(c, lt):
    """R215 (the owner's decision L1): the slope is resolved, the share is scored by syndicate like every other model
    comparison, and the operator does not carry it. A record in which the share predicts unseen syndicates better (a
    bootstrap interval above zero) refuses the words; an unresolved slope is said as such."""
    if not c or not lt:
        raise SystemExit("the composition records are missing: the open question on the long-tail share cannot be written")
    b = c["beta_LT"]
    lo, hi = b["hdi"]
    slope = "$\\beta_{\\text{LT}} = %+.2f$ $[%+.2f, %+.2f]$" % (b["mean"], lo, hi)
    if lo <= 0 <= hi:
        return "the long-tail share slope, not distinguishable from zero (%s);" % slope
    if hi < 0:
        raise SystemExit("the long-tail share's slope is now resolved negative: rewrite the open question")
    r = dig(lt, "by_syndicate/long_tail_minus_composition")
    if not r:
        raise SystemExit("the long-tail share's by-syndicate score is not recorded")
    if r["bb_2.5"] > 0:
        raise SystemExit("the long-tail share now predicts unseen syndicates better: rewrite the open question")
    return ("whether the long-tail share matters for transfer: its slope is resolved positive (%s) but it does not "
            "improve prediction of unseen syndicates (by-syndicate $\\Delta$ELPD $%+.1f$, 95%% credible interval "
            "$[%+.1f, %+.1f]$, $P = %.2f$ that it predicts better), and the operator does not carry it;"
            % (slope, r["delta_ELPD"], r["bb_2.5"], r["bb_97.5"], r["P_first_better"]))


def main():
    m0 = load(MODEL, "dispersion_calibration_ritc.json")
    if m0 is None:
        raise SystemExit("model/dispersion_calibration_ritc.json not found; "
                         "run src/calibrate_dispersion_ritc.py first")
    pool = load(RESULTS, "pooling_compare_results.json")
    khalf = load(RESULTS, "check_k_half_sensitivity_results.json")
    ltshare = load(RESULTS, "check_long_tail_share_results.json")
    het = load(MODEL, "dispersion_calibration_hetscale.json")
    ranef = load(RESULTS, "check_syndicate_random_effect_results.json")
    conc = load(RESULTS, "check_mean_concentration_bayes_results.json")

    L = []
    A = L.append
    A("# Current results")
    A("")
    A("> **Generated file — do not edit.** Written by `src/build_current_results.py` "
      "from the committed model and results JSON. Every number below is read from the "
      "file named beside it.")
    A("")
    A("This is the current-results reference for the analysis behind the manuscript. "
      "`scaling_analysis_writeup.md` is a **development archive** and is not maintained "
      "against these numbers; where the two differ, this file and the manuscript are "
      "correct.")
    A("")

    A("## Adopted model")
    A("")
    A("Two-regime robust Bayesian pooling with a floor, fitted by NUTS. "
      "Source: `model/dispersion_calibration_ritc.json`.")
    A("")
    A("| Quantity | Posterior mean |")
    A("|---|---:|")
    for label, key, nd in (
            ("pooling exponent $k$", "k", 3),
            ("concentration exponent $\\gamma$", "gamma", 3),
            ("undiversifiable floor $\\sigma_{\\text{undiv}}$", "sd_undiv", 4),
            ("diversifiable scale $\\sigma_{\\text{div}}$", "sd_div", 4),
            ("clean-regime tail $\\nu_{\\text{clean}}$", "nu_clean", 2),
            ("RITC-regime tail $\\nu_{\\text{RITC}}$", "nu_ritc", 2),
            ("RITC tail shift $\\lambda_{\\text{RITC}}$", "lambda_ritc", 3),
            ("RITC scale term $\\beta_{\\text{RITC}}$", "beta_ritc", 3)):
        A("| %s | %s |" % (label, f(m0.get(key), nd)))
    A("")
    A("Fitted on n = %s syndicate-years (%s RITC) across %s reporting years, seed %s. "
      "Diagnostics: %s divergences, max $\\hat R$ = %s, min bulk ESS = %s."
      % (m0.get("n"), m0.get("n_ritc"), m0.get("n_years"), m0.get("seed"),
         dig(m0, "diagnostics/divergences"), f(dig(m0, "diagnostics/max_rhat"), 2),
         dig(m0, "diagnostics/min_ess_bulk")))
    A("")

    A("## What the posterior does and does not settle")
    A("")
    A("| Statement | Value | Status |")
    A("|---|---:|---|")
    # the direction word is the fit's (R213: refit 3 reads the RITC tail as the lighter, 0.314)
    p_order = dig(m0, "posterior_prob/nu_ritc_lt_nu_clean")
    A(r"| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | %s | RITC tail %s in this fit; the ordering is not imposed (the prior on $\lambda_{\text{RITC}}$ admits both signs) |"
      % (f(p_order, 3), "direction not recorded" if p_order is None else ("heavier" if p_order >= 0.5 else "lighter")))
    A("| $P(\\nu_{\\text{RITC}} < 2)$ | %s | posterior probability that the RITC regime lacks a finite variance |"
      % f(dig(m0, "posterior_prob/nu_ritc_lt_2"), 3))
    A("| $P(k > \\tfrac12)$, $P(k < 1)$ | $1$ by construction | theory bounds $k$ to $[\\tfrac12,1]$ "
      "(finite-variance independent $\\sqrt N$ pooling to comonotonic pooling) and the prior keeps it there, so these are "
      "not findings; the endpoints are scored by syndicate as fixed alternatives |")
    A("| $P(|\\beta_{\\text{RITC}}| > 0.1)$ | %s | fitted in the likelihood; the "
      "transfer operator omits it, not shown to be zero |"
      % f(dig(m0, "posterior_prob/beta_ritc_gt_0.1_abs"), 3))
    A("")

    if pool:
        A("## Pooling comparison")
        A("")
        A("Source: `results/pooling_compare_results.json`.")
        A("")
        A("| Model | $k$ | elpd$_{\\text{LOO}}$ |")
        A("|---|---:|---:|")
        for name, d in sorted(pool.items()):
            if not isinstance(d, dict) or "k_mean" not in d:
                continue
            A("| `%s` | %s | %s |" % (name, f(d.get("k_mean"), 3),
                                      f(d.get("elpd_loo"), 2)))
        A("")
        # Two DIFFERENT estimands. Printing the PSIS-LOO numbers under a
        # by-syndicate-CV description is how this document mislabelled them.
        A("**Observation-level PSIS-LOO** (`results/pooling_compare_results.json`): "
          "$\\Delta$elpd (M1 blended $-$ M2 finite-variance independent $\\sqrt N$) = "
          "%s, SE %s."
          % (f(pool.get("delta_elpd_M1_minus_M2"), 2), f(pool.get("delta_se"), 2)))
        A("")
        cse = load(RESULTS, "check_cv_clustered_se_results.json")
        bb = dig(cse or {}, "contrasts/composition__vs__k0.5")
        if bb:
            A("**By-syndicate cross-validation, Bayesian bootstrap over syndicate "
              "totals** (`results/check_cv_clustered_se_results.json`) --- the "
              "criterion the manuscript rests on, because observations within a "
              "syndicate are not independent and a plain SE understates the "
              "clustering. $\\Delta$ELPD (free $k$ $-$ $k=\\tfrac12$+floor) = %s, "
              "95%% credible interval $[%s, %s]$, $P(\\text{free }k\\text{ predicts "
              "better}) = %s$."
              % (f(bb.get("delta_ELPD"), 2), f(bb.get("bb_2.5"), 1),
                 f(bb.get("bb_97.5"), 1), f(bb.get("P_first_better"), 2)))
            A("")
        # R213: the words below say neither criterion separates the forms; a record on which one does refuses them
        cv_apart = bool(bb) and not (bb["bb_2.5"] < 0 < bb["bb_97.5"])
        loo_apart = abs(pool.get("delta_elpd_M1_minus_M2") or 0.0) >= 2.0 * (pool.get("delta_se") or float("inf"))
        if cv_apart or loo_apart:
            raise SystemExit("a pooling criterion now separates the free exponent from k = 1/2 with a floor: "
                             "rewrite 'Neither criterion separates the two forms' from the records")
        A("Neither criterion separates the two forms, so the free exponent is **not** "
          "separated from $k=\\tfrac12$-plus-floor on either. That is why pooling "
          "slower than the finite-variance independent $\\sqrt N$ benchmark is treated "
          "as unresolved (independence alone does not give $k=\\tfrac12$ under "
          "infinite-variance aggregation).")
        A("")

    if het:
        A("## Size-loaded co-movement (M4)")
        A("")
        A("Source: `model/dispersion_calibration_hetscale.json`. Specification as "
          "fitted:")
        A("")
        A("```")
        A(str(het.get("spec", "")))
        A("```")
        A("")
        psi = het.get("psi_s") if isinstance(het.get("psi_s"), dict) else None
        if psi:
            A("Loading $\\psi_s$ = %s, $P(\\psi_s > 0)$ = %s. This is a **linear "
              "loading coefficient on centred log effective size**, not a power "
              "elasticity."
              % (f(psi.get("mean"), 3),
                 f(dig(het, "posterior_prob/psi_s_gt_0"), 3)))
            A("")
        A("M3 and M4 load a **common** reporting-year factor on size. Pair-specific "
          "shared-slip or residual-noise dependence is not fitted anywhere in this "
          "analysis, so these sensitivities bound the common-factor channel only.")
        A("")

    if ranef:
        r = dig(ranef, "tau_alpha_vs_scale") or {}
        if r:
            A("## Between-syndicate level differences")
            A("")
            A("Source: `results/check_syndicate_random_effect_results.json`. "
              "$\\tau_\\alpha$ = %s against $\\sigma_{\\text{div}}$ = %s at the "
              "reference size (ratio %s): persistent between-syndicate level "
              "differences are real and material."
              % (f(r.get("tau_alpha"), 3), f(r.get("sd_div_at_reference"), 3),
                 f(r.get("ratio_tau_alpha_over_sd_div"), 2)))
            A("")

    miss = load(RESULTS, "missingness_check_results.json")
    if miss:
        A("## Missingness")
        A("")
        A("Source: `results/missingness_check_results.json`. These figures are read "
          "from that file; prose copies of them drift and have.")
        A("")
        A("- %s filings, %s extracted successfully, **%s without the reserves field "
          "the diagnostic needs**. That is not the same count as the wholly empty "
          "extractions reported in the collection flow, and the two have been "
          "conflated before."
          % (miss.get("n_files"), miss.get("n_success"), miss.get("n_failed")))
        a_ = dig(miss, "A_per_syndicate") or {}
        b_ = dig(miss, "B_per_filing") or {}
        d_ = dig(miss, "D_outcome_given_size") or {}
        if a_:
            A("- Syndicates with at least one failed year: median size "
              "\\pounds%sm against \\pounds%sm for never-fail syndicates "
              "($p = %s$)." % (f(a_.get("median_size_has_failure"), 1),
                               f(a_.get("median_size_no_failure"), 1),
                               f(a_.get("p"), 4)))
        if b_:
            A("- Failed filings' syndicates are smaller than successful ones: "
              "\\pounds%sm against \\pounds%sm. **%s orphan filings** come from "
              "syndicates never observed at all, so no outcome exists for them by "
              "construction." % (f(b_.get("median_failed_synd_size"), 1),
                                 f(b_.get("median_success_size"), 1),
                                 b_.get("n_orphan")))
        if d_:
            if d_.get("abs_S_p", 0.0) < 0.05:
                raise SystemExit("the failure-prone indicator is now associated with dispersion given size "
                                 "(p = %.3f): 'No association was detected' would be false" % d_["abs_S_p"])
            A("- Dispersion given size, failure-prone indicator: coefficient %s, "
              "$p = %s$. **No association was detected among syndicates observed at "
              "least once.** That is the whole of what this diagnostic supports: a "
              "failure to reject is not a demonstration, and it is silent about the "
              "orphans, so **missing-at-random cannot be established**."
              % (f(d_.get("abs_S_failure_prone_coef"), 4), f(d_.get("abs_S_p"), 3)))
        A("")
        sens = load(RESULTS, "check_missingness_sensitivity_results.json")
        A("Two sensitivities are reported instead of resting on it. %s See the manuscript for both."
          % " ".join(sensitivity_sentences(sens, m0)))
        A("")

    A("## Open questions")
    A("")
    A("These are unresolved on public data and nothing downstream rests on them. The "
      "manuscript states each where it arises; `paper/audit_numbers.py` gate M keeps "
      "that list and the register in step.")
    A("")
    for line in (
            "whether pooling is slower than the finite-variance independent $\\sqrt N$ "
            "benchmark -- a floor-plus-$\\sqrt N$ alternative is not predictively "
            "separable;",
            exponent_question(khalf),
            "whether the size-dispersion decline continues past about GBP 1bn;",
            "the within-book concentration--location slope, which is unresolved "
            "rather than zero;",
            long_tail_question(load(RESULTS, "compose_robust_results.json"), ltshare),
            "the concentration functional form, which is indeterminate."):
        A("- " + line)
    A("")
    A("The floor is retained as a **structural choice about extrapolation**, not as an "
      "adjudicated asymptote: a floorless law is not predictively separable from the "
      "floored one, and the floor's posterior is conditional on having fitted a floored "
      "model. $\\mu = 0$ is a **fitting restriction**, not a transfer principle: the "
      "operator rescales the raw severity, so a **clean** donor's persistent level is "
      "carried across and scaled by the size ratio, while an **RITC** donor's realised "
      "level is carried through the nonlinear rank map, where it is neither separable "
      "as a scaled location nor identified or removed.")
    A("")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("wrote %s (%d lines)" % (os.path.relpath(OUT, HERE), len(L)))
    ex = load(MODEL, "exposure_results.json")
    if ex is None:
        raise SystemExit("model/exposure_results.json not found; run src/run_analysis.py first")
    print("docs/data-provenance.md waterfall %s" % ("rewritten" if write_provenance_waterfall(ex) else "already current"))
    print("docs/data-provenance.md counts and sensitivities %s"
          % ("rewritten" if write_provenance_counts(ex) else "already current"))
    print("docs/data-provenance.md typed clauses %s"
          % ("rewritten" if write_provenance_clauses(ex) else "already current"))
    print("README.md donor count %s"
          % ("rewritten" if write_readme_donor_count(ex) else "already current"))
    print("docs/data-provenance.md round-55 correction %s"
          % ("rewritten" if write_provenance_correction(ex) else "already current"))
    print("docs/referee-checks.md generated blocks %s" % ("rewritten" if write_referee_blocks() else "already current"))
    return 0


# ---------------------------------------------------------------------------
# Round 55 (D03, D06): two further public documents carry blocks written from the
# records rather than typed. The corpus waterfall in docs/data-provenance.md is
# printed from the loader's disposition flow and asserted to add up; the referee
# record's blocks that were relabelled as current in round 54 (sections 1, 2 and 5)
# are written from their named result files, so a relabelled block cannot list a
# donor that is no longer in the pool or a floor under a tau_m heading.
PROVENANCE = os.path.join(HERE, "docs", "data-provenance.md")
REFEREE = os.path.join(HERE, "docs", "referee-checks.md")


def _rw(path, fn):
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    t2 = fn(t)
    if t2 != t:
        io.open(path, "w", encoding="utf-8", newline="").write(t2.replace("\n", "\r\n") if crlf else t2)
    return t2 != t


#: the corpus-to-working-sample steps waterfall_lines prints, in the loader's order
WATERFALL_STEPS = ("net_or_unstated_basis", "takeon_not_development", "unusable_severity",
                   "missing_opening_reserves", "missing_lob_weights")


def waterfall_lines(ex):
    """The disjoint stages from files to corpus to working sample, from
    model/exposure_results.json's disposition flow; raises if they do not add up."""
    flow = ex["disposition_flow"]
    pre, tows = flow["pre_corpus"], flow["to_working_sample"]
    files, corpus, ws = flow["files_retrieved"], flow["corpus"], flow["working_sample"]
    if files - sum(pre.values()) != corpus:
        raise SystemExit("disposition flow: %d - %d != corpus %d" % (files, sum(pre.values()), corpus))
    if corpus - sum(tows.values()) != ws:
        raise SystemExit("disposition flow: corpus %d - %d != working sample %d" % (corpus, sum(tows.values()), ws))
    byr = ex["classification_summary"]["by_reason_year"]
    n_net = sum(byr.get("NET_BASIS", {}).values())
    n_unk = sum(byr.get("UNKNOWN_BASIS", {}).values())
    if n_net + n_unk != tows["net_or_unstated_basis"]:
        raise SystemExit("basis exclusions %d + %d != %d" % (n_net, n_unk, tows["net_or_unstated_basis"]))
    # Every step is printed by name below. A step this printer has no words for would drop out
    # of the printed equation while the sum above still passed on the flow's own total; the
    # take-on step (PLAN R213) is the first step added since the printer was written.
    unprinted = [k for k in tows if k not in WATERFALL_STEPS]
    if unprinted:
        raise SystemExit("disposition flow: no wording for step(s) %s" % ", ".join(unprinted))
    takeon = tows.get("takeon_not_development")
    if takeon is None:
        # a flow recorded before the take-on step prints as it did
        steps = ["     `src/pyd_basis_rule.py`) - %d unusable severity - %d missing opening reserves"
                 % (tows["unusable_severity"], tows["missing_opening_reserves"])]
    else:
        n_takeon = sum(byr.get("TAKEON_NOT_DEVELOPMENT", {}).values())
        if n_takeon != takeon:
            raise SystemExit("take-on exclusions %d != %d" % (n_takeon, takeon))
        steps = ["     `src/pyd_basis_rule.py`) - %d take-on, not development" % takeon,
                 "     (`data/takeon_not_development.json`) - %d unusable severity - %d missing "
                 "opening reserves" % (tows["unusable_severity"], tows["missing_opening_reserves"])]
    single = ex["dual_model_stats"]["single_model_files"]
    if single != flow["files_without_dual_model_record_overlapping_audit_count"]:
        raise SystemExit("single-model file count disagrees between the two records")
    names = {"excluded": "excluded", "skipped": "skipped",
             "incomplete_no_development_record": "no development record", "in_runoff": "in run-off",
             "no_reserves": "no reserves"}
    stages = " - ".join("%d %s" % (pre[k], names.get(k, k)) for k in pre)
    return [
        "%d files -> %d corpus -> %d modelling sample" % (files, corpus, ws),
        "  the loader's stages are disjoint and subtract to the corpus",
        "  (generated by src/build_current_results.py from the disposition flow in",
        "   model/exposure_results.json, asserted at build time):",
        "    %d - %s = %d" % (files, stages, corpus),
        "  from the corpus to the working sample, also disjoint:",
        "    %d - %d net or unstated basis (%d net, %d unstated; `data/pyd_basis_register.json`,"
        % (corpus, tows["net_or_unstated_basis"], n_net, n_unk),
        *steps,
        "     - %d without premium weights = %d" % (tows["missing_lob_weights"], ws),
        "  %d of the %d filings carry no usable dual-model extraction. That is a diagnostic"
        % (single, files),
        "  of extraction quality and OVERLAPS the stages above; it is not a further subtraction,",
        "  and treating it as one is what made an earlier version of this flow fail to add up.",
        # a synthetic flow without observations (the equation's own tests) prints the equation alone
        *(population_rows(ex) if "observations" in ex else []),
    ]


def population_rows(ex):
    """The corpus and modelling-sample rows under the waterfall. R213: commit A9d typed refit 3's sample into them by
    hand, after the recorded pass; they are counted here from the records the waterfall itself reads."""
    flow, obs = ex["disposition_flow"], ex["observations"]
    if len(obs) != flow["corpus"]:
        raise SystemExit("corpus: %d observations recorded against a flow of %d" % (len(obs), flow["corpus"]))
    mask = set(ex["eligibility"]["eligible_for_capital"]["mask_indices"])
    if len(mask) != flow["working_sample"]:
        raise SystemExit("working sample: %d eligible records against a flow of %d" % (len(mask), flow["working_sample"]))
    years = sorted({int(o["year"]) for o in obs})
    by_syn = {}
    for o in obs:
        by_syn.setdefault(int(o["syndicate"]), set()).add(int(o["year"]))
    every = sum(1 for ys in by_syn.values() if len(ys) == len(years))
    sample_syn = {int(obs[i]["syndicate"]) for i in mask}
    return ["Corpus:          %d syndicate-years / %d syndicates; %d appear in all %d years (%d-%d)"
            % (len(obs), len(by_syn), every, len(years), years[0], years[-1]),
            "Modelling sample: %d syndicate-years / %d syndicates" % (len(mask), len(sample_syn))]


def write_provenance_waterfall(ex):
    def fn(t):
        # the block runs to its closing fence, so the corpus and sample rows under the stages are written too
        m = re.search(r"```\n\d+ files -> .*?\n```", t, re.S)
        if not m:
            raise SystemExit("docs/data-provenance.md carries no waterfall block")
        return t[:m.start()] + "```\n" + "\n".join(waterfall_lines(ex)) + "\n```" + t[m.end():]
    return _rw(PROVENANCE, fn)



# ── R151: the public counts and sensitivities, written from their records ─────
#
# Three paragraphs of docs/data-provenance.md and one line of README.md quoted counts
# and fitted values from three different eras at once. They are generated here, between
# markers, so a refit carries them and a reader is told which population each count
# belongs to: the collection of 1,065 filings, the 920-record corpus, or the working
# sample. Those three were being used interchangeably.

RITC_SCAN = os.path.join(HERE, "pdf_extraction", "ritc_scan.json")
MARKET_ACTIVE = os.path.join(HERE, "data", "market_active_syndicates.json")
README = os.path.join(HERE, "README.md")
#: Lloyd's Annual Reports / SFCRs for the years before the official active list begins.
MARKET_AR = {2014: 92, 2015: 94, 2016: 99, 2017: 95, 2018: 99, 2019: 93}


def _block(t, name, body):
    """Replace the text between `<!-- name:start -->` and `<!-- name:end -->`."""
    start, end = "<!-- %s:start -->" % name, "<!-- %s:end -->" % name
    i, j = t.find(start), t.find(end)
    if i < 0 or j < 0:
        raise SystemExit("docs: no %s block" % name)
    return t[:i + len(start)] + "\n" + body.rstrip("\n") + "\n" + t[j:]


def _sample_by_year(ex):
    obs = ex["observations"]
    idx = set(ex["eligibility"]["eligible_for_capital"]["mask_indices"])
    out = {}
    for i in sorted(idx):
        y = int(obs[i]["year"])
        out[y] = out.get(y, 0) + 1
    return out


def _active_by_year():
    out = dict(MARKET_AR)
    with io.open(MARKET_ACTIVE, encoding="utf-8") as fh:
        for y, lst in json.load(fh).items():
            out[int(y)] = len(lst)
    return out


def ritc_lines(ex):
    """The RITC flags, counted in each of the three populations they get quoted in."""
    with io.open(RITC_SCAN, encoding="utf-8") as fh:
        scan = json.load(fh)
    regime = assumed_business.sources()
    flagged = {k for k, s in regime.items() if any(x.startswith("ritc_") for x in s)}
    transfers = {k for k, s in regime.items() if any(x.startswith("transfer_") for x in s)}
    transfer_only = transfers - flagged
    by_conf = {}
    for k in flagged:
        c = scan[k].get("confidence") or "unstated"
        by_conf[c] = by_conf.get(c, 0) + 1
    corpus_keys = {"%d_%d" % (o["syndicate"], o["year"]) for o in ex["observations"]}
    in_corpus = len(set(regime) & corpus_keys)
    with io.open(os.path.join(HERE, "results",
                              "check_ritc_scale_term_results.json"), encoding="utf-8") as fh:
        in_sample = json.load(fh)["n_ritc"]
    conf = ", ".join("%d %s" % (by_conf[c], c) for c in sorted(by_conf))
    return [
        "- **`ritc_scan.json`** added \u2014 a deterministic RITC scan (sentence classifier, not a",
        "  language model), keyed `{syndicate}_{year}` with `ritc_occurred` and `confidence`.",
        "  It scans all **%d** collected filings and flags **%d** (%s)."
        % (len(scan), len(flagged), conf),
        "- **Confirmed inward transfers join the same regime** (PLAN R195): the hand-adjudicated",
        "  register `pdf_extraction/audit/portfolio_transfer_adjudication.json` confirms **%d**"
        % len(transfers),
        "  syndicate-years that take on another syndicate's liabilities by transfer; **%d** of them"
        % (len(transfers) - len(transfer_only)),
        "  also accept RITC and **%d** enter the regime by transfer alone, so it holds **%d**."
        % (len(transfer_only), len(regime)),
        "  Those syndicate-years fall in three different populations, and the counts are not",
        "  interchangeable: **%d** are in the **%d-record corpus**, and **%d** are in the"
        % (in_corpus, len(ex["observations"]), in_sample),
        "  **working sample** (`n_ritc` in `results/check_ritc_scale_term_results.json`).",
    ]


def coverage_lines(ex):
    """The overall and per-year coverage, from the sample and the market denominators."""
    samp = _sample_by_year(ex)
    active = _active_by_year()
    years = sorted(samp)
    total_active = sum(active[y] for y in years)
    total_samp = sum(samp.values())
    rates = {y: 100.0 * samp[y] / active[y] for y in years}
    worst = min(rates, key=lambda y: rates[y])
    best = max(rates, key=lambda y: rates[y])
    mid = [rates[y] for y in years if y not in (worst,)]
    return [
        "Coverage is **%d %% of active syndicate-years overall** (%d of %d; it was ~47 %% on the"
        % (round(100.0 * total_samp / total_active), total_samp, total_active),
        "old dataset), and it is **uneven, not flat**: the annual rate runs from **%d %% in %d (%d of"
        % (round(rates[worst]), worst, samp[worst]),
        "%d)** to **%d %% in %d**, with every other year between %d %% and %d %%. The 2020\u20132024 retrieval"
        % (active[worst], round(rates[best]), best, int(min(mid)), int(max(mid))),
        "gap in the old dataset is closed (~90\u201395 PDFs retrieved per year vs ~91\u201399 active syndicates),",
    ]


def _material_moves(lo, hi):
    """R213: the orphan stress's words say two parameters move materially. The thresholds (0.05 on the concentration
    exponent, 0.5 on the clean tail index) are where that stops being a fair reading of the record; the generator
    refuses the words below either."""
    dg = abs(hi["gamma"]["mean"] - lo["gamma"]["mean"])
    dnu = abs(hi["nu_clean"]["mean"] - lo["nu_clean"]["mean"])
    if dg < 0.05 or dnu < 0.5:
        raise SystemExit("orphan stress: gamma moves %.3f and the clean tail %.2f; 'move materially' needs re-reading "
                         "against the record" % (dg, dnu))


def _weighting(ms):
    """The weighting fits and the larger move of gamma and the floor under it. R213: refit 3's weighting moves k from
    0.565 to 0.591, so refit 1's 'leaves the fit essentially unchanged' became false."""
    un, ipw = ms["fits"]["unweighted"], ms["fits"]["ipw_selection_weighted"]
    if ms["propensity_model"]["coef_logR"] <= 0:
        raise SystemExit("the response propensity no longer rises with size: 'confirms the size gradient' is false")
    within = max(abs(ipw["gamma"]["mean"] - un["gamma"]["mean"]),
                 abs(ipw["sd_undiv"]["mean"] - un["sd_undiv"]["mean"]))
    return un, ipw, within


def sensitivity_sentences(ms, m0):
    """The two missingness sensitivities as current-results.md states them, worded from the record."""
    un, ipw, within = _weighting(ms)
    k0 = m0.get("k") if m0.get("k") is not None else dig(m0, "params/k/mean")
    if "%.3f" % un["k"]["mean"] != "%.3f" % k0:
        raise SystemExit("the unweighted missingness fit is not the adopted fit (k %.3f against %.3f)"
                         % (un["k"]["mean"], k0))
    byc = ms["worst_case"]["by_c"]
    cs = sorted(byc, key=float)
    lo, hi = byc[cs[0]], byc[cs[-1]]
    _material_moves(lo, hi)
    ks = [byc[c]["k"]["mean"] for c in cs]
    if "%.3f" % ipw["k"]["mean"] == "%.3f" % un["k"]["mean"]:
        move = "leaves the pooling exponent at $k = %.3f$" % un["k"]["mean"]
    else:
        move = "moves the pooling exponent from $k = %.3f$ to $%.3f$" % (un["k"]["mean"], ipw["k"]["mean"])
    return [
        "Inverse-probability weighting %s and leaves the concentration exponent and the floor within %.3f "
        "of the adopted fit." % (move, within),
        "The high-volatility orphan stress moves the conditional bracketed estimate from $k = %.3f$ at $c=%g$ to "
        "$%.3f$ at $c=%g$, between $%.3f$ and $%.3f$ across the grid --- a construction that makes the "
        "predominantly small missing books more volatile, so it cannot test the adverse-to-sub-linearity "
        "direction --- and moves the concentration exponent and the clean-regime tail materially, so the tail "
        "is **not** unaffected." % (lo["k"]["mean"], float(cs[0]), hi["k"]["mean"], float(cs[-1]), min(ks), max(ks)),
    ]


def missingness_lines():
    """The two selection sensitivities, from check_missingness_sensitivity_results.json."""
    with io.open(os.path.join(HERE, "results",
                              "check_missingness_sensitivity_results.json"), encoding="utf-8") as fh:
        ms = json.load(fh)
    un, ipw, within = _weighting(ms)
    prop = ms["propensity_model"]
    byc = ms["worst_case"]["by_c"]
    cs = sorted(byc, key=float)
    lo, hi = byc[cs[0]], byc[cs[-1]]
    _material_moves(lo, hi)
    ks = [byc[c]["k"]["mean"] for c in cs]

    def m(block, key):
        return block[key]["mean"]

    verb = ("leaves the pooling exponent at" if "%.3f" % m(ipw, "k") == "%.3f" % m(un, "k")
            else "moves the pooling exponent to")
    return [
        "- **Selection weighting (IPW).** Response propensity",
        "  $\\operatorname{logit}P(\\text{success})\\sim\\log R+\\text{year}$ confirms the size",
        "  gradient (coefficient on $\\log R$ $%+.2f$). Refitting with each observation weighted"
        % prop["coef_logR"],
        "  by $1/\\hat p$ \u2014 up-weighting small syndicates by up to $%.1f\\times$ \u2014 %s"
        % (prop["weight_max"], verb),
        "  $k=%.3f$ $[%.3f,%.3f]$ against $%.3f$ $[%.3f,%.3f]$ and leaves $\\gamma$ ($%.3f$ against"
        % (m(ipw, "k"), ipw["k"]["hdi_2.5"], ipw["k"]["hdi_97.5"],
           m(un, "k"), un["k"]["hdi_2.5"], un["k"]["hdi_97.5"], m(ipw, "gamma")),
        "  $%.3f$) and the floor ($%.3f$ against $%.3f$) within $%.3f$ of the unweighted fit;"
        % (m(un, "gamma"), m(ipw, "sd_undiv"), m(un, "sd_undiv"), within),
        "  $\\nu_{\\text{clean}}=%.2f$ against $%.2f$." % (m(ipw, "nu_clean"), m(un, "nu_clean")),
        "- **High-volatility orphan stress.** Appending %d pseudo-records at the size distribution"
        % ms["worst_case"]["n_pseudo"],
        "  of failure-prone syndicates moves the conditional bracketed estimate from $k=%.3f$"
        % m(lo, "k"),
        "  at $c=%g$ to $%.3f$ at $c=%g$, between $%.3f$ and $%.3f$ across the grid. Because the"
        % (float(cs[0]), m(hi, "k"), float(cs[-1]), min(ks), max(ks)),
        "  construction makes the predominantly small missing books *more* volatile, it cannot",
        "  test the adverse-to-sub-linearity direction. Two parameters move",
        "  materially: the concentration exponent $%.3f\\to%.3f$ and the **clean-regime tail"
        % (m(lo, "gamma"), m(hi, "gamma")),
        "  $\\nu_{\\text{clean}}$ from $%.2f$ to $%.2f$** at $c=%g$. The tail is therefore *not*"
        % (m(lo, "nu_clean"), m(hi, "nu_clean"), float(cs[-1])),
        "  unaffected, and neither the tail nor the vignette VaRs should be described as such.",
    ]


def write_provenance_counts(ex):
    def fn(t):
        t = _block(t, "ritc-counts", "\n".join(ritc_lines(ex)))
        t = _block(t, "coverage", "\n".join(coverage_lines(ex)))
        t = _block(t, "missingness", "\n".join(missingness_lines()))
        return t
    return _rw(PROVENANCE, fn)


# ── R213 (A9e): the provenance note's typed clauses, written from their records ─────
#
# Commit A9d brought these clauses to refit 3 by hand, and so changed a declared output of the recorded pass after the
# pass: the run report's hash for the note stopped matching the committed file. The hand edit also left two clauses
# from older extractions standing ("2014: 29%; 2018: 18%; others 7-12%" and "37 orphan filings from 22 syndicates").
# Each clause is found by a pattern that must match exactly once; only its numbers are rewritten, and the words around
# them are checked against the record first.

PROVENANCE_RECORDS = ("missingness_check_results.json", "check_missingness_sensitivity_results.json",
                      "fx_sensitivity_results.json", "check_syndicate_random_effect_results.json")


def provenance_records():
    out = {}
    for name in PROVENANCE_RECORDS:
        out[name] = load(RESULTS, name)
        if out[name] is None:
            raise SystemExit("provenance clauses: results/%s is missing" % name)
    out["currency_scan.json"] = load(HERE, "pdf_extraction", "currency_scan.json")
    if out["currency_scan.json"] is None:
        raise SystemExit("provenance clauses: pdf_extraction/currency_scan.json is missing")
    return out


def _numbers(t, pattern, values, what):
    """Rewrite the named groups of the single match of `pattern` with `values`, leaving the words and the line breaks
    between them as written. With no values it only asserts that the clause is there, once."""
    found = list(re.finditer(pattern, t, re.S))
    if len(found) != 1:
        raise SystemExit("docs/data-provenance.md: %s found %d times" % (what, len(found)))
    m = found[0]
    for a, b, v in sorted(((m.start(k), m.end(k), str(v)) for k, v in values.items()), reverse=True):
        t = t[:a] + v + t[b:]
    return t


def provenance_clauses(t, ex, records=None):
    """Sections 2b, 2c and 4's typed clauses, from their records; raises where a record no longer supports the words
    around a number."""
    r = records or provenance_records()
    mc, ms = r["missingness_check_results.json"], r["check_missingness_sensitivity_results.json"]
    fx, ranef, scan = (r["fx_sensitivity_results.json"], r["check_syndicate_random_effect_results.json"],
                       r["currency_scan.json"])
    flow, obs = ex["disposition_flow"], ex["observations"]

    # 2b: the currency counts over the collected filings and over the corpus
    cc = scan["counts"]
    corp = {}
    for o in obs:
        key = str(o.get("report_currency"))
        corp[key] = corp.get(key, 0) + 1
    und_in = corp.get("UNDETERMINED", 0)
    if sum(cc.values()) != scan["n_reports"] or sum(corp.values()) != flow["corpus"]:
        raise SystemExit("the currency counts do not add up to the filings or to the corpus")
    if (set(cc) | set(corp)) - {"GBP", "USD", "UNDETERMINED"} or scan.get("non_gbp_usd"):
        raise SystemExit("a currency other than GBP or USD: 'No currency other than GBP or USD was found' is false")
    corpus_keys = {"%d_%d" % (int(o["syndicate"]), int(o["year"])) for o in obs}
    if len(set(scan["undetermined"]) - corpus_keys) != cc["UNDETERMINED"] - und_in:
        raise SystemExit("the undetermined filings outside the corpus do not number the difference of the counts")
    t = _numbers(t, r"Corpus currencies \((?P<n>[0-9,]+) filings\): \*\*(?P<gbp>\d+) GBP / (?P<usd>\d+) USD / "
                    r"(?P<und>\d+) undetermined\*\*\. (?P<skip>\d+) of the undetermined\s+are skipped no-model files "
                    r"that never enter the analysis\. The other (?P<inc>\d+) are in the (?P<corpus>\d+)-observation",
                 {"n": "{:,}".format(scan["n_reports"]), "gbp": cc["GBP"], "usd": cc["USD"],
                  "und": cc["UNDETERMINED"], "skip": cc["UNDETERMINED"] - und_in, "inc": und_in,
                  "corpus": flow["corpus"]}, "the filings' currency counts")
    t = _numbers(t, r"The (?P<corpus>\d+)-observation\s+dataset is \*\*(?P<gbp>\d+) GBP / (?P<usd>\d+) USD "
                    r"\((?P<pct>\d+)%\) / (?P<und>\d+) undetermined\*\*",
                 {"corpus": flow["corpus"], "gbp": corp.get("GBP", 0), "usd": corp.get("USD", 0),
                  "pct": "%.0f" % (100.0 * corp.get("USD", 0) / flow["corpus"]), "und": und_in},
                 "the corpus's currency counts")
    if scan["disagreements_with_llm"]:
        raise SystemExit("the currency scan records disagreements with the extraction field: 'found zero "
                         "disagreement' is false")
    t = _numbers(t, r"The scan\s+found zero disagreement with the dual-LLM `currency` field when it ran", {},
                 "the scan-agreement clause")

    # 2b: the currency sensitivity -- point sensitivities of two separately fitted posteriors
    base, nom = fx["fits"]["FX-converted to GBP (baseline)"], fx["fits"]["nominal (as-reported)"]
    if not fx["adopted_agreement"]["ok"]:
        raise SystemExit("the converted baseline no longer reproduces the adopted calibration")
    t = _numbers(t, r"sampling configuration \((?P<chains>\d+) chains x (?P<draws>\d+) post-warmup draws\), so the "
                    r"converted\s+baseline reproduces the published calibration",
                 {"chains": fx["sampling"]["chains"], "draws": fx["sampling"]["draws"]}, "the currency refit's sampling")
    t = _numbers(t, r"\(the pooling exponent moves by (?P<dk>[0-9.]+) and the clean tail by (?P<dnu>[0-9.]+);\s+the "
                    r"Vignette-1 VaR\$_\{99\.5\}\$ moves (?P<pct>[0-9.]+)% -- (?P<va>[0-9.]+) converted against "
                    r"(?P<vn>[0-9.]+) nominal",
                 {"dk": "%.3f" % abs(nom["k"] - base["k"]), "dnu": "%.2f" % abs(nom["nu_clean"] - base["nu_clean"]),
                  "pct": "%.1f" % abs(100.0 * (nom["V1_VaR995"] / base["V1_VaR995"] - 1.0)),
                  "va": "%.3f" % base["V1_VaR995"], "vn": "%.3f" % nom["V1_VaR995"]}, "the currency sensitivity")
    order = [(fit["nu_ritc"] > fit["nu_clean"], fit["conditional_fit_summaries"]["P_nu_ritc_lt_nu_clean"])
             for fit in (base, nom)]
    if order[0][0] != order[1][0] or not all(0.05 < p < 0.95 for _, p in order):
        raise SystemExit("the tail-regime ordering no longer recurs, unresolved, under both currency fits")
    t = _numbers(t, r"the tail-regime point ordering recurs under\s+each fit's own posterior and is resolved under\s+"
                    r"neither", {}, "the tail-ordering clause")

    # 2c: who is missing, and what the outcome regression can and cannot say
    a_, b_, d_ = mc["A_per_syndicate"], mc["B_per_filing"], mc["D_outcome_given_size"]
    if not (a_["median_size_has_failure"] < a_["median_size_no_failure"] and a_["p"] < 0.05
            and b_["median_failed_synd_size"] < b_["median_success_size"] and b_["p"] < 0.05):
        raise SystemExit("the failures' size gradient is no longer present in both size diagnostics")
    t = _numbers(t, r"Syndicates with at least one failed year are\s+materially smaller than never-fail syndicates, "
                    r"failed filings' syndicates are smaller\s+than successful ones", {}, "the size-bias clause")
    rates = {int(y): 100.0 * v[0] / v[1] for y, v in mc["C_failure_by_year"].items()}
    years = sorted(rates)
    later = [rates[y] for y in years[1:]]
    if not rates[years[0]] > max(later):
        raise SystemExit("the earliest vintage no longer has the highest failure rate")
    t = _numbers(t, r"failures cluster in (?P<clause>older, scanned vintages \([^)]*\)|the oldest, scanned vintage "
                    r"\([^)]*\))",
                 {"clause": "the oldest, scanned vintage (%d: %.0f%% of filings; every later year %.0f\u2013%.0f%%)"
                            % (years[0], rates[years[0]], min(later), max(later))}, "the failure-by-year clause")
    if d_["n"] != flow["working_sample"]:
        raise SystemExit("the outcome regression ran on %d records, not the working sample of %d"
                         % (d_["n"], flow["working_sample"]))
    if d_["abs_S_p"] < 0.05:
        raise SystemExit("the failure-prone indicator is now associated with dispersion given size: 'no such "
                         "association is detected' is false")
    t = _numbers(t, r"over the \$n=(?P<n>\d+)\$ sample, \*\*no such association is\s+detected\*\*",
                 {"n": d_["n"]}, "the outcome-given-size clause")
    if ms["n_orphan_filings"] != b_["n_orphan"]:
        raise SystemExit("the two missingness records count different orphan filings")
    t = _numbers(t, r"\*\*(?P<n>\d+) orphan filings from (?P<s>\d+) syndicates never observed\s+at all\*\*",
                 {"n": ms["n_orphan_filings"], "s": ms["n_orphan_syndicates"]}, "the orphan clause")
    if not (d_["signed_S_failure_prone_coef"] > 0 and d_["signed_S_p"] < 0.05):
        raise SystemExit("failure-prone books no longer run off more adversely: the location clause is false")
    t = _numbers(t, r"There is also a small \*\*location\*\* shift \(failure-prone books run off slightly more\s+"
                    r"adversely\)", {}, "the location clause")
    f0 = ranef["fits"]["mu0_adopted"]["sd_undiv"]["mean"]
    f1 = ranef["fits"]["random_intercept"]["sd_undiv"]["mean"]
    if not f1 < f0:
        raise SystemExit("the random intercepts no longer lower the floor: 'exactly this direction of effect' is false")
    t = _numbers(t, r"the floor moves from about (?P<a>[0-9.]+)%\s+to\s+(?P<b>[0-9.]+)% when partially pooled "
                    r"syndicate intercepts are added",
                 {"a": "%.1f" % (100.0 * f0), "b": "%.1f" % (100.0 * f1)}, "the random-intercept clause")

    # 4: the sample the loader builds
    t = _numbers(t, r"the `n=(?P<n>\d+)` modelling sample", {"n": flow["working_sample"]}, "the loader's sample")
    return t


def write_provenance_clauses(ex):
    return _rw(PROVENANCE, lambda t: provenance_clauses(t, ex))


def write_readme_donor_count(ex):
    """The interactive tool ships the working sample; the README must say how many."""
    n = len(ex["eligibility"]["eligible_for_capital"]["mask_indices"])

    def fn(t):
        return re.sub(r"All data \(\d+ donors\) and Chart\.js are",
                      "All data (%d donors) and Chart.js are" % n, t, count=1)
    return _rw(README, fn)

# The commit the manuscript pins for this repository, and so the state a reader of the
# frozen submission holds. The round-55 correction is stated as the difference from it.
PINNED_ANALYSIS = "9c2895f"
CORRECTION_START = "<!-- round-55-correction:start -->"
CORRECTION_END = "<!-- round-55-correction:end -->"


def _flow_at(commit):
    """The disposition flow recorded at a commit, or None if it cannot be read."""
    out = subprocess.run(["git", "-C", HERE, "show",
                          "%s:model/exposure_results.json" % commit], capture_output=True)
    if not out.stdout:
        return None
    try:
        return json.loads(out.stdout.decode("utf-8"))["disposition_flow"]
    except (ValueError, KeyError):
        return None


def correction_lines(ex):
    """The round-55 data correction, stated as the move from the pinned commit."""
    now = ex["disposition_flow"]
    was = _flow_at(PINNED_ANALYSIS)
    L = ["### The round-55 data correction (10 September 2026)", "",
         "Two extraction rules were corrected and the records they touch were re-extracted "
         "offline from the committed response and table caches: the percentage-against-"
         "monetary decision, which now rests on a table's own unit evidence before any "
         "magnitude heuristic; and the transposed-grid parser, which now captures one basis "
         "block of a page printing a gross and a net triangle under one header and labels it "
         "by that block's own heading. The route by which each record's development figure "
         "was adopted is recorded on the record (`_pyd_route`) instead of being inferred "
         "from a sentence in its notes.", "",
         "**Every record that moved is listed, with its figure and route on both sides, in "
         "`docs/extraction-changelog.md` in the extraction repository** "
         "(<https://github.com/colinpriest/lloyds-reserve-stress-testing>), generated by "
         "`scripts/extraction_changelog.py` by diffing the committed records against the "
         "previous pin. Reports whose page caches cannot serve an offline replay are listed "
         "in `pdf_extraction/audit/offline_unservable.json`; their committed records stand "
         "unchanged.", ""]
    if not was:
        L += ["The counts before the correction could not be read from commit `%s`; "
              "compare the waterfall above with that commit's own "
              "`model/exposure_results.json`." % PINNED_ANALYSIS, ""]
        return L
    a, b = was["to_working_sample"], now["to_working_sample"]
    L += ["What it did to the counts, against the pinned commit `%s`:" % PINNED_ANALYSIS, "",
          "| | at `%s` | now | change |" % PINNED_ANALYSIS,
          "|---|---:|---:|---:|",
          "| Corpus | %d | %d | %+d |" % (was["corpus"], now["corpus"], now["corpus"] - was["corpus"]),
          "| Net or unstated basis | %d | %d | %+d |"
          % (a["net_or_unstated_basis"], b["net_or_unstated_basis"],
             b["net_or_unstated_basis"] - a["net_or_unstated_basis"]),
          "| Unusable severity | %d | %d | %+d |"
          % (a["unusable_severity"], b["unusable_severity"],
             b["unusable_severity"] - a["unusable_severity"]),
          "| Missing premium weights | %d | %d | %+d |"
          % (a["missing_lob_weights"], b["missing_lob_weights"],
             b["missing_lob_weights"] - a["missing_lob_weights"]),
          "| **Working sample** | **%d** | **%d** | **%+d** |"
          % (was["working_sample"], now["working_sample"],
             now["working_sample"] - was["working_sample"]), ""]
    return L


def write_provenance_correction(ex):
    def fn(t):
        block = CORRECTION_START + "\n" + "\n".join(correction_lines(ex)) + CORRECTION_END
        if CORRECTION_START in t:
            a = t.index(CORRECTION_START)
            b = t.index(CORRECTION_END) + len(CORRECTION_END)
            return t[:a] + block + t[b:]
        m = re.search(r"\n## 2b\. ", t)
        if not m:
            raise SystemExit("docs/data-provenance.md: no anchor for the correction block")
        return t[:m.start()] + "\n" + block + "\n" + t[m.start():]
    return _rw(PROVENANCE, fn)


def _repeats(ranked):
    from collections import Counter
    c = Counter(s.split("_")[0] for s, _ in ranked)
    out = []
    for syn, n in sorted(c.items()):
        if n > 1:
            yrs = [s.split("_")[1] for s, _ in ranked if s.startswith(syn + "_")]
            out.append("%s appears in %s" % (syn, " and ".join(yrs)))
    return "; ".join(out) if out else "no repeats at the point estimate"


def referee_section_1(ts):
    a, b, c = ts["a_exceedance_sets"], ts["b_icc"], ts["c_syndicate_block_bootstrap"]
    v995, v99 = a["VaR995"], a["VaR99"]
    icc = b["icc"]
    d995, d99 = c["distinct_syndicates_at_VaR995"], c["distinct_syndicates_at_VaR99"]
    q = c["VaR995"]
    strength = "non-trivial" if icc > 0.1 else "small"
    return "\n".join([
        "## 1. Effective independent support in the Vignette-1 tail (`check_tail_support_syndicate.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_tail_support_syndicate_results.json` at each manifest run.",
        "",
        "**Concern.** Top transferred severities can repeat syndicates, so \"about four donors\" may be",
        "fewer than four independent syndicates.",
        "",
        "**Result** (%s; %d donors, %d syndicates):" % (ts["operator"], ts["n_donors"], ts["n_syndicates"]),
        "",
        "- **(a) Exceedance sets.** VaR99.5: **%d syndicate-years = %d distinct syndicates** (%s; %s)."
        % (v995["n_syndicate_years"], v995["n_distinct_syndicates"],
           ", ".join(s for s, _ in v995["ranked_exceedances"]), _repeats(v995["ranked_exceedances"])),
        "  VaR99: %d syndicate-years = **%d distinct syndicates** (%s)."
        % (v99["n_syndicate_years"], v99["n_distinct_syndicates"], _repeats(v99["ranked_exceedances"])),
        "- **(b) ICC.** Syndicate random-intercept on $z=S/\\hat\\sigma$ (%d syndicates with $\\ge$%d obs, %d observations):"
        % (b["n_syndicates_ge_min"], b["min_obs"], b["n_obs"]),
        "  **ICC = %.3f** ($\\tau_\\alpha^2=%.2f$, $\\sigma_\\varepsilon^2=%.2f$) — **%s** (threshold 0.1)."
        % (icc, b["tau_alpha2"], b["sigma_eps2"], strength),
        "- **(c) Syndicate-block bootstrap** (B=%d, whole syndicates resampled): distinct syndicates"
        % c["B"],
        "  supplying the VaR99.5 exceedances **median %d [%d, %d]**; VaR99 **median %d [%d, %d]**;"
        % (d995["median"], d995["lo2.5"], d995["hi97.5"], d99["median"], d99["lo2.5"], d99["hi97.5"]),
        "  VaR99.5 = %.3f [%.3f, %.3f]." % (q["median"], q["lo2.5"], q["hi97.5"]),
        "",
        "**Decision.** ICC is %s, and under syndicate resampling the effective tail support is"
        % strength,
        "**~%d syndicates [%d–%d]**, not four independent draws. → **Recast the tail-support sentence in"
        % (d995["median"], d995["lo2.5"], d995["hi97.5"]),
        "syndicate units**.",
        "",
        "Vignette 2 is *not* the stronger evidence to promote in its place. Its Δ is a",
        "within-transition contrast whose direction follows from the constrained monotonicity",
        "of the operator in the target's size and concentration: with $\\gamma\\ge0$ and a fixed",
        "old-to-new target the sign is fixed before any data are seen, so it carries no",
        "evidential weight of its own. Its magnitude is informative; its sign is structural.",
        "",
        "---",
        "",
        "",
    ])


def referee_section_2(cu):
    a, n, b = cu["a_sterling"], cu["a_nominal"], cu["b_with_usd_share_covariate"]
    share = cu["usd_share_by_year"]
    yrs = sorted(share)
    beta = b["beta_share"]
    lo, hi = beta["hdi"]
    includes = lo <= 0.0 <= hi
    return "\n".join([
        "## 2. Currency / year-effect entanglement (`check_currency_entanglement.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_currency_entanglement_results.json` at each manifest run.",
        "",
        "**Concern.** USD share trends %.0f%%→%.0f%% and conversion uses the year-end rate, so the sterling"
        % (100 * share[yrs[0]], 100 * share[yrs[-1]]),
        "adjustment is time-correlated and could alias the reserve cycle $m_t$.",
        "",
        "**Result** (directional-shock model = systemic M1; $\\tau_m$ is the standard deviation of the",
        "reporting-year location shock in that model, not the adopted model's floor).",
        "",
        "| | $\\tau_m$ | $k$ |",
        "|---|---|---|",
        "| Sterling (converted) | %.4f | %.3f |" % (a["tau_m"], a["k"]),
        "| Nominal (as-reported) | %.4f | %.3f |" % (n["tau_m"], n["k"]),
        "| Sterling + USD-share year covariate | %.4f | %.3f |" % (b["tau_m"], b["k"]),
        "",
        "- $m_t^{\\text{sterling}}-m_t^{\\text{nominal}}$ correlates **%+.2f** with USD-share$_t$ and"
        % cu["corr_mt_diff_vs_usd_share"],
        "  **%+.2f** with the year-end rate." % cu["corr_mt_diff_vs_year_end_rate"],
        "- USD-share covariate coefficient $\\beta=%+.3f$ **[%.3f, %.3f]** — the interval %s 0;"
        % (beta["mean"], lo, hi, "includes" if includes else "excludes"),
        "  adding it moves $\\tau_m$ from %.4f to %.4f." % (a["tau_m"], b["tau_m"]),
        "",
        "**Decision.** " + ("Three currency treatments were compared on the same sample: sterling"
                            " converted at the reporting-date H.10 rate, nominal as-reported, and"
                            " sterling with the year's USD share as a covariate. $\\tau_m$ and the"
                            " shape of $m_t$ are stable across all three, and the covariate's"
                            " coefficient is unresolved — its interval includes zero. → **Report the"
                            " systemic component as stable under these three treatments.** An"
                            " unresolved coefficient is not a demonstration that currency treatment"
                            " and the reserve cycle are unentangled: stability across three related"
                            " fits and an interval that spans zero are both consistent with an FX"
                            " trend this design cannot separate from the cycle, and the year-end"
                            " conversion date is common to two of the three. Do not state the"
                            " absence of entanglement as a finding."
                            if includes else
                            "the covariate's interval excludes zero: restate the decision from the"
                            " values above before relying on it."),
        "",
        "---",
        "",
        "",
    ])


def referee_section_5(g0):
    full, so = g0["full_operator"], g0["size_only_gamma0"]

    def cell(block, key):
        c = block["centre"][key]
        iv = block["intervals"].get(key)
        return ("%.3f [%.3f, %.3f]" % (c, iv["lo"], iv["hi"])) if iv else "%.3f" % c

    pct = 100.0 * (so["centre"]["V1_v995"] / full["centre"]["V1_v995"] - 1.0)
    return "\n".join([
        "## 5. Size-only ($\\gamma=0$) operator vignette VaRs (`check_gamma0_vignette.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_gamma0_vignette_results.json` at each manifest run.",
        "",
        "**Purpose.** If concentration is reframed as an optional overlay with $\\gamma=0$ default, the",
        "size-plus-floor operator's tail numbers are needed.",
        "",
        "**Result** (centres at the posterior-mean operator; 95% cluster×posterior intervals in brackets):",
        "",
        "| | Full ($\\gamma\\approx%.2f$) | Size-only ($\\gamma=0$) |" % g0["gamma_posterior_mean"],
        "|---|---|---|",
        "| V1 VaR99 | %s | %s |" % (cell(full, "V1_v99"), cell(so, "V1_v99")),
        "| V1 VaR99.5 | %s | %s |" % (cell(full, "V1_v995"), cell(so, "V1_v995")),
        "| V2 Δ99.5 | %s | %s |" % (cell(full, "V2_d995"), cell(so, "V2_d995")),
        "",
        "**Decision.** The $\\gamma=0$ vignette figures are **close** to the full-operator ones (V1 99.5",
        "%.3f vs %.3f, %+.0f%%; V2 Δ %+.3f vs %+.3f), consistent with the small Shapley concentration"
        % (full["centre"]["V1_v995"], so["centre"]["V1_v995"], pct,
           full["centre"]["V2_d995"], so["centre"]["V2_d995"]),
        "effect. → This **quantitatively backs \"a size-only operator is a defensible alternative\"** and",
        "supports presenting $\\gamma=0$ as the default with concentration as an overlay.",
        "",
        "---",
        "",
        "",
    ])


# ── R213 (A9e): the referee record's hand-typed sections, written from their records ─────
#
# Sections 3, 4 and 6-9 and the bookkeeping notes were typed when each check was first run and never regenerated, under
# a status note saying their values had since "moved by a few thousandths". By refit 3 the by-syndicate pooling
# contrast had changed sign, the maturity proxies' coefficients had changed direction, the size-loaded scale model had
# gone from LOO-neutral to predicting worse, and the RITC tail figures had moved from 2.54 to 6.61. Each section is
# written here from its result file, its decision is worded from the current values, and a record that no longer
# supports those words stops the build.

REFEREE_STATUS = "\n".join([
    "> **Status: review record, generated.** This logs the checks requested across successive",
    "> review rounds, each with its pre-agreed decision rule. Every section is written from its",
    "> result file by `src/build_current_results.py` at each manifest run, and each decision is",
    "> worded from the current values: a record that no longer supports a decision's words stops",
    "> the build. Where the decision taken when a check was first run has since been withdrawn, a",
    "> note says so. For the full current results use the generated `docs/current-results.md` in the",
    "> analysis repository; the manuscript governs wherever the two differ. The manuscript does not",
    "> cite this file.",
])


def _p_text(p):
    """A small p-value as a power of ten, a larger one at three decimals."""
    return "p\\approx10^{%d}" % int(math.floor(math.log10(p))) if p < 0.001 else "p=%.3f" % p


def referee_section_3(pcv, cse):
    d, se = pcv["delta_ELPD_M1_minus_M2"], pcv["delta_SE"]
    if abs(d) >= 2.0 * se:
        raise SystemExit("referee section 3: the by-syndicate contrast is %.1f standard errors from zero; 'not "
                         "adjudicated by predictive CV' needs re-reading" % (abs(d) / se))
    bb = dig(cse or {}, "contrasts/composition__vs__k0.5")
    if bb and not bb["bb_2.5"] < 0 < bb["bb_97.5"]:
        raise SystemExit("referee section 3: the Bayesian-bootstrap interval for the free exponent excludes zero")
    lines = [
        "## 3. Pooling comparison under by-syndicate CV (`check_pooling_cv.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_pooling_cv_results.json` and `results/check_cv_clustered_se_results.json` at each manifest run.",
        "",
        "**Concern.** Appendix 3.1 adjudicated M1 (free $k$) vs M2 ($\\sqrt N$+floor, $k$=0.5) on",
        "observation-level PSIS-LOO (optimistic under clustering), whereas the headline comparison uses",
        "5-fold by-syndicate CV.",
        "",
        "**Result** (%d by-syndicate folds; %d syndicate-years from %d syndicates; held-out ELPD):"
        % (pcv["folds"], pcv["n"], pcv["n_syndicates"]),
        "",
        "- ΔELPD(M1 − M2) = **%+.2f, SE %.2f**; M1 has the higher held-out density on **%.0f%%** of"
        % (d, se, pcv["pct_held_out_M1_higher_density"]),
        "  syndicate-years.",
    ]
    if bb:
        lines += [
            "- The Bayesian bootstrap over syndicate totals, the criterion the manuscript rests on: ΔELPD",
            "  (free $k$ − $k=\\tfrac12$+floor) = %+.2f, 95%% credible interval **[%.1f, %.1f]**,"
            % (bb["delta_ELPD"], bb["bb_2.5"], bb["bb_97.5"]),
            "  $P(\\text{free }k\\text{ predicts better}) = %.2f$." % bb["P_first_better"],
        ]
    lines += [
        "",
        "**Decision.** Under the by-syndicate criterion the difference is within two standard errors, and",
        "%s is ahead on the point estimate: the pooling **distinction is not adjudicated by predictive CV**."
        % ("M1" if d > 0 else "M2"),
        "→ State this. **Superseded recommendation:** the original advice here was to rest the claim on",
        "$P(k>0.5)=1.00$. That probability is one by construction: theory bounds $k$ to $[\\tfrac12,1]$ and the",
        "prior keeps it there. The manuscript rests the claim on $k<1$, which the by-syndicate comparison with",
        "fixed $k=1$ establishes; it does not claim $k>\\tfrac12$, and it reports what fixing $k=\\tfrac12$ does",
        "to the transferred stresses.",
        "",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def referee_section_4(sm):
    base, age, dur = sm["k_base"], sm["k_plus_age"], sm["k_plus_log_r_gwp"]
    cra, crd = sm["control_regression_absz"]["plus_age"], sm["control_regression_absz"]["plus_log_r_gwp"]
    moves = [age["k"] - base["k"], dur["k"] - base["k"]]
    biggest = max(abs(x) for x in moves)
    if biggest >= 0.05:
        raise SystemExit("referee section 4: a maturity proxy moves k by %.3f; 'stable to the proxies' needs "
                         "re-reading" % biggest)
    da, dd = age["delta_proxy"], dur["delta_proxy"]

    def row(label, blk, delta):
        return "| %s | %.3f [%.3f, %.3f] | %s |" % (
            label, blk["k"], blk["k_hdi"][0], blk["k_hdi"][1],
            "—" if delta is None else "$\\delta=%+.3f$ [%.3f, %.3f]" % (delta["mean"], delta["hdi"][0], delta["hdi"][1]))

    def interval(delta):
        return ("resolved (its interval excludes zero)" if not delta["hdi"][0] < 0 < delta["hdi"][1]
                else "unresolved (its interval spans zero)")

    if all(x < 0 for x in moves) or all(x > 0 for x in moves):
        lead = "Both proxies move $k$ %s" % ("down" if moves[0] < 0 else "up")
    else:
        lead = "The two proxies move $k$ in opposite directions"
    return "\n".join([
        "## 4. Size–maturity partial confound (`check_size_maturity.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_size_maturity_results.json` at each manifest run.",
        "",
        "**Concern.** Larger books may be more mature/vintage-diversified, so part of the size effect is",
        "maturity.",
        "",
        "**Result** (two weak proxies; $k$ to 3 dp, with 95%% HDI; $n=%d$):" % sm["n"],
        "",
        "| Model | $k$ | proxy coef on log-dispersion |",
        "|---|---|---|",
        row("Base (two-regime)", base, None),
        row("+ age-in-window ($t-$ first observed year)", age, da),
        row("+ log(reserve/GWP)", dur, dd),
        "",
        "Control regression $|z|\\sim\\log R+$ proxy: age coef %+.3f (t=%.2f); log(R/GWP) coef %+.3f (t=%.2f)."
        % (cra["coef_proxy"], cra["t_proxy"], crd["coef_proxy"], crd["t_proxy"]),
        "",
        "**Decision.** %s, by at most %.3f (%.3f and %.3f against %.3f), so neither proxy explains the"
        % (lead, biggest, age["k"], dur["k"], base["k"]),
        "size effect away. The age term's coefficient is %s; the duration term's is %s." % (interval(da), interval(dd)),
        "→ Write \"**$k$ was stable to the available (weak) maturity proxies**\" — not that maturity is ruled out.",
        "*(The decision first recorded here, that the age proxy was negligible and that the duration control moved",
        "$k$ up, was written for an earlier fit and is withdrawn.)*",
        "",
        "---",
        "",
        "",
    ])


def referee_section_6(mz):
    a, b, c = mz["a_ar1"], mz["b_credibly_positive"], mz["c_most_persistent_decile"]
    frac = c["implied_one_year_mean_as_fraction_of_sigma"]
    ar = a["pooled_within_syndicate_ar1"]
    if abs(ar) >= 0.2 or abs(a["per_syndicate_ar1_median"]) >= 0.2:
        raise SystemExit("referee section 6: within-syndicate persistence is no longer weak")
    if b["share_credibly_positive"] >= 0.15 or frac >= 0.25:
        raise SystemExit("referee section 6: the credibly adverse share or the implied one-year mean is no longer small")
    share = 100.0 * b["share_credibly_positive"]
    return "\n".join([
        "## 6. Mean-zero boundary for persistent adverse development (`check_mean_zero_boundary.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_mean_zero_boundary_results.json` at each manifest run.",
        "",
        "**Purpose.** Bound how much fixing $\\mu=0$ could understate stress where development is",
        "persistently adverse.",
        "",
        "**Result.**",
        "",
        "- **(a)** Pooled within-syndicate AR(1) of $S$ = **%+.2f** (median per-syndicate %+.2f, interquartile"
        % (ar, a["per_syndicate_ar1_median"]),
        "  range [%+.2f, %+.2f]; %d syndicates with at least 4 observations) — persistence is **weak**."
        % (a["per_syndicate_ar1_iqr"][0], a["per_syndicate_ar1_iqr"][1], a["n_syndicates_ge4obs"]),
        "- **(b)** Syndicate random-intercept: **%d/%d (%.1f%%)** of syndicates have a credibly positive"
        % (b["credibly_positive"], b["n_syndicates"], share),
        "  (adverse) mean; %d/%d credibly negative." % (b["credibly_negative"], b["n_syndicates"]),
        "- **(c)** Most-persistent decile (%d syndicates): mean $S=%+.3f$, mean $\\sigma=%.3f$ →"
        % (c["n_syndicates"], c["mean_S"], c["mean_sigma"]),
        "  implied one-year mean contribution **≈%.2fσ**." % frac,
        "",
        "**Decision.** Persistence is weak and the credibly-adverse share is small, so **one sentence",
        "conceding the boundary suffices** — but note the small subset (≈%.0f%%) with a persistently" % share,
        "positive mean; in the most persistent decile the $\\mu=0$ stress understates the one-year mean by",
        "about %.2fσ." % frac,
        "",
        "---",
        "",
        "",
    ])


def referee_section_7(het, bmc):
    h0, m4, psi = het["params_h0"], het["params_m4"], het["psi_s"]
    bb = bmc["contrasts"]["hetscale_m4_vs_h0"]
    ppc = het["abs_z_large_tercile_ppc"]
    dk = abs(m4["k"]["mean"] - h0["k"]["mean"])
    if dk >= 0.02:
        raise SystemExit("referee section 7: k moves %.3f under the size-loaded scale; 'stable' needs re-reading" % dk)
    if not psi["hdi_2.5"] < 0 < psi["hdi_97.5"]:
        raise SystemExit("referee section 7: psi_s is now resolved; 'weakly identified' is false")
    if not ppc["inside"]:
        raise SystemExit("referee section 7: the large-tercile |z| diagnostic is outside its band")
    if bb["bb_2.5"] > 0:
        raise SystemExit("referee section 7: the size-loaded scale now predicts better")
    worse = bb["bb_97.5"] < 0
    if worse:
        n_better = int(round(bb["P_first_better"] * bmc["bootstrap_draws"]))
        pred = ("M4 predicts **worse** than the uniform-scale model (ΔELPD %+.2f, Bayesian bootstrap over syndicates"
                " 95%% interval [%.2f, %.2f]; better in %s of the %s bootstrap draws)"
                % (bb["delta_ELPD"], bb["bb_2.5"], bb["bb_97.5"], format(n_better, ","),
                   format(bmc["bootstrap_draws"], ",")))
    else:
        pred = ("M4 is not preferred predictively (ΔELPD %+.2f, Bayesian bootstrap over syndicates 95%% interval"
                " [%.2f, %.2f])" % (bb["delta_ELPD"], bb["bb_2.5"], bb["bb_97.5"]))
    lines = [
        "## 7. Heteroscedastic (size-loaded) scale shock — the last unfitted specification (`calibrate_dispersion_hetscale.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `model/dispersion_calibration_hetscale.json` and `results/check_bayes_model_compare_results.json` at each",
        "> manifest run.",
        "",
        "**Concern.** $k$-robustness had been shown against a size-loaded *mean* shock (M3) but not",
        "against a size-loaded *scale* shock — where large syndicates' scale amplitudes co-move more.",
        "That is where the pooling finding lives and the form shared-slip volatility dependence would",
        "take, so it bears most directly on $k$.",
        "",
        "**Result** (M4: $\\log\\sigma_{it}=(1+\\psi_s\\,\\widetilde{\\log R_{\\text{eff}}})\\,s_t+\\ldots$;",
        "$\\psi_s=0$ = uniform-scale headline H0; $n=%d$):" % het["n"],
        "",
        "| | $k$ | $\\gamma$ | $\\sigma_{\\text{undiv}}$ | $\\psi_s$ | ΔELPD vs H0 |",
        "|---|---|---|---|---|---|",
        "| H0 (uniform scale) | %.3f | %.3f | %.3f | ≡0 | — |"
        % (h0["k"]["mean"], h0["gamma"]["mean"], h0["sd_undiv"]["mean"]),
        "| M4 (size-loaded scale) | **%.3f** [%.3f, %.3f] | %.3f | %.3f | **%+.2f [%.2f, %.2f]** | %+.2f [%.2f, %.2f] |"
        % (m4["k"]["mean"], m4["k"]["hdi_2.5"], m4["k"]["hdi_97.5"], m4["gamma"]["mean"], m4["sd_undiv"]["mean"],
           psi["mean"], psi["hdi_2.5"], psi["hdi_97.5"], bb["delta_ELPD"], bb["bb_2.5"], bb["bb_97.5"]),
        "",
        "- $k$ moves by %.3f (%.3f under H0, %.3f under M4). *(Both probabilities quoted in the original —"
        % (dk, h0["k"]["mean"], m4["k"]["mean"]),
        "  $P(k>0.5)=1.00$ and $P(k<1)=1.00$ — are one by construction: theory bounds $k$ to $[\\tfrac12,1]$",
        "  and the prior keeps it there.)*",
        "- $\\psi_s$ is **weakly identified** (HDI spans 0, $P(\\psi_s>0)=%.2f$), and %s: no evidence that"
        % (het["posterior_prob"]["psi_s_gt_0"], pred),
        "  large syndicates' scales co-move more.",
        "- The matching diagnostic (within-year mean $|z|$ in the large tercile) is already well fit by",
        "  the uniform model (observed %.2f in band [%.2f, %.2f], $p_{\\text{PPC}}=%.2f$) — no scale"
        % (ppc["observed_large_mean_absz"], ppc["band_5_95"][0], ppc["band_5_95"][1], ppc["p_ppc"]),
        "  co-movement excess exists to capture. What drives any remaining co-movement is not identified:",
        "  pair-specific overlap or residual covariance would have to be fitted directly, and is not fitted here.",
        "",
        "**Decision.** $k$ is stable under the heteroscedastic scale shock. All the co-movement models",
        "fitted load a *common* reporting-year factor; pair-specific shared-slip or residual-noise",
        "dependence is not fitted anywhere, so this bounds the common-factor channel only. → Rest the",
        "load-bearing case on **sub-linearity: $k<1$**. *(The original wording here rested it on $P(k<1)=1.00$",
        "\"plus the positive floor\". Both were withdrawn: the probability is tautological on the bracketed",
        "support, and the floor is not predictively separable from a floorless law, so the manuscript retains",
        "it as a structural choice about extrapolation, not as evidence.)* Treat \"above $\\sqrt N$\" as",
        "non-load-bearing: the $\\sqrt N$+floor model (M2) is not distinguished from M1 by by-syndicate CV",
        "(§3 above).",
    ]
    if worse:
        lines += ["*(When first run, this check read M4 as LOO-neutral; at the current fit the size-loaded scale "
                  "predicts worse, so that reading is withdrawn.)*"]
    lines += ["", "---", "", ""]
    return "\n".join(lines)


def referee_section_8(sca, corr):
    raw, wy = sca["a_association_raw"], sca["a_association_within_year"]
    red, sep = sca["b_redundancy"], sca["c_separability"]
    hh = raw["logR_vs_HHI"]
    if not (hh["pearson"] < 0 and abs(hh["pearson"]) < 0.5):
        raise SystemExit("referee section 8: the size-concentration association is no longer modest and negative")
    vif_r, vif_h = red["vif_logR_given_line_and_year"], red["vif_log_inv_line_given_size_and_year"]
    cond = red["condition_number_logR_logH"]
    if not (vif_r < 2.5 and vif_h < 2.5 and cond < 10):
        raise SystemExit("referee section 8: size and concentration now look collinear")
    chi = sep["chi2_size_x_conc_tercile"]
    if chi["cramers_v"] >= 0.3:
        raise SystemExit("referee section 8: the tercile grid's association is no longer weak")
    widths = [dec["HHI_iqr"][1] - dec["HHI_iqr"][0] for dec in sep["hhi_within_size_deciles"]]
    words = [("k_gamma", 0.0 < corr["k_gamma"] < 0.3), ("k_floor", corr["k_floor"] <= -0.4),
             ("k_div", corr["k_div"] >= 0.3), ("gamma_div", corr["gamma_div"] >= 0.3),
             ("gamma_floor", abs(corr["gamma_floor"]) < 0.3)]
    wrong = [key for key, ok in words if not ok]
    if wrong:
        raise SystemExit("referee section 8: the posterior correlations no longer support the words for %s"
                         % ", ".join(wrong))
    return "\n".join([
        "## 8. Size vs concentration: association, redundancy, separability (`check_size_concentration_assoc.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_size_concentration_assoc_results.json` and `model/dispersion_posterior_draws_ritc.npz` at",
        "> each manifest run.",
        "",
        "**Why.** The operator's effective size is $\\log R_{\\text{eff}}=\\log R-\\gamma\\log H$, so $k$ (on",
        "size) and $\\gamma$ (on concentration) are separately identified only if $\\log R$ and $\\log H$",
        "are not collinear. If size and concentration were redundant, the two exponents could not be",
        "told apart. Unit: syndicate-year ($n=%d$)." % sca["n"],
        "",
        "**Result.**",
        "",
        "- **(a) Association** — modest and negative (bigger books slightly less concentrated):",
        "  $\\log R$ vs HHI Pearson **%+.2f** ($%s$), Spearman %+.2f; within reporting year"
        % (hh["pearson"], _p_text(hh["pearson_p"]), hh["spearman"]),
        "  Spearman %+.2f; $\\log R$ vs $\\log(1/H)$ (effective line count) Pearson %+.2f."
        % (wy["logR_vs_HHI_within_year"]["spearman"], raw["logR_vs_log_inv_line"]["pearson"]),
        "- **(b) Redundancy** — essentially none: **VIF($\\log R$)=%.2f, VIF($\\log(1/H)$)=%.2f**" % (vif_r, vif_h),
        "  (with year fixed effects), **condition number of [$\\log R,\\log H$] = %.2f**, and size explains" % cond,
        "  only **$R^2=%.3f$** of HHI. All below the usual collinearity thresholds (VIF<2.5, cond<~10)."
        % red["r2_HHI_on_logR"],
        "- **(c) Separability** — concentration varies at fixed size: **median within-size-decile HHI IQR",
        "  width = %.3f** (between %.2f and %.2f across the %d size deciles). The size×concentration tercile"
        % (sep["median_HHI_iqr_width_within_decile"], min(widths), max(widths), len(widths)),
        "  grid is weakly non-independent ($\\chi^2=%.1f$ on %d degrees of freedom, $%s$, **Cramér's V = %.3f**)."
        % (chi["chi2"], chi["dof"], _p_text(chi["p"]), chi["cramers_v"]),
        "",
        "- **(d) Posterior identification** (from the %s headline draws, `dispersion_posterior_draws_ritc.npz`)."
        % format(corr["draws"], ","),
        "  The data-design checks above concern the *covariates*; the direct question is whether the",
        "  *posterior* of $k$ and $\\gamma$ is entangled. They are weakly and mildly positively correlated:",
        "  $\\text{corr}(k,\\gamma)=\\mathbf{%+.2f}$ (Pearson; %+.2f Spearman). $k$'s real posterior trade-off"
        % (corr["k_gamma"], corr["k_gamma_spearman"]),
        "  is with the floor, $\\text{corr}(k,\\sigma_{\\text{undiv}})=\\mathbf{%+.2f}$, and the diversifiable"
        % corr["k_floor"],
        "  scale, $\\text{corr}(k,\\sigma_{\\text{div}})=%+.2f$; $\\gamma$ in turn trades off with" % corr["k_div"],
        "  $\\sigma_{\\text{div}}$ (%+.2f) and is only weakly correlated with the floor (%+.2f). So $k$ and"
        % (corr["gamma_div"], corr["gamma_floor"]),
        "  $\\gamma$ are close to posterior-separable, and the residual identification tension for $k$ is",
        "  against the size-invariant floor, not concentration.",
        "",
        "**Decision.** Size and concentration are **weakly associated but not redundant**; $k$ and",
        "$\\gamma$ are separately identified — data-side (VIF≈%.1f, condition number %.1f) *and*"
        % (max(vif_r, vif_h), cond),
        "posterior-side ($\\text{corr}(k,\\gamma)=%+.2f$). State the posterior correlation at its value, and note"
        % corr["k_gamma"],
        "that $k$'s main posterior trade-off is with the floor (%+.2f), not $\\gamma$. The modest negative"
        % corr["k_floor"],
        "covariate association (%+.2f) is worth one sentence but does not compromise separability." % hh["pearson"],
        "",
        "---",
        "",
        "",
    ])


def referee_section_9(tc, mz, ranef):
    a, raw, b = tc["a_lag1_demeaned"], tc["a_lag1_raw_level"], tc["b_lag2"]
    c, d = tc["c_direction_persistence"], tc["d_effective_sample"]
    lo, hi = a["block_bootstrap_ci95"]
    if not (lo < 0 < hi and a["permutation_p_two_sided"] > 0.05):
        raise SystemExit("referee section 9: a residual lag-1 association is now detected")
    if not 0.2 <= raw["spearman"] < 0.7:
        raise SystemExit("referee section 9: the raw-level Spearman is no longer moderate")
    if not (c["share_same_sign"] > 0.5 and c["binomial_p_vs_50pct"] < 0.001):
        raise SystemExit("referee section 9: direction persistence is no longer resolved")
    if not (b["pearson"] < 0.1 and b["spearman"] < 0.1):
        raise SystemExit("referee section 9: lag-2 now shows positive persistence")
    tau = dig(ranef or {}, "tau_alpha_vs_scale/tau_alpha")
    if tau is None:
        raise SystemExit("referee section 9: the random-intercept scale is not recorded")
    share = 100.0 * mz["b_credibly_positive"]["share_credibly_positive"]
    frac = mz["c_most_persistent_decile"]["implied_one_year_mean_as_fraction_of_sigma"]
    return "\n".join([
        "## 9. Temporal correlation of PYD severity across consecutive years (`check_pyd_temporal_correlation.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_pyd_temporal_correlation_results.json` (with `results/check_mean_zero_boundary_results.json`",
        "> and `results/check_syndicate_random_effect_results.json` for the cross-references) at each manifest run.",
        "",
        "**Why.** The pooling likelihood treats a syndicate's yearly severities as conditionally",
        "independent given size/HHI (with $\\mu=0$). Strong within-syndicate serial correlation in",
        "$S=\\text{PYD}/\\text{reserves}$ would violate that and shrink the effective sample. Unit:",
        "consecutive-year pairs within syndicate (%d syndicates ≥3 obs, %d lag-1 pairs)."
        % (tc["n_syndicates_ge3obs"], tc["n_lag1_pairs"]),
        "",
        "**Result.**",
        "",
        "- **Lag-1, de-meaned within syndicate** (the *dynamic* component): Pearson **%+.3f**" % a["pearson"],
        "  [%+.2f, %+.2f] (syndicate block bootstrap), Spearman %+.3f, within-syndicate permutation"
        % (lo, hi, a["spearman"]),
        "  **p = %.2f** — indistinguishable from zero. Implied variance-inflation" % a["permutation_p_two_sided"],
        "  $(1+\\rho)/(1-\\rho)=%.2f$ — a point diagnostic under the fitted lag-1 structure, not an established"
        % d["variance_inflation_1plusrho_over_1minusrho"],
        "  absence of effective-sample loss.",
        "- **Lag-1, raw level** (not de-meaned): Pearson %+.2f, Spearman **%+.2f** — moderate, but this is"
        % (raw["pearson"], raw["spearman"]),
        "  the *persistent per-syndicate level* (sign), not dynamics.",
        "- **Direction persistence**: **%.1f%%** of consecutive pairs share the sign of PYD (%d pairs,"
        % (100.0 * c["share_same_sign"], c["n_pairs"]),
        "  binomial $p<0.001$) — releasers keep releasing.",
        "- **Lag-2 de-meaned**: Pearson %+.2f, Spearman %+.2f (no positive persistence at two years)."
        % (b["pearson"], b["spearman"]),
        "",
        "**Decision.** The within-syndicate temporal structure is a **persistent level (sign) effect,",
        "not serial dependence detectable in the fluctuations**: once each syndicate's mean is",
        "removed, **no positive residual lag-1 association is detected** (Pearson $%+.3f$" % a["pearson"],
        "$[%+.2f,%+.2f]$, permutation $p=%.2f$). That is a non-detection, not a demonstration of"
        % (lo, hi, a["permutation_p_two_sided"]),
        "conditional independence. So the pooling likelihood's conditional-independence assumption is",
        "**not contradicted** for the *dispersion* process — a failure to detect, not a demonstration that",
        "it holds — and the persistent syndicate intercept is material when tested directly",
        "($\\tau_\\alpha=%.3f$); the only serial feature is the persistent per-syndicate mean, which is exactly"
        % tau,
        "the $\\mu=0$ boundary already bounded in §6 (%.0f%% credibly-positive means, about %.2fσ a year in the"
        % (share, frac),
        "most-persistent decile). Report the raw Spearman %.2f and its decomposition so the persistence is not"
        % raw["spearman"],
        "mistaken for a dynamic AR effect the model omits.",
        "",
        "---",
        "",
        "",
    ])


def referee_bookkeeping(ex, m0, register, rts, ts):
    flow = ex["disposition_flow"]
    ws = flow["working_sample"]
    if not flow.get("working_sample_equals_eligible_for_capital"):
        raise SystemExit("referee bookkeeping: the working sample no longer equals the donor-pool filter's output")
    if m0.get("n") != ws or ts.get("n_donors") != ws:
        raise SystemExit("referee bookkeeping: the fit sample (%s), the donor pool (%s) and the working sample (%d) "
                         "differ" % (m0.get("n"), ts.get("n_donors"), ws))
    entry = (register or {}).get("2015_2014") or {}
    rec = [o for o in ex["observations"] if int(o["syndicate"]) == 2015 and int(o["year"]) == 2014]
    if entry.get("basis") != "net" or not rec or rec[0].get("pyd_basis") != "net":
        raise SystemExit("referee bookkeeping: syndicate 2015's 2014 record is no longer a net-basis exclusion")
    calib, n5 = rts["CALIB (working sample)"], rts["N5 (rescaling pop)"]
    if calib["meta"]["n"] != ws:
        raise SystemExit("referee bookkeeping: the CALIB tail-shape population is not the working sample")
    t_c, t_5 = calib["tests"]["Student-t nu (MLE)"], n5["tests"]["Student-t nu (MLE)"]
    return "\n".join([
        "## Bookkeeping (labels, not re-runs)",
        "",
        "> Generated block: written by `src/build_current_results.py` from `model/exposure_results.json`,",
        "> `data/pyd_basis_register.json`, `model/dispersion_calibration_ritc.json` and",
        "> `results/ritc_tail_shape_results.json` at each manifest run.",
        "",
        "- **Donor pool = fit sample.** The $n=%d$ dispersion-fit sample and the transfer pool" % ws,
        "  coincide: the one syndicate-year the donor-pool filter's `eligible_for_capital` (N4) guard",
        "  used to drop (**syndicate 2015, year 2014**, the earlier 789-vs-790 gap) is a net-basis",
        "  record and leaves at the basis step (`data/pyd_basis_register.json`), so the guard excludes",
        "  nothing.",
        "- **Three $\\nu_{\\text{RITC}}$ figures.** Different estimators on different populations:",
        "  **%.2f** = headline two-regime Bayesian model, the posterior mean of $\\nu_{\\text{clean}}\\!\\cdot\\!e^{-\\lambda}$, full"
        % m0["nu_ritc"],
        "  $n=%d$ (`calibrate_dispersion_ritc`); **%.2f** = direct Student-t MLE on the %d flagged residuals"
        % (ws, t_c["ritc"], calib["meta"]["ritc"]),
        "  of the same $n=%d$ CALIB population (`ritc_tail_shape`, \"CALIB\"); **%.2f** = direct MLE on the"
        % (calib["meta"]["n"], t_5["ritc"]),
        "  %d flagged residuals of the strict rescaling population $n=%d$ (`ritc_tail_shape`, \"N5\")."
        % (n5["meta"]["ritc"], n5["meta"]["n"]),
        "  Label each population in the text (the round-54 record gave 2.54 / 1.23 / 1.10 on $n=678$ and",
        "  $n=347$; the round before, 2.32 / 2.16 / 1.99 on $n=679$ / $n=388$).",
        "",
    ])


REFEREE_RECORDS = {
    "ts": (RESULTS, "check_tail_support_syndicate_results.json"),
    "cu": (RESULTS, "check_currency_entanglement_results.json"),
    "g0": (RESULTS, "check_gamma0_vignette_results.json"),
    "pcv": (RESULTS, "check_pooling_cv_results.json"),
    "cse": (RESULTS, "check_cv_clustered_se_results.json"),
    "sm": (RESULTS, "check_size_maturity_results.json"),
    "mz": (RESULTS, "check_mean_zero_boundary_results.json"),
    "het": (MODEL, "dispersion_calibration_hetscale.json"),
    "bmc": (RESULTS, "check_bayes_model_compare_results.json"),
    "sca": (RESULTS, "check_size_concentration_assoc_results.json"),
    "tc": (RESULTS, "check_pyd_temporal_correlation_results.json"),
    "ranef": (RESULTS, "check_syndicate_random_effect_results.json"),
    "m0": (MODEL, "dispersion_calibration_ritc.json"),
    "ex": (MODEL, "exposure_results.json"),
    "rts": (RESULTS, "ritc_tail_shape_results.json"),
    "register": (HERE, "data", "pyd_basis_register.json"),
}


def referee_records():
    import numpy as np
    out = {}
    for key, parts in REFEREE_RECORDS.items():
        out[key] = load(*parts)
        if out[key] is None:
            raise SystemExit("referee blocks: %s is missing" % "/".join(parts[1:]))
    draws = np.load(os.path.join(MODEL, "dispersion_posterior_draws_ritc.npz"))

    def pearson(a, b):
        return float(np.corrcoef(np.asarray(draws[a], float), np.asarray(draws[b], float))[0, 1])

    def ranks(x):
        return np.argsort(np.argsort(np.asarray(x, float))).astype(float)

    out["corr"] = {"k_gamma": pearson("k", "gamma"), "k_floor": pearson("k", "sd_undiv"),
                   "k_div": pearson("k", "sd_div"), "gamma_div": pearson("gamma", "sd_div"),
                   "gamma_floor": pearson("gamma", "sd_undiv"),
                   "k_gamma_spearman": float(np.corrcoef(ranks(draws["k"]), ranks(draws["gamma"]))[0, 1]),
                   "draws": int(len(draws["k"]))}
    return out


def referee_text(t, r=None):
    """The whole referee record from its records; each block must be found exactly once."""
    r = r or referee_records()
    subs = (
        (r"> \*\*Status: .*?(?=\n\n9 checks)", REFEREE_STATUS),
        (r"## 1\. Effective independent support.*?(?=## 3\. )", referee_section_1(r["ts"]) + referee_section_2(r["cu"])),
        (r"## 3\. Pooling comparison.*?(?=## 4\. )", referee_section_3(r["pcv"], r["cse"])),
        (r"## 4\. Size.maturity.*?(?=## 5\. )", referee_section_4(r["sm"])),
        (r"## 5\. Size-only.*?(?=## 6\. )", referee_section_5(r["g0"])),
        (r"## 6\. Mean-zero boundary.*?(?=## 7\. )", referee_section_6(r["mz"])),
        (r"## 7\. Heteroscedastic.*?(?=## 8\. )", referee_section_7(r["het"], r["bmc"])),
        (r"## 8\. Size vs concentration.*?(?=## 9\. )", referee_section_8(r["sca"], r["corr"])),
        (r"## 9\. Temporal correlation.*?(?=## Bookkeeping)", referee_section_9(r["tc"], r["mz"], r["ranef"])),
        (r"## Bookkeeping.*\Z", referee_bookkeeping(r["ex"], r["m0"], r["register"], r["rts"], r["ts"])),
    )
    for pattern, body in subs:
        t, n = re.subn(pattern, lambda m, body=body: body, t, count=1, flags=re.S)
        if n != 1:
            raise SystemExit("docs/referee-checks.md: no block matching %r" % pattern[:48])
    return t


def write_referee_blocks():
    return _rw(REFEREE, lambda t: referee_text(t))


if __name__ == "__main__":
    raise SystemExit(main())
