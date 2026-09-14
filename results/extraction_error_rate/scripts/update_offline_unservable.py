r"""offline_unservable.json from the R213 full offline replay's own log, not typed.

The file records which reports an offline replay cannot serve from the committed caches, and the manuscript's
replay-coverage sentence is computed from its n_attempted and n_unservable (paper/sync_replay_coverage.py). The
round-56 R193 replay found one data-carrying report unservable, 2008/2021. Its missing page response was made and
cached on 13 September 2026, and the full offline replay under the repaired pipeline (R213) measured the corpus again.

Reads: replay-r213-stems.json (the reports attempted) and replay-r213-full.log (exit status, the run's error count
and every offline cache-miss line). Refuses unless the log ends with an exit status and an error count. Writes the
new measurement beside the earlier ones; the reports with no usable cache, never attempted, stay listed.

    python update_offline_unservable.py [--dry-run]
"""
import datetime
import io
import json
import re
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
P = EX / "pdf_extraction" / "audit" / "offline_unservable.json"
LOG = SCR / "replay-r213-full.log"

attempted = json.load(io.open(str(SCR / "replay-r213-stems.json"), encoding="utf-8"))
log = io.open(str(LOG), encoding="utf-8", errors="replace").read()
exit_m = re.findall(r"^exit=(\d+)$", log, re.M)
errored_m = re.findall(r"Errored:\s+(\d+)", log)
if not exit_m or not errored_m:
    raise SystemExit("the replay log has no exit status or error count yet")
exit_code, errored = int(exit_m[-1]), int(errored_m[-1])
misses = {}
for m in re.finditer(r"offline mode: .*?(syndicate_\d+_\d+)\.pdf.*?would call an external API \(cache miss\)", log):
    misses.setdefault(m.group(1), m.group(0).strip())
if errored != len(misses):
    raise SystemExit("the run reports %d errored records but the log names %d cache misses: read the log first"
                     % (errored, len(misses)))
if (exit_code == 0) != (errored == 0):
    raise SystemExit("exit status %d does not agree with %d errored records" % (exit_code, errored))

rec = json.load(io.open(str(P), encoding="utf-8"))
never = list(rec.get("no_usable_cache_not_attempted") or [])
rec["recorded"] = datetime.date.today().isoformat()
rec["round"] = ("round 56, after R213: the offline replay of every data-carrying record at prompt 2.13, from the "
                "committed caches, after 2008/2021's missing page response was made and cached (13 September 2026)")
rec["n_attempted"] = len(attempted)
rec["n_unservable"] = len(misses)
rec["unservable_in_this_replay"] = {s: misses[s] for s in sorted(misses)}
rec["stems"] = sorted(set(never) | set(misses))
meas = rec.setdefault("measurement", {})
meas["round_56_R213"] = {"attempted": len(attempted), "unservable": len(misses), "unservable_stems": sorted(misses)}
if "--dry-run" in sys.argv:
    print(json.dumps({k: rec[k] for k in ("recorded", "n_attempted", "n_unservable", "unservable_in_this_replay",
                                          "stems")}, indent=1))
    print("measurements: %s" % sorted(meas))
    raise SystemExit(0)
raw = io.open(str(P), encoding="utf-8", newline="").read()
text = json.dumps(rec, indent=1, ensure_ascii=False) + "\n"
io.open(str(P), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if "\r\n" in raw else text)
print("offline_unservable.json: %d attempted, %d unservable %s" % (len(attempted), len(misses), sorted(misses)))
