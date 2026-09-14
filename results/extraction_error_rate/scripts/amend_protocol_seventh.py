r"""The error-rate protocol's seventh amendment, written before any record it names is read. The clock time is read
when it is applied.

    python amend_protocol_seventh.py
"""
import datetime
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
NOW = datetime.datetime.now().strftime("%H:%M")
TEXT = r'''
## Seventh amendment, 13 September 2026, %(now)s, before any record below is read: confirmed errors the samples left in the data, records found in passing, and repair by a confirmed figure

Two facts came to light after the sixth amendment. First, the first sample confirmed seven errors, and the fourth
amendment redrew the sample without repairing them. Three are still in the working sample with the same adopted
figure (persisting-first-sample-errors.json): 3624/2015, now repaired (fifth amendment), 2010/2019 (+132.679m against
the filing's -18.659m) and 4444/2022 (+435.491m against +34.9m). Second, the read-only mapping of the extraction code
named four working-sample records whose figures it could not reconcile with their filings: 1225/2022, 623/2014,
623/2022 and 1206/2014.

On 13 September 2026 the owner decided that a confirmed error whose correct figure the pipeline cannot produce is
repaired by the figure two readings of the filing confirm, through a register the analysis reads, each hand correction
disclosed. The record stays in the working sample.

1. 2010/2019 and 4444/2022 are confirmed errors (the first sample's first and second readings). Their confirmed figures
   are the second readings' filing figures. They are repaired so.
2. 1225/2022, 623/2014, 623/2022 and 1206/2014 are each read twice, as a census record is. They are reported apart,
   never pooled with a random sample, and never counted as a mechanism's census. A record whose two readings find an
   error and agree on the filing's figure is repaired by that figure; any other record is left as it is, with its
   readings recorded.
3. A repair by a confirmed figure changes the record's adopted figure, so the record is read again only if a random
   sample holds it (third amendment, second case). None of the six is in the second sample.
4. The fifth amendment's random draw (point 3) is taken after these repairs, from the working sample they leave.

No other part of the protocol changes.
'''

raw = io.open(str(P), encoding="utf-8", newline="").read()
if "## Seventh amendment" in raw:
    raise SystemExit("already amended")
text = TEXT % {"now": NOW}
io.open(str(P), "a", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if "\r\n" in raw else text)
print("error-rate-protocol.md: the seventh amendment appended at %s" % NOW)
