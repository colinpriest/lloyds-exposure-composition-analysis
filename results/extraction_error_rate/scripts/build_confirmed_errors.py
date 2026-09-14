r"""The errors confirmed before repair, for the propagation's shift model (error-rate-protocol.md, fifth amendment,
point 5: "a shift drawn from the errors confirmed before repair").

Every error that two readings confirmed in an extraction before its repair, whichever reading found it, each once:
  * the second sample's final errors (2008/2021, 3624/2015);
  * the first sample's errors that persisted in that extraction with the same adopted figure
    (persisting-first-sample-errors.json: 2010/2019, 4444/2022; 3624/2015 is the second sample's);
  * the take-on census's errors (2008/2019; 2008/2021 is the second sample's);
  * the confirmed errors among the records found in passing (error-rate-passing-result.json, when it exists);
  * the third sample's errors, both readings error (eighth amendment), where the readings give the filing's figure;
  * the eighth census's confirmed errors whose two readings agree on the filing's figure
    (error-rate-census-eighth-result.json, when it exists).
Each carries the adopted figure, the filing's figure and the opening reserves, all in the report's currency. For the
first four sources the filing's figure is the second reading's, else the first's, else the first reading's triangle
recomputation; for the third sample and the eighth census it is a reading's filing figure only, because a recomputation
there can be of the wrong table (1880/2014's is the net table's). A confirmed error with no filing figure defines no
shift: it is listed, not written. Writes error-rate-confirmed-errors.json.

    python build_confirmed_errors.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


def by_stem(name):
    p = SCR / name
    return {r["stem"]: r for r in json.load(io.open(str(p), encoding="utf-8"))} if p.exists() else {}


def figure(second, first, recomputation=True):
    options = [(second, "filing_figure_m", "second reading"), (first, "filing_figure_m", "first reading")]
    if recomputation:
        options.append((first, "triangle_recomputation_m", "first reading's triangle recomputation"))
    for row, key, how in options:
        if (row or {}).get(key) is not None:
            return row[key], how
    return None, None


out, no_figure = {}, []


def add(stem, source, briefs, second, first, recomputation=True):
    if stem in out:
        return
    fig, how = figure(second.get(stem), first.get(stem), recomputation)
    if fig is None and not recomputation:
        no_figure.append("%s (%s)" % (stem, source))
        return
    out[stem] = {"stem": stem, "from": source, "adopted_m": briefs[stem][ADOPTED], "filing_m": fig,
                 "filing_figure_from": how, "opening_m": briefs[stem][OPENING]}


after_final = load("error-rate-result-after-rerun.json")["rules"]["clarified"]["final_verdicts"]
for s, v in sorted(after_final.items()):
    if v == "error":
        add(s, "second sample", by_stem("error-rate-briefs-after.json"), by_stem("error-rate-verification-after.json"),
            by_stem("error-rate-verdicts-after.json"))
for r in load("persisting-first-sample-errors.json"):
    add(r["stem"], "first sample, persisting", by_stem("error-rate-briefs.json"), by_stem("error-rate-verification.json"),
        by_stem("error-rate-verdicts.json"))
for r in load("error-rate-takeon-result.json")["records"]:
    if r["second_verdict"] == "error" and r["first_verdict"] == "error":
        add(r["stem"], "take-on census", by_stem("error-rate-briefs-takeon.json"),
            by_stem("error-rate-verification-takeon.json"), by_stem("error-rate-verdicts-takeon.json"))
if (SCR / "error-rate-passing-result.json").exists():
    for s in load("error-rate-passing-result.json")["confirmed_errors"]:
        add(s, "found in passing", by_stem("error-rate-briefs-passing.json"),
            by_stem("error-rate-verification-passing.json"), by_stem("error-rate-verdicts-passing.json"))

third_first, third_second = by_stem("error-rate-verdicts-third.json"), by_stem("error-rate-verification-third.json")
for s in load("error-rate-sample-third.json")["third"]["stems"]:
    if (third_first.get(s) or {}).get("clarified_verdict") == "error" and (third_second.get(s) or {}).get("verdict") == "error":
        # both readings must give the filing's figure and agree on it, as the repair rule requires: 1980/2018's first
        # reading wrote 0.0 for an empty recomputation, and its second reading found no figure
        f1, f2 = third_first[s].get("filing_figure_m"), third_second[s].get("filing_figure_m")
        if f1 is None or f2 is None or abs(float(f1) - float(f2)) > max(0.5, 0.05 * abs(float(f2))):
            no_figure.append("%s (third sample: no agreed filing figure)" % s)
            continue
        add(s, "third sample", by_stem("error-rate-briefs-third.json"), third_second, third_first, recomputation=False)
if (SCR / "error-rate-census-eighth-result.json").exists():
    for r in load("error-rate-census-eighth-result.json")["records"]:
        f1, f2 = r.get("first_figure_m"), r.get("second_figure_m")
        if not r.get("confirmed_error"):
            continue
        if f1 is None or f2 is None or abs(float(f1) - float(f2)) > max(0.5, 0.05 * abs(float(f2))):
            no_figure.append("%s (eighth census: no agreed filing figure)" % r["stem"])
            continue
        add(r["stem"], "eighth census", by_stem("error-rate-briefs-eighth.json"),
            by_stem("error-rate-verification-eighth.json"), by_stem("error-rate-verdicts-eighth.json"), recomputation=False)

rows = sorted(out.values(), key=lambda r: r["stem"])
bad = [r["stem"] for r in rows if None in (r["adopted_m"], r["filing_m"], r["opening_m"])]
if bad:
    raise SystemExit("an error without an adopted figure, a filing figure or opening reserves: %s" % bad)
io.open(str(SCR / "error-rate-confirmed-errors.json"), "w", encoding="utf-8").write(json.dumps(rows, indent=1))
for r in rows:
    print("  %-22s %-26s adopted %-9s filing %-9s opening %-9s shift %+.4f (%s)"
          % (r["stem"], r["from"], r["adopted_m"], r["filing_m"], r["opening_m"],
             (r["adopted_m"] - r["filing_m"]) / r["opening_m"], r["filing_figure_from"]))
print("confirmed errors before repair: %d; written error-rate-confirmed-errors.json" % len(rows))
print("confirmed errors with no filing figure (no shift): %s" % no_figure)
