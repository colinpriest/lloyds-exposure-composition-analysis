r"""The tail stratum's brief builder and scorer, brought to the state the samples since have used; and the protocol's
implementation note saying so, written before the tail is drawn.

make_adjudication_briefs_tail.py
  - applies the loader's registers to each record's model block as load_and_classify does (the confirmed figure, then
    the confirmed opening reserves), and carries a confirmed route's figure_kind, basis and register (implementation
    note 1 did this for the third sample's briefs);
  - resolves the filing's PDF as filing_pages.py does (the filed PDF, else the HTML report's conversion);
  - carries readings over from every sample and census read since the fourth amendment, latest first, on the fourth
    amendment's rule (point 3): nothing the verdict was read against has changed.
score_error_rate_tail.py
  - takes a carried reading, and its second reading, from whichever of those it was carried from;
  - compares routes with each record's latest replay log (log_blocks_after_r213, as the third sample's merge does).

Each anchor must match once; line endings are kept.

    python patch_tail_after_eighth.py
"""
import datetime
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent


def patch(name, edits, marker):
    p = SCR / name
    raw = io.open(str(p), encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    if marker in t:
        raise SystemExit("%s already patched" % name)
    for old, new in edits:
        if t.count(old) != 1:
            raise SystemExit("%s: anchor found %d times: %r" % (name, t.count(old), old[:90]))
        t = t.replace(old, new)
    io.open(str(p), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
    print("%s: %d edits" % (name, len(edits)))


READ_SETS = '''READ_SETS = (("eighth census", "error-rate-briefs-eighth.json", "error-rate-verdicts-eighth.json"),
             ("third sample", "error-rate-briefs-third.json", "error-rate-verdicts-third.json"),
             ("take-on census", "error-rate-briefs-takeon.json", "error-rate-verdicts-takeon.json"),
             ("found in passing", "error-rate-briefs-passing.json", "error-rate-verdicts-passing.json"),
             ("census", "error-rate-briefs-census.json", "error-rate-verdicts-census.json"),
             ("second sample", "error-rate-briefs-after.json", "error-rate-verdicts-after.json"),
             ("first sample", "error-rate-briefs.json", "error-rate-verdicts.json"))
'''

patch("make_adjudication_briefs_tail.py", [
    ("obs = {\"%s_%s\" % (o[\"syndicate\"], o[\"year\"]): o for o in cur[\"observations\"]}\n",
     "obs = {\"%s_%s\" % (o[\"syndicate\"], o[\"year\"]): o for o in cur[\"observations\"]}\n"
     "# the figure and the opening reserves the loader adopts: its registers are applied as load_and_classify applies them\n"
     "# (implementation note 3; implementation note 1 did the same for the third sample)\n"
     "CONFIRMED = ra.load_pyd_confirmed_figures()\n"
     "OPENINGS = ra.load_opening_reserves_confirmed()\n"
     "PDFS = Path(r\"D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs\")\n"
     "CONVERTED = Path(r\"D:/dev/lloyds_reserve_stress_testing/pdf_extraction/html_converted\")\n"
     "\n"
     "\n"
     "def filing_pdf(stem):\n"
     "    \"\"\"The PDF the packs' page numbers refer to (filing_pages.py): the filed PDF, else the HTML report's conversion.\"\"\"\n"
     "    for d in (PDFS, CONVERTED):\n"
     "        if (d / (\"%s.pdf\" % stem)).exists():\n"
     "            return str(d / (\"%s.pdf\" % stem))\n"
     "    return None\n"),
    ("    cm = copy.deepcopy(data[\"models\"][ck])\n    route = cm.get(\"_pyd_route\") or {}\n",
     "    cm = copy.deepcopy(data[\"models\"][ck])\n"
     "    if key in CONFIRMED:\n"
     "        cm = ra.apply_confirmed_figure(cm, CONFIRMED[key])\n"
     "    if key in OPENINGS:\n"
     "        cm = ra.apply_confirmed_opening(cm, OPENINGS[key])\n"
     "    route = cm.get(\"_pyd_route\") or {}\n"),
    ("        \"filing_pdf\": \"D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/%s.pdf\" % stem,\n",
     "        \"filing_pdf\": filing_pdf(stem),\n"),
    ("        \"route\": {k: route.get(k) for k in (\"source\", \"value\", \"model_value\", \"triangle_type\",\n"
     "                                             \"triangle_units\", \"triangle_source_page\", \"note\")},\n",
     "        \"route\": dict({k: route.get(k) for k in (\"source\", \"value\", \"model_value\", \"triangle_type\",\n"
     "                                                  \"triangle_units\", \"triangle_source_page\", \"note\")},\n"
     "                      **({k: route.get(k) for k in (\"figure_kind\", \"basis\", \"register\")}\n"
     "                         if route.get(\"source\") == ra.CONFIRMED_FIGURE_SOURCE else {})),\n"),
    ("# the sample a tail record was read in, latest first: its briefs and its merged rows (for the figure source)\n"
     "PRIOR = ((\"second sample\", load(SCR / \"error-rate-sample-after.json\")[\"primary\"][\"stems\"],\n"
     "          {b[\"stem\"]: b for b in load(SCR / \"error-rate-briefs-after.json\")},\n"
     "          {r[\"stem\"]: r[\"figure_source\"] for r in load(SCR / \"error-rate-verdicts-after.json\")}),\n"
     "         (\"first sample\", load(SCR / \"error-rate-sample.json\")[\"primary\"][\"stems\"],\n"
     "          {b[\"stem\"]: b for b in load(SCR / \"error-rate-briefs.json\")},\n"
     "          {r[\"stem\"]: r[\"figure_source\"] for r in load(SCR / \"error-rate-verdicts.json\")}))\n",
     "# every sample and census a tail record may have been read in, latest first: its briefs and its merged rows (for the\n"
     "# figure source); the fourth amendment's rule (point 3) applied to all of them (implementation note 3)\n"
     + READ_SETS +
     "PRIOR = []\n"
     "for _name, _briefs, _merged in READ_SETS:\n"
     "    if (SCR / _briefs).exists() and (SCR / _merged).exists():\n"
     "        _b = {b[\"stem\"]: b for b in load(SCR / _briefs)}\n"
     "        _src = {r[\"stem\"]: r[\"figure_source\"] for r in load(SCR / _merged)}\n"
     "        PRIOR.append((_name, sorted(set(_b) & set(_src)), _b, _src))\n"),
    ("print(\"tail %d; carried over %d (%s); read afresh %d in %d batch(es)\"\n"
     "      % (len(briefs), sum(1 for d in decisions if d[\"carry_over\"]),\n"
     "         {k: sum(1 for d in decisions if d[\"carried_from\"] == k) for k in (\"second sample\", \"first sample\")},\n",
     "print(\"tail %d; carried over %d (%s); read afresh %d in %d batch(es)\"\n"
     "      % (len(briefs), sum(1 for d in decisions if d[\"carry_over\"]),\n"
     "         {k: sum(1 for d in decisions if d[\"carried_from\"] == k) for k, _b, _m in READ_SETS},\n"),
], "READ_SETS = ")

patch("score_error_rate_tail.py", [
    ("import score_error_rate_after_rerun as rr  # noqa: E402\n",
     "import score_error_rate_after_rerun as rr  # noqa: E402\n"
     "from score_error_rate_third import log_blocks_after_r213  # noqa: E402\n"),
    ("FROM = {\"second sample\": (SCR / \"error-rate-verdicts-after.json\", SCR / \"error-rate-verification-after.json\"),\n"
     "        \"first sample\": (SCR / \"error-rate-verdicts.json\", SCR / \"error-rate-verification.json\")}\n",
     "# every sample and census a tail reading may be carried from (implementation note 3)\n"
     "FROM = {name: paths for name, paths in (\n"
     "    (\"eighth census\", (SCR / \"error-rate-verdicts-eighth.json\", SCR / \"error-rate-verification-eighth.json\")),\n"
     "    (\"third sample\", (SCR / \"error-rate-verdicts-third.json\", SCR / \"error-rate-verification-third.json\")),\n"
     "    (\"take-on census\", (SCR / \"error-rate-verdicts-takeon.json\", SCR / \"error-rate-verification-takeon.json\")),\n"
     "    (\"found in passing\", (SCR / \"error-rate-verdicts-passing.json\", SCR / \"error-rate-verification-passing.json\")),\n"
     "    (\"census\", (SCR / \"error-rate-verdicts-census.json\", SCR / \"error-rate-verification-census.json\")),\n"
     "    (\"second sample\", (SCR / \"error-rate-verdicts-after.json\", SCR / \"error-rate-verification-after.json\")),\n"
     "    (\"first sample\", (SCR / \"error-rate-verdicts.json\", SCR / \"error-rate-verification.json\")))\n"
     "    if paths[0].exists()}\n"),
    ("    overruled = ser.overruled_stems()\n    blocks = rr.log_blocks()\n    rows, problems = {}, []\n",
     "    overruled = ser.overruled_stems()\n    blocks = log_blocks_after_r213()\n    rows, problems = {}, []\n"),
    ("    for name, (_merged, verification) in FROM.items():\n"
     "        carried_second += [dict(v, carried_over_from=verification.name) for v in load(verification)\n"
     "                           if carry.get(v[\"stem\"]) == name]\n",
     "    for name, (_merged, verification) in FROM.items():\n"
     "        if not verification.exists():\n"
     "            continue\n"
     "        carried_second += [dict(v, carried_over_from=verification.name) for v in load(verification)\n"
     "                           if carry.get(v[\"stem\"]) == name]\n"),
    ("    overruled = ser.overruled_stems()\n    blocks = rr.log_blocks()\n    seen, problems = {}, []\n",
     "    overruled = ser.overruled_stems()\n    blocks = log_blocks_after_r213()\n    seen, problems = {}, []\n"),
], "log_blocks_after_r213")

NOTE = '''
## Implementation note 3, 14 September 2026 (written %s), before the tail stratum is drawn

The tail's brief builder and scorer were written before the third sample and the censuses. Before the tail is drawn
from refit 3, make_adjudication_briefs_tail.py applies the loader's registers to each record as load_and_classify
applies them (the confirmed figure, then the confirmed opening reserves; implementation note 1 did the same for the third
sample), and resolves the filing's PDF as the packs do. A tail record keeps the readings of the latest sample or census
that read it, the eighth census and the third sample included, under the fourth amendment's rule (point 3): nothing its
verdict was read against has changed. score_error_rate_tail.py takes the carried reading and its second reading from
that sample or census, and compares a route with the record's latest replay log, as the third sample's merge does. No
part of the protocol changes.
'''

proto = SCR / "error-rate-protocol.md"
raw = io.open(str(proto), encoding="utf-8", newline="").read()
if "## Implementation note 3" in raw:
    raise SystemExit("implementation note 3 is already written")
if (SCR / "error-rate-tail.json").exists():
    raise SystemExit("the tail is drawn already: the note must come first")
text = NOTE % datetime.datetime.now().strftime("%H:%M")
io.open(str(proto), "a", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if "\r\n" in raw else text)
print("error-rate-protocol.md: implementation note 3 written")
