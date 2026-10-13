r"""Mutation check of scan_grid_shape.py: each mutant must turn checks_scan_grid_shape.py red.

It rewrites scan_grid_shape.py beside it, one mutant at a time, and restores it at the end, so run it in a copy of the
clone, never in the clone you commit from:

    LLOYDS_EXTRACTION_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 python mutate_scan_grid_shape.py
"""
import io
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
CODE = SCR / "scan_grid_shape.py"
CHECKS = "checks_scan_grid_shape.py"
MUTANTS = [
    ("a zero cell counts as filled",
     "    return x is not None and x != 0.0\n", "    return x is not None\n"),
    ("trailing empty rows are kept",
     "    while rows and not any(filled(v) for v in rows[-1]):\n", "    while False:  # MUTANT\n"),
    ("a column whose diagonal lies beyond the grid is tested",
     "        if e >= n_rows:\n", "        if e > n_rows:\n"),
    ("S1 ignores labels later than t",
     "late = [y for c, y in enumerate(years) if y is not None and y > t and fill[c]]",
     "late = []  # MUTANT"),
    ("S1 ignores duplicated labels",
     "dups = sorted(y for y, n in Counter(y for y in years if y is not None).items() if n > 1)",
     "dups = []  # MUTANT"),
    ("S2 never fails",
     "extra = sorted({c for r in rows for c in range(n_cols, len(r)) if filled(r[c])})", "extra = []  # MUTANT"),
    ("S3 never fails",
     "gaps = [(a, b) for a, b in zip(ys, ys[1:]) if b - a > 1]", "gaps = []  # MUTANT"),
    ("S4 needs twice as many short columns as on",
     "up, down = n_short1 > n_on, n_beyond > n_on", "up, down = n_short1 > 2 * n_on + 8, n_beyond > n_on"),
    ("S4 never reads a grid one row down",
     "up, down = n_short1 > n_on, n_beyond > n_on", "up, down = n_short1 > n_on, False"),
    ("S5 never fails",
     "    sig = (t in col_of", "    sig = False and (t in col_of"),
    ("S6 tests young columns as mature",
     "        if k[\"uw\"] > t - MATURE_LAG or k[\"status\"] == \"on\":\n",
     "        if k[\"status\"] == \"on\":\n"),
    ("S6 never fails",
     "        off.append(\"%d: last row %d", "        0 and off.append(\"%d: last row %d"),
    ("S6 exempts a beyond cell whatever the printed estimate",
     "        if k[\"status\"] == \"beyond\" and p is not None and number(col[k[\"diag_row\"]]) is not None \\\n"
     "                and same_figure(number(col[k[\"diag_row\"]]), p):\n",
     "        if k[\"status\"] == \"beyond\":\n"),
    ("S7 tolerance is 50 times wider",
     "tol = None if raw_m is None else max(0.5, 0.05 * abs(raw_m))",
     "tol = None if raw_m is None else max(25.0, 2.5 * abs(raw_m))"),
    ("the raw figure is read with the registers applied",
     "    raw.confirmed, raw.openings, raw.base = {}, {}, {}\n", "    pass  # MUTANT\n"),
    ("a code_triangle grid is the canonical model's whatever the note says",
     "        k = m.group(1) if m and m.group(1) in models and models[m.group(1)].get(\"_claims_triangle\") else ck\n",
     "        k = ck\n"),
    ("a registered shape-fail is called open",
     "\"already registered\" if reg is not None else \"open\")", "\"open\")"),
    ("the population is the raw figure's only",
     "        if a_src[0] == \"triangle\" or r_src[0] == \"triangle\":\n",
     "        if r_src[0] == \"triangle\":\n"),
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
        print("%-72s %s" % (name, res))
    survived = [n for n, r in results if not r.startswith("killed")]
    print("%d mutants, %d killed, %d survived or not applied" % (len(results), len(results) - len(survived),
                                                                 len(survived)))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
