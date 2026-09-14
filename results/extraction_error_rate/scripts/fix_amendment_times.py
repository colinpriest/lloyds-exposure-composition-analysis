r"""The fifth amendment and the ledger carry clock times I estimated, not read. The file system records the writes:
amend_protocol_fifth.py 19:29:26 (applied before 19:33:20), the first correction's script 19:33:20 (applied before
19:34:58), the second's 19:34:58 (applied 19:35:53, the protocol's mtime), and error-rate-census.json 19:35:55. The
early review finished between the checks at 18:45:52 and 18:53. The order that matters holds: every correction was
written before the census file, and no census record had been read.

    python fix_amendment_times.py
"""
import datetime
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
NOW = datetime.datetime.now().strftime("%H:%M")      # the machine's clock is Brisbane time
EDITS = {
    SCR / "error-rate-protocol.md": [
        ("## Fifth amendment, 13 September 2026, 19:45, after both results",
         "## Fifth amendment, 13 September 2026, 19:29-19:33, after both results"),
        ("(Correction, 19:58, before any", "(Correction, 19:33-19:35, before any"),
        ("(Correction, 20:05, before any", "(Correction, 19:35, before any"),
        ("\nNo other part of the protocol changes.\n",
         "\nThe times in this amendment are bounded by the file system's times: the amendment's script was written at "
         "19:29 and the first correction's at 19:33, the second correction left the protocol at 19:35:53, and the "
         "census file was written at 19:35:55. The first versions carried times I had estimated (19:45, 19:58 and "
         "20:05); they were corrected at " + NOW + ".\n\nNo other part of the protocol changes.\n"),
    ],
    SCR / "round56-findings-ledger.md": [
        ("(13 September 2026, 19:55-20:05)", "(13 September 2026, 19:33-19:36)"),
        ("(read-only agent, 13 September 2026, finished 18:55)", "(read-only agent, 13 September 2026, finished about 18:50)"),
    ],
}

for path, edits in EDITS.items():
    raw = io.open(str(path), encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    for old, new in edits:
        n = t.count(old)
        # the protocol's closing sentence appears once per amendment; only the last one is the fifth amendment's
        if old.startswith("\nNo other part"):
            i = t.rfind(old)
            if i < 0 or "## Fifth amendment" not in t[:i]:
                raise SystemExit("%s: the fifth amendment's closing sentence not found" % path.name)
            t = t[:i] + new + t[i + len(old):]
            continue
        if n != 1:
            raise SystemExit("%s: %r found %d times" % (path.name, old, n))
        t = t.replace(old, new)
    io.open(str(path), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
    print("%s: times corrected" % path.name)
