r"""Read-only: which errors the first sample confirmed are still in the working sample the refit fitted, unrepaired.

The first sample was scored on the extraction before R209 and R210, and the fourth amendment redrew rather than
repairing its errors. A verdict depends only on the adopted figure and the filing (third amendment), so an error
persists when the record is still in the working sample with the same adopted figure. For each first-sample final
error this prints the first sample's adopted and filing figures, the current adopted figure (the analysis copy the
refit read), whether it is still in the working sample, and whether the second sample or a census also holds it.

    python persisting_first_sample_errors.py
"""
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
WT = Path(r"D:/Latex projects/BAJ - Lloyds reserves rescaling/.claude/worktrees/fixed-effects-syndicate-repeats-fff692")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(WT / "paper"))
import claim_registry as CR  # noqa: E402


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


first_final = load(SCR / "error-rate-result.json")["rules"]["clarified"]["final_verdicts"]
first_rows = {r["stem"]: r for r in load(SCR / "error-rate-verdicts.json")}
first_second = {r["stem"]: r for r in load(SCR / "error-rate-verification.json")}
first_briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs.json")}
second = set(load(SCR / "error-rate-sample-after.json")["primary"]["stems"])
census = set(load(SCR / "error-rate-census.json")["stems"]) | set(load(SCR / "error-rate-census-takeon.json")["stems"])
obs = load(AN / "model" / "exposure_results.json")["observations"]
ws = {"syndicate_%d_%d" % (o["syndicate"], o["year"]) for o in CR.working_sample_rows(obs)}

persisting = []
for s, v in sorted(first_final.items()):
    if v != "error":
        continue
    data = load(AN / "pdf_extraction" / ("%s.json" % s))
    now = data["models"][canonical(data)].get("prior_year_development_gbp_m") if data.get("models") else None
    then = first_briefs[s]["adopted_prior_year_development_m_report_currency"]
    filing = (first_second.get(s) or {}).get("filing_figure_m")
    filing = filing if filing is not None else first_rows[s].get("filing_figure_m")
    same = now is not None and then is not None and abs(float(now) - float(then)) < 1e-9
    row = {"stem": s, "adopted_then": then, "adopted_now": now, "filing": filing, "in_working_sample": s in ws,
           "same_figure": same, "in_second_sample": s in second, "in_a_census": s in census,
           "kind": (first_second.get(s) or {}).get("error_kind") or first_rows[s].get("error_kind")}
    print("  %-22s then %-10s now %-10s filing %-9s in WS %-5s same %-5s second %-5s census %-5s kind %s"
          % (s, then, now, filing, row["in_working_sample"], same, row["in_second_sample"], row["in_a_census"], row["kind"]))
    if row["in_working_sample"] and same:
        persisting.append(row)
print("first-sample errors: %d; still in the working sample with the same figure: %d %s"
      % (sum(1 for v in first_final.values() if v == "error"), len(persisting), [r["stem"] for r in persisting]))
io.open(str(SCR / "persisting-first-sample-errors.json"), "w", encoding="utf-8").write(json.dumps(persisting, indent=1))
