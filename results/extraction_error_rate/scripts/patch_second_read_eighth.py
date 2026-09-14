r"""second_read.py and record_second_read.py take --eighth: the eighth amendment's census.

second_read.py --eighth shows the census brief (with its parts and the scan's reasons) and the first reading: the
census's own batch reading, or, for a record whose first reading the carry-over kept, that reading from the sample or
census it was read in (error-rate-carry-over-eighth.json).

record_second_read.py --eighth records into error-rate-verification-eighth.json, and needs one --finding PART=...
for every census part the record sits in (with --gross-opening for opening, --takeon-amount for takeon_triangle).

Each anchor must match exactly once; line endings are kept.

    python patch_second_read_eighth.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent


def patch(name, edits):
    p = SCR / name
    raw = io.open(str(p), encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    if "--eighth" in t:
        raise SystemExit("%s already takes --eighth" % name)
    for old, new in edits:
        if t.count(old) != 1:
            raise SystemExit("%s: anchor found %d times: %r" % (name, t.count(old), old[:80]))
        t = t.replace(old, new)
    io.open(str(p), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
    print("%s: %d edits" % (name, len(edits)))


patch("second_read.py", [
    ("a = ap.parse_args()\n\ntag = (\"-third\" if a.third else ",
     "ap.add_argument(\"--eighth\", action=\"store_true\",\n"
     "                help=\"the eighth amendment's census (error-rate-briefs-eighth.json, its readings; a carried first \"\n"
     "                     \"reading is read from the sample or census it was carried from)\")\n"
     "a = ap.parse_args()\n\ntag = (\"-eighth\" if a.eighth else \"-third\" if a.third else "),
    ("print(\"=\" * 90)\nprint(\"BRIEF  %s  currency",
     "CARRIED_FROM = {\"third sample\": \"-third\", \"take-on census\": \"-takeon\", \"found in passing\": \"-passing\",\n"
     "                \"census\": \"-census\", \"second sample\": \"-after\", \"first sample\": \"\"}\n"
     "if a.eighth and first is None:\n"
     "    decisions = json.load(io.open(str(SCR / \"error-rate-carry-over-eighth.json\"), encoding=\"utf-8\"))[\"decisions\"]\n"
     "    carried = next((d[\"carry_first\"] for d in decisions if d[\"stem\"] == a.stem), None)\n"
     "    if carried:\n"
     "        for v in json.load(io.open(str(SCR / (\"error-rate-verdicts%s.json\" % CARRIED_FROM[carried])), encoding=\"utf-8\")):\n"
     "            if v.get(\"stem\") == a.stem:\n"
     "                first = dict(v, carried_from=carried)\n"
     "print(\"=\" * 90)\nprint(\"BRIEF  %s  currency"),
    ("print(\"  cited %s   loader basis %s   cohort %s\" % (brief[\"cited_pages\"], brief[\"loader_basis\"], brief[\"loader_cohort_scope\"]))\n",
     "print(\"  cited %s   loader basis %s   cohort %s\" % (brief[\"cited_pages\"], brief[\"loader_basis\"], brief[\"loader_cohort_scope\"]))\n"
     "if a.eighth:\n"
     "    print(\"  census parts %s\" % brief.get(\"census_parts\"))\n"
     "    for part, reasons in (brief.get(\"census_reasons\") or {}).items():\n"
     "        for r in reasons:\n"
     "            print(\"    %s: %s\" % (part, r[:600]))\n"),
])

patch("record_second_read.py", [
    ("ap.add_argument(\"--third\", action=\"store_true\")\n",
     "ap.add_argument(\"--third\", action=\"store_true\")\n"
     "# the eighth amendment's census: error-rate-census-eighth.json's stems, second readings to\n"
     "# error-rate-verification-eighth.json, each with the reader's finding for every census part the record sits in\n"
     "ap.add_argument(\"--eighth\", action=\"store_true\")\n"
     "ap.add_argument(\"--finding\", action=\"append\", default=[], help=\"PART=true|false|null, once per census part\")\n"
     "ap.add_argument(\"--gross-opening\", type=float, default=None)\n"),
    ("if sum((a.tail, a.after, a.census, a.takeon, a.passing, a.third)) > 1:\n"
     "    raise SystemExit(\"give at most one of --after, --tail, --census, --takeon, --passing and --third\")\n",
     "if sum((a.tail, a.after, a.census, a.takeon, a.passing, a.third, a.eighth)) > 1:\n"
     "    raise SystemExit(\"give at most one of --after, --tail, --census, --takeon, --passing, --third and --eighth\")\n"),
    ("OUT = SCR / (a.out or (\"error-rate-verification-third.json\" if a.third else\n",
     "OUT = SCR / (a.out or (\"error-rate-verification-eighth.json\" if a.eighth else\n"
     "                       \"error-rate-verification-third.json\" if a.third else\n"),
    ("SAMPLE = SCR / (\"error-rate-briefs-third.json\" if a.third else\n",
     "SAMPLE = SCR / (\"error-rate-census-eighth.json\" if a.eighth else\n"
     "                \"error-rate-briefs-third.json\" if a.third else\n"),
    ("listed = a.census or a.takeon or a.passing\n", "listed = a.census or a.takeon or a.passing or a.eighth\n"),
    ("rows.append(row)\n",
     "if a.eighth:\n"
     "    census_briefs = {b[\"stem\"]: b for b in json.load(io.open(str(SCR / \"error-rate-briefs-eighth.json\"), encoding=\"utf-8\"))}\n"
     "    parts = census_briefs[a.stem][\"census_parts\"]\n"
     "    given = dict(f.split(\"=\", 1) for f in a.finding)\n"
     "    if sorted(given) != sorted(parts) or any(v not in (\"true\", \"false\", \"null\") for v in given.values()):\n"
     "        raise SystemExit(\"an eighth-census reading needs --finding PART=true|false|null for each of %s\" % parts)\n"
     "    row[\"census_check\"] = {p: {\"finding\": {\"true\": True, \"false\": False, \"null\": None}[given[p]]} for p in parts}\n"
     "    if \"opening\" in parts:\n"
     "        row[\"census_check\"][\"opening\"][\"gross_opening_m\"] = a.gross_opening\n"
     "    if \"takeon_triangle\" in parts:\n"
     "        row[\"census_check\"][\"takeon_triangle\"][\"takeon_amount_m\"] = a.takeon_amount\n"
     "rows.append(row)\n"),
])
