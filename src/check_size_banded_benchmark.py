"""A size-banded donor benchmark for the vignettes (the author's decision: "benchmark now").

The operator transfers every donor in the market pool onto the target book: it rescales each donor's severity by the
fitted scale law from the donor's reserve size to the target's, and reads the tail of the rescaled pool. A benchmark
that leans on the scale law as little as possible takes only the donors whose own reserves are close to the target's,
and reads their tail with little or no rescaling. If the operator's transferred quantiles sit near that benchmark where
the benchmark has the donors to say anything, the scale law is not doing the work alone.

For each vignette target (Vignette 1's 500m book; Vignette 2's 800m book before the exit and 650m after it), a band of
donors is taken: those whose opening reserves R_i lie within [lo x R_target, hi x R_target]. The primary band is x0.5 to
x2; its sensitivity is x1/1.5 (0.667) to x1.5. Within the band three readings are made at 90, 95, 99 and 99.5%, each by
pool_quantile.var_q (the inverse CDF, the rule behind every VaR in the paper):

  band_raw              the band donors' own severities, no rescaling at all;
  band_raw_clean        the same without the assumed-business (RITC or inward-transfer) donors, Vignette 1's target being
                        a clean book;
  band_operator         the band donors transferred onto the target by the headline operator (size-only, gamma = 0, the
                        headline fit's posterior means): the rescaling is small because the sizes are close.

They are compared with the operator's own reading, `operator_full_pool`: every donor transferred (the paper's
vignette figures; its 99 and 99.5% centres are checked to equal check_gamma0_vignette_results.json's exactly, or nothing
is written).

Honest counts. The inverse-CDF VaR of n equally weighted donors is one order statistic, the k-th largest. The record
gives, for each band, target and level, n, the number of syndicates, k, the expected number of donors beyond the VaR,
n (1 - alpha), and a plain reading: "readable" when at least 10 are expected beyond it, "thin" from 1 to 10 (the VaR is
the k-th largest of n), and "no estimate" below 1, where the VaR is the band's largest severity and the band cannot say
anything about that level beyond its maximum.

Intervals. A cluster bootstrap by syndicate over the whole pool (check_gamma0_vignette.py's resampler, B and seed),
with the bands applied to each replicate, so every leg and target shares the replicates; the operator legs read one
posterior draw of the headline fit per replicate, as check_gamma0_vignette.operator_vignettes does. The 2.5 and 97.5
percentiles are a resampling interval (a conditional one), not a posterior interval. A replicate whose band holds no
donor is counted and left out.

Vignette 2's change. The change at 99.5% is VaR(650m band) - VaR(800m band) for each leg, beside the operator's, from
the same replicates.

An overlay block (the concentration overlay, the gamma-free fit's posterior means) repeats the two operator legs' centres
as a labelled sensitivity.

Writes check_size_banded_benchmark_results.json.
Usage:  python src/check_size_banded_benchmark.py [B]
"""
import io
import json
import sys
import time

import numpy as np

import transfer_operator
from adopted_model import SD
from check_gamma0_vignette import SEED as G0_SEED, centres
from pool_quantile import var_q
from refit_vignettes import rank_from_top
from vignette_uncertainty import build_resampler, load_pool, load_ritc, load_targets, transfer

OUT = SD / "results" / "check_size_banded_benchmark_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
LEVELS = (0.90, 0.95, 0.99, 0.995)
#: the bands (lo, hi) as multiples of the target's reserves: the primary first
BANDS = {"x0.5_to_x2": (0.5, 2.0), "x0.667_to_x1.5": (1.0 / 1.5, 1.5)}
PRIMARY_BAND = "x0.5_to_x2"
LEGS = ("band_raw", "band_raw_clean", "band_operator")
B_DEFAULT = 4000
SEED = G0_SEED
#: the expected count beyond the VaR at which a band's reading is "readable", and below which it is "no estimate"
READABLE_BEYOND, NO_ESTIMATE_BEYOND = 10.0, 1.0


def band_mask(R, target_R, band):
    lo, hi = band
    return (R >= lo * target_R) & (R <= hi * target_R)


def ordinal(k):
    """1st, 2nd, 3rd, 4th, ..., 11th, 12th, 13th, 21st."""
    suffix = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return "%d%s" % (k, suffix)


def reading(n, alpha):
    """The plain reading of an inverse-CDF VaR of n equally weighted donors at alpha."""
    if n == 0:
        return {"n": 0, "k_from_top": None, "expected_beyond": 0.0, "reading": "no donors"}
    beyond = n * (1.0 - alpha)
    k = rank_from_top(n, alpha)
    if beyond >= READABLE_BEYOND:
        say = "readable: %.1f donors expected beyond the VaR" % beyond
    elif beyond >= NO_ESTIMATE_BEYOND:
        say = "thin: the VaR is the %s largest of %d donors (%.1f expected beyond it)" % (ordinal(k), n, beyond)
    else:
        say = ("no estimate: %.2f donors expected beyond it, so the VaR is the band's largest severity and the band "
               "says nothing about this level beyond its maximum" % beyond)
    return {"n": int(n), "k_from_top": int(k), "expected_beyond": float(beyond), "reading": say}


def legs(S, R, H, ritc, target, th, cfg, mask):
    """{leg: values} for one target and band mask."""
    Sb, Rb, Hb, rb = S[mask], R[mask], H[mask], ritc[mask]
    out = {"band_raw": Sb, "band_raw_clean": Sb[~rb]}
    out["band_operator"] = transfer(Sb, Rb, Hb, target, th, cfg, rb) if mask.any() else Sb
    return out


def quantiles(values, levels=LEVELS):
    return {"%g" % a: (var_q(values, a) if len(values) else None) for a in levels}


def summary(vals):
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    if a.size == 0:
        return {"lo": None, "hi": None, "median": None, "n_replicates": 0}
    return {"lo": float(np.percentile(a, 2.5)), "hi": float(np.percentile(a, 97.5)),
            "median": float(np.percentile(a, 50)), "n_replicates": int(a.size)}


def compute(b=B_DEFAULT, seed=SEED):
    t0 = time.time()
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    v1, v2o, v2n = load_targets()
    targets = {"V1": v1, "V2_old": v2o, "V2_new": v2n}
    draws_fit, ref, hlo, hce = transfer_operator.load_draws(transfer_operator.HEADLINE)
    cfg = (ref, hlo, hce)
    draws = transfer_operator.params(draws_fit, transfer_operator.HEADLINE)
    thbar, cen = centres(transfer_operator.HEADLINE, (S, R, H, synd, year), draws_fit, cfg, ritc, (v1, v2o, v2n))
    with io.open(GAMMA0, encoding="utf-8") as _fh:
        rec = json.load(_fh)[transfer_operator.HEADLINE]["centre"]
    if cen != rec:
        raise SystemExit("the operator's vignette centres differ from check_gamma0_vignette.py's record: %s against %s"
                         % (cen, rec))

    # the point readings
    full = {t: transfer(S, R, H, tg, thbar, cfg, ritc) for t, tg in targets.items()}
    blocks = {}
    for bname, band in BANDS.items():
        blk = {"band": {"lo_multiple": band[0], "hi_multiple": band[1]}, "targets": {}}
        for t, tg in targets.items():
            m = band_mask(R, tg[0], band)
            lg = legs(S, R, H, ritc, tg, thbar, cfg, m)
            row = {"target": {"R_gbp_m": tg[0], "H": tg[1]},
                   "R_range_gbp_m": [band[0] * tg[0], band[1] * tg[0]],
                   "n_donors": int(m.sum()), "n_syndicates": int(len(set(synd[m].tolist()))),
                   "n_assumed_business": int(ritc[m].sum()),
                   "donor_R_gbp_m": {"min": float(R[m].min()), "median": float(np.median(R[m])),
                                     "max": float(R[m].max())} if m.any() else None,
                   "operator_rescaling_factor": None}
            if m.any():
                # how far the operator rescales a band donor: sigma(target)/sigma(donor), its range over the band
                fac = lg["band_operator"][lg["band_raw"] != 0] / lg["band_raw"][lg["band_raw"] != 0]
                if fac.size:
                    row["operator_rescaling_factor"] = {"min": float(fac.min()), "median": float(np.median(fac)),
                                                        "max": float(fac.max())}
            for leg in LEGS:
                row[leg] = {"var": quantiles(lg[leg]),
                            "counts": {"%g" % a: reading(len(lg[leg]), a) for a in LEVELS}}
            row["operator_full_pool"] = {"var": quantiles(full[t]),
                                         "counts": {"%g" % a: reading(len(full[t]), a) for a in LEVELS}}
            row["relative_to_operator_full_pool"] = {
                leg: {"%g" % a: (row[leg]["var"]["%g" % a] / row["operator_full_pool"]["var"]["%g" % a] - 1.0
                                 if row[leg]["var"]["%g" % a] is not None else None) for a in LEVELS}
                for leg in LEGS}
            blk["targets"][t] = row
        blocks[bname] = blk

    # the resampling intervals: one cluster resampler over the whole pool, the bands applied to each replicate
    draw_syn = build_resampler(synd, year, "cluster")
    rng = np.random.default_rng(seed)
    ndraw = len(draws["k"])
    acc = {bname: {t: {leg: {"%g" % a: [] for a in LEVELS} for leg in LEGS} for t in targets} for bname in BANDS}
    acc_full = {t: {"%g" % a: [] for a in LEVELS} for t in targets}
    acc_d995 = {bname: {leg: [] for leg in LEGS} for bname in BANDS}
    acc_d995_full = []
    empty = {bname: {t: 0 for t in targets} for bname in BANDS}
    for _ in range(b):
        idx, _w = draw_syn(rng)
        j = rng.integers(0, ndraw)
        th = {p: draws[p][j] for p in draws}
        Si, Ri, Hi, ri = S[idx], R[idx], H[idx], ritc[idx]
        for t, tg in targets.items():
            a_full = transfer(Si, Ri, Hi, tg, th, cfg, ri)
            for a in LEVELS:
                acc_full[t]["%g" % a].append(var_q(a_full, a))
        acc_d995_full.append(var_q(transfer(Si, Ri, Hi, v2n, th, cfg, ri), 0.995)
                             - var_q(transfer(Si, Ri, Hi, v2o, th, cfg, ri), 0.995))
        for bname, band in BANDS.items():
            got = {}
            for t, tg in targets.items():
                m = band_mask(Ri, tg[0], band)
                if not m.any():
                    empty[bname][t] += 1
                    got[t] = None
                    continue
                lg = legs(Si, Ri, Hi, ri, tg, th, cfg, m)
                got[t] = lg
                for leg in LEGS:
                    for a in LEVELS:
                        acc[bname][t][leg]["%g" % a].append(var_q(lg[leg], a) if len(lg[leg]) else None)
            for leg in LEGS:
                if got["V2_old"] is not None and got["V2_new"] is not None and len(got["V2_old"][leg]) \
                        and len(got["V2_new"][leg]):
                    acc_d995[bname][leg].append(var_q(got["V2_new"][leg], 0.995) - var_q(got["V2_old"][leg], 0.995))

    for bname in BANDS:
        for t in targets:
            row = blocks[bname]["targets"][t]
            for leg in LEGS:
                row[leg]["resampling_interval"] = {"%g" % a: summary(acc[bname][t][leg]["%g" % a]) for a in LEVELS}
            row["operator_full_pool"]["resampling_interval"] = {"%g" % a: summary(acc_full[t]["%g" % a])
                                                               for a in LEVELS}
            row["replicates_with_an_empty_band"] = empty[bname][t]
        d = {}
        for leg in LEGS:
            o = blocks[bname]["targets"]["V2_old"][leg]["var"]["0.995"]
            nw = blocks[bname]["targets"]["V2_new"][leg]["var"]["0.995"]
            d[leg] = {"centre": (nw - o) if (o is not None and nw is not None) else None,
                      "resampling_interval": summary(acc_d995[bname][leg])}
        d["operator_full_pool"] = {"centre": cen["V2_d995"], "resampling_interval": summary(acc_d995_full)}
        blocks[bname]["V2_change_995"] = d

    # the overlay: the two operator legs' centres under the gamma-free fit's posterior means
    od, oref, olo, ohi = transfer_operator.load_draws(transfer_operator.OVERLAY)
    ocfg = (oref, olo, ohi)
    oth = transfer_operator.params({p: float(np.mean(od[p])) for p in od}, transfer_operator.OVERLAY)
    overlay = {**transfer_operator.stamp(transfer_operator.OVERLAY), "bands": {}}
    for bname, band in BANDS.items():
        overlay["bands"][bname] = {}
        for t, tg in targets.items():
            m = band_mask(R, tg[0], band)
            overlay["bands"][bname][t] = {
                "band_operator": quantiles(transfer(S[m], R[m], H[m], tg, oth, ocfg, ritc[m])) if m.any() else None,
                "operator_full_pool": quantiles(transfer(S, R, H, tg, oth, ocfg, ritc))}

    return {
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "question": ("what do the donors whose own reserves are close to the target's say about the target's tail, "
                     "read with little or no rescaling, beside the operator's transferred quantiles; and where are they "
                     "too few to say anything?"),
        "pool": {"n_donors": int(len(S)), "n_syndicates": int(len(set(synd.tolist()))),
                 "n_assumed_business": int(ritc.sum()),
                 "definition": "the vignette donor pool (the shipped tool's donors, vignette_uncertainty.load_pool)"},
        "levels": list(LEVELS), "bands": {k: list(v) for k, v in BANDS.items()}, "primary_band": PRIMARY_BAND,
        "legs": {"band_raw": "the band donors' own severities, no rescaling",
                 "band_raw_clean": "the band donors' own severities, without the assumed-business donors",
                 "band_operator": ("the band donors transferred onto the target by the headline operator at the "
                                   "headline fit's posterior means (a small rescaling, the sizes being close)"),
                 "operator_full_pool": ("every donor transferred by the headline operator at the posterior means: the "
                                        "paper's vignette figures")},
        "quantile_rule": "pool_quantile.var_q (the inverse CDF)",
        "count_rule": ("k_from_top is the order statistic the inverse-CDF VaR reads, counted from the largest; "
                       "'readable' needs at least %g donors expected beyond the VaR, 'thin' 1 to %g, and below 1 the VaR "
                       "is the band's largest severity: no estimate" % (READABLE_BEYOND, READABLE_BEYOND)),
        "interval": ("resampling interval: the 2.5 and 97.5 percentiles over a cluster bootstrap by syndicate of the "
                     "whole pool (B = %d, seed %d), the bands applied to each replicate, the operator legs with one "
                     "posterior draw of the headline fit per replicate; a conditional resampling interval, not a "
                     "posterior interval" % (b, seed)),
        "B": int(b), "seed": int(seed),
        "operator_centres_checked_against": ("results/check_gamma0_vignette_results.json, the headline block's centre "
                                             "(V1 VaR99 and VaR99.5, Vignette 2's VaR99.5 before and after and their "
                                             "change), equal exactly"),
        "by_band": blocks,
        "overlay_sensitivity": overlay,
        "runtime_seconds": time.time() - t0,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    b = int(argv[0]) if argv and argv[0].isdigit() else B_DEFAULT
    out = compute(b)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    for bname, blk in out["by_band"].items():
        print("band %s" % bname)
        for t, row in blk["targets"].items():
            print("  %-6s R %.0fm: %d donors from %d syndicates (%d assumed-business)"
                  % (t, row["target"]["R_gbp_m"], row["n_donors"], row["n_syndicates"], row["n_assumed_business"]))
            for a in LEVELS:
                key = "%g" % a
                print("    %-6s raw %s  operator-in-band %s  operator %s   [%s]"
                      % (key, _f(row["band_raw"]["var"][key]), _f(row["band_operator"]["var"][key]),
                         _f(row["operator_full_pool"]["var"][key]), row["band_raw"]["counts"][key]["reading"]))
        d = blk["V2_change_995"]
        print("  V2 change at 99.5%%: raw %s, operator-in-band %s, operator %s"
              % (_f(d["band_raw"]["centre"]), _f(d["band_operator"]["centre"]), _f(d["operator_full_pool"]["centre"])))
    return 0


def _f(x):
    return "  n/a " if x is None else "%.4f" % x


if __name__ == "__main__":
    sys.exit(main())
