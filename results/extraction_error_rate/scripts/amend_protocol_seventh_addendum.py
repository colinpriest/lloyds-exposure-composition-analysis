r"""The seventh amendment's repair rule, extended to errors the censuses confirm, before the take-on census's error is
second-read. The clock time is read when it is applied.

    python amend_protocol_seventh_addendum.py
"""
import datetime
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
NOW = datetime.datetime.now().strftime("%H:%M")
OLD = "4. The fifth amendment's random draw (point 3) is taken after these repairs, from the working sample they leave.\n"
NEW = OLD + ('''5. (Added %(now)s, before the record it concerns was second-read.) The take-on census's first readings found one
   error that is not a take-on: 2008/2019 adopts +249.0m where the filing's gross change in prior year provisions is
   +14.053m. An error that a census's two readings confirm, and whose correct figure the pipeline cannot produce, is
   repaired by the confirmed figure under the owner's decision above, like the records of points 1 and 2.
''')

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "The take-on census's first readings found one" in t:
    raise SystemExit("already added")
s = t.index("## Seventh amendment")
if t[s:].count(OLD) != 1:
    raise SystemExit("the seventh amendment's point 4 was not found once")
i = t.index(OLD, s)
t = t[:i] + NEW % {"now": NOW} + t[i + len(OLD):]
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("error-rate-protocol.md: the seventh amendment's point 5 added at %s" % NOW)
