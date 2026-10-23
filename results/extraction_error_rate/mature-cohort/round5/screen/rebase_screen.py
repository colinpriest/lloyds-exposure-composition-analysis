r"""Screen the primary sample (649 records) for development tables that rebase their history between reports.

Read only everywhere except this folder. Offline. For each primary record with a year t-1 report grid, for each single
(not aggregated, not oldest-column) underwriting year present in both grids, the year t table's cell at the end of year
t-1 is compared with the year t-1 table's latest cell. The record's exchange factor is the median ratio over those years.

Flag (rebase): any single year whose cell departs from factor x (year t-1 cell) by more than 5% AND by more than
max(1% of R, 1m) in the year t table's terms (R: opening reserves in the grid's currency). Units case: the two grids
state different units (reported apart, not a rebase).

Tiers: "core" excludes the oldest underwriting-year column of either grid (it might be an unmarked aggregated column) and
every column an aggregated_cohort anchor marks; "oldest_only" records are flagged only through such an oldest column;
"t1_year_only" records are flagged only through underwriting year t-1 (outside the movement M's years u <= t-2).

Usage: python rebase_screen.py   (writes rebase_screen.json beside this script)
"""
import io
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = Path("D:/tmp/r62/oc/A")
EXT = Path("D:/dev/lloyds_reserve_stress_testing/pdf_extraction")
UNITS = {"thousands": 1000.0, "millions": 1.0, "units": 1e6, "ones": 1e6}   # units per million
DEV, REL_R, ABS_M, MIN_BASE = 0.05, 0.01, 1.0, 0.1
ONE_LATER = re.compile(r"(?:^|\W)(?:one|1)\s+years?\s+later")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def jload(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def order(k):
    return tuple(int(x) for x in k.split("_"))


def load_rec(key):
    p = EXT / ("syndicate_%s.json" % key)
    return jload(p) if p.exists() else None


def canonical_key(data):
    """build_mature_cohort_figures.canonical_key: the adopted model, by load_and_classify's model resolution."""
    models = data.get("models") or {}
    keys = sorted(models)
    if not keys:
        return None
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if isinstance(models[k], dict) and models[k].get("prior_year_development_pct") is not None]
    if not cands:
        return None
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda c: c[1])[0]


def usable(tri, field):
    return (isinstance(tri, dict) and tri.get("type") == "gross" and tri.get("underwriting_years")
            and tri.get("development_rows") and (field == "_rag_triangle" or tri.get("units")))


def candidates(data, prefer=None):
    """[(model, field, triangle)] in the order fx-translation's gross_grid tries them (the adopted model first)."""
    models = (data or {}).get("models") or {}
    order_ = [m for m in (prefer, canonical_key(data or {})) if m] + sorted(models)
    seen, out = set(), []
    for field in ("_rag_triangle", "_claims_triangle"):
        for mk in order_:
            if (mk, field) in seen or not isinstance(models.get(mk), dict):
                continue
            seen.add((mk, field))
            tri = models[mk].get(field)
            if usable(tri, field):
                out.append((mk, field, tri))
    return out


def page_of(tri):
    return tri.get("source_page") if tri.get("source_page") is not None else tri.get("page")


def columns(tri):
    """{u: cells by development row (None where absent)} for each integer-labelled column; plus the aggregated anchor."""
    rows = tri.get("development_rows") or []
    anchor = (tri.get("aggregated_cohort") or {}).get("anchor")
    out = {}
    ys = tri.get("underwriting_years") or []
    for j, u in enumerate(ys):
        if not isinstance(u, int) or isinstance(u, bool):
            continue
        out[u] = [r[j] if j < len(r) and isinstance(r[j], (int, float)) and not isinstance(r[j], bool) else None
                  for r in rows]
    return out, anchor, [u for u in ys if isinstance(u, int)]


def last_idx(cells):
    idx = [i for i, c in enumerate(cells) if c is not None]
    return idx[-1] if idx else None


def screen(key, rec, t_grid, p_grid, R_m, M_m, raw=False, force_shift=None):
    """Compare two grids. Returns the record's row."""
    year = int(key.split("_")[1])
    tri_t, tri_p = t_grid[2], p_grid[2]
    ct, anc_t, ys_t = columns(tri_t)
    cp, anc_p, ys_p = columns(tri_p)
    st, sp = UNITS.get(str(tri_t.get("units") or "").lower()), UNITS.get(str(tri_p.get("units") or "").lower())
    row = {"t_grid": "%s.%s" % t_grid[:2], "p_grid": "%s.%s" % p_grid[:2], "t_page": page_of(tri_t),
           "p_page": page_of(tri_p), "t_units": tri_t.get("units"), "p_units": tri_p.get("units"),
           "t_currency": tri_t.get("currency"), "p_currency": tri_p.get("currency"),
           "t_years": ys_t, "p_years": ys_p, "t_aggregated_anchor": anc_t, "p_aggregated_anchor": anc_p}
    oldest = {min(ys_t) if ys_t else None, min(ys_p) if ys_p else None} - {None}
    skip_agg = {a for a in (anc_t, anc_p) if a is not None}
    years = []

    def diag_off(cols):
        """{u: expected last index} from the newest column holding a cell: the latest diagonal runs one row up per older
        underwriting year. A grid whose latest cells do not lie on it is misshapen at that column."""
        have = {u: last_idx(c) for u, c in cols.items() if last_idx(c) is not None}
        if not have:
            return {}
        n = max(have)
        return {u: have[n] + (n - u) for u in have}

    exp_t, exp_p = diag_off(ct), diag_off(cp)
    row["newest_uy_t"], row["newest_uy_p"] = (max(exp_t) if exp_t else None), (max(exp_p) if exp_p else None)

    def cal_latest(cols, tri):
        """Calendar year of the grid's latest cell: the first development row is the end of the first year, unless its
        label says "one year later" (then the first row is one year on)."""
        rl = tri.get("row_labels")
        first = re.sub(r"\s+", " ", str(rl[0]).lower()) if rl else ""
        o = 1 if ONE_LATER.search(first) else 0
        cals = [u + last_idx(c) + o for u, c in cols.items() if last_idx(c) is not None]
        return max(cals) if cals else None

    cl_t, cl_p = cal_latest(ct, tri_t), cal_latest(cp, tri_p)
    row["lag_t"] = (year - cl_t) if cl_t else None          # years the year t grid's latest diagonal trails the report
    row["lag_p"] = (year - 1 - cl_p) if cl_p else None
    # how many cells back from the year t grid's latest the end of the year t-1 sits: 1 when both grids' latest cells
    # are their own report years' (equal lags); 0 when the year t grid trails by one more year; 2 when the year t-1 grid
    # trails by one more. Any other lag pair is a misshapen grid: not compared.
    shift = (1 + row["lag_p"] - row["lag_t"]) if (row["lag_t"] is not None and row["lag_p"] is not None) else None
    row["shift"] = shift
    row["alignment_uncertain"] = shift != 1
    shift = force_shift if force_shift is not None else (shift if shift in (0, 1, 2) else 1)
    for u in sorted(set(ct) & set(cp)):
        if u in skip_agg or u > year - 1:
            continue
        tl, pl = last_idx(ct[u]), last_idx(cp[u])
        if tl is None or pl is None:
            continue
        item = {"u": u, "oldest_col": u in oldest, "in_M_years": u <= year - 2}
        if tl < shift:
            item["irregular"] = "year t column has no cell at the end of year t-1"
            years.append(item)
            continue
        if tl != exp_t.get(u) or pl != exp_p.get(u):
            item["irregular"] = "latest cell off the latest diagonal (t row %s, expected %s; t-1 row %s, expected %s)" % (
                tl, exp_t.get(u), pl, exp_p.get(u))
            years.append(item)
            continue
        if any(c is None for c in ct[u][:tl + 1]) or any(c is None for c in cp[u][:pl + 1]):
            item["irregular"] = "a gap inside the column"
            years.append(item)
            continue
        # calendar alignment: each grid's latest cell is its report year's, so the year t table's second-last cell is
        # the end of year t-1, set against the year t-1 table's latest cell
        item["cell_t"], item["cell_p"] = ct[u][tl - shift], cp[u][pl]
        item["age"] = pl
        item["age_t"] = tl - shift
        years.append(item)
    reg = [y for y in years if "irregular" not in y]
    row["n_irregular_years"] = len(years) - len(reg)
    row["irregular"] = [{"u": y["u"], "why": y["irregular"]} for y in years if "irregular" in y]
    row["units_differ"] = str(tri_t.get("units")).lower() != str(tri_p.get("units")).lower()
    if raw and st is not None and sp is not None:
        st = sp = 1000.0
    if st is None or sp is None:
        row["status"] = "unit_unknown"
        return row
    if not reg:
        row["status"] = "no_common_single_year"
        return row
    for y in reg:
        y["t_m"], y["p_m"] = y["cell_t"] / st, y["cell_p"] / sp
        y["ratio_raw"] = (y["cell_t"] / y["cell_p"]) if y["cell_p"] else None
        y["ratio"] = (y["t_m"] / y["p_m"]) if y["p_m"] else None
    row["status"] = "compared"
    row["years"] = reg
    row["R_grid_m"], row["M_grid_m"] = R_m, M_m
    thr = max(REL_R * R_m, ABS_M)
    row["threshold_m"] = thr

    claims_p = p_grid[1] == "_claims_triangle"

    def cluster_factor(items):
        """The exchange factor: the ratio shared by the most years (within 2%); a ratio within 1% of 1 wins a tie (an
        unchanged cell), then the larger base. No shared ratio and no unchanged cell: the median (the brief's rule)."""
        best = None
        for c in items:
            f = c["ratio"]
            if f == 0:
                continue
            members = [y for y in items if abs(y["ratio"] / f - 1) <= 0.02]
            key = (len(members), abs(f - 1) <= 0.01, sum(abs(y["p_m"]) for y in members))
            if best is None or key > best[0]:
                best = (key, f, members)
        return best

    def slip(rf):
        """A cell that differs from the factor by about 1000 or 1e6 (a misread unit), either way."""
        r = abs(rf)
        return any(lo <= r <= hi for lo, hi in ((900, 1100), (1 / 1100.0, 1 / 900.0), (9e5, 1.1e6), (1 / 1.1e6, 1 / 9e5)))

    def evaluate(subset, label):
        items = [y for y in subset if y["ratio"] is not None and abs(y["p_m"]) >= MIN_BASE]
        if not items:
            return None
        med = statistics.median([y["ratio"] for y in items])
        best = cluster_factor(items)
        # a claims-triangle comparator is another table until two years agree; a RAG table needs one unchanged year
        identity = bool(best and (best[0][0] >= 2 or (best[0][1] and not claims_p)))
        m = best[1] if identity else med
        out = {"factor": m, "factor_median": med, "identity_evidence": identity, "n_ratio_years": len(items),
               "flagged_years": [], "flagged_years_median": [], "slip_years": [], "all": []}
        for y in subset:
            for fac, tag in ((m, "flagged_years"), (med, "flagged_years_median")):
                diff = y["t_m"] - fac * y["p_m"]
                dev = abs(diff) > DEV * abs(fac * y["p_m"]) if y["p_m"] else abs(y["t_m"]) > 0
                if dev and abs(diff) > thr:
                    out[tag].append(y["u"])
                if tag == "flagged_years":
                    rec_ = {"u": y["u"], "diff_m": diff, "dev_flag": bool(dev and abs(diff) > thr)}
                    if rec_["dev_flag"] and y["p_m"] and m and slip(y["t_m"] / (m * y["p_m"])):
                        rec_["slip"] = True
                        out["slip_years"].append(y["u"])
                    out["all"].append(rec_)
        return out

    # the three tiers: all single years; core (oldest column of either grid left out); and the factor from all years
    full = evaluate(reg, "all")
    core_years = [y for y in reg if not y["oldest_col"]]
    core = evaluate(core_years, "core") if core_years else None
    row["eval_all"], row["eval_core"] = full, core
    return row


def classify(row, ignore_alignment=False):
    """Reduce the evaluations to a verdict for the record."""
    if row["status"] != "compared":
        return row["status"]
    full, core = row["eval_all"], row["eval_core"]
    if row.get("alignment_uncertain") and not ignore_alignment:
        return "alignment_uncertain"
    ident = bool((core and core["identity_evidence"]) or (full and full["identity_evidence"]))
    row["identity_evidence"] = ident
    if not ident and row["p_grid"].endswith("_claims_triangle"):
        return "no_identity_evidence"
    mscope = {y["u"] for y in row["years"] if y["in_M_years"]}

    def flagged(ev, in_m):
        if not ev:
            return [], []
        keep = [u for u in ev["flagged_years"] if u not in ev["slip_years"] and ((u in mscope) == in_m)]
        sl = [u for u in ev["slip_years"] if (u in mscope) == in_m]
        return keep, sl

    ck, cs = flagged(core, True)
    ak, as_ = flagged(full, True)
    c1, cs1 = flagged(core, False)
    a1, as1 = flagged(full, False)
    if ck:
        return "rebase"
    if ak:
        return "rebase_oldest_column_only"
    if c1 or a1:
        return "rebase_year_t1_only"
    if cs or as_ or cs1 or as1:
        return "cell_scale_slip"
    return "clean"


def prev_reason(prev):
    """Why a year t-1 record offers no gross grid."""
    kinds = set()
    for m, v in (prev.get("models") or {}).items():
        if not isinstance(v, dict):
            continue
        for f in ("_rag_triangle", "_claims_triangle"):
            t = v.get(f)
            if isinstance(t, dict):
                kinds.add((t.get("type"), bool(t.get("development_rows")), t.get("units")))
    if not kinds:
        return "t-1 record holds no triangle block"
    if any(k[0] == "gross" for k in kinds):
        return "t-1 gross triangle without development rows or units"
    if any(k[0] == "net" for k in kinds):
        return "t-1 triangle is net only"
    if any(k[2] in ("percentage", "percent") for k in kinds):
        return "t-1 triangle is a loss-ratio percentage table"
    return "t-1 triangle block has no development rows (type none)"


def main():
    ex = jload(A / "model" / "exposure_results.json")
    recs = [o for o in ex["observations"] if (
        o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None
        and o.get("pyd_basis") == "gross")]
    rates = {int(y): v["usd_per_gbp"] for y, v in ex["fx_conversion"]["year_end_rates_used"].items()}
    reg = {k: v for k, v in jload(A / "data" / "mature_cohort_figures.json").items() if not k.startswith("_")}
    top = {d["donor"]: d["rank"] for d in jload(A / "results" / "check_cohort_scope_results.json")
           ["vignettes"]["v1_top_donors_headline"]["donors"]}
    out, rows = {}, {}
    for o in sorted(recs, key=lambda o: (o["syndicate"], o["year"])):
        key = "%s_%s" % (o["syndicate"], o["year"])
        year = o["year"]
        base = {"key": key, "source": o["pyd_basis_source"], "route": o["pyd_cohort_route"],
                "report_currency": o["report_currency"], "v1_top_donor_rank": top.get(key),
                "s_raw_a": o["s_raw_a"]}
        data = load_rec(key)
        prefer = ((reg.get(key) or {}).get("triangle") or {}).get("model")
        cands = candidates(data, prefer) if data else []
        prev_key = "%s_%d" % (o["syndicate"], year - 1)
        prev = load_rec(prev_key)
        pc = candidates(prev) if prev else []
        if not data or not cands:
            base["status"] = "no_gross_grid_year_t"
        elif prev is None:
            base["status"] = "no_prev_record"
        elif not pc:
            base["status"] = "no_gross_grid_prev"
            base["prev_reason"] = prev_reason(prev)
        else:
            # the register's grid is the adopted one for a register record
            t_grid = cands[0]
            want = (reg.get(key) or {}).get("triangle")
            if want:
                match = [c for c in cands if c[1] == "_rag_triangle"
                         and c[2].get("underwriting_years") == want["underwriting_years"]
                         and c[2].get("source_page") == want["stored_source_page"] and c[0] == want["model"]]
                base["register_grid_matched"] = bool(match)
                if match:
                    t_grid = match[0]
            base["t_is_rag"] = t_grid[1] == "_rag_triangle"
            base["p_is_claims_triangle"] = pc[0][1] == "_claims_triangle"
            gc = t_grid[2].get("currency") or o["report_currency"]
            to_grid = rates[year] if str(gc).upper() == "USD" else 1.0
            base["grid_currency"] = gc
            base["grid_currency_ne_report"] = str(gc).upper() != str(o["report_currency"]).upper()
            R_m = o["opening_reserves_gbp_m"] * to_grid
            M_m = (o["pyd_gbp_m"] * to_grid) if o.get("pyd_gbp_m") is not None else None
            p_grid = pc[0]
            r = screen(key, o, t_grid, p_grid, R_m, M_m)
            base.update(r)
            # the other (model, field) pairs: does the verdict change?
            alts = {}
            for tg in cands:
                for pg in pc:
                    if (tg[0], tg[1]) == (t_grid[0], t_grid[1]) and (pg[0], pg[1]) == (p_grid[0], p_grid[1]):
                        continue
                    if tg[1] != pg[1]:
                        continue
                    rr = screen(key, o, tg, pg, R_m, M_m)
                    alts["%s.%s|%s.%s" % (tg[0], tg[1], pg[0], pg[1])] = classify(rr)
            base["alt_verdicts"] = alts
            base["status"] = r["status"]
            if r["units_differ"] and r["status"] in ("compared", "unit_unknown"):
                rr = screen(key, o, t_grid, p_grid, R_m, M_m, raw=True)
                base["verdict_raw_units"] = classify(rr)
                base["verdict_labelled_units"] = classify(base) if base["status"] == "compared" else base["status"]
                base["raw_ratios"] = [round(y["ratio"], 4) for y in rr.get("years", []) if y.get("ratio") is not None]
        base["verdict"] = classify(base) if base["status"] == "compared" else base["status"]
        if base["verdict"] == "alignment_uncertain":
            # the lag-implied alignment (shift) and the plain latest-cell alignment (shift 1) each get a verdict
            base["verdict_lag_alignment"] = classify(base, True)
            rA = screen(key, o, t_grid, p_grid, R_m, M_m, force_shift=1)
            base["verdict_latest_cell_alignment"] = classify(rA, True) if rA["status"] == "compared" else rA["status"]
            base["ratios_latest_cell_alignment"] = [(y["u"], round(y["ratio"], 4) if y.get("ratio") else None)
                                                    for y in rA.get("years", [])]
            rr_ = [y["ratio"] for y in rA.get("years", []) if y.get("ratio") and abs(y["p_m"]) >= MIN_BASE]
            tight = bool(rr_) and min(rr_) > 0 and max(rr_) / min(rr_) - 1 <= 0.03
            base["latest_cell_alignment_tight"] = tight
            va, vl_ = base["verdict_latest_cell_alignment"], base["verdict_lag_alignment"]
            rebase_types = ("rebase", "rebase_oldest_column_only", "rebase_year_t1_only")
            if va == "clean" and tight:
                base["verdict"] = "clean"                      # the latest cells agree within 3%: that alignment is right
                base["alignment_note"] = "lag-implied shift ignored: the latest-cell alignment agrees within 3%"
            elif va in rebase_types and vl_ in rebase_types:
                base["verdict"] = va                           # flagged under both alignments
                base["alignment_note"] = "flagged under the latest-cell alignment and the lag-implied one"
                base["status_alignment_confirmed"] = True
                for f_ in ("years", "eval_all", "eval_core", "irregular", "n_irregular_years"):
                    base[f_] = rA[f_]
                base["shift_used"] = 1
        if base.get("units_differ") and base["status"] in ("compared", "unit_unknown", "no_common_single_year"):
            base["verdict"] = "units_case"
        rows[key] = base
    # numbers against R and M, for the flagged: "all" counts every single year (oldest columns included), "core" leaves
    # the oldest column of either grid out
    for k, b in rows.items():
        if b["verdict"] not in ("rebase", "rebase_oldest_column_only", "rebase_year_t1_only"):
            continue
        b["flag_kind"] = b["verdict"]
        ysel = {y["u"]: y for y in b["years"]}
        R_m, M_m = b["R_grid_m"], b["M_grid_m"]
        b["size"] = {}
        for tag in ("all", "core"):
            ev = b["eval_all"] if tag == "all" else b["eval_core"]
            if not ev:
                b["size"][tag] = None
                continue
            fl = []
            for a in ev["all"]:
                if a["dev_flag"] and not a.get("slip"):
                    y = ysel[a["u"]]
                    fl.append({"u": a["u"], "in_M_years": y["in_M_years"], "oldest_col": y["oldest_col"],
                               "cell_t": y["cell_t"], "cell_p": y["cell_p"], "age": y["age"],
                               "ratio": round(y["ratio"], 4) if y["ratio"] is not None else None,
                               "diff_m": round(a["diff_m"], 3),
                               "dev_from_factor": round(y["t_m"] / (ev["factor"] * y["p_m"]) - 1, 4)
                               if y["p_m"] else None})
            gross = sum(abs(f["diff_m"]) for f in fl)
            net = sum(f["diff_m"] for f in fl)
            # the table's M differs from the movement against the t-1 print by minus the sum of the diffs, u <= t-2
            net_M = -sum(a["diff_m"] for a in ev["all"] if ysel[a["u"]]["in_M_years"] and not a.get("slip"))
            b["size"][tag] = {
                "factor": ev["factor"], "factor_median": ev["factor_median"], "identity_evidence": ev["identity_evidence"],
                "flagged_years": [f["u"] for f in fl], "flagged_years_under_median_factor": ev["flagged_years_median"],
                "flagged_cells": fl, "gross_flagged_m": round(gross, 3), "net_flagged_m": round(net, 3),
                "gross_over_R": round(gross / R_m, 4), "net_over_R": round(net / R_m, 4),
                "m_effect_m": round(net_M, 3),
                "gross_over_absM": round(gross / abs(M_m), 3) if M_m else None,
                "m_effect_over_absM": round(abs(net_M) / abs(M_m), 3) if M_m else None}
        main = b["size"]["all"] if b["size"]["all"] and b["size"]["all"]["flagged_cells"] else (b["size"]["core"] or b["size"]["all"])
        b["size_basis"] = "all" if main is b["size"]["all"] else "core"
        b["factor"], b["factor_median"] = main["factor"], main["factor_median"]
        b["flagged_cells"] = main["flagged_cells"]
    # a confidence note on each flag
    rtypes = ("rebase", "rebase_oldest_column_only", "rebase_year_t1_only")
    for k, b in rows.items():
        if b["verdict"] not in rtypes:
            continue
        main = b["size"]["all"] if b["size_basis"] == "all" else b["size"]["core"]
        alts = set(b.get("alt_verdicts", {}).values())
        why = []
        if not main["identity_evidence"]:
            why.append("no unchanged year or shared ratio: the whole table differs, so it may be another table")
        if b.get("p_is_claims_triangle"):
            why.append("year t-1 grid is the claims triangle (not the RAG triangle)")
        if b.get("t_is_rag") is False:
            why.append("year t grid is the claims triangle")
        other = alts - set(rtypes) - {"no_identity_evidence"}
        if other:
            why.append("another model/field pair of grids gives %s" % sorted(other))
        if b.get("alignment_note"):
            why.append(b["alignment_note"])
        if b.get("t_currency") != b.get("p_currency"):
            why.append("grid currencies differ (%s against %s)" % (b.get("t_currency"), b.get("p_currency")))
        if b.get("n_irregular_years"):
            why.append("%d single years skipped as misshapen" % b["n_irregular_years"])
        b["confidence"] = "check" if why else "high"
        b["confidence_notes"] = why
    # units cases
    units = {}
    for k, b in rows.items():
        if b.get("status") in ("compared", "no_common_single_year", "unit_unknown") and b.get("units_differ"):
            ys = b.get("years") or []
            conv = [y["ratio"] for y in ys if y.get("ratio") is not None]
            raw = [y["ratio_raw"] for y in ys if y.get("ratio_raw") is not None]
            u = {"t_units": b["t_units"], "p_units": b["p_units"], "t_page": b["t_page"], "p_page": b["p_page"],
                 "ratios_converted": [round(x, 3) for x in conv], "ratios_raw": [round(x, 3) for x in raw],
                 "converted_consistent_near_1": bool(conv) and all(abs(x - 1) < 0.1 for x in conv),
                 "raw_consistent_near_1": bool(raw) and all(abs(x - 1) < 0.1 for x in raw), "verdict": b["verdict"],
                 "v1_top_donor_rank": b["v1_top_donor_rank"]}
            units[k] = u
    pop = Counter(b["status"] for b in rows.values())
    verdicts = Counter(b["verdict"] for b in rows.values())
    result = {"_meta": {
        "primary": len(recs), "source": "model/exposure_results.json observations passing check_cohort_scope."
                                        "in_working_sample (s_raw_a, R, hhi, gross): 649",
        "thresholds": {"deviation_from_factor": DEV, "diff_over_R": REL_R, "diff_abs_m": ABS_M, "min_base_m": MIN_BASE},
        "population_status": dict(pop), "verdicts": dict(verdicts),
        "units_cases": len(units)},
        "records": rows, "units_cases": units}
    with io.open(HERE / "rebase_screen.json", "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(len(recs), dict(pop))
    print(dict(verdicts), "units:", len(units))


if __name__ == "__main__":
    main()
