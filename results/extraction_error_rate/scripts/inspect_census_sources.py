r"""Read-only: the structure of the census's two source lists, before the census file is written.

    python inspect_census_sources.py
"""
import io
import json
import os
import subprocess
import sys

WT = r"D:/Latex projects/BAJ - Lloyds reserves rescaling/.claude/worktrees/fixed-effects-syndicate-repeats-fff692"
sys.path.insert(0, os.path.join(WT, "paper"))
import claim_registry as CR  # noqa: E402

SCR = os.path.dirname(os.path.abspath(__file__))
AN = r"D:/dev/IME-Lloyds-exposure-composition"
EX = r"D:/dev/lloyds_reserve_stress_testing"

cur = json.load(io.open(os.path.join(AN, "model", "exposure_results.json"), encoding="utf-8"))
ws = {"%d_%d" % (o["syndicate"], o["year"]) for o in CR.working_sample_rows(cur["observations"])}
print("refit exposure_results run id %s; working sample %d" % (cur.get("analysis_run_id"), len(ws)))

r = subprocess.run(["git", "-C", EX, "show", "40eb31aa:pdf_extraction/audit/offline_unservable.json"], capture_output=True)
u = json.loads(r.stdout)
for k in ("purpose", "recorded", "round", "driver", "n_attempted", "n_unservable"):
    v = u.get(k)
    print("  %-14s %s" % (k, (json.dumps(v)[:300] if not isinstance(v, str) else v[:300])))
for k in ("stems", "unservable_in_this_replay"):
    v = u.get(k)
    if isinstance(v, list):
        items = [x.get("stem") if isinstance(x, dict) else x for x in v]
        print("  %-26s list of %d; first %s; example item %s" % (k, len(v), items[:3], json.dumps(v[0])[:300] if v else None))
    elif isinstance(v, dict):
        items = list(v)
        print("  %-26s dict of %d; first keys %s; example value %s" % (k, len(v), items[:3], json.dumps(v[items[0]])[:300] if v else None))
    else:
        items = []
        print("  %-26s %s" % (k, type(v).__name__))
    norm = {str(s).replace("syndicate_", "") for s in items}
    print("      in the working sample: %d %s" % (len(norm & ws), sorted(norm & ws)))

cm = os.path.join(SCR, "cohort-manifestations.json")
d = json.load(io.open(cm, encoding="utf-8"))
print("\ncohort-manifestations.json: %s, keys %s" % (type(d).__name__, list(d)[:12] if isinstance(d, dict) else len(d)))
text = json.dumps(d)
for s in ("3624_2015", "2007_2015"):
    i = text.find(s)
    print("  %s at %d: ...%s..." % (s, i, text[max(0, i - 200):i + 200] if i >= 0 else ""))

sa = json.load(io.open(os.path.join(SCR, "error-rate-sample-after.json"), encoding="utf-8"))
print("\nerror-rate-sample-after.json keys %s; primary keys %s" % (list(sa), list(sa.get("primary") or {})))
for k, v in sa.items():
    if k != "primary":
        print("  %s: %s" % (k, json.dumps(v)[:200]))
