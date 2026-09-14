r"""Every committed Azure table in the corpus: where does an aggregated older cohort still stay out of the adopted figure?

R209 fixed the grid parser. Other paths make the same claim, that an aggregated cohort carries no
development and is excluded: the extraction prompt's `_claims_triangle`, the LLM-vision page-triangle
prompt, the adjudicator's prompt, the Adobe xlsx parser, and the documentation. This measures what that
leaves in the adopted figures, offline, from the committed table caches. For every record and every
cached table it records:

  cohort tables       the table parses (R209) with an aggregated cohort carrying development. The
                      adopted figure is compared with the table's figure with the cohort (R209) and
                      without it (the parser before R209): "with", "without" or "neither".
  labels not inserted a header names a cohort (R209's pattern) but no cohort column entered the
                      triangle; the column's numeric cells are counted (a column with two or more
                      is listed for reading).
  unrecognised labels a table that parses as a triangle, whose header (columns after the first) holds
                      "prior", "earlier", "before", "older", "pre" or "YYYY ae", but R209's pattern
                      names no cohort.
  cohort rows         a row label (first column) naming a cohort, with two or more numeric cells: an
                      aggregated cohort printed as a row (a transposed layout, or a summary row).
Working-sample membership is from the analysis repo's current exposure_results.json. A stored triangle
without `cell_binding` did not come from the table parser (the LLM-vision reader, for one).
Read-only.

    python scan_cohort_manifestations.py
"""
import copy
import glob
import io
import json
import os
import re
import sys
import types
from collections import Counter
from pathlib import Path

EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
OUT = SCR / "cohort-manifestations.json"
sys.path.insert(0, str(EX))
os.chdir(str(EX))
os.environ["LLOYDS_EXTRACTION_OFFLINE"] = "1"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import table_extraction as te  # noqa: E402
import test_gemini as tg  # noqa: E402

RECORD = re.compile(r"^syndicate_(\d+)_(\d{4})$")
HINT = re.compile(r"(?i)\b(?:prior|earlier|before|older|pre)\b|\b(?:19|20)\d\d\s*ae\b")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def canonical(data):
    models = data.get("models") or {}
    keys = sorted(models)
    if not keys:
        return None
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    if not cands:
        return None
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]


def pre_r209_parser():
    src = io.open(str(SCR / "fix_r209_aggregated_cohort.py"), encoding="utf-8").read()
    ns = {"__name__": "r209_patch_constants"}
    exec(compile(src[:src.index("\nstage = sys.argv")], "fix_r209_aggregated_cohort.py", "exec"), ns)
    path = EX / "table_extraction.py"
    t = io.open(str(path), encoding="utf-8", newline="").read().replace("\r\n", "\n")
    # R209's correction (fix_r209_depth.py) sits inside R209's own hunk, so it comes out first
    depth = io.open(str(SCR / "fix_r209_depth.py"), encoding="utf-8").read()
    dns = {"__name__": "r209_depth_constants"}
    exec(compile(depth[:depth.index("\nstage = sys.argv")], "fix_r209_depth.py", "exec"), dns)
    if t.count(dns["CODE_NEW"]) == 1:
        t = t.replace(dns["CODE_NEW"], dns["CODE_OLD"])
    swaps = [(ns["HELPERS"] + ns["ANCHOR_FN"], ns["ANCHOR_FN"])]
    swaps += [(ns[k + "_NEW"], ns[k + "_OLD"]) for k in ("LOOP", "SORT", "STRIP", "TRI", "FIELD", "DICT")]
    for new, old in swaps:
        if t.count(new) != 1:
            raise SystemExit("an R209 hunk is not in table_extraction.py exactly once (%d)" % t.count(new))
        t = t.replace(new, old)
    mod = types.ModuleType("table_extraction_pre_r209")
    mod.__file__ = str(path)
    sys.modules[mod.__name__] = mod
    exec(compile(t, "table_extraction_pre_r209", "exec"), mod.__dict__)
    return mod


def tables_of(raw):
    """A cache is an object holding "tables", or (an older layout) a list of tables or of objects holding them."""
    if isinstance(raw, dict):
        return raw.get("tables") or []
    out = []
    for e in raw or []:
        if isinstance(e, dict) and e.get("grid"):
            out.append(e)
        elif isinstance(e, dict) and isinstance(e.get("tables"), list):
            out.extend(e["tables"])
    return out


def parse(module, grid, year):
    try:
        res = module._parse_nutrient_triangle(copy.deepcopy(grid), year)
    except Exception:
        return None
    tri = res[0] if isinstance(res, tuple) else res
    return tri.to_dict() if isinstance(tri, module.TriangleData) else None


def estimator(tri, year):
    if not tri or not tri.get("underwriting_years"):
        return None
    try:
        value, _details = tg.compute_pyd_from_triangle(copy.deepcopy(tri), year)
        return value
    except Exception:
        return None


def close(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) <= 0.001


def numeric(cell):
    try:
        v = te._clean_cell_triangle(cell)
    except Exception:
        return None
    return v if isinstance(v, (int, float)) else None


def population():
    d = load(AN / "model" / "exposure_results.json")
    return {"syndicate_%s_%s" % (o["syndicate"], o["year"]) for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}


old = pre_r209_parser()
sample = population()
cohort_tables, not_inserted, unrecognised, cohort_rows = [], [], [], []
no_cache, list_caches = 0, 0
stored_without_binding = []
records = sorted(os.path.basename(p)[:-5] for p in glob.glob(str(EX / "pdf_extraction" / "syndicate_*.json"))
                 if RECORD.match(os.path.basename(p)[:-5]))
for stem in records:
    year = int(RECORD.match(stem).group(2))
    a = load(EX / "pdf_extraction" / (stem + ".json"))
    ck = canonical(a)
    m = ((a.get("models") or {}).get(ck) or {}) if ck else {}
    adopted = m.get("prior_year_development_gbp_m")
    route = (m.get("_pyd_route") or {}).get("source")
    stored = m.get("_rag_triangle") or {}
    base = {"stem": stem, "in_sample": stem in sample, "adopted": adopted, "route": route,
            "stored_type": stored.get("type"), "stored_binding": stored.get("cell_binding"),
            "stored_page": stored.get("source_page") or stored.get("page")}
    if stored and not stored.get("cell_binding"):
        stored_without_binding.append(dict(base, stored_gives=estimator(stored, year),
                                           stored_years=stored.get("underwriting_years")))
    cache = EX / "pdf_extraction" / "azure_output" / ("%s_azure.json" % stem)
    if not cache.exists():
        no_cache += 1
        continue
    raw = load(cache)
    list_caches += isinstance(raw, list)
    for i, t in enumerate(tables_of(raw)):
        grid = t.get("grid") if isinstance(t, dict) else None
        if not grid or len(grid) < 4:
            continue
        ncol = max((len(r) for r in grid[:3]), default=0)
        cohorts, labels = te._aggregated_cohort_columns(grid)
        new_tri = parse(te, grid, year)
        if new_tri and new_tri.get("aggregated_cohort"):
            with_c = estimator(new_tri, year)
            without_c = estimator(parse(old, grid, year), year)
            match = "with" if close(adopted, with_c) else "without" if close(adopted, without_c) else "neither"
            cohort_tables.append(dict(base, table=i, page=t.get("orig_page"), cohort=new_tri["aggregated_cohort"],
                                      with_cohort=with_c, without_cohort=without_c, adopted_matches=match))
        elif new_tri and cohorts:
            oldest = min(int(y) for y in new_tri["underwriting_years"])
            for col, anchor in cohorts:
                nums = [numeric(grid[r][col]) for r in range(3, len(grid)) if col < len(grid[r])]
                nums = [v for v in nums if v not in (None, 0)]
                if len(nums) >= 2:
                    not_inserted.append(dict(base, table=i, page=t.get("orig_page"), column=col, anchor=anchor,
                                             oldest_single_year=oldest, nonzero_numeric_cells=len(nums),
                                             label=" ".join(te._header_cells(grid, col))[:80]))
        elif new_tri:
            text = " | ".join(" ".join(te._header_cells(grid, c)) for c in range(1, ncol))
            if HINT.search(text):
                unrecognised.append(dict(base, table=i, page=t.get("orig_page"), header=text[:260]))
        for r in range(1, len(grid)):
            label = str(grid[r][0]).strip() if grid[r] else ""
            if te._COHORT_HEADER.search(label) or re.search(r"(?i)\b(?:19|20)\d\d\s*ae\b", label):
                nums = [numeric(c) for c in grid[r][1:]]
                nums = [v for v in nums if v not in (None, 0)]
                if len(nums) >= 2:
                    cohort_rows.append(dict(base, table=i, page=t.get("orig_page"), row=r, label=label[:60],
                                            nonzero_numeric_cells=len(nums), parses_as_triangle=bool(new_tri)))

json.dump({"records": len(records), "without_table_cache": no_cache, "list_form_caches": list_caches,
           "cohort_tables": cohort_tables, "cohort_labels_not_inserted": not_inserted,
           "unrecognised_labels": unrecognised, "cohort_rows": cohort_rows,
           "stored_triangles_not_from_the_table_parser": stored_without_binding},
          io.open(str(OUT), "w", encoding="utf-8"), indent=1)

print("records %d; without a committed table cache %d; list-form caches %d" % (len(records), no_cache, list_caches))
print("tables parsing with an aggregated cohort (R209): %d, in %d records; adopted figure matches: %s"
      % (len(cohort_tables), len({r["stem"] for r in cohort_tables}), dict(Counter(r["adopted_matches"] for r in cohort_tables))))
for r in cohort_tables:
    if r["adopted_matches"] != "with":
        print("  %-22s t%-3s p%-4s sample %-5s adopted %-9s with %-9s without %-9s route %-15s stored %s/%s p%s  %s"
              % (r["stem"], r["table"], r["page"], r["in_sample"], r["adopted"], r["with_cohort"], r["without_cohort"],
                 r["route"], r["stored_type"], r["stored_binding"], r["stored_page"], r["cohort"].get("label")))
print("cohort labels whose column was not inserted but holds 2+ non-zero numbers: %d" % len(not_inserted))
for r in not_inserted:
    print("  %-22s t%-3s p%-4s sample %-5s col %s anchor %s oldest single %s cells %s label %r route %s"
          % (r["stem"], r["table"], r["page"], r["in_sample"], r["column"], r["anchor"], r["oldest_single_year"],
             r["nonzero_numeric_cells"], r["label"], r["route"]))
print("triangle tables with a cohort-like header word R209 does not read: %d" % len(unrecognised))
for r in unrecognised:
    print("  %-22s t%-3s p%-4s sample %-5s %s" % (r["stem"], r["table"], r["page"], r["in_sample"], r["header"][:200]))
print("rows labelled as a cohort with 2+ non-zero numbers: %d (in tables that parse as a triangle: %d)"
      % (len(cohort_rows), sum(1 for r in cohort_rows if r["parses_as_triangle"])))
for r in cohort_rows[:80]:
    print("  %-22s t%-3s p%-4s sample %-5s row %-3s cells %-3s triangle %-5s %r"
          % (r["stem"], r["table"], r["page"], r["in_sample"], r["row"], r["nonzero_numeric_cells"],
             r["parses_as_triangle"], r["label"]))
print("stored triangles not from the table parser (no cell_binding): %d; in the working sample: %d"
      % (len(stored_without_binding), sum(1 for r in stored_without_binding if r["in_sample"])))
for r in stored_without_binding:
    print("  %-22s sample %-5s adopted %-9s stored gives %-9s route %-15s years %s"
          % (r["stem"], r["in_sample"], r["adopted"], r["stored_gives"], r["route"], r["stored_years"]))
print("written: %s" % OUT.name)
