"""Rule 4b's population scan (decision of the Claude analysis session, 24 October 2026): every passage, in every reading
of rounds 5 to 8 (round5/readings/*.json, round8/readings/Z7.json, Z8.json), that reports a cumulative paid figure
falling, or lower than the year t-1 report's, for some year. Two passes: a narrow one (cumulative paid or payments near a
word of decrease) and a loose one ('paid' or 'payments' within 120 characters of such a word). It decides nothing: it
lists the records whose readings a session must read against rule 4b's conditions, and the records no reading reports a
fall for, which fail condition (i) by its wording ('both readings report'). The answers are in rule_4b_scan.json.

    python results/extraction_error_rate/mature-cohort/round8/scan_rule_4b.py [--json]
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R5 = os.path.join(HERE, "..", "round5", "readings")
R8 = os.path.join(HERE, "readings")
NARROW = (re.compile(r"(cumulative[^.;]{0,60}paid|paid[^.;]{0,60}cumulative|cumulative payments?|paid to date)"
                     r"[^.;]{0,160}?(\bfall|\bfalls|\bfell|\bfallen|\bdrop|\bdecreas|\bdeclin|\blower than|\bbelow the|"
                     r"\breduc|negative|cannot fall|can ?not)", re.I),
          re.compile(r"(\bfall|\bfalls|\bfell|\bdrop|\bdecreas|\bdeclin|\blower)[^.;]{0,80}(cumulative paid|"
                     r"cumulative payments|paid to date)", re.I))
LOOSE = re.compile(r"(paid|payments?)[^.;]{0,120}?\b(lower|below|less than|regress\w*|smaller|reduced|down|"
                   r"fall\w*|fell|drop\w*|decreas\w*|declin\w*|negative|shrank|cannot)\b", re.I)


def readings():
    """{key: {reader: entry}} over the archived readings of rounds 5 to 8 (a '|<task>' suffix and Z8's 'syndicate_'
    prefix dropped)."""
    out = {}
    for folder in (R5, R8):
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            with io.open(os.path.join(folder, name), encoding="utf-8") as fh:
                for k, e in json.load(fh).items():
                    out.setdefault(k.split("|")[0].replace("syndicate_", "", 1), {})[name[:-5]] = e
    return out


def scan():
    """{key: [(reader, pass, passage)]} for every record of the round (the records the round-5 readers read)."""
    hits = {}
    for key, by_reader in sorted(readings().items()):
        if not any(r[0] in "PQV" for r in by_reader):
            continue
        hits[key] = []
        for rid, e in sorted(by_reader.items()):
            text = json.dumps(e, ensure_ascii=False)
            for name, pats in (("narrow", NARROW), ("loose", (LOOSE,))):
                for pat in pats:
                    for m in pat.finditer(text):
                        s = max(0, m.start() - 120)
                        hits[key].append((rid, name, text[s:m.end() + 160]))
    return hits


def main(argv):
    hits = scan()
    flagged = sorted(k for k, h in hits.items() if h)
    if "--json" in argv:
        print(json.dumps({"records": len(hits), "with_a_passage": flagged,
                          "without": sorted(k for k, h in hits.items() if not h)}, indent=1))
        return 0
    for k in flagged:
        print("== %s" % k)
        for rid, name, frag in hits[k]:
            print("   %s [%s] ...%s..." % (rid, name, frag))
    print("%d records; %d with a passage to read" % (len(hits), len(flagged)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
