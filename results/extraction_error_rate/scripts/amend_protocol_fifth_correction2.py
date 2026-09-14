r"""The fifth amendment's cohort census, stated from the check's own file before any census record is read
(13 September 2026, 20:05).

cohort-manifestations.json (the round-56 check) lists five working-sample records whose adopted figure equals the
triangle without the aggregated cohort, not two: 2007/2015 and 3624/2015 (no route: the models' triangle decides),
and 4242/2021, 4242/2022 and 4242/2023 (route rag_triangle: the deterministic triangle decides, and the check could
not compute the figure with the cohort). The amendment already adds a record the check names; this states the
five and how they are selected.

    python amend_protocol_fifth_correction2.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
OLD = """   - Aggregated older cohort omitted: every working-sample record whose adopted figure comes from a triangle
     that leaves out an aggregated older cohort the filing prints. The round-56 check named two, 3624/2015 and
     2007/2015. What that check covered is recorded with the census, and a record it missed is added if found.
"""
NEW = """   - Aggregated older cohort omitted: every working-sample record whose adopted figure comes from a triangle
     that leaves out an aggregated older cohort the filing prints. The round-56 check
     (`cohort-manifestations.json`) lists five working-sample records whose adopted figure equals a cohort
     table's triangle without the cohort: 2007/2015 and 3624/2015, where the models' triangle decides, and
     4242/2021, 4242/2022 and 4242/2023, where the deterministic triangle decides and the check could not
     compute the figure with the cohort. What that check covered is recorded with the census, and a record it
     missed is added if found. (Correction, 20:05, before any census record was read: the first version named
     only the first two.)
"""

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "(Correction, 20:05, before any" in t:
    raise SystemExit("already corrected")
if t.count(OLD) != 1:
    raise SystemExit("the cohort census bullet was not found once")
t = t.replace(OLD, NEW)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("error-rate-protocol.md: the fifth amendment's cohort census names the check's five records")
