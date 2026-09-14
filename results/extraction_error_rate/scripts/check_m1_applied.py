r"""Close mechanism M1 of scan_mechanism_variants.py (read-only).

For every working-sample record where a model's stored triangle starts later than the pipeline's deterministic
triangle, compare each model's adopted figure with the deterministic triangle's own figure, summed over the columns
up to t-2 (the cohort-enforced scope) and up to t-1. A record agrees when either sum is within the protocol's
tolerance, max(0.5, 0.05 x |adopted|). Records that do not agree are printed with the override tags their notes carry,
for reading. Reads the committed records at the extraction repo's HEAD.

The check refuses to report unless it flags the three records already known to differ (1225/2022, 2007/2015 and
3624/2015, whose deterministic figures the sign veto refused).

    python check_m1_applied.py
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TAGS = re.compile(r"\[((?:RAG|CODE)[^\]]*)\]")
KNOWN = {"syndicate_1225_2022", "syndicate_2007_2015", "syndicate_3624_2015"}


def committed(stem):
    out = subprocess.run(["git", "-C", str(EXT), "show", "HEAD:pdf_extraction/%s.json" % stem],
                         capture_output=True, check=True).stdout
    return json.loads(out.decode("utf-8"))


def triangle_pyd(tri, last_year):
    ys = tri.get("underwriting_years") or []
    rows = tri.get("development_rows") or []
    total, used = 0.0, []
    for j, y in enumerate(ys):
        if y > last_year:
            continue
        col = [row[j] for row in rows if j < len(row) and row[j] is not None]
        if len(col) >= 2:
            total += col[-1] - col[-2]
            used.append(y)
    return round(total, 3), used


scan = json.load(io.open(str(SCR / "mechanism-variants-scan.json"), encoding="utf-8"))
agree, differ = [], []
for e in scan["M1"]:
    if not e["in_working_sample"]:
        continue
    stem = e["stem"]
    t = int(stem.rsplit("_", 1)[1])
    rec = committed(stem)
    lines, ok_all = [], True
    for m, md in sorted(rec["models"].items()):
        rag = md.get("_rag_triangle") or {}
        adopted = md.get("prior_year_development_gbp_m")
        if not rag or adopted is None:
            lines.append("    %-16s adopted %s, no deterministic triangle" % (m, adopted))
            ok_all = False
            continue
        units = (rag.get("units") or "").lower()
        scales = {"millions": [1.0], "thousands": [0.001]}.get(units, [1.0, 0.001])
        p2, used2 = triangle_pyd(rag, t - 2)
        p1, used1 = triangle_pyd(rag, t - 1)
        tol = max(0.5, 0.05 * abs(adopted))
        ok = any(abs(adopted - p * s) <= tol for p in (p2, p1) for s in scales)
        ok_all = ok_all and ok
        lines.append("    %-16s adopted %-9s deterministic (%s) to t-2 %-9s (%s-%s)  to t-1 %-9s %s  %s"
                     % (m, adopted, units or "units unstated", round(p2 * scales[0], 3),
                        min(used2) if used2 else "-", max(used2) if used2 else "-", round(p1 * scales[0], 3),
                        "agrees" if ok else "DIFFERS", " | ".join(x[:110] for x in TAGS.findall(md.get("data_quality_notes") or ""))))
    (agree if ok_all else differ).append((stem, lines))

missing = KNOWN - {s for s, _ in differ}
if missing:
    raise SystemExit("the check does not flag %s, which are known to differ: it is wrong" % sorted(missing))
print("M1 working-sample records: %d agree, %d differ" % (len(agree), len(differ)))
for stem, lines in differ:
    print("  DIFFERS " + stem + ("  (known)" if stem in KNOWN else ""))
    print("\n".join(lines))
for stem, lines in agree:
    print("  agrees  " + stem)
