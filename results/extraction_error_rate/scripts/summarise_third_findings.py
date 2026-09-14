r"""What the third sample found, for the owner's decision (read-only).

1. Every third-sample record whose final verdict is not correct: its final reading, compactly.
2. The families behind the new mechanisms: every working-sample record of syndicates 382, 2010 and 3010, and the
   transposition scan's other candidates, with every reading each has had in any sample.
3. Second readings in any sample that name a transfer (RITC, take-on, reassumed, reinsured to close) or a misread
   opening figure, with the passage.
4. The found-in-passing record left to the owner (623/2014).

    python summarise_third_findings.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


def short(x, n=900):
    x = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return x if len(x) <= n else x[:n] + " ..."


res = load("error-rate-result-third.json")
third = load("error-rate-sample-third.json")
merged = {v["stem"]: v for v in load("error-rate-verdicts-third.json")}
verified = {v["stem"]: v for v in load("error-rate-verification-third.json")}
third_stems = set(third["third"]["stems"])
pop = set(load("error-rate-population-698.json")["stems"])
ws = pop - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])

print("=" * 100)
print("1. Third-sample records not correct")
A = res["final_verdicts"]["A"]
for s in sorted(third_stems):
    if A[s] == "correct":
        continue
    v = verified.get(s, {})
    first = merged.get(s, {})
    print("-" * 100)
    print("%s  final %s  first reader %s  adopted %s  filing %s  kind %s  pages %s" % (
        s, A[s], first.get("verdict"), first.get("adopted_figure_m"), v.get("filing_figure_m"), v.get("error_kind"),
        v.get("pages")))
    print("   why: %s" % short(v.get("why") or first.get("clarified_why")))

print("=" * 100)
print("2. Mechanism families in the working sample (%d records)" % len(ws))
readings = {}
for merged_name, ver_name, label in (("error-rate-verdicts.json", "error-rate-verification.json", "first sample"),
                                     ("error-rate-verdicts-after.json", "error-rate-verification-after.json", "second sample"),
                                     ("error-rate-verdicts-census.json", "error-rate-verification-census.json", "census"),
                                     ("error-rate-verdicts-third.json", "error-rate-verification-third.json", "third sample")):
    if (SCR / merged_name).exists():
        for r in load(merged_name):
            readings.setdefault(r["stem"], []).append("%s first %s/clarified %s" % (label, r.get("verdict"), r.get("clarified_verdict")))
    if (SCR / ver_name).exists():
        for r in load(ver_name):
            readings.setdefault(r["stem"], []).append("%s second %s" % (label, r.get("verdict")))
if (SCR / "error-rate-verification-passing.json").exists():
    for r in load("error-rate-verification-passing.json"):
        readings.setdefault(r["stem"], []).append("found in passing %s" % r.get("verdict"))
families = sorted(s for s in ws if re.match(r"syndicate_(382|2010|3010)_\d{4}$", s))
for s in families + ["syndicate_5678_2015", "syndicate_1945_2021"]:
    print("  %-22s WS %-5s %s" % (s, s in ws, "; ".join(readings.get(s, ["never read"]))))
for fam in ("382", "2010", "3010"):
    fs = [s for s in ws if s.startswith("syndicate_%s_" % fam)]
    print("  syndicate %s: %d in the working sample, %d never read" % (fam, len(fs), sum(1 for s in fs if s not in readings)))

print("=" * 100)
print("3. Transfers or misread opening figures named in second readings")
pat = re.compile(r"(RITC|take-on|takeon|reassum|reinsured to close|reinsurance to close|misread|reinsurers' share as)", re.I)
for name in sorted(glob.glob(str(SCR / "error-rate-verification*.json"))):
    data = json.load(io.open(name, encoding="utf-8"))
    if not isinstance(data, list):
        continue
    for r in data:
        why = r.get("why") or ""
        hits = [m.start() for m in pat.finditer(why)]
        if not hits:
            continue
        print("  %-22s %-40s %-14s WS %-5s" % (r["stem"], Path(name).name, r.get("verdict"), r["stem"] in ws))
        at = hits[0]
        print("      ... %s ..." % why[max(0, at - 300): at + 400].replace("\n", " "))

print("=" * 100)
print("4. 623/2014")
for name in sorted(glob.glob(str(SCR / "error-rate-*passing*.json"))):
    data = json.load(io.open(name, encoding="utf-8"))
    rows = data if isinstance(data, list) else [data]
    for r in rows:
        if isinstance(r, dict) and "623_2014" in json.dumps(r):
            print("  %s: %s" % (Path(name).name, short(r, 1500)))
