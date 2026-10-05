"""The extraction error-rate study's unfound-error propagation, re-run on the CURRENT fit.

The study (results/extraction_error_rate/, an evidence archive; protocol fifth amendment, point 5, and
tenth amendment) simulated the errors its samples had not found onto Vignette 1's VaR99.5: an error rate
drawn from the posterior of its sampled records, a count of the working-sample records nobody read, and
each chosen record's severity changed under three error models -- its sign reversed ("sign"), replaced by
another record's ("replace"), or shifted by a shift drawn from the errors confirmed before repair
("shift"). It ran once, on analysis commit 5b31803 and a 685-record fit, and the manuscript then said it
ran "on the final fit" (review of 29 September 2026, M-3). A record is a record of the fit it ran on.

So this manifest step runs the same simulation on the fit in the tree, after vignette_uncertainty.py, with
the study's own inputs read from the archive (the rate's errors and adjudicable records, the records read,
the confirmed errors) and the study's constants (seed, replicates, the materiality line, checked against
the archive's script by src/test_error_rate_propagation.py). It refuses unless the headline it perturbs is
vignette_uncertainty_results.json's own, under the same operator, and it records the fit it ran on: the
commit, whether the tree was clean, the working-sample size and the loader's run identifier.

Reported, for each error model and for the rate drawn from its posterior and held at its 97.5% point: the
probability that the relative change in VaR99.5 exceeds 5% in absolute value, and the median and 95%
interval of the relative change. Under the paper's headline size-only operator (transfer_operator.py), and
again under the concentration overlay, the labelled sensitivity; the two start the generator afresh, so
they see the same records, replacements, shifts and signs.

The rate's population is bound to the current working sample too (the review of 2 October 2026, P-3): the
sampled records were drawn from the working sample of an earlier loader run, and some have left it since. The
result records that run, how many of the sampled records are still in the current working sample, their
verdicts, and the rate on them alone, beside the study's rate.

Run: python src/error_rate_propagation.py
"""
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import stats

import transfer_operator
import vignette_uncertainty as vu

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "error_rate_propagation_results.json"
ARCHIVE = SD / "results" / "extraction_error_rate"
RATE = ARCHIVE / "third-sample" / "error-rate-result-third.json"
READ = (ARCHIVE / "propagation" / "error-rate-read-stems.json",
        ARCHIVE / "tenth-census" / "error-rate-read-stems-tenth.json")
CONFIRMED = ARCHIVE / "tenth-census" / "error-rate-confirmed-errors-tenth.json"
VU = SD / "results" / "vignette_uncertainty_results.json"
EXPOSURE = SD / "model" / "exposure_results.json"
#: the study's constants (results/extraction_error_rate/scripts/error_rate_propagation.py)
SEED = 20260915
M = 2000
MATERIAL = 0.05
MODELS = ("sign", "replace", "shift")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def stems_in(obj):
    """Every syndicate_NNNN_YYYY string anywhere in a JSON document."""
    out = set()
    if isinstance(obj, str):
        if obj.startswith("syndicate_"):
            out.add(obj)
    elif isinstance(obj, list):
        for x in obj:
            out |= stems_in(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            out |= stems_in(x)
    return out


def inputs():
    """The study's inputs, read from the archive."""
    a = load(RATE)["A_sampled"]
    read = set()
    for p in READ:
        read |= stems_in(load(p))
    confirmed = load(CONFIRMED)
    shifts = np.array([(c["adopted_m"] - c["filing_m"]) / c["opening_m"] for c in confirmed], float)
    if len(shifts) == 0 or not np.all(np.isfinite(shifts)):
        raise SystemExit("no usable confirmed error shifts")
    return {"errors": int(a["errors"]), "adjudicable": int(a["adjudicable_n"]), "read": read,
            "confirmed": confirmed, "shifts": shifts}


def rate_population(rate, pool_stems, current_run_id):
    """The error rate's sampled population against the current working sample (P-3).

    `rate` is the study's result file: its A_sampled rate, its final verdicts for the sampled records, and the
    loader run and working-sample size it drew from. `pool_stems` is the current working sample. Returned: the
    run drawn from, the sampled records still in the current working sample and those that have left it, the
    verdicts of each group, and the Jeffreys posterior of the rate on the records still in it.

    `current_run_id` is the loader's run identifier derived without the calibration (analysis_run_id_without_
    calibration): it is the same in the loader pass and the outputs pass, so the recorded value reproduces. The
    study's own run id is an earlier definition's full identifier, so the two cannot be compared: `same_population`
    is None, with its reason, and the records still in the working sample (below) are the comparison.
    """
    verdicts = rate["final_verdicts"]["A"]
    pool = set(pool_stems)
    kept = sorted(s for s in verdicts if s in pool)
    left = sorted(s for s in verdicts if s not in pool)

    def count(stems):
        c = {"error": 0, "correct": 0, "undeterminable": 0}
        for st in stems:
            c[verdicts[st]] += 1
        return c

    now = count(kept)
    a, b = 0.5 + now["error"], 0.5 + now["correct"]
    return {
        "drawn_from": {"exposure_results_run_id": rate["exposure_results_run_id"],
                       "working_sample_n": rate["working_sample"]["A_n"]},
        "current": {"exposure_results_run_id_without_calibration": current_run_id, "working_sample_n": len(pool)},
        "same_population": None,
        "same_population_reason": ("the study's run id is a full run id of an earlier definition and the current one is "
                                   "calibration-free, so they cannot be compared; n_in_current_working_sample and "
                                   "n_left_current_working_sample say how far the populations differ"),
        "n_sampled": len(verdicts),
        "n_in_current_working_sample": len(kept),
        "n_left_current_working_sample": len(left),
        "left_current_working_sample": [{"stem": st, "verdict": verdicts[st]} for st in left],
        "verdicts_in_current_working_sample": now,
        "posterior_in_current_working_sample": {
            "prior": "Beta(1/2, 1/2)", "alpha": a, "beta": b, "mean": a / (a + b),
            "ci95_equal_tailed": [float(stats.beta.ppf(0.025, a, b)), float(stats.beta.ppf(0.975, a, b))]},
        "note": ("the study's rate (A_sampled) is the rate of the working sample it drew from; the records still "
                 "in the current working sample give the rate beside it"),
    }


def summary(deltas, base):
    d = np.asarray(deltas, float)
    rel = d / abs(base)
    q = lambda a, x: float(np.percentile(a, x))
    return {"change": {"median": q(d, 50), "p2_5": q(d, 2.5), "p97_5": q(d, 97.5)},
            "relative_change": {"median": q(rel, 50), "p2_5": q(rel, 2.5), "p97_5": q(rel, 97.5)},
            "P_abs_relative_change_gt_5pct": float(np.mean(np.abs(rel) > MATERIAL))}


def propagate(S, R, H, ritc, thbar, cfg, v1, unread, shifts, a_post, b_post, m=M, seed=SEED):
    """The study's simulation at the parameters `thbar` (gamma already set for the operator): replicates with
    the rate from its posterior, then with the rate at its 97.5% point, from one generator started at `seed`."""
    base = vu.var_q(vu.transfer(S, R, H, v1, thbar, cfg, ritc), 0.995)
    p975 = float(stats.beta.ppf(0.975, a_post, b_post))
    rng = np.random.default_rng(seed)

    def replicates(fixed_p=None):
        out = {mm: [] for mm in MODELS}
        ks = []
        for _ in range(m):
            p = fixed_p if fixed_p is not None else float(rng.beta(a_post, b_post))
            k = int(rng.binomial(len(unread), p))
            chosen = rng.choice(unread, size=k, replace=False) if k else np.array([], int)
            others = rng.integers(0, len(S) - 1, size=k)          # a different record's severity
            others = np.where(others >= chosen, others + 1, others) if k else others
            shift = rng.choice(shifts, size=k) * rng.choice((-1.0, 1.0), size=k)
            ks.append(k)
            for mm in MODELS:
                s2 = S.copy()
                if k:
                    if mm == "sign":
                        s2[chosen] = -S[chosen]
                    elif mm == "replace":
                        s2[chosen] = S[others]
                    else:
                        s2[chosen] = S[chosen] + shift
                out[mm].append(vu.var_q(vu.transfer(s2, R, H, v1, thbar, cfg, ritc), 0.995) - base)
        return out, ks

    post, k_post = replicates()
    fixed, k_fixed = replicates(fixed_p=p975)
    return {
        "V1_VaR995": base,
        "p_from_posterior": {"K": {"mean": float(np.mean(k_post)), "p97_5": float(np.percentile(k_post, 97.5))},
                             **{mm: summary(post[mm], base) for mm in MODELS}},
        "p_at_posterior_97_5": {"p": p975,
                                "K": {"mean": float(np.mean(k_fixed)), "p97_5": float(np.percentile(k_fixed, 97.5))},
                                **{mm: summary(fixed[mm], base) for mm in MODELS}},
    }


def per_model(block):
    """What the manuscript quotes: each model's probability and the shift model's median and interval."""
    return {"P_abs_relative_change_gt_5pct": {mm: block["p_from_posterior"][mm]["P_abs_relative_change_gt_5pct"]
                                              for mm in MODELS},
            "P_abs_relative_change_gt_5pct_at_rate_97_5": {
                mm: block["p_at_posterior_97_5"][mm]["P_abs_relative_change_gt_5pct"] for mm in MODELS},
            "shift_model_relative_change": {
                "median": block["p_from_posterior"]["shift"]["relative_change"]["median"],
                "interval_95": [block["p_from_posterior"]["shift"]["relative_change"]["p2_5"],
                                block["p_from_posterior"]["shift"]["relative_change"]["p97_5"]],
                "note": "the shift model is the one built from the errors actually confirmed"}}


def fit_record():
    """The fit this ran on: commit, tree state, working sample, loader run."""
    head = subprocess.run(["git", "-C", str(SD), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(SD), "status", "--porcelain", "--", "src", "model", "results"],
                           capture_output=True, text=True).stdout.strip()
    ex = load(EXPOSURE)
    # The loader's run id derived without the calibration, not its full run id: the full id changes between the
    # loader pass and the outputs pass (each loads a different calibration), so the recorded value would not
    # reproduce in the recorded pass (the review of 4 October 2026, finding 1); main() refuses a file written by a
    # loader older than the field.
    loader_id = ex.get("analysis_run_id_without_calibration")
    return {"analysis_commit": head or None, "tree_dirty_src_model_results": bool(dirty),
            "loader_run_id_without_calibration": loader_id,
            "n_working_sample": int(ex["disposition_flow"]["working_sample"])}


def main():
    S, R, H, synd, year = vu.load_pool()
    draws, ref, hlo, hce = vu.load_draws()
    ritc = vu.load_ritc(synd, year)
    cfg = (ref, hlo, hce)
    v1, _v2_old, _v2_new = vu.load_targets()
    inp = inputs()
    pool_stems = ["syndicate_%s_%s" % (s, y) for s, y in zip(synd, year)]
    unread = np.array([i for i, s in enumerate(pool_stems) if s not in inp["read"]], int)
    a_post, b_post = 0.5 + inp["errors"], 0.5 + inp["adjudicable"] - inp["errors"]
    committed = load(VU)
    fit = fit_record()
    if not fit["loader_run_id_without_calibration"]:
        raise SystemExit("model/exposure_results.json has no analysis_run_id_without_calibration: regenerate it "
                         "with build_working_sample.py first")
    if fit["n_working_sample"] != len(S):
        raise SystemExit("the donor pool (%d) is not the working sample (%d)" % (len(S), fit["n_working_sample"]))

    blocks = {}
    for mode in transfer_operator.MODES:
        thbar = transfer_operator.params({p: float(draws[p].mean()) for p in draws}, mode)
        block = propagate(S, R, H, ritc, thbar, cfg, v1, unread, inp["shifts"], a_post, b_post)
        # the headline it perturbs must be vignette_uncertainty's own, under the same operator
        src = committed if mode == committed.get("operator") else committed.get("overlay_sensitivity", {})
        if src.get("operator") != mode:
            raise SystemExit("vignette_uncertainty_results.json records no %s block to check against" % mode)
        recorded = src["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
        if abs(block["V1_VaR995"] - recorded) > 1e-12:
            raise SystemExit("reproduced %s VaR99.5 %.15f is not the recorded centre %.15f"
                             % (mode, block["V1_VaR995"], recorded))
        blocks[mode] = {**transfer_operator.stamp(mode), **block, "per_model": per_model(block)}

    out = {
        "protocol": ("error-rate-protocol.md, fifth amendment point 5 and tenth amendment; re-run on the current "
                     "fit by this manifest step (review of 29 September 2026, M-3)"),
        "fit": {**fit, "note": "the fit this simulation ran on; the archive's own runs record theirs"},
        "inputs": {"rate": str(RATE.relative_to(SD)).replace("\\", "/"),
                   "read_records": [str(p.relative_to(SD)).replace("\\", "/") for p in READ],
                   "confirmed_errors": str(CONFIRMED.relative_to(SD)).replace("\\", "/")},
        "rate_population": rate_population(load(RATE), pool_stems, fit["loader_run_id_without_calibration"]),
        "rate_posterior": {"prior": "Beta(1/2, 1/2)", "errors": inp["errors"], "adjudicable": inp["adjudicable"],
                           "alpha": a_post, "beta": b_post, "mean": a_post / (a_post + b_post),
                           "p97_5": float(stats.beta.ppf(0.975, a_post, b_post))},
        "unread_working_sample_records": int(len(unread)),
        "read_records_in_pool": int(len(S) - len(unread)),
        "n_confirmed_error_shifts": int(len(inp["shifts"])),
        "replicates": M, "seed": SEED, "materiality_line_relative": MATERIAL,
        **{k: blocks[transfer_operator.HEADLINE][k] for k in ("operator", "operator_role", "operator_construction",
                                                              "V1_VaR995", "p_from_posterior",
                                                              "p_at_posterior_97_5", "per_model")},
        "overlay_sensitivity": blocks[transfer_operator.SENSITIVITY],
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
    print("fit: commit %s, tree dirty %s, n=%d, loader run %s"
          % (fit["analysis_commit"], fit["tree_dirty_src_model_results"], fit["n_working_sample"],
             fit["loader_run_id_without_calibration"]))
    print("rate ~ Beta(%.1f, %.1f); unread %d of %d" % (a_post, b_post, len(unread), len(S)))
    for mode in transfer_operator.MODES:
        pm_ = blocks[mode]["per_model"]
        print("%-9s VaR99.5 %.4f  P(|rel|>5%%): %s  shift median %.1f%% [%.1f%%, %.1f%%]"
              % (mode, blocks[mode]["V1_VaR995"],
                 ", ".join("%s %.3f" % (k, v) for k, v in pm_["P_abs_relative_change_gt_5pct"].items()),
                 100 * pm_["shift_model_relative_change"]["median"],
                 100 * pm_["shift_model_relative_change"]["interval_95"][0],
                 100 * pm_["shift_model_relative_change"]["interval_95"][1]))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
