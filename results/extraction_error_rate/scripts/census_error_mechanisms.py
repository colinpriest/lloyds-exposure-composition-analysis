r"""Read-only: how many working-sample records share the two error mechanisms the random sample found.

1. 2008/2021's: the offline replay stops at a response the caches do not hold, so the record keeps an earlier
   extraction's figure. The extraction repository enumerates those stems in
   pdf_extraction/audit/offline_unservable.json.
2. 3624/2015's: an adopted figure summed from a triangle that omits the filing's aggregated older cohort. The
   round-56 scan found it where the deterministic triangle is refused and the extraction models' own triangle
   decides; this lists the working-sample records whose adopted route is a model triangle, the population that
   mechanism can reach, and names 3624/2015 and 2007/2015.

The working sample is the refit's model/exposure_results.json under claim_registry's predicate.

    python census_error_mechanisms.py
"""
import collections
import io
import json
import os
import sys

WT = r"D:/Latex projects/BAJ - Lloyds reserves rescaling/.claude/worktrees/fixed-effects-syndicate-repeats-fff692"
sys.path.insert(0, os.path.join(WT, "paper"))
import claim_registry as CR  # noqa: E402

ANALYSIS = r"D:/dev/IME-Lloyds-exposure-composition"
EXTRACTION = r"D:/dev/lloyds_reserve_stress_testing"
obs = json.load(io.open(os.path.join(ANALYSIS, "model", "exposure_results.json"), encoding="utf-8"))["observations"]
ws = CR.working_sample_rows(obs)
ws_stems = {"%d_%d" % (o["syndicate"], o["year"]) for o in ws}
print("working sample: %d records" % len(ws))

rec = json.load(io.open(os.path.join(EXTRACTION, "pdf_extraction", "audit", "offline_unservable.json"), encoding="utf-8"))
print("offline_unservable.json: %s, top-level keys %s" % (type(rec).__name__, list(rec)[:8] if isinstance(rec, dict) else "-"))
stems = set()
if isinstance(rec, dict):
    for k, v in rec.items():
        if isinstance(v, list):
            for x in v:
                s = x.get("stem") if isinstance(x, dict) else x
                if isinstance(s, str):
                    stems.add(s.replace("syndicate_", ""))
        elif isinstance(v, dict) and k not in ("_meta", "meta"):
            for s in v:
                stems.add(str(s).replace("syndicate_", ""))
elif isinstance(rec, list):
    for x in rec:
        s = x.get("stem") if isinstance(x, dict) else x
        stems.add(str(s).replace("syndicate_", ""))
print("unservable stems listed: %d; in the working sample: %d %s"
      % (len(stems), len(stems & ws_stems), sorted(stems & ws_stems)[:30]))

routes = collections.Counter(str(o.get("pyd_cohort_route")) for o in ws)
print("\nworking-sample adopted routes: %s" % dict(routes.most_common()))
for s in ("3624_2015", "2007_2015", "2008_2021"):
    o = next((x for x in obs if "%d_%d" % (x["syndicate"], x["year"]) == s), None)
    print("  %s: in working sample %s, route %s, cohort scope %s"
          % (s, s in ws_stems, o and o.get("pyd_cohort_route"), o and o.get("pyd_cohort_scope")))
