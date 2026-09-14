"""Print, for each named record, its ninth census brief, its first reading and any recorded second reading, in full.

    python view_ninth_remaining.py syndicate_2008_2015 ... > out.txt
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


briefs = {b["stem"]: b for b in load("error-rate-briefs-ninth.json")}
merged = {v["stem"]: v for v in load("error-rate-verdicts-ninth.json")}
verified = {v["stem"]: v for v in load("error-rate-verification-ninth.json")}
for s in sys.argv[1:]:
    print("=" * 110)
    print(s)
    print("-- BRIEF")
    print(json.dumps(briefs.get(s), indent=1, ensure_ascii=False))
    print("-- FIRST READING")
    print(json.dumps(merged.get(s), indent=1, ensure_ascii=False))
    print("-- SECOND READING")
    print(json.dumps(verified.get(s), indent=1, ensure_ascii=False))
