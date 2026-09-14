r"""What the working tree's extraction records differ in from the extraction repo's HEAD, counted by field (read-only).

Every modified record under pdf_extraction/ (audit files and the LLM cache excepted) is compared with its HEAD blob as
parsed JSON, so a line-ending or key-order change is not counted. Each differing field path is counted once per record,
with model names folded to <model>, and the records whose differences go beyond the fields a replay rewrites anyway are
listed in full.

    python diff_replayed_vs_head.py
"""
import collections
import io
import json
import subprocess
import sys
from pathlib import Path

EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPLAY_FIELDS = ("extraction_timestamp", "_extraction_meta", "total_cost_usd", "total_tokens")


def head(name):
    r = subprocess.run(["git", "-C", str(EXT), "show", "HEAD:" + name], capture_output=True)
    return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None


def paths(a, b, p=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            key = "<model>" if p == ".models" else k
            if k not in a or k not in b:
                yield p + "." + key + (" (added)" if k not in a else " (removed)")
            else:
                yield from paths(a[k], b[k], p + "." + key if p != ".models" else p + ".<model>")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for x, y in zip(a, b):
            yield from paths(x, y, p + "[]")
    elif a != b:
        yield p


names = subprocess.run(["git", "-C", str(EXT), "diff", "--name-only", "HEAD", "--", "pdf_extraction/"],
                       capture_output=True, text=True, check=True).stdout.split()
names = [n for n in names if n.endswith(".json") and "/audit/" not in n and "llm_cache" not in n]
counter, beyond = collections.Counter(), {}
identical = 0
for name in names:
    new = json.load(io.open(str(EXT / name), encoding="utf-8"))
    old = head(name)
    if old is None:
        counter["(not in HEAD)"] += 1
        continue
    ps = sorted(set(paths(old, new)))
    if not ps:
        identical += 1
    for q in ps:
        counter[q] += 1
    extra = [q for q in ps if not any(f in q for f in REPLAY_FIELDS)]
    if extra:
        beyond[name] = extra
print("modified records: %d; identical as JSON: %d" % (len(names), identical))
for q, n in counter.most_common(40):
    print("%5d  %s" % (n, q))
print("records differing beyond %s: %d" % (", ".join(REPLAY_FIELDS), len(beyond)))
for name, extra in sorted(beyond.items()):
    print("  %s: %s" % (name, "; ".join(extra[:12])))
