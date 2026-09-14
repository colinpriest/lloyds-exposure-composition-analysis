r"""The records the error-rate study read, for the propagation's N (fifth amendment, point 5; eighth amendment, point 6:
"the working-sample records read in no sample or census, this census included").

error_rate_propagation.py counts every syndicate stem anywhere in a --read-samples file as read, so a sample file that
also lists its population or frame would mark unread records as read. This takes each file's read records from the
key that holds them, and nothing else:
  * the first and second draws' primary stems; the third draw's stems and its entrants;
  * each census's stems: the two mechanisms, the take-on census, the records found in passing, the eighth census (its
    read records and the records it listed as decided, which earlier draws read) and the take-on base census;
  * implementation note 4's record; and the tail stratum's stems, which must exist unless --before-tail is given.
Writes error-rate-read-stems.json.

    python build_read_stems.py [--before-tail]
"""
import datetime
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


def stems_under(node):
    out = set()
    if isinstance(node, str):
        if node.startswith("syndicate_"):
            out.add(node)
    elif isinstance(node, list):
        for x in node:
            out |= stems_under(x)
    elif isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.startswith("syndicate_"):
                out.add(k)
            out |= stems_under(v)
    return out


SOURCES = [
    ("error-rate-sample.json", lambda d: d["primary"]["stems"]),
    ("error-rate-sample-after.json", lambda d: d["primary"]["stems"]),
    ("error-rate-sample-third.json", lambda d: d["third"]["stems"] + d["E_entrants"]["stems"]),
    ("error-rate-census.json", lambda d: d["stems"]),
    ("error-rate-census-takeon.json", lambda d: d["stems"]),
    ("error-rate-census-passing.json", lambda d: d["stems"]),
    ("error-rate-census-eighth.json", lambda d: sorted(set(d["stems"]) | stems_under(d["decided"]))),
    ("error-rate-census-ninth.json", lambda d: d["stems"]),
    ("error-rate-briefs-ninth-sixth-2003.json", lambda d: [b["stem"] for b in d]),
]
if (SCR / "error-rate-tail.json").exists():
    SOURCES.append(("error-rate-tail.json", lambda d: d["tail"]["stems"]))
elif "--before-tail" not in sys.argv:
    raise SystemExit("error-rate-tail.json does not exist: draw the tail first, or give --before-tail")

read, counts = set(), {}
for name, take in SOURCES:
    stems = list(take(load(name)))
    bad = [s for s in stems if not (isinstance(s, str) and s.startswith("syndicate_"))]
    if not stems or bad:
        raise SystemExit("%s: no stems, or stems that are not syndicate stems (%s)" % (name, bad[:3]))
    counts[name] = len(stems)
    read |= set(stems)
out = {"purpose": "the records the error-rate study read (build_read_stems.py), for error_rate_propagation.py --read-samples",
       "written": datetime.datetime.now().isoformat(timespec="seconds"), "sources": counts, "n": len(read),
       "stems": sorted(read)}
io.open(str(SCR / "error-rate-read-stems.json"), "w", encoding="utf-8", newline="").write(json.dumps(out, indent=1) + "\n")
print("read stems %d from %s" % (len(read), counts))
