"""Build data/mature_cohort_figures.json: the mature-cohort figures of the primary outcome (the owner's decision,
22 October 2026, option c).

The paper's outcome (Equation 1) is the gross prior-year movement over the underwriting years u <= t-2. The extraction
applies two precedence rules that replaced a printed gross triangle's mature-cohort figure with a broader one only
because the two had opposite signs: the provisions sign-disagreement override (route rag_provisions) and the
model-agreement veto (a "[RAG PYD NOT APPLIED: ...]" note, the models' reading kept). The owner decided that a valid
mature-cohort triangle figure is never replaced merely because a broader movement has the other sign. The register
holds one entry per record of the corpus whose gross RAG triangle such a rule displaced (DISPLACED, the corpus rule
the completeness test reads): the triangle's figure where readings of the filing confirm it as a valid mature-cohort
figure, or no figure and the reason. run_analysis.py (apply_mature_cohort_figure) adopts the figures under the
primary outcome; the 672-record construction (outcome "precedence_672") ignores the register.

Each figure is recomputed here from the record's stored grid (models.<model>._rag_triangle) by the extraction's own
estimator, test_gemini.compute_pyd_from_triangle and its helpers, read from the extraction checkout
(LLOYDS_EXTRACTION_REPO) at the commit this analysis pins (record_tests.extraction_pin), parsed and never imported
(its import loads .env and the API clients), so the analysis does not carry a copy of the estimator. The rest of each
entry is assembled from committed evidence:

  - results/extraction_error_rate/mature-cohort/readings/<reader>.json, the readings of 22 October 2026 (A1-A4, B1);
  - results/extraction_error_rate/mature-cohort/decisions.csv, the adjudication's decision per record
    (adjudication.md beside it);
  - results/extraction_error_rate/mature-cohort/design_per_record.csv, the design study's deterministic
    reconciliation census and route;
  - the extraction error-rate study's earlier readings that recomputed the same printed triangle
    (results/extraction_error_rate/);
  - NO_FIGURE below, the records the register keeps without a figure, with the reason.

Usage:
  python src/build_mature_cohort_figures.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_mature_cohort_figures.py --write    # rebuild and write the register
"""
import ast
import csv
import glob
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))

REGISTER = HERE / "data" / "mature_cohort_figures.json"
EVIDENCE = HERE / "results" / "extraction_error_rate" / "mature-cohort"
READERS = ("A1", "A2", "A3", "A4", "B1")
READING_ROUND = "mature-cohort readings of 22 October 2026"
STUDY = HERE / "results" / "extraction_error_rate"
RECORDS = HERE / "pdf_extraction"

EXTRACTION_ENV = "LLOYDS_EXTRACTION_REPO"
EXTRACTION_DEFAULT = os.path.join("D:" + os.sep, "dev", "lloyds_reserve_stress_testing")
#: the definitions of test_gemini.py the estimator needs, read by name from its syntax tree
ESTIMATOR_NAMES = ("_as_number", "MIN_STEP_RATIO", "_same_figure", "_thousandfold", "_printed_current_estimates",
                   "_diagonal_cells", "_null_zeros_beyond_the_staircase", "_staircase_limit",
                   "_validate_triangle_structure", "_single_cohort_staircase", "MIN_TRIANGLE_STRUCTURE_SCORE",
                   "compute_pyd_from_triangle")
#: the two constants compute_pyd_from_triangle reads from table_extraction.py, checked against that file at the pin
TABLE_CONSTANTS = {"MAX_UW_YEAR_LAG": 5, "PYD_EXCLUDED_RECENT_UW_YEARS": 2}

#: the corpus rule: a block displaced a gross triangle when its stored RAG triangle is gross and its figure is the
#: provisions note's after the sign-disagreement override, or a veto note records a deterministic figure not applied
VETO_NOTE = re.compile(r"\[(?:RAG|CODE) PYD NOT APPLIED")
RAG_VETO = re.compile(r"\[RAG PYD NOT APPLIED: deterministic figure ([+-]?\d+(?:\.\d+)?)m "
                      r"(has the opposite sign|is \d+% of opening)")
FIGURE_TOL = 0.0015

#: the records the register keeps without a figure, each with its reason (decisions of the Claude analysis session,
#: 22 October 2026, under the rules the analysis already applies; design.md section 3 and adjudication.md)
NO_FIGURE = {
    # a figure two readings confirmed stands in data/pyd_confirmed_figures.json, which decides the record
    **{k: ("confirmed_figure_register",
           "data/pyd_confirmed_figures.json holds this record's figure, confirmed by two readings of the filing; that "
           "register decides it, under either outcome")
       for k in ("1991_2018", "2010_2018", "3010_2018", "3010_2019", "3010_2022", "3500_2018", "6112_2016")},
    # the stored triangle holds no underwriting year up to t-2
    **{k: ("no_mature_cohort",
           "the stored gross triangle holds no underwriting year up to t-2, so it has no mature-cohort figure "
           "(the estimator computes none)")
       for k in ("1947_2019", "2014_2015", "6125_2017")},
    # a deterministic triangle figure is the adopted block's route already: nothing displaced it there
    "2007_2015": ("triangle_figure_stands",
                  "the adopted block's figure is the code triangle's (-2.0m, the models' triangles without the '2010 & "
                  "prior' column); the RAG figure +148.8m rests on that column, whose last two diagonals two readings "
                  "of the error-rate study found not like for like (design.md section 3)"),
    "2014_2017": ("triangle_figure_stands",
                  "the adopted block's figure is the code triangle's (+4.024m); the vetoed RAG figure (-1.2m) is not "
                  "the stored gross triangle's"),
    # outside the working sample under either outcome for a reason that is not the figure; not read
    **{k: ("outside_working_sample_not_read",
           "outside the working sample under either outcome for a reason that is not its figure (%s), so the "
           "triangle was not read and its figure is not adopted" % why)
       for k, why in (("1206_2019", "in run-off"), ("1209_2016", "in run-off"),
                      ("3002_2017", "no usable line-of-business weights"),
                      ("3002_2019", "no usable line-of-business weights"),
                      ("3002_2020", "no usable line-of-business weights"),
                      ("3002_2024", "no usable line-of-business weights"),
                      ("6104_2016", "no usable line-of-business weights"),
                      ("6117_2018", "no usable line-of-business weights"),
                      ("6117_2024", "no usable line-of-business weights"),
                      ("779_2015", "no usable line-of-business weights"),
                      ("779_2016", "no premium mix: incomplete"), ("6134_2024", "no premium mix: incomplete"))},
    # the readings' own finding, under Appendix 2.1's rule for an aggregated column (adjudication.md, Q2)
    "6134_2023": ("aggregated_column_not_like_for_like",
                  "the 2021 column, the only one up to t-2, absorbs the 2019 and 2020 years of account at its latest "
                  "cell only (reinsured to close into Syndicate 2121 and reassumed under the 2021 quota share, p43): "
                  "its last step is not the report year's movement, so Appendix 2.1 leaves the column out and no "
                  "mature column remains; both readings also read the step as a take-on dominating it"),
}

#: the figure entries that leave the primary through data/takeon_not_development.json (their entries there carry
#: figure_route "mature_cohort_triangle"): the take-on, or the outward transfer, dominates the triangle's step
TAKEON_EXCLUDED = ("1084_2022", "1861_2020", "2001_2022")

OWNER = ("owner's decision, 22 October 2026 (option c): the primary outcome is the mature-cohort movement of "
         "Equation (1), and a valid mature-cohort triangle figure is never replaced merely because a broader movement "
         "has the other sign")


# --------------------------------------------------------------------------------------------- the estimator
def extraction_root():
    return os.environ.get(EXTRACTION_ENV) or EXTRACTION_DEFAULT


def extraction_blob(path, root=None, pin=None):
    """`path` at the pinned commit of the extraction checkout, as text (LF)."""
    import record_tests
    root = root or extraction_root()
    pin = pin or record_tests.extraction_pin()
    r = subprocess.run(["git", "-C", root, "cat-file", "blob", "%s:%s" % (pin, path)], capture_output=True)
    if r.returncode != 0:
        raise SystemExit("the extraction checkout %s does not hold %s at the pinned commit %s (%s): set %s"
                         % (root, path, pin, r.stderr.decode("utf-8", "replace").strip(), EXTRACTION_ENV))
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


def estimator(root=None, pin=None, source=None, table_source=None):
    """compute_pyd_from_triangle and its helpers, exec'd from the pinned test_gemini.py's syntax tree (the named
    definitions only), with table_extraction.py's two constants checked against that file at the pin."""
    source = source if source is not None else extraction_blob("test_gemini.py", root, pin)
    table_source = table_source if table_source is not None else extraction_blob("table_extraction.py", root, pin)
    for name, value in TABLE_CONSTANTS.items():
        if "\n%s = %r\n" % (name, value) not in table_source:
            raise SystemExit("table_extraction.py at the pin does not set %s = %r" % (name, value))
    keep, found = [], set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in ESTIMATOR_NAMES:
            keep.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ESTIMATOR_NAMES
                                                  for t in node.targets):
            keep.append(node)
            found.update(t.id for t in node.targets if isinstance(t, ast.Name))
    missing = set(ESTIMATOR_NAMES) - found
    if missing:
        raise SystemExit("test_gemini.py at the pin lacks %s" % sorted(missing))
    ns = dict(TABLE_CONSTANTS)
    exec(compile(ast.Module(body=keep, type_ignores=[]), "test_gemini.py@pin", "exec"), ns)
    return ns["compute_pyd_from_triangle"]


def compute(fn, tri, year):
    import copy
    return fn(copy.deepcopy(tri), int(year))


# --------------------------------------------------------------------------------------------- the corpus rule
def displaced_by(block):
    """The precedence rules that displaced the block's gross RAG triangle ("sign_override", "veto"), or ()."""
    tri = block.get("_rag_triangle")
    if not (isinstance(tri, dict) and tri.get("underwriting_years") and tri.get("type") == "gross"):
        return ()
    why = []
    if str((block.get("_pyd_route") or {}).get("source") or "").startswith("rag_provisions"):
        why.append("sign_override")
    if VETO_NOTE.search(block.get("data_quality_notes") or ""):
        why.append("veto")
    return tuple(why)


def population(records_dir=RECORDS):
    """{key: {model: rules}} for every record of the corpus with a block whose gross triangle a rule displaced."""
    out = {}
    for path in sorted(glob.glob(str(Path(records_dir) / "syndicate_*.json"))):
        key = os.path.basename(path)[len("syndicate_"):-len(".json")]
        with io.open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for mk, block in sorted((data.get("models") or {}).items()):
            if isinstance(block, dict) and displaced_by(block):
                out.setdefault(key, {})[mk] = list(displaced_by(block))
    return out


def canonical_key(data):
    """The adopted model, by load_and_classify's model resolution."""
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


# --------------------------------------------------------------------------------------------- evidence
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pages(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return [int(p) for p in (v or []) if isinstance(p, (int, float)) and not isinstance(p, bool) and int(p) >= 1]


def load_readings():
    out = {}
    for rid in READERS:
        with io.open(EVIDENCE / "readings" / ("%s.json" % rid), encoding="utf-8") as fh:
            for key, r in json.load(fh).items():
                out.setdefault(key, []).append((rid, r))
    return out


def round_reading(rid, r):
    stated = r.get("stated_prior_year_line") or {}
    return {"kind": "reading", "reader": rid, "round": READING_ROUND,
            "source": "results/extraction_error_rate/mature-cohort/readings/%s.json" % rid,
            "pages": _pages(r.get("pages")), "read_by": r.get("read_by"),
            "table": r.get("table"), "verdict": r.get("verdict"),
            "figure_m": _num(r.get("recomputed_mature_figure_m")), "cells": r.get("cells"),
            "x_and_prior": r.get("x_and_prior"), "reconciliation": r.get("reconciliation"),
            "transaction": r.get("transaction"),
            "stated_prior_year_line": {k: stated.get(k) for k in ("value_m", "page", "quote", "stated_less_triangle_m")
                                       if k in stated} or None}


def _walk_study(obj, path, keys, out):
    if isinstance(obj, dict):
        stem = obj.get("stem")
        if isinstance(stem, str) and stem.startswith("syndicate_") and "triangle_recomputation_m" in obj:
            key = stem[len("syndicate_"):]
            if key in keys:
                out.setdefault(key, []).append((path, obj))
        for v in obj.values():
            _walk_study(v, path, keys, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_study(v, path, keys, out)


def study_readings(keys):
    """The error-rate study's earlier readings that recomputed a record's printed triangle (merged files only: a
    batch file repeats its merged file's entry)."""
    out = {}
    for path in sorted(glob.glob(str(STUDY / "**" / "*.json"), recursive=True)):
        base = os.path.basename(path)
        if re.search(r"-batch-\d+\.json$", base) or not any(w in base for w in ("verdict", "verification", "reading")):
            continue
        try:
            with io.open(path, encoding="utf-8") as fh:
                obj = json.load(fh)
        except ValueError:
            continue
        _walk_study(obj, Path(path).relative_to(HERE).as_posix(), set(keys), out)
    return out


def study_reading(path, row):
    who = row.get("second_reader") or row.get("first_reader")
    return {"kind": "error_rate_study", "reader": "error-rate study, %s%s" % (path, (" (%s)" % who) if who else ""),
            "source": path, "pages": _pages(row.get("triangle_pages")),
            "verdict": "printed triangle recomputed; the study's verdict on the then adopted figure: %s"
                       % row.get("verdict"),
            "figure_m": _num(row.get("triangle_recomputation_m")), "cells": row.get("triangle_arithmetic")}


def table_read(model, tri, figure, details, printed_page):
    page = tri.get("source_page")
    pages = [page] if isinstance(page, int) and page >= 1 else ([printed_page] if printed_page else [])
    lines = [ln.strip() for ln in str(details).splitlines() if ln.strip()]
    return {"kind": "extraction_table_read",
            "reader": "the extraction's table read: the stored grid models.%s._rag_triangle, recomputed by "
                      "compute_pyd_from_triangle at the pinned commit" % model,
            "source": "pdf_extraction/ (the record file)",
            "pages": pages,
            "verdict": "the grid the table backend transcribed from the printed page%s" % (
                "" if isinstance(page, int) else " (the grid records no page; the readers place the table on p%s)"
                % printed_page),
            "figure_m": figure, "cells": "; ".join(lines)}


def load_csv(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return {r["key"]: r for r in csv.DictReader(fh)}


def fx_gbp(key, figure):
    import run_analysis as ra
    currency = ra.FX_CURRENCIES.get(key, "UNDETERMINED")
    if currency != "USD" or figure is None:
        return currency, (None if figure is None else round(figure, 6))
    rate = ra.FX_RATES[int(key.rsplit("_", 1)[1])]["usd_per_gbp"]
    return currency, round(figure / rate, 6)


# --------------------------------------------------------------------------------------------- the register
def entry_for(key, data, pop_blocks, fn, decisions, design, readings, study):
    year = int(key.split("_")[1])
    ck = canonical_key(data)
    cm = data["models"][ck]
    models = sorted(pop_blocks)
    model = ck if ck in pop_blocks else models[0]
    tri = cm.get("_rag_triangle") if ck in pop_blocks else data["models"][model]["_rag_triangle"]
    figure, details = compute(fn, tri, year)
    figures = set()
    for mk in models:
        f, _d = compute(fn, data["models"][mk]["_rag_triangle"], year)
        figures.add(f)
    if len(figures) != 1:
        raise SystemExit("%s: the displaced blocks' triangles compute to different figures %s" % (key, figures))
    route = cm.get("_pyd_route") or {}
    rules = displaced_by(cm)
    by = "sign_override" if "sign_override" in rules else ("veto" if "veto" in rules else None)
    gate = None
    if by == "veto":
        m = [g for g in RAG_VETO.finditer(cm.get("data_quality_notes") or "")
             if figure is not None and abs(float(g.group(1)) - figure) <= FIGURE_TOL]
        gate = ("sign" if m[0].group(2).startswith("has") else "magnitude") if m else None
    d = design.get(key) or {}
    dec = decisions.get(key)
    printed_page = int(dec["triangle_page"]) if dec and dec.get("triangle_page", "").isdigit() else None
    years = list(tri.get("underwriting_years") or [])
    mature = [y for y in years if isinstance(y, int) and y <= year - 2]
    currency, gbp = fx_gbp(key, figure)
    entry = {
        "figure_m": None, "figure_gbp_m": None, "report_currency": currency, "figure_kind": None, "basis": "gross",
        "displaced": {"by": by, "veto_gate": gate, "route": route.get("source"),
                      "figure_m": _num(cm.get("prior_year_development_gbp_m")), "adopted_model": ck,
                      "blocks": {mk: pop_blocks[mk] for mk in models},
                      "status_under_precedence_672": d.get("current_status") or None,
                      "route_label": d.get("current_route") or None},
        "triangle": {"printed_page": printed_page, "stored_source_page": tri.get("source_page"),
                     "model": model, "type": tri.get("type"), "units": tri.get("units"),
                     "entity": tri.get("entity"), "underwriting_years": years, "mature_years": mature},
        "recomputation": {"estimator": "test_gemini.compute_pyd_from_triangle at the pinned extraction commit "
                                       "(record_tests.extraction_pin), parsed from the extraction checkout",
                          "figure_m": figure, "figure_gbp_m": gbp,
                          "refusal": None if figure is not None else str(details)},
        "reconciliation": {"census_class_deterministic": d.get("reconciliation_class_deterministic") or None,
                           "co_g_m": _num(d.get("CO_g")), "co_n_m": _num(d.get("CO_n")),
                           "table_latest_diagonal_m": _num(d.get("table_latest_diagonal")),
                           "shape_check": d.get("shape_check") or None,
                           "source": "results/extraction_error_rate/mature-cohort/design_per_record.csv "
                                     "(the census's own script on the "
                                     "stored grid), and each reading's reconciliation below"},
    }
    rr = [round_reading(rid, r) for rid, r in readings.get(key, [])]
    if key in NO_FIGURE:
        reason, why = NO_FIGURE[key]
        entry["reason"] = reason
        entry["reason_evidence"] = why
        entry["readings"] = rr
        entry["status"] = "no_figure"
        if rr:
            entry["pages"] = sorted({p for r in rr for p in r["pages"]})
            entry["quote"] = " | ".join("reader %s: %s" % (r["reader"], r["transaction"] or r["cells"]) for r in rr)
        entry["decision"] = ("decision of the Claude analysis session, 22 October 2026: no mature-cohort figure is "
                             "adopted (%s), under the %s" % (reason, OWNER))
        return entry
    if dec is None:
        raise SystemExit("%s: a displaced record with neither a decision (decisions.csv) nor a NO_FIGURE reason" % key)
    if figure is None:
        raise SystemExit("%s: decided with a figure, but the estimator computes none: %s" % (key, details))
    study_rows = [study_reading(p, row) for p, row in study.get(key, [])
                  if _num(row.get("triangle_recomputation_m")) is not None
                  and abs(_num(row.get("triangle_recomputation_m")) - figure) <= FIGURE_TOL]
    reads = rr + study_rows
    if len(reads) < 2:
        reads.append(table_read(model, tri, figure, details, printed_page))
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["readings"] = reads
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], (r.get("table") or {}).get("page"), r["cells"])
                                for r in rr)
    if key in TAKEON_EXCLUDED:
        entry["status"] = "excluded_takeon_not_development"
        rule = ("the take-on dominates the triangle's step: data/takeon_not_development.json holds the record with "
                "figure_route mature_cohort_triangle, so the loader adopts the figure and then tags the record "
                "TAKEON_NOT_DEVELOPMENT")
    else:
        entry["status"] = "primary"
        rule = "a valid mature-cohort figure: the printed gross table's own development over u <= t-2"
    agreed = dec.get("readers_agreed") or ""
    entry["decision"] = ("decision of the Claude analysis session, 22 October 2026 "
                         "(results/extraction_error_rate/mature-cohort/"
                         "decisions.csv, adjudication.md): %s; %s; under the %s%s"
                         % (dec.get("final_status"), rule, OWNER,
                            "" if agreed == "yes" else "; readers: " + agreed))
    return entry


def build():
    import run_analysis as ra  # noqa: F401  (FX tables)
    fn = estimator()
    pop = population()
    decisions = load_csv(EVIDENCE / "decisions.csv")
    design = load_csv(EVIDENCE / "design_per_record.csv")
    readings = load_readings()
    study = study_readings(pop)
    missing = sorted(set(decisions) - set(pop))
    if missing:
        raise SystemExit("decided records outside the displaced population: %s" % missing)
    reg = {"_purpose": PURPOSE}
    for key in sorted(pop, key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1]))):
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            data = json.load(fh)
        reg[key] = entry_for(key, data, pop[key], fn, decisions, design, readings, study)
    return reg


PURPOSE = (
    "Mature-cohort figures of the primary outcome (the owner's decision, 22 October 2026, option c): the gross "
    "prior-year movement over underwriting years u <= t-2 of Equation (1), for every record of the corpus whose "
    "stored gross RAG triangle a sign-only precedence rule displaced (the provisions sign-disagreement override, route "
    "rag_provisions, or the model-agreement veto, a '[RAG|CODE] PYD NOT APPLIED' note). Built by "
    "src/build_mature_cohort_figures.py, which recomputes each figure from the record's stored grid by the extraction's "
    "own estimator at the pinned commit and assembles the evidence from "
    "results/extraction_error_rate/mature-cohort/ and the error-rate "
    "study. figure_m is in millions of the report's own currency (figure_gbp_m at the loader's H.10 rate, for "
    "reference). Under ANALYSIS_CONFIG['outcome'] 'mature_cohort' (the primary) run_analysis.py "
    "(apply_mature_cohort_figure) adopts figure_m before the basis and cohort decisions and before the FX conversion, "
    "writes route 'mature_cohort_triangle' (gross, mature-enforced), and refuses an entry unless every model block of "
    "the record shows the displaced gross triangle; under 'precedence_672' the register is not applied. An entry with "
    "a figure carries at least two readings, each with its reader, pages and cells: the readings of 22 October 2026 "
    "(kind 'reading'), earlier readings of the error-rate study that recomputed the same printed triangle (kind "
    "'error_rate_study'), and, where only one reader read the record, the extraction's own table read of the printed "
    "page (kind 'extraction_table_read', the stored grid the estimator computed from). An entry without a figure "
    "states its reason (confirmed_figure_register, no_mature_cohort, triangle_figure_stands, "
    "outside_working_sample_not_read, aggregated_column_not_like_for_like), and the loader adopts nothing for it. "
    "status 'excluded_takeon_not_development' marks a figure whose record data/takeon_not_development.json excludes "
    "(an entry there with figure_route 'mature_cohort_triangle').")


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    reg = build()
    text = dumps(reg)
    if "--write" in argv:
        with io.open(REGISTER, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote %s: %d entries" % (REGISTER.relative_to(HERE), len(reg) - 1))
        return 0
    with io.open(REGISTER, encoding="utf-8", newline="") as fh:
        committed = fh.read()
    if committed != text:
        print("data/mature_cohort_figures.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/mature_cohort_figures.json equals its rebuild (%d entries)" % (len(reg) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
