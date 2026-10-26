"""The small-book diagnosis: where the operator's held-out adverse tail fails by size of book, on the primary.

The operator backtest (check_operator_backtest.py) scores every held-out syndicate-year against the VaR the headline
operator reads from the other syndicates' pool. Its overall counts can be right while one size band is not. This
record reads that backtest's per-target held-out predictions on the primary and sets out the calibration by size at
99 and 99.5%, for both pool rules (leave_out, and leave_out_and_target_year), in two groupings that are kept apart:

  own_quartiles          the primary's own descriptive quartiles: the boundaries are recomputed from the primary's
                         opening reserves (np.quantile at 25, 50 and 75%), so "band 1" is the smallest quarter of the
                         primary as it stands;
  fixed_original_bands   the cutoffs of the earlier 643-record sample, 172.5745, 425.362 and 837.0151141803343 (GBP m),
                         held fixed so that a different sample is read against the same bands. A record falls in band j
                         by np.searchsorted(cutoffs, R, side="right") + 1, the backtest's own rule.

The two groupings differ by the records that cross a cutoff, never by a forecast: the same flags are counted in both.
For each grouping, band and level the record holds the targets, the distinct syndicates, the exceedances against the
expected count, the exceedance rate, the event syndicates and the event record ids ("SSSS_YYYY"). For the smallest band's
events it also holds each target's observed severity and its threshold (the VaR the operator read for it) under each
pool rule.

The backtest record keeps each target's exceedance flag but not its threshold, nor its severity. The plug-in version's
thresholds are recomputed here, with no fit, from the ten fold fits' posterior means that the record stores
(check_operator_backtest.leave_out_quantiles, the backtest's own function) on the working sample the loader returns; the
recomputed flags must equal the stored flags target for target, at every level and under both pool rules, or nothing is
written. The posterior-draw version's flags are counted as stored; its thresholds are not available, because the fold
fits' draws are not written to the record.

The record is stale, and the run stops, if it is not on the loader's working sample (the targets' syndicates, years and
opening reserves, in order) or if its size quartiles are not the primary's own.

Writes check_small_book_diagnosis_results.json.
Usage:  python src/check_small_book_diagnosis.py
"""
import io
import json
import sys

import numpy as np

import check_operator_backtest as BT
from adopted_model import SD, load_sample
# a `from` import: this record is counts and thresholds, not a transferred stress, and carries the headline stamp only
from transfer_operator import HEADLINE, load_draws, stamp

OUT = SD / "results" / "check_small_book_diagnosis_results.json"
BACKTEST = SD / "results" / "check_operator_backtest_results.json"
EXPOSURE = SD / "model" / "exposure_results.json"
LEVELS = (0.99, 0.995)
#: the cutoffs of the earlier 643-record sample (GBP m), held fixed; the influence record reproduces them from that
#: sample's own quartiles before it uses them
FIXED_BAND_EDGES = (172.5745, 425.362, 837.0151141803343)
RULES = tuple(BT.POOL_RULES)
#: the backtest's two versions: the plug-in at each fold fit's posterior means, and the mixture over its draws
VERSIONS = ("honest_plug_in", "honest_posterior_draws")
N_BANDS = 4
#: the Codex analysis's 642-record prototype (omit 6131/2021 only), kept as a cross-check and nothing else. The primary
#: here is not that sample (the census set records aside under rule 8), so it is expected to differ.
CODEX_642_PROTOTYPE = {
    "label": ("recommendation of the Codex analysis, 642-record prototype (only 6131/2021 omitted), plug-in version, "
              "pool rule leave_out; a cross-check, not a result of this repository"),
    "own_quartile_1": {"0.99": [8, 161], "0.995": [6, 161]},
    "fixed_band_1": {"0.99": [8, 160], "0.995": [6, 160]},
    "events_0.995": ["1991_2015", "1991_2016", "1991_2019", "1991_2020", "1945_2020", "5820_2016"],
    "events_0.99_extra": ["1991_2017", "1991_2018"],
}


def level_key(a):
    return "%g" % a


def record_id(syn, yr):
    return "%s_%s" % (syn, yr)


def own_edges(R):
    """The primary's own quartile boundaries: the 25, 50 and 75% points of the targets' opening reserves."""
    return tuple(float(e) for e in np.quantile(np.asarray(R, float), [0.25, 0.5, 0.75]))


def band_of(R, edges):
    """The band 1..4 of each book (1 the smallest): the backtest's rule, np.searchsorted(edges, R, side="right") + 1."""
    return np.searchsorted(np.asarray(edges, float), np.asarray(R, float), side="right") + 1


def group_row(flags, mask, syn, yr, level):
    """The row for the targets in `mask` (bool per target) at `level`, from exceedance flags `flags`: the targets and
    the distinct syndicates, the exceedances against the expected count n (1 - level), the rate, and the event
    syndicates and event record ids."""
    flags, mask = np.asarray(flags, bool), np.asarray(mask, bool)
    syn, yr = np.asarray(syn), np.asarray(yr)
    hit = mask & flags
    n = int(mask.sum())
    return {
        "n_targets": n,
        "n_syndicates": int(len(set(syn[mask].tolist()))),
        "exceedances": int(hit.sum()),
        "expected": float(n * (1.0 - level)),
        "rate": float(hit.sum() / n) if n else None,
        "nominal_rate": float(1.0 - level),
        "event_syndicates": sorted(set(int(s) for s in syn[hit].tolist())),
        "n_event_syndicates": int(len(set(syn[hit].tolist()))),
        "event_record_ids": [record_id(s, y) for s, y in zip(syn[hit].tolist(), yr[hit].tolist())]}


def band_table(flags, bands, syn, yr, level, n_bands=N_BANDS):
    """{"band_j": group_row} for the four bands of `bands` (1 the smallest books)."""
    bands = np.asarray(bands)
    return {"band_%d" % j: group_row(flags, bands == j, syn, yr, level) for j in range(1, n_bands + 1)}


def grouping_table(flags_by_level, bands, syn, yr, levels=LEVELS):
    return {level_key(a): band_table(flags_by_level[a], bands, syn, yr, a) for a in levels}


def canonical_sha256(path):
    """SHA-256 of a JSON record in reproduce.py's canonical form (the keys reproduce.VOLATILE names removed, keys sorted):
    the hash --verify compares. A record's runtime_seconds changes on every pass, so a byte hash would differ between two
    passes on the same inputs; the content hash does not."""
    sys.path.insert(0, str(SD))
    import reproduce
    with open(str(path), "rb") as fh:
        return reproduce.canonical_json_sha256(fh.read())


# ------------------------------------------------------------------------ the record against the loader's sample
def check_record_is_on_sample(rec, S, R, yr, syn, ritc):
    """Stop unless the backtest record scores exactly the loader's working sample, in the loader's order, and its size
    quartiles are the primary's own. A record from an earlier sample would be read against the wrong books."""
    pt = rec["per_target"]
    tg = pt["targets"]
    problems = []
    if rec["n"] != len(S) or len(tg["syndicate"]) != len(S):
        problems.append("the record scores %d targets, the working sample has %d" % (rec["n"], len(S)))
    else:
        if [int(x) for x in tg["syndicate"]] != [int(x) for x in syn.tolist()]:
            problems.append("the targets' syndicates differ")
        if [int(x) for x in tg["year"]] != [int(x) for x in yr.tolist()]:
            problems.append("the targets' years differ")
        if not np.array_equal(np.asarray(tg["R_gbp_m"], float), np.asarray(R, float)):
            problems.append("the targets' opening reserves differ")
        if [int(x) for x in tg["ritc"]] != [int(x) for x in np.asarray(ritc, bool).astype(int).tolist()]:
            problems.append("the targets' assumed-business flags differ")
    if not problems:
        edges = own_edges(R)
        if not np.array_equal(np.asarray(rec["size_quartiles"]["edges_gbp_m"], float), np.asarray(edges, float)):
            problems.append("the record's size quartile edges are not the primary's own")
        if not np.array_equal(np.asarray(tg["size_quartile"]), band_of(R, edges)):
            problems.append("the record's size quartile of each target differs from the primary's own bands")
    if problems:
        raise SystemExit("results/check_operator_backtest_results.json is not on the loader's working sample (%s): "
                         "regenerate it first" % "; ".join(problems))


def fold_thetas(rec):
    """{fold: the operator's parameters} at each fold fit's stored posterior means (gamma identically 0)."""
    return {int(f["fold"]): BT.operator_params(
        {p: (float(f["params"][p]["mean"]) if p in f["params"] else 0.0) for p in BT.OPERATOR_PARAMS})
        for f in rec["honest"]["fits"]}


def recompute_plug_in(rec, S, R, H, yr, syn, ritc, cfg, levels=LEVELS):
    """{rule: {level: thresholds}}: every target's plug-in VaR from the ten fold fits' stored posterior means, by the
    backtest's own function. Stops unless the recomputed exceedance flags equal the stored ones, target for target."""
    fold = BT.fold_assignment(syn, rec["honest"]["folds"])
    thetas = fold_thetas(rec)
    out = {}
    for rule, drop in (("leave_out", False), ("leave_out_and_target_year", True)):
        q = BT.leave_out_quantiles(S, R, H, ritc, fold, syn, yr, thetas, cfg, drop, levels)[BT.OPERATOR_METHOD]
        out[rule] = q
        for a in levels:
            stored = np.asarray(rec["per_target"]["exceedance_flags"]["honest_plug_in"][rule][level_key(a)], int)
            mine = (S > q[a]).astype(int)
            if not np.array_equal(stored, mine):
                bad = np.flatnonzero(stored != mine)
                raise SystemExit("the recomputed %s plug-in flags at %s differ from the record's at %d targets (first: "
                                 "%s): the fold fits' stored means do not reproduce the backtest"
                                 % (rule, level_key(a), len(bad), record_id(syn[bad[0]], yr[bad[0]])))
    return out


# ------------------------------------------------------------------------------------------- the record
def event_rows(mask, flags, S, R, yr, syn, thresholds_by_rule, level, own_band, fixed_band):
    """The events among the targets in `mask` (flags true): each with its observed severity, opening reserves, both
    groupings' band, and its threshold under each pool rule (None where the version has no thresholds)."""
    rows = []
    for i in np.flatnonzero(np.asarray(mask, bool) & np.asarray(flags, bool)):
        row = {"record_id": record_id(syn[i], yr[i]), "syndicate": int(syn[i]), "year": int(yr[i]),
               "R_gbp_m": float(R[i]), "observed_S": float(S[i]),
               "own_quartile": int(own_band[i]), "fixed_band": int(fixed_band[i]), "thresholds": {}}
        for rule, q in thresholds_by_rule.items():
            t = float(q[level][i])
            row["thresholds"][rule] = {"threshold": t, "observed_over_threshold": float(S[i] / t) if t else None}
        rows.append(row)
    return rows


def compute(rec, S, R, H, yr, syn, ritc, cfg, fixed_edges=FIXED_BAND_EDGES, levels=LEVELS):
    """The record for the backtest record `rec` on the working sample (S, R, H, yr, syn, ritc)."""
    check_record_is_on_sample(rec, S, R, yr, syn, ritc)
    edges = own_edges(R)
    own, fixed = band_of(R, edges), band_of(R, fixed_edges)
    q = recompute_plug_in(rec, S, R, H, yr, syn, ritc, cfg, levels)
    flags = rec["per_target"]["exceedance_flags"]

    versions = {}
    for ver in VERSIONS:
        versions[ver] = {"pool_rules": {}}
        for rule in RULES:
            f = {a: np.asarray(flags[ver][rule][level_key(a)], bool) for a in levels}
            versions[ver]["pool_rules"][rule] = {
                "own_quartiles": grouping_table(f, own, syn, yr, levels),
                "fixed_original_bands": grouping_table(f, fixed, syn, yr, levels)}
        versions[ver]["thresholds"] = (
            "recomputed from the fold fits' stored posterior means; equal flags to the record's at every target"
            if ver == "honest_plug_in" else
            "not available: the fold fits' draws are not written to the backtest record, so only its flags are counted")

    # the smallest band's events with their per-target thresholds (plug-in version, both pool rules)
    smallest = {}
    for a in levels:
        f = np.asarray(flags["honest_plug_in"]["leave_out"][level_key(a)], bool)
        smallest[level_key(a)] = {
            "own_quartile_1": event_rows(own == 1, f, S, R, yr, syn, q, a, own, fixed),
            "fixed_band_1": event_rows(fixed == 1, f, S, R, yr, syn, q, a, own, fixed)}
        # the event set under the target-year rule can differ from the primary pool's: list it beside, with thresholds
        g = np.asarray(flags["honest_plug_in"]["leave_out_and_target_year"][level_key(a)], bool)
        smallest[level_key(a)]["own_quartile_1_target_year_rule"] = event_rows(own == 1, g, S, R, yr, syn, q, a, own,
                                                                               fixed)
        smallest[level_key(a)]["fixed_band_1_target_year_rule"] = event_rows(fixed == 1, g, S, R, yr, syn, q, a, own,
                                                                             fixed)

    # who is in the smallest band of one grouping and not the other (the regrouping, not a new fit)
    regroup = {"in_own_quartile_1_not_fixed_band_1": [
                   {"record_id": k, "R_gbp_m": float(R[i])} for k, i in sorted(
                       ((record_id(syn[i], yr[i]), i) for i in np.flatnonzero((own == 1) & (fixed != 1))))],
               "in_fixed_band_1_not_own_quartile_1": [
                   {"record_id": k, "R_gbp_m": float(R[i])} for k, i in sorted(
                       ((record_id(syn[i], yr[i]), i) for i in np.flatnonzero((fixed == 1) & (own != 1))))],
               "reading": ("the two groupings use the same forecasts and the same flags; a record that crosses a "
                           "cutoff moves between groups and changes the denominators, not an event")}

    # the Codex analysis's prototype, beside what this primary gives
    pq = versions["honest_plug_in"]["pool_rules"]["leave_out"]
    cross = {"reference": CODEX_642_PROTOTYPE, "this_primary": {"own_quartile_1": {}, "fixed_band_1": {}},
             "expected_to_differ": ("the primary here sets aside the census's rule-8 records as well as 6131/2021, so "
                                    "its bands and denominators are not the prototype's")}
    for a in levels:
        k = level_key(a)
        o, fx = pq["own_quartiles"][k]["band_1"], pq["fixed_original_bands"][k]["band_1"]
        cross["this_primary"]["own_quartile_1"][k] = [o["exceedances"], o["n_targets"]]
        cross["this_primary"]["fixed_band_1"][k] = [fx["exceedances"], fx["n_targets"]]
    cross["events_0.995_this_primary_own_quartile_1"] = pq["own_quartiles"]["0.995"]["band_1"]["event_record_ids"]
    cross["same_counts_as_prototype"] = bool(
        cross["this_primary"]["own_quartile_1"] == CODEX_642_PROTOTYPE["own_quartile_1"]
        and cross["this_primary"]["fixed_band_1"] == CODEX_642_PROTOTYPE["fixed_band_1"])

    ex = {}
    if EXPOSURE.exists():
        with io.open(str(EXPOSURE), encoding="utf-8") as fh:
            ex = json.load(fh)
    return {
        **stamp(HEADLINE),
        "question": ("Where does the operator's held-out adverse tail fail by size of book, on the primary: at 99 and "
                     "99.5%, by the primary's own quartiles and by the fixed bands of the earlier 643-record sample?"),
        "inputs": {"backtest_record": "results/check_operator_backtest_results.json",
                   "backtest_record_sha256": canonical_sha256(BACKTEST) if BACKTEST.exists() else None,
                   "backtest_record_sha256_is": "the canonical JSON content (volatile fields such as runtime_seconds removed)",
                   "loader_run_id_without_calibration": ex.get("analysis_run_id_without_calibration"),
                   "n_working_sample": int(len(S)), "n_syndicates": int(len(set(syn.tolist()))),
                   "n_assumed_business": int(np.asarray(ritc, bool).sum()),
                   "folds": rec["honest"]["folds"], "fold_rule": "the frozen fold map (data/fold_map.json) through oos_validation.fold_assignment"},
        "levels": [level_key(a) for a in levels],
        "pool_rules": {"leave_out": "every row whose held-out unit differs from the target's (the primary pool)",
                       "leave_out_and_target_year": "as leave_out, and without the rows of the target's own reporting year"},
        "groupings": {
            "own_quartiles": {
                "reading": "the primary's own descriptive quartiles, recomputed from its opening reserves",
                "edges_gbp_m": list(edges),
                "counts": [int((own == j).sum()) for j in range(1, N_BANDS + 1)],
                "distinct_syndicates": [int(len(set(syn[own == j].tolist()))) for j in range(1, N_BANDS + 1)]},
            "fixed_original_bands": {
                "reading": ("the cutoffs of the earlier 643-record sample, held fixed; not a size boundary the data "
                            "certify as safe or unsafe"),
                "edges_gbp_m": list(fixed_edges),
                "counts": [int((fixed == j).sum()) for j in range(1, N_BANDS + 1)],
                "distinct_syndicates": [int(len(set(syn[fixed == j].tolist()))) for j in range(1, N_BANDS + 1)]}},
        "regrouping": regroup,
        "exceedance": "S_target > VaR of the transferred pool (strict); expected rate 1 - level",
        "versions": versions,
        "smallest_band_events": smallest,
        "codex_prototype_cross_check": cross,
        "note": ("counts are the stored flags of the backtest on this primary; the events of one syndicate are repeated "
                 "outcomes, not independent firms: read n_event_syndicates beside exceedances. The record gives no "
                 "explanation of the events and claims no calibration for any band"),
    }


def main(argv=None):
    if not BACKTEST.exists():
        raise SystemExit("results/check_operator_backtest_results.json is absent: run check_operator_backtest.py first")
    with io.open(str(BACKTEST), encoding="utf-8") as fh:
        rec = json.load(fh)
    S, R, H, yr, syn, ritc_f = load_sample()
    ritc = ritc_f.astype(bool)
    _draws, ref, hlo, hce = load_draws(HEADLINE)
    out = compute(rec, S, R, H, yr, syn, ritc, (ref, hlo, hce))
    with io.open(str(OUT), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    pq = out["versions"]["honest_plug_in"]["pool_rules"]["leave_out"]
    for grouping in ("own_quartiles", "fixed_original_bands"):
        for k in out["levels"]:
            b1 = pq[grouping][k]["band_1"]
            print("  %-21s %-6s band 1: %d / %d targets (%d syndicates), expected %.3f, event syndicates %s"
                  % (grouping, k, b1["exceedances"], b1["n_targets"], b1["n_syndicates"], b1["expected"],
                     b1["event_syndicates"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
