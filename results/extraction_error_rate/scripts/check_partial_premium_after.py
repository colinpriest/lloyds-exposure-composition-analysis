r"""The tenth amendment's premium census rule, run again after its repairs (implementation note 8).

For every working-sample record of model/exposure_results.json (s_raw_a, opening reserves and HHI present), the
adopted block is resolved as load_and_classify resolves it, and its classes (total rows excluded, with their signs) are
compared with every premium total two independent readers agree on within 2%: the two models' own totals, or a
model's total and the table's printed total. A record is PARTIAL when its classes sum to under 80% of such a total
(the census's rule), and OFF when they are more than 2% (or 0.2m) from every such total. Records with no such pair are
listed. Nothing here reads a filing. The run records the results file's run identifier and source-data hash, which
name the records and registers it read.

    python results/extraction_error_rate/scripts/check_partial_premium_after.py
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "results", "extraction_error_rate", "tenth-census", "partial-premium",
                   "partial-premium-after-repairs.json")
sys.path.insert(0, os.path.join(ROOT, "src"))

import run_analysis as ra  # noqa: E402


def adopted(record):
    models = record.get("models") or {}
    keys = sorted(models)
    if not keys:
        return None
    if (record.get("validation") or {}).get("passed") is True:
        return models[keys[0]]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    if not cands:
        return None
    return models[cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]]


def agree(a, b):
    return a is not None and b is not None and a > 0 and b > 0 and abs(a - b) <= 0.02 * max(a, b)


def main():
    ex = json.load(io.open(os.path.join(ROOT, "model", "exposure_results.json"), encoding="utf-8"))
    ws = sorted("%s_%s" % (o["syndicate"], o["year"]) for o in ex["observations"]
                if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None)
    partial, off, no_pair = [], [], []
    for stem in ws:
        rec = json.load(io.open(os.path.join(ROOT, "pdf_extraction", "syndicate_%s.json" % stem), encoding="utf-8"))
        cm = adopted(rec)
        s = ra.mix_reconciles(cm.get("gross_premium_mix") or [], 1.0)[1]
        readers = [ra.safe_float(m.get("gross_premiums_written_gbp_m")) for m in (rec.get("models") or {}).values()]
        table = ra.safe_float((cm.get("_adobe_lob") or rec.get("_adobe_lob") or {}).get("table_total"))
        pairs = set()
        for i in range(len(readers)):
            for j in range(i + 1, len(readers)):
                if agree(readers[i], readers[j]):
                    pairs.add(round(readers[i], 6))
            if agree(readers[i], table):
                pairs.add(round(table, 6))
        if not pairs:
            no_pair.append({"stem": stem, "class_sum": round(s, 6), "model_totals": readers, "table_total": table})
        elif any(s < 0.8 * t for t in pairs):
            partial.append({"stem": stem, "class_sum": round(s, 6), "agreed_totals": sorted(pairs)})
        elif not any(abs(s - t) <= max(0.02 * t, 0.2) for t in pairs):
            off.append({"stem": stem, "class_sum": round(s, 6), "agreed_totals": sorted(pairs)})
    out = {"_about": ("the tenth amendment's premium census rule on the working sample after its repairs "
                      "(results/extraction_error_rate/scripts/check_partial_premium_after.py; implementation note 8)"),
           "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
           "analysis_run_id": ex.get("analysis_run_id"), "source_data_hash": ex.get("source_data_hash"),
           "working_sample_n": len(ws), "partial_n": len(partial), "off_n": len(off), "no_agreed_total_n": len(no_pair),
           "partial": partial, "off": off, "no_agreed_total": no_pair}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("working sample %d: partial %d, off %d, no agreed total %d" % (len(ws), len(partial), len(off), len(no_pair)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
