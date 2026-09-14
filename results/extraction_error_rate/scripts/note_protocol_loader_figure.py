r"""A dated implementation note in error-rate-protocol.md, written before the third sample is drawn.

The third sample's briefs give the adopted figure the loader uses: a record in data/pyd_confirmed_figures.json
carries its confirmed figure, and score_error_rate.figure_source classifies a confirmed figure by its kind. The time
is the clock's. Refuses once the third sample exists.

    python note_protocol_loader_figure.py
"""
import datetime
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
P = SCR / "error-rate-protocol.md"
HEAD = "## Implementation note, 13 September 2026, before the third sample is drawn"
if (SCR / "error-rate-sample-third.json").exists():
    raise SystemExit("the third sample is drawn; this note had to come before it")
raw = io.open(str(P), encoding="utf-8", newline="").read()
if HEAD in raw:
    raise SystemExit("already noted")
now = datetime.datetime.now().strftime("%H:%M")
TEXT = ("\n%s (written %s)\n\n" % (HEAD, now)
        + "The protocol compares \"the adopted figure -- the one the loader would use\" with the filing. Since the "
          "seventh amendment the loader replaces two records' figures with confirmed ones (4444/2022 and 2008/2019, "
          "data/pyd_confirmed_figures.json). The third sample's briefs therefore apply that register as the loader "
          "does (make_adjudication_briefs_third.py, through run_analysis.apply_confirmed_figure), so a drawn record "
          "carries the figure the model uses. A confirmed figure is checked by its kind: one read from a printed "
          "triangle as a triangle figure, one the filing states as a stated figure (score_error_rate.figure_source). "
          "The records the extraction repairs (3624/2015, 1225/2022, 2010/2019) carry their figures in the records "
          "themselves. No part of the protocol changes.\n")
io.open(str(P), "a", encoding="utf-8", newline="").write(TEXT.replace("\n", "\r\n") if "\r\n" in raw else TEXT)
print("protocol: implementation note written %s" % now)
