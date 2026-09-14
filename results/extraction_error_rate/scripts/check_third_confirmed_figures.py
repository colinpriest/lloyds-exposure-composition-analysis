r"""The third sample's confirmed errors and the loss-ratio mechanism, for the owner's decision (read-only).

1. For each of the eight errors: the first and the second readings' filing figures (the seventh amendment repairs a
   record by a confirmed figure only when two readings find an error and agree on the filing's figure).
2. 623/2014 and 2623/2019: what the extraction record says about the adopted figure (route, override note, the
   stored triangle's units and first cells).
3. Candidates for 623/2014's mechanism, a loss-ratio grid stored as a money triangle: a triangle whose units are
   millions, whose cells all lie in [0, 200], and whose record's opening reserves are at least five times its largest
   cell. The scan refuses to report unless it flags 623/2014, the record that defines it.

    python check_third_confirmed_figures.py
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


merged = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-third.json")}
verified = {v["stem"]: v for v in load(SCR / "error-rate-verification-third.json")}
ERRORS = ["syndicate_2010_2018", "syndicate_3010_2019", "syndicate_382_2015", "syndicate_382_2016",
          "syndicate_382_2018", "syndicate_382_2019", "syndicate_1880_2014", "syndicate_1980_2018"]

print("1. First and second readings of the eight errors")
for s in ERRORS:
    f, v = merged[s], verified[s]
    a, b = f.get("filing_figure_m"), v.get("filing_figure_m")
    same = "agree" if (a is not None and b is not None and abs(a - b) < 0.0005) else (
        "both none" if a is None and b is None else "DIFFER")
    print("  %-22s adopted %-9s first %-7s %-9s second %-7s %-9s %s" % (
        s, f.get("adopted_figure_m"), f.get("verdict"), a, v.get("verdict"), b, same))
    if same == "DIFFER":
        print("      first reader: %s" % (f.get("arithmetic") or "")[:600])
o = merged["syndicate_2003_2018"].get("opening_reserves")
print("  syndicate_2003_2018 opening: first reading %s; second reading: %s" % (
    o, [x for x in (verified["syndicate_2003_2018"].get("why") or "").split(". ") if "pening" in x]))

print("2. Loss-ratio records")
for s in ("syndicate_623_2014", "syndicate_2623_2019"):
    rec = load(EXT / "pdf_extraction" / (s + ".json"))
    for model, md in sorted((rec.get("models") or {}).items()):
        notes = [str(v) for k, v in md.items() if isinstance(v, str) and ("OVERRIDE" in v or "loss ratio" in v.lower())]
        print("  %s %s adopted %s route %s" % (s, model, md.get("prior_year_development_gbp_m"), md.get("_pyd_route")))
        for n in notes:
            i = max(n.find("OVERRIDE"), 0)
            print("      note: ... %s ..." % n[max(0, i - 200): i + 500])
        for kind in ("_rag_triangle", "_claims_triangle"):
            tri = md.get(kind) or {}
            if tri:
                rows = tri.get("development_rows") or []
                print("      %s units %s years %s first rows %s" % (kind, tri.get("units"), tri.get("underwriting_years"),
                                                                    rows[:2]))

print("3. Loss-ratio grids stored as money triangles (working sample)")
third = load(SCR / "error-rate-sample-third.json")
ws = set(load(SCR / "error-rate-population-698.json")["stems"]) - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])
hits = {}
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*_*.json"))):
    stem = Path(p).stem
    parts = stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit() or stem not in ws:
        continue
    rec = json.load(io.open(p, encoding="utf-8"))
    for model, md in sorted((rec.get("models") or {}).items()):
        opening = next((v for k, v in md.items() if "opening" in k.lower() and isinstance(v, (int, float))), None)
        for kind in ("_rag_triangle", "_claims_triangle"):
            tri = md.get(kind) or {}
            if (tri.get("units") or "").lower() != "millions":
                continue
            cells = [c for row in (tri.get("development_rows") or []) for c in row if isinstance(c, (int, float))]
            if len(cells) < 6 or min(cells) < 0 or max(cells) > 200 or not opening or opening < 5 * max(cells):
                continue
            hits.setdefault(stem, []).append((model, kind, (md.get("_pyd_route") or {}).get("source"),
                                              md.get("prior_year_development_gbp_m"), opening, max(cells)))
if "syndicate_623_2014" not in hits:
    raise SystemExit("the scan does not flag 623/2014, the record that defines it: it is wrong")
print("  candidates: %d" % len(hits))
for stem in sorted(hits):
    for h in hits[stem]:
        print("  %-22s %-17s %-17s route %-20s adopted %-9s opening %-9s largest cell %s" % ((stem,) + h))
