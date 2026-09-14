r"""First readers' prompts for the new sample's records read afresh (protocol, fourth amendment, point 4).

Each prompt is the first readers' instruction as reader-prompt-r209.txt gives it: the brief, pack and page
tool, the protocol's definitions, the triangle recomputation recorded beside the verdict, and the rule
that a reader opens no verdict, verification or result file. Two descriptions follow the pipeline as it
now records a figure's source, and change no definition. The routes R208 introduced (rag_provisions,
rag_provisions_text, the narrative parsers) are named. The recomputation is also asked for where an empty
route's notes carry a code override computed from the models' triangles, which the merge treats as a
triangle's figure (refinement 3).

Writes reader-prompt-after-batch-N.txt for every error-rate-briefs-after-batch-N.json, with the output
path error-rate-verdicts-after-batch-N.json. Each substitution must match exactly once in the template.

    python make_reader_prompts_after.py
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
batches = sorted(glob.glob(str(SCR / "error-rate-briefs-after-batch-*.json")),
                 key=lambda p: int(re.search(r"batch-(\d+)\.json$", p).group(1)))
if not batches:
    raise SystemExit("no error-rate-briefs-after-batch-*.json: run make_adjudication_briefs_after.py first")
for path in batches:
    n = int(re.search(r"batch-(\d+)\.json$", path).group(1))
    k = len(json.load(io.open(path, encoding="utf-8")))
    t = template
    t = once(t, "for a re-reading batch of an extraction error-rate study",
             "for batch %d of the new sample of an extraction error-rate study" % n)
    t = once(t, "For each of 5 sampled records", "For each of %d sampled records" % k)
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
    t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-after-batch-%d.json" % n)
    out = SCR / ("reader-prompt-after-batch-%d.txt" % n)
    io.open(str(out), "w", encoding="utf-8").write(t)
    print("%s: %d record(s) -> error-rate-verdicts-after-batch-%d.json" % (out.name, k, n))
