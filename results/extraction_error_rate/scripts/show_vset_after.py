r"""The new sample's verification set (fourth amendment): one line per record, or one record in detail.

    python show_vset_after.py                       every record the second reader verifies: why it is in the
                                                    set, the figure's source, the first and clarified verdicts,
                                                    the adopted and filing figures, and any second reading
    python show_vset_after.py syndicate_2008_2021   one record: the brief's essentials, the first reading's
                                                    evidence and arithmetic, the clarified verdict and why

It reads error-rate-verdicts-after.json, error-rate-verification-set-after.json,
error-rate-verification-after.json and error-rate-briefs-after.json, and prints no filing page (use
second_read.py --after or filing_pages.py for pages). Read-only.
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


rows = {r["stem"]: r for r in load("error-rate-verdicts-after.json")}
vset = load("error-rate-verification-set-after.json")
verified = {v["stem"]: v for v in load("error-rate-verification-after.json")}
briefs = {b["stem"]: b for b in load("error-rate-briefs-after.json")}
reasons = {s: [k for k, members in vset.items() if isinstance(members, list) and k != "all" and s in members]
           for s in vset["all"]}


def cut(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + " ..."


if len(sys.argv) == 1:
    todo = [s for s in vset["all"] if s not in verified]
    print("verification set %d; second readings recorded %d; still to read %d" % (len(vset["all"]), len(verified), len(todo)))
    for s in vset["all"]:
        r, b, v = rows[s], briefs[s], verified.get(s)
        print("%-22s %-6s first %-14s clarified %-14s adopted %-10s filing %-10s triangle %-10s %s | %s"
              % (s, r["figure_source"], r["verdict"], r["clarified_verdict"],
                 b["adopted_prior_year_development_m_report_currency"], r.get("filing_figure_m"),
                 r.get("triangle_recomputation_m"),
                 ("SECOND %s%s" % (v["verdict"], " (carried)" if v.get("carried_over_from") else "")) if v else "to read",
                 ",".join(x.replace("_", " ") for x in reasons[s])))
    print("still to read: %s" % todo)
else:
    for s in sys.argv[1:]:
        r, b = rows[s], briefs[s]
        print("=" * 100)
        print("%s  %s  currency %s  canonical %s  in the set because: %s" % (
            s, r["figure_source"], b["report_currency"], b["canonical_model"], ", ".join(reasons.get(s, [])) or "not in the set"))
        print("  adopted %s; opening %s; route %s; cited %s; basis %s; cohort %s" % (
            b["adopted_prior_year_development_m_report_currency"], b["adopted_opening_reserves_m_report_currency"],
            json.dumps(b["route"]), b["cited_pages"], b["loader_basis"], b["loader_cohort_scope"]))
        print("  model notes: %s" % cut(b.get("model_notes"), 700))
        print("  FIRST (%s): %s; filing %s; pages %s; error kind %s" % (
            r.get("first_reader"), r["verdict"], r.get("filing_figure_m"), r.get("pages"), r.get("error_kind")))
        print("    quote: %s" % cut(r.get("quote"), 700))
        print("    arithmetic: %s" % cut(r.get("arithmetic"), 900))
        print("    triangle: %s on pages %s: %s" % (r.get("triangle_recomputation_m"), r.get("triangle_pages"),
                                                   cut(r.get("triangle_arithmetic"), 1400)))
        print("    basis: %s | binding: %s" % (cut(r.get("basis_check"), 250), cut(r.get("page_binding_check"), 250)))
        print("    opening: %s" % json.dumps(r.get("opening_reserves")))
        print("    reasoning: %s" % cut(r.get("reasoning"), 700))
        print("  CLARIFIED: %s -- %s" % (r["clarified_verdict"], r.get("clarified_why")))
        if s in verified:
            v = verified[s]
            print("  SECOND: %s%s; filing %s; pages %s; why: %s" % (
                v["verdict"], " (carried over)" if v.get("carried_over_from") else "", v.get("filing_figure_m"),
                v.get("pages"), cut(v.get("why"), 600)))
