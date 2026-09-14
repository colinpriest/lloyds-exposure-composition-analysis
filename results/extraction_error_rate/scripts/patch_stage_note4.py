r"""stage_extraction_error_rate.py: implementation note 4 (2003/2018's reading on the sixth amendment's question and
the owner's decision), and the take-on base census's dry runs counted from their logs.

Each replacement must match exactly once, or nothing is written.

    python patch_stage_note4.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
TARGET = SCR / "stage_extraction_error_rate.py"

REPLACEMENTS = [
    ('"error-rate-census-ninth-result.json", "ninth-repairs-draft.json"]',
     '"error-rate-census-ninth-result.json", "ninth-repairs-draft.json",\n'
     '                         "error-rate-briefs-ninth-sixth-2003.json", "reader-prompt-ninth-sixth-2003.txt",\n'
     '                         "error-rate-verdicts-ninth-sixth-2003.json"]'),
    ('                     "patch_stage_ninth.py"]',
     '                     "patch_stage_ninth.py", "list_ninth_outcomes.py", "view_ninth_remaining.py",\n'
     '                     "view_json_stem.py", "make_brief_2003_sixth.py", "register_2003_takeon.py",\n'
     '                     "patch_stage_note4.py"]'),
    ('rules9 = ", ".join("%s %d" % (rule, len(v)) for rule, v in census9_file["parts"].items())\n',
     'rules9 = ", ".join("%s %d" % (rule, len(v)) for rule, v in census9_file["parts"].items())\n'
     'dry9 = []\n'
     'for name in ("census-ninth-dryrun.log", "census-ninth-dryrun2.log", "census-ninth-dryrun3.log"):\n'
     '    mm = re.search(r"^listed (\\d+):", io.open(str(SCR / name), encoding="utf-8").read(), re.M)\n'
     '    if not mm:\n'
     '        raise SystemExit("%s: no \'listed N:\' line" % name)\n'
     '    dry9.append(mm.group(1))\n'
     '# implementation note 4: 2003/2018 read once more on the sixth amendment\'s question, then excluded by the owner\n'
     'note4 = load("error-rate-verdicts-ninth-sixth-2003.json")\n'
     'note4_answer = ((note4[0].get("census_check") or {}).get("takeon_triangle") or {}) if len(note4) == 1 else {}\n'
     'if len(note4) != 1 or note4[0].get("stem") != "syndicate_2003_2018" or note4_answer.get("finding") is not True:\n'
     '    raise SystemExit("implementation note 4\'s reading is not the take-on finding the README describes")\n'
     'if "2003_2018" not in an_takeons or "syndicate_2003_2018" not in no_transfer9:\n'
     '    raise SystemExit("2003/2018 is not where the README puts it (the committed take-on register, no covered transfer)")\n'),
    ('refit 3 ({rules9}; a record may meet several). Two dry runs tightened the row rule before any reading.',
     'refit 3 ({rules9}; a record may meet several). On dry runs that read no filing for a verdict, the row rule was\n'
     'tightened twice: {dry9[0]} records listed, then {dry9[1]}, then {dry9[2]}.'),
    ('transfer is under 5% of the opening reserves; and {listing(other9)}.\n',
     'transfer is under 5% of the opening reserves; and {listing(other9)}.\n'
     '\n'
     '2003/2018 is one of the records with no covered transfer: both readings find Syndicate 1209\'s reinsurance to close\n'
     'entering its triangle\'s step without restatement, which point 2 leaves to the sixth amendment. Under\n'
     'implementation note 4 it was read once more, on that amendment\'s question (`error-rate-briefs-ninth-sixth-2003.json`,\n'
     '`reader-prompt-ninth-sixth-2003.txt`, `error-rate-verdicts-ninth-sixth-2003.json`). That reading and the editor\'s\n'
     'both find the take-on dominating the figure, and on the owner\'s decision of 14 September 2026 the record is\n'
     'excluded as a take-on (`data/takeon_not_development.json`, analysis repository {an_head}).\n'),
    ('census\'s in %s (and batch 12b of two), and the take-on base census\'s in %s.',
     'census\'s in %s (and batch 12b of two), and the take-on base census\'s in %s, with one further reader for\n'
     '  2003/2018 (implementation note 4).'),
    ('reader prompts, first and second readings, result and draft; `ninth-census/packs/` holds its evidence packs.',
     'reader prompts, first and second readings, result and draft, and implementation note 4\'s brief, prompt and\n'
     '  reading of 2003/2018; `ninth-census/packs/` holds its evidence packs.'),
]

raw = io.open(str(TARGET), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
for old, new in REPLACEMENTS:
    n = text.count(old)
    if n != 1:
        raise SystemExit("expected once, found %d: %r" % (n, old[:90]))
    text = text.replace(old, new)
io.open(str(TARGET), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print("patched %d sites in %s" % (len(REPLACEMENTS), TARGET.name))
