"""Census (read-only): records whose adopted development figure came from a deterministic route
that FILLED a blank the extraction models had left, where the models' own words give a
transfer, RITC or quota share as the reason.

Per record (pdf_extraction/syndicate_<N>_<YYYY>.json under BASE):
  filled      model blocks whose `_pyd_route.note` is "filled a blank model value" (the route
              filled that model's blank; a block whose note is "overrode the model value" had a
              figure of its own, kept in `_pyd_route.model_value`)
  blames      sentences of the model's data_quality_notes that name a transaction (RITC,
              reinsurance to close, transfer, quota share, LPT, novation, commutation, take-on)
              AND a reason word (distort, unreliable, unsuitable, could not, null, excluded, not
              used, due to, because, affected, impact ...)
  names       the model's raw_causal_phrases and prior_year_events that name a transaction

Tiers:
  A  every block filled a blank, and every model's data_quality_notes blame a transaction
     (the brief's definition: a route filled a blank both models left, and both models' own
     notes give the transaction as the reason)
  B  every block filled a blank, every model names a transaction somewhere in its own words,
     but not every model's notes tie it to the reason
  C  (context, the investigator's step-4b gate) at least one block filled a blank and at least
     one model's notes blame a transaction; not in A or B

Nothing is written except the two output files beside this script.
Usage: python -B census_filled_blanks.py [BASE]   (default: the extraction repository)"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = sys.argv[1] if len(sys.argv) > 1 else r"D:\dev\lloyds_reserve_stress_testing"
EXT = r"D:\dev\lloyds_reserve_stress_testing"
ANA = r"D:\dev\IME-Lloyds-exposure-composition"
TAG = "extraction" if os.path.normcase(os.path.abspath(BASE)) == os.path.normcase(EXT) else "analysis"

TX = re.compile(r"\bRITC\b|reinsur\w*[- ]to[- ]close|\btransferr?(?:ed|ing|s)?\b|\bquota[- ]?shares?\b|\bQS\b|"
                r"\bLPTs?\b|loss portfolio|portfolio transfer|\bnovat\w*|\bcommut\w*|\btake[- ]?on\b|\btaken on\b",
                re.I)
REASON = re.compile(r"distort\w*|unreliab\w*|not reliab\w*|unsuitab\w*|could not|cannot|can't|not possible|"
                    r"\bnull\b|excluded?|not (?:be )?(?:used|usable|extracted|comparable|meaningful|derived)|"
                    r"contaminat\w*|\bdue to\b|\bbecause\b|owing to|as a result|affect\w*|impact\w*|"
                    r"not reflect\w*|inflat\w*|misleading", re.I)
SYND = re.compile(r"\bsyndicates?\s*(?:no\.?\s*)?(\d{3,4})\b", re.I)


def sentences(text):
    flat = re.sub(r"\s+", " ", text or "").strip()
    return [s for s in re.split(r"(?<=[.;])\s+(?=[A-Z(\"'])", flat) if s]


def own_words(block):
    dqn = sentences(block.get("data_quality_notes"))
    rcp = [re.sub(r"\s+", " ", x).strip() for x in (block.get("raw_causal_phrases") or []) if isinstance(x, str)]
    pye = []
    for e in block.get("prior_year_events") or []:
        if isinstance(e, dict):
            s = " -- ".join(x for x in (e.get("event_name"), e.get("impact_description")) if x)
            if s:
                pye.append(re.sub(r"\s+", " ", s))
    return dqn, rcp, pye


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def main():
    ritc = load(os.path.join(EXT, "pdf_extraction", "ritc_scan.json"))
    pts = load(os.path.join(EXT, "pdf_extraction", "portfolio_transfer_scan.json"))
    new_pts_p = os.path.join(HERE, "rescan", "transfer_new_a.json")
    new_pts = load(new_pts_p) if os.path.exists(new_pts_p) else {}
    reg = load(os.path.join(EXT, "pdf_extraction", "audit", "portfolio_transfer_adjudication.json"))
    confirmed = {r["stem"] for r in reg["records"] + reg.get("found_by_hand", [])
                 if r.get("verdict") == "genuine" and r.get("direction") in ("inward", "both")}
    fp_removed = {x.get("stem") for x in reg.get("summary", {}).get("false_positives_found_and_removed_this_round", [])
                  if isinstance(x, dict)}
    not_dev = {k for k in load(os.path.join(ANA, "data", "takeon_not_development.json")) if not k.startswith("_")}
    base_adj = {k for k in load(os.path.join(ANA, "data", "opening_reserves_takeon_base.json")) if not k.startswith("_")}
    res = load(os.path.join(ANA, "model", "exposure_results.json"))
    obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in res["observations"]}
    ws = {k for k, o in obs.items() if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
          and o.get("hhi") is not None}

    rows, unreadable = [], []
    for f in sorted(glob.glob(os.path.join(BASE, "pdf_extraction", "syndicate_*_*.json"))):
        m = re.match(r"syndicate_(\d+)_(\d{4})\.json$", os.path.basename(f))
        if not m:
            continue
        stem = "%s_%s" % (m.group(1), m.group(2))
        try:
            d = load(f)
        except Exception as exc:  # a record another process is writing
            unreadable.append((stem, repr(exc)[:120]))
            continue
        models = d.get("models") or {}
        if len(models) < 2:
            continue
        per = {}
        for name, b in models.items():
            route = b.get("_pyd_route") or {}
            dqn, rcp, pye = own_words(b)
            per[name] = {
                "route_note": route.get("note"), "route_source": route.get("source"),
                "route_value": route.get("value"), "model_value": route.get("model_value"),
                "filled": route.get("note") == "filled a blank model value",
                "blames": [s for s in dqn if TX.search(s) and REASON.search(s)],
                "names": [s for s in rcp + pye if TX.search(s)],
                "mentions_in_notes": [s for s in dqn if TX.search(s) and not REASON.search(s)],
            }
        all_filled = all(v["filled"] for v in per.values())
        any_filled = any(v["filled"] for v in per.values())
        all_blame = all(v["blames"] for v in per.values())
        any_blame = any(v["blames"] for v in per.values())
        all_name = all(v["blames"] or v["names"] or v["mentions_in_notes"] for v in per.values())
        if all_filled and all_blame:
            tier = "A"
        elif all_filled and all_name:
            tier = "B"
        elif any_filled and any_blame:
            tier = "C"
        else:
            continue
        own = m.group(1)
        others = sorted({n.lstrip("0") for v in per.values() for s in v["blames"] + v["names"]
                         for n in SYND.findall(s) if n.lstrip("0") != own.lstrip("0")})
        o = obs.get(stem) or {}
        rows.append({
            "stem": stem, "tier": tier, "in_working_sample": stem in ws,
            "S": o.get("s_raw_a"), "M_gbp_m": o.get("pyd_gbp_m"), "R_gbp_m": o.get("opening_reserves_gbp_m"),
            "other_syndicates_named": others,
            "ritc_scan_committed": (ritc.get(stem) or {}).get("ritc_occurred"),
            "transfer_scan_committed": (pts.get(stem) or {}).get("transfer_occurred") if stem in pts else "not scanned",
            "transfer_scan_rescan": (new_pts.get(stem) or {}).get("transfer_occurred") if new_pts else None,
            "register": ("confirmed inward/both" if stem in confirmed else
                         "listed as a removed false positive" if stem in fp_removed else None),
            "takeon_registers": [n for n, s in (("TAKEON_NOT_DEVELOPMENT", not_dev), ("TAKEON_BASE", base_adj))
                                 if stem in s],
            "models": per,
        })

    def order(r):
        return (r["tier"], not r["in_working_sample"], -abs(r["S"] or 0), -abs(r["M_gbp_m"] or 0))
    rows.sort(key=order)
    out_json = os.path.join(HERE, "census_filled_blanks_%s.json" % TAG)
    with io.open(out_json, "w", encoding="utf-8", newline="") as fh:
        json.dump({"base": BASE, "unreadable": unreadable, "rows": rows}, fh, indent=1, ensure_ascii=False)

    lines = ["base: %s | unreadable record files: %s" % (BASE, unreadable or "none"),
             "tier A %d, tier B %d, tier C %d" % tuple(sum(1 for r in rows if r["tier"] == t) for t in "ABC"), ""]
    for r in rows:
        regime = ("RITC" if r["ritc_scan_committed"] else "") + (" REG" if r["register"] == "confirmed inward/both" else "")
        lines.append("== %s tier %s | WS=%s S=%s M=%s R=%s | regime: %s | transfer scan committed=%s rescan=%s | "
                     "register=%s | take-on=%s | other syndicates named: %s" % (
                         r["stem"], r["tier"], r["in_working_sample"],
                         None if r["S"] is None else round(r["S"], 4), r["M_gbp_m"], r["R_gbp_m"],
                         regime.strip() or "none", r["transfer_scan_committed"], r["transfer_scan_rescan"],
                         r["register"], r["takeon_registers"] or "none", r["other_syndicates_named"] or "none"))
        for name, v in r["models"].items():
            lines.append("   %s: route %s via %s = %s%s" % (
                name, v["route_note"], v["route_source"], v["route_value"],
                "" if v["model_value"] is None else " (model's own value %s)" % v["model_value"]))
            for s in v["blames"]:
                lines.append("      notes (reason): %s" % s[:420])
            for s in v["mentions_in_notes"]:
                lines.append("      notes (names):  %s" % s[:420])
            for s in v["names"]:
                lines.append("      phrase/event:   %s" % s[:420])
        lines.append("")
    out_txt = os.path.join(HERE, "census_filled_blanks_%s.txt" % TAG)
    with io.open(out_txt, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:3]))
    print("wrote", out_json, "and", out_txt)


if __name__ == "__main__":
    main()
