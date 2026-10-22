r"""Build data/aggregated_column_review.json: the review of the older-years ("& prior") columns of the primary sample.

Equation (1)'s outcome is the gross prior-year movement over the underwriting years u <= t-2, from the year t report's
printed gross claims development table. Appendix 2.1's rule for an older-years column such as "2013 and prior": the
column is one of the mature years only if its LAST STEP (its latest cell less the cell before it in the year t table) is a
like-for-like movement of the same underwriting years during year t. A column the table restates BY CALENDAR YEAR passes
the test (each cell is the total of the same years at one calendar date). A column built BY DEVELOPMENT AGE (the year t
cell at age a is the year t-1 report's older column at age a plus the underwriting year that joined the block) fails it,
because the last step mixes calendar dates; and a column with no development of its own (a single figure) is not part of
the triangle.

The register holds one entry for each of the 64 records of the primary sample whose gross claims development table was
read in round 2 (23 October 2026): two independent arms (X1-X8 and Y1-Y8) read each record once, and two tie-break
readers (Z1, Z2) read the 13 records on which the arms' constructions could not be settled or disagreed. The readings,
briefs, batches and the comparison are archived under results/extraction_error_rate/mature-cohort/round2/ and this script
reads them there. The figures the primary adopts are not changed by this register, except for 1945/2022 (the column leaves
the figure: -13.840 to -13.831, data/mature_cohort_figures.json). The decisions below that are not the readers' own
agreement are decisions of the Claude analysis session.

Usage:
  python src/build_aggregated_column_review.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_aggregated_column_review.py --write    # rebuild and write the register
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))

REGISTER = HERE / "data" / "aggregated_column_review.json"
ROUND2 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round2"
TASK = "aggregated_column"
ARM_READERS = tuple("%s%d" % (arm, i) for arm in "XY" for i in range(1, 9))
TIEBREAK_READERS = ("Z1", "Z2")
TOL_ABS_M = 0.5
TOL_REL = 0.01
FIGURE_TOL = 0.0015
CONSTRUCTIONS = ("calendar_year", "development_age", "no_own_development", "undeterminable")
#: the readers' own words for the same construction
CONSTRUCTION_ALIAS = {"no_older_years_column": "no_own_development", "calendar_restated": "calendar_year"}

#: the six records whose construction could not be settled (decision of the Claude analysis session, 23 October 2026);
#: the least-certain-records sensitivity (src/check_low_confidence_sensitivity.py) reads them from the register
LOW_CONFIDENCE = ("3624_2015", "1955_2018", "1200_2015", "2007_2015", "33_2015", "1200_2017")

#: the figure the primary adopts after this register: only 1945/2022 moves (data/mature_cohort_figures.json)
ADOPTED_AFTER = {"1945_2022": -13.831}

RULE = (
    "Appendix 2.1 and Equation (1): the outcome is the gross prior-year movement over the underwriting years u <= t-2 "
    "of the year t report's printed gross claims development table. An older-years column (such as '2013 and prior') is "
    "one of those mature years only if its last step (its latest cell less the cell before it, in the year t table) is a "
    "like-for-like movement of the same set of underwriting years during year t. Restated BY CALENDAR YEAR (the year t "
    "report recomputes the whole column for its coverage, so each cell is the total of the same years at one calendar "
    "date; the label is fixed, or the rows read 'n years or more later'): the last step is like for like and the column "
    "stays in. Built BY DEVELOPMENT AGE (the year t cell at age a is the year t-1 report's older column at age a plus "
    "the underwriting year that joined the block, so its coverage grows by one year each report): the last step mixes "
    "calendar dates, so the column is left out. A column with no development of its own (a single figure, or one the "
    "stored grid does not carry) is not part of the triangle and is left out. rule_figure_m is the figure the test "
    "gives, adopted_figure_m the figure the primary adopts, and consistent says whether the two are the same figure "
    "(the adopted figure treats the column as the rule does; null where the construction is undeterminable, so there is "
    "no single rule figure); agrees_within_tolerance is the readers' looser test, within 0.5m or 1% (for an "
    "undeterminable construction, within it of every candidate figure). The structured fields (construction, "
    "last_step_like_for_like, rule_includes_column, rule_figure_m, consistent) follow the readers' construction by the "
    "rule and nothing else. One record is the exception: 1200_2017 is adopted against the rule as the readers apply it "
    "(the column stays in, 44.9, where the rule leaves it out, 40.5). Its structured fields carry the readers' view "
    "(rule_includes_column false, rule_figure_m 40.5, consistent false); adopted_by_decision is true and decision_override "
    "records the figure adopted and the decision, a decision of the Claude analysis session, 23 October 2026. A record "
    "whose construction, or whose application of the rule, could not be settled is marked confidence 'low_confidence'; "
    "its adopted figure stands (a decision of the Claude analysis session, 23 October 2026).")

#: decisions that are not the plain agreement of the two arms. construction is the construction the register records;
#: rule: 'including' (the column stays in: the last step is like for like), 'excluding' (the column is left out), or
#: 'undetermined'; confidence one of high / medium / low_confidence (None: from the readers); text is the reason.
DECISIONS = {
    "1200_2015": dict(construction="calendar_year", rule="including", confidence="low_confidence", text=(
        "X2 undeterminable (no year t-1 table); Y3 calendar_year; the tie-break readers Z1 and Z2 both find it restated "
        "by calendar year, each with medium confidence. The adopted 0.5 (column in) stands; with the column left out the "
        "figure would be 8.4. The construction rests on an inference from the 2016 report (the oldest column there is a "
        "single underwriting year, 2010, at the same factor as 2011), so the record is low confidence.")),
    "1200_2017": dict(construction="development_age", rule="excluding", confidence="low_confidence", text=(
        "X3, Y4, Z1 and Z2 all find the column built by development age (the 2017 cell at age a is the 2016 report's "
        "2010 column plus UY2011 at age a), so the rule leaves it out (40.5). The structured fields of this entry "
        "(rule_includes_column, rule_figure_m, last_step_like_for_like, consistent) are the readers' application of the "
        "rule. The primary adopts 44.9 (the column in) against it, by a decision recorded in decision_override. Z2 would "
        "leave the column out (40.5); Z1 (medium) would keep 44.9."),
        override=dict(adopted_figure_m=44.9, adopted_includes_column=True, text=(
            "Decision of the Claude analysis session, 23 October 2026: the column stays in (44.9), against the rule as "
            "the readers apply it (40.5), because its second-to-last cell equals the end-2016 calendar total (UY2010 "
            "266.9 at ages 5 and 6 in the 2016 report), so the last step holds only 2017 movements, and leaving the "
            "column out would drop UY2011's 2017 movement. The rule's application to this column could not be settled, "
            "so the record is low confidence."))),
    "1955_2018": dict(construction="calendar_year", rule="including", confidence="low_confidence", text=(
        "X6 development_age (rule 18.5); Y7 undeterminable; Z1 (medium) and Z2 (low) calendar_restated. No year t-1 "
        "report is in the corpus (the 2019 report is used as year t+1). The adopted 16.7 (column in) stands; with the "
        "column left out the figure would be 18.5. The construction could not be settled, so the record is low confidence.")),
    "1955_2015": dict(construction="undeterminable", rule="undetermined", confidence="medium", text=(
        "X5 undeterminable (no comparable table in the year t-1 or t+1 report); Y6 development_age. The two candidate "
        "figures, 11.444 with the column and 11.763 without it, differ by 0.319m, inside the 0.5m tolerance, so the "
        "adopted 11.444 is consistent with the rule under either construction.")),
    "1955_2020": dict(construction="calendar_year", rule="including", confidence=None, text=(
        "X8 and Y1 development_age (rule 10.7); the tie-break readers Z1 and Z2 (both high) find it restated by calendar "
        "year, so the column stays in and the adopted 15.9 stands.")),
    "2791_2022": dict(construction="calendar_year", rule="including", confidence=None, text=(
        "X4 and Y5 development_age (rule -8.245); the tie-break readers Z1 and Z2 (both high) find it restated by "
        "calendar year, so the column stays in and the adopted -17.497 stands.")),
    "2791_2023": dict(construction="calendar_year", rule="including", confidence=None, text=(
        "X5 calendar_year, Y6 development_age; the tie-break readers Z1 and Z2 (both high) find it restated by calendar "
        "year, so the column stays in and the adopted -35.529 stands.")),
    "2791_2024": dict(construction="calendar_year", rule="including", confidence=None, text=(
        "X6 development_age, Y7 calendar_year; the tie-break readers Z1 and Z2 (both high) find it restated by calendar "
        "year, so the column stays in and the adopted -36.191 stands.")),
    "2007_2015": dict(construction="development_age", rule="excluding", confidence="low_confidence", text=(
        "X1, Y2 and Z2 development_age; Z1 undeterminable. No year t-1 table exists; the call rests on the paid pattern "
        "(4% paid at the first step, as a single underwriting year) and on the filing's net release on the 2013 and "
        "prior years (p7). The adopted -2.0 (column out, the code triangle's figure) stands; with the column in the "
        "figure would be 148.8. The construction rests on inference, so the record is low confidence.")),
    "33_2015": dict(construction="calendar_year", rule="including", confidence="low_confidence", text=(
        "X1 and Y2 calendar_year, from the shape of the year t table alone (no year t-1 table in the corpus: the column "
        "is a flat stock re-estimated at successive year ends, and the 2016 report's 'Provision in respect of prior "
        "years' covers the same pre-2011 set). The adopted -118.31 (column in) stands; with the column out the figure "
        "would be -86.114. The evidence is structural only, so the record is low confidence.")),
    "3624_2015": dict(construction="undeterminable", rule="undetermined", confidence="low_confidence", text=(
        "X7 and Y8 undeterminable: no year t-1 table exists and the 2016 report prints no older-years column. The "
        "adopted 5.025 includes the column (the column carries the whole pre-2011 gross balance, 393,088 in all with "
        "the other years); excluding it would give -0.912. The construction could not be settled, so the record is "
        "low confidence and its adopted figure stands.")),
    "1945_2022": dict(construction="development_age", rule="excluding", confidence=None, text=(
        "X4, Y5, Z1 and Z2 all find the '2012&Prior' column built by development age (the 2021 report's UY2011 column "
        "plus UY2012 at each age, at a uniform factor of 1.0606 on ages 4 to 9). The column is left out: the figure "
        "moves from -13.840 to -13.831 (data/mature_cohort_figures.json, decision of the Claude analysis session, "
        "23 October 2026).")),
}


# ----------------------------------------------------------------------------------------------------- readings
def _load(path):
    with io.open(str(path), encoding="utf-8") as fh:
        return json.load(fh)


def sort_key(k):
    return tuple(int(p) for p in k.split("_"))


def load_batches():
    """{key: batch record} of the aggregated-column task, from the archived X and Y batches (each record once per arm)."""
    out = {}
    for rid in ARM_READERS:
        for rec in _load(ROUND2 / "batches" / ("%s.json" % rid)):
            if rec["task"] == TASK:
                out.setdefault(rec["key"], rec)
    return out


def load_arm_readings():
    """{key: [(reader, entry), ...]} from the X and Y arms."""
    out = {}
    for rid in ARM_READERS:
        for name, e in _load(ROUND2 / "readings" / ("%s.json" % rid)).items():
            if name.endswith("|" + TASK):
                out.setdefault(e["key"], []).append((rid, e))
    return out


def load_tiebreak_readings():
    """{key: [(reader, entry), ...]} from the tie-break readers Z1 and Z2."""
    out = {}
    for rid in TIEBREAK_READERS:
        for key, e in _load(ROUND2 / "readings" / ("%s.json" % rid)).items():
            out.setdefault(key, []).append((rid, e))
    return out


def _ints(vals):
    if not isinstance(vals, list):
        vals = [vals]
    out = []
    for v in vals:
        if isinstance(v, int) and not isinstance(v, bool):
            out.append(v)
        elif isinstance(v, str):
            out += [int(m) for m in re.findall(r"\bp(\d+)", v)]
    return out


def pages_of(key, pages):
    """{'year_t': [...], 'other_reports': {name: [...]}} from a reader's `pages`: a list for the record's own filing, or
    a dict keyed by report (the filing, '<t>_report', 'year_t', or 'year_t_minus_1')."""
    year = key.split("_")[1]
    if isinstance(pages, list):
        # ints are the record's own filing; a string names a filing and its pages ('435_2018 p36, p29')
        own, other = [p for p in pages if isinstance(p, int)], {}
        for s in (p for p in pages if isinstance(p, str)):
            m = re.match(r"(?:syndicate_)?(\d+_\d{4})\b", s)
            ps = _ints(s)
            if m is None or m.group(1) == key:
                own += ps
            elif ps:
                other[m.group(1)] = other.get(m.group(1), []) + ps
        return {"year_t": own, "other_reports": other}
    own, other = [], {}
    for name, val in pages.items():
        is_own = (name.endswith(key) or name == "year_t" or name == "%s_report" % year
                  or name.startswith("%s report" % year))
        if is_own:
            own += _ints(val)
        elif _ints(val):
            other[name] = _ints(val)
    return {"year_t": own, "other_reports": other}


def norm_construction(c):
    c = CONSTRUCTION_ALIAS.get(c, c)
    if c not in CONSTRUCTIONS:
        raise SystemExit("construction %r is not one of %s" % (c, CONSTRUCTIONS))
    return c


def _num(v):
    """v as a float when it is a number, else None (Z2 gives 4242/2021 and 4242/2023's `figure_including_m` as a note)."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def arm_reading(key, rid, e):
    out = {
        "reader": rid, "arm": rid[0],
        "construction": norm_construction(e["construction"]),
        "verdict": e["verdict"],
        "rule_figure_m": _num(e.get("rule_figure_m")),
        "figure_including_column_m": _num(e.get("figure_including_column_m")),
        "figure_excluding_column_m": _num(e.get("figure_excluding_column_m")),
        "pages": pages_of(key, e["pages"]),
    }
    if isinstance(e.get("rule_figure_m"), str):
        out["rule_figure_note"] = e["rule_figure_m"]      # e.g. Y7 on 1955/2018 gives both candidates as text
    return out


def tiebreak_reading(key, rid, e):
    out = {
        "reader": rid, "arm": "Z",
        "construction": norm_construction(e["construction"]),
        "confidence": e["confidence"],
        "rule_figure_m": _num(e.get("rule_figure_m")),
        "figure_including_column_m": _num(e.get("figure_including_m")),
        "figure_excluding_column_m": _num(e.get("figure_excluding_m")),
        "pages": pages_of(key, e["pages"]),
    }
    if isinstance(e.get("figure_including_m"), dict):
        out["figure_including_note"] = e["figure_including_m"]
    return out


def _agree(vals):
    vals = [v for v in vals if v is not None]
    return vals[0] if vals and all(abs(v - vals[0]) <= FIGURE_TOL for v in vals) else None


def within_tolerance(adopted, rule):
    d = abs(adopted - rule)
    return d <= TOL_ABS_M or d <= TOL_REL * abs(rule)


def currency_and_gbp(key, figure):
    import run_analysis as ra
    cur = ra.FX_CURRENCIES.get(key, "UNDETERMINED")
    if cur != "USD":
        return cur, round(figure, 6)
    return cur, round(figure / ra.FX_RATES[int(key.rsplit("_", 1)[1])]["usd_per_gbp"], 6)


# ----------------------------------------------------------------------------------------------------- entries
def _numbers(text):
    """The numbers a decision text prints ('(44.9)', '-13.831', '60.0'), with their sign."""
    return [float(m.replace("−", "-")) for m in re.findall(r"(?<![\w.,])[-−]?\d+(?:\.\d+)?(?![\w])", text)]


def check_override(key, override, adopted, includes):
    """Stop the build unless the override is a decision about the figure the register adopts: it carries its own
    `adopted_figure_m`, equal to the adopted figure within FIGURE_TOL and printed in its decision text, and its own
    `adopted_includes_column`, equal to whether the adopted figure includes the column and stated by the text ('the column
    stays in' or 'the column is left out'). A text that names another figure, or says the column is in where the flag says
    it is out, is a decision about something else."""
    figure, flag, text = override.get("adopted_figure_m"), override.get("adopted_includes_column"), override["text"]
    if (not isinstance(figure, (int, float)) or isinstance(figure, bool) or abs(figure - adopted) > FIGURE_TOL):
        raise SystemExit("%s: an override carries its own adopted_figure_m, equal to the adopted figure %s within %s; it "
                         "has %r" % (key, adopted, FIGURE_TOL, figure))
    if not any(abs(n - figure) <= FIGURE_TOL for n in _numbers(text)):
        raise SystemExit("%s: an override's decision text does not print its adopted figure %s" % (key, figure))
    if not isinstance(flag, bool) or flag != includes:
        raise SystemExit("%s: an override's adopted_includes_column %r is not the adopted figure's (%r)" % (key, flag, includes))
    says = ("column stays in" if flag else r"column (?:is )?(?:left out|stays out)")
    if not re.search(says, text, re.IGNORECASE):
        raise SystemExit("%s: an override's decision text does not say the column %s, as adopted_includes_column says"
                         % (key, "stays in" if flag else "is left out"))


def entry_for(key, batch, arms, tiebreak):
    readers = [arm_reading(key, rid, e) for rid, e in sorted(arms, key=lambda p: p[0])]
    if [r["arm"] for r in readers] != ["X", "Y"]:
        raise SystemExit("%s: one X-arm and one Y-arm reading are needed, got %s" % (key, [r["reader"] for r in readers]))
    breaks = [tiebreak_reading(key, rid, e) for rid, e in sorted(tiebreak, key=lambda p: p[0])]
    # the figures with and without the column are the readers' (recomputed from the printed table). For Part A records
    # the extraction's estimator on the stored grid is a further check; for Part B the column is not in the stored grid,
    # and the batch's grid figure is not always the printed table's (1274_2023: 58.692 against the printed 87.073)
    from_grid = batch["part"] == "A"
    incl = _agree([r["figure_including_column_m"] for r in readers + breaks]
                  + ([batch.get("grid_figure_with_column_m")] if from_grid else []))
    excl = _agree([r["figure_excluding_column_m"] for r in readers + breaks]
                  + ([batch.get("grid_figure_without_column_m")] if from_grid else []))
    before = batch["adopted_figure_m"]
    adopted = ADOPTED_AFTER.get(key, before)
    includes_after = False if key in ADOPTED_AFTER else bool(batch["adopted_figure_includes_column"])
    dec = DECISIONS.get(key)
    override = (dec or {}).get("override")
    if override is not None and (not isinstance(override, dict) or not isinstance(override.get("text"), str)
                                 or not override["text"].strip()
                                 or not isinstance(adopted, (int, float)) or isinstance(adopted, bool)):
        # a decision to adopt a figure against the rule is the session's words and the figure it adopts: an empty override
        # would record a decision nobody made
        raise SystemExit("%s: an override needs a decision text and an adopted figure; it has text %r and adopted figure %r"
                         % (key, None if not isinstance(override, dict) else override.get("text"), adopted))
    if override is not None:
        check_override(key, override, adopted, includes_after)
    xy = [r for r in readers]
    if dec is None:
        c = {r["construction"] for r in xy}
        v = {r["verdict"] for r in xy}
        rules = [r["rule_figure_m"] for r in xy]
        if len(c) != 1 or v != {"consistent"} or None in rules or abs(rules[0] - rules[1]) > FIGURE_TOL:
            raise SystemExit("%s: the arms do not agree (%s, %s, %s); the register needs a decision for it"
                             % (key, sorted(c), sorted(v), rules))
        construction = c.pop()
        rule = "including" if construction == "calendar_year" else "excluding"
        confidence = "high"
        text = ("X and Y agree: %s, rule figure %s (%s the column), the adopted figure %s."
                % (construction, rules[0], "with" if rule == "including" else "without", before))
    else:
        construction, rule, confidence, text = dec["construction"], dec["rule"], dec["confidence"], dec["text"]
    if dec is None:
        # both arms give the rule figure; where they also give the figure with or without the column, it is that one
        rule_figure = _agree([r["rule_figure_m"] for r in xy])
        check = incl if rule == "including" else excl
        if rule_figure is None or (check is not None and abs(check - rule_figure) > FIGURE_TOL):
            raise SystemExit("%s: the arms' rule figure %s is not the figure %s the column (%s)"
                             % (key, rule_figure, rule, check))
        if rule == "including":
            incl = rule_figure
        else:
            excl = rule_figure
    elif rule == "including":
        rule_figure = incl
    elif rule == "excluding":
        rule_figure = excl
    else:
        rule_figure = None
    if rule != "undetermined" and rule_figure is None:
        raise SystemExit("%s: the readers give no agreed figure %s the column" % (key, rule))
    if rule == "undetermined":
        # undeterminable construction: no single rule figure, so no verdict (null); the figure is within the readers'
        # tolerance only if it agrees with every candidate figure
        cands = [f for f in (incl, excl) if f is not None]
        consistent = None
        agrees = bool(cands) and all(within_tolerance(adopted, f) for f in cands)
    else:
        # consistent: the adopted figure is the rule's figure (the same treatment of the column); agrees_within_
        # tolerance: the readers' test, within 0.5m or 1%
        consistent = abs(adopted - rule_figure) <= FIGURE_TOL
        agrees = within_tolerance(adopted, rule_figure)
    if confidence is None:
        # tie-break records: the lowest confidence the tie-break readers gave, when they all agree with the construction
        order = {"high": 2, "medium": 1, "low": 0}
        agree = all(b["construction"] == construction for b in breaks)
        low = min((order[b["confidence"]] for b in breaks), default=2)
        confidence = "high" if agree and low == 2 else "medium"
    if (confidence == "low_confidence") != (key in LOW_CONFIDENCE):
        raise SystemExit("%s: confidence %s against the low-confidence list" % (key, confidence))
    # the test of the rule: is the column's last step a like-for-like movement during year t? A column with no
    # development of its own has no last step (null). The structured fields follow the construction by the rule and
    # nothing else; a figure the primary adopts against the rule is a decision recorded beside them (`override`)
    if construction in ("undeterminable", "no_own_development"):
        last_step = None
    else:
        last_step = construction == "calendar_year"
    if override is not None and (consistent is not False or rule == "undetermined"):
        raise SystemExit("%s: an override is a decision to adopt a figure against the rule's, but the adopted figure %s "
                         "is the rule's %s" % (key, adopted, rule_figure))
    if consistent is False and override is None:
        # the other direction: an adopted figure that is not the rule's is a decision, and it is recorded or it does not
        # build (no entry may be inconsistent by accident)
        raise SystemExit("%s: the adopted figure %s is not the rule's figure %s (the column %s), and the register records "
                         "no decision to adopt it against the rule (DECISIONS[%r]['override'])"
                         % (key, adopted, rule_figure, rule, key))
    cur, gbp = currency_and_gbp(key, adopted)
    pages = sorted({p for r in readers + breaks for p in r["pages"]["year_t"]})
    e = {
        "part": batch["part"],
        "column_label": batch.get("column_label_year_t") or batch.get("column_label_from_notes"),
        "construction": construction,
        "last_step_like_for_like": last_step,
        "rule_includes_column": {"including": True, "excluding": False, "undetermined": None}[rule],
        "rule_figure_m": rule_figure,
        "adopted_figure_m": adopted,
        "adopted_figure_gbp_m": gbp,
        "report_currency": cur,
        "adopted_includes_column": includes_after,
        "figure_before_this_register_m": before,
        "figure_with_column_m": incl,
        "figure_without_column_m": excl,
        "difference_m": None if rule_figure is None else round(adopted - rule_figure, 6),
        "consistent": consistent,
        "agrees_within_tolerance": agrees,
        "confidence": confidence,
        "readers": readers,
        "tie_break_readers": breaks,
        "pages": pages,
        "decision": text,
    }
    e["adopted_by_decision"] = override is not None
    if override is not None:
        e["decision_override"] = {
            "adopted_by_decision": True, "adopted_figure_m": override["adopted_figure_m"],
            "adopted_includes_column": override["adopted_includes_column"],
            "rule_figure_m": rule_figure, "rule_includes_column": e["rule_includes_column"],
            "decided_by": "decision of the Claude analysis session, 23 October 2026", "text": override["text"]}
    if key in ADOPTED_AFTER:
        e["consistent_before"] = abs(before - rule_figure) <= FIGURE_TOL
    return e


def population(batches, arms):
    agg = _load(ROUND2 / "measurement" / "aggcol.json")
    part_a = agg["A_aggregated_column_in_stored_grid"]
    part_b = agg["B_column_named_in_notes_not_in_stored_grid"]
    part_c = agg["C_heuristic_candidates_first_column_possibly_unlabelled_aggregate"]
    a_prim = sorted((k for k, v in part_a.items() if v.get("in_primary")), key=sort_key)
    b_prim = sorted((k for k, v in part_b.items() if v.get("in_primary")), key=sort_key)
    read = sorted(batches, key=sort_key)
    a_not_read = [k for k in a_prim if k not in batches]
    c_prim = sorted((k for k, v in part_c.items() if v.get("in_primary", True)), key=sort_key)
    if {k for k in batches if batches[k]["part"] == "A"} != {k for k in a_prim if k in batches}:
        raise SystemExit("Part A of the batches is not Part A of the measurement")
    if {k for k in batches if batches[k]["part"] == "B"} != set(b_prim):
        raise SystemExit("Part B of the batches is not Part B of the measurement")
    return {
        "records_read": len(read),
        "how_chosen": (
            "The measurement (round2/measurement/aggcol.json and report.md) scanned all 1,065 record files of the "
            "corpus for an older-years ('& prior') column. Part A: records whose stored gross RAG triangle carries the "
            "column (aggregated_cohort), %d in the primary sample. Part B: records whose extraction notes say the "
            "filing's table has an older-years column the stored grid leaves out, %d in the primary sample. Primary "
            "sample only: records outside it (510_2014, 557_2014, 2468_2016, 4020_2017, 5678_2015 and other records of "
            "the 672 construction alone) were not read. The %d records read are the %d of Part A in the primary that the "
            "measurement did not settle by its own cell test, and all %d of Part B. Each was read by one reader of the X "
            "arm and one of the Y arm, independently (round 2 of 23 October 2026); the 13 records on which the arms "
            "could not settle the construction or disagreed were read again by the tie-break readers Z1 and Z2 (round "
            "3)." % (len(a_prim), len(b_prim), len(read), len(read) - len(b_prim), len(b_prim))),
        "part_a_in_primary": a_prim,
        "part_b_in_primary": b_prim,
        "part_a_not_read_again": a_not_read,
        "part_a_not_read_again_why": (
            "218_2016 to 218_2020: the measurement's cell test found the column calendar-restated (cells equal, rows "
            "labelled 'n years or more later'), consistent with the adopted figure. 1945_2023 and 1945_2024: left out of "
            "the figure since the author's decision of 22 October 2026 (readings F1, F2; data/mature_cohort_figures.json), "
            "and read again by Z1 and Z2 as development_age."),
        "section_c_heuristic_candidates_not_read": c_prim,
        "section_c_why": ("%d records whose first stored column's age-0 cell is more than 2.5 times its neighbours' "
                          "(probably individual large underwriting years, not aggregated columns); the measurement did "
                          "not find a printed older-years column for them and they were not read" % len(c_prim)),
        "low_confidence": list(LOW_CONFIDENCE),
    }


def build():
    batches = load_batches()
    arms = load_arm_readings()
    tie = load_tiebreak_readings()
    keys = sorted(batches, key=sort_key)
    if len(keys) != 64:
        raise SystemExit("the batches hold %d aggregated-column records, not 64" % len(keys))
    if set(arms) != set(keys):
        raise SystemExit("the arms' readings and the batches differ: %s" % sorted(set(arms) ^ set(keys)))
    out = {"_rule": RULE, "_population": population(batches, arms)}
    for key in keys:
        out[key] = entry_for(key, batches[key], arms[key], tie.get(key, []))
    return out


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    text = dumps(build())
    if "--write" in argv:
        with io.open(str(REGISTER), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote %s" % REGISTER.relative_to(HERE))
        return 0
    with io.open(str(REGISTER), encoding="utf-8", newline="") as fh:
        committed = fh.read()
    if committed != text:
        print("data/aggregated_column_review.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/aggregated_column_review.json equals its rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
