"""Compare round-5 readings (arms P and Q) per record, and each reading's recomputed M against the analysis's own figure
(s_raw_a x opening reserves, in GBP m, and the record's pyd_gbp_m). Writes compare_r5.json and compare_r5.md. Read only.
"""
import io
import json
import os

BASE = r"D:/tmp/r62/oc/readings"
with io.open(r"D:/tmp/r62/oc/A/model/exposure_results.json", encoding="utf-8") as fh:
    ex = json.load(fh)
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in ex["observations"]}


def load(arm):
    out = {}
    for i in range(1, 9):
        p = os.path.join(BASE, "%s%d" % (arm, i), "readings.json")
        if not os.path.exists(p):
            continue
        with io.open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.items():
            k = k.split("|")[0]
            out[k] = ("%s%d" % (arm, i), v)
    return out


def m_of(v):
    for f in ("m_recomputed_m", "M_recomputed_m", "m_recomputed", "M_m"):
        x = v.get(f)
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict):
            for g in ("value_m", "m", "report_ccy_m", "value"):
                if isinstance(x.get(g), (int, float)):
                    return float(x[g])
    return None


P, Q = load("P"), load("Q")
keys = sorted(set(P) | set(Q), key=lambda s: (int(s.split("_")[0]), int(s.split("_")[1])))
rows = []
for k in keys:
    o = obs.get(k, {})
    r = {"key": k,
         "analysis_pyd_gbp_m": o.get("pyd_gbp_m"),
         "analysis_route": o.get("pyd_basis_source"),
         "report_currency": o.get("report_currency"),
         "opening_gbp_m": o.get("opening_reserves_gbp_m"),
         "fx_usd_per_gbp": o.get("fx_rate_usd_per_gbp")}
    for arm, src in (("P", P), ("Q", Q)):
        if k in src:
            who, v = src[k]
            r[arm] = {"reader": who, "verdict": v.get("verdict"), "m": m_of(v)}
    vp = r.get("P", {}).get("verdict")
    vq = r.get("Q", {}).get("verdict")
    r["verdicts_agree"] = vp == vq or {vp, vq} <= {"valid", "screen_misread", "units_slip"}
    # analysis figure in the report currency, for comparison with the readers' M
    a = r["analysis_pyd_gbp_m"]
    if a is not None and r["report_currency"] == "USD" and r["fx_usd_per_gbp"]:
        a = a * r["fx_usd_per_gbp"]
    r["analysis_m_report_ccy"] = a
    diffs = []
    for arm in ("P", "Q"):
        m = r.get(arm, {}).get("m")
        if m is not None and a is not None:
            diffs.append(abs(m - a))
    r["max_abs_diff_vs_analysis_m"] = max(diffs) if diffs else None
    r["figure_differs"] = bool(diffs) and max(diffs) > max(0.5, 0.01 * abs(a or 0))
    rows.append(r)
with io.open(os.path.join(BASE, "compare_r5.json"), "w", encoding="utf-8", newline="") as fh:
    fh.write(json.dumps(rows, indent=1) + "\n")
lines = ["| key | P | Q | M P | M Q | analysis M | flag |", "|---|---|---|---|---|---|---|"]
for r in rows:
    flag = []
    if not r["verdicts_agree"]:
        flag.append("VERDICTS DIFFER")
    if r["figure_differs"]:
        flag.append("FIGURE DIFFERS")
    if "restated" in str(r.get("P", {}).get("verdict")) or "restated" in str(r.get("Q", {}).get("verdict")):
        flag.append("restated")
    lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
        r["key"], r.get("P", {}).get("verdict"), r.get("Q", {}).get("verdict"), r.get("P", {}).get("m"),
        r.get("Q", {}).get("m"), None if r["analysis_m_report_ccy"] is None else round(r["analysis_m_report_ccy"], 3),
        ", ".join(flag)))
with io.open(os.path.join(BASE, "compare_r5.md"), "w", encoding="utf-8", newline="") as fh:
    fh.write("\n".join(lines) + "\n")
print("records", len(rows), "with both arms", sum(1 for r in rows if "P" in r and "Q" in r))
print("verdicts differ", sum(1 for r in rows if not r["verdicts_agree"]),
      "| figure differs from analysis", sum(1 for r in rows if r["figure_differs"]))
