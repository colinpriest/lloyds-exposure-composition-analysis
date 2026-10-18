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
interval of the relative change. Under the paper's headline size-only operator (the headline fit, gamma
fixed at 0 in the likelihood: transfer_operator.py), and again under the concentration overlay (the
gamma-free fit), the labelled sensitivity, each at its own fit's posterior means; the two start the
generator afresh, so they see the same records, replacements, shifts and signs.

The rate is draw four's (the fourth protocol, results/extraction_error_rate/protocol/error-rate-protocol-fourth.md,
"What happens to the propagation"): its Jeffreys posterior under the clarified rule, the rate among the records
nobody had read, applied to the records nobody has read. Draw four's 100 records and its census stratum's 7 join the
read set, so the unread records fall from the 400 of its frame (fewer as records leave the working sample). The
pooled rate of the second and third samples, Beta(8.5, 154.5), is run beside it as a sensitivity, with the same seed
and replicates (`pooled_rate_sensitivity`); nothing else changes. Draw four's errors are listed with whether a
register repaired them: a known error left unrepaired stays in the fit as it is.

Each rate's population is bound to the current working sample too (the review of 2 October 2026, P-3): the
sampled records were drawn from the working sample of an earlier loader run, and some may have left it since. The
result records that run, how many of the sampled records are still in the current working sample, their
verdicts, and the rate on them alone, beside the rate.

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
#: draw four's scored result: the rate the propagation applies (the fourth protocol)
RATE = ARCHIVE / "fourth-sample" / "error-rate-result-fourth.json"
#: draw four's draw: its 100 records and the census stratum's 7, which join the read set, and the run it drew from
DRAW = ARCHIVE / "fourth-sample" / "error-rate-sample-fourth.json"
#: draw four's frame: the working sample and the loader run it was drawn from
FRAME = ARCHIVE / "fourth-sample" / "error-rate-frame-fourth.json"
#: the pooled rate of the second and third samples, run beside draw four's as a sensitivity
POOLED = ARCHIVE / "third-sample" / "error-rate-result-third.json"
READ = (ARCHIVE / "propagation" / "error-rate-read-stems.json",
        ARCHIVE / "tenth-census" / "error-rate-read-stems-tenth.json",
        DRAW)
CONFIRMED_REGISTER = SD / "data" / "pyd_confirmed_figures.json"
CONFIRMED = ARCHIVE / "tenth-census" / "error-rate-confirmed-errors-tenth.json"
VU = SD / "results" / "vignette_uncertainty_results.json"
EXPOSURE = SD / "model" / "exposure_results.json"
#: the study's constants (results/extraction_error_rate/scripts/error_rate_propagation.py)
SEED = 20260915
M = 2000
MATERIAL = 0.05
MODELS = ("sign", "replace", "shift")


def load(p):
    with io.open(str(p), encoding="utf-8") as _fh:
        return json.load(_fh)


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
    """The study's inputs, read from the archive: draw four's rate (clarified rule) and the pooled rate beside it, the
    records read (draw four's included), and the confirmed errors' shifts."""
    c = load(RATE)["clarified"]
    e, n = int(c["errors"]), int(c["adjudicable_n"])
    post = c["posterior"]
    if (post["alpha"], post["beta"]) != (0.5 + e, 0.5 + n - e):
        raise SystemExit("draw four's recorded posterior Beta(%s, %s) is not Beta(1/2 + %d, 1/2 + %d)"
                         % (post["alpha"], post["beta"], e, n - e))
    a = load(POOLED)["A_sampled"]
    draw = load(DRAW)
    drawn = stems_in(draw["records"])
    if len(drawn) != len(draw["records"]):
        raise SystemExit("draw four's sample file names %d stems for %d records" % (len(drawn), len(draw["records"])))
    read = set()
    for p in READ:
        read |= stems_in(load(p))
    confirmed = load(CONFIRMED)
    shifts = np.array([(c["adopted_m"] - c["filing_m"]) / c["opening_m"] for c in confirmed], float)
    if len(shifts) == 0 or not np.all(np.isfinite(shifts)):
        raise SystemExit("no usable confirmed error shifts")
    return {"errors": e, "adjudicable": n, "pooled_errors": int(a["errors"]), "pooled_adjudicable": int(a["adjudicable_n"]),
            "read": read, "draw_four_records": drawn, "confirmed": confirmed, "shifts": shifts}


def draw_four_errors(result, register):
    """Draw four's errors under the clarified rule, each with whether a register entry carries the readings' figure
    (the fourth protocol: a known error left unrepaired stays in the fit as it is, and is listed with the result)."""
    out = []
    for stem, verdict in sorted(result["clarified"]["final_verdicts"].items()):
        if verdict != "error":
            continue
        entry = register.get(stem.replace("syndicate_", ""))
        out.append({"stem": stem, "repaired": isinstance(entry, dict) and entry.get("figure_m") is not None,
                    "register_figure_m": entry.get("figure_m") if isinstance(entry, dict) else None})
    return out


def draw_four_rate(result, frame):
    """Draw four's result in the shape rate_population reads: its clarified final verdicts, and the run and working
    sample its frame was computed from."""
    return {"exposure_results_run_id": frame["exposure_results"]["analysis_run_id"],
            "working_sample": {"A_n": int(frame["W_working_sample"]["n"])},
            "final_verdicts": {"A": result["clarified"]["final_verdicts"]}}


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


#: further lines beside the 5% one (12 October 2026): about 15% of replicates move Vignette 1's VaR99.5 by close to
#: 5% (one discrete jump: on the gamma = 0 headline it lands between 5.5% and 6%, on the overlay between 4.5% and 5%),
#: so P(> 5%) can swing between fits while P(> 4%) and P(> 6%) do not move. Each block records the probability at
#: these lines too, and the share of replicates with |rel| in [4%, 6%] (a band of half a point either side caught
#: the overlay's cluster but not the headline's: 0.002 against 15%)
OTHER_LINES = {"P_abs_relative_change_gt_4pct": 0.04, "P_abs_relative_change_gt_6pct": 0.06,
               "P_abs_relative_change_gt_10pct": 0.10}
NEAR_LINE = "share_of_replicates_with_abs_relative_change_between_4_and_6pct"
NEAR_BAND = (0.04, 0.06)
#: every per-replicate probability summary() records, the 5% line's first
LINE_KEYS = ("P_abs_relative_change_gt_5pct",) + tuple(OTHER_LINES) + (NEAR_LINE,)


def summary(deltas, base):
    d = np.asarray(deltas, float)
    rel = d / abs(base)
    a = np.abs(rel)
    q = lambda x, p: float(np.percentile(x, p))
    return {"change": {"median": q(d, 50), "p2_5": q(d, 2.5), "p97_5": q(d, 97.5)},
            "relative_change": {"median": q(rel, 50), "p2_5": q(rel, 2.5), "p97_5": q(rel, 97.5)},
            "P_abs_relative_change_gt_5pct": float(np.mean(a > MATERIAL)),
            **{k: float(np.mean(a > t)) for k, t in OTHER_LINES.items()},
            NEAR_LINE: float(np.mean((a >= NEAR_BAND[0]) & (a <= NEAR_BAND[1])))}


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
    """What the manuscript quotes: each model's probability at the 5% line and the shift model's median and interval;
    beside them each model's probability at the other lines and its share of replicates near the 5% line (LINE_KEYS),
    from the posterior rate and at its 97.5% point."""
    return {**{k: {mm: block["p_from_posterior"][mm][k] for mm in MODELS} for k in LINE_KEYS},
            **{k + "_at_rate_97_5": {mm: block["p_at_posterior_97_5"][mm][k] for mm in MODELS} for k in LINE_KEYS},
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


def posterior_record(errors, adjudicable, source):
    a, b = 0.5 + errors, 0.5 + adjudicable - errors
    return {"source": source, "prior": "Beta(1/2, 1/2)", "errors": errors, "adjudicable": adjudicable,
            "alpha": a, "beta": b, "mean": a / (a + b), "p97_5": float(stats.beta.ppf(0.975, a, b))}


def main():
    S, R, H, synd, year = vu.load_pool()
    ritc = vu.load_ritc(synd, year)
    v1, _v2_old, _v2_new = vu.load_targets()
    inp = inputs()
    pool_stems = ["syndicate_%s_%s" % (s, y) for s, y in zip(synd, year)]
    unread = np.array([i for i, s in enumerate(pool_stems) if s not in inp["read"]], int)
    # draw four's rate (the fourth protocol), and the pooled rate beside it as a sensitivity
    rates = {"draw_four": (inp["errors"], inp["adjudicable"]),
             "pooled": (inp["pooled_errors"], inp["pooled_adjudicable"])}
    committed = load(VU)
    fit = fit_record()
    if not fit["loader_run_id_without_calibration"]:
        raise SystemExit("model/exposure_results.json has no analysis_run_id_without_calibration: regenerate it "
                         "with build_working_sample.py first")
    if fit["n_working_sample"] != len(S):
        raise SystemExit("the donor pool (%d) is not the working sample (%d)" % (len(S), fit["n_working_sample"]))

    blocks = {rate: {} for rate in rates}
    for mode in transfer_operator.MODES:
        # each operator from its own fit (transfer_operator.SOURCE)
        draws, ref, hlo, hce = vu.load_draws(mode)
        cfg = (ref, hlo, hce)
        thbar = transfer_operator.params({p: float(draws[p].mean()) for p in draws}, mode)
        # the headline it perturbs must be vignette_uncertainty's own, under the same operator
        src = committed if mode == committed.get("operator") else committed.get("overlay_sensitivity", {})
        if src.get("operator") != mode:
            raise SystemExit("vignette_uncertainty_results.json records no %s block to check against" % mode)
        recorded = src["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
        for rate, (e, n) in rates.items():
            # the same seed and replicates for both rates: each run starts the generator afresh
            block = propagate(S, R, H, ritc, thbar, cfg, v1, unread, inp["shifts"], 0.5 + e, 0.5 + n - e)
            if abs(block["V1_VaR995"] - recorded) > 1e-12:
                raise SystemExit("reproduced %s VaR99.5 %.15f is not the recorded centre %.15f"
                                 % (mode, block["V1_VaR995"], recorded))
            blocks[rate][mode] = {**transfer_operator.stamp(mode), **block, "per_model": per_model(block)}

    result = load(RATE)
    run_now = fit["loader_run_id_without_calibration"]
    headline_keys = ("operator", "operator_role", "operator_construction", "V1_VaR995", "p_from_posterior",
                     "p_at_posterior_97_5", "per_model")
    rel = lambda path: str(path.relative_to(SD)).replace("\\", "/")
    out = {
        "protocol": ("error-rate-protocol.md, fifth amendment point 5 and tenth amendment; re-run on the current "
                     "fit by this manifest step (review of 29 September 2026, M-3); since 13 October 2026 its rate is "
                     "draw four's and its read set holds draw four's records (error-rate-protocol-fourth.md, "
                     "'What happens to the propagation')"),
        "fit": {**fit, "note": "the fit this simulation ran on; the archive's own runs record theirs"},
        "inputs": {"rate": rel(RATE), "pooled_rate_sensitivity": rel(POOLED),
                   "read_records": [rel(p) for p in READ], "confirmed_errors": rel(CONFIRMED)},
        "rate_population": rate_population(draw_four_rate(result, load(FRAME)), pool_stems, run_now),
        "rate_posterior": posterior_record(inp["errors"], inp["adjudicable"],
                                           "draw four, clarified rule (fourth-sample/error-rate-result-fourth.json)"),
        "draw_four_errors": draw_four_errors(result, load(CONFIRMED_REGISTER)),
        "unread_working_sample_records": int(len(unread)),
        "read_records_in_pool": int(len(S) - len(unread)),
        "draw_four_records_in_pool": int(sum(1 for s in pool_stems if s in inp["draw_four_records"])),
        "n_confirmed_error_shifts": int(len(inp["shifts"])),
        "replicates": M, "seed": SEED, "materiality_line_relative": MATERIAL,
        **{k: blocks["draw_four"][transfer_operator.HEADLINE][k] for k in headline_keys},
        "overlay_sensitivity": blocks["draw_four"][transfer_operator.SENSITIVITY],
        "pooled_rate_sensitivity": {
            "note": ("the pooled rate of the second and third samples, run beside draw four's with the same seed, "
                     "replicates and unread records (the fourth protocol); never pooled with draw four"),
            "rate_posterior": posterior_record(inp["pooled_errors"], inp["pooled_adjudicable"],
                                               "the pooled rate, third-sample/error-rate-result-third.json A_sampled"),
            "rate_population": rate_population(load(POOLED), pool_stems, run_now),
            **{k: blocks["pooled"][transfer_operator.HEADLINE][k] for k in headline_keys},
            "overlay_sensitivity": blocks["pooled"][transfer_operator.SENSITIVITY],
        },
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as _fh:
        _fh.write(json.dumps(out, indent=1) + "\n")
    print("fit: commit %s, tree dirty %s, n=%d, loader run %s"
          % (fit["analysis_commit"], fit["tree_dirty_src_model_results"], fit["n_working_sample"], run_now))
    print("unread %d of %d" % (len(unread), len(S)))
    for rate, (e, n) in rates.items():
        print("rate %s ~ Beta(%.1f, %.1f)" % (rate, 0.5 + e, 0.5 + n - e))
        for mode in transfer_operator.MODES:
            pm_ = blocks[rate][mode]["per_model"]
            print("  %-9s VaR99.5 %.4f  P(|rel|>5%%): %s  shift median %.1f%% [%.1f%%, %.1f%%]"
                  % (mode, blocks[rate][mode]["V1_VaR995"],
                     ", ".join("%s %.3f" % (k, v) for k, v in pm_["P_abs_relative_change_gt_5pct"].items()),
                     100 * pm_["shift_model_relative_change"]["median"],
                     100 * pm_["shift_model_relative_change"]["interval_95"][0],
                     100 * pm_["shift_model_relative_change"]["interval_95"][1]))
            for label, k in (("P(|rel|>4%)", "P_abs_relative_change_gt_4pct"),
                             ("P(|rel|>6%)", "P_abs_relative_change_gt_6pct"),
                             ("P(|rel|>10%)", "P_abs_relative_change_gt_10pct"),
                             ("share |rel| in [4%, 6%]", NEAR_LINE)):
                print("  %-9s   %s: %s" % ("", label, ", ".join("%s %.3f" % (mm, v) for mm, v in pm_[k].items())))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
