"""A report with no mature cohort, and a figure its own model calls a change in provision, are not development
(frozen review of 21 September 2026, M01).

1884/2016 began underwriting in April 2015. Its 2016 report's triangles hold 2015 and 2016 only and its claims
note has no prior-year line, so neither source of the paper's numerator exists. One model left the figure
blank; the other took the 2015 year's closing outstanding less the whole opening outstanding (21.372m - 6.328m
= +15.044m), and the loader adopted that lone reading: the largest severity in the sample. Two rules stop it:

  * a report whose own triangles hold no underwriting year up to t-2 is counted with the first-year reports the
    extraction skips. Until the author's decision of 1 October 2026 (round 62, fourth cycle) the rule read only a
    lone model reading with no route where the readings disagreed; it now holds whatever the figure's route,
    because such a report has no cohort the numerator counts (u <= t-2). On fixed inputs it moves 11 records,
    each a first- or second-year report by its own filing (data/no_mature_cohort_records.json);
  * a model reading whose own notes describe its figure as the year's movement in the claims provision, or as
    closing less opening outstanding, is not a usable severity (3622/2017 and 6107/2020 were read that way).

The record as the loader read it is kept in tests_data/, because the extraction's replay turns the committed
record into a first-year stub.
"""
import copy
import csv
import io
import json
import os
import re

import pytest

import run_analysis as ra

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(HERE, "tests_data", "syndicate_1884_2016_before_M01.json")
NAME = "syndicate_1884_2016.json"

#: the adopted blocks' own descriptions of their figures (the committed records, 21 September 2026)
DECLARED = {
    "1884_2016": ("Prior year development (15.044m) was derived by comparing the gross claims outstanding at "
                  "31/12/2015 (balance sheet total 6,328k) to the gross outstanding attributed to the 2015 "
                  "underwriting year at 31/12/2016 (21,372k) as shown in the gross claims development table."),
    "3622_2017": ("Prior-year development figure taken from the 'Movement in the provision' (gross claims "
                  "outstanding) line in the Technical Provisions note."),
    "6107_2020": ("The 'Movement in the provision' gross claims figure (-3,541.9) was used as the prior-year "
                  "movement (converted to millions)."),
}
#: descriptions of explicit prior-year lines, which are development
NOT_DECLARED = [
    ("The prior year development figure is taken from the 'Change in prior year provisions' in Note 19, which "
     "is a direct statement of the movement in the gross claims provision."),
    "The gross prior year development figure is taken from the 'Change in prior year provisions' line.",
    "Movement in prior year's provision: a release of 3.1m, as stated in note 11.",
]


def _record():
    return json.load(io.open(FIXTURE, encoding="utf-8"))


def _young_but_mature(rec):
    """The same record with the triangles holding 2012-2016: the no-mature-cohort rule no longer applies."""
    rec = copy.deepcopy(rec)
    for block in rec["models"].values():
        block["_claims_triangle"]["underwriting_years"] = [2012, 2013, 2014, 2015, 2016]
    return rec


def _neutral_notes(rec):
    rec = copy.deepcopy(rec)
    for block in rec["models"].values():
        block["data_quality_notes"] = "The figure is the prior-year movement the filing discloses."
    return rec


def _load(tmp_path, rec):
    d = tmp_path / "records"
    d.mkdir()
    (d / NAME).write_text(json.dumps(rec), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        records, counters, log, _files = ra.load_and_classify()
    finally:
        mp.undo()
    entries = [e for e in log if e["file"] == NAME]
    assert len(entries) == 1, entries
    return records, counters, entries[0]


def test_the_fixture_is_the_record_the_review_found():
    rec = _record()
    gpt = rec["models"]["gpt-5-mini"]
    assert rec["validation"]["passed"] is False
    assert rec["models"]["gemini-2.5-flash"]["prior_year_development_gbp_m"] is None
    assert gpt["prior_year_development_gbp_m"] == pytest.approx(15.044)
    assert ra.triangle_years(rec) and max(ra.triangle_years(rec)) == 2016
    assert min(ra.triangle_years(rec)) == 2015


def test_a_lone_reading_in_a_report_with_no_mature_cohort_is_skipped(tmp_path):
    records, counters, entry = _load(tmp_path, _record())
    assert records == []
    assert entry == {"file": NAME, "status": "SKIPPED", "reason": ra.NO_MATURE_COHORT_REASON}
    assert counters["skipped"] == 1 and counters["no_mature_cohort_skipped"] == 1


def test_a_mature_cohort_leaves_the_rule_alone(tmp_path):
    rec = _young_but_mature(_neutral_notes(_record()))
    records, counters, entry = _load(tmp_path, rec)
    assert entry["status"] == "RELIABLE" and counters["no_mature_cohort_skipped"] == 0
    assert records[0]["s_raw_a"] == pytest.approx(15.044 / 6.328, rel=1e-3)


def _agreed(rec):
    """Both readings agree on the figure, as validation passed."""
    rec = _neutral_notes(rec)
    rec["validation"]["passed"] = True
    for block in rec["models"].values():
        block["prior_year_development_gbp_m"], block["prior_year_development_pct"] = 15.044, 237.7
    return rec


#: a figure a deterministic step read from the filing's reserve text (the route the four young records carry)
READ_ROUTE = {"source": "rag_provisions", "value": 15.044, "note": "confirmed by the model value"}


def _routed(rec):
    rec = _agreed(rec)
    for block in rec["models"].values():
        block["_pyd_route"] = dict(READ_ROUTE)
    return rec


def test_agreeing_readings_and_a_routed_figure_are_caught_too(tmp_path):
    """The decision of 1 October 2026: the rule is the record's, not the figure's. Readings that agree, or a figure a
    deterministic step read from the filing, in a report with no year up to t-2 are counted with the first-year
    reports as the lone reading is."""
    agreed = _agreed(_record())
    assert ra.no_mature_cohort(agreed, agreed["models"]["gemini-2.5-flash"], 2016)
    routed = _routed(_record())
    assert ra.figure_route(routed["models"]["gpt-5-mini"]) == READ_ROUTE
    records, counters, entry = _load(tmp_path, routed)
    assert records == []
    assert entry == {"file": NAME, "status": "SKIPPED", "reason": ra.NO_MATURE_COHORT_REASON}
    assert counters["skipped"] == 1 and counters["no_mature_cohort_skipped"] == 1


def test_a_routed_figure_with_a_mature_cohort_stays(tmp_path):
    records, counters, entry = _load(tmp_path, _young_but_mature(_routed(_record())))
    assert entry["status"] == "RELIABLE" and counters["no_mature_cohort_skipped"] == 0 and len(records) == 1


@pytest.mark.parametrize("years, caught", [([2015, 2016], True), ([2014, 2015, 2016], False), ([2016], True),
                                           ([2013], False)])
def test_the_boundary_is_t_minus_2(years, caught):
    """A cohort u <= t-2 is mature (Equation severity): at t = 2016 a 2014 year makes the report eligible."""
    rec = _record()
    for block in rec["models"].values():
        block["_claims_triangle"]["underwriting_years"] = years
    rec.pop("_rag_triangle", None)
    assert ra.no_mature_cohort(rec, rec["models"]["gpt-5-mini"], 2016) is caught


def test_the_structural_step_keeps_its_name_and_no_longer_says_no_stated_figure(monkeypatch):
    """The reconciliation's structural step said "no eligible mature cohort and no stated development figure"; the
    records the widened rule adds state a figure, so the step now says only what all of its records share. The
    manuscript's gates find the row by "no eligible mature cohort"."""
    from test_runoff_label import _table39
    rows = [line for line in _table39(monkeypatch, 1).splitlines() if "structural exclusion" in line]
    assert len(rows) == 1
    assert "(no eligible mature cohort: no underwriting year up to $t-2$)" in rows[0]
    assert "no stated development figure" not in rows[0]


def test_the_data_audit_names_the_structural_step_the_same_way(monkeypatch):
    import generate_data_audit as gda
    monkeypatch.setattr(gda, "load_runoff_corpus_register", lambda: {})
    monkeypatch.setattr(gda, "load_reviewed_not_runoff", lambda: {})
    text = gda.md(gda.compute(), gda.mine_raw())
    rows = [line for line in text.splitlines() if "No eligible mature cohort" in line]
    assert len(rows) == 1
    assert "No eligible mature cohort: no underwriting year up to t-2" in rows[0]
    assert "no stated development figure" not in rows[0]


def test_a_record_with_no_triangle_year_is_left_alone():
    """The rule's blind side, said in run_analysis and measured in the register: with no triangle year it cannot
    tell a report's age, so it does not act."""
    rec = _routed(_record())
    for block in rec["models"].values():
        block["_claims_triangle"]["underwriting_years"] = []
    rec.pop("_rag_triangle", None)
    assert ra.triangle_years(rec) == []
    assert not ra.no_mature_cohort(rec, rec["models"]["gpt-5-mini"], 2016)


def test_a_figure_its_model_calls_the_movement_in_the_provision_has_no_severity(tmp_path):
    records, counters, entry = _load(tmp_path, _young_but_mature(_record()))
    assert entry["status"] == ra.PROVISION_MOVEMENT_TAG
    assert entry["reason"].startswith("the adopted model's notes describe its figure")
    (obs,) = records
    assert obs["pyd_pct"] is None and obs["pyd_gbp_m"] is None and obs["s_raw_a"] is None
    assert counters["provision_movement_unusable"] == 1
    flow = ra.build_disposition_ledger([entry], records, str(tmp_path / "ledger.csv"))
    assert flow["to_working_sample"]["unusable_severity"] == 1
    assert flow["corpus"] - sum(flow["to_working_sample"].values()) == flow["working_sample"] == 0


@pytest.mark.parametrize("key", sorted(DECLARED))
def test_the_declaration_rule_reads_the_known_descriptions(key):
    assert ra.declares_provision_movement({"data_quality_notes": "Other text. " + DECLARED[key]})


@pytest.mark.parametrize("sentence", NOT_DECLARED)
def test_an_explicit_prior_year_line_is_not_such_a_description(sentence):
    assert ra.declares_provision_movement({"data_quality_notes": sentence}) is None


def test_a_routed_figure_is_not_read_through_the_models_notes():
    cm = {"data_quality_notes": DECLARED["3622_2017"], "_pyd_route": {"source": "rag_triangle", "value": 1.0}}
    assert ra.declares_provision_movement(cm) is None


#: the route the extraction writes for a figure no deterministic step set (round 58, test_gemini.py)
MODEL_READING = {"source": "model_reading", "value": 15.044,
                 "note": "derived: not printed in either block's reserve text", "stated": False}


def _labelled(rec):
    """The record as the round-58 extraction writes it: the adopted model's reading carries a model_reading route."""
    rec = copy.deepcopy(rec)
    rec["models"]["gpt-5-mini"]["_pyd_route"] = dict(MODEL_READING)
    return rec


def test_a_model_reading_route_leaves_the_no_mature_cohort_rule_in_force(tmp_path):
    records, counters, entry = _load(tmp_path, _labelled(_record()))
    assert records == []
    assert entry == {"file": NAME, "status": "SKIPPED", "reason": ra.NO_MATURE_COHORT_REASON}
    assert counters["no_mature_cohort_skipped"] == 1


def test_a_model_reading_route_leaves_the_declaration_rule_in_force(tmp_path):
    records, counters, entry = _load(tmp_path, _young_but_mature(_labelled(_record())))
    assert entry["status"] == ra.PROVISION_MOVEMENT_TAG and counters["provision_movement_unusable"] == 1
    (obs,) = records
    assert obs["s_raw_a"] is None
    for key in sorted(DECLARED):
        cm = {"data_quality_notes": DECLARED[key], "_pyd_route": dict(MODEL_READING, stated=True)}
        assert ra.declares_provision_movement(cm), key


def test_no_working_sample_record_carries_either_figure():
    """The committed sample, against the committed records: no adopted block meets either rule."""
    ex = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))
    sample = {"%s_%s" % (o["syndicate"], o["year"]) for o in ex["observations"]
              if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}
    assert len(sample) > 600
    assert "1884_2016" not in sample
    hits = []
    for key in sorted(sample):
        rec = json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8"))
        models = rec.get("models") or {}
        keys = sorted(models)
        if (rec.get("validation") or {}).get("passed") is True:
            cm = models[keys[0]]
        else:
            cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
                     if models[k].get("prior_year_development_pct") is not None]
            cm = models[max(cands, key=lambda x: x[1])[0]]
        year = int(key.split("_")[1])
        if ra.no_mature_cohort(rec, cm, year) or ra.declares_provision_movement(cm):
            hits.append(key)
    assert hits == [], hits


# ---- the decision of 1 October 2026: the records the widened rule moves, and the ones it cannot see ------------

def _register():
    raw = json.load(io.open(os.path.join(HERE, "data", "no_mature_cohort_records.json"), encoding="utf-8"))
    return raw, {k: v for k, v in raw.items() if not k.startswith("_")}


def _imported(key):
    return json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8"))


#: how a filing says a syndicate started: it began, commenced or was established, or it is in its first or second year
START_VERB = re.compile(r"\b(?:began|commenced|was established)\b")
FIRST_OR_SECOND_YEAR = re.compile(r"\b(?:first|second)\b[^.]*\byear\b")
YEAR = re.compile(r"\b(?:19|20)\d\d\b")


def is_a_start_statement(quote, syndicate, t):
    """Whether the words are this syndicate's own start statement and put the start in t or t-1.

    The syndicate began, commenced or was established: the words before the verb name this syndicate and no other
    syndicate's number, and the first year after the verb is t-1 or t. Or the words call the year the syndicate's
    first or second, and name no year but t-1 or t. A quote that only names t or t-1 ("The Syndicate's 2016 accounts
    are in sterling"), or tells of another syndicate's start, passed the test this replaces (review of 1 October 2026,
    finding 4)."""
    started = START_VERB.search(quote)
    if started:
        subject, rest = quote[:started.start()], quote[started.end():]
        others = {int(n) for n in re.findall(r"\bSyndicate\s+(\d+)", subject)} - {syndicate}
        years = [int(y) for y in YEAR.findall(rest)]
        if "syndicate" in subject.lower() and not others and years and years[0] in (t - 1, t):
            return True
    return bool(FIRST_OR_SECOND_YEAR.search(quote)) and {int(y) for y in YEAR.findall(quote)} <= {t - 1, t}


@pytest.mark.parametrize("quote, syndicate, t, is_one", [
    ("The Syndicate commenced underwriting on 1 January 2016.", 6125, 2017, True),
    ("The Syndicate began underwriting on the 2017 YOA, replacing the Incidental Syndicate that previously operated "
     "within Syndicate 4020.", 3902, 2018, True),
    ("This report covers the business of Syndicate 6130, which was established for the 2016 year of account as a "
     "Special Purpose Syndicate.", 6130, 2017, True),
    ("Syndicate 6134 was established during 2018 as a Special Purpose Arrangement", 6134, 2019, True),
    ("2018 was the first year of trading and therefore there is no historic development prior to this.", 6133, 2019,
     True),
    ("The Syndicate is in its second underwriting year and is still developing the book", 1996, 2024, True),
    # names t-1 and says nothing of a start
    ("The Syndicate's 2016 accounts are in sterling.", 6125, 2017, False),
    # another syndicate's start (in an earlier year, and in t-1), and this one's start in an earlier year
    ("Syndicate 4444 commenced underwriting in 2009 and in 2016 it grew.", 6125, 2017, False),
    ("Syndicate 4444 commenced underwriting on 1 January 2016.", 6125, 2017, False),
    ("Syndicate 6125 commenced underwriting in 2009 and in 2016 it grew.", 6125, 2017, False),
    ("The Syndicate commenced underwriting on 1 January 2012.", 6125, 2017, False),
    # a start by another entity, and a first year in another year
    ("The underwriting team commenced writing the class on 1 January 2016.", 6125, 2017, False),
    ("2009 was the first year of trading.", 6125, 2017, False),
])
def test_a_start_statement_is_the_syndicates_own_and_in_t_or_t_minus_1(quote, syndicate, t, is_one):
    assert is_a_start_statement(quote, syndicate, t) is is_one


def test_each_entry_is_its_records_triangles_and_its_filings_words_on_its_start():
    raw, entries = _register()
    measured = raw["_measurement"]
    assert len(entries) == measured["decisions_changed"] == 11
    assert sorted(measured["left_the_working_sample"] + list(measured["left_another_exclusion"])) == sorted(entries)
    for key, e in entries.items():
        s, t = (int(x) for x in key.split("_"))
        assert (e["syndicate"], e["year"]) == (s, t), key
        years = sorted(set(ra.triangle_years(_imported(key))))
        assert years and years == e["triangle_years"], key
        assert e["mature_cutoff"] == t - ra.MATURE_LAG and not any(y <= e["mature_cutoff"] for y in years), key
        assert re.fullmatch(r"[0-9a-f]{64}", e["source_sha256"]), key
        quotes = e["start_statements"]
        assert quotes and all(isinstance(q["page"], int) and q["page"] > 0 for q in quotes), key
        # each quote is the syndicate's own start statement, and puts the start in t or t-1
        assert all(is_a_start_statement(q["quote"], s, t) for q in quotes), key


def test_the_loaders_catch_is_the_register():
    """On the committed ledger: the filings the loader skipped under M01 are the register's entries, no more and no
    fewer (missingness_check refuses either difference at run time)."""
    _raw, entries = _register()
    with io.open(os.path.join(HERE, "results", "disposition_ledger.csv"), encoding="utf-8") as fh:
        caught = {row["file"][len("syndicate_"):-len(".json")] for row in csv.DictReader(fh)
                  if row["disposition"] == "SKIPPED" and row["reason"] == ra.NO_MATURE_COHORT_REASON}
    assert caught == set(entries)


def test_the_records_the_rule_cannot_see_are_the_samples_records_without_triangle_years():
    """The rule cannot see a record with no triangle year. The register names the working-sample records that have
    none, and the scan of their filings; a sample that gains such a record shows here."""
    raw, _entries = _register()
    blind = raw["_records_the_rule_cannot_see"]
    with io.open(os.path.join(HERE, "results", "inferential_disposition_ledger.csv"), encoding="utf-8") as fh:
        sample = [row["file"][len("syndicate_"):-len(".json")] for row in csv.DictReader(fh)
                  if row["in_model_sample"] == "True"]
    unseen = sorted((k for k in sample if not ra.triangle_years(_imported(k))),
                    key=lambda k: (int(k.split("_")[1]), int(k.split("_")[0])))
    assert sorted(blind["records"]) == sorted(unseen) and blind["count"] == len(unseen) == 20
    # the rule reads each model block's _rag_triangle (the stage-3 review, finding 6): five of the original 25 records
    # hold triangle years there, each with a year up to t-2, so their decisions are unchanged
    gone = blind["restated_4_october_2026"]
    assert gone["count_before"] == 25 and sorted(gone["removed"]) == ["1225_2017", "1967_2014", "2012_2015",
                                                                       "4141_2018", "780_2016"]
    for key in gone["removed"]:
        s, t = (int(x) for x in key.split("_"))
        years = ra.triangle_years(_imported(key))
        assert years and any(y <= t - ra.MATURE_LAG for y in years), key
        assert key not in blind["records"] and key in sample


#: the year each syndicate began, as the scan's `found` text gives it for the three records it names
SCAN_NAMES = {"3334_2018": 2006, "3902_2022": 2017, "5678_2014": 2014}


def test_the_scans_verdict_rests_on_the_records_it_names():
    """`found` opens with its verdict ("none: no filing puts the syndicate's start in t or t-1") and then names the
    records whose filings say when their syndicate began. The structure is held, not the verdict's first word (review of
    1 October 2026, finding 4): the text names these three records and no others, each one a record the scan read,
    with the year its syndicate began in the text's own clause for it. 3334/2018 and 3902/2022 began at or before t-2.
    5678/2014's live underwriting began in 2014, which is t, on top of reinsurance to close business written in
    2008-2010: the one record the text names whose start is in t or t-1, so the verdict says one, not none (FOLLOWUP5
    item 9: "none" was stronger than the clause that followed it). A record added to or dropped from the text, or a
    start year moved, fails here."""
    raw, _entries = _register()
    blind = raw["_records_the_rule_cannot_see"]
    found = blind["found"]
    assert re.match(r"one, and it is no new syndicate's: 5678/2014's", found)
    parts = re.split(r"\b(\d{3,4})/(\d{4})\b", found)  # text, syndicate, year, text, syndicate, year, text, ...
    clauses = {"%s_%s" % (parts[i], parts[i + 1]): parts[i + 2].split(".")[0] for i in range(1, len(parts) - 2, 3)}
    assert sorted(clauses) == sorted(SCAN_NAMES) and set(SCAN_NAMES) <= set(blind["records"])
    for key, began in SCAN_NAMES.items():
        assert str(began) in clauses[key], key
    assert [k for k, began in SCAN_NAMES.items() if began >= int(k.split("_")[1]) - 1] == ["5678_2014"]


@pytest.mark.parametrize("labels,expected", [
    (["Prior", "2020", "2021"], [2020, 2021, 2019]),
    (["Prior years", 2020, 2021], [2020, 2021, 2019]),
    (["2018 & prior", "2020", "2021"], [2018, 2020, 2021]),
    (["2018&P", 2020, 2021], [2018, 2020, 2021]),
    (["2018 and prior", 2020, 2021], [2018, 2020, 2021]),
    (["Pre 2019", 2020, 2021], [2018, 2020, 2021]),
    (["Before 2019", 2020, 2021], [2018, 2020, 2021]),
    ([2019, 2020, 2021], [2019, 2020, 2021]),
    (["Prior"], []),
    (["Total", 2020, 2021], [2020, 2021]),
])
def test_a_grouped_older_column_is_a_mature_cohort(labels, expected):
    """FOLLOWUP5 item 10: an "X and prior" or bare "Prior" column holds the older, mature years. Read as nothing, a
    triangle whose only mature cohort is that group looked like one with no mature cohort, and rule M01 would have
    skipped a record that has one."""
    assert ra.triangle_years({"_rag_triangle": {"underwriting_years": labels}}) == expected


def test_a_triangle_whose_only_mature_cohort_is_a_group_is_not_skipped():
    data = {"_rag_triangle": {"underwriting_years": ["Prior", "2020", "2021"]}}
    assert not ra.no_mature_cohort(data, {}, 2021)
    assert ra.no_mature_cohort({"_rag_triangle": {"underwriting_years": ["2020", "2021"]}}, {}, 2021)
    grouped = {"_rag_triangle": {"underwriting_years": [2011, 2012], "aggregated_cohort": {"anchor": 2010}}}
    assert ra.triangle_years(grouped) == [2011, 2012, 2010]


def test_the_models_rag_triangles_are_read():
    """The RAG triangle sits in each model block (models/*/_rag_triangle): no record has a top-level one, so the rule
    read none of them, and a group's anchor year recorded in aggregated_cohort was never seen (the stage-3 review,
    finding 6)."""
    grouped = {"_rag_triangle": {"underwriting_years": [2011, 2012], "aggregated_cohort": {"anchor": 2010}}}
    data = {"models": {"a": {"_rag_triangle": grouped["_rag_triangle"]},
                       "b": {"_claims_triangle": {"underwriting_years": [2012]}}, "c": None}}
    assert sorted(ra.triangle_years(data)) == [2010, 2011, 2012, 2012]
    only_group = {"models": {"a": {"_rag_triangle": {"underwriting_years": [2020, 2021],
                                                     "aggregated_cohort": {"anchor": 2010}}}}}
    assert not ra.no_mature_cohort(only_group, {}, 2021), "the group's anchor is the mature cohort"
    assert ra.no_mature_cohort({"models": {"a": {"_rag_triangle": {"underwriting_years": [2020, 2021]}}}}, {}, 2021)


def test_the_committed_aggregated_cohort_anchors_are_seen():
    """On the committed records: every model-level RAG triangle with an aggregated_cohort anchor (58 blocks in 29
    records) contributes that anchor, which the rule did not see before finding 6 of the stage-3 review."""
    import glob
    blocks = records = 0
    for path in sorted(glob.glob(os.path.join(HERE, "pdf_extraction", "syndicate_*.json"))):
        with io.open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        seen = False
        for m in (data.get("models") or {}).values():
            tri = (m or {}).get("_rag_triangle")
            anchor = ((tri or {}).get("aggregated_cohort") or {}).get("anchor")
            if isinstance(anchor, int):
                blocks += 1
                seen = True
                assert anchor in ra.triangle_years(data), os.path.basename(path)
        records += seen
    assert (blocks, records) == (58, 29)
