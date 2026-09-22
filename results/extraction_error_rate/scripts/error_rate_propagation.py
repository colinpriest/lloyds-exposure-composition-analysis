r"""The extraction errors' effect on Vignette 1's VaR99.5 (error-rate-protocol.md, fifth amendment, point 5).

Run on the analysis repository at the refit after the repairs, once the third sample is scored. It first reproduces
the headline exactly as src/vignette_uncertainty.py computes its centre (the full pool, the transfer operator at the
posterior-mean parameters, type-7 empirical quantile) and refuses unless that equals the committed
results/vignette_uncertainty_results.json value. Then:

  * the repaired errors: VaR99.5 from the refit before the repairs (--before-results) and after them;
  * errors not yet found: 2,000 replicates, numpy.random.default_rng(20260915). Each draws an error rate p from the
    repaired extraction's posterior, Beta(1/2 + e, 1/2 + n - e) over the sampled records of A (--rate-errors,
    --rate-adjudicable); a count K ~ Binomial(N, p), where N is the working-sample records read in no sample or
    census (each treated as adjudicable); and K of them at random. Each chosen record's severity is changed under
    three error models, with the same records, replacements, shifts and signs for all three: its sign reversed;
    replaced by the severity of another working-sample record drawn at random; shifted by a shift drawn from the
    errors confirmed before repair, (adopted - filing) / opening reserves in the report's currency, with a random
    sign. The transferred pool's VaR99.5 is recomputed at the posterior-mean parameters. A second set of 2,000
    replicates, drawn after the first from the same generator, holds p at the posterior's 97.5% point.

Reported for each error model and each setting of p: the median, 2.5% and 97.5% points of the change and of the
relative change, and the probability that the relative change exceeds 5% in absolute value (the materiality line).

The comparison of the two refits covers every repair between them together (ninth amendment, point 6): the samples'
and censuses' repairs, through the registers and the extraction, and the take-on base. The report says so and lists
each take-on base record adjusted (--takeon-base-result) with its severity before and after.

    python error_rate_propagation.py --rate-errors E --rate-adjudicable N --read-samples FILE [FILE ...] \
        --confirmed-errors error-rate-confirmed-errors.json --takeon-base-result error-rate-census-ninth-result.json \
        --before-results PATH --out error-rate-propagation.json
"""
import argparse
import datetime
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import stats

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SEED = 20260915
M = 2000
MATERIAL = 0.05
REPAIRS_COMPARED = ("the refit before any repair against the refit after every repair: the samples' and censuses' "
                    "repairs, through the registers and the extraction, and the take-on base adjustments, together "
                    "(ninth amendment, point 6)")
PROTOCOL = ("error-rate-protocol.md, fifth amendment, point 5, and ninth amendment, point 6 (written before this was "
            "computed)")

ap = argparse.ArgumentParser()
ap.add_argument("--rate-errors", type=int, required=True)
ap.add_argument("--rate-adjudicable", type=int, required=True)
ap.add_argument("--read-samples", nargs="+", required=True,
                help="JSON files whose stems were read: sample files ({primary|third|tail: {stems}}), census or lists")
ap.add_argument("--confirmed-errors", required=True,
                help="JSON list of {stem, adopted_m, filing_m, opening_m}: the errors confirmed before repair")
ap.add_argument("--takeon-base-result", required=True,
                help="error-rate-census-ninth-result.json: the take-on base census, whose adjusted records are listed")
ap.add_argument("--before-results", required=True,
                help="results/vignette_uncertainty_results.json from the refit before the repairs")
ap.add_argument("--out", required=True)
# the ninth amendment's run used the defaults; the tenth amendment's names its own comparison (R221)
ap.add_argument("--repairs-compared", default=REPAIRS_COMPARED,
                help="what the before and after refits differ by; the report and the claim registry print it")
ap.add_argument("--protocol", default=PROTOCOL, help="the protocol points the run answers")
args = ap.parse_args()
REPAIRS_COMPARED = args.repairs_compared

sys.argv = [sys.argv[0]]          # vignette_uncertainty reads positional integers from argv at import
sys.path.insert(0, str(AN / "src"))
import vignette_uncertainty as vu  # noqa: E402


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


# --- the take-on base census's adjusted records, checked against the register the refit read
tb = load(args.takeon_base_result)
takeon_base = [{"stem": r["stem"], "adopted_figure_m": r["adopted_figure_m"], "opening_m": r["opening_m"],
                "takeon_m": r["second"]["takeon_amount_m"], "severity_pct_before": r["severity_pct"],
                "severity_pct_after": r["severity_pct_adjusted"]}
               for r in tb["table"] if r["outcome"] == "adjusted"]
if sorted(t["stem"] for t in takeon_base) != sorted(tb.get("adjusted") or []):
    raise SystemExit("the take-on base result's table and its adjusted list disagree")
register = load(AN / "data" / "opening_reserves_takeon_base.json")
registered = sorted("syndicate_" + k for k in register if not k.startswith("_"))
if registered != sorted(t["stem"] for t in takeon_base):
    raise SystemExit("the take-on base register %s is not the census's adjusted records %s"
                     % (registered, sorted(t["stem"] for t in takeon_base)))

# --- the headline, reproduced before anything is perturbed
S, R, H, synd, year = vu.load_pool()
draws, ref, hlo, hce = vu.load_draws()
ritc = vu.load_ritc(synd, year)
cfg = (ref, hlo, hce)
v1, _v2_old, _v2_new = vu.load_targets()
thbar = {p: float(draws[p].mean()) for p in draws}
base = vu.var_q(vu.transfer(S, R, H, v1, thbar, cfg, ritc), 0.995)
committed = load(AN / "results" / "vignette_uncertainty_results.json")
after_v995 = committed["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
if abs(base - after_v995) > 1e-12:
    raise SystemExit("reproduced VaR99.5 %.15f is not the committed centre %.15f" % (base, after_v995))
before_v995 = load(args.before_results)["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]

# --- who has been read, and the unread records errors may sit in
pool_stems = ["syndicate_%s_%s" % (s, y) for s, y in zip(synd, year)]
read = set()
for f in args.read_samples:
    read |= stems_in(load(f))
unread = np.array([i for i, s in enumerate(pool_stems) if s not in read], int)
confirmed = load(args.confirmed_errors)
shifts = np.array([(c["adopted_m"] - c["filing_m"]) / c["opening_m"] for c in confirmed], float)
if len(shifts) == 0 or not np.all(np.isfinite(shifts)):
    raise SystemExit("no usable confirmed error shifts")

a_post, b_post = 0.5 + args.rate_errors, 0.5 + args.rate_adjudicable - args.rate_errors
p975 = float(stats.beta.ppf(0.975, a_post, b_post))
rng = np.random.default_rng(SEED)
MODELS = ("sign", "replace", "shift")


def replicates(fixed_p=None):
    out = {m: [] for m in MODELS}
    ks = []
    for _ in range(M):
        p = fixed_p if fixed_p is not None else float(rng.beta(a_post, b_post))
        k = int(rng.binomial(len(unread), p))
        chosen = rng.choice(unread, size=k, replace=False) if k else np.array([], int)
        others = rng.integers(0, len(S) - 1, size=k)          # a different record's severity
        others = np.where(others >= chosen, others + 1, others) if k else others
        shift = rng.choice(shifts, size=k) * rng.choice((-1.0, 1.0), size=k)
        ks.append(k)
        for m in MODELS:
            s2 = S.copy()
            if k:
                if m == "sign":
                    s2[chosen] = -S[chosen]
                elif m == "replace":
                    s2[chosen] = S[others]
                else:
                    s2[chosen] = S[chosen] + shift
            out[m].append(vu.var_q(vu.transfer(s2, R, H, v1, thbar, cfg, ritc), 0.995) - base)
    return out, ks


def summary(deltas):
    d = np.asarray(deltas, float)
    rel = d / abs(base)
    q = lambda a, x: float(np.percentile(a, x))
    return {"change": {"median": q(d, 50), "p2_5": q(d, 2.5), "p97_5": q(d, 97.5)},
            "relative_change": {"median": q(rel, 50), "p2_5": q(rel, 2.5), "p97_5": q(rel, 97.5)},
            "P_abs_relative_change_gt_5pct": float(np.mean(np.abs(rel) > MATERIAL))}


post, k_post = replicates()
fixed, k_fixed = replicates(fixed_p=p975)
head = subprocess.run(["git", "-C", str(AN), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = bool(subprocess.run(["git", "-C", str(AN), "status", "--porcelain", "--", "model", "results", "src"],
                            capture_output=True, text=True).stdout.strip())
result = {
    "protocol": args.protocol,
    "computed": datetime.datetime.now().isoformat(timespec="seconds"),
    "analysis_commit": head, "analysis_tree_dirty": dirty,
    "headline": {"V1_VaR995_after_repairs": base, "V1_VaR995_before_repairs": before_v995,
                 "change_from_repairs": base - before_v995,
                 "relative_change_from_repairs": (base - before_v995) / abs(before_v995),
                 "repairs_compared": REPAIRS_COMPARED},
    "takeon_base_adjustments": takeon_base,
    "rate_posterior": {"alpha": a_post, "beta": b_post, "mean": a_post / (a_post + b_post), "p97_5": p975},
    "unread_working_sample_records": int(len(unread)), "read_records_in_pool": int(len(S) - len(unread)),
    "confirmed_error_shifts": [dict(c, shift=float(x)) for c, x in zip(confirmed, shifts)],
    "replicates": M, "seed": SEED, "materiality_line_relative": MATERIAL,
    "p_from_posterior": {"K": {"mean": float(np.mean(k_post)), "p97_5": float(np.percentile(k_post, 97.5))},
                         **{m: summary(post[m]) for m in MODELS}},
    "p_at_posterior_97_5": {"p": p975, "K": {"mean": float(np.mean(k_fixed)), "p97_5": float(np.percentile(k_fixed, 97.5))},
                            **{m: summary(fixed[m]) for m in MODELS}},
}
io.open(args.out, "w", encoding="utf-8", newline="").write(json.dumps(result, indent=1) + "\n")
print("VaR99.5 %.4f (before repairs %.4f); unread %d; p ~ Beta(%.1f, %.1f), 97.5%% point %.4f"
      % (base, before_v995, len(unread), a_post, b_post, p975))
print("the change from repairs compares %s" % REPAIRS_COMPARED)
for t in takeon_base:
    print("  take-on base %-22s take-on %-10s opening %-10s severity %s%% -> %s%%"
          % (t["stem"], t["takeon_m"], t["opening_m"], t["severity_pct_before"], t["severity_pct_after"]))
for setting, block in (("posterior p", result["p_from_posterior"]), ("p at 97.5%", result["p_at_posterior_97_5"])):
    for m in MODELS:
        s = block[m]
        print("  %-11s %-7s change median %+.4f [%+.4f, %+.4f]; relative [%+.1f%%, %+.1f%%]; P(|rel|>5%%) %.3f"
              % (setting, m, s["change"]["median"], s["change"]["p2_5"], s["change"]["p97_5"],
                 100 * s["relative_change"]["p2_5"], 100 * s["relative_change"]["p97_5"],
                 s["P_abs_relative_change_gt_5pct"]))
