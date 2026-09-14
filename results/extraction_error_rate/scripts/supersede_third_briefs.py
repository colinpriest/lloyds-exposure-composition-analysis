r"""Set aside the third sample's first briefs, built before any reading with a defect, and note it in the protocol.

make_adjudication_briefs_third.py took "still in the working sample" from every parsed observation, so 2008/2021,
which the take-on register keeps in the corpus but not in the working sample, was briefed as a repaired record. The
script now takes the working sample from adopted_model.load_sample, the draw's own source. This moves the first
briefs, the carry-over decisions, the fresh stems and the batch files to superseded-before-reading-<time>/ and writes
a dated implementation note. It refuses if any first reading of the third sample exists, so the note's "before any
reading" is checked, not asserted. The time is the clock's.

    python supersede_third_briefs.py
"""
import datetime
import glob
import io
import shutil
from pathlib import Path

SCR = Path(__file__).resolve().parent
readings = sorted(glob.glob(str(SCR / "error-rate-verdicts-third*.json")))
if readings:
    raise SystemExit("third-sample readings exist (%s): the briefs cannot be set aside" % readings)
files = [SCR / "error-rate-briefs-third.json", SCR / "error-rate-carry-over-third.json",
         SCR / "error-rate-fresh-stems-third.json"] + [Path(p) for p in glob.glob(str(SCR / "error-rate-briefs-third-batch-*.json"))]
files += [Path(p) for p in glob.glob(str(SCR / "reader-prompt-third-batch-*.txt"))]
present = [f for f in files if f.exists()]
if not present:
    raise SystemExit("nothing to set aside")
now = datetime.datetime.now()
dest = SCR / ("superseded-before-reading-%s" % now.strftime("%H%M%S"))
dest.mkdir()
for f in present:
    shutil.move(str(f), str(dest / f.name))
P = SCR / "error-rate-protocol.md"
raw = io.open(str(P), encoding="utf-8", newline="").read()
TEXT = ("\n## Implementation note 2, 13 September 2026 (written %s), before any reading of the third sample\n\n"
        % now.strftime("%H:%M")
        + "The first briefs for the records read after the repairs were built with a defect: "
          "make_adjudication_briefs_third.py took \"still in the working sample\" from every parsed observation, so "
          "2008/2021, which the take-on register keeps in the corpus but not in the working sample, was briefed as a "
          "repaired record to be read again. The script now takes the working sample from adopted_model.load_sample, "
          "the source the draw used, and the briefs, the carry-over decisions and the batches were rebuilt. The first "
          "files are kept in %s. No reading of the third sample had begun (no first-reading file existed). The draw "
          "itself is unchanged.\n" % dest.name)
io.open(str(P), "a", encoding="utf-8", newline="").write(TEXT.replace("\n", "\r\n") if "\r\n" in raw else TEXT)
print("set aside %d file(s) in %s; protocol note written %s" % (len(present), dest.name, now.strftime("%H:%M")))
