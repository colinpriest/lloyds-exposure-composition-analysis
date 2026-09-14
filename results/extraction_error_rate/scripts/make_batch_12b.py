r"""Batch 12b of the eighth census: the two records whose first reading batch 12 never wrote (609/2023, 780/2018).

Batch 12's reader stopped on the spend limit after writing 5678/2015 only. This writes the two records' briefs to
error-rate-briefs-eighth-batch-12b.json, and batch 12's reader prompt, pointed at those briefs and at
error-rate-verdicts-eighth-batch-12b.json, to reader-prompt-eighth-batch-12b.txt. It refuses if batch 12's verdicts
already cover either record, or if any text it replaces is not in the prompt exactly once.

    python make_batch_12b.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
STEMS = ["syndicate_609_2023", "syndicate_780_2018"]
briefs = json.load(io.open(str(SCR / "error-rate-briefs-eighth-batch-12.json"), encoding="utf-8"))
done = {v["stem"] for v in json.load(io.open(str(SCR / "error-rate-verdicts-eighth-batch-12.json"), encoding="utf-8"))}
if done & set(STEMS):
    raise SystemExit("batch 12 already has a reading for %s" % sorted(done & set(STEMS)))
keep = [b for b in briefs if b["stem"] in STEMS]
if [b["stem"] for b in keep] != STEMS:
    raise SystemExit("batch 12's briefs do not hold both records")
prompt = io.open(str(SCR / "reader-prompt-eighth-batch-12.txt"), encoding="utf-8").read()
subs = [("batch 12 of", "batch 12b of"), ("For each of 3 records", "For each of 2 records"),
        ("Briefs for your 3 records", "Briefs for your 2 records"),
        ("error-rate-briefs-eighth-batch-12.json", "error-rate-briefs-eighth-batch-12b.json"),
        ("a JSON list of 3 objects", "a JSON list of 2 objects"),
        ("error-rate-verdicts-eighth-batch-12.json", "error-rate-verdicts-eighth-batch-12b.json")]
for old, new in subs:
    if prompt.count(old) != 1:
        raise SystemExit("the prompt holds %r %d times, not once" % (old, prompt.count(old)))
    prompt = prompt.replace(old, new)
io.open(str(SCR / "error-rate-briefs-eighth-batch-12b.json"), "w", encoding="utf-8", newline="").write(
    json.dumps(keep, indent=1, ensure_ascii=False))
io.open(str(SCR / "reader-prompt-eighth-batch-12b.txt"), "w", encoding="utf-8", newline="").write(prompt)
print("wrote the briefs and the prompt for batch 12b: %s" % STEMS)
