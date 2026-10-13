r"""The grid shape check (protocol/error-rate-protocol-shape-check.md, the fifteenth amendment). Read-only.

For every record of the working sample whose raw or adopted figure is triangle-sourced, test the shape of the RAW
stored grid (the grid the raw figure was computed from) against its labels and the report-year diagonal:

    S1 labels             distinct integers; no label later than t heads a column holding a filled cell
    S2 unlabelled values  no filled cell in a position without a label
    S3 label gaps         the labels run without a skipped year
    S4 shifted staircase  more tested columns one short of (or beyond) the diagonal than on it
    S5 4444 signature     year t labelled and empty while year t-1 holds exactly one cell
    S6 mature off-diag    a tested column with y <= t-2 is off its diagonal (unless its printed estimate places it)
    S7 reproduction       the grid recomputes the raw figure within max(0.5, 5%)
    R1 latest diagonal    D less paid (the census's deterministic run) against CO_g (its final run); reported only

and classify: pass, shape-fail (with the failing tests), or not checkable (with the reason). A shape-fail is "already
registered" when its key is in data/pyd_confirmed_figures.json, else "open".

    python scan_grid_shape.py                       # the whole population; writes grid-shape-check/grid-shape-check.json
    python scan_grid_shape.py --stems syndicate_4444_2022 --print   # some records; writes nothing

Offline: it reads the analysis copies of the records, the loader's registers and the census's two outputs; it opens no
filing and calls no API. Run with PYTHONDONTWRITEBYTECODE=1 and LLOYDS_EXTRACTION_OFFLINE=1.
"""
import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCR = Path(__file__).resolve().parent
STUDY = SCR.parent
AN = STUDY.parent.parent
OUT_DIR = STUDY / "grid-shape-check"
OUT = OUT_DIR / "grid-shape-check.json"
CENSUS = STUDY / "triangle-table-scan" / "triangle-table-scan.json"
CENSUS_DET = STUDY / "triangle-table-scan" / "triangle-table-scan-deterministic.json"
EXTRACTION = Path(r"D:/dev/lloyds_reserve_stress_testing")

RECON_TOL = 0.02       # R1: the protocol's opening-reserves tolerance
MATURE_LAG = 2         # a mature column: y <= t - 2 (PYD_EXCLUDED_RECENT_UW_YEARS)
OVERRIDE_FROM = re.compile(r"OVERRIDE from (\S+) triangle")
CLASS_TESTS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")

sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def number(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def filled(v):
    """A cell is filled when it holds a number other than an exact zero (a zero is a dash either way)."""
    x = number(v)
    return x is not None and x != 0.0


def same_figure(a, b):
    """test_gemini._same_figure: one printed figure, rounding of the last digit aside."""
    return abs(a - b) <= max(5e-4, 1e-5 * max(abs(a), abs(b)))


def as_year(y):
    try:
        f = float(y)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else None


# --- the shape tests --------------------------------------------------------------------------------------------------

def shape_tests(grid, t, raw_m, recompute=None):
    """The fifteenth amendment's tests on one grid. Returns (class, reasons, detail).

    `recompute(grid, t, raw_m)` returns the figure the grid gives at the scale that reproduces raw_m (S7); the default
    is the fourteenth amendment's recompute and grid_scale."""
    if not grid:
        return "not checkable", ["no stored grid"], {}
    labels = list(grid.get("underwriting_years") or [])
    rows = [list(r) if isinstance(r, list) else [] for r in (grid.get("development_rows") or [])]
    years = [as_year(y) for y in labels]
    if not labels or all(y is None for y in years):
        return "not checkable", ["the grid has no integer labels"], {"labels": labels}
    while rows and not any(filled(v) for v in rows[-1]):
        rows.pop()
    n_rows = len(rows)
    detail = {"labels": labels, "n_rows": n_rows}
    if n_rows < 2:
        return "not checkable", ["the grid has fewer than two development rows"], detail
    n_cols = len(labels)
    cells = [[rows[r][c] if c < len(rows[r]) else None for r in range(n_rows)] for c in range(n_cols)]
    fill = [[r for r, v in enumerate(col) if filled(v)] for col in cells]
    pr = grid.get("current_estimate_row")
    printed = [number(v) for v in pr] if isinstance(pr, list) and len(pr) == n_cols else None

    cols = []
    for c, y in enumerate(years):
        if y is None or y > t or not fill[c]:
            continue
        e, last = t - y, fill[c][-1]
        if e >= n_rows:
            status = "untested (diagonal row %d beyond the grid's %d rows)" % (e, n_rows)
        elif last == e:
            status = "on"
        elif last == e - 1:
            status = "one short"
        elif last < e:
            status = "short"
        else:
            status = "beyond"
        cols.append({"uw": y, "col": c, "diag_row": e, "last_row": last, "n_filled": len(fill[c]), "status": status,
                     "printed": None if printed is None else printed[c]})
    tested = [k for k in cols if not k["status"].startswith("untested")]
    detail["columns"] = cols
    tests = {}

    # S1 labels
    bad = [l for l, y in zip(labels, years) if y is None]
    dups = sorted(y for y, n in Counter(y for y in years if y is not None).items() if n > 1)
    late = [y for c, y in enumerate(years) if y is not None and y > t and fill[c]]
    tests["S1"] = {"pass": not (bad or dups or late),
                   "detail": "; ".join(x for x in (
                       bad and "labels that are not years: %s" % bad,
                       dups and "duplicated labels: %s" % dups,
                       late and "labels later than t=%d holding cells: %s" % (t, late)) if x) or "ok"}
    # S2 unlabelled values
    extra = sorted({c for r in rows for c in range(n_cols, len(r)) if filled(r[c])})
    tests["S2"] = {"pass": not extra, "detail": ("filled cells in unlabelled positions %s" % extra) if extra else "ok"}
    # S3 label gaps
    ys = sorted({y for y in years if y is not None})
    gaps = [(a, b) for a, b in zip(ys, ys[1:]) if b - a > 1]
    tests["S3"] = {"pass": not gaps, "detail": ("skipped years between %s" % gaps) if gaps else "ok"}
    # S4 a shifted staircase
    n_on = sum(1 for k in tested if k["status"] == "on")
    n_short1 = sum(1 for k in tested if k["status"] == "one short")
    n_beyond = sum(1 for k in tested if k["status"] == "beyond")
    up, down = n_short1 > n_on, n_beyond > n_on
    tests["S4"] = {"pass": not (up or down),
                   "detail": "tested columns: %d on the diagonal, %d one short, %d beyond, %d short by more%s"
                             % (n_on, n_short1, n_beyond, len(tested) - n_on - n_short1 - n_beyond,
                                "; the grid reads one row up (labels one year early, or a lost first row)" if up else
                                "; the grid reads one row down (labels one year late)" if down else "")}
    # S5 the 4444/2022 signature
    col_of = {y: c for c, y in enumerate(years) if y is not None}
    sig = (t in col_of and not fill[col_of[t]] and (t - 1) in col_of and len(fill[col_of[t - 1]]) == 1)
    tests["S5"] = {"pass": not sig,
                   "detail": ("the year-%d column is empty and the year-%d column holds one cell" % (t, t - 1))
                   if sig else "ok"}
    # S6 a mature column off its diagonal
    off = []
    for k in tested:
        if k["uw"] > t - MATURE_LAG or k["status"] == "on":
            continue
        p, col = k["printed"], cells[k["col"]]
        if k["status"] == "beyond" and p is not None and number(col[k["diag_row"]]) is not None \
                and same_figure(number(col[k["diag_row"]]), p):
            continue
        if k["status"] == "one short" and p is not None and not same_figure(number(col[k["last_row"]]), p):
            continue
        off.append("%d: last row %d, diagonal row %d (%s)" % (k["uw"], k["last_row"], k["diag_row"], k["status"]))
    tests["S6"] = {"pass": not off, "detail": "; ".join(off) if off else "ok"}
    # S7 reproduction
    rec = (recompute or default_recompute)(grid, t, raw_m)
    tol = None if raw_m is None else max(0.5, 0.05 * abs(raw_m))
    ok = rec is not None and raw_m is not None and abs(rec - raw_m) <= tol
    tests["S7"] = {"pass": ok, "recomputed_m": rec, "raw_m": raw_m,
                   "detail": "ok" if ok else ("the grid gives %s where the raw figure is %s" % (rec, raw_m))}
    detail["tests"] = tests
    if not tested:
        return "not checkable", ["no tested column (no filled column whose diagonal lies inside the grid)"], detail
    failed = [s for s in CLASS_TESTS if not tests[s]["pass"]]
    if failed:
        return "shape-fail", ["%s: %s" % (s, tests[s]["detail"]) for s in failed], detail
    return "pass", [], detail


def default_recompute(grid, t, raw_m):
    import scan_triangle_tables as st
    scale, _how = st.grid_scale(grid, t, raw_m)
    return st.recompute(grid, t, scale) if scale else None


# --- the population and the grid tested -------------------------------------------------------------------------------

def tested_grid(data, ck, raw_route):
    """The raw stored grid (fifteenth amendment, "The grid tested")."""
    import scan_triangle_tables as st
    models = data.get("models") or {}
    src = (raw_route or {}).get("source")
    if src == "code_triangle":
        m = OVERRIDE_FROM.search((raw_route or {}).get("note") or "")
        k = m.group(1) if m and m.group(1) in models and models[m.group(1)].get("_claims_triangle") else ck
        g = models[k].get("_claims_triangle")
        if g:
            return g, "_claims_triangle", k
    if src == "rag_triangle":
        if models[ck].get("_rag_triangle"):
            return models[ck]["_rag_triangle"], "_rag_triangle", ck
        for k in sorted(models):
            if models[k].get("_rag_triangle"):
                return models[k]["_rag_triangle"], "_rag_triangle", k
        return models[ck].get("_claims_triangle"), "_claims_triangle", ck
    g, field = st.used_grid(data, ck, "confirmed_figure")
    mk = ck
    m = re.search(r"\(model (.+)\)", field)
    if m:
        mk = m.group(1)
    return g, field.split(" ")[0], mk


def population():
    import draw_error_rate_fourth as d4
    loader = d4.Loader()
    raw = d4.Loader()
    raw.confirmed, raw.openings, raw.base = {}, {}, {}
    W = d4.working_sample()
    overruled = d4.ser.overruled_stems()
    pop, outside = [], Counter()
    for s in W:
        b, rb = loader.brief(s), raw.brief(s)
        a_src = d4.figure_source(b, overruled)
        r_src = d4.figure_source(rb, overruled)
        if a_src[0] == "triangle" or r_src[0] == "triangle":
            pop.append((s, b, rb, a_src, r_src))
        else:
            outside[a_src[1]] += 1
    return W, pop, loader, outside


def census_rows():
    out = {}
    for name, p in (("final", CENSUS), ("det", CENSUS_DET)):
        if p.exists():
            for r in load(p)["records"]:
                out.setdefault(r["stem"], {})[name] = r
    return out


def r1(cen):
    det, fin = (cen or {}).get("det") or {}, (cen or {}).get("final") or {}
    dlp, co_g = det.get("d_less_paid"), fin.get("co_g")
    if dlp is None or co_g is None:
        return {"checked": False, "why": "no D less paid in the census's deterministic run" if dlp is None
                else "no CO_g placed by the census"}
    return {"checked": True, "d_less_paid_m": dlp, "co_g_m": co_g,
            "agrees": abs(dlp - co_g) <= RECON_TOL * abs(co_g)}


def scan_record(stem, b, rb, a_src, r_src, confirmed, cen):
    import draw_error_rate_fourth as d4
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = d4.canonical(data)
    raw_route = (data["models"][ck].get("_pyd_route") or {})
    grid, field, gm = tested_grid(data, ck, raw_route)
    t = int(stem.split("_")[2])
    key = stem.replace("syndicate_", "")
    raw_m = rb.get(d4.ADOPTED)
    cls, reasons, detail = shape_tests(grid, t, raw_m)
    reg = confirmed.get(key)
    row = {"stem": stem, "report_year": t, "canonical_model": ck,
           "raw_route": raw_route.get("source"), "raw_source": r_src[0], "raw_m": raw_m,
           "adopted_route": (b.get("route") or {}).get("source"), "adopted_source": a_src[0],
           "adopted_m": b.get(d4.ADOPTED), "report_currency": b.get("report_currency"),
           "registered": reg is not None,
           "register_entry": None if reg is None else {k: reg.get(k) for k in ("figure_m", "figure_kind", "basis",
                                                                              "pages")},
           "grid_field": field, "grid_model": gm,
           "grid_page": None if not grid else (grid.get("source_page") or grid.get("page")),
           "grid_type": None if not grid else grid.get("type"), "grid_units": None if not grid else grid.get("units"),
           "class": cls, "reasons": reasons, "detail": detail,
           "r1_latest_diagonal": r1(cen),
           "census_class": ((cen or {}).get("final") or {}).get("class"),
           "reading_status": ((cen or {}).get("final") or {}).get("reading_status")}
    row["shape_fail_status"] = (None if cls != "shape-fail" else
                                "already registered" if reg is not None else "open")
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    if os.environ.get("LLOYDS_EXTRACTION_OFFLINE") != "1":
        raise SystemExit("set LLOYDS_EXTRACTION_OFFLINE=1")
    W, pop, loader, outside = population()
    cens = census_rows()
    todo = [p for p in pop if not a.stems or p[0] in a.stems]
    rows = []
    for s, b, rb, a_src, r_src in todo:
        r = scan_record(s, b, rb, a_src, r_src, loader.confirmed, cens.get(s))
        rows.append(r)
        if a.print:
            print("%-22s %-13s %-18s raw %s adopted %s | %s" % (s, r["class"], r["shape_fail_status"] or "",
                                                               r["raw_m"], r["adopted_m"], " | ".join(r["reasons"])))
    if a.stems:
        return rows
    fails = [r for r in rows if r["class"] == "shape-fail"]
    out = {
        "protocol": "protocol/error-rate-protocol-shape-check.md (the fifteenth amendment)",
        "computed": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "analysis_commit": subprocess.run(["git", "-C", str(AN), "rev-parse", "HEAD"], capture_output=True,
                                          text=True).stdout.strip(),
        "extraction_commit": subprocess.run(["git", "-C", str(EXTRACTION), "rev-parse", "HEAD"],
                                            capture_output=True, text=True).stdout.strip(),
        "working_sample": len(W),
        "population": {"n": len(pop),
                       "by_raw_and_adopted": dict(sorted(Counter(
                           "raw %s (%s), adopted %s" % (p[4][0], (p[2]["route"] or {}).get("source"), p[3][0])
                           for p in pop).items()))},
        "outside_population": dict(sorted(outside.items())),
        "counts": dict(sorted(Counter(r["class"] for r in rows).items())),
        "shape_fail_by_status": dict(sorted(Counter(r["shape_fail_status"] for r in fails).items())),
        "shape_fail_by_test": {s: sum(1 for r in fails if not r["detail"]["tests"][s]["pass"]) for s in CLASS_TESTS},
        "not_checkable_reasons": dict(Counter(r["reasons"][0] for r in rows if r["class"] == "not checkable")),
        "r1_latest_diagonal": dict(Counter("agrees" if x["checked"] and x["agrees"] else "disagrees" if x["checked"]
                                           else "not checked" for x in (r["r1_latest_diagonal"] for r in rows))),
        "shape_fails": [{"stem": r["stem"], "status": r["shape_fail_status"], "failed": [x.split(":")[0]
                                                                                        for x in r["reasons"]]}
                        for r in fails],
        "records": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    io.open(str(OUT), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("population %d: %s; shape-fails %s -> %s" % (len(rows), out["counts"], out["shape_fail_by_status"],
                                                       OUT.relative_to(AN)))
    return rows


if __name__ == "__main__":
    main()
