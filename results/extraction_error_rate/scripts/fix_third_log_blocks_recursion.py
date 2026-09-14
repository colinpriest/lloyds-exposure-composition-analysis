r"""Repair fix_third_log_blocks.py's own defect: it replaced the R209 reader's call after inserting the new function, so
the new function's first line, `blocks = rr.log_blocks()`, became a call to itself and the merge recursed.

This restores that one line, inside log_blocks_after_r213 only, and checks the result: the function reads rr.log_blocks()
once, and check() and merge() call log_blocks_after_r213() once each.

    python fix_third_log_blocks_recursion.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "score_error_rate_third.py"
BAD = "    blocks = log_blocks_after_r213()\n"
GOOD = "    blocks = rr.log_blocks()\n"

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
start = t.index("def log_blocks_after_r213():")
end = t.index("def batch_rows(", start)
inside = t.index(BAD, start) if BAD in t[start:end] else -1
if inside < 0 or inside > end:
    raise SystemExit("the recursive line is not inside log_blocks_after_r213: nothing to repair")
t = t[:inside] + GOOD + t[inside + len(BAD):]
calls, reads = t.count(BAD), t.count(GOOD)
if calls != 2 or reads != 1:
    raise SystemExit("after the repair: log_blocks_after_r213() calls %d (want 2), rr.log_blocks() %d (want 1)" % (calls, reads))
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("score_error_rate_third.py: log_blocks_after_r213 reads rr.log_blocks() again; check and merge call it once each")
