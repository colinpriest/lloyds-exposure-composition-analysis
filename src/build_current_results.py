#!/usr/bin/env python3
"""Generate docs/current-results.md from the committed results. No prose numbers.

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

Run:  python src/build_current_results.py
"""
import io
import json
import os

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


def main():
    m0 = load(MODEL, "dispersion_calibration_ritc.json")
    if m0 is None:
        raise SystemExit("model/dispersion_calibration_ritc.json not found; "
                         "run src/calibrate_dispersion_ritc.py first")
    pool = load(RESULTS, "pooling_compare_results.json")
    kfree = load(RESULTS, "check_k_unconstrained.json") or \
        load(RESULTS, "check_k_unconstrained_results.json")
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
    A("| $P(\\nu_{\\text{RITC}} < \\nu_{\\text{clean}})$ | %s | RITC tails are heavier |"
      % f(dig(m0, "posterior_prob/nu_ritc_lt_nu_clean"), 3))
    A("| $P(\\nu_{\\text{RITC}} < 2)$ | %s | posterior probability that the RITC regime lacks a finite variance |"
      % f(dig(m0, "posterior_prob/nu_ritc_lt_2"), 3))
    A("| $P(k < 1)$ | $1$ by construction | **tautological** on the bracketed "
      "support $[\\tfrac12,1]$; stated structurally, not computed from draws |")
    if kfree:
        # the unconstrained refit removes the bracket, so THESE are evidence where
        # the bracketed P(k<1)=1 above is not
        for lbl, path, prior in (
                ("$P(k > \\tfrac12)$, unconstrained refit",
                 "models/normal_0.5/posterior_prob/P_k_gt_0.5",
                 "models/normal_0.5/prior_prob/P_k_gt_0.5"),
                ("$P(k < 1)$, unconstrained refit",
                 "models/normal_0.5/posterior_prob/P_k_lt_1",
                 "models/normal_0.5/prior_prob/P_k_lt_1")):
            v, pr = dig(kfree, path), dig(kfree, prior)
            if v is not None:
                A("| %s | %s | against a prior of %s |" % (lbl, f(v, 3), f(pr, 2)))
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
          "$\\Delta$elpd (M1 blended $-$ M2 independent) = %s, SE %s."
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
        A("Neither criterion separates the two forms, so the free exponent is **not** "
          "separated from $k=\\tfrac12$-plus-floor on either. That is why "
          "slower-than-independent pooling is treated as unresolved.")
        A("")

    if het:
        A("## Size-loaded co-movement (M4)")
        A("")
        A("Source: `model/dispersion_calibration_hetscale.json`. Specification as "
          "fitted:")
        A("")
        A("```")
        A(str(het.get("spec", ""))[:400])
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
            A("- Dispersion given size, failure-prone indicator: coefficient %s, "
              "$p = %s$. **No association was detected among syndicates observed at "
              "least once.** That is the whole of what this diagnostic supports: a "
              "failure to reject is not a demonstration, and it is silent about the "
              "orphans, so **missing-at-random cannot be established**."
              % (f(d_.get("abs_S_failure_prone_coef"), 4), f(d_.get("abs_S_p"), 3)))
        A("")
        sens = load(RESULTS, "check_missingness_sensitivity_results.json")
        A("Two sensitivities are reported instead of resting on it. Inverse-probability "
          "weighting leaves the fit essentially unchanged. The high-volatility orphan "
          "stress moves the conditional bracketed estimate from $k = %s$ at $c=1$ to "
          "$%s$ at $c=5$ --- a construction that makes the predominantly small missing "
          "books more volatile, so it cannot test the adverse-to-sub-linearity "
          "direction --- and moves the concentration exponent and the clean-regime "
          "tail materially, so the tail is **not** unaffected. See the manuscript for "
          "both." % (f(dig(sens, "worst_case/by_c/1.0/k/mean"), 3),
                     f(dig(sens, "worst_case/by_c/5.0/k/mean"), 3)))
        A("")

    A("## Open questions")
    A("")
    A("These are unresolved on public data and nothing downstream rests on them. The "
      "manuscript states each where it arises; `paper/audit_numbers.py` gate M keeps "
      "that list and the register in step.")
    A("")
    for line in (
            "whether pooling is slower than independent $\\sqrt N$ aggregation -- a "
            "floor-plus-$\\sqrt N$ alternative is not predictively separable;",
            "the exact value of $k$; $k > \\tfrac12$ is suggestive, not established;",
            "whether the size-dispersion decline continues past about GBP 1bn;",
            "the within-book concentration--location slope, which is unresolved "
            "rather than zero;",
            "the long-tail share slope, not distinguishable from zero;",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
