"""Round-2 reading batches: aggregated older-years columns (63 primary records) and exchange lines (97 records).

Each record goes to one reader in arm X (X1..X8) and one in arm Y (Y1..Y8); the arms chunk the list differently.
"""
import io
import json
import os

AGG = r"D:/tmp/r62/oc/aggcol/aggcol.json"
FX = r"D:/tmp/r62/oc/A/results/extraction_error_rate/mature-cohort/fx-translation/fx_translation.json"
OUT = r"D:/tmp/r62/oc/readings"

with io.open(AGG, encoding="utf-8") as fh:
    agg = json.load(fh)
with io.open(FX, encoding="utf-8") as fh:
    fx = json.load(fh)

recs = []
for k, v in agg["A_aggregated_column_in_stored_grid"].items():
    if not v.get("in_primary"):
        continue
    if v.get("verdict") == "consistent" and v.get("construction") in ("calendar_year", "development_age") \
            and k not in ("4020_2016",):
        continue
    recs.append({
        "task": "aggregated_column", "part": "A", "key": k,
        "adopted_figure_m": v.get("adopted_figure_primary_m"), "report_currency": v.get("report_currency"),
        "adopted_figure_includes_column": v.get("adopted_figure_includes_column"),
        "grid_figure_with_column_m": v.get("figure_with_column_m"),
        "grid_figure_without_column_m": v.get("figure_without_column_m"),
        "column_label_year_t": v.get("column_label_year_t"),
        "column_label_year_t_minus_1": v.get("column_label_year_t_minus_1"),
        "script_construction": v.get("construction"), "script_lean": v.get("lean_if_undeterminable"),
        "pages_hint": v.get("page_numbers") or v.get("pages"),
    })
for k, v in agg["B_column_named_in_notes_not_in_stored_grid"].items():
    if not v.get("in_primary"):
        continue
    recs.append({
        "task": "aggregated_column", "part": "B", "key": k,
        "adopted_figure_m": v.get("adopted_figure_m"),
        "adopted_figure_includes_column": False,
        "grid_figure_without_column_m": v.get("estimator_on_stored_grid_m"),
        "column_label_from_notes": v.get("column_label_from_notes_year_t"),
        "script_presumption": v.get("presumption_from_anchor_pattern"),
        "extraction_notes": [s["sentence"] for s in v.get("sentences", [])][:2],
        "pages_hint": v.get("page_numbers"),
    })
n_agg = len(recs)

summ = fx["_summary"]
fx_keys = set(summ["of_those_fx_line_under_5pct_of_R"])
for k, v in fx.items():
    if k.startswith("_"):
        continue
    mv = v.get("gbp_usd_move")
    if v["cells"]["class"] == "no_comparison" and mv is not None and abs(mv) >= 0.05:
        fx_keys.add(k)
for k in sorted(fx_keys, key=lambda s: (int(s.split("_")[0]), int(s.split("_")[1]))):
    v = fx[k]
    line = v.get("fx_line") or {}
    recs.append({
        "task": "exchange_line", "key": k, "report_currency": v.get("report_currency"),
        "gbp_usd_move_in_year_t": v.get("gbp_usd_move"),
        "script_cells_class": v["cells"]["class"],
        "script_no_comparison_why": v["cells"].get("why") or v["cells"].get("reason"),
        "script_opening_m_hint": v.get("opening_m"),
        "script_fx_line_hint": {"page": line.get("page"), "line": line.get("line")} if line else None,
        "development_table_pages_hint": v.get("table_pages"),
    })
n_fx = len(recs) - n_agg

# interleave tasks so each reader gets a mix; arm Y uses a rotated order
x = [recs[i::8] for i in range(8)]
rot = recs[len(recs) // 2:] + recs[:len(recs) // 2]
y = [rot[i::8][::-1] for i in range(8)]
for arm, parts in (("X", x), ("Y", y)):
    for i, part in enumerate(parts):
        d = os.path.join(OUT, f"{arm}{i + 1}")
        os.makedirs(d, exist_ok=True)
        with io.open(os.path.join(d, "batch.json"), "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(part, indent=1) + "\n")
print("aggregated", n_agg, "exchange", n_fx, "total", len(recs))
print("X sizes", [len(p) for p in x], "Y sizes", [len(p) for p in y])
xs = {r["key"] + r["task"] for p in x for r in p}
ys = {r["key"] + r["task"] for p in y for r in p}
assert xs == ys and len(xs) == len(recs)
