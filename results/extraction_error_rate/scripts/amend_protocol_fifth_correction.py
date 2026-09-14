r"""The fifth amendment's replay census, corrected before any census record is read (13 September 2026, 19:58).

The first version listed seven working-sample records as replay-stopped. That list merged the file's round-55
measurement into its current list: offline_unservable.json at 40eb31aa records each of the six others as "served in
this replay", and its `stems` (every report not servable offline now) holds one working-sample record, 2008/2021.
The correction says so in the amendment itself. It also names the paid call the repair needs: the missing
response is a gemini-2.5-flash page-triangle call, so "these Azure calls" was too narrow.

    python amend_protocol_fifth_correction.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
EDITS = [
    ("""   - Replay stopped: every working-sample record listed in `pdf_extraction/audit/offline_unservable.json` at
     extraction commit 40eb31aa. Seven of the 698 are listed: 1301/2016, 1969/2015, 2008/2021, 2988/2021,
     2988/2022, 2988/2023 and 623/2016.
""",
     """   - Replay stopped: every working-sample record that `pdf_extraction/audit/offline_unservable.json` at
     extraction commit 40eb31aa lists as not servable offline now (its `stems`: this replay's unservable reports
     and the reports with no usable cache). One of the 698 is listed, 2008/2021. (Correction, 19:58, before any
     census record was read: the first version of this point listed seven records. The six others, 1301/2016,
     1969/2015, 2988/2021, 2988/2022, 2988/2023 and 623/2016, come from the file's round-55 measurement, and the
     file records each of them as served in the round-56 replay.)
"""),
    ("""   - A record whose replay stopped is re-extracted with the calls its caches lack, made under the pipeline's
     cost guards and cached. The owner authorised these Azure calls on 13 September 2026. No prompt changes,
     and no other record's cache is touched.
""",
     """   - A record whose replay stopped is re-extracted with the calls its caches lack, made under the pipeline's
     cost guards and cached. The owner authorised the paid calls for these repairs, Azure included, on 13
     September 2026. 2008/2021's missing response is a gemini-2.5-flash page-triangle call (page 53). No prompt
     changes, and no other record's cache is touched.
"""),
]

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "(Correction, 19:58, before any" in t:
    raise SystemExit("already corrected")
for old, new in EDITS:
    if t.count(old) != 1:
        raise SystemExit("amendment text not found once: %r" % old[:80])
    t = t.replace(old, new)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("error-rate-protocol.md: the fifth amendment's replay census and its paid call corrected")
