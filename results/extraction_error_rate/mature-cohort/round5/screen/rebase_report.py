r"""Assemble rebase_screen.json's summary sections (population, flagged, units, validation, comparison with the crude
screen) and write rebase_report.md. Reads rebase_screen.json (written by rebase_screen.py); read only elsewhere."""
import io
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = Path("D:/tmp/r62/oc/A")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RTYPES = ("rebase", "rebase_oldest_column_only", "rebase_year_t1_only")


def jload(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def main_size(b):
    return b["size"]["all"] if b["size_basis"] == "all" else b["size"]["core"]


def fmt(x, n=3):
    return "-" if x is None else ("%.*f" % (n, x))


d = jload(HERE / "rebase_screen.json")
R = d["records"]
top = {x["donor"]: x["rank"] for x in jload(A / "results" / "check_cohort_scope_results.json")
       ["vignettes"]["v1_top_donors_headline"]["donors"]}

# ---------------------------------------------------------------- population
st = Counter(b["status"] for b in R.values())
prev_reason = Counter(b.get("prev_reason") for b in R.values() if b["status"] == "no_gross_grid_prev")
ver = Counter(b["verdict"] for b in R.values())
pop = {
    "primary": len(R),
    "no_year_t_grid": [k for k, b in R.items() if b["status"] == "no_gross_grid_year_t"],
    "no_prev_record": sorted([k for k, b in R.items() if b["status"] == "no_prev_record"],
                             key=lambda k: tuple(map(int, k.split("_")))),
    "no_gross_grid_prev": st["no_gross_grid_prev"],
    "no_gross_grid_prev_by_reason": dict(prev_reason),
    "no_gross_grid_prev_first_report_year_2015": sum(1 for k, b in R.items() if b["status"] == "no_gross_grid_prev"
                                                     and k.endswith("_2015")),
    "grids_in_both_years": st["compared"] + st["no_common_single_year"] + st["unit_unknown"],
    "compared_with_a_common_single_year": st["compared"],
    "no_common_single_year": st["no_common_single_year"],
    "unit_unknown": st["unit_unknown"],
    "verdicts": dict(ver),
}
pop["no_common_single_year_records"] = sorted(k for k, b in R.items() if b["status"] == "no_common_single_year")
pop["compared_by_p_grid_field"] = dict(Counter(("claims" if b["p_is_claims_triangle"] else "rag") for b in R.values()
                                               if b["status"] == "compared"))

# ---------------------------------------------------------------- flagged
flag_rows = []
for k, b in R.items():
    if b["verdict"] not in RTYPES:
        continue
    s = main_size(b)
    c = b["size"]["core"]
    flag_rows.append({
        "key": k, "kind": b["verdict"], "confidence": b["confidence"], "confidence_notes": b["confidence_notes"],
        "size_basis": b["size_basis"], "gross_over_R": s["gross_over_R"], "net_over_R": s["net_over_R"],
        "core_gross_over_R": c["gross_over_R"] if c else None,
        "m_effect_m": s["m_effect_m"], "m_effect_over_absM": s["m_effect_over_absM"],
        "gross_flagged_m": s["gross_flagged_m"], "gross_over_absM": s["gross_over_absM"],
        "R_m": round(b["R_grid_m"], 2), "M_m": None if b["M_grid_m"] is None else round(b["M_grid_m"], 2),
        "grid_currency": b["t_currency"], "factor": round(s["factor"], 4), "factor_median": round(s["factor_median"], 4),
        "flagged_years": s["flagged_years"], "flagged_years_under_median_factor": s["flagged_years_under_median_factor"],
        "flagged_cells": s["flagged_cells"],
        "all_year_ratios": {y["u"]: (round(y["ratio"], 4) if y.get("ratio") is not None else None) for y in b["years"]},
        "t_grid": b["t_grid"], "p_grid": b["p_grid"], "t_page": b["t_page"], "p_page": b["p_page"],
        "t_units": b["t_units"], "p_units": b["p_units"], "t_currency": b["t_currency"], "p_currency": b["p_currency"],
        "v1_top_donor_rank": top.get(k), "alt_verdicts": b.get("alt_verdicts"), "p_is_claims_triangle": b["p_is_claims_triangle"],
        "source": b["source"]})
flag_rows.sort(key=lambda r: -r["gross_over_R"])

# ---------------------------------------------------------------- units cases
units = []
for k, u in d["units_cases"].items():
    b = R[k]
    if u["converted_consistent_near_1"]:
        sub = "genuine change of units: the converted cells agree"
    elif u["raw_consistent_near_1"]:
        sub = "label slip: the raw cell values agree, so one grid's units label is wrong"
    else:
        sub = "units differ and the cells do not agree either way"
    entry = dict(u, key=k, sub=sub, rebase_pattern=(b.get("verdict_labelled_units") in RTYPES or b.get("verdict_raw_units") in RTYPES), status=b["status"], verdict_labelled_units=b.get("verdict_labelled_units"),
                 verdict_raw_units=b.get("verdict_raw_units"), t_currency=b["t_currency"], p_currency=b["p_currency"])
    ys = [y for y in b.get("years", []) if y.get("t_m") is not None]
    if ys and b.get("R_grid_m"):
        entry["t_cell_over_R_labelled"] = round(statistics.median(abs(y["t_m"]) for y in ys) / b["R_grid_m"], 4)
        entry["p_cell_over_R_labelled"] = round(statistics.median(abs(y["p_m"]) for y in ys) / b["R_grid_m"], 4)
    units.append(entry)
units.sort(key=lambda e: (e["sub"], tuple(map(int, e["key"].split("_")))))

# ---------------------------------------------------------------- validation
fx = jload(A / "results" / "extraction_error_rate" / "mature-cohort" / "fx-translation" / "fx_translation.json")
one_rate = []
for k, v in fx.items():
    if k.startswith("_") or k not in R:
        continue
    c = v["cells"]
    if c["class"] == "changed" and c.get("one_rate"):
        b = R[k]
        one_rate.append({"key": k, "fx_ratio_before_t1": c.get("ratio_before_t1"), "verdict": b["verdict"],
                         "status": b["status"],
                         "ratios": {y["u"]: round(y["ratio"], 3) for y in b.get("years", []) if y.get("ratio")}})
named = {}
for k in ("2689_2023", "5820_2016", "4020_2016", "1301_2016", "6119_2016"):
    b = R.get(k)
    if not b:
        named[k] = "not in the primary"
        continue
    named[k] = {"verdict": b["verdict"], "status": b["status"], "prev_reason": b.get("prev_reason"),
                "ratios": {y["u"]: round(y["ratio"], 4) for y in b.get("years", []) if y.get("ratio")},
                "t_page": b.get("t_page"), "p_page": b.get("p_page")}

crude = jload(HERE / "flagged.json")
crude_in = [c for c in crude if c["key"] in R]
crude_cmp = Counter(R[c["key"]]["verdict"] for c in crude_in)
crude_detail = []
for c in crude_in:
    b = R[c["key"]]
    crude_detail.append({"key": c["key"], "crude_class": c["class"], "crude_spread": c["spread"],
                         "new_verdict": b["verdict"], "units_differ": b.get("units_differ"),
                         "t_aggregated_anchor": b.get("t_aggregated_anchor"), "p_aggregated_anchor": b.get("p_aggregated_anchor"),
                         "status": b["status"]})
mine_not_crude = sorted(r["key"] for r in flag_rows if r["key"] not in {c["key"] for c in crude})
v1 = {}
for donor, rank in sorted(top.items(), key=lambda x: x[1]):
    b = R.get(donor)
    v1[donor] = {"rank": rank, "verdict": b["verdict"] if b else "not in primary",
                 "why_not_screened": (b.get("prev_reason") or b.get("status")) if b and b["status"] != "compared" else None,
                 "size_over_R": main_size(b)["gross_over_R"] if b and b["verdict"] in RTYPES else None}

# ---------------------------------------------------------------- median rule against the shared-ratio factor
cmp_ = Counter()
median_only, cluster_only = [], []
for k, b in R.items():
    if b["status"] != "compared" or b["verdict"] in ("units_case", "alignment_uncertain", "no_identity_evidence"):
        continue
    ev = b.get("eval_all")
    if not ev:
        continue
    mscope = {y["u"] for y in b["years"] if y["in_M_years"]}
    cl = bool([u for u in ev["flagged_years"] if u in mscope and u not in ev["slip_years"]])
    md = bool([u for u in ev["flagged_years_median"] if u in mscope])
    cmp_[(cl, md)] += 1
    if md and not cl:
        median_only.append(k)
    if cl and not md:
        cluster_only.append(k)
d["median_rule_comparison"] = {"cluster_and_median": cmp_[(True, True)], "cluster_only": cluster_only,
                               "median_only": median_only, "neither": cmp_[(False, False)],
                               "note": "flags in underwriting years u <= t-2 over all single years, compared records "
                                       "other than units, alignment and identity cases"}

# ---------------------------------------------------------------- write back
d["_meta"]["population"] = pop
d["population"] = pop
d["flagged"] = flag_rows
d["units_cases_list"] = units
d["alignment_uncertain"] = {k: {"lag_t": b["lag_t"], "lag_p": b["lag_p"], "verdict_lag_alignment": b.get("verdict_lag_alignment"),
                                "verdict_latest_cell_alignment": b.get("verdict_latest_cell_alignment"),
                                "ratios_latest_cell_alignment": b.get("ratios_latest_cell_alignment"),
                                "t_page": b["t_page"], "p_page": b["p_page"]}
                            for k, b in R.items() if b["verdict"] == "alignment_uncertain"}
d["no_identity_evidence"] = {k: {"ratios": {y["u"]: round(y["ratio"], 3) for y in b["years"] if y.get("ratio")},
                                 "t_page": b["t_page"], "p_page": b["p_page"], "p_is_claims_triangle": b["p_is_claims_triangle"]}
                             for k, b in R.items() if b["verdict"] == "no_identity_evidence"}
d["cell_scale_slips"] = {k: {"ratios": {y["u"]: round(y["ratio"], 3) for y in b["years"] if y.get("ratio")},
                             "t_page": b["t_page"], "p_page": b["p_page"]}
                         for k, b in R.items() if b["verdict"] == "cell_scale_slip"}
d["validation"] = {"named": named, "retranslated_one_rate_in_primary": one_rate,
                   "crude_screen": {"crude_flagged_rows": len(crude), "in_the_649": len(crude_in),
                                    "new_verdict_of_those": dict(crude_cmp), "detail": crude_detail,
                                    "flagged_now_but_not_by_crude": mine_not_crude}}
d["v1_top20_donors"] = v1
with io.open(HERE / "rebase_screen.json", "w", encoding="utf-8", newline="") as fh:
    fh.write(json.dumps(d, indent=1, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- markdown
L = []
w = L.append
w("# Rebased development tables in the primary sample (read-only screen)\n")
w("Script: `rebase_screen.py` (screen) and `rebase_report.py` (this report); output `rebase_screen.json`. Offline, no API.\n")
w("## Population\n")
w("- Primary sample: **%d** records (`s_raw_a` present, R, HHI present, gross: `check_cohort_scope.in_working_sample` on `model/exposure_results.json`)." % pop["primary"])
w("- No year t grid: %d (%s). No year t-1 record file: %d (%s)." % (len(pop["no_year_t_grid"]), ", ".join(pop["no_year_t_grid"]) or "-",
                                                                   len(pop["no_prev_record"]), ", ".join(pop["no_prev_record"])))
w("- Year t-1 record present but **no gross grid** to compare: **%d** (of which %d are 2015 reports, whose 2014 report holds no stored triangle)." % (
    pop["no_gross_grid_prev"], pop["no_gross_grid_prev_first_report_year_2015"]))
for r_, n in sorted(pop["no_gross_grid_prev_by_reason"].items(), key=lambda x: -x[1]):
    w("    - %d: %s" % (n, r_))
w("- Gross grids in both years: **%d**. Of these **%d** share at least one single (non-aggregated, on the latest diagonal) underwriting year and were compared (RAG against RAG for %d; %d compare against the year t-1 claims triangle); %d share none (misshapen or offset grids: %s); %d has a units label that cannot be converted." % (
    pop["grids_in_both_years"], pop["compared_with_a_common_single_year"], pop["compared_by_p_grid_field"].get("rag", 0),
    pop["compared_by_p_grid_field"].get("claims", 0), pop["no_common_single_year"], ", ".join(pop["no_common_single_year_records"]), pop["unit_unknown"]))
w("")
w("Verdicts over the %d records:\n" % len(R))
w("| verdict | records |\n|---|---|")
for v, n in sorted(pop["verdicts"].items(), key=lambda x: -x[1]):
    w("| %s | %d |" % (v, n))
w("")
w("## Method\n")
w("- Grid: the adopted one (the register's `triangle.model` for a register record, else the canonical model's `_rag_triangle`; the `_claims_triangle` only where no RAG grid is stored). The year t-1 grid is the year t-1 report's stored gross RAG grid (claims triangle as a fallback, which then needs two years agreeing before the table is accepted as the same table).")
w("- Years: every integer-labelled underwriting year in both grids except a column an `aggregated_cohort` anchor marks (either grid) and years the grid shapes do not align. The year t cell at the end of year t-1 is the year t table's second-last cell of the column, set against the year t-1 table's last cell (each grid's latest cell is its own report year's); the shift is moved by one or two cells when the grids' latest diagonals trail their report years by different amounts (lag read from the first row label), and a record whose lag cannot be reconciled is `alignment_uncertain`.")
w("- Factor: the brief asks for the median ratio. A median over 3 to 4 years can sit on a restated year (2689_2023: ratios 1.506, 1.262, 1.003, median 1.262, which would flag the unchanged 2022 cell). The screen therefore takes, as the factor, the ratio shared by the most years (within 2%), an unchanged year (within 1% of 1) winning a tie, and falls back to the median where no ratio is shared. `factor_median` and `flagged_years_under_median_factor` are kept for every flagged record so that the brief's median rule can be compared.")
w("- Flag: a year's cell departs from `factor x` (year t-1 cell) by more than 5% **and** by more than max(1% of R, 1m) in the year t table's terms. R is the loader's opening reserves in the grid's currency (USD at the year-end H.10 rate for USD grids).")
w("- Tiers: `rebase` = flagged in underwriting years u <= t-2 with the oldest column of either grid left out (it may be an unmarked aggregated column); `rebase_oldest_column_only` = flagged only through that oldest column; `rebase_year_t1_only` = flagged only through underwriting year t-1 (outside M's years). Sizes use every flagged single year (oldest column included); `core_gross_over_R` leaves the oldest column out.")
w("- Size against R: sum of |year t cell - factor x year t-1 cell| over the flagged years, over R. Effect on M: the table's M (sum over u <= t-2 of latest less previous estimate, read within the year t table) differs from the movement against what the t-1 report printed by minus the sum of those differences over the years u <= t-2; shown in millions and against |M|.")
w("- Cell slips of about 1000 (a misread unit in one cell, 2121_2019 and 2001_2018) are set apart as `cell_scale_slip`, not rebases.\n")

w("## Flagged records (%d), ordered by size against R\n" % len(flag_rows))
w("`conf` is `high` unless a note under the table applies. Years are underwriting years; `diff` is the flagged cell less factor x the t-1 cell (m, grid currency).\n")
w("| key | kind | conf | gross/R | core/R | M effect m (/|M|) | factor (median) | flagged years: cell t vs cell t-1 [ratio; diff m] | pg t / t-1 | V1 rank |")
w("|---|---|---|---|---|---|---|---|---|---|")
for r in flag_rows:
    fc = "; ".join("%s: %s vs %s [%s; %s]" % (f["u"], format(int(f["cell_t"]) if float(f["cell_t"]).is_integer() else f["cell_t"], ","),
                                              format(int(f["cell_p"]) if float(f["cell_p"]).is_integer() else f["cell_p"], ","),
                                              fmt(f["ratio"], 3), fmt(f["diff_m"], 1)) for f in r["flagged_cells"])
    w("| %s | %s | %s | %s | %s | %s (%s) | %s (%s) | %s | %s / %s | %s |" % (
        r["key"], r["kind"].replace("rebase_", "").replace("rebase", "core"), r["confidence"], fmt(r["gross_over_R"], 3),
        fmt(r["core_gross_over_R"], 3), fmt(r["m_effect_m"], 1), fmt(r["m_effect_over_absM"], 2), fmt(r["factor"], 3),
        fmt(r["factor_median"], 3), fc, r["t_page"], r["p_page"], r["v1_top_donor_rank"] or "-"))
w("")
w("Notes on the `check` flags (what to look at before relying on a flag):\n")
for r in flag_rows:
    if r["confidence_notes"]:
        w("- %s: %s" % (r["key"], "; ".join(r["confidence_notes"])))
w("")

w("## Units cases (%d): the two grids state different units\n" % len(units))
w("Reported apart; not rebases. Sub-type is read from the ratios of the single years common to both grids: converted by the stated units (`conv`), and as raw numbers (`raw`).\n")
w("| key | t units / t-1 units | sub-type | conv ratios | raw ratios | verdict as labelled / as raw | pg t / t-1 | V1 rank |")
w("|---|---|---|---|---|---|---|---|")
for e in units:
    w("| %s | %s / %s | %s | %s | %s | %s / %s | %s / %s | %s |" % (
        e["key"], e["t_units"], e["p_units"], e["sub"].split(":")[0], e["ratios_converted"][:5], e["ratios_raw"][:5],
        e["verdict_labelled_units"], e["verdict_raw_units"], e["t_page"], e["p_page"], e["v1_top_donor_rank"] or "-"))
w("")
cnt = Counter(e["sub"].split(":")[0] for e in units)
w("Units cases that also show a rebase pattern (under the labelled or the raw units): %s.\n" % ", ".join(e["key"] for e in units if e["rebase_pattern"]))
w("Sub-type counts: %s.\n" % ", ".join("%s %d" % (a, n) for a, n in cnt.items()))

w("## Other records the screen sets apart\n")
w("- `alignment_uncertain` (%d): %s" % (len(d["alignment_uncertain"]), ", ".join(sorted(d["alignment_uncertain"]))))
w("- `no_identity_evidence` (%d, the year t-1 grid is the claims triangle and no two years agree, so it is probably another table): %s" % (
    len(d["no_identity_evidence"]), ", ".join(sorted(d["no_identity_evidence"]))))
w("- `cell_scale_slip` (%d): %s\n" % (len(d["cell_scale_slips"]), ", ".join(sorted(d["cell_scale_slips"]))))

w("## Validation\n")
f89 = next(r for r in flag_rows if r["key"] == "2689_2023")
w("- 2689_2023: **%s** (ratios %s; pages %s / %s). Factor %s from the unchanged 2022 cell; flagged %s; %.0f%% of R in all, %.0f%% of R without the oldest column (the 2020 column)." % (
    named["2689_2023"]["verdict"], named["2689_2023"]["ratios"], named["2689_2023"]["t_page"], named["2689_2023"]["p_page"],
    f89["factor"], [(f["u"], f["diff_m"]) for f in f89["flagged_cells"]], 100 * f89["gross_over_R"], 100 * f89["core_gross_over_R"]))
for k in ("5820_2016", "4020_2016", "1301_2016", "6119_2016"):
    n = named[k]
    if isinstance(n, str):
        w("- %s: %s" % (k, n))
    elif n["status"] != "compared":
        w("- %s: **not comparable** (%s): the 2015 report stores no triangle block, so the screen cannot test it; it is not flagged." % (k, n["prev_reason"]))
    else:
        w("- %s: **%s**, ratios %s (pages %s / %s)." % (k, n["verdict"], n["ratios"], n["t_page"], n["p_page"]))
w("")
bad = [o for o in one_rate if o["verdict"] in RTYPES]
genuine = [o for o in one_rate if o["fx_ratio_before_t1"] and abs(o["fx_ratio_before_t1"][1] - 1) > 0.02
           and 0.2 < o["fx_ratio_before_t1"][1] < 5]
w("- Of those, %d have a retranslation factor more than 2%% from 1 (the earlier diagonals' median ratio, measure 1 of the fx study) and are the genuine one-rate retranslations: verdicts %s; flagged: %s." % (
    len(genuine), dict(Counter(o["verdict"] for o in genuine)), ", ".join(o["key"] for o in genuine if o["verdict"] in RTYPES) or "-"))
w("  A flag on such a record is not for the retranslation: the one rate is divided out as the factor. It comes from a single year whose t-1 cell departs from that rate (1729_2023: 2021 at 1.776 against 1.20 for the other eight years; 4141_2022: 2018 and 2019 at 0.914 and 1.292 against 1.118; 1301_2016: underwriting year 2015 only).")
w("- Records the earlier fx-translation measure classed as retranslated at one rate (cells `changed`, `one_rate`) that are in the 649: %d; flagged now: %d (%s); verdicts %s." % (
    len(one_rate), len(bad), ", ".join(o["key"] for o in bad) or "-", dict(Counter(o["verdict"] for o in one_rate))))
cs = d["validation"]["crude_screen"]
w("- Crude screen (`flagged.json`): %d rows, %d of them in the 649. Verdict of the new screen on those: %s." % (cs["crude_flagged_rows"], cs["in_the_649"], cs["new_verdict_of_those"]))
agg = [x for x in cs["detail"] if (x["t_aggregated_anchor"] or x["p_aggregated_anchor"])]
un = [x for x in cs["detail"] if x["units_differ"]]
w("  Of the crude hits in the 649, %d have an aggregated-cohort anchor in one of the two grids and %d state different units." % (len(agg), len(un)))
w("  Flagged now (rebase tiers) but not by the crude screen: %s.\n" % (", ".join(cs["flagged_now_but_not_by_crude"]) or "-"))

mr = d["median_rule_comparison"]
w("## The brief's median factor against the shared-ratio factor\n")
w("Over the compared records (units, alignment and identity cases left out), flagged in underwriting years u <= t-2 under both factors: %d; under the shared-ratio factor only: %d (%s); under the median only: %d (%s); under neither: %d." % (
    mr["cluster_and_median"], len(mr["cluster_only"]), ", ".join(mr["cluster_only"]), len(mr["median_only"]), ", ".join(mr["median_only"]), mr["neither"]))
w("")
hi = [r for r in flag_rows if r["confidence"] == "high" and r["kind"] == "rebase"]
big = [r for r in hi if r["gross_over_R"] >= 0.05]
chk = [r for r in flag_rows if r["confidence"] == "check"]
w("## Which flagged records need a page reading\n")
w("A. High-confidence flags in years u <= t-2 (RAG against RAG, an unchanged year or shared ratio present, one currency, no disagreement from the other model's grids) with size >= 5%% of R: **%d**: %s. A reading decides whether the filing restates the history (then M is not the year's movement) or the stored grid misreads a cell. 2689_2023 is the reference case." % (
    len(big), ", ".join("%s (%.0f%%)" % (r["key"], 100 * r["gross_over_R"]) for r in big)))
small = [r for r in hi if r["gross_over_R"] < 0.05]
w("A2. High-confidence flags under 5%% of R (%d): %s. Lower priority." % (len(small), ", ".join(r["key"] for r in small)))
oc = [r for r in flag_rows if r["confidence"] == "high" and r["kind"] != "rebase"]
w("A3. High-confidence flags only through the oldest column or only through underwriting year t-1 (%d): %s. The oldest-column ones need the table's own heading read for an unmarked 'and prior' column first." % (
    len(oc), ", ".join("%s (%s)" % (r["key"], r["kind"].replace("rebase_", "")) for r in oc)))
w("B. Flags the screen cannot vouch for (%d; the reasons are listed under the table above): %s." % (len(chk), ", ".join(r["key"] for r in chk)))
w("C. Units cases with a rebase pattern: %s. Label slips (the raw cells agree, so one of the two units labels is wrong; the t grid's label sets the scale of that record's M): %s." % (
    ", ".join(e["key"] for e in units if e["rebase_pattern"]), ", ".join("%s (t cells %s of R, t-1 cells %s of R, as labelled)" % (
        e["key"], e.get("t_cell_over_R_labelled"), e.get("p_cell_over_R_labelled")) for e in units if e["sub"].startswith("label slip"))))
w("D. `alignment_uncertain`: %s; `no_identity_evidence`: %s; `cell_scale_slip`: %s (a single misread cell each, in the t grid or the t-1 grid)." % (
    ", ".join(sorted(d["alignment_uncertain"])), ", ".join(sorted(d["no_identity_evidence"])), ", ".join(sorted(d["cell_scale_slips"]))))
w("E. Not screenable (%d + %d + %d records: no year t-1 record, no t-1 gross grid, no common single year). Among Vignette 1's top 20 donors: %s." % (
    len(pop["no_prev_record"]), pop["no_gross_grid_prev"], pop["no_common_single_year"],
    ", ".join("%s (rank %d)" % (dn, x["rank"]) for dn, x in v1.items() if x["verdict"] in ("no_gross_grid_prev", "no_prev_record", "no_common_single_year"))))
w("")
d["reading_needed"] = {"A_high_confidence_ge_5pct_R": [r["key"] for r in big], "A2_high_confidence_lt_5pct_R": [r["key"] for r in small],
                       "A3_oldest_column_or_t1_only": [r["key"] for r in oc], "B_check": [r["key"] for r in chk],
                       "C_units_with_rebase_pattern": [e["key"] for e in units if e["rebase_pattern"]],
                       "C_label_slips": [e["key"] for e in units if e["sub"].startswith("label slip")]}
with io.open(HERE / "rebase_screen.json", "w", encoding="utf-8", newline="") as fh:
    fh.write(json.dumps(d, indent=1, ensure_ascii=False) + "\n")

w("## Vignette 1 top-20 donors\n")
w("| rank | donor | verdict | size / R | note |\n|---|---|---|---|---|")
for donor, x in v1.items():
    w("| %d | %s | %s | %s | %s |" % (x["rank"], donor, x["verdict"], fmt(x["size_over_R"], 3), x["why_not_screened"] or ""))
w("")
with io.open(HERE / "rebase_report.md", "w", encoding="utf-8", newline="") as fh:
    fh.write("\n".join(L) + "\n")
print("written", len(flag_rows), "flagged;", len(units), "units")
print(json.dumps(pop, indent=1)[:1500])
print(cs["new_verdict_of_those"])
print([o for o in one_rate if o["verdict"] not in ("clean",)])
print(v1)
