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

  - results/extraction_error_rate/mature-cohort/readings/<reader>.json, the readings of 22 October 2026 (A1-A4, B1),
    and the second readings of the records that round read once (C1, C2), so that every figure entry rests on two
    independent agent readings of the filing;
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
import copy
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
READERS = ("A1", "A2", "A3", "A4", "B1", "C1", "C2")
READING_ROUND = "mature-cohort readings of 22 October 2026"
#: the second readings of the 43 figure entries the first round read once (each read by C1 or C2, who opened no other
#: reader's folder); they replace the extraction's table read as the entry's second reading
SECOND_ROUND = "mature-cohort second readings of 22 October 2026 (the records the first round read once)"
ROUNDS = {"C1": SECOND_ROUND, "C2": SECOND_ROUND}
#: the kinds of reading that are an agent's reading of the filing; the extraction's table read is not one
AGENT_READING_KINDS = ("reading", "error_rate_study")
STUDY = HERE / "results" / "extraction_error_rate"
RECORDS = HERE / "pdf_extraction"

#: Appendix 2.1 leaves an aggregated development-age column ("2014 & Prior": older underwriting years added by
#: development age) out of the mature-cohort figure, because its last two diagonal cells are not like for like by
#: calendar year. The author's decision of 22 October 2026 applies it to the two records of syndicate 1945, whose oldest
#: column is such a column (the label and anchor year of the column are the stored grid's aggregated_cohort). Two
#: independent readings (F1, F2) recompute each figure from the printed table without the column, and the
#: extraction's estimator on the stored grid without the column gives the same figure. The readings are archived with
#: the exchange-rate readings of the same brief (fx-translation/readings/F1.json, F2.json).
AGGREGATED_COLUMN = {"1945_2023": {"label": "2013&Prior", "anchor": 2013},
                     "1945_2024": {"label": "2014 & Prior", "anchor": 2014}}
#: the entries of AGGREGATED_COLUMN that no precedence rule displaced: the adopted figure is the code or RAG
#: triangle's own, with the column in it (the corpus rule, population(), does not see them)
COLUMN_ONLY = ("1945_2023",)
COLUMN_READERS = ("F1", "F2")
COLUMN_READINGS = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "fx-translation" / "readings"
COLUMN_ROUND = "aggregated-column readings of 22 October 2026 (F1, F2)"
COLUMN_RULE = (
    "Appendix 2.1 leaves an aggregated development-age column out of the mature-cohort figure, because its last two "
    "diagonal cells are not like for like by calendar year: it adds the older underwriting years age by age, so its "
    "'ten years later' cell holds the older years at age 10 and its 'nine years later' cell the older years at age 9. "
    "The author's decision of 22 October 2026 applies the rule to this record: the figure is the sum over the "
    "underwriting years up to t-2 of the latest estimate less the previous one, without that column")

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

#: flags the second readings raised that the existing rules decide, each with its rule (decisions of the Claude
#: analysis session, 22 October 2026); no figure changes
NOTES = {
    "5151_2016": (
        {"flag": "readers disagree: A4 confirmed (+18.850, 'the earlier diagonals are restated in this table, so the two "
                 "diagonals used are on the same (restated) basis'); C2 table_invalid: the cells are never retranslated "
                 "between reports (the cells before the 2015 diagonal are identical in the 2015 and 2016 reports, and "
                 "the 2017 report repeats the 2016 diagonal exactly), the functional currency is US dollars from 1 "
                 "January 2016 (p25; p20 'The Syndicate changed its functional currency to US dollars with effect from "
                 "1st January 2016'), the gross claims outstanding roll-forward prints 'Foreign exchange 35,556' on an "
                 "opening 244,293 (p33, 14.6%), and C2 estimates the translation in the step at roughly +20m to +26m, "
                 "which is not a printed figure. Both readers recompute +18.850 and reconcile the table exactly to "
                 "gross claims outstanding 304,206 (p44, p33)",
         "reader": "A4, C2",
         "rule": "no existing rule covers a triangle held at historical rates or a change of functional currency. The "
                 "validity rule (design.md section 2, points 1-4) tests the table's computation, its gross basis and "
                 "reconciliation, a transaction in the step and an aggregated column's coverage, not its exchange "
                 "basis; the paper converts R and M at the reporting-date rate and treats S as invariant to the "
                 "reporting currency, which holds for that conversion, not for translation inside the filing's own "
                 "table; and the one precedent, 3500/2018 in the error-rate study's tail stratum, took a printed gross "
                 "line that included exchange because the filing printed no figure without it. An estimate of the "
                 "translation is not a printed figure, so no rule puts one in the figure's place",
         "decision": "the figure stands under the existing rules: primary, +18.850. Whether a historical-rate triangle "
                     "or a year-t change of functional currency leaves the primary is a scope question for the author, "
                     "for every affected record. fx-translation/fx_translation.json measures the primary sample's 653 "
                     "from the stored grids: 506 tables re-presented between reports, 37 not retranslated (their "
                     "earlier diagonals equal the year t-1 report's), 110 not comparable; of the 37, 18 in a year "
                     "sterling moved 5% or more against the dollar, and of those the gross claims-outstanding "
                     "roll-forward prints an exchange movement of 5% or more of R for 3 (2468/2016, 5151/2016, "
                     "5151/2017); 13 records change functional currency in year t (a lower bound), 5151/2016 the "
                     "only one measured as not retranslated"},
        {"flag": "the 2016 report amends the 2015 diagonal ('Certain amounts in the prior period triangles have been "
                 "amended to correctly reflect the claims incurred by pure year of account', p44) on a basis it does "
                 "not state (C2): 2011 96,952 -> 117,599, 2012 67,682 -> 80,021, 2013 78,897 -> 91,276, 2014 97,599 -> "
                 "106,295, 2015 42,095 -> 43,849, every earlier cell unchanged",
         "reader": "C2 (A4 reads the same amendment as a restatement on both diagonals)",
         "rule": "the figure is the latest less the previous diagonal of the year-t report's own table (design.md "
                 "section 2, point 1; Appendix 2.1), and a prior diagonal the year-t report itself amends is that "
                 "table's previous diagonal, as a triangle restated in the year-t report is under the take-on base "
                 "rule (error-rate protocol, ninth amendment). The amendment is not a transaction (both readers find "
                 "none in 2016), the table reconciles exactly, and the stored grids show the amended cells continuing "
                 "each column's own history where the 2015 report's did not (2011: 114,839 at end-2014, 117,599 "
                 "amended end-2015, 121,341 end-2016; the 2015 report printed 96,952 after 114,839)",
         "decision": "not a table-validity failure: the figure stands"},
    ),
    "2689_2022": (
        {"flag": "a remnant after an outward RITC at the start of year t: 'Immediately following 31 December 2021, the "
                 "2019 and prior underwriting years were externally Reinsured-to-Close (RITC) to an external party, "
                 "Syndicate 1254' (p12); 'External RITC (101,597)' in the gross claims outstanding movement (p35); the "
                 "table develops the 2020 year alone up to t-2",
         "reader": "C1 (A3 reads the same transfer and finds it does not move the 2020 column)",
         "rule": "the figure is the development of the years the table develops (Appendix 2.1), and the transfer is "
                 "of years the table does not print, so it is not in the step (design.md section 2, point 4); "
                 "no_mature_cohort applies only to a table with no column up to t-2. R stays the unadjusted gross "
                 "claims outstanding at 1 January, which includes the 101.597m transferred out (the author's decision "
                 "of 29 September 2026, data/outbound_transfer_retained_base.json); the retained-base sensitivity "
                 "(src/check_outbound_transfer_sensitivity.py) replaces R by the balance retained for that register's "
                 "confirmed records, and 2689/2022 has been among them since the readings of 22 October "
                 "2026 (F1, F2)",
         "decision": "primary, figure unchanged (-3.651); in the outbound-transfer sensitivity register since 22 "
                     "October 2026"},
    ),
    "1492_2022": (
        {"flag": "an outward loss portfolio transfer (31 August 2022, to Syndicate 2008, of the 2020 year of account) and "
                 "a split RITC of the 2018 and prior liabilities effective 31 December 2022 (p62); the gross table "
                 "still carries the 2015-2018 liabilities at 31 December 2022 (PRA approval of the split RITC came "
                 "on 25 January 2023)",
         "reader": "C2",
         "rule": "an outward loss portfolio transfer is ceded reinsurance: it moves the net table and leaves the gross "
                 "table and gross R unchanged (data/outbound_transfer_retained_base.json, 1200/2022); an outward "
                 "transfer takes a figure out of the primary only where it dominates the gross step "
                 "(data/takeon_not_development.json: 1856/2020, 2001/2022), and here it does not move the gross "
                 "table; a transfer at the balance-sheet date does not move year t (error-rate protocol, ninth "
                 "amendment). Whether the 2018 year's +12.2m was set in pricing the deal cannot be told from the "
                 "pages, and no rule turns on it",
         "decision": "primary, figure unchanged (+3.669); the split RITC is an outward transfer at the start of "
                     "1492/2023, in the outbound-transfer sensitivity register since 22 October 2026"},
    ),
    "4444_2024": (
        {"flag": "a take-on in year t-1, not t: 'On 1 January 2023 the 2021 year of account of the Syndicate accepted "
                 "the RITC of the 2020 year of account of Syndicate 1861' (p99), carried on both 2024 diagonals (the "
                 "2023 report, p26: 'The 2019 and 2020 years of account development includes the business assumed "
                 "from Syndicate 1861'); presentation changed to US dollars in 2024, and the previous diagonal is the "
                 "2023 table's end-2023 cells retranslated at about 1.257 (C1, and the stored grids)",
         "reader": "C1",
         "rule": "the validity rule asks for no transaction in the step that the opening reserves do not carry "
                 "(design.md section 2, point 4); the 1 January 2024 reserves carry Syndicate 1861's business, which "
                 "entered in 2023, the year whose take-on base data/opening_reserves_takeon_base.json registers "
                 "(4444/2023). The take-on base and take-on rules concern the report year's transfers only",
         "decision": "primary, figure unchanged (+115.290)"},
    ),
    "1945_2024": (
        {"flag": "the '2014 & Prior' column is the 2023 report's '2013&Prior' and '2014' columns added by development "
                 "age (C2, from the 2023 report p52; F2 the same), so its last step holds the 2013&Prior block's 2023 "
                 "movement (-37k at 2023 rates) in place of its 2024 movement, and the column contributes -425k of "
                 "the +4.839m that includes it",
         "reader": "C2, F2",
         "rule": COLUMN_RULE,
         "decision": "the column is left out: the figure is +5.264 (F1 and F2 recompute it from the printed table, "
                     "and the estimator on the stored grid without the column gives it); +4.839 includes the column "
                     "and rests on A4 and C2, kept under superseded_readings"},
    ),
    "1945_2023": (
        {"flag": "the '2013&Prior' column of the 2023 table is built by development age from the older underwriting "
                 "years (C2 read the same construction), so its last step (-37k, ten years later 62,948 less nine "
                 "years later 62,985) is not the report year's movement",
         "reader": "F1, F2",
         "rule": COLUMN_RULE,
         "decision": "the column is left out: the figure is -4.997 (F1 and F2 recompute it from the printed table, "
                     "and the estimator on the stored grid without the column gives it); the triangle's own figure "
                     "with the column, -5.034, is the 672 construction's and the adopted figure before this decision"},
    ),
}

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
    return {"kind": "reading", "reader": rid, "round": ROUNDS.get(rid, READING_ROUND),
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


def strip_aggregated_column(tri, key):
    """A copy of a stored grid without its aggregated development-age column (the first column, whose label and anchor
    year AGGREGATED_COLUMN names), for the extraction's estimator."""
    want = AGGREGATED_COLUMN[key]
    agg = tri.get("aggregated_cohort") or {}
    years = list(tri.get("underwriting_years") or [])
    if agg.get("anchor") != want["anchor"] or agg.get("column") != 1 or not years or years[0] != want["anchor"]:
        raise SystemExit("%s: the stored grid's aggregated cohort %r is not the first column anchored at %s"
                         % (key, agg, want["anchor"]))
    if want["label"].replace(" ", "") not in str(agg.get("label", "")).replace(" ", ""):
        raise SystemExit("%s: the stored grid's aggregated column is %r, not %r" % (key, agg.get("label"), want["label"]))
    extra = set(tri) - {"type", "currency", "units", "units_evidence", "cell_binding", "underwriting_years",
                        "development_rows", "row_labels", "aggregated_cohort", "source_page", "entity"}
    if extra:
        raise SystemExit("%s: the stored grid has fields %s this build does not strip by column" % (key, sorted(extra)))
    out = copy.deepcopy(tri)
    out["underwriting_years"] = years[1:]
    out["development_rows"] = [list(row)[1:] for row in tri["development_rows"]]
    del out["aggregated_cohort"]
    return out


def column_blocks(data):
    """{model: ["aggregated_column"]} for every block whose stored gross RAG triangle carries an aggregated cohort (the
    blocks of a COLUMN_ONLY record the corpus rule does not see)."""
    out = {}
    for mk, block in sorted((data.get("models") or {}).items()):
        tri = block.get("_rag_triangle") if isinstance(block, dict) else None
        if isinstance(tri, dict) and tri.get("type") == "gross" and tri.get("aggregated_cohort"):
            out[mk] = ["aggregated_column"]
    return out


def load_column_readings():
    out = {}
    for rid in COLUMN_READERS:
        with io.open(COLUMN_READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
            out[rid] = json.load(fh)
    return out


def column_reading(rid, key, e):
    """One of the two column readers' readings of a 1945 record, in the register's reading form. F1 and F2 recompute
    the mature-cohort figure from the printed gross table without the aggregated column, and give the figure with it."""
    f = e["figure"]
    without = f.get("mature_excluding_and_prior_m", f.get("excluding_aggregated_column_m"))
    with_col = f.get("mature_including_and_prior_m", f.get("including_aggregated_column_m"))
    pages = e["pages"]
    own = pages.get(key, []) if isinstance(pages, dict) else pages
    other = {k: v for k, v in pages.items() if k != key} if isinstance(pages, dict) else {}
    if "cells_used" in e:
        cells = "; ".join("%s %s" % (y, t) for y, t in e["cells_used"].items())
        cells = "u<=%d (000s) without the column: %s; sum %+.3f excluding the column, %+.3f including it" % (
            max(int(y) for y in e["cells_used"]), cells, without, with_col)
        x_and_prior = e["and_prior_column"]
    else:
        cells = e["cells"]
        x_and_prior = e["x_and_prior"]
    out = {"kind": "reading", "reader": rid, "round": COLUMN_ROUND,
           "source": "results/extraction_error_rate/mature-cohort/fx-translation/readings/%s.json" % rid,
           "pages": _pages(own), "read_by": e.get("read_by"), "table": e.get("table"),
           "verdict": "confirmed_excluding_the_aggregated_column", "figure_m": _num(without),
           "figure_with_column_m": _num(with_col), "cells": cells, "x_and_prior": x_and_prior,
           "reconciliation": e.get("reconciliation"), "transaction": e.get("transaction")}
    if other:
        out["pages_of_the_earlier_report"] = {k: _pages(v) for k, v in other.items()}
    return out


def column_entry(entry, key, tri, year, fn, figure_with, model, printed_page, column_files, earlier):
    """Complete the figure entry of an AGGREGATED_COLUMN record: the figure is the estimator's on the stored grid
    without the column, and both column readers' (F1, F2); the figure with the column is the stored grid's own, the
    earlier readings of it (A4, C2) are kept under superseded_readings."""
    col = AGGREGATED_COLUMN[key]
    figure, details = compute(fn, strip_aggregated_column(tri, key), year)
    if figure is None:
        raise SystemExit("%s: the estimator computes no figure without the aggregated column: %s" % (key, details))
    reads = [column_reading(rid, key, column_files[rid][key]) for rid in COLUMN_READERS]
    for r in reads:
        if r["figure_m"] is None or abs(r["figure_m"] - figure) > FIGURE_TOL:
            raise SystemExit("%s: reader %s's figure %s is not the estimator's %s without the column"
                             % (key, r["reader"], r["figure_m"], figure))
        if r["figure_with_column_m"] is None or abs(r["figure_with_column_m"] - figure_with) > FIGURE_TOL:
            raise SystemExit("%s: reader %s's figure with the column %s is not the stored grid's %s"
                             % (key, r["reader"], r["figure_with_column_m"], figure_with))
    currency, gbp = fx_gbp(key, figure)
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["recomputation"].update({"figure_with_column_m": figure_with, "figure_without_column_m": figure,
                                   "estimator_without_column": "the same estimator on the stored grid with its "
                                                               "first column removed (strip_aggregated_column)"})
    entry["aggregated_column"] = {"label": col["label"], "anchor": col["anchor"], "rule": COLUMN_RULE,
                                  "figure_with_column_m": figure_with, "figure_without_column_m": figure,
                                  "column_step_m": round(figure_with - figure, 3)}
    entry["readings"] = reads
    if earlier:
        entry["superseded_readings"] = earlier
    gaps = independent_reading_gaps(entry)
    if gaps:
        raise SystemExit("%s: a figure entry needs two independent agent readings of the filing: %s" % (key, "; ".join(gaps)))
    tr = table_read(model, strip_aggregated_column(tri, key), figure, details, printed_page)
    tr["verdict"] += "; the aggregated column '%s' left out (Appendix 2.1)" % col["label"]
    entry["table_read"] = tr
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], (r.get("table") or {}).get("page"), r["cells"])
                                for r in reads)
    if key in NOTES:
        entry["notes"] = [dict(n) for n in NOTES[key]]
    entry["status"] = "primary"
    entry["decision"] = ("decision of the Claude analysis session, 22 October 2026, applying the author's decision of "
                         "22 October 2026 that Appendix 2.1's rule leaves the aggregated column '%s' out of the "
                         "mature-cohort figure (%s): primary; a valid mature-cohort figure: the printed gross table's "
                         "own development over u <= t-2 without that column; under the %s"
                         % (col["label"], key, OWNER))
    return entry


def independent_reading_gaps(entry):
    """Why a figure entry does not rest on two independent agent readings of the filing, or []: every reading is an
    agent's (AGENT_READING_KINDS; the extraction's table read is not a reading), at least two distinct readers, at
    least one of them a reader's own reading of 22 October 2026, and each with its pages and cells, giving the
    entry's figure."""
    reads = entry.get("readings") or []
    gaps = ["reading %d is not an agent's reading (kind %r)" % (i, r.get("kind"))
            for i, r in enumerate(reads) if r.get("kind") not in AGENT_READING_KINDS]
    agents = [r for r in reads if r.get("kind") in AGENT_READING_KINDS]
    if len({r.get("reader") for r in agents if r.get("reader")}) < 2:
        gaps.append("two distinct readers (%s)" % sorted({str(r.get("reader")) for r in agents}))
    if not any(r.get("kind") == "reading" for r in agents):
        gaps.append("a reader's own reading (kind 'reading')")
    for i, r in enumerate(agents):
        if not r.get("pages") or not str(r.get("cells") or "").strip():
            gaps.append("reading %s's pages and cells" % r.get("reader"))
        if r.get("figure_m") is None or abs(r["figure_m"] - entry["figure_m"]) > FIGURE_TOL:
            gaps.append("reading %s's figure %s against the entry's %s" % (r.get("reader"), r.get("figure_m"),
                                                                           entry["figure_m"]))
    return gaps


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
def entry_for(key, data, pop_blocks, fn, decisions, design, readings, study, column_files=None):
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
    if by is None and key in COLUMN_ONLY:
        by = "aggregated_column"
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
    if key in AGGREGATED_COLUMN:
        if figure is None:
            raise SystemExit("%s: the estimator computes no figure on the stored grid: %s" % (key, details))
        return column_entry(entry, key, tri, year, fn, figure, model, printed_page, column_files, rr)
    if dec is None:
        raise SystemExit("%s: a displaced record with neither a decision (decisions.csv) nor a NO_FIGURE reason" % key)
    if figure is None:
        raise SystemExit("%s: decided with a figure, but the estimator computes none: %s" % (key, details))
    study_rows = [study_reading(p, row) for p, row in study.get(key, [])
                  if _num(row.get("triangle_recomputation_m")) is not None
                  and abs(_num(row.get("triangle_recomputation_m")) - figure) <= FIGURE_TOL]
    reads = rr + study_rows
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["readings"] = reads
    gaps = independent_reading_gaps(entry)
    if gaps:
        raise SystemExit("%s: a figure entry needs two independent agent readings of the filing: %s"
                         % (key, "; ".join(gaps)))
    # supporting evidence, not a reading: the grid the extraction's table backend transcribed, which the figure is
    # recomputed from
    entry["table_read"] = table_read(model, tri, figure, details, printed_page)
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], (r.get("table") or {}).get("page"), r["cells"])
                                for r in rr)
    if key in NOTES:
        entry["notes"] = [dict(n) for n in NOTES[key]]
    if key in TAKEON_EXCLUDED:
        entry["status"] = "excluded_takeon_not_development"
        rule = ("the take-on dominates the triangle's step: data/takeon_not_development.json holds the record with "
                "figure_route mature_cohort_triangle, so the loader adopts the figure and then tags the record "
                "TAKEON_NOT_DEVELOPMENT")
    else:
        entry["status"] = "primary"
        rule = "a valid mature-cohort figure: the printed gross table's own development over u <= t-2"
    agreed = dec.get("readers_agreed") or ""
    verdicts = ["%s %s" % (r["reader"], r["verdict"]) for r in rr]
    if agreed != "yes":
        readers_note = "; readers: " + agreed
    elif len({r["verdict"] for r in rr}) > 1:
        readers_note = "; readers disagree (%s), settled under the existing rules in notes" % ", ".join(verdicts)
    else:
        readers_note = ""
    entry["decision"] = ("decision of the Claude analysis session, 22 October 2026 "
                         "(results/extraction_error_rate/mature-cohort/"
                         "decisions.csv, adjudication.md): %s; %s; under the %s%s"
                         % (dec.get("final_status"), rule, OWNER, readers_note))
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
    column_files = load_column_readings()
    if set(COLUMN_ONLY) & set(pop) or not set(COLUMN_ONLY) <= set(AGGREGATED_COLUMN):
        raise SystemExit("COLUMN_ONLY %s must be aggregated-column records no precedence rule displaced" % (COLUMN_ONLY,))
    blocks = dict(pop)
    for key in COLUMN_ONLY:
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            blocks[key] = column_blocks(json.load(fh))
    reg = {"_purpose": PURPOSE}
    for key in sorted(blocks, key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1]))):
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            data = json.load(fh)
        reg[key] = entry_for(key, data, blocks[key], fn, decisions, design, readings, study, column_files)
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
    "a figure carries at least two independent agent readings of the filing, each with its reader, pages and cells: "
    "the readings of 22 October 2026 and the second readings of the records that round read once (kind 'reading'), "
    "and earlier readings of the error-rate study that recomputed the same printed triangle (kind "
    "'error_rate_study'). The extraction's own table read of the printed page (the stored grid the estimator computed "
    "from) is kept under table_read as supporting evidence; it is not a reading. notes records a flag a reader raised "
    "and the existing rule that decides it. An entry without a figure "
    "states its reason (confirmed_figure_register, no_mature_cohort, triangle_figure_stands, "
    "outside_working_sample_not_read, aggregated_column_not_like_for_like), and the loader adopts nothing for it. "
    "status 'excluded_takeon_not_development' marks a figure whose record data/takeon_not_development.json excludes "
    "(an entry there with figure_route 'mature_cohort_triangle'). An entry with an aggregated_column object (the two "
    "records of syndicate 1945, the author's decision of 22 October 2026) leaves the stored grid's aggregated "
    "development-age column out of the figure (Appendix 2.1): its figure is the estimator's on the grid without the "
    "column and both column readers' (F1, F2, archived in fx-translation/readings/), figure_with_column_m is the grid's "
    "own, and the earlier readings of that figure are kept under superseded_readings. Its displaced.by is a "
    "precedence rule where one displaced the triangle (1945/2024), and 'aggregated_column' where the adopted figure "
    "is the triangle's own with the column in it (1945/2023).")


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
