r"""score_error_rate.figure_source learns the loader's confirmed-figure route (data/pyd_confirmed_figures.json).

A confirmed figure read from a printed triangle is checked as a triangle figure (the clarification's rule 1); one the
filing states is checked as a stated figure (rule 2). No earlier brief carries that route, so no earlier score moves.

    python fix_figure_source_confirmed.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "score_error_rate.py"
OLD = ('    if route.get("source") == "rag_triangle":\n'
       '        if carries_triangle(route):\n')
NEW = ('    if route.get("source") == "confirmed_figure":\n'
       '        if route.get("figure_kind") == "triangle":\n'
       '            return "triangle", ("a figure two readings confirmed from a printed triangle "\n'
       '                                "(data/pyd_confirmed_figures.json)")\n'
       '        return "stated", "a figure two readings confirmed as the filing states it (data/pyd_confirmed_figures.json)"\n'
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
print("score_error_rate.figure_source: a confirmed figure is classified by its kind")
