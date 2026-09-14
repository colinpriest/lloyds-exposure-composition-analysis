r"""First readers' prompts for the records the fifth amendment has read after the repairs (the third sample, the
entrants and the repaired records).

The same instruction every earlier first reader had (reader-prompt-r209.txt), with the batch named and the output
path error-rate-verdicts-third-batch-N.json. Each substitution must match exactly once in the template.

    python make_reader_prompts_third.py
"""
import glob
import io
import json
import os
import re
from pathlib import Path

SCR = Path(__file__).resolve().parent
TEMPLATE = SCR / "reader-prompt-r209.txt"


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("template: %r found %d times" % (old[:70], text.count(old)))
    return text.replace(old, new)


template = io.open(str(TEMPLATE), encoding="utf-8").read()
batches = sorted(glob.glob(str(SCR / "error-rate-briefs-third-batch-*.json")),
                 key=lambda p: int(re.search(r"batch-(\d+)\.json$", p).group(1)))
if not batches:
    raise SystemExit("no error-rate-briefs-third-batch-*.json: run make_adjudication_briefs_third.py first")
for path in batches:
    n = int(re.search(r"batch-(\d+)\.json$", path).group(1))
    k = len(json.load(io.open(path, encoding="utf-8")))
    t = template
    t = once(t, "for a re-reading batch of an extraction error-rate study",
             "for batch %d of the third sample of an extraction error-rate study" % n)
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
    if any((b.get("route") or {}).get("source") == "confirmed_figure"
           for b in json.load(io.open(path, encoding="utf-8"))):
        t = once(t, "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED.",
                 "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED. A route whose source is confirmed_figure "
                 "carries a figure that two earlier readings of the filing confirmed and the loader adopts in "
                 "place of the extraction's; its figure_kind says whether it was read from a printed triangle "
                 "(triangle) or is a figure the filing states (stated). Check it against the filing like any "
                 "other adopted figure, and where its figure_kind is triangle also record the triangle "
                 "recomputation.")
    t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)
    t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-third-batch-%d.json" % n)
    out = SCR / ("reader-prompt-third-batch-%d.txt" % n)
    io.open(str(out), "w", encoding="utf-8").write(t)
    print("%s: %d record(s) -> error-rate-verdicts-third-batch-%d.json" % (out.name, k, n))
