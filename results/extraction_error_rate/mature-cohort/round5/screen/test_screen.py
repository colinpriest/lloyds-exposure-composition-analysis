"""Mutation checks of rebase_screen.screen on the stored 2689_2023 / 2689_2022 grids (read only; offline).
  1. as stored: flagged (the defect);
  2. the restated end-2022 cells of 2020 and 2021 put back to the 2022 report's latest cells: clean;
  3. every year t cell scaled by 1.2 (a retranslation at one rate): clean;
  4. only underwriting year 2021 scaled by 1.2 on top of 2.: flagged;
  5. an aggregated_cohort anchor on 2020 leaves that column out: the flag falls to year 2021 only.
"""
import copy
import importlib.util
import io
import json
import sys

spec = importlib.util.spec_from_file_location("rs", "D:/tmp/r62/oc/rebase/rebase_screen.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXT = "D:/dev/lloyds_reserve_stress_testing/pdf_extraction/"


def grid(key):
    d = json.load(io.open(EXT + "syndicate_%s.json" % key, encoding="utf-8"))
    m = "gemini-2.5-flash"
    return (m, "_rag_triangle", copy.deepcopy(d["models"][m]["_rag_triangle"]))


def verdict(tg, pg):
    row = rs.screen("2689_2023", None, tg, pg, 108.9, 42.4)
    return rs.classify(row), row


tg, pg = grid("2689_2023"), grid("2689_2022")
v, row = verdict(tg, pg)
print("1 as stored:", v, [(y["u"], round(y["ratio"], 3)) for y in row["years"]])
assert v == "rebase"

t2 = copy.deepcopy(tg)
rows = t2[2]["development_rows"]
# the year t table's second-last cell of columns 2020 and 2021 is row 2 for 2020 (index 0) and row 1 for 2021 (index 1)
pr = pg[2]["development_rows"]
ys = pg[2]["underwriting_years"]
for u in (2020, 2021):
    j = t2[2]["underwriting_years"].index(u)
    jp = ys.index(u)
    last_p = max(i for i, r in enumerate(pr) if r[jp] is not None)
    last_t = max(i for i, r in enumerate(rows) if r[j] is not None)
    rows[last_t - 1][j] = pr[last_p][jp]
v, row = verdict(t2, pg)
print("2 restated cells put back:", v)
assert v == "clean", v

t3 = copy.deepcopy(tg)
for r in t3[2]["development_rows"]:
    for j, c in enumerate(r):
        if c is not None:
            r[j] = c * 1.2
# the p grid is untouched, so the 2022 cell ratio is 1.2 x 1.0034, 2020 and 2021 ratios are 1.2 x their stored ratios
v3, _ = verdict(t3, pg)
print("3 whole t grid x1.2 on the stored restatement:", v3)
t4 = copy.deepcopy(t2)
for r in t4[2]["development_rows"]:
    for j, c in enumerate(r):
        if c is not None:
            r[j] = c * 1.2
v, row = verdict(t4, pg)
print("3b restatement removed, then whole t grid x1.2:", v)
assert v == "clean", v

t5 = copy.deepcopy(t4)
j = t5[2]["underwriting_years"].index(2021)
rows5 = t5[2]["development_rows"]
last = max(i for i, r in enumerate(rows5) if r[j] is not None)
rows5[last - 1][j] *= 1.2
v, row = verdict(t5, pg)
print("4 one year moved 20% off the rate:", v, row["eval_all"]["flagged_years"])
assert v in ("rebase", "rebase_oldest_column_only") and 2021 in row["eval_all"]["flagged_years"]

t6 = copy.deepcopy(tg)
t6[2]["aggregated_cohort"] = {"anchor": 2020, "label": "2020 & prior", "column": 0}
v, row = verdict(t6, pg)
print("5 anchor on 2020:", v, row["eval_all"]["flagged_years"])
assert 2020 not in [y["u"] for y in row["years"]]
print("all mutation checks passed")
