"""Screen the primary sample for development tables whose history is rebased between reports: the year t table's cells
for years before t (its t-1 diagonal and older cells) differ from the year t-1 report's by more than one exchange rate
explains. Reads the fx-translation measure (cells compared per record) and the primary's keys. Read only.

Flag: cells class "changed" or "t1_amended" AND not one_rate AND the spread of the t-1 ratios or of the older ratios
(max/min - 1) above SPREAD, or any ratio more than DEV away from 1 beyond the GBP/USD move.
"""
import io
import json

FX = r"D:/tmp/r62/oc/A/results/extraction_error_rate/mature-cohort/fx-translation/fx_translation.json"
PRIM = r"D:/tmp/r62/oc/A/results/extraction_error_rate/mature-cohort/fx-translation/primary_keys.json"
SPREAD = 0.05
with io.open(FX, encoding="utf-8") as fh:
    d = json.load(fh)
with io.open(PRIM, encoding="utf-8") as fh:
    prim = json.load(fh)
prim = set(prim if isinstance(prim, list) else prim.get("keys", prim))
with io.open(r"D:/tmp/r62/oc/A/model/exposure_results.json", encoding="utf-8") as fh:
    ex = json.load(fh)
inprim = {"%s_%s" % (o["syndicate"], o["year"]) for o in ex["observations"]
          if o.get("s_raw_a") is not None}
rows = []
for k, v in d.items():
    if k.startswith("_"):
        continue
    c = v["cells"]
    if c["class"] not in ("changed", "t1_amended"):
        continue
    if c.get("one_rate"):
        continue
    rt = [x for x in (c.get("ratio_t1") or []) if x]
    rb = [x for x in (c.get("ratio_before_t1") or []) if x]
    def spread(r):
        return (max(r) / min(r) - 1) if len(r) >= 2 and min(r) > 0 else 0.0
    s = max(spread(rt), spread(rb), abs(spread(rt + rb)))
    if s > SPREAD:
        rows.append((round(s, 3), k, k in inprim, c["class"], [round(x, 3) for x in rt], [round(x, 3) for x in rb]))
rows.sort(reverse=True)
print("primary records in the model:", len(inprim))
print("flagged (all):", len(rows), "| in the primary:", sum(1 for r in rows if r[2]))
for r in rows:
    if r[2]:
        print(r)
with io.open(r"D:/tmp/r62/oc/rebase/flagged.json", "w", encoding="utf-8", newline="") as fh:
    fh.write(json.dumps([{"key": r[1], "spread": r[0], "in_primary": r[2], "class": r[3], "ratio_t1": r[4],
                          "ratio_before_t1": r[5]} for r in rows], indent=1) + "\n")
