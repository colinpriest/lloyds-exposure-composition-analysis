r"""score_error_rate_third.py reads each record's latest replay log, which is now the R213 replay.

The merge compares every briefed route with the record's latest replay-log block
(score_error_rate_after_rerun.route_disagrees_with_log). Its block reader takes the R209 replays, the latest when the
second sample was scored. The third sample's records were last written by the full offline replay under R213
(replay-r213-full.log) and, for 1225/2022 and 2010/2019, by the replay after their register entries
(replay-r213b.log). With the R209 logs alone the merge sees 3624/2015's and 2010/2019's routes change with no log
line to show it, and refuses.

This adds log_blocks_after_r213() to score_error_rate_third.py (the R209 blocks, then the R213 full replay's, then
replay-r213b.log's, each later block replacing an earlier one for its record) and makes check() and merge() use it.
The second sample's scoring is untouched.

    python fix_third_log_blocks.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "score_error_rate_third.py"
ANCHOR = "def batch_rows(stems, carry, problems):\n"
CALL_OLD = "    blocks = rr.log_blocks()\n"
CALL_NEW = "    blocks = log_blocks_after_r213()\n"
FUNC = '''def log_blocks_after_r213():
    """Each record's latest replay-log block: the R209 replays, then the R213 full replay, then the replay of the two
    records added to the extraction's register (replay-r213b.log). A later block replaces an earlier one."""
    blocks = rr.log_blocks()
    for name in ("replay-r213-full.log", "replay-r213b.log"):
        path = SCR / name
        if not path.exists():
            raise SystemExit("%s is missing: the records' latest replay log cannot be read" % name)
        current = None
        for ln in io.open(str(path), encoding="utf-8", errors="replace"):
            m = rr.HEADER.match(ln)
            if m:
                current = "syndicate_%s_%s" % (m.group(1), m.group(2))
                blocks[current] = []
                continue
            if current:
                blocks[current].append(ln.rstrip("\\n"))
    return blocks


'''

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "def log_blocks_after_r213" in t:
    raise SystemExit("already patched")
if t.count(ANCHOR) != 1 or t.count(CALL_OLD) != 2:
    raise SystemExit("anchors: batch_rows %d (want 1), log_blocks calls %d (want 2)" % (t.count(ANCHOR), t.count(CALL_OLD)))
t = t.replace(ANCHOR, FUNC + ANCHOR).replace(CALL_OLD, CALL_NEW)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("score_error_rate_third.py: check and merge read the R213 replay logs as each record's latest block")
