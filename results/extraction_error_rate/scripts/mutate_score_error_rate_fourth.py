r"""Mutation check of score_error_rate_fourth.py: each mutant must turn checks_score_error_rate_fourth.py red.

It rewrites score_error_rate_fourth.py beside it, one mutant at a time, and restores it at the end, so run it in a
copy of the clone, never in the clone you commit from:

    python mutate_score_error_rate_fourth.py
"""
import io
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
CODE = SCR / "score_error_rate_fourth.py"
CHECKS = "checks_score_error_rate_fourth.py"
MUTANTS = [
    ("a code_triangle route is read as stated",
     '    if (brief.get("route") or {}).get("source") == "code_triangle":\n',
     '    if False:  # MUTANT\n'),
    ("the route field ignores code_triangle",
     'TRIANGLE_ROUTES = ("rag_triangle", "code_triangle")\n',
     'TRIANGLE_ROUTES = ("rag_triangle",)  # MUTANT\n'),
    ("a second reading does not stand over the first",
     '            clar[s] = second[s]["verdict"]\n',
     '            pass  # MUTANT\n'),
    ("the first readers' rule takes the clarified verdicts",
     '        first[s] = rows[s]["verdict"]\n',
     '        first[s] = rows[s]["clarified_verdict"]  # MUTANT\n'),
    ("a tenth, not a fifth, of the remaining corrects",
     '    k = int(math.ceil(0.2 * len(rest)))\n',
     '    k = int(math.ceil(0.1 * len(rest)))  # MUTANT\n'),
    ("the random fifth from another seed",
     'np.random.default_rng(seed).choice(len(rest)',
     'np.random.default_rng(42).choice(len(rest)'),
    ("the second reader's brief carries the first reading",
     '    blind = [{k_: v_ for k_, v_ in briefs[s].items() if k_ not in READING_FIELDS} for s in vset["all"]]\n',
     '    blind = [dict(briefs[s], **rows[s]) for s in vset["all"]]  # MUTANT\n'),
    ("an undeterminable enters the denominator as correct",
     '    c = sum(1 for v in final.values() if v == "correct")\n',
     '    c = sum(1 for v in final.values() if v in ("correct", "undeterminable"))  # MUTANT\n'),
    ("a census disagreement is scored an error",
     '    return "undeterminable", "the readings disagree (%s, %s)" % (va, vb)\n',
     '    return "error", "MUTANT"\n'),
    ("a reading without a quotation is merged",
     '    if v.get("verdict") != "undeterminable" and not (v.get("quote") or "").strip():\n',
     '    if False:  # MUTANT\n'),
    ("a missing reading is not noticed",
     '    if missing:\n        problems.append',
     '    if False:  # MUTANT\n        problems.append'),
    ("a rag_triangle route without its triangle is merged",
     'if (b.get("route") or {}).get("source") == "rag_triangle" and not ser.carries_triangle(b["route"])]\n',
     'if False]  # MUTANT\n'),
    ("the paper's rate in P(theta4 > .) moves",
     'PAPER_RATE = 0.052\n',
     'PAPER_RATE = 0.05  # MUTANT\n'),
    ("F's unread records all count as adjudicable",
     '    a_unread = int(round(unread * n4 / n_drawn))\n',
     '    a_unread = unread  # MUTANT\n'),
    ("the score is written twice (both guards removed)",
     ['    if target.exists():\n        raise SystemExit("%s exists; draw four is scored once"',
      '    if path.exists():\n        raise SystemExit("%s exists; it is written once"'],
     ['    if False:  # MUTANT\n        raise SystemExit("%s exists; draw four is scored once"',
      '    if False:  # MUTANT\n        raise SystemExit("%s exists; it is written once"']),
    ("the merge is written twice (both guards removed)",
     ['    if done:\n', '    if path.exists():\n        raise SystemExit("%s exists; it is written once"'],
     ['    if False:  # MUTANT\n', '    if False:  # MUTANT\n        raise SystemExit("%s exists; it is written once"']),
    ("a K record repaired to the readings' figure keeps its old verdict",
     '        out[s] = "correct" if abs(float(read) - float(now)) > 1e-9 else final\n',
     '        out[s] = final  # MUTANT\n'),
]

text = io.open(str(CODE), encoding="utf-8", newline="").read()
bad = 0
try:
    for why, olds, news in MUTANTS:
        olds, news = ([olds], [news]) if isinstance(olds, str) else (olds, news)
        counts = [text.count(o) for o in olds]
        if counts != [1] * len(olds):
            print("  %-62s anchor not found once (%s)" % (why, counts))
            bad += 1
            continue
        mutant = text
        for o, n in zip(olds, news):
            mutant = mutant.replace(o, n)
        io.open(str(CODE), "w", encoding="utf-8", newline="").write(mutant)
        out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", CHECKS],
                             cwd=str(SCR), capture_output=True, text=True)
        tail = [ln for ln in out.stdout.splitlines() if " passed" in ln or " failed" in ln or " error" in ln]
        red = out.returncode != 0
        print("  %-62s -> %s %s" % (why, "RED (caught)" if red else "GREEN (NOT caught)", tail[-1] if tail else ""))
        bad += 0 if red else 1
finally:
    io.open(str(CODE), "w", encoding="utf-8", newline="").write(text)
left = io.open(str(CODE), encoding="utf-8").read().count("MUTANT")
print("mutants not caught or not applied: %d; mutant markers left: %d" % (bad, left))
sys.exit(0 if bad == 0 and left == 0 else 1)
