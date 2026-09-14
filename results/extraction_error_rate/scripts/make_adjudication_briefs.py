r"""One brief per sampled record: exactly what the loader adopted, so an adjudicator checks that and nothing else.

The error-rate study scores the figure the loader uses. Re-deriving the loader's choice of model
block, its route and its basis decision by eye is where adjudications stop being comparable, so this
reads them: the canonical block the loader selects, its prior-year development and opening
reserves in the report's own currency (before FX conversion, as the filing prints them), the route
that produced the figure, the pages the extraction cited, and the basis and cohort scope the loader
recorded on the observation. It also records where the record's adjudication pack is.

Writes error-rate-briefs.json and six batch files of ten, in the order the sample lists the stems.
Read-only over the records.
"""
import copy
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402

sample = json.load(io.open(str(SCR / "error-rate-sample.json"), encoding="utf-8"))
stems = sample["primary"]["stems"]
cur = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}


def canonical(data):
    models = data.get("models") or {}
    keys = sorted(models)
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]


briefs = []
for stem in stems:
    key = stem.replace("syndicate_", "")
    data = json.load(io.open(str(AN / "pdf_extraction" / ("%s.json" % stem)), encoding="utf-8"))
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    route = cm.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    briefs.append({
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        "adopted_prior_year_development_m_report_currency": cm.get("prior_year_development_gbp_m"),
        "adopted_opening_reserves_m_report_currency": cm.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": {k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                             "triangle_units", "triangle_source_page", "note")},
        "cited_pages": {"prior_year_movement": cm.get("prior_year_movement_page"),
                        "opening_reserves": cm.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "model_notes": notes[:1500],
    })

io.open(str(SCR / "error-rate-briefs.json"), "w", encoding="utf-8").write(json.dumps(briefs, indent=1, ensure_ascii=False))
for b in range(6):
    part = briefs[b * 10:(b + 1) * 10]
    io.open(str(SCR / ("error-rate-briefs-batch-%d.json" % (b + 1))), "w", encoding="utf-8").write(
        json.dumps(part, indent=1, ensure_ascii=False))
print("briefs: %d; batches: 6 of %s" % (len(briefs), [len(briefs[b * 10:(b + 1) * 10]) for b in range(6)]))
print("currencies: %s" % sorted({b["report_currency"] for b in briefs}))
print("routes: %s" % sorted({str(b["route"]["source"]) for b in briefs}))
