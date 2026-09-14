r"""Mutation check of the refinement clauses in score_error_rate.py: each mutant must turn test_score_clarified.py red.

    python mutate_score_error_rate.py
"""
import io
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
CODE = SCR / "score_error_rate.py"
MUTANTS = [
    ("a rag_triangle route without a triangle is a triangle",
     '        return "stated", "a rag_triangle route that carries no triangle: the RAG step\'s fallback (refinement 3)"\n',
     '        return "triangle", "MUTANT"\n'),
    ("an empty route's code override is ignored",
     '            return "triangle", "an empty route whose code override computed the adopted figure (refinement 3)"\n',
     '            return "stated", "MUTANT"\n'),
    ("the sign-veto register is ignored",
     '    if brief.get("stem") in overruled:\n',
     '    if False:  # MUTANT\n'),
    ("a triangle route whose log prints another method passes",
     '        elif carries_triangle(route) and logged:\n',
     '        elif False:  # MUTANT\n'),
    ("records whose source is not the route field are not second-read",
     '        "source_is_not_the_route_field": {s for s in stems if src[s] != route_field_says(briefs[s])},\n',
     '        "source_is_not_the_route_field": set(),  # MUTANT\n'),
    ("a first reader's scope error falls through to the recomputation",
     '    if first["verdict"] == "error" and kind and kind not in ("magnitude", "sign"):\n',
     '    if False:  # MUTANT\n'),
]

text = io.open(str(CODE), encoding="utf-8", newline="").read()
bad = 0
try:
    for why, old, new in MUTANTS:
        if text.count(old) != 1:
            print("  %-62s anchor not found once (%d)" % (why, text.count(old)))
            bad += 1
            continue
        io.open(str(CODE), "w", encoding="utf-8", newline="").write(text.replace(old, new))
        out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_score_clarified.py"],
                             cwd=str(SCR), capture_output=True, text=True)
        tail = [ln for ln in out.stdout.splitlines() if " passed" in ln or " failed" in ln]
        red = out.returncode != 0
        print("  %-62s -> %s %s" % (why, "RED (caught)" if red else "GREEN (NOT caught)", tail[-1] if tail else ""))
        bad += 0 if red else 1
finally:
    io.open(str(CODE), "w", encoding="utf-8", newline="").write(text)
left = io.open(str(CODE), encoding="utf-8").read().count("MUTANT")
print("mutant markers left: %d" % left)
sys.exit(0 if bad == 0 and left == 0 else 1)
