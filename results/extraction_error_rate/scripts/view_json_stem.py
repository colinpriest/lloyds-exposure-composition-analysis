"""Print every entry for a record in a scratchpad JSON file (a list of entries, or a dict holding lists), in full.

    python view_json_stem.py error-rate-verification-eighth.json syndicate_2008_2023 [more stems]
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent


def entries(node):
    if isinstance(node, list):
        for x in node:
            if isinstance(x, dict) and "stem" in x:
                yield x
            else:
                yield from entries(x)
    elif isinstance(node, dict):
        if "stem" in node:
            yield node
        else:
            for v in node.values():
                yield from entries(v)


data = json.load(io.open(str(SCR / sys.argv[1]), encoding="utf-8"))
wanted = set(sys.argv[2:])
n = 0
for e in entries(data):
    if e.get("stem") in wanted:
        n += 1
        print("=" * 100)
        print(json.dumps(e, indent=1, ensure_ascii=False))
print("entries found: %d" % n)
