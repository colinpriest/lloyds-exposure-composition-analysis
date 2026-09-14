r"""The error-rate protocol's sixth amendment, written before any take-on census record is read. The clock time is read
when it is applied.

    python amend_protocol_sixth.py
"""
import datetime
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
NOW = datetime.datetime.now().strftime("%H:%M")      # the machine's clock is Brisbane time
TEXT = r'''
## Sixth amendment, 13 September 2026, %(now)s, before any record below is read: the take-on mechanism

The fifth amendment's replay repair was made. 2008/2021's missing gemini-2.5-flash page-image call (page 53) was
made under the cost guards and cached, and the record now replays offline. Its adopted figure did not change: the
page-image triangle also fails the pipeline's structure check, so the provisions note's "change in prior year
provisions" of +383.9m is adopted again. The second sample's first reading shows that figure to be the whole 2021
gross claims charge, the first-year recognition of a loss portfolio transfer written into the report year's year of
account. So the error's mechanism is not the stopped replay. It is a stated movement adopted as development in a year
the syndicate took on another's liabilities, where the movement is the take-on.

On 13 September 2026 the owner decided that a record whose filing shows its adopted figure to be the take-on itself
leaves the working sample, because it is not development.

1. Census of the take-on mechanism. It is purposive, reported on its own and never pooled with a random sample: every
   working-sample record in the RITC regime (its recorded sources: an accepted RITC or a confirmed inward transfer)
   whose adopted figure is a stated movement (score_error_rate.figure_source on its brief, with 2008/2021 read from
   its record after the replay repair). The records are computed from the refit's exposure_results.json and the
   records, and written to error-rate-census-takeon.json before any is read.
2. Each record gets a first and a second reading from the same brief, pack and page tool, under the same instruction
   and one added question: is the adopted figure the year's take-on (the RITC premium or the reserves transferred in,
   or a charge dominated by them), or the change in the estimate for earlier years? The reading records the filing's
   evidence. 2008/2021 keeps its first reading, which answers the question, and gets a second reading on it.
3. A record whose two readings both find the adopted figure to be the take-on leaves the working sample, through a
   register in the extraction repository that the analysis loader reads, with the page and quote. A record that the
   readings do not both find so stays. A record that leaves the second sample's population is dropped from A, and
   the drawn sample is conditioned on not containing it (third amendment).
4. The fifth amendment's random draw (point 3) is taken after this repair, from the working sample it leaves.

No other part of the protocol changes.
'''

raw = io.open(str(P), encoding="utf-8", newline="").read()
if "## Sixth amendment" in raw:
    raise SystemExit("already amended")
text = TEXT % {"now": NOW}
io.open(str(P), "a", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if "\r\n" in raw else text)
print("error-rate-protocol.md: the sixth amendment appended at %s" % NOW)
