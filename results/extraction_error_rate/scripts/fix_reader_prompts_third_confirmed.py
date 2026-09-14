r"""make_reader_prompts_third.py tells a batch's first reader what a confirmed-figure route is, in that batch only.

Since the seventh amendment the loader adopts a figure two readings confirmed for 4444/2022 and 2008/2019, and the
third sample's briefs carry that figure with route source "confirmed_figure" (implementation note, before the draw).
The reader template names the other routes but not this one. A batch that holds such a brief gets one added sentence;
every other batch keeps the instruction every earlier first reader had.

    python fix_reader_prompts_third_confirmed.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "make_reader_prompts_third.py"
OLD = '    t = once(t, "a JSON list of 5 objects", "a JSON list of %d objects" % k)\n'
NEW = ('    if any((b.get("route") or {}).get("source") == "confirmed_figure"\n'
       '           for b in json.load(io.open(path, encoding="utf-8"))):\n'
       '        t = once(t, "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED.",\n'
       '                 "THE BRIEF IS AUTHORITATIVE FOR WHAT WAS ADOPTED. A route whose source is confirmed_figure "\n'
       '                 "carries a figure that two earlier readings of the filing confirmed and the loader adopts in "\n'
       '                 "place of the extraction\'s; its figure_kind says whether it was read from a printed triangle "\n'
       '                 "(triangle) or is a figure the filing states (stated). Check it against the filing like any "\n'
       '                 "other adopted figure, and where its figure_kind is triangle also record the triangle "\n'
       '                 "recomputation.")\n'
       + OLD)

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if '"confirmed_figure"' in t:
    raise SystemExit("already patched")
if t.count(OLD) != 1:
    raise SystemExit("anchor found %d times, not once" % t.count(OLD))
t = t.replace(OLD, NEW)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("make_reader_prompts_third.py: a batch holding a confirmed-figure brief is told what that route is")
