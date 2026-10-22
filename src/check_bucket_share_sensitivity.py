"""Older-years bucket sensitivity (the adjudication of 22 October 2026, Q5; the author's choice (i): option A, with a
sensitivity that leaves out the records whose bucket is above 30%).

Equation (1) sums the movement over every underwriting year u <= t-2, while its denominator holds every year's
reserves. Where the filing prints an "X and prior" bucket as a reserve with no development of its own, or the table
leaves older years out, the bucket is inside R and outside the movement, which pulls |S| towards zero by up to its
share. The adjudication measured the share for 383 of its 657 records and left 274 unmeasured.

This script measures the share for every primary record the stored data allows (bucket_share.py: a reader's share, a
developed older-years column, the design's diagonal-less-paid measure where it rests on a gross payments line or a
reader's placement, an eye placement's bucket, a reserve line by year against the stored grid, or a bucket reserve
line), lists the rest as not measurable with the reasons, records the distribution of the share (above 2%, 10% and
30%, and the unmeasured), and cross-checks the methods where two measure the same record. Its inputs are the census
(results/extraction_error_rate/triangle-table-scan/), the adjudication's population measures and the design's scan of
the restored grids (results/extraction_error_rate/mature-cohort/measures/), and the stored grids (pdf_extraction/):
offline, no API.

It then refits the adopted model and transfers the vignettes without the records whose share is above 30%
(sample_scope.refit_without), and reports k, the floor, both tail indices and the year-shock scale, and Vignette 1's
VaR99 and VaR99.5 and Vignette 2's VaR99 and VaR99.5 before and after and their change, beside the primary's. A record
whose share is not measured stays in the fit: the record says how many there are.

Writes check_bucket_share_sensitivity_results.json.
Usage:  python src/check_bucket_share_sensitivity.py
"""
import io
import json
import sys
import time

import bucket_share as BK
import check_earned_basis_sensitivity as EB
import sample_scope as SS
from adopted_model import SD

OUT = SD / "results" / "check_bucket_share_sensitivity_results.json"
EXTRACTION = SD / "pdf_extraction"
THRESHOLD = 0.30
LINES = (0.02, 0.10, 0.30)


def census_records():
    """{key: record} from the triangle-table census (the 571 and the other triangle-sourced records) and the design's
    scan of the restored grids (the 86), the census's record first where both hold one."""
    out = {r["stem"].replace("syndicate_", ""): r for r in SS.load_json(SS.CENSUS)["records"]}
    for r in SS.load_json(SS.SCAN_RESTORED):
        out.setdefault(r["stem"].replace("syndicate_", ""), r)
    return out


def load_record(key):
    path = EXTRACTION / ("syndicate_%s.json" % key)
    return SS.load_json(path) if path.exists() else None


def measure_primary(keys):
    rows = BK.measure_all(keys, census_records(), SS.load_json(SS.POP_MEASURES), SS.load_json(SS.POP_CLASSIFIED),
                          load_record)
    return rows


def compute():
    t0 = time.time()
    keys = [SS.key_of(o) for o in SS.primary()]
    rows = measure_primary(keys)
    dist = BK.distribution(rows, LINES)
    above = sorted((k for k, r in rows.items() if r["share"] is not None and r["share"] > THRESHOLD), key=SS.order_key)
    block = SS.refit_without(
        above, "bucket_share_above_30pct",
        "without the %d primary records whose measured older-years share is above %.0f%% (adjudication.md, Q5 option B); "
        "the %d records whose share is not measured stay in the fit" % (len(above), 100 * THRESHOLD,
                                                                         dist["n_unmeasured"]))
    for row in block["left_out"]:
        r = rows[row["record"]]
        row.update(share=r["share"], method=r["method"], detail=r["detail"])
    order = lambda d: dict(sorted(d.items(), key=lambda kv: SS.order_key(kv[0])))
    return {
        "question": ("how much of each primary record's gross reserves sits outside the years its triangle develops, and "
                     "what do the fit and the vignette stresses become without the records where it is above 30%?"),
        "source": "results/extraction_error_rate/mature-cohort/adjudication.md, Q5 (option B)",
        "measure": ("share = 1 - (gross reserves of the years the stored grid develops) / CO_g; a script measure, not "
                    "a reading (bucket_share.py's docstring gives each method and its order)"),
        "methods_in_order": list(BK.PRECEDENCE),
        "threshold": THRESHOLD,
        "distribution": {**dist, "unmeasured_reason_text": {c: BK.REASONS[c] for c in dist["reasons_unmeasured"]}},
        "adjudication_comparison": {
            "note": ("the adjudication's script measure (pop_classified.json) on the same records: measured in its "
                     "classes 'reserves outside the developed years (measured)', 'table covers the reserves (within "
                     "2%)' and 'older-years column developed in the grid'"),
            **adjudication_counts(keys)},
        "cross_check": BK.cross_check(rows),
        "above_threshold": above,
        "unmeasured": order({k: {"reasons": r["reasons_unmeasured"]} for k, r in rows.items() if r["share"] is None}),
        "by_record": order({k: {"share": r["share"], "method": r["method"], "other_methods": r["other_methods"]}
                            for k, r in rows.items() if r["share"] is not None}),
        **block,
        "runtime_seconds": time.time() - t0,
    }


def adjudication_counts(keys):
    pc = SS.load_json(SS.POP_CLASSIFIED)
    measured = {"reserves outside the developed years (measured)", "table covers the reserves (within 2%)"}
    shares = [pc[k]["uncovered_share"] for k in keys if k in pc and pc[k]["coverage"] in measured]
    cols = sum(1 for k in keys if k in pc and pc[k]["coverage"] == "older-years column developed in the grid")
    return {"n_measured": len(shares) + cols,
            "n_above_30_pct": int(sum(s > 0.30 for s in shares)),
            "n_above_10_pct": int(sum(s > 0.10 for s in shares)),
            "n_above_2_pct": int(sum(s > 0.02 for s in shares))}


def main():
    out = compute()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    d = out["distribution"]
    print("  %d primary records: %d measured, %d not (%s)" % (d["n"], d["n_measured"], d["n_unmeasured"],
                                                              d["reasons_unmeasured"]))
    print("  by method %s" % d["by_method"])
    print("  above 2%% %d, above 10%% %d, above 30%% %d; median %.3f"
          % (d["n_above_2_pct"], d["n_above_10_pct"], d["n_above_30_pct"], d["median_measured"]))
    print("  left out: %s" % ", ".join(out["above_threshold"]))
    EB.report(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
