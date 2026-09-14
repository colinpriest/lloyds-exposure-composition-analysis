r"""First readers' prompts for the take-on census (error-rate-protocol.md, sixth amendment).

The same instruction every earlier first reader had (reader-prompt-r209.txt), with the batch named, the output path
error-rate-verdicts-takeon-batch-N.json, and the amendment's one added question with its output field. Each
substitution must match exactly once in the template.

    python make_reader_prompts_takeon.py
"""
import glob
import io
import json
import os
import re
from pathlib import Path

SCR = Path(__file__).resolve().parent
TEMPLATE = SCR / "reader-prompt-r209.txt"
QUESTION = (
    "CENSUS QUESTION (this batch only). Each record is a year in which its syndicate accepted another syndicate's "
    "liabilities: an accepted reinsurance to close or a loss portfolio transfer (the brief's regime_sources say which; "
    "ritc_* is an RITC acceptance, transfer_* a confirmed inward transfer). Besides the verdict, answer: is the adopted "
    "figure the year's take-on -- the RITC premium received or the reserves transferred in, or a charge dominated by "
    "them -- rather than the change in the estimate for earlier years? Look for the RITC or transfer line in the "
    "technical provisions or claims note, the transferred reserves stated in the report, and whether the adopted "
    "figure equals or is dominated by them. Record it in a field \"takeon_check\": {\"is_takeon\": true | false | null, "
    "\"takeon_amount_m\": <number or null>, \"evidence\": \"<verbatim quotes with pages>\", \"pages\": [<ints>]}. "
    "Answer true only when the filing shows it, false when the filing shows the figure is the development of earlier "
    "years, and null when the filing does not settle it.")


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("template: %r found %d times" % (old[:70], text.count(old)))
    return text.replace(old, new)


template = io.open(str(TEMPLATE), encoding="utf-8").read()
batches = sorted(glob.glob(str(SCR / "error-rate-briefs-takeon-batch-*.json")),
                 key=lambda p: int(re.search(r"batch-(\d+)\.json$", p).group(1)))
if not batches:
    raise SystemExit("no error-rate-briefs-takeon-batch-*.json: run make_adjudication_briefs_takeon.py first")
for path in batches:
    n = int(re.search(r"batch-(\d+)\.json$", path).group(1))
    k = len(json.load(io.open(path, encoding="utf-8")))
    t = template
    t = once(t, "for a re-reading batch of an extraction error-rate study",
             "for batch %d of the take-on census of an extraction error-rate study" % n)
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
    t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)
    t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-takeon-batch-%d.json" % n)
    t = once(t, "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\"}",
             "\"reasoning\": \"<short: why the verdict follows, any conflict between the filing's own figures>\",\n"
             " \"takeon_check\": {\"is_takeon\": true | false | null, \"takeon_amount_m\": <number or null>, "
             "\"evidence\": \"<quotes with pages>\", \"pages\": [<ints>]}}")
    t = once(t, "\nRULES:", "\n" + QUESTION + "\n\nRULES:")
    out = SCR / ("reader-prompt-takeon-batch-%d.txt" % n)
    io.open(str(out), "w", encoding="utf-8").write(t)
    print("%s: %d record(s) -> error-rate-verdicts-takeon-batch-%d.json" % (out.name, k, n))
