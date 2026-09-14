r"""First readers' prompt for the records found in passing (error-rate-protocol.md, seventh amendment, point 2).

The instruction every earlier first reader had (reader-prompt-r209.txt), with the batch named and the output path
error-rate-verdicts-passing-batch-1.json. Each substitution must match exactly once in the template.

    python make_reader_prompts_passing.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
TEMPLATE = SCR / "reader-prompt-r209.txt"
BATCH = SCR / "error-rate-briefs-passing-batch-1.json"


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("template: %r found %d times" % (old[:70], text.count(old)))
    return text.replace(old, new)


k = len(json.load(io.open(str(BATCH), encoding="utf-8")))
t = io.open(str(TEMPLATE), encoding="utf-8").read()
t = once(t, "for a re-reading batch of an extraction error-rate study",
         "for a batch of records found in passing in an extraction error-rate study")
t = once(t, "For each of 5 sampled records", "For each of %d records" % k)
t = once(t, "Briefs for your 5 records:", "Briefs for your %d records:" % k)
t = once(t, "error-rate-briefs-r209.json", BATCH.name)
t = once(t, "(source rag_triangle = computed from a claims development triangle; None = a model's reading of a note or narrative)",
         "(source rag_triangle = computed from a claims development triangle; rag_provisions, rag_provisions_text "
         "or a rag_..._narrative source = the filing's provisions note, provisions text or narrative, read by the "
         "pipeline's own parsers; None = a model's reading of a note or narrative, or, where the notes carry a "
         "CODE OVERRIDE computed from a triangle, the models' own triangles)")
t = once(t, "- Where the route is rag_triangle, also record the triangle recomputation",
         "- Where the route is rag_triangle, or the notes carry a CODE OVERRIDE computed from a triangle, also "
         "record the triangle recomputation")
t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)
t = once(t, "error-rate-verdicts-r209.json", "error-rate-verdicts-passing-batch-1.json")
out = SCR / "reader-prompt-passing-batch-1.txt"
io.open(str(out), "w", encoding="utf-8").write(t)
print("%s: %d record(s) -> error-rate-verdicts-passing-batch-1.json" % (out.name, k))
