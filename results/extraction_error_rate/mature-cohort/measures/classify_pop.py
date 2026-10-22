"""Classify the primary population (571 + 86) for the earned-basis question (Q4) and the older-years coverage gap
(Q5), from pop_measures.json and the stored grids. Read only; writes pop_classified.json and prints the counts."""
import io, json, re, sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
d = json.load(io.open(HERE / "pop_measures.json", encoding="utf-8"))
CENSUS = Path(r"D:/tmp/r62/pub4/results/extraction_error_rate/triangle-table-scan/triangle-table-scan.json")
RESTORED = Path(r"D:/tmp/r62/oc/design/scan_restored.json")
REC = Path(r"D:/tmp/r62/pub4/pdf_extraction")
meta = {r["stem"].replace("syndicate_", ""): r for r in json.load(io.open(CENSUS, encoding="utf-8"))["records"]}
meta.update({r["stem"].replace("syndicate_", ""): r for r in json.load(io.open(RESTORED, encoding="utf-8"))
             if r["stem"].replace("syndicate_", "") not in meta or True})

EARNED_TABLE = re.compile(
    r"earned ultimate|estimates? of earned|earned (?:gross |net )?(?:and net )?claims|earned loss reserves|"
    r"(?:reported|shown) on an earned basis|premiums? earned to (?:date|statement|the balance)|"
    r"(?:on|of) (?:cumulative )?premiums? earned|pattern of earned premium|pattern of earning|earned cumulative|"
    r"pure year earned|reserves \(earned\)|current estimate of earned|claims on premium earned|"
    r"earned, underwriting year basis|cumulative premiums earned|Gross earned|Net earned ultimate", re.I)
FIRST_EARNED = re.compile(r"initial estimate .*earned basis", re.I)
UNEARNED_DED = re.compile(r"unearned (?:portion|proportion) of (?:ultimate|claims)|(?:gross|net) unearned claims|"
                          r"unearned claims reserve|unearned portion of ultimate losses", re.I)
LATE_EARNING = re.compile(r"continue to increase in subsequent years|delaying premium earning|over the first 3 years|"
                          r"24 months beyond|long earning patterns", re.I)
GROUP = re.compile(r"\b(?:prior|pre|earlier|older|before|ae)\b|&\s*P\b", re.I)


def grid_of(key, m):
    try:
        rec = json.load(io.open(REC / ("syndicate_%s.json" % key), encoding="utf-8"))
    except FileNotFoundError:
        return None
    blk = (rec.get("models") or {}).get(m.get("canonical_model")) or {}
    return blk.get(m.get("grid_field") or "_rag_triangle")


out = {}
for key, r in d.items():
    m = meta.get(key) or {}
    el = r.get("earned_lines") or []
    joined = " | ".join(el)
    plain = re.sub(r"unearned", "UNERND", joined, flags=re.I)   # "unearned claims" is not an earned-basis table
    if EARNED_TABLE.search(plain):
        earned = "earned-basis table"
    elif FIRST_EARNED.search(plain):
        earned = "first diagonal earned"
    elif UNEARNED_DED.search(joined):
        earned = "ultimate basis, unearned portion deducted"
    else:
        earned = "no earned wording found"
    late = bool(LATE_EARNING.search(joined))
    g = grid_of(key, m) or {}
    labels = [str(y) for y in (g.get("underwriting_years") or [])]
    grid_group = any(GROUP.search(x) for x in labels) or bool(g.get("aggregated_cohort"))
    unc = r.get("uncovered_share")
    dlp, cog = r.get("d_less_paid"), r.get("co_g")
    if unc is not None and not (r.get("class") != "B" and dlp is not None and cog and 0 < dlp <= 1.02 * cog):
        unc = None   # a negative or excess table reserve, or a net table since repaired: not a measurement
    has_bucket_line = bool(r.get("prior_lines"))
    if grid_group:
        cov = "older-years column developed in the grid"
    elif unc is not None and unc > 0.02:
        cov = "reserves outside the developed years (measured)"
    elif unc is not None and unc >= -0.02:
        cov = "table covers the reserves (within 2%)"
    elif has_bucket_line:
        cov = "older-years line printed; share not measured"
    elif unc is not None:
        cov = "table exceeds CO_g (ultimate basis or other scope); share not measured"
    else:
        cov = "not measured (no reserve total placed)"
    out[key] = {"group": r["group"], "class": r.get("class"), "earned": earned, "late_earning_wording": late,
                "coverage": cov, "uncovered_share": unc, "grid_group_column": grid_group,
                "bucket_lines": (r.get("prior_lines") or [])[:3], "earned_lines": el[:3]}

with io.open(HERE / "pop_classified.json", "w", encoding="utf-8", newline="") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)

for grp in ("571", "86", None):
    sub = {k: v for k, v in out.items() if grp is None or v["group"] == grp}
    print("=== group", grp or "all 657", len(sub))
    print(" earned:", dict(Counter(v["earned"] for v in sub.values())))
    print(" late-earning wording:", sum(v["late_earning_wording"] for v in sub.values()))
    print(" coverage:", dict(Counter(v["coverage"] for v in sub.values())))
    shares = sorted(v["uncovered_share"] for v in sub.values()
                    if v["coverage"] == "reserves outside the developed years (measured)")
    for th in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50):
        print("  uncovered > %.0f%%: %d" % (th * 100, sum(s > th for s in shares)))
    if shares:
        print("  median uncovered share among measured gaps: %.3f" % shares[len(shares) // 2])
