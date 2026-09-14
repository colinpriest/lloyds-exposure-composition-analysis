r"""R213 on fixed inputs: replay every data-carrying record offline under the repaired pipeline and read what moved.

The rule change is keyed to its register, so by construction it can move only 3624/2015; 2008/2021's missing page
response is now cached, so its replay should be served. A full offline replay proves both on the committed caches,
and it is the measurement offline_unservable.json must record (the sentence in the manuscript is computed from it).

  prep     write replay-r213-stems.json (every record with model output) and replay-r213-before.json (each record's
           adopted figure per model, route source and the notes' override and veto tags), read from the working tree
  compare  after the replay, list every record whose adopted figure, route source or tags changed, and every stem
           the replay did not rewrite

    python replay_r213_isolation.py prep
    (replay)  python test_gemini.py --stems <scratchpad>/replay-r213-stems.json --offline --table-backend azure
    python replay_r213_isolation.py compare
"""
import glob
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
SCR = Path(__file__).resolve().parent
STEMS = SCR / "replay-r213-stems.json"
BEFORE = SCR / "replay-r213-before.json"
TAGS = re.compile(r"\[(?:RAG|CODE)[^\]]*?(?:OVERRIDE|NOT APPLIED|APPLIED OVER THE SIGN VETO)[^\]]*\]")


def state():
    out = {}
    for p in sorted(glob.glob(str(EX / "pdf_extraction" / "syndicate_*.json"))):
        d = json.load(io.open(p, encoding="utf-8"))
        models = d.get("models") or {}
        if not models:
            continue
        stem = Path(p).stem
        out[stem] = {
            "mtime": os.path.getmtime(p),
            "models": {k: {"pyd": m.get("prior_year_development_gbp_m"),
                           "route": (m.get("_pyd_route") or {}).get("source"),
                           "tags": hashlib.sha1("|".join(TAGS.findall(str(m.get("data_quality_notes") or "")))
                                                .encode("utf-8")).hexdigest()[:12]}
                       for k, m in sorted(models.items())},
        }
    return out


if sys.argv[1] == "prep":
    s = state()
    io.open(str(STEMS), "w", encoding="utf-8").write(json.dumps(sorted(s), indent=1))
    io.open(str(BEFORE), "w", encoding="utf-8").write(json.dumps(s, indent=1))
    print("data-carrying records: %d -> %s, %s" % (len(s), STEMS.name, BEFORE.name))
elif sys.argv[1] == "compare":
    before = json.load(io.open(str(BEFORE), encoding="utf-8"))
    after = state()
    moved, untouched = [], []
    for stem, b in before.items():
        a = after.get(stem)
        if a is None:
            moved.append((stem, "record lost its model output"))
            continue
        if a["mtime"] == b["mtime"]:
            untouched.append(stem)
        for k in sorted(set(b["models"]) | set(a["models"])):
            bm, am = b["models"].get(k), a["models"].get(k)
            if bm != am:
                moved.append((stem, "%s: %s -> %s" % (k, bm, am)))
    print("records compared %d; rewritten %d; not rewritten by the replay %d"
          % (len(before), len(before) - len(untouched), len(untouched)))
    print("not rewritten: %s" % untouched[:20])
    print("changed adopted figure, route or tags: %d" % len(moved))
    for stem, what in moved:
        print("  %-24s %s" % (stem, what))
