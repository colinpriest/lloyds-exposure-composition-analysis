r"""The second reader's tools for the ninth amendment's take-on base census.

  second_read.py         --ninth: the brief from error-rate-briefs-ninth.json, the first reading from the ninth batches
                         (or the merged error-rate-verdicts-ninth.json); for a record whose readings the carry-over kept,
                         the eighth census's two readings and the carried answers (error-rate-carry-over-ninth.json)
  record_second_read.py  --ninth: error-rate-census-ninth.json's stems, second readings to
                         error-rate-verification-ninth.json, each with --finding takeon_base=true|false|null,
                         --takeon-amount, --gross-opening and --carried (where the business sits)

Every anchor must match exactly once; otherwise the script writes nothing.

    python patch_second_read_ninth.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
SECOND = SCR / "second_read.py"
RECORD = SCR / "record_second_read.py"

SECOND_SUBS = [
    ('ap.add_argument("--eighth", action="store_true",\n',
     'ap.add_argument("--ninth", action="store_true",\n'
     '                help="the ninth amendment\'s take-on base census (error-rate-briefs-ninth.json, its readings; a record "\n'
     '                     "whose readings were carried shows the eighth census\'s two readings and the carried answers)")\n'
     'ap.add_argument("--eighth", action="store_true",\n'),
    ('tag = ("-eighth" if a.eighth else',
     'tag = ("-ninth" if a.ninth else "-eighth" if a.eighth else'),
    ('if a.eighth and first is None:\n',
     'if a.ninth and first is None:\n'
     '    decisions = json.load(io.open(str(SCR / "error-rate-carry-over-ninth.json"), encoding="utf-8"))["decisions"]\n'
     '    d = next((x for x in decisions if x["stem"] == a.stem), None)\n'
     '    if d and d["carry"]:\n'
     '        e1 = next(v for v in json.load(io.open(str(SCR / "error-rate-verdicts-eighth.json"), encoding="utf-8")) if v["stem"] == a.stem)\n'
     '        e2 = next(v for v in json.load(io.open(str(SCR / "error-rate-verification-eighth.json"), encoding="utf-8")) if v["stem"] == a.stem)\n'
     '        first = {"carried_from": "eighth census", "carry_decision": d, "eighth_first_reading": e1,\n'
     '                 "eighth_second_reading": e2, "pages": sorted(set((e1.get("pages") or []) + (e2.get("pages") or [])))}\n'
     'if a.eighth and first is None:\n'),
    ('if a.eighth:\n    print("  census parts %s" % brief.get("census_parts"))\n',
     'if a.eighth or a.ninth:\n    print("  census parts %s" % brief.get("census_parts"))\n'),
]
RECORD_SUBS = [
    ('ap.add_argument("--gross-opening", type=float, default=None)\n',
     'ap.add_argument("--gross-opening", type=float, default=None)\n'
     '# the ninth amendment\'s take-on base census: error-rate-census-ninth.json\'s stems, second readings to\n'
     '# error-rate-verification-ninth.json, each with --finding takeon_base=..., the amount, the gross opening and where the\n'
     '# business sits\n'
     'ap.add_argument("--ninth", action="store_true")\n'
     'ap.add_argument("--carried", default=None)\n'),
    ('if sum((a.tail, a.after, a.census, a.takeon, a.passing, a.third, a.eighth)) > 1:\n'
     '    raise SystemExit("give at most one of --after, --tail, --census, --takeon, --passing, --third and --eighth")\n',
     'if sum((a.tail, a.after, a.census, a.takeon, a.passing, a.third, a.eighth, a.ninth)) > 1:\n'
     '    raise SystemExit("give at most one of --after, --tail, --census, --takeon, --passing, --third, --eighth and --ninth")\n'),
    ('OUT = SCR / (a.out or ("error-rate-verification-eighth.json" if a.eighth else\n',
     'OUT = SCR / (a.out or ("error-rate-verification-ninth.json" if a.ninth else\n'
     '                       "error-rate-verification-eighth.json" if a.eighth else\n'),
    ('SAMPLE = SCR / ("error-rate-census-eighth.json" if a.eighth else\n',
     'SAMPLE = SCR / ("error-rate-census-ninth.json" if a.ninth else\n'
     '                "error-rate-census-eighth.json" if a.eighth else\n'),
    ('listed = a.census or a.takeon or a.passing or a.eighth\n',
     'listed = a.census or a.takeon or a.passing or a.eighth or a.ninth\n'),
    ('rows.append(row)\n',
     'if a.ninth:\n'
     '    given = dict(f.split("=", 1) for f in a.finding)\n'
     '    if sorted(given) != ["takeon_base"] or given["takeon_base"] not in ("true", "false", "null"):\n'
     '        raise SystemExit("a ninth-census reading needs --finding takeon_base=true|false|null")\n'
     '    if not (a.carried or "").strip():\n'
     '        raise SystemExit("a ninth-census reading needs --carried: where the adopted figure\'s table or line carries the business")\n'
     '    row["census_check"] = {"takeon_base": {"finding": {"true": True, "false": False, "null": None}[given["takeon_base"]],\n'
     '                                           "takeon_amount_m": a.takeon_amount, "gross_opening_m": a.gross_opening,\n'
     '                                           "carried": a.carried}}\n'
     'rows.append(row)\n'),
]


def patched(path, subs):
    text = io.open(str(path), encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in subs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if text.count(old) != 1:
            raise SystemExit("%s: anchor found %d times, nothing written: %r" % (path.name, text.count(old), old[:90]))
        text = text.replace(old, new)
    return text


out = {SECOND: patched(SECOND, SECOND_SUBS), RECORD: patched(RECORD, RECORD_SUBS)}
for path, text in out.items():
    io.open(str(path), "w", encoding="utf-8", newline="").write(text)
print("patched %s" % ", ".join(p.name for p in out))
