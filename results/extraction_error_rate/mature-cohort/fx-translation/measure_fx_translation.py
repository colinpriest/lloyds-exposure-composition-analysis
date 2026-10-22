r"""Exchange-rate basis of the primary sample's triangles, and functional-currency changes (read only; offline).

Question (the second readings of 22 October 2026, 5151/2016): a triangle whose cells are never retranslated between
reports holds each diagonal at its own year-end rate, so the step from the year t-1 diagonal to the year t diagonal
carries the translation of the foreign-currency part of the book. How many records of the primary sample have such a
triangle, or a change of functional or presentational currency in year t?

For every record of the primary sample (the keys file written by the loader under outcome "mature_cohort"), three
measures:

1. Cells. The year-t report's stored gross grid (models.<adopted model>._rag_triangle; the register's model for a
   data/mature_cohort_figures.json entry) is compared, cell by cell, with the year t-1 report's stored gross grid (the
   RAG grid, else the models' own gross triangle, _claims_triangle, where it records its units), over
   the underwriting years both print up to t-2, by calendar year (each column's cells counted back from its latest).
   Two sets of ratios (year-t report / year t-1 report): the t-1 diagonal, and the diagonals before it.
     identical         every common cell agrees (within 1 unit or 0.1%): the earlier diagonals are not retranslated
     t1_amended        the diagonals before t-1 agree, the t-1 diagonal does not (the year-t report amended it)
     mostly_identical  at least 80% of the cells before t-1 agree (some columns restated or misaligned)
     changed           the earlier diagonals were re-presented: retranslated (one_rate: the ratios within 3% of each
                       other) or restated
     no_comparison     no t-1 report grid, or no common column with a cell before t-1
   "identical" is what a table held at historical rates shows, and also what a single-currency book shows; the rate
   move of the year (GBP/USD, H.10), the stated basis (2) and the exchange line of the gross claims-outstanding
   roll-forward (4) tell them apart only in part.
2. Stated basis. The lines of the table's page, the page before and the page after that state the exchange basis of
   the table: closing (one rate for all years: "closing rate", "rates prevailing at 31 December", "consistent rate",
   "year end rates") or historical ("historical rate", "rates ruling at the date of the transaction", "original rates").
3. Currency changes in year t. (a) The presentational currency of the year-t report differs from the year t-1
   report's (pdf_extraction/currency_scan.json). (b) A line of the year-t filing that states a change of functional
   currency effective in year t ("functional currency" with "change", "changed", "effective" or "from" and the year t
   or 1 January t); the lines are kept, and FUNCTIONAL_READING below records the Claude analysis session's reading of
   every such line in the primary sample (a lower bound: a scanned page or other wording is not found).
4. The exchange line of the gross claims-outstanding roll-forward (fx_line): its first amount, as a share of R and of
   |M| (the loader's opening reserves and figure, in the report's currency). A pattern placement, not a reading.

summary in the output counts the classes.

Usage (from anywhere; writes fx_translation.json beside this script):
  python measure_fx_translation.py <primary keys json> <analysis repo>
The keys file maps "mature_cohort" to {key: {...}} (the loader's working sample). Run with PYTHONDONTWRITEBYTECODE=1
and LLOYDS_EXTRACTION_OFFLINE=1.
"""
import io
import json
import os
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = Path(sys.argv[1])
AN = Path(sys.argv[2])
sys.path.insert(0, str(AN / "results" / "extraction_error_rate" / "scripts"))
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_triangle_tables as stt  # noqa: E402
import build_mature_cohort_figures as bm  # noqa: E402

RECORDS = AN / "pdf_extraction"
UNITS = {"thousands": 1000.0, "millions": 1.0, "units": 1e6, "ones": 1e6}
REL_TOL, ABS_TOL, RATE_SPREAD, MIN_CELL, MOSTLY = 0.001, 1.0, 0.03, 100.0, 0.8

#: the Claude analysis session's reading of the functional-currency lines measure 3(b) found in the primary sample
#: (22 October 2026): "year_t" a change effective in year t; "earlier" a change effective before year t;
#: "presentation_only" the presentational currency changed, the functional did not; "none" a statement of the
#: functional currency, not a change
FUNCTIONAL_READING = {
    "33_2018": ("year_t", "sterling to US dollars on 1 January 2018 (p51, p69); presentation US dollars too"),
    "780_2015": ("year_t", "functional currency redetermined during 2015 (p5); functional and presentational US "
                           "dollars (docs/fx-conversion.md)"),
    "1084_2019": ("year_t", "sterling to US dollars as at 1 January 2019, presentation too (p34)"),
    "1200_2024": ("year_t", "sterling to US dollars from 1 January 2024 (p21); presented in sterling"),
    "1856_2021": ("year_t", "US dollars, changed from sterling as from 1 January 2021 (p26); presented in sterling"),
    "1967_2015": ("year_t", "from 1 January 2015 functional and presentational US dollars (p26)"),
    "2001_2024": ("year_t", "changed to US dollars from sterling with effect from 1 January 2024; presentation "
                            "remains sterling (p32)"),
    "2987_2015": ("year_t", "change applied prospectively from 1 January 2015 (p16)"),
    "3500_2019": ("year_t", "US dollars to sterling effective 1 January 2019 (p20)"),
    "3500_2021": ("year_t", "sterling to US dollars with effect from 1 January 2021 (p21)"),
    "4000_2016": ("year_t", "for 2016, sterling to US dollars; presented in sterling (p22)"),
    "4444_2016": ("year_t", "US dollar, changed from sterling with effect from 1 January 2016 (p20); presented in "
                            "sterling"),
    "5151_2016": ("year_t", "changed to US dollars with effect from 1 January 2016 (p20, p25); presented in sterling"),
    "435_2015": ("earlier", "GBP to USD with effect from 1 January 2014, with the transition to FRS 102 (p35)"),
    "1274_2015": ("earlier", "sterling to US dollar on 1 January 2014, with the transition to FRS 102 (p25)"),
    "4444_2015": ("none", "a change with effect from 1 January 2016, after the year (p8)"),
    "1414_2024": ("presentation_only", "presentational currency sterling to US dollar from 1 January 2024; "
                                       "functional US dollar (p51)"),
    "1458_2021": ("presentation_only", "presentational currency sterling to US dollars from 1 January 2021 (p4, p21)"),
    "1856_2024": ("presentation_only", "presentational currency sterling to US dollars for 2024 (p39)"),
    "1945_2015": ("none", "presented in sterling under FRS 102 from 1 January 2015; functional US dollars (p19)"),
    "3000_2024": ("none", "functional currency US dollars; the 2024 change is to Lloyd's accounts process (p30)"),
}
for _k in ("609_2016", "609_2017", "609_2021", "609_2022", "609_2023", "609_2024", "1458_2022", "1458_2023",
           "1729_2019", "1729_2022", "1861_2015", "1861_2016", "1910_2023", "1945_2018", "1945_2019", "2999_2024",
           "4141_2016", "4141_2017", "4141_2018", "4141_2019", "4711_2017", "5820_2016", "5820_2017"):
    FUNCTIONAL_READING[_k] = ("none", "a statement of the functional currency or of translation, not a change")

CLOSING = re.compile(r"closing\s+rates?|rates?\s+(?:of\s+exchange\s+)?prevailing\s+at|consistent\s+rate|"
                     r"year[- ]end\s+(?:exchange\s+)?rates?|(?:translated|converted|retranslated|restated|stated|"
                     r"presented)\s+(?:\w+\s+){0,4}at\s+(?:the\s+)?(?:31\s+December|balance\s+sheet\s+date|"
                     r"reporting\s+date|current\s+(?:exchange\s+)?rates?)|rates?\s+(?:of\s+exchange\s+)?(?:as\s+)?at\s+"
                     r"31\s+December|same\s+(?:exchange\s+)?rates?", re.I)
HISTORICAL = re.compile(r"historic(?:al)?\s+(?:exchange\s+)?rates?|rates?\s+(?:of\s+exchange\s+)?ruling\s+at\s+the\s+"
                        r"date|original\s+(?:exchange\s+)?rates?|not\s+(?:been\s+)?retranslated|"
                        r"rates?\s+(?:of\s+exchange\s+)?(?:at|on)\s+the\s+date\s+of\s+(?:the\s+)?transaction", re.I)
FX_CONTEXT = re.compile(r"exchange|rate|translat|currenc", re.I)
FUNCTIONAL = re.compile(r"functional\s+currency", re.I)
CHANGE = re.compile(r"chang|effective|with\s+effect|from\s+1(?:st)?\s+January|previously|re-?denominat", re.I)
FX_LINE = re.compile(r"\bfore\W*\s*\w*\s+exchange|exchange\s+(?:rate\s+)?(?:adjustments?|movements?|differences?|gains?|losses?|"
                     r"translation)|effect\s+of\s+(?:movements?\s+in\s+)?(?:foreign\s+)?exchange|currency\s+"
                     r"(?:translation|movements?)|translation\s+(?:differences?|adjustments?)|^\W*FX\b", re.I)
CO_PAGE = re.compile(r"claims\s+outstanding|outstanding\s+claims|provisions?\s+for\s+claims|claims\s+provisions?", re.I)
OPEN_PAGE = re.compile(r"(?:at|as\s+at|balance\s+at)\s*[1l](?:st)?\s+January|beginning\s+of\s+(?:the\s+)?year|"
                       r"brought\s+forward", re.I)
UNEARNED = re.compile(r"unearned|premium", re.I)
POLICY = re.compile(r"\bpolicy\b|policies|\bcash\b|are\s+translated|is\s+translated|recogni[sz]ed\s+in", re.I)


def load(key):
    path = RECORDS / ("syndicate_%s.json" % key)
    if not path.exists():
        return None
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def gross_grid(data, prefer=None):
    """The stored gross RAG grid: the preferred model's, else the adopted model's, else any model's."""
    models = (data or {}).get("models") or {}
    order = [m for m in (prefer, bm.canonical_key(data or {})) if m] + sorted(models)
    for field in ("_rag_triangle", "_claims_triangle"):
        for mk in order:
            tri = (models.get(mk) or {}).get(field) if isinstance(models.get(mk), dict) else None
            if isinstance(tri, dict) and tri.get("type") == "gross" and tri.get("underwriting_years") \
                    and tri.get("development_rows") and (field == "_rag_triangle" or tri.get("units")):
                return "%s.%s" % (mk, field), tri
    return None, None


def columns(tri):
    """{underwriting year: [cells, oldest first, in millions]} for each integer-labelled column."""
    scale = UNITS.get(str(tri.get("units") or "").lower(), 1000.0)
    out = {}
    rows = tri.get("development_rows") or []
    for j, u in enumerate(tri.get("underwriting_years") or []):
        if not isinstance(u, int):
            continue
        cells = [r[j] for r in rows if j < len(r) and isinstance(r[j], (int, float))]
        if cells:
            out[u] = [c / scale for c in cells]
    return out, scale


def scale_of(tri):
    """The grid's units per million (thousands: 1000), the scale the filing's notes are usually printed in too."""
    return UNITS.get(str((tri or {}).get("units") or "").lower(), 1000.0)


def agree(a, b, scale):
    return abs(a - b) <= max(REL_TOL * max(abs(a), abs(b)), ABS_TOL / scale)


def compare(key, year, tri_t, tri_p):
    """Classify the year-t grid against the year t-1 grid (module docstring, measure 1)."""
    ct, st = columns(tri_t)
    cp, sp = columns(tri_p)
    scale = max(st, sp)
    common = sorted(u for u in set(ct) & set(cp) if u <= year - 2)
    d1, early, cells = [], [], []
    for u in common:
        a, b = ct[u], cp[u]
        # a's last cell is calendar t; b's last is calendar t-1: align on calendar years
        for back in range(1, len(a)):
            ia, ib = len(a) - 1 - back, len(b) - back
            if ia < 0 or ib < 0:
                break
            x, y = a[ia], b[ib]
            cal = year - back
            cells.append((u, cal, x, y))
            if max(abs(x), abs(y)) * scale < MIN_CELL:
                continue
            (d1 if cal == year - 1 else early).append((u, cal, x, y))
    if not early:
        return {"class": "no_comparison", "why": "no common column with a cell before t-1" if common else
                "no common column up to t-2", "common_years": common}
    same_early = all(agree(x, y, scale) for _u, _c, x, y in early)
    same_d1 = all(agree(x, y, scale) for _u, _c, x, y in d1)
    ratios_e = [x / y for _u, _c, x, y in early if y]
    ratios_1 = [x / y for _u, _c, x, y in d1 if y]
    share_same = sum(1 for _u, _c, x, y in early if agree(x, y, scale)) / float(len(early))
    if same_early and same_d1:
        cls = "identical"
    elif same_early:
        cls = "t1_amended"
    elif share_same >= MOSTLY:
        cls = "mostly_identical"
    else:
        cls = "changed"
    one_rate = bool(ratios_e) and max(ratios_e) - min(ratios_e) <= RATE_SPREAD
    return {"class": cls, "one_rate": one_rate if cls == "changed" else None,
            "share_identical_before_t1": round(share_same, 3),
            "common_years": common, "n_cells_before_t1": len(early), "n_cells_t1": len(d1),
            "max_deviation_t1": round(max((abs(r - 1) for r in ratios_1), default=0.0), 4),
            "ratio_before_t1": [round(min(ratios_e), 4), round(statistics.median(ratios_e), 4),
                                round(max(ratios_e), 4)] if ratios_e else None,
            "ratio_t1": [round(min(ratios_1), 4), round(statistics.median(ratios_1), 4),
                         round(max(ratios_1), 4)] if ratios_1 else None}


def text_measures(key, year, pages):
    out = {"stated_basis": "unstated", "basis_lines": [], "functional_change_lines": [], "functional_lines": [],
           "text": None}
    try:
        f = stt.Filing("syndicate_" + key)
    except Exception as exc:  # pragma: no cover
        out["text"] = "error: %s" % exc
        return out
    if f.path is None:
        out["text"] = "no filing"
        return out
    look = sorted({q for p in pages for q in (p - 1, p, p + 1) if q >= 1})
    out["text"] = sorted({f.how.get(p, "?") for p in pages}) or None
    for p in look:
        lines = [ln.text for ln in f.pages.get(p, [])]
        for i, t in enumerate(lines):
            ctx = " ".join(lines[max(0, i - 1):i + 2])
            if not FX_CONTEXT.search(t):
                continue
            if HISTORICAL.search(t) or (HISTORICAL.search(ctx) and FX_CONTEXT.search(ctx)):
                out["basis_lines"].append(("historical", "p%d: %s" % (p, ctx[:300])))
            elif CLOSING.search(t) or (CLOSING.search(ctx) and re.search(r"exchange|translat|currenc", ctx, re.I)):
                out["basis_lines"].append(("closing", "p%d: %s" % (p, ctx[:300])))
    kinds = {k for k, _ in out["basis_lines"]}
    out["stated_basis"] = ("both" if len(kinds) == 2 else (kinds.pop() if kinds else "unstated"))
    out["basis_lines"] = [b for _k, b in out["basis_lines"]][:6]
    ys = str(year)
    for p in sorted(f.pages):
        lines = [ln.text for ln in f.pages[p]]
        for i, t in enumerate(lines):
            if not FUNCTIONAL.search(t):
                continue
            ctx = " ".join(lines[max(0, i - 1):i + 2])
            out["functional_lines"].append("p%d: %s" % (p, ctx[:300]))
            if CHANGE.search(ctx) and ys in ctx:
                out["functional_change_lines"].append("p%d: %s" % (p, ctx[:400]))
    out["functional_lines"] = out["functional_lines"][:4]
    out["fx_line"] = fx_line(f)
    return out


def fx_line(f):
    """The first exchange line of a claims-outstanding roll-forward: after a heading that names claims outstanding (or
    the claims provision) and an opening-balance line under it, the first line labelled as exchange, whose first amount
    is taken (the gross column, where the roll-forward prints gross first). The block ends at another note's heading or
    after 90 lines. A pattern placement, not a reading."""
    active, seen_open, count = False, False, 0
    for p in sorted(f.pages):
        for ln in f.pages[p]:
            t = ln.text
            if (not stt.amounts_of(re.sub(r"^\s*\d{1,2}\s*[.)]?\s+", "", t)) and CO_PAGE.search(t)
                    and not UNEARNED.search(t) and len(t) < 90):
                active, seen_open, count = True, False, 0
                continue
            if active and stt.NOTE_HEAD.match(t) and not CO_PAGE.search(t):
                active = False
            if not active:
                continue
            count += 1
            if count > 90:
                active = False
                continue
            if OPEN_PAGE.search(t):
                seen_open = True
            elif seen_open and FX_LINE.match(re.sub(r"^[\W\d]*(?:net\s+)?", "", ln.label or "")) and ln.amts and not POLICY.search(t):
                return {"page": p, "line": t[:240], "amount": ln.amts[0]}
    return None


NOT_RETRANSLATED = ("identical", "t1_amended", "mostly_identical")


def summary(out):
    """The counts the author's scope question needs."""
    from collections import Counter

    def order(keys):
        return sorted(keys, key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1])))

    nr = [k for k, v in out.items() if v["cells"]["class"] in NOT_RETRANSLATED]
    big = [k for k in nr if abs(out[k].get("gbp_usd_move") or 0) >= 0.05]
    fx = {k: (out[k].get("fx_line") or {}).get("share_of_opening") for k in big}
    return {
        "records": len(out),
        "cells_class": dict(Counter(v["cells"]["class"] for v in out.values())),
        "no_comparison_why": dict(Counter(v["cells"].get("why") for v in out.values()
                                          if v["cells"]["class"] == "no_comparison")),
        "stated_basis": dict(Counter(v["stated_basis"] for v in out.values())),
        "not_retranslated": order(nr),
        "not_retranslated_by_stated_basis": dict(Counter(out[k]["stated_basis"] for k in nr)),
        "not_retranslated_rate_moved_5pct": order(big),
        "of_those_fx_line_at_least_5pct_of_R": order(k for k, s in fx.items() if s is not None and s >= 0.05),
        "of_those_fx_line_under_5pct_of_R": order(k for k, s in fx.items() if s is not None and s < 0.05),
        "of_those_fx_line_not_placed": order(k for k, s in fx.items() if s is None),
        "functional_change_year_t": order(k for k, v in out.items()
                                          if (v.get("functional_change_reading") or ("",))[0] == "year_t"),
        "functional_change_year_t_cells": {k: out[k]["cells"]["class"] for k in out
                                           if (out[k].get("functional_change_reading") or ("",))[0] == "year_t"},
        "presentation_change_year_t": order(k for k, v in out.items() if v["presentation_change"]),
        "presentation_change_year_t_cells": {k: out[k]["cells"]["class"] for k in out if out[k]["presentation_change"]},
    }


def main():
    with io.open(KEYS, encoding="utf-8") as fh:
        primary = json.load(fh)["mature_cohort"]
    with io.open(AN / "pdf_extraction" / "currency_scan.json", encoding="utf-8") as fh:
        cur = json.load(fh)["reports"]
    register = bm.REGISTER
    with io.open(register, encoding="utf-8") as fh:
        reg = json.load(fh)
    import csv
    with io.open(HERE.parent / "design_per_record.csv", encoding="utf-8", newline="") as fh:
        design = {r["key"]: r for r in csv.DictReader(fh)}
    import run_analysis as ra
    rates = {int(y): v["usd_per_gbp"] for y, v in ra.FX_RATES.items()}
    out = {}
    keys = sorted(primary, key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1])))
    for n, key in enumerate(keys):
        s, year = key.split("_")
        year = int(year)
        data = load(key)
        prefer = ((reg.get(key) or {}).get("triangle") or {}).get("model")
        mk, tri = gross_grid(data, prefer)
        prev_key = "%s_%d" % (s, year - 1)
        prev = load(prev_key)
        pmk, ptri = gross_grid(prev) if prev else (None, None)
        row = {"key": key, "report_currency": (cur.get(key) or {}).get("currency"),
               "prev_report_currency": (cur.get(prev_key) or {}).get("currency"),
               "usd_per_gbp_t": rates.get(year), "usd_per_gbp_t1": rates.get(year - 1),
               "grid_model": mk, "prev_grid_model": pmk}
        if rates.get(year) and rates.get(year - 1):
            row["gbp_usd_move"] = round(rates[year] / rates[year - 1] - 1, 4)
        row["presentation_change"] = bool(row["prev_report_currency"] in ("GBP", "USD")
                                          and row["report_currency"] in ("GBP", "USD")
                                          and row["prev_report_currency"] != row["report_currency"])
        row["functional_change_reading"] = FUNCTIONAL_READING.get(key)
        if tri is None:
            row["cells"] = {"class": "no_comparison", "why": "no stored gross grid for year t"}
        elif ptri is None:
            row["cells"] = {"class": "no_comparison", "why": "no stored gross grid for year t-1"
                            if prev else "no year t-1 record"}
        else:
            row["cells"] = compare(key, year, tri, ptri)
        page = (design.get(key) or {}).get("triangle_page") or ""
        pages = [int(page)] if page.isdigit() else ([tri["source_page"]] if tri and isinstance(
            tri.get("source_page"), int) else [])
        row["table_pages"] = pages
        row.update(text_measures(key, year, pages))
        # the loader's opening reserves and figure, back in the report's currency (millions)
        to_report = (rates.get(year) or 1.0) if row["report_currency"] == "USD" else 1.0
        rec = primary[key]
        r_m = rec.get("opening_gbp_m") * to_report if rec.get("opening_gbp_m") else None
        m_m = rec.get("pyd_gbp_m") * to_report if rec.get("pyd_gbp_m") is not None else None
        row["opening_m"] = round(r_m, 3) if r_m else None
        row["figure_m"] = round(m_m, 3) if m_m is not None else None
        fxl = row.get("fx_line")
        if fxl and r_m:
            # the notes are in thousands unless the grid says otherwise; a share above half of R is a scale slip
            scales = [scale_of(tri), 1000.0, 1e6]
            fx_m = next((fxl["amount"] / sc for sc in scales if abs(fxl["amount"] / sc) <= 0.5 * r_m),
                        fxl["amount"] / scales[0])
            fxl["amount_m"] = round(fx_m, 3)
            fxl["share_of_opening"] = round(abs(fx_m) / r_m, 4)
            fxl["over_abs_figure"] = round(abs(fx_m) / abs(m_m), 3) if m_m else None
        out[key] = row
        if n % 50 == 0:
            print(n, key, row["cells"]["class"], row["stated_basis"], flush=True)
    unread = sorted(k for k, v in out.items() if v["functional_change_lines"] and k not in FUNCTIONAL_READING)
    if unread:
        raise SystemExit("functional-currency lines not yet read: %s" % unread)
    result = {"_summary": summary(out), **out}
    with io.open(HERE / "fx_translation.json", "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print("written", len(out))


if __name__ == "__main__":
    main()
