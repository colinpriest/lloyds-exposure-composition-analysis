"""Print the shape of the error-rate study's result files: top-level keys, and each rule's counts and posterior.

    python inspect_results.py FILE [FILE ...]
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent


def short(v, n=160):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + " ..."


for name in sys.argv[1:]:
    p = SCR / name
    print("=" * 100)
    if not p.exists():
        print("%s: MISSING" % name)
        continue
    d = json.load(io.open(str(p), encoding="utf-8"))
    print(name, type(d).__name__, len(d))
    if isinstance(d, list):
        print("  first entry keys:", sorted(d[0]) if d and isinstance(d[0], dict) else short(d[:2]))
        continue
    for k, v in d.items():
        if k == "rules" and isinstance(v, dict):
            for rk, rv in v.items():
                keep = {x: rv.get(x) for x in ("errors", "adjudicable_n", "undeterminable", "correct", "n") if x in rv}
                post = rv.get("posterior") or {}
                print("  rules.%s: %s posterior mean %s ci %s; other keys %s" % (
                    rk, keep, post.get("mean"), post.get("ci95_equal_tailed"),
                    sorted(x for x in rv if x not in keep and x != "posterior")))
        elif isinstance(v, (dict, list)):
            print("  %s: %s of %d; %s" % (k, type(v).__name__, len(v), short(v)))
        else:
            print("  %s: %s" % (k, short(v)))
