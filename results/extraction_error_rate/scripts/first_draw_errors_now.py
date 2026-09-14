"""The first draw's errors: the adopted figure then, the filing's figure, and whether persisting-first-sample-errors.json
lists the record with the figure unchanged (read-only).

    python first_draw_errors_now.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent


def load(name):
    d = json.load(io.open(str(SCR / name), encoding="utf-8"))
    if isinstance(d, dict):
        d = d.get("verdicts") or [v for v in d.values() if isinstance(v, dict)]
    return {v["stem"]: v for v in d if isinstance(v, dict) and "stem" in v}


r1 = json.load(io.open(str(SCR / "error-rate-result.json"), encoding="utf-8"))
errs = sorted(s for s, v in r1["rules"]["clarified"]["final_verdicts"].items() if v == "error")
first, second = load("error-rate-verdicts.json"), load("error-rate-verification.json")
pers = {r["stem"]: r for r in json.load(io.open(str(SCR / "persisting-first-sample-errors.json"), encoding="utf-8"))}
print("persisting file lists: %s" % sorted(pers))
for s in errs:
    f, g = first.get(s) or {}, second.get(s) or {}
    p = pers.get(s)
    print("%-22s adopted then %-9s filing (second %s, first %s) kind %s | persisting %s" % (
        s, f.get("adopted_figure_m"), g.get("filing_figure_m"), f.get("filing_figure_m"),
        g.get("error_kind") or f.get("error_kind"),
        None if p is None else {k: p.get(k) for k in ("adopted_now", "same_figure", "in_working_sample", "kind")}))
