r"""The exchange-rate rule of the primary sample (the author's decision of 22 October 2026, rule B).

A record leaves the primary sample when (a) its development table is not retranslated between the year t-1 and year t
reports across a sterling/dollar move of 5% or more, and (b) the filing's own gross claims-outstanding roll-forward
prints an exchange line of at least 5% of the opening gross claims outstanding. data/fx_untranslated_excluded.json holds
the four records both conditions hold for (2468/2016, 5151/2016, 5151/2017, 1897/2016) and the nine candidates two
readers (F1, F2) found to fail a condition; src/build_fx_untranslated_excluded.py builds it from the archived readings.
Under outcome "precedence_672" nothing changes.

Run:  python -m pytest src/test_fx_untranslated_excluded.py -q
"""
import copy
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_fx_untranslated_excluded as bf  # noqa: E402
import run_analysis as ra  # noqa: E402

EXCLUDED = {"1897_2016": 17.82, "2468_2016": 14.35, "5151_2016": 14.55, "5151_2017": -6.86}
KEPT = {"218_2017": None, "1301_2023": 0.15, "1686_2018": -2.75, "1971_2023": 0.18, "2468_2017": -2.43,
        "4242_2016": None, "4242_2017": None, "4242_2018": None, "5151_2018": 4.22}


def _register():
    with io.open(os.path.join(HERE, "data", "fx_untranslated_excluded.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _archive(rid):
    with io.open(os.path.join(bf.READINGS, "%s.json" % rid), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def loaded():
    out = {}
    for outcome in ra.OUTCOMES:
        records, counters, log, files = ra.load_and_classify(outcome)
        out[outcome] = {"records": records, "counters": counters, "log": {e["file"]: e for e in log},
                        "by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}}
    return out


def _ws(records):
    return {"%s_%s" % (r["syndicate"], r["year"]) for r in records
            if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["hhi"] is not None
            and r["pyd_basis"] == "gross"}


# --- the register -----------------------------------------------------------------------------------------------------

def test_the_register_equals_its_rebuild_from_the_archived_readings():
    with io.open(str(bf.REGISTER), encoding="utf-8", newline="") as fh:
        assert fh.read() == bf.dumps(bf.build())


def test_the_register_holds_the_four_excluded_and_the_nine_read_and_kept():
    reg = _register()
    assert set(reg["excluded"]) == set(EXCLUDED) and set(reg["read_and_kept"]) == set(KEPT)
    for bucket, want in (("excluded", EXCLUDED), ("read_and_kept", KEPT)):
        for key, pct in want.items():
            e = reg[bucket][key]
            assert e["fx_line_pct_of_opening"] == pct, key
            assert [r["reader"] for r in e["readings"]] == ["F1", "F2"], key
    assert ra.load_fx_untranslated_excluded().keys() == set(EXCLUDED)
    assert reg["_population"]["candidates_read_twice"] == 13
    assert len(reg["_population"]["candidates_read_twice_are"]) == 13
    assert "rule B" in reg["_rule"] and "22 October 2026" in reg["_rule"]


def test_the_rule_is_recomputed_from_each_readers_own_figures():
    """Driven by the archived readings, not by the register: both readers' R and exchange line give the percentage, a
    record is excluded exactly when the line is at least 5% of R, and the two readers agree on every candidate."""
    f1, f2 = _archive("F1"), _archive("F2")
    reg = _register()
    for key in list(EXCLUDED) + list(KEPT):
        seen = []
        for rd in (f1, f2):
            e = rd[key]
            r = e.get("opening_gross_claims_outstanding_R") or e["opening_R"]
            line = e.get("fx_line_gross", e.get("fx_line"))
            m = line.get("value_m") if isinstance(line, dict) else None
            seen.append((r["value_m"], m, e["verdict"]))
            if m is not None:
                pct = abs(m) / r["value_m"] * 100
                assert (e["verdict"] == "exclude") == (pct >= 5.0), (key, pct)
            else:
                assert e["verdict"] == "keep", key
        assert seen[0] == seen[1], key
        assert (key in reg["excluded"]) == (seen[0][2] == "exclude"), key


def test_1897_2016_is_treated_as_exchange_on_the_retranslation_of_r():
    """The line is labelled 'Effect of FX and other movements'; the session's decision rests on R retranslated at the
    filing's printed rates (1.47 to 1.24), which gives 14.3m of the 13.8m line."""
    e = _register()["excluded"]["1897_2016"]
    assert "Effect of FX and other movements" in e["quote"]
    note = e["session_decision"]
    assert note.startswith("decision of the Claude analysis session") and "treated as exchange" in note
    assert abs(77.314 * (1.47 / 1.24 - 1) - 14.3) < 0.05 and abs(e["fx_line_gross_m"] - 13.777) < 1e-9


@pytest.mark.parametrize("bucket,key,change", [
    ("excluded", "2468_2016", "no-readings"), ("excluded", "2468_2016", "one-reading"),
    ("excluded", "2468_2016", "same-reader-twice"), ("excluded", "2468_2016", "reader-off-the-line"),
    ("excluded", "2468_2016", "reader-off-r"), ("excluded", "2468_2016", "reader-says-keep"),
    ("excluded", "2468_2016", "reader-no-quote"), ("excluded", "2468_2016", "reader-no-pages"),
    ("excluded", "2468_2016", "line-under-5pct"), ("excluded", "2468_2016", "no-line"),
    ("excluded", "2468_2016", "table-retranslated"), ("excluded", "2468_2016", "pct-off"),
    ("excluded", "2468_2016", "no-decision"), ("excluded", "2468_2016", "no-pages"),
    ("excluded", "2468_2016", "no-quote"), ("excluded", "2468_2016", "text-opening"),
    ("read_and_kept", "5151_2018", "no-reason"), ("read_and_kept", "5151_2018", "unknown-reason"),
    ("read_and_kept", "5151_2018", "kept-line-at-5pct"), ("read_and_kept", "218_2017", "reason-line-printed"),
    ("read_and_kept", "5151_2018", "reader-says-exclude")])
def test_the_loader_refuses_an_entry_without_its_evidence(tmp_path, bucket, key, change):
    reg = _register()
    e = reg[bucket][key]
    if change == "no-readings":
        e["readings"] = []
    elif change == "one-reading":
        e["readings"] = e["readings"][:1]
    elif change == "same-reader-twice":
        e["readings"][1]["reader"] = e["readings"][0]["reader"]
    elif change == "reader-off-the-line":
        e["readings"][1]["fx_line_gross"]["value_m"] += 1.0
    elif change == "reader-off-r":
        e["readings"][0]["opening_gross_claims_outstanding"]["value_m"] += 1.0
    elif change in ("reader-says-keep", "reader-says-exclude"):
        e["readings"][1]["verdict"] = "keep" if change == "reader-says-keep" else "exclude"
    elif change == "reader-no-quote":
        e["readings"][0]["fx_line_gross"]["quote"] = " "
    elif change == "reader-no-pages":
        e["readings"][0]["pages"] = []
    elif change == "line-under-5pct":
        e["fx_line_gross_m"] = 20.0
        e["fx_line_pct_of_opening"] = round(100 * 20.0 / e["opening_gross_claims_outstanding_m"], 2)
        for r in e["readings"]:
            r["fx_line_gross"]["value_m"] = 20.0
    elif change == "no-line":
        e["fx_line_gross_m"] = None
        for r in e["readings"]:
            r["fx_line_gross"]["value_m"] = None
    elif change == "table-retranslated":
        e["table_retranslated"] = True
    elif change == "pct-off":
        e["fx_line_pct_of_opening"] = 30.0
    elif change == "no-decision":
        e["decision"] = ""
    elif change == "no-pages":
        e["pages"] = []
    elif change == "no-quote":
        e["quote"] = ""
    elif change == "text-opening":
        e["opening_gross_claims_outstanding_m"] = "551.198"
    elif change == "no-reason":
        del e["reason"]
    elif change == "unknown-reason":
        e["reason"] = "the sign looked wrong"
    elif change == "kept-line-at-5pct":
        e["fx_line_gross_m"] = 0.05 * e["opening_gross_claims_outstanding_m"]
        e["fx_line_pct_of_opening"] = 5.0
        for r in e["readings"]:
            r["fx_line_gross"]["value_m"] = e["fx_line_gross_m"]
    elif change == "reason-line-printed":
        e["reason"] = "no_fx_line_printed"
        e["fx_line_gross_m"] = 1.0
        e["fx_line_pct_of_opening"] = round(100 / e["opening_gross_claims_outstanding_m"], 2)
        for r in e["readings"]:
            r["fx_line_gross"]["value_m"] = 1.0
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match=key):
        ra.load_fx_untranslated_excluded(p)
    p.write_text(json.dumps(_register()), encoding="utf-8")
    assert set(ra.load_fx_untranslated_excluded(p)) == set(EXCLUDED)


def test_a_record_cannot_be_both_excluded_and_kept(tmp_path):
    reg = _register()
    reg["read_and_kept"]["2468_2016"] = copy.deepcopy(reg["read_and_kept"]["2468_2017"])
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="2468_2016"):
        ra.load_fx_untranslated_excluded(p)


# --- the loader ----------------------------------------------------------------------------------------------------------

def test_the_primary_removes_the_four_records_with_a_named_countable_reason(loaded):
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    for key in EXCLUDED:
        r = prim["by_key"][key]
        assert r["data_quality_tag"] == ra.FX_UNTRANSLATED_TAG == "FX_UNTRANSLATED_TABLE", key
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, key
        entry = prim["log"]["syndicate_%s.json" % key]
        assert entry["status"] == ra.FX_UNTRANSLATED_TAG and "data/fx_untranslated_excluded.json" in entry["reason"]
        # the 672 construction keeps three of them with their severity; 5151/2016's gross figure (+18.850) is a
        # mature-cohort figure the primary adopts, and the 672 reads it on an unstated basis, outside its sample
        if key == "5151_2016":
            assert old["by_key"][key]["data_quality_tag"] == "UNKNOWN_BASIS" and old["by_key"][key]["s_raw_a"] is None
        else:
            assert old["by_key"][key]["data_quality_tag"] == "RELIABLE" and old["by_key"][key]["s_raw_a"] is not None
    assert prim["counters"]["fx_untranslated_excluded"] == 4
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.FX_UNTRANSLATED_TAG) == 4
    assert set(EXCLUDED) - {"5151_2016"} <= _ws(old["records"]) and not set(EXCLUDED) & _ws(prim["records"])


def test_the_kept_candidates_stay_in_the_primary(loaded):
    ws = _ws(loaded[ra.MATURE_COHORT_OUTCOME]["records"])
    for key in KEPT:
        assert key in ws, key


def test_the_672_construction_does_not_read_the_register(loaded, monkeypatch, tmp_path):
    """Under precedence_672 the register is not read: a loader pointed at a missing register still loads it, with no
    exclusion and no counter."""
    old = loaded[ra.PRECEDENCE_672_OUTCOME]
    assert "fx_untranslated_excluded" not in old["counters"]
    assert not any(e["status"] == ra.FX_UNTRANSLATED_TAG for e in old["log"].values())
    monkeypatch.setattr(ra, "FX_UNTRANSLATED_REGISTER", tmp_path / "missing.json")
    records, counters, log, files = ra.load_and_classify(ra.PRECEDENCE_672_OUTCOME)
    assert len(records) == len(old["records"]) and "fx_untranslated_excluded" not in counters
    with pytest.raises(FileNotFoundError):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_an_entry_that_reaches_no_record_stops_the_run(monkeypatch):
    """A register that claims an exclusion the loader did not make stops the run: a record missing from the sample, or
    one that is not a reliable gross record (here a record in run-off and one on a net basis)."""
    real = ra.load_fx_untranslated_excluded()
    for stale in ("9999_2020", "1206_2019"):
        extra = dict(real)
        extra[stale] = real["2468_2016"]
        monkeypatch.setattr(ra, "load_fx_untranslated_excluded", lambda path=None, e=extra: e)
        with pytest.raises(ValueError, match=stale):
            ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_the_register_is_a_hashed_raw_byte_input():
    assert str(ra.FX_UNTRANSLATED_REGISTER) in ra.source_files_for_hash([])
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/fx_untranslated_excluded.json -text" in fh.read().splitlines()
