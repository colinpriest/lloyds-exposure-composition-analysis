r"""stage_extraction_error_rate.py: the tail stratum's second readings and render, and opening reserves the take-on base
adjusts by design.

  * scripts/: record_tail_readings.py and the readings files it recorded (readings_tail_part*.py);
  * tail/syndicate_1991_2020_p38.png: the rendered page the second reading of 1991/2020 read its image triangle from;
  * the README's list of first readings whose opening reserves fall outside the 2% check leaves out a record the take-on
    base register adjusts (its brief's opening reserves add the business taken on, so they cannot match the filing's
    1 January figure), and the take-on base section names those readings instead.

Each replacement must match exactly once, or nothing is written.

    python patch_stage_tail_readings.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
TARGET = SCR / "stage_extraction_error_rate.py"
REPLACEMENTS = [
    ('EXTRA = [("renders/syndicate_623_2014_p45.png", "found-in-passing/syndicate_623_2014_p45.png")]',
     'EXTRA = [("renders/syndicate_623_2014_p45.png", "found-in-passing/syndicate_623_2014_p45.png"),\n'
     '         ("renders/syndicate_1991_2020_p38.png", "tail/syndicate_1991_2020_p38.png")]\n'
     'FILES["scripts"] += ["record_tail_readings.py", "patch_stage_tail_readings.py"]\n'
     'FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_tail_part*.py"))'),
    ('openings_outside = []\n',
     'openings_outside, base_openings = [], []\n'),
    ('        if isinstance(o, dict) and o.get("within_2pct") is False:\n'
     '            openings_outside.append(',
     '        if isinstance(o, dict) and o.get("within_2pct") is False and r["stem"].replace("syndicate_", "") in base_register:\n'
     '            base_openings.append("%s (brief %s, the filing\'s 1 January %s, p%s; %s)" % (key(r["stem"]), o.get("adopted_m"),\n'
     '                                                                              o.get("filing_m"), o.get("page"), p.name))\n'
     '        elif isinstance(o, dict) and o.get("within_2pct") is False:\n'
     '            openings_outside.append('),
    ('transfer is under 5% of the opening reserves; and {listing(other9)}.\n',
     'transfer is under 5% of the opening reserves; and {listing(other9)}. Later first readings of an adjusted record find its\n'
     'opening reserves outside the 2% check, as they must: {"; ".join(base_openings) or "none"}.\n'),
]

raw = io.open(str(TARGET), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if "base_openings" in text:
    raise SystemExit("the staging script already separates the take-on base's openings")
for old, new in REPLACEMENTS:
    n = text.count(old)
    if n != 1:
        raise SystemExit("expected once, found %d: %r" % (n, old[:90]))
    text = text.replace(old, new)
compile(text, TARGET.name, "exec")
io.open(str(TARGET), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print("patched %d sites in %s" % (len(REPLACEMENTS), TARGET.name))
