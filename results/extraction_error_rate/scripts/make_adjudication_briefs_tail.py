r"""Briefs for the error-rate study's tail stratum, and the carry-over decision (protocol, amendment point 3; fourth amendment, point 3).

The tail is error-rate-tail.json: the 20 largest Vignette-1 transferred severities, computed after the refit
(draw_error_rate_tail.py). A tail record is read once. A record the second sample also holds keeps that
sample's readings, and a record only the first sample holds keeps the first sample's, provided nothing its
verdict was read against has changed. The comparison is the fourth amendment's: the adopted figure, the
opening reserves, the figure's source, the basis and the cohort scope. It reads no verdict to decide. Every
other tail record is read afresh.

Writes error-rate-briefs-tail.json (all 20), error-rate-carry-over-tail.json (the decision and its reasons),
error-rate-fresh-stems-tail.json, and batch files of ten (error-rate-briefs-tail-batch-N.json) for the records
read afresh. Packs for those are written by the extraction repository's pack generator:

    cd D:/dev/lloyds_reserve_stress_testing && python scripts/adjudication_pack.py \
        --stems <scratchpad>/error-rate-fresh-stems-tail.json --out <scratchpad>/packs-error-rate-tail

Read-only over the records.

    python make_adjudication_briefs_tail.py
"""
import copy
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402
import score_error_rate as ser  # noqa: E402

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
BATCH = 10
OUT_BRIEFS = SCR / "error-rate-briefs-tail.json"


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


if OUT_BRIEFS.exists():
    raise SystemExit("%s exists; the carry-over is decided once, before any tail reading" % OUT_BRIEFS.name)
tail = load(SCR / "error-rate-tail.json")
stems = tail["tail"]["stems"]
cur = load(AN / "model" / "exposure_results.json")
if cur.get("analysis_run_id") != tail["exposure_results_run_id"]:
    raise SystemExit("exposure_results.json is not the run the tail was computed from")
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}
# the figure and the opening reserves the loader adopts: its registers are applied as load_and_classify applies them
# (implementation note 3; implementation note 1 did the same for the third sample), the take-on base after the confirmed
# opening reserves (ninth amendment, point 6)
CONFIRMED = ra.load_pyd_confirmed_figures()
OPENINGS = ra.load_opening_reserves_confirmed()
BASE = ra.load_takeon_base()
PDFS = Path(r"D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs")
CONVERTED = Path(r"D:/dev/lloyds_reserve_stress_testing/pdf_extraction/html_converted")


def filing_pdf(stem):
    """The PDF the packs' page numbers refer to (filing_pages.py): the filed PDF, else the HTML report's conversion."""
    for d in (PDFS, CONVERTED):
        if (d / ("%s.pdf" % stem)).exists():
            return str(d / ("%s.pdf" % stem))
    return None


def brief(stem):
    key = stem.replace("syndicate_", "")
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    if key in CONFIRMED:
        cm = ra.apply_confirmed_figure(cm, CONFIRMED[key])
    if key in OPENINGS:
        cm = ra.apply_confirmed_opening(cm, OPENINGS[key])
    if key in BASE:
        cm = ra.apply_takeon_base(cm, BASE[key])
    route = cm.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": filing_pdf(stem),
        "pack": str(SCR / "packs-error-rate-tail" / ("%s.txt" % stem)),
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
        "model_notes": notes[:1500],
    }


def same_number(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) <= 1e-9


briefs = [brief(s) for s in stems]
overruled = ser.overruled_stems()
# every sample and census a tail record may have been read in, latest first: its briefs and its merged rows (for the
# figure source); the fourth amendment's rule (point 3) applied to all of them (implementation note 3). The take-on base
# census is not one: its fresh first readings were neither clarified nor scored, and its carried readings are the
# eighth census's, which is here (implementation note 5)
READ_SETS = (("eighth census", "error-rate-briefs-eighth.json", "error-rate-verdicts-eighth.json"),
             ("third sample", "error-rate-briefs-third.json", "error-rate-verdicts-third.json"),
             ("take-on census", "error-rate-briefs-takeon.json", "error-rate-verdicts-takeon.json"),
             ("found in passing", "error-rate-briefs-passing.json", "error-rate-verdicts-passing.json"),
             ("census", "error-rate-briefs-census.json", "error-rate-verdicts-census.json"),
             ("second sample", "error-rate-briefs-after.json", "error-rate-verdicts-after.json"),
             ("first sample", "error-rate-briefs.json", "error-rate-verdicts.json"))
PRIOR = []
for _name, _briefs, _merged in READ_SETS:
    if (SCR / _briefs).exists() and (SCR / _merged).exists():
        _b = {b["stem"]: b for b in load(SCR / _briefs)}
        _src = {r["stem"]: r["figure_source"] for r in load(SCR / _merged)}
        PRIOR.append((_name, sorted(set(_b) & set(_src)), _b, _src))

decisions = []
for b in briefs:
    s = b["stem"]
    new_source = ser.figure_source(b, overruled)[0]
    held = next((p for p in PRIOR if s in p[1]), None)
    if held is None:
        decisions.append({"stem": s, "carry_over": False, "carried_from": None, "figure_source": new_source,
                          "why": ["neither primary sample holds it"]})
        continue
    name, _stems, old_briefs, old_source = held
    ob = old_briefs[s]
    why = []
    if not same_number(ob[ADOPTED], b[ADOPTED]):
        why.append("adopted figure %s -> %s" % (ob[ADOPTED], b[ADOPTED]))
    if not same_number(ob[OPENING], b[OPENING]):
        why.append("opening reserves %s -> %s" % (ob[OPENING], b[OPENING]))
    if old_source[s] != new_source:
        why.append("figure source %s -> %s" % (old_source[s], new_source))
    if (ob["loader_basis"] or [None])[0] != (b["loader_basis"] or [None])[0]:
        why.append("basis %s -> %s" % (ob["loader_basis"], b["loader_basis"]))
    if (ob["loader_cohort_scope"] or [None])[0] != (b["loader_cohort_scope"] or [None])[0]:
        why.append("cohort scope %s -> %s" % (ob["loader_cohort_scope"], b["loader_cohort_scope"]))
    decisions.append({"stem": s, "carry_over": not why, "carried_from": name if not why else None,
                      "figure_source": new_source,
                      "why": why or ["read in the %s; nothing its verdict was read against changed" % name]})

fresh = [b for b, d in zip(briefs, decisions) if not d["carry_over"]]
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(briefs, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-carry-over-tail.json"), "w", encoding="utf-8").write(json.dumps(
    {"sample": "error-rate-tail.json", "rule": "error-rate-protocol.md, fourth amendment, point 3, applied to the tail",
     "decided_before_any_tail_reading": True, "decisions": decisions}, indent=1))
io.open(str(SCR / "error-rate-fresh-stems-tail.json"), "w", encoding="utf-8").write(
    json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-tail-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
print("tail %d; carried over %d (%s); read afresh %d in %d batch(es)"
      % (len(briefs), sum(1 for d in decisions if d["carry_over"]),
         {k: sum(1 for d in decisions if d["carried_from"] == k) for k, _b, _m in READ_SETS},
         len(fresh), nb))
for d in decisions:
    print("  %-22s carry over %-5s %s" % (d["stem"], d["carry_over"], "; ".join(d["why"])))
