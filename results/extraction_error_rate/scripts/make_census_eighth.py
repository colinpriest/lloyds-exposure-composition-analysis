r"""The eighth amendment's census (error-rate-protocol.md): its records, briefs, carry-over decisions and batches.

Computed from the records and refit 2's outputs (analysis 8addc04, exposure_results run a5d20430) before any record
below is read. Six parts, one per mechanism the third sample and its second readings found; a record may sit in more
than one. Each part refuses unless its rule flags its defining records.

  movement         Syndicate 382's movement tables differenced as if cumulative. Every working-sample record of
                   syndicate 382; and every working-sample record with a stored triangle that looks like a movement
                   table: over the cells after the first row, a share below zero of at least 0.2 or a share under a
                   quarter of the column's first cell of at least 0.5, leaving out a cumulative table printed negative
                   (share below zero at least 0.95 and share small at most 0.05).
  transposed       A provisions note whose prior-year line holds the current year of account. Every working-sample
                   record of syndicates 2010 and 3010; and every working-sample record whose adopted figure, in a model
                   whose route is not a triangle, lies within 5% of the report year's first-row cell in that model's
                   triangle (scan_transposed_note_lines.py).
  net_table        A net table taken for gross. Every working-sample record whose adopted figure is a triangle figure
                   (score_error_rate.figure_source) and whose triangle page names a net table ("net of reinsurance",
                   "after reinsurance", "net claims", "incurred net", "ultimate net", "cumulative net", "net basis")
                   and has no gross heading ("gross and net", "gross of reinsurance", "gross claims", "incurred gross", "ultimate gross",
                   "cumulative gross", "gross basis", "before reinsurance", "gross ultimate", or a line reading Gross).
  provisions_row   A provisions row that is not a movement. Every working-sample record whose route is rag_provisions
                   and whose _adobe_provisions.movement_semantics says the table is not a movement note or the column
                   is not bound to the report year.
  opening          An opening-reserves misreading. Every working-sample record whose adopted opening reserves are under
                   half or over twice both neighbouring years' (t-1 and t+1), where the two neighbours are within a
                   factor of two of each other.
  takeon_triangle  A take-on inside a triangle figure. Every working-sample record whose adopted figure is a triangle
                   figure and whose filing records a transfer in from outside the syndicate: the RITC scan decides an
                   inward RITC in the report year; or a passage (its sentence, at most 300 characters either side)
                   names reinsurance to close, RITC or a portfolio transfer, an inward word (accept, into the
                   syndicate, take-on, a transfer or closure into this syndicate, from Syndicate N), the report year, and another syndicate's
                   number or a portfolio transfer, and is not about a managing agent taking on or novating the
                   management of syndicates; or a roll-forward row reads "RITC (accepted) from" another syndicate.

Records already decided are listed and not read: the third sample's eight confirmed errors, 1274/2018 and 623/2014
(the owner's decisions of 14 September 2026), 2003/2018 (both readings: the opening reserves are the reinsurers'
share, and whether the triangle carries Syndicate 1209's RITC the filing does not say), and the records the seventh
amendment repaired by a confirmed figure.

Carry-over, decided here before any reading. Every part but takeon_triangle asks what a verdict already answers (is the
adopted figure, its basis or its opening reserves right?). A record read in an earlier sample or census keeps that
first reading, and its second reading where it has one, when nothing its verdict was read against has changed (the
adopted figure, the opening reserves, the figure's source, the basis, the cohort scope); a record with a first reading
alone gets a second. takeon_triangle's question is new, so its records are read afresh. Everything else is read
afresh, in batches of five.

    python make_census_eighth.py --dry-run     # counts and lists only, writes nothing
    python make_census_eighth.py               # writes the census, briefs, carry-over and batches
"""
import argparse
import copy
import datetime
import glob
import io
import json
import re
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fitz  # noqa: E402
import run_analysis as ra  # noqa: E402
import score_error_rate as ser  # noqa: E402
import adopted_model  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
BATCH = 5
OUT_CENSUS = SCR / "error-rate-census-eighth.json"
OUT_BRIEFS = SCR / "error-rate-briefs-eighth.json"
PARTS = ("movement", "transposed", "net_table", "provisions_row", "opening", "takeon_triangle")
DEFINERS = {"movement": ["syndicate_382_2015", "syndicate_382_2016"],
            "transposed": ["syndicate_2010_2018", "syndicate_3010_2019"],
            "net_table": ["syndicate_1880_2014"],
            "provisions_row": ["syndicate_1980_2018"],
            "opening": ["syndicate_2003_2018"],
            "takeon_triangle": ["syndicate_1274_2018", "syndicate_2003_2018"]}
THIRD_ERRORS = ["syndicate_2010_2018", "syndicate_3010_2019", "syndicate_382_2015", "syndicate_382_2016",
                "syndicate_382_2018", "syndicate_382_2019", "syndicate_1880_2014", "syndicate_1980_2018"]
DECIDED = dict({s: "a confirmed error of the third sample, repaired under the owner's decision of 14 September 2026"
                for s in THIRD_ERRORS},
               **{"syndicate_1274_2018": "excluded as a take-on inside its triangle (owner's decision, 14 September 2026)",
                  "syndicate_623_2014": "excluded: its figure is loss-ratio points (owner's decision, 14 September 2026)",
                  "syndicate_2003_2018": "both readings: the opening reserves are the reinsurers' share (repaired by the "
                                         "owner's decision, 14 September 2026); whether the triangle carries Syndicate "
                                         "1209's RITC the filing does not say",
                  "syndicate_3624_2015": "repaired by a confirmed figure (fifth and seventh amendments)",
                  "syndicate_1225_2022": "repaired by a confirmed figure (seventh amendment)",
                  "syndicate_2010_2019": "repaired by a confirmed figure (seventh amendment)",
                  "syndicate_4444_2022": "repaired by a confirmed figure (seventh amendment)",
                  "syndicate_2008_2019": "repaired by a confirmed figure (seventh amendment, point 5)"})
SCALE = {"thousands": 0.001, "millions": 1.0}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def canonical(data):
    models = data.get("models") or {}
    keys = sorted(models)
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]


for p in (OUT_CENSUS, OUT_BRIEFS):
    if p.exists() and not args.dry_run:
        raise SystemExit("%s exists; the eighth census is fixed once, before any reading" % p.name)
third = load(SCR / "error-rate-sample-third.json")
cur = load(AN / "model" / "exposure_results.json")
if cur.get("analysis_run_id") != third["exposure_results_run_id"]:
    raise SystemExit("exposure_results.json is not refit 2's run, from which the third sample was drawn")
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}
_S, _R, _H, _yr, _syn, _ritc = adopted_model.load_sample()
WS = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(_syn, _yr))
if len(WS) != third["rebuilt_working_sample_n"]:
    raise SystemExit("the working sample holds %d records, not refit 2's %d" % (len(WS), third["rebuilt_working_sample_n"]))
CONFIRMED = ra.load_pyd_confirmed_figures()
overruled = ser.overruled_stems()
records = {s: load(AN / "pdf_extraction" / ("%s.json" % s)) for s in WS}


PDFS = EX / "syndicate_reports" / "pdfs"
CONVERTED = EX / "pdf_extraction" / "html_converted"


def filing_pdf(stem):
    """The PDF the packs' page numbers refer to (filing_pages.py): the filed PDF, else the HTML report's conversion."""
    for d in (PDFS, CONVERTED):
        if (d / ("%s.pdf" % stem)).exists():
            return str(d / ("%s.pdf" % stem))
    return None


def brief(stem):
    key = stem.replace("syndicate_", "")
    data = records[stem]
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    if key in CONFIRMED:
        cm = ra.apply_confirmed_figure(cm, CONFIRMED[key])
    route = cm.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": filing_pdf(stem),
        "pack": str(SCR / "packs-error-rate-eighth" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        ADOPTED: cm.get("prior_year_development_gbp_m"),
        OPENING: cm.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": dict({k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                                  "triangle_units", "triangle_source_page", "note")},
                      **({k: route.get(k) for k in ("figure_kind", "basis", "register")}
                         if route.get("source") == ra.CONFIRMED_FIGURE_SOURCE else {})),
        "cited_pages": {"prior_year_movement": cm.get("prior_year_movement_page"),
                        "opening_reserves": cm.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "regime_sources": o.get("assumed_business"),
        "model_notes": notes[:1500],
    }


briefs = {s: brief(s) for s in WS}
source = {s: ser.figure_source(briefs[s], overruled)[0] for s in WS}
hits = {p: {} for p in PARTS}


def flag(part, stem, why):
    hits[part].setdefault(stem, []).append(why)


# --- movement ---------------------------------------------------------------------------------------------------------
def shape(tri):
    rows = tri.get("development_rows") or []
    if len(rows) < 3 or not rows[0]:
        return None
    later = neg = small = 0
    for j, first in enumerate(rows[0]):
        if not isinstance(first, (int, float)) or first == 0:
            continue
        for row in rows[1:]:
            if j >= len(row) or not isinstance(row[j], (int, float)):
                continue
            later += 1
            neg += row[j] < 0
            small += abs(row[j]) < 0.25 * abs(first)
    if later < 6:
        return None
    return round(neg / later, 2), round(small / later, 2), later


for s in WS:
    if s.startswith("syndicate_382_"):
        flag("movement", s, "a working-sample record of syndicate 382")
    for model, md in sorted((records[s].get("models") or {}).items()):
        for kind in ("_rag_triangle", "_claims_triangle"):
            sh = shape(md.get(kind) or {})
            if sh and (sh[0] >= 0.2 or sh[1] >= 0.5) and not (sh[0] >= 0.95 and sh[1] <= 0.05):
                flag("movement", s, "%s %s: share below zero %.2f, share small %.2f, %d cells" % ((model, kind) + sh))

# --- transposed -------------------------------------------------------------------------------------------------------
for s in WS:
    if re.match(r"syndicate_(2010|3010)_\d{4}$", s):
        flag("transposed", s, "a working-sample record of syndicate %s" % s.split("_")[1])
    year = int(s.split("_")[2])
    for model, md in sorted((records[s].get("models") or {}).items()):
        adopted = md.get("prior_year_development_gbp_m")
        if adopted is None or (md.get("_pyd_route") or {}).get("source") == "rag_triangle":
            continue
        for kind in ("_rag_triangle", "_claims_triangle"):
            tri = md.get(kind) or {}
            ys, rows = tri.get("underwriting_years") or [], tri.get("development_rows") or []
            scale = SCALE.get((tri.get("units") or "").lower())
            if year not in ys or not rows or scale is None:
                continue
            j = ys.index(year)
            first = rows[0][j] if j < len(rows[0]) else None
            if first is None or first == 0:
                continue
            if abs(adopted - first * scale) <= 0.05 * abs(first * scale):
                flag("transposed", s, "%s: adopted %s within 5%% of the report year's first estimate %.3f (%s)"
                     % (model, adopted, first * scale, kind))
            break

# --- net_table --------------------------------------------------------------------------------------------------------
NET_HEAD = re.compile(r"net of reinsurance|after reinsurance|net claims|incurred net|ultimate net|cumulative net|net basis", re.I)
GROSS_HEAD = re.compile(r"gross and net|gross of reinsurance|gross claims|incurred gross|ultimate gross|cumulative gross|gross basis|"
                        r"before reinsurance|gross ultimate|gross of reinsurers|^\s*gross\s*$", re.I | re.M)
page_cache = {}


def page_text(stem, page):
    k = (stem, page)
    if k not in page_cache:
        if not briefs[stem]["filing_pdf"]:
            page_cache[k] = ""
        else:
            doc = fitz.open(briefs[stem]["filing_pdf"])
            page_cache[k] = doc[page - 1].get_text() if 1 <= page <= len(doc) else ""
            doc.close()
    return page_cache[k]


no_page = []
for s in WS:
    if source[s] != "triangle":
        continue
    cm = records[s]["models"][briefs[s]["canonical_model"]]
    page = briefs[s]["route"].get("triangle_source_page") or (cm.get("_rag_triangle") or {}).get("source_page")
    if not isinstance(page, int):
        no_page.append(s)
        continue
    raw = page_text(s, page)
    m = NET_HEAD.search(raw)
    if m and not GROSS_HEAD.search(raw):
        flag("net_table", s, "p%d: '%s' and no gross heading: ...%s..."
             % (page, m.group(0), re.sub(r"\s+", " ", raw[max(0, m.start() - 150): m.end() + 150])))

# --- provisions_row ---------------------------------------------------------------------------------------------------
for s in WS:
    cm = records[s]["models"][briefs[s]["canonical_model"]]
    if (cm.get("_pyd_route") or {}).get("source") != "rag_provisions":
        continue
    ms = (cm.get("_adobe_provisions") or {}).get("movement_semantics") or {}
    if ms.get("table_is_movement_note") is False or ms.get("column_bound_to_report_year") is False:
        flag("provisions_row", s, "row %r: table_is_movement_note %s, column_bound_to_report_year %s"
             % (ms.get("row_label"), ms.get("table_is_movement_note"), ms.get("column_bound_to_report_year")))

# --- opening ----------------------------------------------------------------------------------------------------------
panel = {}
for p in glob.glob(str(AN / "pdf_extraction" / "syndicate_*_*.json")):
    parts = Path(p).stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit():
        continue
    data = records.get(Path(p).stem) or load(p)
    if not data.get("models"):
        continue
    try:
        v = data["models"][canonical(data)].get("opening_reserves_gbp_m")
    except (ValueError, KeyError):
        continue
    if isinstance(v, (int, float)) and v > 0:
        panel[(parts[1], int(parts[2]))] = v
for s in WS:
    syn, year = s.split("_")[1], int(s.split("_")[2])
    v = briefs[s][OPENING]
    if not isinstance(v, (int, float)) or v <= 0:
        continue
    nb = [panel[(syn, y)] for y in (year - 1, year + 1) if (syn, y) in panel]
    if len(nb) != 2 or max(nb) > 2 * min(nb):
        continue
    if all(v < 0.5 * n for n in nb) or all(v > 2 * n for n in nb):
        others = ["%s says %s" % (model, md.get("opening_reserves_gbp_m"))
                  for model, md in sorted((records[s].get("models") or {}).items())
                  if model != briefs[s]["canonical_model"] and md.get("opening_reserves_gbp_m") != v]
        flag("opening", s, "opening %s against neighbouring years %s%s"
             % (v, nb, ("; " + "; ".join(others)) if others else ""))

# --- takeon_triangle --------------------------------------------------------------------------------------------------
scan = load(EX / "pdf_extraction" / "ritc_scan.json")
no_filing = []
TRANSFER = re.compile(r"reinsur\w*\s+to\s+close|\bRITC\b|portfolio\s+transfer", re.I)
ACCEPTS = re.compile(r"\baccept|into (?:the|this) syndicate\b|take-on|taken on", re.I)
TO_SYNDICATE = re.compile(r"(?:transferred|reinsured to close|closed)\s+(?:in)?to\s+(?:the\s+|this\s+)?"
                          r"syndicate\s*(\d{3,4})?", re.I)
FROM_SYNDICATE = re.compile(r"\bfrom\s+(?:syndicate\s*|s)(\d{3,4})\b", re.I)


def inward(w, syn):
    """Whether a passage describes business coming into this syndicate: an acceptance, a take-on, a transfer or
    closure into the syndicate or into this syndicate's own number, or business from another syndicate."""
    if ACCEPTS.search(w):
        return True
    if any(m.group(1) is None or int(m.group(1)) == int(syn) for m in TO_SYNDICATE.finditer(w)):
        return True
    return any(int(m.group(1)) != int(syn) for m in FROM_SYNDICATE.finditer(w))


SYND = re.compile(r"(?:\b[Ss]yndicates?\s+|\bS)(\d{3,4})\b")
ROW = re.compile(r"\bRITC\s+(?:accepted\s+)?from\s+(?:[Ss]yndicate\s+|S)(\d{3,4})\b")
MANAGEMENT = re.compile(r"management of|took on (?:the )?management|novat", re.I)
for s in WS:
    if source[s] != "triangle":
        continue
    key, syn, year = s.replace("syndicate_", ""), s.split("_")[1], int(s.split("_")[2])
    top = scan.get(key) or {}
    if top.get("ritc_occurred") is True and top.get("direction") == "inward" and top.get("event_year") == year:
        flag("takeon_triangle", s, "RITC scan: an inward RITC in %d: %s"
             % (year, re.sub(r"\s+", " ", top.get("evidence") or "")[:240]))
    if not briefs[s]["filing_pdf"]:
        no_filing.append(s)
        continue
    doc = fitz.open(briefs[s]["filing_pdf"])
    text = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in doc))
    doc.close()
    for m in TRANSFER.finditer(text):
        a = text.rfind(". ", 0, m.start())
        b = text.find(". ", m.end())
        w = text[max(a + 2 if a >= 0 else 0, m.start() - 300): min(b + 1 if b >= 0 else len(text), m.end() + 300)]
        if (inward(w, syn) and re.search(r"\b%d\b" % year, w) and not MANAGEMENT.search(w)
                and ([n for n in SYND.findall(w) if int(n) != int(syn)] or re.search(r"portfolio\s+transfer", w, re.I))):
            flag("takeon_triangle", s, "text: ...%s..." % w[:500])
            break
    r = next((x for x in ROW.finditer(text) if int(x.group(1)) != int(syn)), None)
    if r:
        flag("takeon_triangle", s, "row: ...%s..." % text[max(0, r.start() - 120): r.end() + 160])

# --- definers, decided records, carry-over ----------------------------------------------------------------------------
for part, ds in DEFINERS.items():
    missing = [d for d in ds if d not in hits[part]]
    if missing:
        raise SystemExit("part %s does not flag %s, the records that define it: its rule is wrong" % (part, missing))

READ_SETS = [("third sample", "error-rate-briefs-third.json", "error-rate-verdicts-third.json", "error-rate-verification-third.json"),
             ("take-on census", "error-rate-briefs-takeon.json", "error-rate-verdicts-takeon.json", "error-rate-verification-takeon.json"),
             ("found in passing", "error-rate-briefs-passing.json", "error-rate-verdicts-passing.json", "error-rate-verification-passing.json"),
             ("census", "error-rate-briefs-census.json", "error-rate-verdicts-census.json", "error-rate-verification-census.json"),
             ("second sample", "error-rate-briefs-after.json", "error-rate-verdicts-after.json", "error-rate-verification-after.json"),
             ("first sample", "error-rate-briefs.json", "error-rate-verdicts.json", "error-rate-verification.json")]
held = []
for name, b, v, w in READ_SETS:
    bs = {x["stem"]: x for x in load(SCR / b)}
    vs = {x["stem"] for x in load(SCR / v)}
    ws2 = {x["stem"] for x in load(SCR / w)} if (SCR / w).exists() else set()
    held.append((name, bs, vs, ws2))


def same_number(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) <= 1e-9


def changes(old, new):
    why = []
    if not same_number(old.get(ADOPTED), new[ADOPTED]):
        why.append("adopted figure %s -> %s" % (old.get(ADOPTED), new[ADOPTED]))
    if not same_number(old.get(OPENING), new[OPENING]):
        why.append("opening reserves %s -> %s" % (old.get(OPENING), new[OPENING]))
    if ser.figure_source(old, overruled)[0] != ser.figure_source(new, overruled)[0]:
        why.append("figure source %s -> %s" % (ser.figure_source(old, overruled)[0], ser.figure_source(new, overruled)[0]))
    if (old.get("loader_basis") or [None])[0] != (new["loader_basis"] or [None])[0]:
        why.append("basis %s -> %s" % (old.get("loader_basis"), new["loader_basis"]))
    if (old.get("loader_cohort_scope") or [None])[0] != (new["loader_cohort_scope"] or [None])[0]:
        why.append("cohort scope %s -> %s" % (old.get("loader_cohort_scope"), new["loader_cohort_scope"]))
    return why


stems = sorted({s for part in PARTS for s in hits[part]})
decided = {s: DECIDED[s] for s in stems if s in DECIDED}
census, decisions = [], []
for s in stems:
    if s in DECIDED:
        continue
    parts = [p for p in PARTS if s in hits[p]]
    b = dict(briefs[s], census_parts=parts, census_reasons={p: hits[p][s] for p in parts})
    census.append(b)
    if "takeon_triangle" in parts:
        decisions.append({"stem": s, "parts": parts, "carry_first": None, "carry_second": False,
                          "why": ["the take-on question is new: read afresh"]})
        continue
    found = next((h for h in held if s in h[2]), None)
    if found is None:
        decisions.append({"stem": s, "parts": parts, "carry_first": None, "carry_second": False,
                          "why": ["no earlier sample or census read it"]})
        continue
    name, bs, _vs, ws2 = found
    why = changes(bs[s], briefs[s])
    if why:
        decisions.append({"stem": s, "parts": parts, "carry_first": None, "carry_second": False,
                          "why": ["read in the %s, since changed: %s" % (name, "; ".join(why))]})
    else:
        decisions.append({"stem": s, "parts": parts, "carry_first": name, "carry_second": s in ws2,
                          "why": ["read in the %s; nothing its verdict was read against changed" % name]})

fresh = [b for b, d in zip(census, decisions) if d["carry_first"] is None]
second_only = [d["stem"] for d in decisions if d["carry_first"] and not d["carry_second"]]
both = [d["stem"] for d in decisions if d["carry_first"] and d["carry_second"]]
print("working sample %d; triangle figures %d (no triangle page for %d; no filing PDF for %d: %s)" % (len(WS), sum(1 for s in WS if source[s] == "triangle"), len(no_page), len(no_filing), no_filing))
for part in PARTS:
    print("part %-16s flagged %3d (decided %d)" % (part, len(hits[part]), sum(1 for s in hits[part] if s in DECIDED)))
    for s in sorted(hits[part]):
        print("    %-22s %s%s" % (s, "DECIDED " if s in DECIDED else "", hits[part][s][0][:230]))
print("census records %d: read afresh %d, first reading carried and second to read %d, both readings carried %d; decided %d"
      % (len(census), len(fresh), len(second_only), len(both), len(decided)))
if args.dry_run:
    sys.exit(0)

now = datetime.datetime.now().isoformat(timespec="seconds")
io.open(str(OUT_CENSUS), "w", encoding="utf-8").write(json.dumps({
    "protocol": "error-rate-protocol.md, eighth amendment, written before this file",
    "written": now, "exposure_results_run_id": cur["analysis_run_id"], "working_sample_n": len(WS),
    "rules": {p: re.sub(r"\s+", " ", __doc__.split("  " + p, 1)[1].split("\n  ", 1)[0]).strip() if ("  " + p) in __doc__ else None
              for p in PARTS},
    "parts": {p: {s: hits[p][s] for s in sorted(hits[p])} for p in PARTS},
    "decided": decided, "stems": [b["stem"] for b in census],
    "no_triangle_page": no_page, "no_filing_pdf": no_filing}, indent=1, ensure_ascii=False))
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(census, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-carry-over-eighth.json"), "w", encoding="utf-8").write(json.dumps(
    {"census": OUT_CENSUS.name, "rule": "eighth amendment (carry-over as the fourth amendment, point 3)",
     "decided_before_any_reading": True, "decisions": decisions}, indent=1))
io.open(str(SCR / "error-rate-fresh-stems-eighth.json"), "w", encoding="utf-8").write(json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-eighth-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
print("written %s (%s), %s, error-rate-carry-over-eighth.json, error-rate-fresh-stems-eighth.json, %d batch(es)"
      % (OUT_CENSUS.name, now, OUT_BRIEFS.name, nb))
