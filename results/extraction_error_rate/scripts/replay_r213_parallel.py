r"""The R213 full offline replay in parallel chunks (the single-process run wrote 4.4 records a minute).

Splits replay-r213-stems.json into N chunk files, runs `test_gemini.py --stems <chunk> --offline --table-backend azure`
for each in its own process (the pipeline locks its shared audit files), waits for all, and writes
replay-r213-full.log: every chunk's log in order, then one summary with the total error count and the worst exit
status, which update_offline_unservable.py reads. No API can be called: --offline makes a cache miss an error, and
LLOYDS_ALLOW_TABLE_BACKEND_CALLS is removed from the children's environment.

    python replay_r213_parallel.py [N]
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCR = Path(__file__).resolve().parent
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
stems = json.load(io.open(str(SCR / "replay-r213-stems.json"), encoding="utf-8"))
full = SCR / "replay-r213-full.log"
if full.exists():
    full.rename(SCR / "replay-r213-single-process-stopped.log")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
env.pop("LLOYDS_ALLOW_TABLE_BACKEND_CALLS", None)
env.pop("LLOYDS_EXTRACTION_OFFLINE", None)

procs = []
start = datetime.datetime.now()
for i in range(N):
    chunk = stems[i::N]
    cfile = SCR / ("replay-r213-chunk-%02d.json" % i)
    io.open(str(cfile), "w", encoding="utf-8").write(json.dumps(chunk))
    log = io.open(str(SCR / ("replay-r213-chunk-%02d.log" % i)), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "test_gemini.py", "--stems", str(cfile), "--offline", "--table-backend", "azure"],
                         cwd=str(EX), env=env, stdout=log, stderr=subprocess.STDOUT)
    procs.append((i, len(chunk), p, log))
    time.sleep(2)      # stagger start-up reads of the shared manifest
codes = []
for i, n, p, log in procs:
    codes.append(p.wait())
    log.close()
end = datetime.datetime.now()

errored_total = 0
with io.open(str(full), "w", encoding="utf-8") as out:
    out.write("start Brisbane %s (parallel, %d chunks)\n" % (start.strftime("%H:%M:%S"), N))
    for i, n, p, _log in procs:
        text = io.open(str(SCR / ("replay-r213-chunk-%02d.log" % i)), encoding="utf-8", errors="replace").read()
        found = re.findall(r"Errored:\s+(\d+)", text)
        if not found:
            raise SystemExit("chunk %d (%d stems) printed no error count; exit %s" % (i, n, codes[i]))
        errored_total += int(found[-1])
        out.write("===== chunk %02d: %d stems, exit %d, errored %s\n" % (i, n, codes[i], found[-1]))
        out.write(text + "\n")
    out.write("===== all chunks\n  Errored:          %d\nexit=%d\nend Brisbane %s\n"
              % (errored_total, max(codes), end.strftime("%H:%M:%S")))
print("chunks %d, stems %d, errored %d, exit codes %s, %s to %s"
      % (N, len(stems), errored_total, codes, start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S")))
