r"""What the take-on base census's row rule matches, on the cached filing text of the dry run (read-only).

For every cached working-sample filing (ninth-text-cache/), every match of make_census_ninth.py's ROW pattern that the
rule would count (not this syndicate's own number, an amount within 40 characters), with its label normalised and the
80 characters after it. Prints the counts by label, then each record's first counted match. Reads no filing for a
verdict: it only shows the rule's hits, to tighten the rule before the census is written.

    python probe_census_ninth_rows.py
"""
import collections
import io
import re
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROW = re.compile(r"(?:\bRITC\b|reinsurance\s+to\s+close)(?:\s+premium)?\s+(?:accepted|received|take[\s-]*on|taken\s+on|"
                 r"adjustment|inwards?|from\s+(?:syndicate\s*|s)(\d{3,4}))"
                 r"|\binwards?\s+(?:RITC|reinsurance\s+to\s+close)"
                 r"|\breinsurance\s+of\s+new\s+liabilities"
                 r"|\btake[\s-]*on\s+(?:of\s+)?(?:reserves|balances)"
                 r"|\b(?:loss\s+)?portfolio\s+transfers?\b|\bLPTs?\b", re.I)
AMOUNT = re.compile(r"\(?\d{1,3}(?:,\d{3})+\)?|\(?\d+\.\d+\)?")
labels = collections.Counter()
records = collections.defaultdict(set)
first = {}
for p in sorted((SCR / "ninth-text-cache").glob("syndicate_*.txt")):
    stem = p.stem
    syn = stem.split("_")[1]
    text = io.open(str(p), encoding="utf-8").read()
    for m in ROW.finditer(text):
        if m.group(1) and int(m.group(1)) == int(syn):
            continue
        after = text[m.end(): m.end() + 40]
        if not AMOUNT.search(after):
            continue
        label = re.sub(r"\d{3,4}", "N", re.sub(r"\s+", " ", m.group(0).lower()))
        labels[label] += 1
        records[label].add(stem)
        first.setdefault(stem, (label, text[m.end(): m.end() + 80]))
print("labels (matches, records):")
for label, n in labels.most_common():
    print("  %-45s %5d %4d" % (label, n, len(records[label])))
print()
by_label = collections.defaultdict(list)
for stem, (label, after) in first.items():
    by_label[label].append((stem, after))
for label, rows in sorted(by_label.items(), key=lambda x: -len(x[1])):
    print("== %s (%d records by first match)" % (label, len(rows)))
    for stem, after in rows[:12]:
        print("   %-22s ...%s" % (stem, after))
