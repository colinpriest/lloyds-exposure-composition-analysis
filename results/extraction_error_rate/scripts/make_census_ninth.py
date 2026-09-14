r"""The ninth amendment's take-on base census (error-rate-protocol.md): its records, briefs and carry-over skeleton.

Computed before any record below is read, from the working sample the loader predicts for refit 3 on the committed
registers (after the ninth amendment's point 1), with the loader's own flow (load_and_classify, assign_event_groups,
build_subsets, compute_eligibility) as predict_refit3_population.py runs it. A record is listed when its filing records a
transfer into the syndicate in the report year, by any of three rules. The census refuses unless it lists 1884/2021,
3500/2021 and 2008/2019, which define it; a run that writes refuses unless the registers and the loader are committed.

  scan     the RITC scan (pdf_extraction/ritc_scan.json) decides an inward RITC in the report year.
  passage  a passage (its sentence, at most 300 characters either side) names a reinsurance to close, an RITC, a
           portfolio transfer or an LPT, an inward word (accept, into the syndicate, take-on, taken on, assumed, a
           transfer or closure into this syndicate, from Syndicate N), the report year, and another syndicate's number
           or a portfolio transfer, and is not about a managing agent taking on or novating the management of
           syndicates: the eighth census's takeon_triangle rule, for every figure source, with LPTs.
  row      a table row names a take-on, its amount directly after the label (a footnote mark allowed): an RITC or
           reinsurance to close taken on (reserves, balances or provisions), adjusted, inwards or from another
           syndicate; inwards RITC; reinsurance of new liabilities; a take-on of reserves or balances; a portfolio
           transfer, loss portfolio transfer or LPT; or an RITC or reinsurance to close accepted or received inside a
           claims roll-forward (a 1 January balance within 300 characters before the label, and no year of account
           named within 200 characters of it). A premium line is not a take-on row, and neither is a syndicate's own
           years of account closing into each other, which every Lloyd's syndicate books each year.
           Tightened on two dry runs (census-ninth-dryrun.log, census-ninth-dryrun2.log, probe-census-ninth-rows.txt)
           that listed the rule's hits and read no filing for a verdict. The first rule counted any such words with an
           amount within 40 characters and listed 150 records, 53 of them on the technical account's own premium line;
           the second, a label with its amount directly after it, listed 75, mostly the syndicate's own RITC between
           its years of account in class and cash-flow tables ("RITC received", "RITC Accepted").

Carry-over skeleton: a listed record the eighth census read in its takeon_triangle part carries both readings' findings,
amounts and evidence, and what has changed in its brief since, for the editor to record before any new reading whether
both readings answer where the table carries the transferred business and how much was transferred (ninth amendment,
point 4; record_carry_ninth.py). Every other listed record is to be read afresh.

The filings' text is cached in ninth-text-cache/ so a dry run and the run that writes read the same text.

    python make_census_ninth.py --dry-run     # counts and lists only, writes nothing but the text cache
    python make_census_ninth.py               # writes the census, the briefs and the carry-over skeleton
"""
import argparse
import copy
import datetime
import io
import json
import re
import subprocess
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

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
OUT_CENSUS = SCR / "error-rate-census-ninth.json"
OUT_BRIEFS = SCR / "error-rate-briefs-ninth.json"
OUT_CARRY = SCR / "error-rate-carry-over-ninth-skeleton.json"
CACHE = SCR / "ninth-text-cache"
RULES = ("scan", "passage", "row")
DEFINERS = ["syndicate_1884_2021", "syndicate_3500_2021", "syndicate_2008_2019"]
COMMITTED = ["data/pyd_confirmed_figures.json", "data/opening_reserves_confirmed.json", "data/takeon_not_development.json",
             "data/opening_reserves_takeon_base.json", "data/pyd_basis_register.json", "src/run_analysis.py"]
PDFS = EX / "syndicate_reports" / "pdfs"
CONVERTED = EX / "pdf_extraction" / "html_converted"


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


def filing_pdf(stem):
    """The PDF the packs' page numbers refer to (filing_pages.py): the filed PDF, else the HTML report's conversion."""
    for d in (PDFS, CONVERTED):
        if (d / ("%s.pdf" % stem)).exists():
            return str(d / ("%s.pdf" % stem))
    return None


if not args.dry_run:
    for p in (OUT_CENSUS, OUT_BRIEFS):
        if p.exists():
            raise SystemExit("%s exists; the ninth census is fixed once, before any reading" % p.name)
    dirty = subprocess.run(["git", "-C", str(AN), "status", "--porcelain", "--"] + COMMITTED,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("the registers or the loader are not committed, nothing written:\n%s" % dirty)

# --- the working sample the loader predicts for refit 3 ------------------------------------------------------------
ra.log = lambda *a, **k: None
loaded, counters, _clog, _files = ra.load_and_classify()
ra.assign_event_groups(loaded, min_events=3)
_meta, subsets = ra.build_subsets(loaded)
ra.compute_eligibility(loaded, subsets)
REC = {"syndicate_%s_%s" % (r["syndicate"], r["year"]): r for r in loaded}
WS = sorted(s for s, r in REC.items() if r.get("eligible_for_capital"))
CONFIRMED = ra.load_pyd_confirmed_figures()
OPENINGS = ra.load_opening_reserves_confirmed()
BASE = ra.load_takeon_base()
overruled = ser.overruled_stems()
raw = {s: load(AN / "pdf_extraction" / ("%s.json" % s)) for s in WS}


def brief(stem):
    key = stem.replace("syndicate_", "")
    data = raw[stem]
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    if key in CONFIRMED:
        cm = ra.apply_confirmed_figure(cm, CONFIRMED[key])
    if key in OPENINGS:
        cm = ra.apply_confirmed_opening(cm, OPENINGS[key])
    if key in BASE:
        cm = ra.apply_takeon_base(cm, BASE[key])
    route = cm.get("_pyd_route") or {}
    r = REC[stem]
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": filing_pdf(stem),
        "pack": str(SCR / "packs-error-rate-ninth" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        ADOPTED: cm.get("prior_year_development_gbp_m"),
        OPENING: cm.get("opening_reserves_gbp_m"),
        "opening_registers": {"confirmed_opening": key in OPENINGS, "takeon_base": key in BASE},
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": dict({k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                                  "triangle_units", "triangle_source_page", "note")},
                      **({k: route.get(k) for k in ("figure_kind", "basis", "register")}
                         if route.get("source") == ra.CONFIRMED_FIGURE_SOURCE else {})),
        "cited_pages": {"prior_year_movement": cm.get("prior_year_movement_page"),
                        "opening_reserves": cm.get("opening_reserves_page")},
        "loader_basis": [r.get("pyd_basis"), r.get("pyd_basis_source")],
        "loader_cohort_scope": [r.get("pyd_cohort_scope"), r.get("pyd_cohort_route")],
        "model_notes": notes[:1500],
    }


briefs = {s: brief(s) for s in WS}
hits = {rule: {} for rule in RULES}


def flag(rule, stem, why):
    hits[rule].setdefault(stem, []).append(why)


def filing_text(stem):
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / ("%s.txt" % stem)
    if cached.exists():
        return io.open(str(cached), encoding="utf-8").read()
    pdf = briefs[stem]["filing_pdf"]
    if not pdf:
        return None
    doc = fitz.open(pdf)
    text = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in doc))
    doc.close()
    io.open(str(cached), "w", encoding="utf-8").write(text)
    return text


scan = load(EX / "pdf_extraction" / "ritc_scan.json")
TRANSFER = re.compile(r"reinsur\w*\s+to\s+close|\bRITC\b|portfolio\s+transfer|\bLPTs?\b", re.I)
ACCEPTS = re.compile(r"\baccept|into (?:the|this) syndicate\b|take-on|taken on|\bassum", re.I)
TO_SYNDICATE = re.compile(r"(?:transferred|reinsured to close|closed)\s+(?:in)?to\s+(?:the\s+|this\s+)?"
                          r"syndicate\s*(\d{3,4})?", re.I)
FROM_SYNDICATE = re.compile(r"\bfrom\s+(?:syndicate\s*|s)(\d{3,4})\b", re.I)
SYND = re.compile(r"(?:\b[Ss]yndicates?\s+|\bS)(\d{3,4})\b")
MANAGEMENT = re.compile(r"management of|took on (?:the )?management|novat", re.I)
ROW = re.compile(r"(?:\bRITC\b|reinsurance\s+to\s+close)\s+(?:(?:take[\s-]*on|taken\s+on)"
                 r"(?:\s+(?:reserves|balances|provisions))?|adjustment|inwards?|from\s+(?:syndicate\s*|s)(\d{3,4}))"
                 r"|\binwards?\s+(?:RITC|reinsurance\s+to\s+close)"
                 r"|\breinsurance\s+of\s+new\s+liabilities"
                 r"|\btake[\s-]*on\s+(?:of\s+)?(?:reserves|balances)"
                 r"|\b(?:loss\s+)?portfolio\s+transfers?\b|\bLPTs?\b"
                 r"|(?P<rollforward>(?:\bRITC\b|reinsurance\s+to\s+close)\s+(?:accepted|received))", re.I)
JANUARY = re.compile(r"\b1(?:st)?\s+January\b", re.I)
OWN_YEARS = re.compile(r"\byears?\s+of\s+account\b", re.I)
#: the amount directly after a row's label: an optional footnote mark, then a figure with thousands separators or decimals
AMOUNT = re.compile(r"^\s*(?:[*¹²³]|\d(?=\s))?\s*\(?(?:\d{1,3}(?:,\d{3})+|\d+\.\d+)\)?")


def inward(w, syn):
    """Whether a passage describes business coming into this syndicate: an acceptance, a take-on, an assumption, a
    transfer or closure into the syndicate or into this syndicate's own number, or business from another syndicate."""
    if ACCEPTS.search(w):
        return True
    if any(m.group(1) is None or int(m.group(1)) == int(syn) for m in TO_SYNDICATE.finditer(w)):
        return True
    return any(int(m.group(1)) != int(syn) for m in FROM_SYNDICATE.finditer(w))


no_filing = []
for s in WS:
    key, syn, year = s.replace("syndicate_", ""), s.split("_")[1], int(s.split("_")[2])
    top = scan.get(key) or {}
    if top.get("ritc_occurred") is True and top.get("direction") == "inward" and top.get("event_year") == year:
        flag("scan", s, "RITC scan: an inward RITC in %d: %s" % (year, re.sub(r"\s+", " ", top.get("evidence") or "")[:240]))
    text = filing_text(s)
    if text is None:
        no_filing.append(s)
        continue
    for m in TRANSFER.finditer(text):
        a = text.rfind(". ", 0, m.start())
        b = text.find(". ", m.end())
        w = text[max(a + 2 if a >= 0 else 0, m.start() - 300): min(b + 1 if b >= 0 else len(text), m.end() + 300)]
        if (inward(w, syn) and re.search(r"\b%d\b" % year, w) and not MANAGEMENT.search(w)
                and ([n for n in SYND.findall(w) if int(n) != int(syn)] or re.search(r"portfolio\s+transfer|\bLPTs?\b", w, re.I))):
            flag("passage", s, "text: ...%s..." % w[:500])
            break
    for m in ROW.finditer(text):
        if m.group(1) and int(m.group(1)) == int(syn):
            continue
        if re.search(r"premium\s*$", text[max(0, m.start() - 12): m.start()], re.I):
            continue
        if m.group("rollforward") and (not JANUARY.search(text[max(0, m.start() - 300): m.start()])
                                       or OWN_YEARS.search(text[max(0, m.start() - 200): m.end() + 200])):
            continue
        amt = AMOUNT.match(text[m.end(): m.end() + 40])
        if amt:
            flag("row", s, "row: ...%s..." % text[max(0, m.start() - 120): m.end() + 160])
            break

listed = sorted({s for rule in RULES for s in hits[rule]})
missing = [d for d in DEFINERS if d not in listed]
if missing:
    raise SystemExit("the census does not list %s, the records that define it (in the working sample: %s): its rule is wrong"
                     % (missing, [d in WS for d in missing]))

# --- the carry-over skeleton --------------------------------------------------------------------------------------------
e_briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs-eighth.json") if "takeon_triangle" in b["census_parts"]}
e_first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-eighth.json")}
e_second = {v["stem"]: v for v in load(SCR / "error-rate-verification-eighth.json")}


def changed(old, new):
    why = []
    for field, label in ((ADOPTED, "adopted figure"), (OPENING, "opening reserves")):
        if old.get(field) is None or new.get(field) is None or abs(float(old[field]) - float(new[field])) > 1e-9:
            if old.get(field) != new.get(field):
                why.append("%s %s -> %s" % (label, old.get(field), new.get(field)))
    return why


skeleton = []
for s in listed:
    if s in e_briefs and s in e_first and s in e_second:
        f = (e_first[s].get("census_check") or {}).get("takeon_triangle") or {}
        g = (e_second[s].get("census_check") or {}).get("takeon_triangle") or {}
        skeleton.append({"stem": s, "eighth_census": True, "carry": None,
                         "changed_since": changed(e_briefs[s], briefs[s]),
                         "first": {"reader": e_first[s].get("first_reader"), "finding": f.get("finding"),
                                   "takeon_amount_m": f.get("takeon_amount_m"), "evidence": (f.get("evidence") or "")[:1500]},
                         "second": {"recorded": e_second[s].get("recorded"), "finding": g.get("finding"),
                                    "takeon_amount_m": g.get("takeon_amount_m"), "why": (e_second[s].get("why") or "")[:1500]}})
    else:
        skeleton.append({"stem": s, "eighth_census": False, "carry": False,
                         "why": "no earlier reading of the take-on base question"})

print("working sample %d (confirmed figures applied %d, confirmed openings %d, take-on bases %d); no filing PDF %d: %s"
      % (len(WS), counters["confirmed_figures_applied"], counters["confirmed_openings_applied"],
         counters["takeon_base_applied"], len(no_filing), no_filing))
for rule in RULES:
    print("rule %-8s listed %3d" % (rule, len(hits[rule])))
eighth = [x["stem"] for x in skeleton if x["eighth_census"]]
fresh = [x["stem"] for x in skeleton if not x["eighth_census"]]
print("listed %d: read in the eighth census's takeon_triangle part %d, to read afresh %d" % (len(listed), len(eighth), len(fresh)))
for s in listed:
    rules = [rule for rule in RULES if s in hits[rule]]
    first_reason = hits[rules[0]][s][0]
    b = briefs[s]
    print("  %-22s %-5s %-18s pyd %-10s open %-10s %s %s | %s" % (
        s, "8th" if s in eighth else "new", ",".join(rules), b[ADOPTED], b[OPENING], b["report_currency"],
        (b["route"] or {}).get("source"), first_reason[:170]))
if args.dry_run:
    sys.exit(0)

now = datetime.datetime.now().isoformat(timespec="seconds")
rules_doc = {rule: re.sub(r"\s+", " ", __doc__.split("  " + rule + " ", 1)[1].split("\n  ", 1)[0].split("\n\n", 1)[0]).strip()
             for rule in RULES}
io.open(str(OUT_CENSUS), "w", encoding="utf-8").write(json.dumps({
    "protocol": "error-rate-protocol.md, ninth amendment, written before this file",
    "written": now, "working_sample_n": len(WS),
    "loader_counters": {k: counters[k] for k in ("confirmed_figures_applied", "confirmed_openings_applied",
                                                 "takeon_base_applied", "takeon_excluded")},
    "rules": rules_doc, "definers": DEFINERS,
    "parts": {rule: {s: hits[rule][s] for s in sorted(hits[rule])} for rule in RULES},
    "stems": listed, "eighth_census_read": eighth, "fresh": fresh, "no_filing_pdf": no_filing}, indent=1, ensure_ascii=False))
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(
    [dict(briefs[s], census_parts=["takeon_base"], census_reasons={"takeon_base": [r for rule in RULES for r in hits[rule].get(s, [])]})
     for s in listed], indent=1, ensure_ascii=False))
io.open(str(OUT_CARRY), "w", encoding="utf-8").write(json.dumps(
    {"census": OUT_CENSUS.name, "rule": "ninth amendment, point 4", "decided_before_any_reading": True,
     "records": skeleton}, indent=1, ensure_ascii=False))
print("written %s (%s), %s, %s" % (OUT_CENSUS.name, now, OUT_BRIEFS.name, OUT_CARRY.name))
