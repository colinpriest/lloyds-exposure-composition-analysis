r"""The eighth census's two take-on readings of each record, to decide the ninth census's carry-over (read-only).

For each record the eighth census read in its takeon_triangle part (or those named on the command line): the adopted
figure and opening reserves, the first reading's finding, amount and evidence, and the second reading's finding, amount
and reasons, trimmed. Prints only; the decisions go in carry_decisions_ninth.py before any new reading.

    python carry_view_ninth.py [syndicate_1234_2020 ...]
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs-eighth.json") if "takeon_triangle" in b["census_parts"]}
first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-eighth.json")}
second = {v["stem"]: v for v in load(SCR / "error-rate-verification-eighth.json")}
FULL = "--full" in sys.argv
LIMIT = 100000 if FULL else 900
stems = [a for a in sys.argv[1:] if a != "--full"] or sorted(briefs)
for s in stems:
    b = briefs[s]
    f = ((first[s].get("census_check") or {}).get("takeon_triangle") or {})
    g = ((second[s].get("census_check") or {}).get("takeon_triangle") or {})
    print("=" * 110)
    print("%s  pyd %s  opening %s %s  route %s" % (s, b["adopted_prior_year_development_m_report_currency"],
                                                 b["adopted_opening_reserves_m_report_currency"], b["report_currency"],
                                                 (b["route"] or {}).get("source")))
    print(" FIRST  (%s) finding %s amount %s" % (first[s].get("first_reader"), f.get("finding"), f.get("takeon_amount_m")))
    print("   " + " ".join(str(f.get("evidence") or "").split())[:LIMIT])
    print(" SECOND (%s) finding %s amount %s" % (second[s].get("recorded"), g.get("finding"), g.get("takeon_amount_m")))
    print("   " + " ".join(str(second[s].get("why") or "").split())[:LIMIT])
