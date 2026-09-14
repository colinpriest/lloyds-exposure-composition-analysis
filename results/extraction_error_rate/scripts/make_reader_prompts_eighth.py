r"""First readers' prompts for the eighth amendment's census.

The same instruction every earlier first reader had (reader-prompt-r209.txt, with the third sample's substitutions),
the batch named, the output path error-rate-verdicts-eighth-batch-N.json, and the amendment's census questions: each
brief's census_parts name the questions its record answers, in a field census_check. Each substitution must match
exactly once in the template.

    python make_reader_prompts_eighth.py
"""
import glob
import io
import json
import os
import re
from pathlib import Path

SCR = Path(__file__).resolve().parent
TEMPLATE = SCR / "reader-prompt-r209.txt"
QUESTIONS = """CENSUS QUESTIONS (this batch only). Each brief names its census_parts and, in census_reasons, what the scan
that listed the record found. Besides the verdict, answer every question the record's census_parts name, in a field
"census_check" holding one object per part: {"<part>": {"finding": true | false | null, "evidence": "<verbatim quotes
with pages>", "pages": [<ints>]}}, adding "gross_opening_m" for opening and "takeon_amount_m" for takeon_triangle.
Answer true only when the filing shows the mechanism in this record, false when the filing shows it is absent, and
null when the filing does not settle it.
- movement: is the development table the adopted figure comes from, or the gross table the filing prints, a table of
  movements (each row after the first a year's change, so a column's estimate is its first row plus the movements)
  that the adopted figure reads as if it held cumulative estimates? true when it does; false when the table is
  cumulative, or is a movement table read as one.
- transposed: where the adopted figure is a provisions note's prior-year line ('change in prior year provisions',
  'claims incurred in prior underwriting years' or similar), does that line hold the current year of account's claims
  rather than the earlier years' movement? Compare its gross value with the report year's first-year estimate in the
  filing's own gross triangle, and its comparative with the previous year's. true when the rows are transposed.
- net_table: is the table or statement the adopted figure comes from net of reinsurance (for example 'after
  reinsurance recoveries') where the record claims gross? Compare its reserves with gross and net claims outstanding.
  true when it is net.
- provisions_row: the pipeline read the adopted figure from a row of a provisions or segmental table (census_reasons
  names the row). true when that row is not a movement in the estimate of earlier years' claims (for example a
  premium, a balance, or a class whose name contains 'prior year').
- opening: are the adopted opening reserves something other than the gross claims outstanding at 1 January of the
  report year (for example the reinsurers' share, a net figure, another date's balance or another unit)? true when
  they are; give gross_opening_m, the gross figure in millions of the report's currency, whenever the filing prints it.
- takeon_triangle: the filing records a transfer into the syndicate in the report year (an accepted reinsurance to
  close or a portfolio transfer; census_reasons quote what the scan found). Does the transferred business enter the
  triangle's step from the previous diagonal to the latest for underwriting years up to t-2, so that the adopted
  figure is dominated by the take-on (more than half of it) rather than the change in the estimate for earlier years?
  Check whether the table restates earlier diagonals to include the transferred business, which column carries it,
  and the reserves the report says were transferred. true only when the filing shows the take-on dominates the figure;
  false when the filing shows it does not enter the step, or is small beside it, or that no transfer into the
  syndicate happened in the report year; give takeon_amount_m, the transferred amount the filing states."""


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("template: %r found %d times" % (old[:70], text.count(old)))
    return text.replace(old, new)


template = io.open(str(TEMPLATE), encoding="utf-8").read()
batches = sorted(glob.glob(str(SCR / "error-rate-briefs-eighth-batch-*.json")),
                 key=lambda p: int(re.search(r"batch-(\d+)\.json$", p).group(1)))
if not batches:
    raise SystemExit("no error-rate-briefs-eighth-batch-*.json: run make_census_eighth.py first")
for path in batches:
    n = int(re.search(r"batch-(\d+)\.json$", path).group(1))
    rows = json.load(io.open(path, encoding="utf-8"))
    k = len(rows)
    t = template
    t = once(t, "for a re-reading batch of an extraction error-rate study",
             "for batch %d of the eighth amendment's census of an extraction error-rate study" % n)
    t = once(t, "For each of 5 sampled records", "For each of %d records" % k)
    t = once(t, "Briefs for your 5 records:", "Briefs for your %d records:" % k)
    t = once(t, "error-rate-briefs-r209.json", os.path.basename(path))
    t = once(t, "(source rag_triangle = computed from a claims development triangle; None = a model's reading of a note or narrative)",
             "(source rag_triangle = computed from a claims development triangle; rag_provisions, rag_provisions_text "
             "or a rag_..._narrative source = the filing's provisions note, provisions text or narrative, read by the "
             "pipeline's own parsers; None = a model's reading of a note or narrative, or, where the notes carry a "
             "CODE OVERRIDE computed from a triangle, the models' own triangles)")
    t = once(t, "- Where the route is rag_triangle, also record the triangle recomputation",
             "- Where the route is rag_triangle, or the notes carry a CODE OVERRIDE computed from a triangle, also "
             "record the triangle recomputation")
    if any((b.get("route") or {}).get("source") == "confirmed_figure" for b in rows):
        t = once(t, "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED.",
                 "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED. A route whose source is confirmed_figure "
                 "carries a figure that two earlier readings of the filing confirmed and the loader adopts in "
                 "place of the extraction's; its figure_kind says whether it was read from a printed triangle "
                 "(triangle) or is a figure the filing states (stated). Check it against the filing like any "
                 "other adopted figure, and where its figure_kind is triangle also record the triangle "
                 "recomputation.")
    t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)
    t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-eighth-batch-%d.json" % n)
    t = once(t, "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\"}",
             "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\",\n"
             " \"census_check\": {\"<part>\": {\"finding\": true | false | null, \"evidence\": \"<quotes with pages>\", "
             "\"pages\": [<ints>]}}}")
    t = once(t, "\nRULES:", "\n" + QUESTIONS + "\n\nRULES:")
    out = SCR / ("reader-prompt-eighth-batch-%d.txt" % n)
    io.open(str(out), "w", encoding="utf-8").write(t)
    print("%s: %d record(s), parts %s -> error-rate-verdicts-eighth-batch-%d.json"
          % (out.name, k, sorted({p for b in rows for p in b["census_parts"]}), n))
