"""The triangle-table census (scan_triangle_tables.scan_record, the fourteenth amendment's rule, unchanged) run on the
triangles the mature-cohort rule restores, offline and read-only, from the copy of the analysis repository. The brief
carries the restored triangle figure as the adopted one, so the grid's scale is chosen as the census chose it for the
573 triangle-sourced records. Writes scan_restored.json; writes nothing in either repository."""
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["LLOYDS_EXTRACTION_OFFLINE"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
ANA = HERE / "ana"
SCR = ANA / "results" / "extraction_error_rate" / "scripts"
sys.path.insert(0, str(ANA / "src"))
sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_triangle_tables as stt  # noqa: E402
import run_analysis as ra  # noqa: E402

s1 = {r["key"]: r for r in json.load(io.open(HERE / "stage1.json", encoding="utf-8"))["rows"]}
s2 = json.load(io.open(HERE / "stage2.json", encoding="utf-8"))
openings = ra.load_opening_reserves_confirmed()
base = ra.load_takeon_base()
out = []
for key, rest in sorted(s2["restored"].items()):
    r1 = s1[key]
    fig = rest[0][2]
    op = r1.get("block_opening")
    if key in openings:
        op = float(openings[key]["opening_reserves_m"])
    if key in base:
        op = float(op) + float(base[key]["takeon_m"])
    brief = {"adopted_prior_year_development_m_report_currency": fig, "adopted_opening_reserves_m_report_currency": op,
             "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
             "route": {"source": "rag_triangle", "triangle_source_page": r1.get("rag_tri_page")}}
    stem = "syndicate_%s" % key
    try:
        t = stt.scan_record(stem, brief, "rag_triangle", None)
    except Exception as e:  # report, do not stop
        t = {"stem": stem, "class": "ERROR", "reason": repr(e)[:300]}
    t["key"] = key
    out.append(t)
    print("%-10s %s %-70s | tri %s recomputed %s | D %s | CO_g %s CO_n %s | I %s %s | pages %s | %s" % (
        key, t.get("class"), (t.get("reason") or "")[:70], fig, t.get("recomputed_m"), t.get("d_used"), t.get("co_g"),
        t.get("co_n"), t.get("i_g"), t.get("i_n"), (t.get("locate") or {}).get("pages"), t.get("filing")), flush=True)
io.open(HERE / "scan_restored.json", "w", encoding="utf-8", newline="").write(
    json.dumps(out, indent=1, ensure_ascii=False, default=str))
print(Counter(t.get("class") for t in out))
