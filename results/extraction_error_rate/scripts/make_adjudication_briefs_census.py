r"""Briefs for the census of the two error mechanisms (error-rate-protocol.md, fifth amendment, point 1), and the
carry-over decision.

The census is purposive and never pooled with a random sample. Its records are computed from the committed lists,
not typed:
  * replay stopped: the working-sample records in pdf_extraction/audit/offline_unservable.json's `stems` (every
    report not servable offline now) at extraction commit 40eb31aa;
  * aggregated older cohort omitted: the working-sample records that cohort-manifestations.json (the round-56 check)
    lists with an adopted figure equal to a cohort table's triangle without the cohort (adopted_matches "without").
The working sample is the refit's model/exposure_results.json under claim_registry's predicate, and it must hold the
second sample's population (the same size, and the same run id where the sample file records one).

A record either sample read keeps its readings when nothing its verdict was read against has changed (fourth
amendment, point 3). Writes error-rate-census.json first, then error-rate-briefs-census.json,
error-rate-carry-over-census.json, error-rate-fresh-stems-census.json and batches of four. Packs for the fresh
records come from the extraction repository:

    cd D:/dev/lloyds_reserve_stress_testing && python scripts/adjudication_pack.py \
        --stems <scratchpad>/error-rate-fresh-stems-census.json --out <scratchpad>/packs-error-rate-census

Read-only over the records.

    python make_adjudication_briefs_census.py
"""
import copy
import datetime
import io
import json
import subprocess
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
OUT_CENSUS = SCR / "error-rate-census.json"
OUT_BRIEFS = SCR / "error-rate-briefs-census.json"


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
        raise SystemExit("%s exists; the census is fixed once, before any census reading" % p.name)
cur = load(AN / "model" / "exposure_results.json")
after = load(SCR / "error-rate-sample-after.json")
ws = {"%s_%s" % (o["syndicate"], o["year"]) for o in CR.working_sample_rows(cur["observations"])}
if len(ws) != after["population"]["n"]:
    raise SystemExit("the working sample holds %d records; the second sample's population held %d"
                     % (len(ws), after["population"]["n"]))
pop_run = after["population"].get("analysis_run_id") or after["population"].get("exposure_results_run_id")
if pop_run and pop_run != cur.get("analysis_run_id"):
    raise SystemExit("exposure_results.json is run %s; the second sample was drawn from %s" % (cur.get("analysis_run_id"), pop_run))
if not all(s.replace("syndicate_", "") in ws for s in after["primary"]["stems"]):
    raise SystemExit("a second-sample record is not in the working sample")

r = subprocess.run(["git", "-C", str(EX), "show", "40eb31aa:pdf_extraction/audit/offline_unservable.json"],
                   capture_output=True)
if r.returncode:
    raise SystemExit("offline_unservable.json is not at extraction 40eb31aa")
unserv = json.loads(r.stdout.decode("utf-8"))
replay = sorted(s for s in unserv["stems"] if s.replace("syndicate_", "") in ws)
cm = load(SCR / "cohort-manifestations.json")
cohort = sorted({x["stem"] for x in cm["cohort_tables"]
                 if x.get("adopted_matches") == "without" and x["stem"].replace("syndicate_", "") in ws})
stems = sorted(set(replay) | set(cohort))
census = {
    "protocol": "error-rate-protocol.md, fifth amendment (13 September 2026), point 1, written before this file",
    "written": datetime.datetime.now().isoformat(timespec="seconds"),
    "exposure_results_run_id": cur.get("analysis_run_id"),
    "working_sample_n": len(ws),
    "mechanisms": {
        "replay_stopped": {
            "source": "pdf_extraction/audit/offline_unservable.json at extraction 40eb31aa: its stems (every report "
                      "not servable offline now), in the working sample",
            "stems": replay},
        "aggregated_older_cohort_omitted": {
            "source": "cohort-manifestations.json (the round-56 check): cohort_tables rows whose adopted figure equals "
                      "the triangle without the aggregated cohort, in the working sample",
            "stems": cohort,
            "coverage": "the check read the tables of %d of the %d collected reports; %d have no table cache"
                        % (cm["records"] - cm["without_table_cache"], cm["records"], cm["without_table_cache"])}},
    "stems": stems,
}
io.open(str(OUT_CENSUS), "w", encoding="utf-8").write(json.dumps(census, indent=1))
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}


def brief(stem):
    key = stem.replace("syndicate_", "")
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = canonical(data)
    cm_ = copy.deepcopy(data["models"][ck])
    route = cm_.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm_.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate-census" / ("%s.txt" % stem)),
        "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
        "canonical_model": ck,
        ADOPTED: cm_.get("prior_year_development_gbp_m"),
        OPENING: cm_.get("opening_reserves_gbp_m"),
        "sign_convention": "positive = deterioration (strengthening), negative = release",
        "route": {k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                             "triangle_units", "triangle_source_page", "note")},
        "cited_pages": {"prior_year_movement": cm_.get("prior_year_movement_page"),
                        "opening_reserves": cm_.get("opening_reserves_page")},
        "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
        "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
        "model_notes": notes[:1500],
    }


def same_number(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) <= 1e-9


briefs = [brief(s) for s in stems]
overruled = ser.overruled_stems()
PRIOR = (("second sample", after["primary"]["stems"],
          {b["stem"]: b for b in load(SCR / "error-rate-briefs-after.json")},
          {r_["stem"]: r_["figure_source"] for r_ in load(SCR / "error-rate-verdicts-after.json")}),
         ("first sample", load(SCR / "error-rate-sample.json")["primary"]["stems"],
          {b["stem"]: b for b in load(SCR / "error-rate-briefs.json")},
          {r_["stem"]: r_["figure_source"] for r_ in load(SCR / "error-rate-verdicts.json")}))

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
io.open(str(SCR / "error-rate-carry-over-census.json"), "w", encoding="utf-8").write(json.dumps(
    {"census": "error-rate-census.json", "rule": "error-rate-protocol.md, fourth amendment, point 3, applied to the census",
     "decided_before_any_census_reading": True, "decisions": decisions}, indent=1))
io.open(str(SCR / "error-rate-fresh-stems-census.json"), "w", encoding="utf-8").write(
    json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-census-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
print("census: replay stopped %s; aggregated cohort omitted %s" % (replay, cohort))
print("coverage: %s" % census["mechanisms"]["aggregated_older_cohort_omitted"]["coverage"])
print("%d records; carried over %d; read afresh %d in %d batch(es)"
      % (len(briefs), sum(1 for d in decisions if d["carry_over"]), len(fresh), nb))
for d in decisions:
    print("  %-22s carry over %-5s %s" % (d["stem"], d["carry_over"], "; ".join(d["why"])))
