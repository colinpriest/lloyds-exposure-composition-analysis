r"""Briefs for the records the fifth amendment has read after the repairs, and the carry-over decision.

Three groups, each tagged in its brief:
  * third: the 110 drawn from A (error-rate-sample-third.json), a simple random sample with the second sample's 60;
  * entrant: every record of E, the rebuilt working sample's records the second sample's population did not hold
    (a census stratum, read in full);
  * repaired: every record of the second sample or the census whose verdict was read against something a repair
    changed (the adopted figure, the opening reserves, the figure's source, the basis or the cohort scope), read
    again from its filing (third amendment, second case; fifth amendment, point 2).
A third or entrant record that an earlier sample or the census read keeps those readings when nothing its verdict
was read against has changed (fourth amendment, point 3). Everything else is read afresh, in batches of ten.

Writes error-rate-briefs-third.json, error-rate-carry-over-third.json, error-rate-fresh-stems-third.json and
error-rate-briefs-third-batch-N.json. Packs:

    cd D:/dev/lloyds_reserve_stress_testing && python scripts/adjudication_pack.py \
        --stems <scratchpad>/error-rate-fresh-stems-third.json --out <scratchpad>/packs-error-rate-third

Read-only over the records.

    python make_adjudication_briefs_third.py
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
OUT_BRIEFS = SCR / "error-rate-briefs-third.json"


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
    raise SystemExit("%s exists; the carry-over is decided once, before any reading" % OUT_BRIEFS.name)
third = load(SCR / "error-rate-sample-third.json")
cur = load(AN / "model" / "exposure_results.json")
if cur.get("analysis_run_id") != third["exposure_results_run_id"]:
    raise SystemExit("exposure_results.json is not the run the third sample was drawn from")
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in cur["observations"]}


# the figure the loader adopts: for the records in data/pyd_confirmed_figures.json the confirmed figure replaces the
# record's, applied by run_analysis.apply_confirmed_figure exactly as load_and_classify applies it (implementation
# note in error-rate-protocol.md, before the third sample was drawn)
CONFIRMED = ra.load_pyd_confirmed_figures()


def brief(stem, role):
    key = stem.replace("syndicate_", "")
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    ck = canonical(data)
    cm = copy.deepcopy(data["models"][ck])
    if key in CONFIRMED:
        cm = ra.apply_confirmed_figure(cm, CONFIRMED[key])
    route = cm.get("_pyd_route") or {}
    o = obs.get(key) or {}
    notes = cm.get("data_quality_notes") or ""
    notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
    return {
        "stem": stem, "role": role,
        "report_year": int(key.split("_")[1]),
        "syndicate": key.split("_")[0],
        "filing_pdf": "D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf" % stem,
        "pack": str(SCR / "packs-error-rate-third" / ("%s.txt" % stem)),
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


overruled = ser.overruled_stems()


def changes(old, new):
    why = []
    if not same_number(old[ADOPTED], new[ADOPTED]):
        why.append("adopted figure %s -> %s" % (old[ADOPTED], new[ADOPTED]))
    if not same_number(old[OPENING], new[OPENING]):
        why.append("opening reserves %s -> %s" % (old[OPENING], new[OPENING]))
    if ser.figure_source(old, overruled)[0] != ser.figure_source(new, overruled)[0]:
        why.append("figure source %s -> %s" % (ser.figure_source(old, overruled)[0], ser.figure_source(new, overruled)[0]))
    if (old["loader_basis"] or [None])[0] != (new["loader_basis"] or [None])[0]:
        why.append("basis %s -> %s" % (old["loader_basis"], new["loader_basis"]))
    if (old["loader_cohort_scope"] or [None])[0] != (new["loader_cohort_scope"] or [None])[0]:
        why.append("cohort scope %s -> %s" % (old["loader_cohort_scope"], new["loader_cohort_scope"]))
    return why


# the readings a record may already have, latest first
PRIOR = (("census", load(SCR / "error-rate-census.json")["stems"],
          {b["stem"]: b for b in load(SCR / "error-rate-briefs-census.json")}),
         ("second sample", load(SCR / "error-rate-sample-after.json")["primary"]["stems"],
          {b["stem"]: b for b in load(SCR / "error-rate-briefs-after.json")}),
         ("first sample", load(SCR / "error-rate-sample.json")["primary"]["stems"],
          {b["stem"]: b for b in load(SCR / "error-rate-briefs.json")}))

# the working sample is what adopted_model.load_sample retains, the draw's own source: every parsed observation would
# also hold a record the take-on register keeps in the corpus but not in the working sample (2008/2021)
import adopted_model  # noqa: E402

_S, _R, _H, _yr, _syn, _ritc = adopted_model.load_sample()
in_ws = {"%s_%s" % (s, y) for s, y in zip(_syn, _yr)}
if len(in_ws) != third["rebuilt_working_sample_n"]:
    raise SystemExit("the working sample holds %d records; the draw was taken from %d"
                     % (len(in_ws), third["rebuilt_working_sample_n"]))
briefs, decisions = [], []
for s in third["third"]["stems"]:
    briefs.append(brief(s, "third"))
for s in third["E_entrants"]["stems"]:
    briefs.append(brief(s, "entrant"))
# repaired: second-sample and census records still in the working sample whose read-against fields changed
for name, stems, old in PRIOR[:2]:
    for s in stems:
        if s.replace("syndicate_", "") not in in_ws or any(b["stem"] == s for b in briefs):
            continue
        new = brief(s, "repaired")
        why = changes(old[s], new)
        if why:
            new["repaired_why"] = why
            briefs.append(new)
for b in briefs:
    s = b["stem"]
    if b["role"] == "repaired":
        decisions.append({"stem": s, "role": "repaired", "carry_over": False, "carried_from": None,
                          "why": ["read again after a repair: " + "; ".join(b["repaired_why"])]})
        continue
    held = next((p for p in PRIOR if s in p[1]), None)
    if held is None:
        decisions.append({"stem": s, "role": b["role"], "carry_over": False, "carried_from": None,
                          "why": ["no earlier sample or census holds it"]})
        continue
    name, _stems, old = held
    why = changes(old[s], b)
    decisions.append({"stem": s, "role": b["role"], "carry_over": not why, "carried_from": name if not why else None,
                      "why": why or ["read in the %s; nothing its verdict was read against changed" % name]})

fresh = [b for b, d in zip(briefs, decisions) if not d["carry_over"]]
io.open(str(OUT_BRIEFS), "w", encoding="utf-8").write(json.dumps(briefs, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-carry-over-third.json"), "w", encoding="utf-8").write(json.dumps(
    {"sample": "error-rate-sample-third.json", "rule": "fourth amendment, point 3; third amendment, second case; "
     "fifth amendment, points 2 and 3", "decided_before_any_reading": True, "decisions": decisions}, indent=1))
io.open(str(SCR / "error-rate-fresh-stems-third.json"), "w", encoding="utf-8").write(
    json.dumps([b["stem"] for b in fresh], indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-third-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps(fresh[i * BATCH:(i + 1) * BATCH], indent=1, ensure_ascii=False))
roles = {r: sum(1 for b in briefs if b["role"] == r) for r in ("third", "entrant", "repaired")}
print("briefs %d %s; carried over %d; read afresh %d in %d batch(es)"
      % (len(briefs), roles, sum(1 for d in decisions if d["carry_over"]), len(fresh), nb))
for d in decisions:
    if d["role"] != "third" or d["carry_over"]:
        print("  %-22s %-9s carry over %-5s %s" % (d["stem"], d["role"], d["carry_over"], "; ".join(d["why"])))
