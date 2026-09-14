r"""Briefs for the error-rate study's new sample, and the carry-over decision (protocol, fourth amendment, points 3 and 4).

For each of the 60 records in error-rate-sample-after.json this writes a brief exactly as
make_adjudication_briefs.py did for the first sample: the loader's canonical block, its adopted figure
and opening reserves in the report's own currency, the route, the cited pages, the basis and cohort scope
the loader records, and the pack path (packs-error-rate-after/).

Then it decides, for every record the first sample also held, whether its readings carry over. It
compares what the verdict was read against, and nothing else: the adopted figure, the opening reserves,
the figure's source (score_error_rate.figure_source on the new brief, against the source the first merge
recorded), the basis and the cohort scope. It reads no verdict to decide. A record whose comparison holds
keeps its first, clarified and second readings. Every other record, and every record the first sample did
not hold, is read afresh.

Writes error-rate-briefs-after.json (all 60), error-rate-carry-over.json (the decision and its reasons),
error-rate-fresh-stems.json, and batch files of ten (error-rate-briefs-after-batch-N.json) for the
records read afresh, in sample order. Read-only over the records.

    python make_adjudication_briefs_after.py
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


sample = load(SCR / "error-rate-sample-after.json")
stems = sample["primary"]["stems"]
cur = load(AN / "model" / "exposure_results.json")
if cur.get("analysis_run_id") != sample["population"]["exposure_results_run_id"]:
    raise SystemExit("exposure_results.json is not the run the new sample was drawn from")
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}


def brief(stem):
    key = stem.replace("syndicate_", "")
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    route = cm.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate-after" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        ADOPTED: cm.get("prior_year_development_gbp_m"),
        OPENING: cm.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": {k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                             "triangle_units", "triangle_source_page", "note")},
        "cited_pages": {"prior_year_movement": cm.get("prior_year_movement_page"),
                        "opening_reserves": cm.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "model_notes": notes[:1500],
    }


def same_number(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) <= 1e-9


briefs = [brief(s) for s in stems]
first_stems = set(load(SCR / "error-rate-sample.json")["primary"]["stems"])
old_briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs.json")}
old_source = {r["stem"]: r["figure_source"] for r in load(SCR / "error-rate-verdicts.json")}
overruled = ser.overruled_stems()

decisions = []
for b in briefs:
    s = b["stem"]
    new_source = ser.figure_source(b, overruled)[0]
    if s not in first_stems:
        decisions.append({"stem": s, "carry_over": False, "figure_source": new_source,
                          "why": ["the first sample did not hold it"]})
        continue
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
    decisions.append({"stem": s, "carry_over": not why, "figure_source": new_source,
                      "why": why or ["nothing its verdict was read against changed"]})

fresh = [b for b, d in zip(briefs, decisions) if not d["carry_over"]]
io.open(str(SCR / "error-rate-briefs-after.json"), "w", encoding="utf-8").write(
    json.dumps(briefs, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-carry-over.json"), "w", encoding="utf-8").write(json.dumps(
    {"sample": "error-rate-sample-after.json", "rule": "error-rate-protocol.md, fourth amendment, point 3",
     "decided_before_any_new_reading": True, "decisions": decisions}, indent=1))
io.open(str(SCR / "error-rate-fresh-stems.json"), "w", encoding="utf-8").write(
    json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-after-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
both = [d for d in decisions if d["stem"] in first_stems]
print("new sample %d; also in the first sample %d; carried over %d; read afresh %d in %d batch(es)"
      % (len(briefs), len(both), sum(1 for d in decisions if d["carry_over"]), len(fresh), nb))
for d in both:
    print("  %-22s carry over %-5s %s" % (d["stem"], d["carry_over"], "; ".join(d["why"])))
print("figure source in the new sample: %s" % {src: sum(1 for d in decisions if d["figure_source"] == src)
                                              for src in ("triangle", "stated")})
print("currencies: %s; routes: %s" % (sorted({b["report_currency"] for b in briefs}),
                                     sorted({str(b["route"]["source"]) for b in briefs})))
