r"""The take-on census (error-rate-protocol.md, sixth amendment): its records, their briefs and batches.

The records are computed, not typed: every working-sample record in the RITC regime (the refit's recorded sources,
assumed_business) whose adopted figure is a stated movement (score_error_rate.figure_source on its brief). Each brief
is built from the extraction repository's record, so a record the replay repair relabelled (2008/2021: now
rag_provisions) is read as it now stands; the adopted figure, which the loader took from the analysis copy, must be
the same in both. 2008/2021 keeps its second-sample first reading, which answers the census question; every other
record is read afresh, because the question is new.

Writes error-rate-census-takeon.json first, then error-rate-briefs-takeon.json, error-rate-fresh-stems-takeon.json
and batches of four. Packs:

    cd D:/dev/lloyds_reserve_stress_testing && python scripts/adjudication_pack.py \
        --stems <scratchpad>/error-rate-fresh-stems-takeon.json --out <scratchpad>/packs-error-rate-takeon

    python make_adjudication_briefs_takeon.py
"""
import copy
import datetime
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
WT = Path(r"D:/Latex projects/BAJ - Lloyds reserves rescaling/.claude/worktrees/fixed-effects-syndicate-repeats-fff692")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.path.insert(0, str(SCR))
sys.path.insert(0, str(WT / "paper"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402
import score_error_rate as ser  # noqa: E402
import claim_registry as CR  # noqa: E402

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
BATCH = 4
OUT_CENSUS = SCR / "error-rate-census-takeon.json"
OUT_BRIEFS = SCR / "error-rate-briefs-takeon.json"
CARRIED_FIRST = {"syndicate_2008_2021": "second sample"}


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
        raise SystemExit("%s exists; the take-on census is fixed once, before any reading" % p.name)
cur = load(AN / "model" / "exposure_results.json")
overruled = ser.overruled_stems()


def brief(o):
    key = "%d_%d" % (o["syndicate"], o["year"])
    stem = "syndicate_%s" % key
    data = load(EX / "pdf_extraction" / ("%s.json" % stem))
    analysis_copy = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = canonical(data)
    m = copy.deepcopy(data["models"][ck])
    a = analysis_copy["models"][canonical(analysis_copy)]
    if m.get("prior_year_development_gbp_m") != a.get("prior_year_development_gbp_m"):
        raise SystemExit("%s: the extraction record's adopted figure %s is not the analysis copy's %s"
                         % (stem, m.get("prior_year_development_gbp_m"), a.get("prior_year_development_gbp_m")))
    route = m.get("_pyd_route") or {}
    notes = m.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate-takeon" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        ADOPTED: m.get("prior_year_development_gbp_m"),
        OPENING: m.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": {k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                             "triangle_units", "triangle_source_page", "note")},
        "cited_pages": {"prior_year_movement": m.get("prior_year_movement_page"),
                        "opening_reserves": m.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "regime_sources": o["assumed_business"],
        "model_notes": notes[:1500],
    }


candidates = []
for o in CR.working_sample_rows(cur["observations"]):
    if not CR.regime_kind(o):
        continue
    b = brief(o)
    source = ser.figure_source(b, overruled)[0]
    candidates.append((b, source))
census = [b for b, source in candidates if source == "stated"]
stems = [b["stem"] for b in census]
io.open(str(OUT_CENSUS), "w", encoding="utf-8").write(json.dumps({
    "protocol": "error-rate-protocol.md, sixth amendment (13 September 2026), written before this file",
    "written": datetime.datetime.now().isoformat(timespec="seconds"),
    "exposure_results_run_id": cur.get("analysis_run_id"),
    "rule": "working-sample records in the RITC regime whose adopted figure is a stated movement, briefs from the "
            "extraction repository's records",
    "regime_records": len(candidates),
    "by_figure_source": {s: sum(1 for _b, x in candidates if x == s) for s in sorted({x for _b, x in candidates})},
    "stems": stems,
    "regime_sources": {b["stem"]: b["regime_sources"] for b in census},
}, indent=1))
fresh = [b for b in census if b["stem"] not in CARRIED_FIRST]
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(census, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-fresh-stems-takeon.json"), "w", encoding="utf-8").write(
    json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-takeon-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
print("regime records in the working sample %d; stated figures %d; read afresh %d in %d batch(es); carried %s"
      % (len(candidates), len(census), len(fresh), nb, sorted(set(stems) & set(CARRIED_FIRST))))
for b in census:
    print("  %-22s route %-16s adopted %-10s %s" % (b["stem"], b["route"]["source"], b[ADOPTED], b["regime_sources"]))
