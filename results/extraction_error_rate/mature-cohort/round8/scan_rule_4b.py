"""Rule 4b's population scan (decisions of the Claude analysis session, 24 October 2026) over every reading of rounds 5
to 8 (round5/readings/*.json, round8/readings/Z7.json, Z8.json). It decides nothing: it lists what a session must read
against rule 4b's conditions. The answers are in rule_4b_scan.json.

What 'reports' means (rules.md, rule 4b): a reading reports a fall when it quotes both cells, the year t table's
cumulative paid and the year t-1 report's, for the same underwriting year, whether or not it names the fall.

Three passes:
  * structural: in every reading, every pair of paid cells quoted against each other (a difference 'A-B=C' or '(A-B)'
    in a paid working, 'A vs B', 'A against B', 'A -> B', 'from A to B', 'A to B') whose later figure is below the
    earlier one, inside a passage about paid or payments; each hit is a pair of cells a session must answer
    (structural_hits);
  * narrow: cumulative paid or payments near a word of decrease;
  * loose: 'paid' or 'payments' within 120 characters of such a word.
A record no pass flags has no reading that quotes a falling pair of paid cells, so condition (i) fails for it.

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
#: a quoted figure: digits with thousands commas or a decimal part (a bare four-digit year is not one)
NUM = (r"(?<![\d.,x])(?:\(?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?\d+\.\d+\)?|\(?\d{1,3}\)?(?![\d.,]))(?!\s*%)")
#: a difference in a paid working: later minus earlier (A-B=C, or (A-B) inside a sum)
DIFF = re.compile(r"(?P<a>%s)\s*-\s*(?P<b>%s)\s*(?:=|\))" % (NUM, NUM))
#: a later figure set against an earlier one: 'A vs B', 'A against B' (the reader's later figure first), and 'A -> B',
#: 'from A to B', 'A to B' (earlier first); up to 60 characters of label (a page or a table) may sit after each figure
VS = re.compile(r"(?P<a>%s)(?:\s*\([^()]{0,60}\))?(?:\s+(?:in|at)\s+[^,;()]{0,40}?)?\s+"
                r"(?:vs\.?|versus|against|(?:is\s+)?inconsistent\s+with|compared\s+with)\s+"
                r"(?:the\s+)?(?:[^\d(]{0,30}?)(?P<b>%s)" % (NUM, NUM), re.I)
#: 'the 2021 filing prints B for the same cell' after A (later first); '(B) then (A)' (earlier first); 'A ... below
#: the 2015 report's B' (later first)
PRINTS = re.compile(r"(?P<a>%s)[^;]{0,200}?\b(?:prints|printed)\s+(?P<b>%s)\s+for the same" % (NUM, NUM), re.I)
THEN = re.compile(r"(?P<a>%s)[^.;]{0,40}?\bthen\s+(?P<b>%s)" % (NUM, NUM), re.I)
BELOW = re.compile(r"(?P<a>%s)(?:\s*\([^()]{0,60}\))?\s+(?:is\s+|are\s+)?below\s+(?:the\s+)?[^\d]{0,40}?(?P<b>%s)"
                   % (NUM, NUM), re.I)
ARROW = re.compile(r"(?:from\s+)?(?P<a>%s)(?:\s*\([^()]{0,60}\))?\s*(?:->|→|\bto\b)\s*(?P<b>%s)" % (NUM, NUM), re.I)
PAID = re.compile(r"paid|payment", re.I)
#: what a passage about the year's accounts says: a table figure against the accounts is the paid test, not two reports'
ACCOUNTS = re.compile(r"accounts|technical account|claims paid\s*[-:]?\s*gross|gross claims paid|claims paid - gross|"
                      r"year's (?:gross )?paid|claims paid during", re.I)


def _value(s):
    return float(s.strip("()").replace(",", ""))


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


def _strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, path + "/%d" % i)
    elif isinstance(o, str):
        yield path, o


def structural_hits(entry):
    """[(later, earlier)] for every pair of paid cells a reading quotes against each other with the later below the
    earlier (rounded to the cell's own precision), inside a passage about paid or payments that is not a table-against-
    accounts comparison."""
    hits = []
    for path, text in _strings(entry):
        for pat, later_first in ((DIFF, True), (VS, True), (ARROW, False), (PRINTS, True), (THEN, False),
                                 (BELOW, True)):
            for m in pat.finditer(text):
                s = max(0, m.start() - 160)
                ctx = path + " " + text[s:m.end() + 60]
                if not PAID.search(ctx):
                    continue
                near = text[max(0, m.start() - 60):m.end() + 40]
                if ACCOUNTS.search(near):
                    continue
                a, b = _value(m.group("a")), _value(m.group("b"))
                later, earlier = (a, b) if later_first else (b, a)
                # a factor or ratio (under 1.5) is not a paid cell
                if min(a, b) < 1.5 or not (0.02 <= later / earlier < 0.995):
                    continue
                hits.append((m.group("a").strip("()") if later_first else m.group("b").strip("()"),
                             m.group("b").strip("()") if later_first else m.group("a").strip("()")))
    return sorted(set(hits))


def scan():
    """{key: {"structural": {reader: [(later, earlier)]}, "text": [(reader, pass, passage)]}} for every record of the
    round (the records the round-5 readers read)."""
    out = {}
    for key, by_reader in sorted(readings().items()):
        if not any(r[0] in "PQV" for r in by_reader):
            continue
        rec = {"structural": {}, "text": []}
        for rid, e in sorted(by_reader.items()):
            h = structural_hits(e)
            if h:
                rec["structural"][rid] = h
            text = json.dumps(e, ensure_ascii=False)
            for name, pats in (("narrow", NARROW), ("loose", (LOOSE,))):
                for pat in pats:
                    for m in pat.finditer(text):
                        s = max(0, m.start() - 120)
                        rec["text"].append((rid, name, text[s:m.end() + 160]))
        out[key] = rec
    return out


def main(argv):
    hits = scan()
    flagged = sorted(k for k, h in hits.items() if h["structural"] or h["text"])
    if "--json" in argv:
        print(json.dumps({"records": len(hits), "with_a_passage": flagged,
                          "without": sorted(k for k in hits if k not in flagged),
                          "structural_hits": {k: {r: [list(p) for p in v] for r, v in h["structural"].items()}
                                              for k, h in hits.items() if h["structural"]}}, indent=1))
        return 0
    for k in flagged:
        print("== %s" % k)
        for rid, pairs in hits[k]["structural"].items():
            print("   %s [structural] %s" % (rid, "; ".join("%s below %s" % p for p in pairs)))
        for rid, name, frag in hits[k]["text"]:
            print("   %s [%s] ...%s..." % (rid, name, frag))
    print("%d records; %d with a passage to read; %d with a structural hit" % (
        len(hits), len(flagged), sum(1 for h in hits.values() if h["structural"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
