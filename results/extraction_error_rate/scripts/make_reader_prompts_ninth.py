r"""First readers' prompts for the ninth amendment's take-on base census.

The same instruction every earlier first reader had (reader-prompt-r209.txt, with the eighth census's substitutions),
the batch named, the output path error-rate-verdicts-ninth-batch-N.json, and the amendment's take-on base question in
a field census_check. Each substitution must match exactly once in the template.

    python make_reader_prompts_ninth.py
"""
import glob
import io
import json
import os
import re
from pathlib import Path

SCR = Path(__file__).resolve().parent
TEMPLATE = SCR / "reader-prompt-r209.txt"
QUESTION = """TAKE-ON BASE QUESTION (this batch only). Each brief names the census part takeon_base and, in census_reasons,
what the scan that listed the record found. Besides the verdict, answer it in a field "census_check":
{"takeon_base": {"finding": true | false | null, "takeon_amount_m": <number or null>, "gross_opening_m": <number or null>,
"carried": "<where the adopted figure's table or line carries the transferred business>", "evidence": "<verbatim quotes
with pages>", "pages": [<ints>]}}.
- takeon_base: severity is the adopted development over the adopted opening reserves (the gross claims outstanding at
  1 January of the report year). Did business come into the syndicate in the report year (an accepted reinsurance to
  close, an RITC, a loss portfolio transfer or another portfolio transfer, booked in the report year's accounts) that
  the adopted figure covers while the adopted opening reserves do not? The adopted figure covers it when its triangle
  carries the transferred business on both diagonals of the step for underwriting years up to t-2 (the table restates
  its earlier diagonals to include the business), or when the adopted figure is a provisions note's prior-year line
  that follows the take-on row in the same roll-forward. It does not cover it when the business sits in the report
  year's own column or in a column or line with no development rows, when the transfer came in an earlier year (the
  opening reserves hold it already) or after the balance sheet date, when the counterparty was a quota-share reinsurer
  of this syndicate's own business, or when the transfer is outward. If the transferred reserves enter a triangle's
  step itself (the table does not restate its earlier diagonals), say so in "carried" and answer false: that is a
  different mechanism. Answer true only when the filing shows a transfer the adopted figure covers and the opening
  reserves exclude; false when the filing shows there is none; null when the filing does not settle it. Whenever there
  is a transfer in the report year, give takeon_amount_m, the gross claims reserves transferred that the filing states,
  in millions of the report's currency (the take-on row of its gross claims reconciliation, or, where it prints an
  adjusted opening balance, that balance less the unadjusted one), and gross_opening_m, the gross claims outstanding
  at 1 January before the transfer. Where only part of the year's transfers is covered (for example loss portfolio
  transfers carried in the report year's own column beside reinsurances to close restated into earlier years, or a
  transfer that replaces business the opening reserves already hold), give the covered part as takeon_amount_m, built
  from the amounts the filing states for each transaction, and say in "carried" how you split it."""


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("template: %r found %d times" % (old[:70], text.count(old)))
    return text.replace(old, new)


template = io.open(str(TEMPLATE), encoding="utf-8").read()
batches = sorted(glob.glob(str(SCR / "error-rate-briefs-ninth-batch-*.json")),
                 key=lambda p: int(re.search(r"batch-(\d+)\.json$", p).group(1)))
if not batches:
    raise SystemExit("no error-rate-briefs-ninth-batch-*.json: run record_carry_ninth.py first")
for path in batches:
    n = int(re.search(r"batch-(\d+)\.json$", path).group(1))
    rows = json.load(io.open(path, encoding="utf-8"))
    k = len(rows)
    if any(b["census_parts"] != ["takeon_base"] for b in rows):
        raise SystemExit("%s: a brief that is not the take-on base census's" % os.path.basename(path))
    t = template
    t = once(t, "for a re-reading batch of an extraction error-rate study",
             "for batch %d of the ninth amendment's take-on base census of an extraction error-rate study" % n)
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
                 "recomputation. Where the brief's opening_registers marks confirmed_opening, the adopted opening "
                 "reserves are a figure two earlier readings confirmed.")
    t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)
    t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-ninth-batch-%d.json" % n)
    t = once(t, "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\"}",
             "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\",\n"
             " \"census_check\": {\"takeon_base\": {\"finding\": true | false | null, \"takeon_amount_m\": <number or null>, "
             "\"gross_opening_m\": <number or null>, \"carried\": \"<where>\", \"evidence\": \"<quotes with pages>\", "
             "\"pages\": [<ints>]}}}")
    t = once(t, "\nRULES:", "\n" + QUESTION + "\n\nRULES:")
    out = SCR / ("reader-prompt-ninth-batch-%d.txt" % n)
    io.open(str(out), "w", encoding="utf-8").write(t)
    print("%s: %d record(s) -> error-rate-verdicts-ninth-batch-%d.json" % (out.name, k, n))
