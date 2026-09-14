r"""Record second readings for the tail stratum from a Python file of readings, without shell quoting.

The file defines READINGS, a list of dicts: stem, verdict, pages, quote, why, and optionally filing (the filing's
figure) and error_kind. Each is passed to record_second_read.py --tail as an argument list, so quotes in the text need
no escaping. A record already in error-rate-verification-tail.json is skipped, so the file can be run again after an
addition.

    python record_tail_readings.py readings_tail_part1.py
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
VERIFIED = SCR / "error-rate-verification-tail.json"
spec = importlib.util.spec_from_file_location("readings", str(SCR / sys.argv[1]))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
done = {v["stem"] for v in json.load(io.open(str(VERIFIED), encoding="utf-8"))} if VERIFIED.exists() else set()
failed = 0
for r in mod.READINGS:
    if r["stem"] in done:
        print("skip %s: already recorded" % r["stem"])
        continue
    argv = [sys.executable, str(SCR / "record_second_read.py"), r["stem"], r["verdict"], "--tail",
            "--pages"] + [str(p) for p in r["pages"]] + ["--quote", r.get("quote", ""), "--why", r["why"]]
    if r.get("filing") is not None:
        argv += ["--filing-figure", repr(float(r["filing"]))]
    if r.get("error_kind"):
        argv += ["--error-kind", r["error_kind"]]
    out = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((out.stdout + out.stderr).strip())
    failed += out.returncode != 0
sys.exit(1 if failed else 0)
