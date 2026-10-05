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
import glob
import io
import json
import math
import os
import re
import subprocess
import assumed_business
import market_active
import transfer_operator

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


#: the paper's rule for a posterior probability (review M-4): within this distance of its prior mass it is not read as
#: evidence either way
PRIOR_CLOSE = 0.05


def posterior_rows(m0):
    """The table of what the posterior does and does not settle: each posterior probability beside the prior mass the
    calibration records for the same event (model/dispersion_calibration_ritc.json prior_prob), and no direction read
    from a probability within PRIOR_CLOSE of its prior. Round 62's verification (N-V-A-6) found
    P(nu_RITC < nu_clean) = 0.496 printed as "RITC tail lighter in this fit" against a prior mass of 0.500, and two
    more probabilities printed without their prior masses."""
    post, prior = m0.get("posterior_prob") or {}, m0.get("prior_prob") or {}

    def pair(key):
        if post.get(key) is None or prior.get(key) is None:
            raise SystemExit("the calibration records no %s for P(%s): the table cannot be written"
                             % ("posterior" if post.get(key) is None else "prior mass", key))
        return post[key], prior[key]

    def moved(p, q):
        return abs(p - q) >= PRIOR_CLOSE

    rows = ["| Statement | Posterior | Prior | Status |", "|---|---:|---:|---|"]
    p, q = pair("nu_ritc_lt_nu_clean")
    if moved(p, q):
        order = ("the data move it %s its prior mass, so the RITC tail reads as the %s"
                 % ("above" if p > q else "below", "heavier" if p > q else "lighter"))
    else:
        order = ("within %.2f of its prior mass: the data do not settle the order of the two tail indices"
                 % PRIOR_CLOSE)
    rows.append(r"| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | %.3f | %.3f | %s; the ordering is not imposed (the "
                r"prior on $\lambda_{\text{RITC}}$ admits both signs) |" % (p, q, order))
    p, q = pair("nu_ritc_lt_2")
    rows.append(r"| $P(\nu_{\text{RITC}} < 2)$ | %.3f | %.3f | posterior probability that the RITC regime lacks a "
                "finite variance%s |" % (p, q, "" if moved(p, q) else
                                         "; within %.2f of its prior mass, so its size is the prior's, not a finding"
                                         % PRIOR_CLOSE))
    rows.append("| $P(k > \\tfrac12)$, $P(k < 1)$ | $1$ by construction | $1$ | theory bounds $k$ to $[\\tfrac12,1]$ "
                "(finite-variance independent $\\sqrt N$ pooling to comonotonic pooling) and the prior keeps it "
                "there, so these are not findings; the endpoints are scored by syndicate as fixed alternatives |")
    p, q = pair("beta_ritc_gt_0.1_abs")
    rows.append(r"| $P(|\beta_{\text{RITC}}| > 0.1)$ | %.3f | %.3f | %s; fitted in the likelihood, and the transfer "
                "operator omits it, not shown to be zero |"
                % (p, q, ("the data move it %s its prior mass" % ("above" if p > q else "below")) if moved(p, q)
                   else "within %.2f of its prior mass" % PRIOR_CLOSE))
    return rows


def exponent_question(khalf):
    """R214 (the owner's decision of 15 September 2026): theory bounds k to [1/2, 1] and the prior keeps it there, so
    the open question is where k lies inside the bracket. It is written from the k = 1/2 sensitivity's record, and a
    k = 1/2 fit that did not sample cleanly refuses it."""
    fit = (khalf or {}).get("k_half_fit") or {}
    pct = dig(khalf or {}, "vignettes/centre_pct_change/V1_v995")
    ratio = (khalf or {}).get("size_ratio_100_2000") or {}
    headline = (khalf or {}).get("size_ratio_100_2000_size_only") or {}
    if pct is None or "adopted" not in ratio or "k_half" not in ratio:
        raise SystemExit("the k = 1/2 sensitivity is not recorded: the open question on k cannot be written")
    # round 62's verification (N-V-A-4): the ratio printed was the concentration overlay's scale law at H = 0.4 and
    # the sentence named neither; each ratio is now printed under the operator whose scale law it is
    if (dig(khalf, "vignettes/operator") != "size_only" or headline.get("operator") != "size_only"
            or ratio.get("operator") != "overlay" or "adopted" not in headline or "k_half" not in headline):
        raise SystemExit("the k = 1/2 sensitivity does not record the size ratio under each operator")
    diag = fit.get("diagnostics") or {}
    if diag.get("divergences") != 0 or not diag.get("max_rhat", 9.0) <= 1.01:
        raise SystemExit("the k = 1/2 fit did not sample cleanly: its figures cannot be written")
    return ("the exact value of $k$ inside its theoretical bracket $[\\tfrac12, 1]$: fixing $k = \\tfrac12$ moves "
            "Vignette 1's VaR$_{99.5}$ by %+.1f%% under the size-only headline operator, and the 100m/2,000m scale "
            "ratio from %.2f to %.2f under that operator (the same at every $H$) and from %.2f to %.2f under the "
            "concentration overlay at $H = %.1f$;"
            % (pct, headline["adopted"], headline["k_half"], ratio["adopted"], ratio["k_half"], ratio["H"]))


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
    # the A+/L1 review (B-01, C-F1): the score is stated as Supplement S4 and Table 18 state it, the model without the
    # share against the model with it; "scores ... higher" refuses when that difference is not positive
    if not -r["delta_ELPD"] > 0:
        raise SystemExit("the composition model without the long-tail share no longer scores higher: rewrite the open "
                         "question")
    return ("whether the long-tail share matters for transfer: its slope is resolved positive (%s) but it does not "
            "improve prediction of unseen syndicates (the composition model without the share scores $%+.1f$ higher "
            "by-syndicate held-out ELPD than with it, Bayesian-bootstrap 95%% credible interval $[%+.1f, %+.1f]$, "
            "$P = %.2f$ that the model without it predicts better), and the operator does not carry it;"
            % (slope, -r["delta_ELPD"], -r["bb_97.5"], -r["bb_2.5"], 1.0 - r["P_first_better"]))


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
    for line in posterior_rows(m0):
        A(line)
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
          "analysis, so these simulations diagnose that common-factor channel only; "
          "they do not bound residual dependence.")
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
        A("Source: `results/missingness_check_results.json`. Every filing is assigned "
          "one inferential disposition before any selection diagnostic is calculated.")
        A("")
        disp = miss["disposition_counts"]
        A("- Of %s filings: **%s** have no eligible outcome structurally, **%s** have "
          "economic eligibility unresolved because the extraction has no deterministic reading of them "
          "(its parsers found no prior-year figure and its models were not run, which says nothing about "
          "the filings), **%s** are scientific exclusions, **%s** have an eligible but unavailable outcome, "
          "**%s** have the outcome but no usable composition, and **%s** enter the model."
          % (miss["n_filings"], disp["structural_no_eligible_outcome"],
             disp["eligibility_unresolved"], disp["scientific_exclusion"],
             disp["eligible_outcome_unavailable"],
             disp["eligible_observed_composition_unavailable"], disp["working_sample"]))
        sel = miss["model_sample_selection_by_size"]
        A("- The response is membership in the %s-record model sample within the "
          "%s-record supported disclosure-defined target. The broader potential target is "
          "%s if all unresolved filings were eligible. Included records have median size "
          "£%sm, against £%sm for target-population records not included (%s)."
          % (miss["n_model_sample"], miss["n_supported_target_population"],
             miss["n_broader_potential_target_if_all_unresolved_eligible"],
             f(sel["median_size_included"], 1),
             f(sel["median_size_not_included"], 1), rank_test_text(sel["mann_whitney_p"])))
        A(scientific_exclusion_sentence(miss))
        A(withdrawn_grouping_sentence(disp))
        A("")
        sens = load(RESULTS, "check_missingness_sensitivity_results.json")
        A("Three sensitivities are reported instead of resting on it. %s See the manuscript for all three."
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
             # P-9 and P-6 (the review of 2 October 2026): the loader's tests, in their words
             "incomplete_no_development_record": "no usable development reading", "in_runoff": "in run-off",
             "no_reserves": "no reserves above the floor"}
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
README = os.path.join(HERE, "README.md")


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


def _retrieved_by_year():
    """Filings retrieved by reporting year: the extraction's record files, one per filing."""
    out = {}
    for path in glob.glob(os.path.join(HERE, "pdf_extraction", "syndicate_*_[0-9][0-9][0-9][0-9].json")):
        y = int(os.path.basename(path)[:-len(".json")].rsplit("_", 1)[1])
        out[y] = out.get(y, 0) + 1
    return out


def _active_by_year():
    """Active syndicates by year, as every coverage figure reads them (market_active.py)."""
    return market_active.active_by_year()


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
        "  register `pdf_extraction/audit/portfolio_transfer_adjudication.json` and the take-ons",
        "  two readings confirmed (`data/opening_reserves_takeon_base.json`, R221) confirm **%d**"
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
    # the recent years' retrieval against the market, generated (FOLLOWUP5 item 7: the range was typed), and the
    # other years' rates rounded as the paper rounds them (item 7b: int() printed 2021's 57.6% as 57%)
    recent = [y for y in years if 2020 <= y <= 2024]
    got = _retrieved_by_year()
    return [
        "Coverage is **%d %% of active syndicate-years overall** (%d of %d; it was ~47 %% on the"
        % (round(100.0 * total_samp / total_active), total_samp, total_active),
        "old dataset), and it is **uneven, not flat**: the annual rate runs from **%d %% in %d (%d of"
        % (round(rates[worst]), worst, samp[worst]),
        "%d)** to **%d %% in %d**, with every other year between %d %% and %d %%. The 2020\u20132024 retrieval"
        % (active[worst], round(rates[best]), best, round(min(mid)), round(max(mid))),
        "gap in the old dataset is closed (%d\u2013%d PDFs retrieved per year in 2020\u20132024 vs %d\u2013%d active "
        "syndicates)," % (min(got.get(y, 0) for y in recent), max(got.get(y, 0) for y in recent),
                          min(active[y] for y in recent), max(active[y] for y in recent)),
    ]


def _material_moves(lo, hi):
    """The eligible-outcome stress says two parameters move materially. The thresholds (0.05 on the concentration
    exponent, 0.5 on the clean tail index) are where that stops being a fair reading of the record; the generator
    refuses the words below either."""
    dg = abs(hi["gamma"]["mean"] - lo["gamma"]["mean"])
    dnu = abs(hi["nu_clean"]["mean"] - lo["nu_clean"]["mean"])
    if dg < 0.05 or dnu < 0.5:
        raise SystemExit("eligible-outcome stress: gamma moves %.3f and the clean tail %.2f; 'move materially' needs re-reading "
                         "against the record" % (dg, dnu))


def _weighting(ms):
    """The weighting fits and the larger move of gamma and the floor under it. R213: refit 3's weighting moves k from
    0.565 to 0.591, so refit 1's 'leaves the fit essentially unchanged' became false."""
    un, ipw = ms["fits"]["unweighted"], ms["fits"]["ipw_model_sample"]
    if ms["propensity_model"]["coef_logR"] <= 0:
        raise SystemExit("the response propensity no longer rises with size: 'confirms the size gradient' is false")
    within = max(abs(ipw["gamma"]["mean"] - un["gamma"]["mean"]),
                 abs(ipw["sd_undiv"]["mean"] - un["sd_undiv"]["mean"]))
    return un, ipw, within


#: what each scientific-exclusion detail says (the words generate_data_audit prints for the same details); a detail not
#: listed is printed under its own name, so a new one cannot vanish from the count
SCIENTIFIC_DETAIL_WORDS = {
    "in_runoff": "a run-off year",
    "non_gross_or_unstated_development": "development on a net or unstated basis",
    "no_positive_reserve_base": "no opening-reserve base above the floor",
    "takeon_not_development": "adjudicated a take-on, not development",
    "provision_movement_not_development": "adjudicated a movement in the provision, not development",
    "mix_names_no_line_of_business": "the extracted premium mix names no line of business (a contract form or "
                                     "distribution channels only; scope)",
    "life_book": "the extracted premium mix is life business (scope)",
}


def scientific_exclusion_sentence(miss):
    """The scientific exclusions by detail, the two scope exclusions (D3-1) beside the others and counted apart from
    them, with the records left as composition unavailable because the extraction lost the lines (another model's
    reading names one, or the filing prints premium by line: the reviews of 4 and 5 October 2026). The counts come from
    the missingness record."""
    details = miss["scientific_exclusion_detail_counts"]
    scope = miss["composition_scope_exclusion_counts"]
    reasons = miss["composition_unavailable_reason_counts"]
    parts = ["%d %s" % (n, SCIENTIFIC_DETAIL_WORDS.get(d, d))
             for d, n in sorted(details.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ("- The %d scientific exclusions are, by detail: %s. %d of them are scope exclusions: a record is out of "
            "scope only if its filing prints no premium amount for any non-life line of business (life books are "
            "out of scope as life business; a page reading of the filing "
            "decides, and outranks the models' readings in both directions). %d records stay in the target as "
            "composition unavailable because the filing prints premium by line although every model's mix names none "
            "(the extraction lost the lines), and %d because another model's reading names a line the adopted block's "
            "mix lost, for a record no page has been read for; they get no weights."
            % (sum(details.values()), "; ".join(parts), sum(scope.values()), reasons.get("extraction_lost_lines", 0),
               reasons.get("readers_disagree", 0)))


def withdrawn_grouping_sentence(disp):
    """The withdrawn structural grouping, with the count of records the extraction did not read from the inferential
    partition. The count was typed as 58 and stayed 58 when round 62's records (extraction d9f2bdee) made it 45; the
    records were called "no-disclosure" records, a claim about filings nobody read (round 62's verification, MAT-2)."""
    return ("- The former 128-case structural grouping is withdrawn: the %d records with no deterministic reading "
            "(the extraction's parsers found no prior-year figure and its models were not run) establish only that "
            "the extraction did not read them, not economic ineligibility. Missing-at-random cannot be established."
            % disp["eligibility_unresolved"])


def sensitivity_sentences(ms, m0):
    """The three missingness sensitivities, worded from their generated record. The broader stress's counts are the
    record's: they were typed as 58 and 12 and stayed so when round 62's records made the first 45."""
    un, ipw, within = _weighting(ms)
    k0 = m0.get("k") if m0.get("k") is not None else dig(m0, "params/k/mean")
    if "%.3f" % un["k"]["mean"] != "%.3f" % k0:
        raise SystemExit("the unweighted missingness fit is not the adopted fit (k %.3f against %.3f)"
                         % (un["k"]["mean"], k0))
    byc = ms["eligible_outcome_stress"]["by_c"]
    cs = sorted(byc, key=float)
    lo, hi = byc[cs[0]], byc[cs[-1]]
    _material_moves(lo, hi)
    ks = [byc[c]["k"]["mean"] for c in cs]
    stress = ms["eligibility_unresolved_stress"]
    broad = stress["by_c"]
    bc = sorted(broad, key=float)
    if stress["n_pseudo"] != stress["n_eligibility_unresolved"] + stress["n_known_eligible_unavailable"]:
        raise SystemExit("the broader stress's records are not its unresolved filings plus the known unavailable "
                         "outcomes (%d against %d + %d)" % (stress["n_pseudo"], stress["n_eligibility_unresolved"],
                                                            stress["n_known_eligible_unavailable"]))
    if "%.3f" % ipw["k"]["mean"] == "%.3f" % un["k"]["mean"]:
        move = "leaves the pooling exponent at $k = %.3f$" % un["k"]["mean"]
    else:
        move = "moves the pooling exponent from $k = %.3f$ to $%.3f$" % (un["k"]["mean"], ipw["k"]["mean"])
    return [
        "Bounded inverse-probability weighting with the disclosed 0.15 probability floor %s and leaves "
        "the concentration exponent and the floor within %.3f of the adopted fit; 0.10 and 0.20 cap "
        "fits report the cap sensitivity, and intervals condition on the fitted weights." % (move, within),
        "The high-volatility eligible-outcome stress moves the conditional bracketed estimate from $k = %.3f$ at $c=%g$ to "
        "$%.3f$ at $c=%g$, between $%.3f$ and $%.3f$ across the grid --- a construction that makes the "
        "predominantly small missing books more volatile, so it cannot test the adverse-to-sub-linearity "
        "direction --- and moves the concentration exponent and the clean-regime tail materially, so the tail "
        "is **not** unaffected." % (lo["k"]["mean"], float(cs[0]), hi["k"]["mean"], float(cs[-1]), min(ks), max(ks)),
        "A separate broader-potential-target stress assumes all %d eligibility-unresolved filings were "
        "eligible, appends them with the %d known unavailable outcomes, and moves $k$ from $%.3f$ at "
        "$c=%g$ to $%.3f$ at $c=%g$; it is not a bound or an eligibility estimate."
        % (stress["n_eligibility_unresolved"], stress["n_known_eligible_unavailable"],
           broad[bc[0]]["k"]["mean"], float(bc[0]), broad[bc[-1]]["k"]["mean"], float(bc[-1])),
    ]


def _missingness_lines_legacy():
    """Retained only for historical diff context; the active producer is below."""
    with io.open(os.path.join(HERE, "results",
                              "check_missingness_sensitivity_results.json"), encoding="utf-8") as fh:
        ms = json.load(fh)
    un, ipw, within = _weighting(ms)
    prop = ms["propensity_model"]
    byc = ms["eligible_outcome_stress"]["by_c"]
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
        "  $\\operatorname{logit}P(\\text{model-sample membership})\\sim\\log R+\\text{year}$ measures selection",
        "  gradient (coefficient on $\\log R$ $%+.2f$). Refitting with each observation weighted"
        % prop["coef_logR"],
        "  by the mean-one bounded rule with probability floor 0.15 \u2014 up-weighting small syndicates by up to $%.1f\\times$ \u2014 %s"
        % (prop["primary_diagnostics"]["weight_max"], verb),
        "  $k=%.3f$ $[%.3f,%.3f]$ against $%.3f$ $[%.3f,%.3f]$ and leaves $\\gamma$ ($%.3f$ against"
        % (m(ipw, "k"), ipw["k"]["hdi_2.5"], ipw["k"]["hdi_97.5"],
           m(un, "k"), un["k"]["hdi_2.5"], un["k"]["hdi_97.5"], m(ipw, "gamma")),
        "  $%.3f$) and the floor ($%.3f$ against $%.3f$) within $%.3f$ of the unweighted fit;"
        % (m(un, "gamma"), m(ipw, "sd_undiv"), m(un, "sd_undiv"), within),
        "  $\\nu_{\\text{clean}}=%.2f$ against $%.2f$." % (m(ipw, "nu_clean"), m(un, "nu_clean")),
        "- **High-volatility eligible-outcome stress.** Appending only the %d records whose outcome is"
        % ms["eligible_outcome_stress"]["n_pseudo"],
        "  eligible but unavailable moves the conditional bracketed estimate from $k=%.3f$"
        % m(lo, "k"),
        "  at $c=%g$ to $%.3f$ at $c=%g$, between $%.3f$ and $%.3f$ across the grid. Because the"
        % (float(cs[0]), m(hi, "k"), float(cs[-1]), min(ks), max(ks)),
        "  construction makes those unavailable outcomes *more* volatile, it cannot",
        "  test the adverse-to-sub-linearity direction. Two parameters move",
        "  materially: the concentration exponent $%.3f\\to%.3f$ and the **clean-regime tail"
        % (m(lo, "gamma"), m(hi, "gamma")),
        "  $\\nu_{\\text{clean}}$ from $%.2f$ to $%.2f$** at $c=%g$. The tail is therefore *not*"
        % (m(lo, "nu_clean"), m(hi, "nu_clean"), float(cs[-1])),
        "  unaffected, and neither the tail nor the vignette VaRs should be described as such. Structural",
        "  stubs and scientific exclusions receive no synthetic outcome; this is not a bound.",
    ]


def missingness_lines():
    """The three selection sensitivities, from the generated sensitivity record."""
    with io.open(os.path.join(HERE, "results",
                              "check_missingness_sensitivity_results.json"), encoding="utf-8") as fh:
        ms = json.load(fh)
    un, ipw, _within = _weighting(ms)
    prop = ms["propensity_model"]
    primary = prop["primary_diagnostics"]
    uncapped = prop["uncapped_diagnostic_not_fitted"]
    byc = ms["eligible_outcome_stress"]["by_c"]
    cs = sorted(byc, key=float)
    lo, hi = byc[cs[0]], byc[cs[-1]]
    _material_moves(lo, hi)
    ks = [byc[c]["k"]["mean"] for c in cs]
    broad = ms["eligibility_unresolved_stress"]["by_c"]

    def m(block, key):
        return block[key]["mean"]

    verb = ("leaves the pooling exponent at" if "%.3f" % m(ipw, "k") == "%.3f" % m(un, "k")
            else "moves the pooling exponent to")
    return [
        "- **Bounded selection weighting (IPW).** Response propensity",
        "  $\\operatorname{logit}P(\\text{model-sample membership})\\sim\\log R+\\text{year}$ measures selection",
        "  gradient (coefficient on $\\log R$ $%+.2f$). Refitting with each observation weighted"
        % prop["coef_logR"],
        "  by $[1/\\max(\\hat p,0.15)]/\\operatorname{mean}[1/\\max(\\hat p,0.15)]$ — %s"
        % verb,
        "  $k=%.3f$ $[%.3f,%.3f]$ against $%.3f$ $[%.3f,%.3f]$. %d of %d model"
        % (m(ipw, "k"), ipw["k"]["hdi_2.5"], ipw["k"]["hdi_97.5"],
           m(un, "k"), un["k"]["hdi_2.5"], un["k"]["hdi_97.5"],
           primary["n_below_cap"], ms["n_model_sample"]),
        "  records lie below the 0.15 floor; $\\hat p_{\\min}=%.4f$, the mean-one weights span"
        % prop["p_hat_min"],
        "  %.2f--%.2f and have descriptive Kish ESS %.0f. Uncapped diagnostics span %.2f--%.2f"
        % (primary["weight_min"], primary["weight_max"], primary["kish_effective_sample_size"],
           uncapped["weight_min"], uncapped["weight_max"]),
        "  with ESS %.0f; uncapped weights are not fitted. Caps 0.10, 0.15 and 0.20 are refitted."
        % uncapped["kish_effective_sample_size"],
        "  The likelihood is $\\sum_i w_i\\log p(S_i\\mid\\theta)$; weights are fixed, so intervals",
        "  are conditional and omit propensity-model uncertainty. At the primary cap, $\\gamma=%.3f$"
        % m(ipw, "gamma"),
        "  against $%.3f$ and the floor %.3f against %.3f; $\\nu_{\\text{clean}}=%.2f$ against %.2f."
        % (m(un, "gamma"), m(ipw, "sd_undiv"), m(un, "sd_undiv"),
           m(ipw, "nu_clean"), m(un, "nu_clean")),
        "- **High-volatility eligible-outcome stress.** Appending only the %d records whose outcome is"
        % ms["eligible_outcome_stress"]["n_pseudo"],
        "  eligible but unavailable moves the conditional bracketed estimate from $k=%.3f$"
        % m(lo, "k"),
        "  at $c=%g$ to $%.3f$ at $c=%g$, between $%.3f$ and $%.3f$ across the grid. Because the"
        % (float(cs[0]), m(hi, "k"), float(cs[-1]), min(ks), max(ks)),
        "  construction makes those unavailable outcomes more volatile, it cannot test the",
        "  adverse-to-sub-linearity direction. The concentration exponent moves $%.3f\\to%.3f$ and"
        % (m(lo, "gamma"), m(hi, "gamma")),
        "  $\\nu_{\\text{clean}}$ moves %.2f to %.2f at $c=%g$; this is not a bound."
        % (m(lo, "nu_clean"), m(hi, "nu_clean"), float(cs[-1])),
        "- **Eligibility-unresolved stress.** Assuming all %d filings with no deterministic reading were economically"
        % ms["n_eligibility_unresolved"],
        "  eligible expands the potential target from %d to %d and appends them with the %d known"
        % (ms["n_supported_target_population"],
           ms["n_broader_potential_target_if_all_unresolved_eligible"],
           ms["n_eligible_outcome_unavailable"]),
        "  unavailable outcomes. This %d-record stress moves $k=%.3f$ at $c=1$ to $%.3f$ at $c=5$."
        % (ms["eligibility_unresolved_stress"]["n_pseudo"],
           m(broad["1.0"], "k"), m(broad["5.0"], "k")),
        "  It is not a bound, not an estimate that those filings were eligible, and does not repair poor overlap.",
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


def currency_clauses(t, scan, obs, corpus):
    """Section 2b's currency counts, over the collected filings (the scan) and over the corpus (the observations).

    Which words the first clause needs depends on the record. With undetermined filings in the corpus it says how many
    and what they are; with none, it says none is there. Each form is refused where the record calls for the other,
    so a rescan that settles the last undetermined corpus filing cannot leave "The other 0 are in the corpus: scanned
    filings ... both extraction models read as GBP" standing (round 62: the rescan after extraction d9f2bdee)."""
    cc = scan["counts"]
    corp = {}
    for o in obs:
        key = str(o.get("report_currency"))
        corp[key] = corp.get(key, 0) + 1
    und_in = corp.get("UNDETERMINED", 0)
    if sum(cc.values()) != scan["n_reports"] or sum(corp.values()) != corpus:
        raise SystemExit("the currency counts do not add up to the filings or to the corpus")
    if (set(cc) | set(corp)) - {"GBP", "USD", "UNDETERMINED"} or scan.get("non_gbp_usd"):
        raise SystemExit("a currency other than GBP or USD: 'No currency other than GBP or USD was found' is false")
    corpus_keys = {"%d_%d" % (int(o["syndicate"]), int(o["year"])) for o in obs}
    if len(set(scan["undetermined"]) - corpus_keys) != cc.get("UNDETERMINED", 0) - und_in:
        raise SystemExit("the undetermined filings outside the corpus do not number the difference of the counts")
    head = (r"Corpus currencies \((?P<n>[0-9,]+) filings\): \*\*(?P<gbp>\d+) GBP / (?P<usd>\d+) USD / "
            r"(?P<und>\d+) undetermined\*\*\. ")
    values = {"n": "{:,}".format(scan["n_reports"]), "gbp": cc.get("GBP", 0), "usd": cc.get("USD", 0),
              "und": cc.get("UNDETERMINED", 0), "corpus": corpus}
    if und_in:
        t = _numbers(t, head + r"(?P<skip>\d+) of the undetermined\s+are skipped no-model files that never enter "
                               r"the analysis\. The other (?P<inc>\d+) are in the (?P<corpus>\d+)-observation",
                     dict(values, skip=cc.get("UNDETERMINED", 0) - und_in, inc=und_in),
                     "the filings' currency counts (with undetermined filings in the corpus)")
    else:
        t = _numbers(t, head + r"None\s+of\s+them\s+is\s+in\s+the\s+(?P<corpus>\d+)-observation\s+dataset:\s+they\s+"
                               r"are\s+no-model\s+files\s+that\s+never\s+enter\s+the\s+analysis\.",
                     values, "the filings' currency counts (with no undetermined filing in the corpus)")
    t = _numbers(t, r"The (?P<corpus>\d+)-observation\s+dataset is \*\*(?P<gbp>\d+) GBP / (?P<usd>\d+) USD "
                    r"\((?P<pct>\d+)%\) / (?P<und>\d+) undetermined\*\*",
                 {"corpus": corpus, "gbp": corp.get("GBP", 0), "usd": corp.get("USD", 0),
                  "pct": "%.0f" % (100.0 * corp.get("USD", 0) / corpus), "und": und_in},
                 "the corpus's currency counts")
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
    t = currency_clauses(t, scan, obs, flow["corpus"])
    # 2: the filings with no usable dual-model output, the loader's own count. It was typed as 128 on 27 September
    # 2026 and stayed 128 when the count moved to 116 on 29 September, while the generated waterfall followed it
    t = _numbers(t, r"The (?P<n>[0-9,]+) filings\s+with\s+no\s+usable\s+dual-model\s+output\s+cannot\s+all\s+be\s+"
                    r"labelled\s+OCR\s+failures",
                 {"n": flow["files_without_dual_model_record_overlapping_audit_count"]},
                 "the filings with no usable dual-model output")
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

    # 2c: inferential disposition and model-sample response
    disp = mc["disposition_counts"]
    if sum(disp.values()) != mc["n_filings"] or mc["n_model_sample"] != flow["working_sample"]:
        raise SystemExit("the inferential dispositions do not reconcile to the filing or model-sample counts")
    sel = mc["model_sample_selection_by_size"]
    t = _numbers(
        t,
        r"The (?P<files>[0-9,]+) filings are classified before any selection diagnostic: "
        r"(?P<struct>[0-9,]+) have no eligible\s+outcome structurally, (?P<unresolved>[0-9,]+) have "
        r"economic eligibility unresolved.*?, (?P<sci>[0-9,]+) are scientific "
        r"exclusions, (?P<unavail>[0-9,]+) have an eligible but\s+unavailable outcome, (?P<comp>[0-9,]+) have an "
        r"observed eligible outcome but no usable composition,\s+and (?P<sample>[0-9,]+) enter the model",
        {"files": mc["n_filings"], "struct": disp["structural_no_eligible_outcome"],
         "unresolved": disp["eligibility_unresolved"],
         "sci": disp["scientific_exclusion"], "unavail": disp["eligible_outcome_unavailable"],
         "comp": disp["eligible_observed_composition_unavailable"], "sample": disp["working_sample"]},
        "the inferential disposition",
    )
    # the three clauses the first version of this function had no pattern for, so a refit rewrote the
    # disposition counts around them and left "794", "852" and "685" standing beside 795, 853 and 686 (review
    # of 29 September 2026, A-3); their words are checked against the arithmetic they state
    target_sum = (disp["eligible_outcome_unavailable"] + disp["eligible_observed_composition_unavailable"]
                  + disp["working_sample"])
    if mc["n_supported_target_population"] != target_sum:
        raise SystemExit("the supported target is not the three observed-or-unavailable dispositions: "
                         "'therefore' is false")
    broader = mc["n_broader_potential_target_if_all_unresolved_eligible"]
    if broader != mc["n_supported_target_population"] + disp["eligibility_unresolved"]:
        raise SystemExit("the broader potential target is not the supported target plus the unresolved filings")
    t = _numbers(t, r"The supported disclosure-defined target is therefore (?P<target>[0-9,]+)\s+records\.",
                 {"target": mc["n_supported_target_population"]}, "the supported target's size")
    t = _numbers(t, r"If all (?P<unresolved>[0-9,]+) unresolved filings were economically eligible, the "
                    r"broader potential\s+target would be (?P<broader>[0-9,]+);",
                 {"unresolved": disp["eligibility_unresolved"], "broader": broader},
                 "the broader potential target")
    t = _numbers(t, r"The selection response is membership in the (?P<n>[0-9,]+)-record model sample\.",
                 {"n": mc["n_model_sample"]}, "the selection response's sample")
    if (mc["n_eligible_outcome_unavailable"] != disp["eligible_outcome_unavailable"]
            or mc["n_eligibility_unresolved"] != disp["eligibility_unresolved"]):
        raise SystemExit("the stresses' populations are not the disposition counts")
    t = _numbers(t, r"a stress for the (?P<unavail>[0-9,]+) known eligible unavailable outcomes, and a\s+"
                    r"separate broader-potential-target stress that assumes all (?P<unresolved>[0-9,]+) "
                    r"unresolved cases eligible",
                 {"unavail": mc["n_eligible_outcome_unavailable"],
                  "unresolved": mc["n_eligibility_unresolved"]}, "the three sensitivities' populations")
    t = _numbers(
        t,
        r"Within the\s+(?P<target>[0-9,]+)-record supported disclosure-defined target, included records have median size £(?P<inside>[0-9.]+)m "
        r"against £(?P<outside>[0-9.]+)m",
        {"target": mc["n_supported_target_population"], "inside": "%.1f" % sel["median_size_included"],
         "outside": "%.1f" % sel["median_size_not_included"]},
        "the model-sample size selection",
    )
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

# This repository's last commit before the round-55 correction (10 September 2026, the round-54 suite record), which
# the manuscript pinned at the time; it is not the manuscript's pin now. The counts there are set beside today's.
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
    # FOLLOWUP5 item 8: the change from that commit to now is not the correction's alone; it carries every later
    # rule and import, so the table says what it compares and claims no effect for the correction
    L += ["The counts at `%s`, before the correction, and now. The change is not the correction's alone: it also "
          "carries every rule and extraction import since (the run-off rules, rule M01, the basis and take-on "
          "registers among them)." % PINNED_ANALYSIS, "",
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
    a, b, c = ts["a_at_or_beyond_sets"], ts["b_icc"], ts["c_syndicate_block_bootstrap"]
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
        "- **(a) Inclusive tail-support sets (at or beyond the empirical quantile).** VaR99.5: "
        "**%d syndicate-years = %d distinct syndicates** (%s; %s)."
        % (v995["n_syndicate_years"], v995["n_distinct_syndicates"],
           ", ".join(s for s, _ in v995["ranked_at_or_beyond"]), _repeats(v995["ranked_at_or_beyond"])),
        "  VaR99: %d syndicate-years = **%d distinct syndicates** (%s)."
        % (v99["n_syndicate_years"], v99["n_distinct_syndicates"], _repeats(v99["ranked_at_or_beyond"])),
        "- **(b) ICC.** Syndicate random-intercept on $z=S/\\hat\\sigma$ (%d syndicates with $\\ge$%d obs, %d observations):"
        % (b["n_syndicates_ge_min"], b["min_obs"], b["n_obs"]),
        "  **ICC = %.3f** ($\\tau_\\alpha^2=%.2f$, $\\sigma_\\varepsilon^2=%.2f$) — **%s** (threshold 0.1)."
        % (icc, b["tau_alpha2"], b["sigma_eps2"], strength),
        "- **(c) Syndicate-block bootstrap** (B=%d, whole syndicates resampled): distinct syndicates"
        % c["B"],
        "  supplying the VaR99.5 at-or-beyond set **median %d [%d, %d]**; VaR99 **median %d [%d, %d]**;"
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
        "within-transition contrast whose scale ratio follows from the constrained monotonicity",
        "of the operator in the target's size and concentration: with $\\gamma\\ge0$ and a fixed",
        "old-to-new target the scale ratio exceeds one before any data are seen. The quantile",
        "rises only conditional on a positive old quantile, as at the reported equal weights;",
        "all 4,000 sampled replicates rose, but an allowable positive weighting concentrated",
        "on syndicate 318 makes the old quantile negative and the new quantile lower. The",
        "magnitude is informative; probability one is not a universal reweighting identity.",
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
    """The two transfer operators' vignette figures, headline (size-only) first (review of 29 September 2026,
    MAT-1: until then every headline was the overlay's while the paper called size-only its default)."""
    head_mode = g0.get("headline_operator")
    if head_mode != transfer_operator.HEADLINE:
        raise SystemExit("check_gamma0_vignette_results.json does not name %s as its headline operator"
                         % transfer_operator.HEADLINE)
    so, ov = g0[transfer_operator.SIZE_ONLY], g0[transfer_operator.OVERLAY]
    if so.get("operator") != transfer_operator.SIZE_ONLY or ov.get("operator") != transfer_operator.OVERLAY:
        raise SystemExit("check_gamma0_vignette_results.json: a block does not carry its own operator key")

    def cell(block, key):
        c = block["centre"][key]
        iv = block["intervals"].get(key)
        return ("%.3f [%.3f, %.3f]" % (c, iv["lo"], iv["hi"])) if iv else "%.3f" % c

    rel = g0["overlay_relative_to_headline"]
    return "\n".join([
        "## 5. The two transfer operators' vignette VaRs (`check_gamma0_vignette.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_gamma0_vignette_results.json` at each manifest run.",
        "",
        "**Purpose.** The paper's headline operator is the size-only one ($\\gamma=0$, set to zero in every",
        "retained draw of the adopted fit, not a refit); the fitted concentration overlay is a labelled",
        "sensitivity. This records both operators' tail numbers side by side.",
        "",
        "**Result** (centres at the posterior-mean operator; 95% cluster×posterior intervals in brackets):",
        "",
        "| | Size-only ($\\gamma=0$), headline | Overlay ($\\gamma\\approx%.2f$), sensitivity |"
        % g0["gamma_posterior_mean"],
        "|---|---|---|",
        "| V1 VaR99 | %s | %s |" % (cell(so, "V1_v99"), cell(ov, "V1_v99")),
        "| V1 VaR99.5 | %s | %s |" % (cell(so, "V1_v995"), cell(ov, "V1_v995")),
        "| V2 Δ99.5 | %s | %s |" % (cell(so, "V2_d995"), cell(ov, "V2_d995")),
        "",
        "**Decision.** Every headline vignette figure is the size-only operator's. Switching the overlay on",
        "moves Vignette 1's VaR99.5 from %.3f to %.3f (%+.1f%%) and Vignette 2's change from %+.3f to %+.3f"
        % (so["centre"]["V1_v995"], ov["centre"]["V1_v995"], 100.0 * rel["V1_v995"],
           so["centre"]["V2_d995"], ov["centre"]["V2_d995"]),
        "(%+.1f%%). Until 29 September 2026 this record supported presenting $\\gamma=0$ as the default while"
        % (100.0 * rel["V2_d995"]),
        "the headline tables kept the overlay's figures; that split is withdrawn.",
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


def rank_test_text(p):
    """The size contrast's rank test, named, with its p as the article prints it: "Mann-Whitney p < 0.001" below
    that, three decimals above (the review of 2 October 2026, A-2: the document printed an unnamed "p=0.0000" for
    1.5e-32, beside a LaTeX pound macro left in Markdown)."""
    return "Mann-Whitney p < 0.001" if p < 0.001 else "Mann-Whitney p = %.3f" % p


def _p_text(p):
    """A small p-value as a power of ten, a larger one at three decimals."""
    return "p\\approx10^{%d}" % int(math.floor(math.log10(p))) if p < 0.001 else "p=%.3f" % p


def referee_section_3(pcv, cse):
    d, se = pcv["delta_ELPD_M1_minus_M2"], pcv["delta_SE"]
    # the decision rests on the Bayesian bootstrap over syndicate totals, the criterion the manuscript uses, not on
    # a multiple of the standard error (the review of 2 October 2026, A-7: the paper reads no z-type statistic)
    bb = dig(cse or {}, "contrasts/composition__vs__k0.5")
    if not bb:
        raise SystemExit("referee section 3: no Bayesian-bootstrap record of the contrast to decide on")
    if not bb["bb_2.5"] < 0 < bb["bb_97.5"]:
        raise SystemExit("referee section 3: the Bayesian-bootstrap interval for the free exponent excludes zero; "
                         "'not adjudicated by predictive CV' needs re-reading")
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
    lines += [
        "- The Bayesian bootstrap over syndicate totals, the criterion the manuscript rests on: ΔELPD",
        "  (free $k$ − $k=\\tfrac12$+floor) = %+.2f, 95%% credible interval **[%.1f, %.1f]**,"
        % (bb["delta_ELPD"], bb["bb_2.5"], bb["bb_97.5"]),
        "  $P(\\text{free }k\\text{ predicts better}) = %.2f$." % bb["P_first_better"],
    ]
    lines += [
        "",
        "**Decision.** Under the by-syndicate criterion the Bayesian-bootstrap interval for the difference",
        "includes zero ($P(\\text{free }k\\text{ predicts better}) = %.2f$), and %s is ahead on the point"
        % (bb["P_first_better"], "M1" if d > 0 else "M2"),
        "estimate: the pooling **distinction is not adjudicated by predictive CV**.",
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
    share = 100.0 * b["share_credibly_positive"]
    return "\n".join([
        "## 6. Mean-zero boundary for persistent adverse development (`check_mean_zero_boundary.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_mean_zero_boundary_results.json` at each manifest run.",
        "",
        "**Purpose.** Describe selected diagnostics relevant to fixing $\\mu=0$; neither the selected decile nor",
        "its signed mean bounds location misspecification in other syndicates or adverse subgroups.",
        "",
        "**Result.**",
        "",
        "- **(a)** Pooled within-syndicate AR(1) of $S$ = **%+.2f** (median per-syndicate %+.2f, interquartile"
        % (ar, a["per_syndicate_ar1_median"]),
        "  range [%+.2f, %+.2f]; %d syndicates with at least 4 observations). This de-meaned statistic is biased"
        % (a["per_syndicate_ar1_iqr"][0], a["per_syndicate_ar1_iqr"][1], a["n_syndicates_ge4obs"]),
        "  downward and does not support a weak-persistence conclusion.",
        "- **(b)** Syndicate random-intercept: **%d/%d (%.1f%%)** of syndicates have a credibly positive"
        % (b["credibly_positive"], b["n_syndicates"], share),
        "  (adverse) mean; %d/%d credibly negative." % (b["credibly_negative"], b["n_syndicates"]),
        "- **(c)** Most-persistent decile (%d syndicates): mean $S=%+.3f$, mean $\\sigma=%.3f$ →"
        % (c["n_syndicates"], c["mean_S"], c["mean_sigma"]),
        "  implied one-year mean contribution **≈%.2fσ**." % frac,
        "",
        "**Decision.** About %.0f%% of fitted syndicate means are credibly adverse, so fixing $\\mu=0$ is a" % share,
        "material structural limitation. The selected-decile mean of %.2fσ is descriptive only and is not used" % frac,
        "as a bound or as evidence that one sentence resolves the location sensitivity.",
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
        "  the uniform model (observed %.2f in band [%.2f, %.2f], $p_{\\text{PPC}}=%.2f$), so this check"
        % (ppc["observed_large_mean_absz"], ppc["band_5_95"][0], ppc["band_5_95"][1], ppc["p_ppc"]),
        "  detects no excess scale co-movement for the model to capture. That is one test's non-detection,",
        "  not a demonstration that none exists. What drives any remaining co-movement is not identified:",
        "  pair-specific overlap or residual covariance would have to be fitted directly, and is not fitted here.",
        "",
        "**Decision.** $k$ is stable under the heteroscedastic scale shock. All the co-movement models",
        "fitted load a *common* reporting-year factor; pair-specific shared-slip or residual-noise",
        "dependence is not fitted anywhere. These models diagnose the common-factor channel only and do not",
        "bound residual dependence. → Rest the",
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
    red, sep = sca["b_redundancy"], sca["c_within_size_variation"]
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
        "## 8. Size vs concentration: association, redundancy and posterior trade-offs (`check_size_concentration_assoc.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_size_concentration_assoc_results.json` and `model/dispersion_posterior_draws_ritc.npz` at",
        "> each manifest run.",
        "",
        "**Why.** The operator's effective size is $\\log R_{\\text{eff}}=\\log R-\\gamma\\log H$. Strong",
        "collinearity between $\\log R$ and $\\log H$ would make the two covariate channels hard to distinguish,",
        "so the diagnostics below test redundancy and pairwise posterior association. They are not, by themselves,",
        "an identification or predictive-performance argument for $\\gamma$. Unit: syndicate-year ($n=%d$)." % sca["n"],
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
        "- **(c) Within-size variation** — concentration varies at fixed size: **median within-size-decile HHI IQR",
        "  width = %.3f** (between %.2f and %.2f across the %d size deciles). The size×concentration tercile"
        % (sep["median_HHI_iqr_width_within_decile"], min(widths), max(widths), len(widths)),
        "  grid is weakly non-independent ($\\chi^2=%.1f$ on %d degrees of freedom, $%s$, **Cramér's V = %.3f**)."
        % (chi["chi2"], chi["dof"], _p_text(chi["p"]), chi["cramers_v"]),
        "",
        "- **(d) Pairwise posterior association** (from the %s headline draws, `dispersion_posterior_draws_ritc.npz`)."
        % format(corr["draws"], ","),
        "  The data-design checks above concern the *covariates*; the direct question is whether the",
        "  *posterior* of $k$ and $\\gamma$ is entangled. They are weakly and mildly positively correlated:",
        "  $\\text{corr}(k,\\gamma)=\\mathbf{%+.2f}$ (Pearson; %+.2f Spearman). $k$'s real posterior trade-off"
        % (corr["k_gamma"], corr["k_gamma_spearman"]),
        "  is with the floor, $\\text{corr}(k,\\sigma_{\\text{undiv}})=\\mathbf{%+.2f}$, and the diversifiable"
        % corr["k_floor"],
        "  scale, $\\text{corr}(k,\\sigma_{\\text{div}})=%+.2f$; $\\gamma$ in turn trades off with" % corr["k_div"],
        "  $\\sigma_{\\text{div}}$ (%+.2f) and is only weakly correlated with the floor (%+.2f). Thus $k$ and"
        % (corr["gamma_div"], corr["gamma_floor"]),
        "  $\\gamma$ have little pairwise linear posterior association, while $k$'s larger pairwise trade-off is",
        "  with the size-invariant floor rather than concentration.",
        "",
        "**Decision.** Size and concentration are **weakly associated but not strongly collinear**: VIF≈%.1f and"
        " condition number %.1f. The low pairwise posterior correlation"
        % (max(vif_r, vif_h), cond),
        "($\\text{corr}(k,\\gamma)=%+.2f$) is useful descriptively, and $k$'s main pairwise trade-off is with"
        % corr["k_gamma"],
        " the floor (%+.2f), not $\\gamma$. These diagnostics do not establish separate identification or precision"
        % corr["k_floor"],
        " for $\\gamma$, nor that concentration improves prediction; $\\gamma$ still trades off with the diversifiable"
        " scale. The modest negative covariate association is %+.2f." % hh["pearson"],
        "",
        "---",
        "",
        "",
    ])


def _perm_p(entry):
    """A one-sided permutation p-value as it may be printed: an estimate with its count, or -- when no
    permutation reached the observed statistic -- the bound (review of 29 September 2026, M-14: the floor
    1/(B+1) was printed as p = 0.0002)."""
    st = entry.get("p_upper_statement")
    if not st or "exceedances" not in st:
        raise SystemExit("referee section 9: a permutation p-value is recorded without its count, so a "
                         "zero-exceedance floor cannot be told from an estimate: rerun "
                         "src/check_pyd_temporal_correlation.py")
    n = "{:,}".format(int(st["permutations"]))
    if st["p_is_bound"]:
        if st["exceedances"] != 0:
            raise SystemExit("referee section 9: a p-value is marked as a bound with exceedances recorded")
        return "$p<%g$ (0 of %s permutations)" % (st["p_upper_bound"], n)
    return "$p=%.4f$ (%d of %s permutations)" % (st["p"], st["exceedances"], n)


def referee_section_9(tc, mz, ranef, ss, vu):
    a, raw, b = tc["a_lag1_demeaned"], tc["a_lag1_raw_level"], tc["b_lag2"]
    c, d = tc["c_direction_persistence"], tc["d_effective_sample"]
    bench = tc.get("e_demeaning_benchmark")
    if not bench or bench.get("rho_reading_the_interval_upper") is None:
        raise SystemExit("referee section 9: the demeaning benchmark is not recorded")
    mc = bench.get("monte_carlo_check") or {}
    if abs(mc.get("difference", 1.0)) > 0.01:
        raise SystemExit("referee section 9: the benchmark and the simulation of the same statistic disagree (%s)"
                         % mc.get("difference"))
    lo, hi = a["block_bootstrap_ci95"]
    # The test is one-sided for positive persistence, so the guards are on the direction and on the
    # null's own location -- the things that went wrong -- and NOT on the finding coming out either way.
    # A p-value read as distance from zero is what the frozen review of 25 September 2026 (M01) found.
    for key in ("p_upper_positive_persistence", "p_two_sided_rank", "permutation_null"):
        if key not in a:
            raise SystemExit("referee section 9: %s is not recorded, so the test's direction cannot be stated" % key)
    null = a["permutation_null"]
    if null["mean"] >= 0:
        raise SystemExit("referee section 9: the permutation null is no longer centred below zero, so the "
                         "demeaning bias this section explains is not present (%.4f)" % null["mean"])
    cond = dig(tc, "f_conditional_on_adopted_model/tests")
    if not cond:
        raise SystemExit("referee section 9: the conditional test on the adopted model's residuals is not recorded")
    cal = dig(tc, "g_null_calibration/rejection_shares") or {}
    # the section quotes the statistic it leads with, which is the rank one
    size = dig(cal, "common_year_component_only/spearman") or {}
    power = dig(cal, "within_syndicate_ar1/spearman") or {}
    if not size or not power:
        raise SystemExit("referee section 9: the nulls' calibration is not recorded for the statistic the "
                         "section reports, so it cannot say which null its finding rests on")
    if not (size["per_year_adjusted"] < size["unadjusted"]):
        raise SystemExit("referee section 9: the adjusted test is no longer the better-sized one (%.2f against "
                         "%.2f), so the section's reason for resting on it is gone"
                         % (size["per_year_adjusted"], size["unadjusted"]))
    if power["per_year_adjusted"] < 0.5:
        raise SystemExit("referee section 9: the adjusted test has no power on these year sets (%.2f)"
                         % power["per_year_adjusted"])
    ce = bench.get("counterexample_to_excluding_dynamics") or {}
    if ce.get("variance_for_short_histories") is None:
        raise SystemExit("referee section 9: the counterexample to excluding dynamics is not recorded")
    if abs(ce["reading"] - a["pearson"]) > 1e-6:
        raise SystemExit("referee section 9: the counterexample does not read the observed statistic (%s vs %s)"
                         % (ce["reading"], a["pearson"]))
    if not 0.2 <= raw["spearman"] < 0.7:
        raise SystemExit("referee section 9: the raw-level Spearman is no longer moderate")
    if not (c["share_same_sign"] > 0.5 and c["binomial_p_vs_50pct"] < 0.001):
        raise SystemExit("referee section 9: direction persistence is no longer resolved")
    if not (b["pearson"] < 0.1 and b["spearman"] < 0.1):
        raise SystemExit("referee section 9: lag-2 now shows positive persistence")
    if not (0 < bench["rho_reading_the_observed_demeaned"] < bench["rho_reading_the_interval_upper"]
            < bench["observed_raw_lag1"]):
        raise SystemExit("referee section 9: the benchmark's three lag-1 correlations are no longer ordered")
    het = bench.get("heterogeneous_variance_reading") or {}
    if het.get("rho_reading_the_observed_demeaned") is None:
        raise SystemExit("referee section 9: the heterogeneous-variance reading is not recorded")
    tau = dig(ranef or {}, "tau_alpha_vs_scale/tau_alpha")
    if tau is None:
        raise SystemExit("referee section 9: the random-intercept scale is not recorded")
    kcal = dig(ss, "design_a_group_dispersion/k") or {}
    if kcal.get("descriptive_ratio_between_over_reported") is None:
        raise SystemExit("referee section 9: the subgroup descriptive ratio is not recorded")
    adj = dig(ss, "design_b_adjacency/sd_ratio_thinned_over_random/k")
    if adj is None:
        raise SystemExit("referee section 9: the adjacency ratio is not recorded")
    prim = cond["per_year_adjusted"]["spearman"]
    block = cond["year_block_permutation"]["spearman"]
    clus = dig(vu, "robustness/V1_adj_var995_CI_by_clustering") or {}
    # The two CONDITIONAL FREQUENTIST entries, which differ only in the resampling unit. The primary
    # interval is a Bayesian bootstrap crossed with posterior draws, so setting it against a
    # frequentist one would attribute the parameter uncertainty to the clustering as well.
    by_syn = (clus.get("cluster_syndicate_freq") or {}).get("sd")
    by_row = (clus.get("iid_row_freq") or {}).get("sd")
    primary = (clus.get("bayesian_bootstrap_primary") or {}).get("sd")
    if by_syn is None or by_row is None or primary is None:
        raise SystemExit("referee section 9: the vignette's clustering comparison is not recorded")
    if by_syn <= by_row:
        raise SystemExit("referee section 9: resampling whole syndicates no longer gives the wider interval "
                         "(%.4f against %.4f), so the section's reason is gone" % (by_syn, by_row))
    share = 100.0 * mz["b_credibly_positive"]["share_credibly_positive"]
    frac = mz["c_most_persistent_decile"]["implied_one_year_mean_as_fraction_of_sigma"]
    panels = int(dig(tc, "g_null_calibration/panels_per_design"))
    counts = dig(tc, "g_null_calibration/rejection_counts") or {}
    size_n = dig(counts, "common_year_component_only/spearman/per_year_adjusted")
    power_n = dig(counts, "within_syndicate_ar1/spearman/per_year_adjusted")
    if not size_n or not power_n:
        raise SystemExit("referee section 9: the calibration's rejection counts and intervals are not recorded")
    adjusted_rejections, adjusted_power_rejections = size_n["rejections"], power_n["rejections"]
    if (adjusted_rejections != int(round(panels * size["per_year_adjusted"]))
            or adjusted_power_rejections != int(round(panels * power["per_year_adjusted"]))):
        raise SystemExit("referee section 9: the calibration's counts disagree with its shares")
    return "\n".join([
        "## 9. Temporal correlation of PYD severity across consecutive years (`check_pyd_temporal_correlation.py`)",
        "",
        "> Generated block: written by `src/build_current_results.py` from",
        "> `results/check_pyd_temporal_correlation_results.json` and `results/check_serial_sensitivity_results.json`",
        "> (with `results/check_mean_zero_boundary_results.json`, `results/check_syndicate_random_effect_results.json`",
        "> and `results/vignette_uncertainty_results.json` for the cross-references) at each manifest run.",
        "",
        "**Why.** The pooling likelihood treats a syndicate's yearly severities as conditionally",
        "independent given size/HHI (with $\\mu=0$). Strong within-syndicate serial correlation in",
        "$S=\\text{PYD}/\\text{reserves}$ would violate that and shrink the effective sample. Unit:",
        "consecutive-year pairs within syndicate (%d syndicates ≥3 obs, %d lag-1 pairs)."
        % (tc["n_syndicates_ge3obs"], tc["n_lag1_pairs"]),
        "",
        "**How the p-value is read, which this section got wrong until 25 September 2026.** De-meaning within",
        "syndicate biases the pooled lag-1 correlation down by about $1/(T-1)$, so the permutation null is centred",
        "at **%+.3f**, not at zero. The published $p=%.2f$ was the share of permutations *further from zero* than"
        % (null["mean"], a["p_absolute_distance_from_zero_superseded"]),
        "the observed statistic, which in a null centred below zero is not a test of positive persistence: a",
        "negative observed value can sit high in it. Read in the direction of the alternative, the same 4,000",
        "permutations give %s." % _perm_p(a),
        "",
        "**And which null.** That is the arithmetic corrected, not the finding established, because the",
        "within-syndicate permutation is itself the wrong null here. Permuting a syndicate's own years destroys",
        "its alignment with the calendar, so a common reporting-year component lands in the observed statistic and",
        "not in the null. In one deliberately small experiment on these year sets, over %d simulated panels at "
        "$\\alpha=%.2f$, it rejects"
        % (dig(tc, "g_null_calibration/panels_per_design"), dig(tc, "g_null_calibration/alpha")),
        "**%.2f** of panels that carry a common year component (lag-1 %.2f) and no within-syndicate dynamics at"
        % (size["unadjusted"], dig(tc, "g_null_calibration/year_component_lag1")),
        "all. Taking each reporting year's location and scale",
        "out of the cross-section first gives **%d/%d rejections** (exact binomial 95%% interval [%.4f, %.4f]),"
        % ((adjusted_rejections, panels) + tuple(size_n["exact_binomial_ci95"])),
        "with **%d/%d** ([%.4f, %.4f]) against a within-syndicate"
        % ((adjusted_power_rejections, panels) + tuple(power_n["exact_binomial_ci95"])),
        "AR(1) panel under that one design. Twenty panels are far too few to establish the test's general size or",
        "calibration over nuisance configurations. The experiment exposes the original procedure's severe inflation",
        "and motivates the year-adjusted test used below; the script refuses to write this section if that ordering reverses.",
        "",
        "**Result.**",
        "",
        "- **Lag-1, de-meaned within syndicate**: Pearson **%+.3f** [%+.2f, %+.2f] (syndicate block bootstrap),"
        % (a["pearson"], lo, hi),
        "  Spearman %+.3f. Against the within-syndicate permutation null (mean %+.3f), the one-sided test for"
        % (a["spearman"], null["mean"]),
        "  positive persistence gives **%s** (two-sided rank %.4f). The interval is for the *statistic*, which the"
        % (_perm_p(a), a["p_two_sided_rank"]),
        "  demeaning biases down; it is not an interval for an AR coefficient.",
        "- **The same test on the adopted model's own residuals** $z=S/\\sigma_{it}$, which is what conditional",
        "  independence given size, HHI, regime and reporting year actually asserts, with each reporting year's",
        "  location and scale taken out of the cross-section: Spearman **%+.3f** against a null centred at %+.3f,"
        % (prim["observed"], prim["permutation_null"]["mean"]),
        "  **%s**. This is the year-adjusted test; the association survives conditioning on the"
        % _perm_p(prim),
        "  year, so it is not the systemic year component the model already carries as $\\exp(s_t)$. Permuting the",
        "  calendar-year labels instead, which leaves each year's cross-section whole but also destroys the",
        "  arrangement of the year blocks, gives %s on the same residuals."
        % _perm_p(block),
        "- **Lag-1, raw level** (not de-meaned): Pearson %+.2f, Spearman **%+.2f** — moderate. It carries the"
        % (raw["pearson"], raw["spearman"]),
        "  *persistent per-syndicate level* (sign) and any serial component together.",
        "- **Direction persistence**: **%.1f%%** of consecutive pairs share the sign of PYD (%d pairs,"
        % (100.0 * c["share_same_sign"], c["n_pairs"]),
        "  binomial $p<0.001$) — releasers keep releasing.",
        "- **Lag-2 de-meaned**: Pearson %+.2f, Spearman %+.2f (no positive persistence at two years)."
        % (b["pearson"], b["spearman"]),
        "",
        "**Decision.** There **is** positive residual lag-1 association in the adopted model's own residuals under the",
        "year-adjusted procedure, and it survives conditioning on the reporting",
        "year. The pooling likelihood's conditional-independence assumption is **not supported** for the dispersion",
        "process; the earlier reading of this section, that no residual dependence was detected and that there was",
        "therefore no reason to consider an autoregressive term, was an artefact of measuring distance from zero in",
        "a null centred at %+.3f." % null["mean"],
        "What these diagnostics do **not** do is identify the process. Over these syndicates' own year sets a",
        "level-free AR(1) whose own lag-1 correlation is %.2f would read the observed $%+.3f$, and one as strong as"
        % (bench["rho_reading_the_observed_demeaned"] or 0.0, a["pearson"]),
        "%.2f would still read inside the interval — but that mapping assumes ONE coefficient and the SAME variance"
        % bench["rho_reading_the_interval_upper"],
        "for every syndicate. With each syndicate's own observed variance the first figure becomes %.2f, and a"
        % het["rho_reading_the_observed_demeaned"],
        "level-free process at the observed raw lag-1 %+.2f reads the observed de-meaned $%+.3f$ exactly once the"
        % (bench["observed_raw_lag1"], ce["reading"]),
        "%d histories of at most four years are given variance %.1f. So the raw-against-de-meaned contrast excludes"
        % (ce["n_short_histories"], ce["variance_for_short_histories"]),
        "**nothing** about dynamics, and the equal-variance figures are an illustration under stated assumptions",
        "rather than a bound on the serial component.",
        "",
        "**What the exploratory refits show** (`check_serial_sensitivity.py`). Six disjoint syndicate groups, refitting the",
        "adopted model on each: the spread of the six estimates of $k$ is %.4f against the %.4f each fit reports"
        % (kcal["between_group_sd"], kcal["mean_reported_sd"]),
        "for itself, a descriptive ratio of **%.2f**. That ratio is not expected to equal one under an independent"
        % kcal["descriptive_ratio_between_over_reported"],
        "Bayesian model and is not a posterior-SD multiplier. Holding $n$ and cluster sizes fixed, the one thinned",
        "comparison gives a width ratio of %.2f; changing the retained years and covariates prevents it from"
        % adj,
        "isolating an adjacency effect. Holding the parameters at their posterior",
        "mean and changing only the resampling unit, the interval's SD is %.4f by syndicate against %.4f by"
        % (by_syn, by_row),
        "syndicate-year; the published interval is %.4f because"
        % primary,
        "it crosses donor-composition weights with draws from the original likelihood. That resampling measures",
        "donor composition; it does not correct parameter covariance. No dependence-adjusted width is reported for",
        "$k$, $\\gamma$, the floor, the tail parameters or the transferred stress.",
        "On this evidence the paper reports the association and leaves all posterior uncertainty explicitly",
        "conditional on the working independence likelihood. It does not add a longitudinal component because the",
        "diagnostics do not identify the process that would justify a particular one,",
        "and the persistent syndicate intercept is material when tested directly ($\\tau_\\alpha=%.3f$) while the"
        % tau,
        "persistent per-syndicate mean is the unresolved $\\mu=0$ boundary in §6 (%.0f%% credibly-positive"
        % share,
        "means, about %.2fσ a year in the most-persistent decile). Dependence of a form a lag-1 statistic cannot"
        % frac,
        "see is still not tested.",
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

    def mle(t, grp):
        """How a Student-t figure is described: an interior MLE, or the clip bound it sits on (review of
        29 September 2026, A-6: 1.00 was called a direct MLE; it is the lower clip of t_nu)."""
        clip = t.get("clip")
        if clip is None or (grp + "_at_bound") not in t:
            raise SystemExit("referee bookkeeping: results/ritc_tail_shape_results.json does not record whether "
                             "its Student-t nu sits on the clip bound: rerun src/ritc_tail_shape.py")
        bound = t[grp + "_at_bound"]
        on_bound = t[grp] <= clip[0] or t[grp] >= clip[1]
        if bool(bound) != on_bound:
            raise SystemExit("referee bookkeeping: the Student-t nu's clip flag disagrees with its value")
        if bound:
            return ("not an estimate but the %s clip bound of the Student-t MLE (`t_nu` clips $\\nu$ to "
                    "$[%g, %g]$; the unclipped fit reaches or passes it)" % (bound, clip[0], clip[1]))
        return "direct Student-t MLE"

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
        "  $n=%d$ (`calibrate_dispersion_ritc`); **%.2f** = %s on the %d flagged residuals"
        % (ws, t_c["ritc"], mle(t_c, "ritc"), calib["meta"]["ritc"]),
        # round 62's verification: the clip incidence was given for the N5 contrast only
        "  of the same $n=%d$ CALIB population (`ritc_tail_shape`, \"CALIB\"; %d of that contrast's %d bootstrap"
        % (calib["meta"]["n"], t_c["n_boot_at_bound"], t_c["n_boot"]),
        "  replicates had a group on a clip bound); **%.2f** = %s on the"
        % (t_5["ritc"], mle(t_5, "ritc")),
        "  %d flagged residuals of the strict rescaling population $n=%d$ (`ritc_tail_shape`, \"N5\");"
        % (n5["meta"]["ritc"], n5["meta"]["n"]),
        "  %d of that contrast's %d bootstrap replicates had a group on a clip bound."
        % (t_5["n_boot_at_bound"], t_5["n_boot"]),
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
    "ss": (RESULTS, "check_serial_sensitivity_results.json"),
    "vu": (RESULTS, "vignette_uncertainty_results.json"),
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


#: section 5 under the heading it had until 29 September 2026 and under the one referee_section_5 writes, so the
#: record is found both on its first regeneration and on every one after (a scratch regeneration showed the
#: second run could not find the block it had just written)
SECTION_5 = r"## 5\. (?:Size-only|The two transfer operators).*?(?=## 6\. )"


def referee_text(t, r=None):
    """The whole referee record from its records; each block must be found exactly once."""
    r = r or referee_records()
    subs = (
        (r"> \*\*Status: .*?(?=\n\n9 checks)", REFEREE_STATUS),
        (r"## 1\. Effective independent support.*?(?=## 3\. )", referee_section_1(r["ts"]) + referee_section_2(r["cu"])),
        (r"## 3\. Pooling comparison.*?(?=## 4\. )", referee_section_3(r["pcv"], r["cse"])),
        (r"## 4\. Size.maturity.*?(?=## 5\. )", referee_section_4(r["sm"])),
        (SECTION_5, referee_section_5(r["g0"])),
        (r"## 6\. Mean-zero boundary.*?(?=## 7\. )", referee_section_6(r["mz"])),
        (r"## 7\. Heteroscedastic.*?(?=## 8\. )", referee_section_7(r["het"], r["bmc"])),
        (r"## 8\. Size vs concentration.*?(?=## 9\. )", referee_section_8(r["sca"], r["corr"])),
        (r"## 9\. Temporal correlation.*?(?=## Bookkeeping)",
         referee_section_9(r["tc"], r["mz"], r["ranef"], r["ss"], r["vu"])),
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
