r"""After stopping a replay: every extraction record written since the replay started still parses, and the shared
audit files a concurrent run could touch are intact.

    python validate_replayed_records.py 2026-09-13T20:44:00
"""
import datetime
import glob
import io
import json
import os
import subprocess
import sys
from pathlib import Path

EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
since = datetime.datetime.fromisoformat(sys.argv[1]).timestamp()
touched, broken = [], []
for p in glob.glob(str(EX / "pdf_extraction" / "syndicate_*.json")):
    if os.path.getmtime(p) >= since:
        touched.append(Path(p).name)
        try:
            d = json.load(io.open(p, encoding="utf-8"))
            if not d.get("models"):
                broken.append((Path(p).name, "no models"))
        except (OSError, ValueError) as exc:
            broken.append((Path(p).name, str(exc)[:120]))
for rel in ("pdf_extraction/audit/run_manifest.json", "pdf_extraction/audit/disagreement_log.json",
            "pdf_extraction/syndicate_inception_years.json"):
    try:
        json.load(io.open(str(EX / rel), encoding="utf-8"))
    except (OSError, ValueError) as exc:
        broken.append((rel, str(exc)[:120]))
status = subprocess.run(["git", "-C", str(EX), "status", "--porcelain", "--", "pdf_extraction/audit",
                         "pdf_extraction/syndicate_inception_years.json"], capture_output=True, text=True).stdout
print("records written since %s: %d; unreadable or empty: %d %s" % (sys.argv[1], len(touched), len(broken), broken))
print("shared files changed:\n%s" % (status or "  (none)"))
