r"""Briefs for the records found in passing (error-rate-protocol.md, seventh amendment, point 2).

The records are the four the amendment names, whose figures the read-only mapping of the extraction code could not
reconcile with their filings. Each is read twice, reported apart and never pooled. The briefs are built as the census
briefs are, from the analysis copies the refit read (the extraction records are identical for these four).

Writes error-rate-census-passing.json, error-rate-briefs-passing.json, error-rate-fresh-stems-passing.json and one
batch. Packs:

    cd D:/dev/lloyds_reserve_stress_testing && python scripts/adjudication_pack.py \
        --stems <scratchpad>/error-rate-fresh-stems-passing.json --out <scratchpad>/packs-error-rate-passing

    python make_adjudication_briefs_passing.py
"""
import copy
import datetime
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
STEMS = ["syndicate_1225_2022", "syndicate_623_2014", "syndicate_623_2022", "syndicate_1206_2014"]
OUT_CENSUS = SCR / "error-rate-census-passing.json"
OUT_BRIEFS = SCR / "error-rate-briefs-passing.json"


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
    if p.exists():
        raise SystemExit("%s exists" % p.name)
cur = load(AN / "model" / "exposure_results.json")
obs = {"syndicate_%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}
briefs = []
for stem in STEMS:
    key = stem.replace("syndicate_", "")
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    if load(EX / "pdf_extraction" / ("%s.json" % stem)) != data:
        raise SystemExit("%s: the extraction record differs from the analysis copy" % stem)
    ck = canonical(data)
    m = copy.deepcopy(data["models"][ck])
    route = m.get("_pyd_route") or {}
    o = obs.get(stem) or {}
    notes = m.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    briefs.append({
        "stem": stem, "report_year": int(key.split("_")[1]), "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate-passing" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"), "canonical_model": ck,
        ADOPTED: m.get("prior_year_development_gbp_m"), OPENING: m.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": {k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                             "triangle_units", "triangle_source_page", "note")},
        "cited_pages": {"prior_year_movement": m.get("prior_year_movement_page"),
                        "opening_reserves": m.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "model_notes": notes[:1500],
    })
io.open(str(OUT_CENSUS), "w", encoding="utf-8").write(json.dumps({
    "protocol": "error-rate-protocol.md, seventh amendment, point 2, written before this file",
    "written": datetime.datetime.now().isoformat(timespec="seconds"),
    "exposure_results_run_id": cur.get("analysis_run_id"), "stems": STEMS}, indent=1))
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(briefs, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-fresh-stems-passing.json"), "w", encoding="utf-8").write(json.dumps(STEMS, indent=1))
io.open(str(SCR / "error-rate-briefs-passing-batch-1.json"), "w", encoding="utf-8").write(
    json.dumps(briefs, indent=1, ensure_ascii=False))
for b in briefs:
    print("  %-22s route %-16s adopted %-10s basis %s" % (b["stem"], b["route"]["source"], b[ADOPTED], b["loader_basis"]))
