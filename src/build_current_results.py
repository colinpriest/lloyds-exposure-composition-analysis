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

Run:  python src/build_current_results.py
"""
import io
import json
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
    A(r"| $P(\nu_{\text{RITC}} < \nu_{\text{clean}})$ | %s | RITC tail heavier in this fit; the ordering is not imposed (the prior on $\lambda_{\text{RITC}}$ admits both signs) |"
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
                # an empirical fraction of the posterior draws. At the boundary it is
                # a simulation count -- none of the draws crossed -- and neither an
                # exact probability of one nor a strict bound above 0.999 (0.5/n is a plotting
                # convention that ignores MCMC dependence): say the count.
                n = (kfree.get("draws") or 0) * (kfree.get("chains") or 0)
                if n and v >= 1.0:
                    shown = "all %s draws" % format(n, ",")
                    why = ("none of the %s post-warmup draws reached the boundary, at "
                           "the available Monte Carlo resolution: a simulation count, "
                           "not a bound on the posterior probability; against a prior "
                           "of %s" % (format(n, ","), f(pr, 2)))
                elif n and v <= 0.0:
                    shown = "none of %s draws" % format(n, ",")
                    why = ("no post-warmup draw of %s lay inside, at the available "
                           "Monte Carlo resolution: a simulation count, not a bound on "
                           "the posterior probability; against a prior of %s"
                           % (format(n, ","), f(pr, 2)))
                else:
                    shown, why = f(v, 3), "against a prior of %s" % f(pr, 2)
                A("| %s | %s | %s |" % (lbl, shown, why))
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
            "whether pooling is slower than the finite-variance independent $\\sqrt N$ "
            "benchmark -- a floor-plus-$\\sqrt N$ alternative is not predictively "
            "separable;",
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
    ex = load(MODEL, "exposure_results.json")
    if ex is None:
        raise SystemExit("model/exposure_results.json not found; run src/run_analysis.py first")
    print("docs/data-provenance.md waterfall %s" % ("rewritten" if write_provenance_waterfall(ex) else "already current"))
    print("docs/data-provenance.md counts and sensitivities %s"
          % ("rewritten" if write_provenance_counts(ex) else "already current"))
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
        "     `src/pyd_basis_rule.py`) - %d unusable severity - %d missing opening reserves"
        % (tows["unusable_severity"], tows["missing_opening_reserves"]),
        "     - %d without premium weights = %d" % (tows["missing_lob_weights"], ws),
        "  %d of the %d filings carry no usable dual-model extraction. That is a diagnostic"
        % (single, files),
        "  of extraction quality and OVERLAPS the stages above; it is not a further subtraction,",
        "  and treating it as one is what made an earlier version of this flow fail to add up.",
    ]


def write_provenance_waterfall(ex):
    def fn(t):
        m = re.search(r"```\n\d+ files -> .*?(?=\nCorpus:)", t, re.S)
        if not m:
            raise SystemExit("docs/data-provenance.md carries no waterfall block")
        return t[:m.start()] + "```\n" + "\n".join(waterfall_lines(ex)) + t[m.end():]
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


def missingness_lines():
    """The two selection sensitivities, from check_missingness_sensitivity_results.json."""
    with io.open(os.path.join(HERE, "results",
                              "check_missingness_sensitivity_results.json"), encoding="utf-8") as fh:
        ms = json.load(fh)
    un, ipw = ms["fits"]["unweighted"], ms["fits"]["ipw_selection_weighted"]
    prop = ms["propensity_model"]
    byc = ms["worst_case"]["by_c"]
    cs = sorted(byc, key=float)
    lo, hi = byc[cs[0]], byc[cs[-1]]

    def m(block, key):
        return block[key]["mean"]

    return [
        "- **Selection weighting (IPW).** Response propensity",
        "  $\\operatorname{logit}P(\\text{success})\\sim\\log R+\\text{year}$ confirms the size",
        "  gradient (coefficient on $\\log R$ $%+.2f$). Refitting with each observation weighted"
        % prop["coef_logR"],
        "  by $1/\\hat p$ \u2014 up-weighting small syndicates by up to $%.1f\\times$ \u2014 leaves the fit"
        % prop["weight_max"],
        "  essentially unchanged: $k=%.3f$ $[%.3f,%.3f]$ against $%.3f$ $[%.3f,%.3f]$,"
        % (m(ipw, "k"), ipw["k"]["hdi_2.5"], ipw["k"]["hdi_97.5"],
           m(un, "k"), un["k"]["hdi_2.5"], un["k"]["hdi_97.5"]),
        "  $\\gamma=%.3f$ against $%.3f$, floor $%.3f$ against $%.3f$, $\\nu_{\\text{clean}}=%.2f$"
        % (m(ipw, "gamma"), m(un, "gamma"), m(ipw, "sd_undiv"), m(un, "sd_undiv"),
           m(ipw, "nu_clean")),
        "  against $%.2f$." % m(un, "nu_clean"),
        "- **High-volatility orphan stress.** Appending %d pseudo-records at the size distribution"
        % ms["worst_case"]["n_pseudo"],
        "  of failure-prone syndicates moves the conditional bracketed estimate from $k=%.3f$"
        % m(lo, "k"),
        "  at $c=%g$ to $%.3f$ at $c=%g$. Because the construction makes the predominantly"
        % (float(cs[0]), m(hi, "k"), float(cs[-1])),
        "  small missing books *more* volatile, it cannot test the adverse-to-sub-linearity",
        "  direction. Two parameters move",
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


def write_referee_blocks():
    ts = load(RESULTS, "check_tail_support_syndicate_results.json")
    cu = load(RESULTS, "check_currency_entanglement_results.json")
    g0 = load(RESULTS, "check_gamma0_vignette_results.json")
    if not (ts and cu and g0):
        raise SystemExit("referee blocks: a named result file is missing")

    def fn(t):
        t = re.sub(r"## 1\. Effective independent support.*?(?=## 3\. )",
                   lambda m: referee_section_1(ts) + referee_section_2(cu), t, count=1, flags=re.S)
        t = re.sub(r"## 5\. Size-only.*?(?=## 6\. )", lambda m: referee_section_5(g0), t, count=1, flags=re.S)
        return t
    return _rw(REFEREE, fn)


if __name__ == "__main__":
    raise SystemExit(main())
