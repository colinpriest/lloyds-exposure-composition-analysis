r"""The runbook, PLAN R213 and the findings ledger: the eighth census's result, the owner's midday decisions of
14 September 2026, the ninth amendment, the A4b commit and the take-on base census so far.

Counts come from the readings and census files; times from files and the analysis repository (the amendment's heading,
the census file's "written", the A4b commit); the runbook block's own time is the clock's when this runs.

    python record_ninth_state.py
"""
import collections
import datetime
import io
import json
import re
import subprocess
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
PLAN = Path(r"D:/Latex projects/BAJ - Lloyds reserves rescaling/PLAN.md")
RUNBOOK = SCR / "stage8-worklist.md"
LEDGER = SCR / "round56-findings-ledger.md"


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


protocol = io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read()
m = re.search(r"## Ninth amendment, 14 September 2026, (\d\d:\d\d)", protocol)
if not m:
    raise SystemExit("no ninth amendment in the protocol")
amended = m.group(1)

# the eighth census, from its readings (as score_error_rate_eighth.py scores it)
briefs8 = {b["stem"]: b for b in load("error-rate-briefs-eighth.json")}
merged8 = {v["stem"]: v for v in load("error-rate-verdicts-eighth.json")}
verified8 = {v["stem"]: v for v in load("error-rate-verification-eighth.json")}
if set(merged8) != set(briefs8) or set(verified8) < set(briefs8):
    raise SystemExit("the eighth census is not fully read: score it first")
clarified = collections.Counter(v["clarified_verdict"] for v in merged8.values())
errors = sorted(s for s in briefs8 if merged8[s]["clarified_verdict"] == "error" and verified8[s]["verdict"] == "error")
found = collections.defaultdict(list)
for s, b in briefs8.items():
    for part in b["census_parts"]:
        f = ((merged8[s].get("census_check") or {}).get(part) or {}).get("finding")
        g = ((verified8[s].get("census_check") or {}).get(part) or {}).get("finding")
        if f is True and g is True:
            found[part].append(s.replace("syndicate_", "").replace("_", "/"))
parts8 = "; ".join("%s %s" % (p, ", ".join(found[p]) if found[p] else "none")
                   for p in ("movement", "transposed", "net_table", "provisions_row", "opening", "takeon_triangle"))
if len(errors) != 6:
    raise SystemExit("the eighth census's confirmed errors are %d, not the six this entry describes: %s" % (len(errors), errors))

# the ninth census so far
census9 = load("error-rate-census-ninth.json")
decisions9 = load("error-rate-carry-over-ninth.json")["decisions"]
carried9 = sum(1 for d in decisions9 if d["carry"])
fresh9 = len(load("error-rate-fresh-stems-ninth.json"))
batches9 = len(list(SCR.glob("error-rate-briefs-ninth-batch-*.json")))
written9 = census9["written"][11:16]
parts9 = ", ".join("%s %d" % (p, len(v)) for p, v in census9["parts"].items())
dry = []
for name in ("census-ninth-dryrun.log", "census-ninth-dryrun2.log", "census-ninth-dryrun3.log"):
    mm = re.search(r"^listed (\d+):", io.open(str(SCR / name), encoding="utf-8").read(), re.M)
    dry.append(mm.group(1) if mm else "?")

# the A4b commit, the suite and the mutation check
log = subprocess.run(["git", "-C", str(AN), "log", "--grep", "R213 ninth amendment", "-1", "--format=%h %ad",
                      "--date=format:%H:%M"], capture_output=True, text=True, check=True).stdout.split()
if len(log) != 2:
    raise SystemExit("no A4b commit in the analysis repository")
a4b = "%s at %s" % (log[0], log[1])
suite = re.findall(r"^(\d+ failed, \d+ passed, \d+ skipped)", io.open(str(SCR / "analysis-suite-a4b.log"), encoding="utf-8").read(), re.M)
mut = re.search(r"mutants caught (\d+) of (\d+)", io.open(str(SCR / "mutate-takeon-base.txt"), encoding="utf-8").read())
if not suite or not mut:
    raise SystemExit("the suite log or the mutation log lacks its summary")
now = datetime.datetime.now().strftime("%H:%M")
V = {"now": now, "amended": amended, "n8": len(briefs8), "c": clarified["correct"], "e": clarified["error"],
     "u": clarified["undeterminable"], "errs": ", ".join(s.replace("syndicate_", "").replace("_", "/") for s in errors),
     "parts8": parts8, "a4b": a4b, "suite": suite[-1], "mut": "%s of %s" % mut.groups(), "written9": written9,
     "dry": " then ".join(dry), "n9": len(census9["stems"]), "parts9": parts9, "carried": carried9, "fresh9": fresh9,
     "nb": batches9}


def write(path, old_anchor, new_text, marker):
    raw = io.open(str(path), encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    if marker in t:
        raise SystemExit("%s: already recorded" % path.name)
    if old_anchor is None:
        t = t + new_text
    else:
        if t.count(old_anchor) != 1:
            raise SystemExit("%s: anchor found %d times" % (path.name, t.count(old_anchor)))
        t = t.replace(old_anchor, new_text + old_anchor)
    io.open(str(path), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)


RUNBOOK_BLOCK = '''
### State at %(now)s (14 September 2026)
- Eighth census scored (score_error_rate_eighth.py; error-rate-census-eighth-result.json): %(n8)d records, clarified
  %(c)d correct, %(e)d errors, %(u)d undeterminable. Both readings find six errors: %(errs)s. Found by both, by part:
  %(parts8)s.
- Batch 12's first reader stopped on the spend limit after one record; batch 12b (make_batch_12b.py) read 609/2023 and
  780/2018. The staging script's batch count must allow the extra batch.
- Owner's decisions (midday): 2010/2015 is repaired by the note's -9.646m; the take-on base is repaired by adjusting the
  opening reserves.
- Ninth amendment written %(amended)s. A4b committed (%(a4b)s): the census's repairs (register_eighth_repairs.py) and the
  take-on base register and loader step, test-first (mutants caught %(mut)s; suite %(suite)s, the six known pre-refit
  failures).
- Take-on base census written %(written9)s (make_census_ninth.py; its dry runs listed %(dry)s records): %(n9)d records
  (%(parts9)s); %(carried)d keep their eighth-census readings, %(fresh9)d are read afresh in %(nb)d batches.
- The tail's brief builder now applies the take-on base register after the confirmed opening reserves (point 6).
- Running: the %(nb)d first-reader agents (reader-prompt-ninth-batch-N.txt).
- Next: score_error_rate_ninth.py check, merge; second readings (second_read.py --ninth, record_second_read.py --ninth);
  score; register_ninth_takeon_base.py; suite; commit A4c; predict refit 3; refit 3; tail stratum; propagation; staging
  (the ninth census, batch 12b); A5; push (authorised); Stage 8.
''' % V

PLAN_PARA = '''
*The ninth amendment (14 September 2026):* the eighth census confirmed six errors, repaired through the registers
(2791/2015, 3010/2018, 382/2017 and 5678/2015 by confirmed figures; 510/2014 recorded as net and excluded; the opening
reserves of 1225/2018 and 609/2023), with the owner deciding 2010/2015's figure (-9.646m). It also found a mechanism no
amendment covered. A triangle restated to carry business taken on in the report year covers that business on both
diagonals of its step, while the opening reserves at 1 January exclude it, so the severity is overstated (1884/2021:
-27.3%%, and -2.2%% with the 839.8m taken on). The owner decided to adjust the opening reserves. The amendment
(%(amended)s) fixes the rule, a census computed before any reading (%(written9)s; %(n9)d records), its readings, and the
register the loader reads (data/opening_reserves_takeon_base.json, test-first). Refit 3 follows both.
''' % V

LEDGER_TEXT = '''
## The eighth census scored, the owner's midday decisions and the ninth amendment (14 September 2026)

- Material, data, repairing: the eighth census's six confirmed errors are repaired through the registers (A4b, %(a4b)s):
  2791/2015 -2.131m, 3010/2018 -4.140m and 382/2017 +7.401m (printed gross triangles); 5678/2015 -8.135m (its 2015 note
  rows are transposed); 2010/2015 -9.646m (owner's decision); 510/2014 net and excluded. Opening reserves 1225/2018
  595.8m and 609/2023 1,171.381m: both adopted figures were the reinsurers' share.
- Material, data, repairing (owner's decision): the take-on base. A triangle restated to carry a take-on on both
  diagonals of its step covers the acquired business, while the 1 January opening reserves exclude it. Largest:
  1884/2021 -27.3%% (839.8m taken on against 73.7m of opening reserves), 3500/2021 +14.2%%, 3500/2019 +10.2%%,
  3500/2022 -11.2%%. The ninth amendment (%(amended)s) and its census (%(n9)d records) settle which records are adjusted.
- Medium, data, recorded: 2010/2015's provisions-text route dropped the brackets of a negative line and overrode the
  models' sign (a scan of every record's routes finds no other); 2791/2015's triangle route read 139,326 as 139.326.
- Medium, data, recorded: 1945/2021 prints two gross prior-year lines that differ beyond tolerance (31,711 in note 16,
  29,652 in note 6); both readings score it undeterminable, and it keeps its figure. 2010/2020, 2010/2022 and 2010/2023
  are errors on their first readings only; 780/2018 and 2008/2023 are undeterminable on their first readings only.
- Low, process, fixed: batch 12's first reader stopped on the spend limit after one record; batch 12b read the other two.
- Low, process, fixed before any reading: the take-on base census's row rule counted each syndicate's own
  year-of-account RITC rows; three dry runs that read no filing for a verdict listed %(dry)s records.
''' % V

write(RUNBOOK, "\n## 1. Refit verification (analysis)", RUNBOOK_BLOCK, "- Eighth census scored (score_error_rate_eighth.py;")
write(PLAN, "\n## Definition of done", PLAN_PARA, "*The ninth amendment (14 September 2026):*")
write(LEDGER, None, LEDGER_TEXT, "## The eighth census scored, the owner's midday decisions and the ninth amendment")
print("runbook (state at %s), PLAN R213 and the ledger: the eighth census and the ninth amendment recorded" % now)
