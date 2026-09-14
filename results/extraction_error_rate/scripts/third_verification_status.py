r"""Which second readings the third sample's scoring still lacks, and which recorded ones sit outside its verification set
(read-only).

    python third_verification_status.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
vset = json.load(io.open(str(SCR / "error-rate-verification-set-third.json"), encoding="utf-8"))
verified = json.load(io.open(str(SCR / "error-rate-verification-third.json"), encoding="utf-8"))
want = set(vset["all"])
have = {}
for v in verified:
    have.setdefault(v["stem"], []).append(v)
print("verification set %d; recorded second readings %d (%d distinct records)" % (len(want), len(verified), len(have)))
print("still to read: %s" % sorted(want - set(have)))
print("recorded but outside the set: %s" % sorted(set(have) - want))
print("recorded twice: %s" % sorted(s for s, vs in have.items() if len(vs) > 1))
for name, members in sorted(vset.items()):
    if isinstance(members, list):
        print("  %-40s %d" % (name, len(members)))
for v in verified:
    if v["stem"] in ("syndicate_1274_2017",) or v.get("carried_over_from"):
        print("  carried/target %s: verdict %s, from %s" % (v["stem"], v.get("verdict"), v.get("carried_over_from")))
