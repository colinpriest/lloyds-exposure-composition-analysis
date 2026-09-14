r"""The ninth amendment's point 4: the editor's carry-over decisions for the take-on base census, recorded before any
new reading, and the batches of the records read afresh.

The decisions file (a Python module) defines DECISIONS: {stem: dict}. Every record the census lists that the eighth
census read in its takeon_triangle part needs one. A carried record gives carry=True, a reason, and each earlier
reading's answer to the take-on base question as that reading states it: {"finding": True | False | None,
"takeon_amount_m": number or None, "gross_opening_m": number or None, "carried": "<where the reading says the business
sits>"} under "first" and "second". A record not carried gives carry=False and a reason; it is read afresh.

Writes error-rate-carry-over-ninth.json, error-rate-fresh-stems-ninth.json and error-rate-briefs-ninth-batch-N.json
(batches of five). Refuses if the carry-over file or any ninth-census batch or verdict file exists already, if a listed
eighth-census record has no decision, or if a decision names a record the census does not list.

    python record_carry_ninth.py carry_decisions_ninth.py
"""
import glob
import importlib.util
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
BATCH = 5
CARRY = SCR / "error-rate-carry-over-ninth.json"


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def need(cond, why):
    if not cond:
        raise SystemExit(why)


spec = importlib.util.spec_from_file_location("decisions", str(SCR / sys.argv[1]))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DECISIONS = mod.DECISIONS

need(not CARRY.exists(), "%s exists: the carry-over is decided once, before any new reading" % CARRY.name)
need(not glob.glob(str(SCR / "error-rate-briefs-ninth-batch-*.json")) and not glob.glob(str(SCR / "error-rate-verdicts-ninth-batch-*.json")),
     "ninth-census batches or verdicts exist already")
census = load(SCR / "error-rate-census-ninth.json")
skeleton = {r["stem"]: r for r in load(SCR / "error-rate-carry-over-ninth-skeleton.json")["records"]}
briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs-ninth.json")}
need(set(skeleton) == set(census["stems"]) == set(briefs), "the census, its skeleton and its briefs list different records")
unknown = sorted(set(DECISIONS) - set(skeleton))
need(not unknown, "decisions for records the census does not list: %s" % unknown)
eighth = sorted(s for s, r in skeleton.items() if r["eighth_census"])
undecided = [s for s in eighth if s not in DECISIONS]
need(not undecided, "eighth-census records without a decision: %s" % undecided)

ANSWER = {"finding", "takeon_amount_m", "gross_opening_m", "carried"}
decisions = []
for s in sorted(skeleton):
    if not skeleton[s]["eighth_census"]:
        need(s not in DECISIONS or DECISIONS[s].get("carry") is False,
             "%s: the eighth census did not read it, so it cannot be carried" % s)
        decisions.append({"stem": s, "carry": False, "why": "no earlier reading of the take-on base question"})
        continue
    d = DECISIONS[s]
    need(isinstance(d.get("carry"), bool) and str(d.get("reason") or "").strip(), "%s: carry (True or False) and a reason" % s)
    row = {"stem": s, "carry": d["carry"], "why": d["reason"], "changed_since": skeleton[s]["changed_since"]}
    if d["carry"]:
        for which in ("first", "second"):
            ans = d.get(which) or {}
            need(set(ans) == ANSWER, "%s: the %s reading's answer needs exactly %s" % (s, which, sorted(ANSWER)))
            need(ans["finding"] in (True, False, None), "%s: the %s reading's finding must be True, False or None" % (s, which))
            for k in ("takeon_amount_m", "gross_opening_m"):
                need(ans[k] is None or isinstance(ans[k], (int, float)), "%s: %s %s must be a number or None" % (s, which, k))
            row[which] = ans
        row["first_reader"] = skeleton[s]["first"]["reader"]
        row["second_recorded"] = skeleton[s]["second"]["recorded"]
    decisions.append(row)

fresh = [s for s in sorted(skeleton) if not next(x for x in decisions if x["stem"] == s)["carry"]]
io.open(str(CARRY), "w", encoding="utf-8").write(json.dumps(
    {"census": "error-rate-census-ninth.json", "rule": "ninth amendment, point 4", "decided_before_any_reading": True,
     "decisions": decisions}, indent=1, ensure_ascii=False))
io.open(str(SCR / "error-rate-fresh-stems-ninth.json"), "w", encoding="utf-8").write(json.dumps(fresh, indent=1))
nb = (len(fresh) + BATCH - 1) // BATCH
for i in range(nb):
    io.open(str(SCR / ("error-rate-briefs-ninth-batch-%d.json" % (i + 1))), "w", encoding="utf-8").write(
        json.dumps([briefs[s] for s in fresh[i * BATCH:(i + 1) * BATCH]], indent=1, ensure_ascii=False))
carried = [x["stem"] for x in decisions if x["carry"]]
print("carried %d: %s" % (len(carried), carried))
print("read afresh %d in %d batch(es): %s" % (len(fresh), nb, fresh))
