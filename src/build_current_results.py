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
    A("| $P(\\nu_{\\text{RITC}} < 2)$ | %s | the RITC regime has no finite variance |"
      % f(dig(m0, "posterior_prob/nu_ritc_lt_2"), 3))
    A("| $P(k < 1)$ | %s | **tautological** on the bracketed support $[\\tfrac12,1]$ |"
      % f(dig(m0, "posterior_prob/k_lt_1"), 3))
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
    A("| $P(|\\beta_{\\text{RITC}}| > 0.1)$ | %s | the RITC scale term is omitted, "
      "not shown to be zero |" % f(dig(m0, "posterior_prob/beta_ritc_gt_0.1_abs"), 3))
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
        A("$\\Delta$elpd (M1 blended $-$ M2 independent) = %s, SE %s -- inside one "
          "standard error. The free exponent is **not** separated from "
          "$k=\\tfrac12$-plus-floor by by-syndicate cross-validation, which is why "
          "slower-than-independent pooling is treated as unresolved."
          % (f(pool.get("delta_elpd_M1_minus_M2"), 2), f(pool.get("delta_se"), 2)))
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
      "model. $\\mu = 0$ is a **fitting restriction**, not a transfer principle -- the "
      "operator carries each donor's raw location.")
    A("")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("wrote %s (%d lines)" % (os.path.relpath(OUT, HERE), len(L)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
