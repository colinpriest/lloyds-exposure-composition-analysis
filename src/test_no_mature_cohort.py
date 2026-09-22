"""A report with no mature cohort, and a figure its own model calls a change in provision, are not development
(frozen review of 21 September 2026, M01).

1884/2016 began underwriting in April 2015. Its 2016 report's triangles hold 2015 and 2016 only and its claims
note has no prior-year line, so neither source of the paper's numerator exists. One model left the figure
blank; the other took the 2015 year's closing outstanding less the whole opening outstanding (21.372m - 6.328m
= +15.044m), and the loader adopted that lone reading: the largest severity in the sample. Two rules stop it:

  * a lone model reading with no route, where the readings disagreed, in a report whose own triangles hold no
    underwriting year up to t-2, is counted with the first-year reports the extraction skips;
  * a model reading whose own notes describe its figure as the year's movement in the claims provision, or as
    closing less opening outstanding, is not a usable severity (3622/2017 and 6107/2020 were read that way).

The record as the loader read it is kept in tests_data/, because the extraction's replay turns the committed
record into a first-year stub.
"""
import copy
import io
import json
import os

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


def test_a_mature_cohort_or_agreeing_readings_leave_the_rule_alone(tmp_path):
    rec = _young_but_mature(_neutral_notes(_record()))
    records, counters, entry = _load(tmp_path, rec)
    assert entry["status"] == "RELIABLE" and counters["no_mature_cohort_skipped"] == 0
    assert records[0]["s_raw_a"] == pytest.approx(15.044 / 6.328, rel=1e-3)
    agreed = _neutral_notes(_record())
    agreed["validation"]["passed"] = True
    for block in agreed["models"].values():
        block["prior_year_development_gbp_m"], block["prior_year_development_pct"] = 15.044, 237.7
    assert not ra.no_mature_cohort(agreed, agreed["models"]["gemini-2.5-flash"], 2016)


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
