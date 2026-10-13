r"""Mutation check of scan_triangle_tables.py: each mutant must turn checks_scan_triangle_tables.py red.

It rewrites scan_triangle_tables.py beside it, one mutant at a time, and restores it at the end, so run it in a copy
of the clone, never in the clone you commit from:

    LLOYDS_EXTRACTION_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 python mutate_scan_triangle_tables.py
"""
import io
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
CODE = SCR / "scan_triangle_tables.py"
CHECKS = "checks_scan_triangle_tables.py"
MUTANTS = [
    ("the tolerance is 5%, not 2%",
     "TOL = 0.02 ", "TOL = 0.05 "),
    ("gross and net are indistinguishable within 10%",
     "INDISTINCT = 0.04 ", "INDISTINCT = 0.10 "),
    ("a net hit is read against the gross figure",
     'n_hits = [c for c in cands if co_n is not None and reconcile(c["value"], co_n, co_g)]',
     'n_hits = [c for c in cands if co_n is not None and reconcile(c["value"], co_g, co_n)]'),
    ("a line printing both bases binds to both",
     '    g_hits = [c for c in g_hits if c["line"] not in both_lines]\n',
     '    pass  # MUTANT\n'),
    ("the block never stops at the next table",
     "            if yh or ds or ah or bh:\n", "            if False:  # MUTANT\n"),
    ("a paid sub-table ends the block",
     'ds = bool(DEVSTART.search(ln.label or "")) and not in_paid',
     'ds = bool(DEVSTART.search(ln.label or ""))'),
    ("the filing's own latest-estimate totals are never placed",
     '    if co_g is None or co_n is None:\n        return None\n    for p, lines in filing.pages.items():',
     '    return None  # MUTANT\n    for p, lines in filing.pages.items():'),
    ("the movement note's net is read from the reinsurers' share",
     'net.append((z / s, "movement closing line, opening anchored", f))',
     'net.append((abs(y) / s, "movement closing line, opening anchored", f))'),
    ("a label wrapped below its amounts is ignored",
     "            ctx.append(block[k + 1].text)\n", "            pass  # MUTANT\n"),
    ("a paid row counts as a total",
     "            continue          # a paid row is never a reserve total\n", "            pass  # MUTANT\n"),
    ("an underwriting year's row counts as a total",
     "            continue          # an underwriting year's row of a table, not a total\n", "            pass  # MUTANT\n"),
    ("a table that reconciles to gross but fails its own gross total passes",
     "        if i_g is not None and d is not None and not d_g:\n", "        if False:  # MUTANT\n"),
    ("a table with no printed total is called unreconciled",
     "    if not printed:\n", "    if False:  # MUTANT\n"),
    ("the located page is the one with the fewest cells",
     "best = max(sorted(hits), key=lambda p: (len(hits[p]), -p))",
     "best = min(sorted(hits), key=lambda p: (len(hits[p]), -p))"),
]


def main():
    original = CODE.read_bytes()
    results = []
    try:
        for name, old, new in MUTANTS:
            src = original.decode("utf-8")
            if src.count(old) != 1:
                results.append((name, "NOT APPLIED (pattern found %d times)" % src.count(old)))
                continue
            io.open(str(CODE), "w", encoding="utf-8", newline="\n").write(src.replace(old, new))
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", CHECKS],
                               cwd=str(SCR), capture_output=True, text=True)
            tail = (r.stdout.strip().splitlines() or [""])[-1]
            results.append((name, ("killed: " if r.returncode != 0 else "SURVIVED: ") + tail))
    finally:
        CODE.write_bytes(original)
    for name, res in results:
        print("%-70s %s" % (name, res))
    survived = [n for n, r in results if not r.startswith("killed")]
    print("%d mutants, %d killed, %d survived or not applied" % (len(results), len(results) - len(survived),
                                                                 len(survived)))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
