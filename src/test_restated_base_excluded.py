#!/usr/bin/env python3
"""The restated-base register (round 5 of the filing readings; decision rules of 23 October 2026, a decision of the Claude
analysis session).

  * data/restated_base_excluded.json equals its rebuild from the archived readings (src/build_restated_base_excluded.py);
  * every one of the round's 83 records has one rule and one outcome, and each outcome is in the register that carries
    it: rule 1 here ('excluded'), rule 2 in data/fx_untranslated_excluded.json, rules 3 and 4 in
    data/mature_cohort_figures.json, rule 5 in data/opening_reserves_takeon_base.json, rule 6 here ('history_restated');
  * the loader removes the five records of rule 1 from the primary with a named, countable tag, and the 672 construction
    does not read the register;
  * the loader refuses an entry without its evidence (mutation-checked), a record in both buckets, a stale entry and a
    mistyped key; the register is a hashed raw-byte input of the run identifier.

Run:  python -m pytest src/test_restated_base_excluded.py -q
"""
import copy
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_restated_base_excluded as rb  # noqa: E402
import run_analysis as ra  # noqa: E402

EXCLUDED = ["780_2016", "2689_2023", "4242_2022", "4747_2024", "6134_2022"]
CORRECTED = {"318_2024": "printed_table_error", "1274_2016": "printed_table_error", "1609_2024": "printed_table_error",
             "2232_2020": "previous_report_base"}
TAKEON_IN_R = ["1686_2021", "1856_2024", "1884_2021", "2488_2019", "3000_2016", "3500_2022", "3500_2023", "4000_2022",
               "4444_2018", "4444_2023"]


def _register():
    with io.open(str(rb.REGISTER), encoding="utf-8") as fh:
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


# --- the register and the adjudication --------------------------------------------------------------------------------

def test_the_register_equals_its_rebuild_from_the_archived_readings():
    with io.open(str(rb.REGISTER), encoding="utf-8", newline="") as fh:
        assert fh.read() == rb.dumps(rb.build())


def test_every_record_of_the_round_has_one_rule_and_one_outcome():
    reg = _register()
    adj = reg["_adjudicated"]
    assert len(adj) == 83 == rb.ROUND_RECORDS
    counts = {}
    for k, a in adj.items():
        counts[a["outcome"]] = counts.get(a["outcome"], 0) + 1
    assert counts == {"corrected": 4, "excluded": 6, "least_certain": 24, "stands": 37, "take_on_amount_not_read": 2,
                      "take_on_base": 9, "take_on_base_and_least_certain": 1}
    assert reg["_population"]["outcomes"] == dict(sorted(counts.items()))
    assert sorted(reg["excluded"], key=rb.order_key) == sorted(EXCLUDED, key=rb.order_key)
    assert sorted(k for k, a in adj.items() if a["rule"] == "1") == sorted(reg["excluded"])
    assert sorted(k for k, a in adj.items() if "6" in a["rule"]) == sorted(reg["history_restated"])
    assert len(reg["history_restated"]) == 25


def test_each_outcome_is_in_the_register_that_carries_it():
    reg = _register()
    adj = reg["_adjudicated"]
    fx = ra.load_fx_untranslated_excluded()
    mature = ra.load_mature_cohort_figures()
    takeon = ra.load_takeon_base()
    assert [k for k, a in adj.items() if a["rule"] == "2"] == ["3000_2022"] and "3000_2022" in fx
    for k, by in CORRECTED.items():
        assert adj[k]["outcome"] == "corrected" and mature[k]["displaced"]["by"] == by, k
    assert sorted(k for k, a in adj.items() if a["rule"] in ("3", "4")) == sorted(CORRECTED)
    assert sorted(k for k, a in adj.items() if a["outcome"].startswith("take_on_base")) == sorted(TAKEON_IN_R)
    for k in TAKEON_IN_R:
        assert k in takeon, k
    # rule 5 with no printed amount in either reading: no take-on base, recorded as outstanding
    for k in ("1110_2022", "1458_2024"):
        assert adj[k]["outcome"] == "take_on_amount_not_read" and k not in takeon, k
    # the records that stand are in no bucket of this register and in no correction
    for k, a in adj.items():
        if a["outcome"] == "stands":
            assert k not in reg["excluded"] and k not in reg["history_restated"] and k not in fx, k
            assert (mature.get(k) or {}).get("correction") is None, k


def test_every_entry_rests_on_two_readings_with_the_year_t_filings_pages_and_the_archived_verdicts():
    reg = _register()
    for bucket in ra.RESTATED_BUCKETS:
        for k, e in reg[bucket].items():
            assert ra._restated_entry_gaps(e, bucket) == [], k
            for r in e["readings"]:
                with io.open(os.path.join(HERE, *r["source"].split("/")), encoding="utf-8") as fh:
                    arch = json.load(fh)[k]
                assert r["verdict"] == arch["verdict"] and r["pages_as_read"] == arch["pages"], (k, r["reader"])
                assert set(r["pages"]) <= set(rb._ints(arch["pages"] if isinstance(arch["pages"], list)
                                                       else list(arch["pages"].values()))), (k, r["reader"])
            assert e["decision"].startswith("decision of the Claude analysis session, 23 October 2026"), k
    assert [r["reader"] for r in reg["excluded"]["2689_2023"]["readings"]] == ["V1", "V2"]
    assert [r["reader"] for r in reg["excluded"]["2689_2023"]["supporting_readings"]] == ["W1", "W2"]
    assert [r["reader"] for r in reg["history_restated"]["4444_2017"]["readings"]] == ["P1", "Q8", "Z5", "Z6"]


def test_the_year_t_pages_are_split_from_the_readers_own_page_fields():
    assert rb.split_pages("1_2020", [5, 6]) == ([5, 6], {})
    own, other = rb.split_pages("1_2020", {"t": 44, "prev": 43, "accounts_t": [21, 25], "accounts_prev": "2019 p21"})
    assert own == [21, 25, 44] and other == {"prev": [43], "accounts_prev": [21]}
    own, other = rb.split_pages("1_2020", {"2020": [5, 7], "2019": [12]})
    assert own == [5, 7] and other == {"2019": [12]}
    own, other = rb.split_pages("1_2020", {"t_table": 29, "prev_table": "2019 PDF p.29", "accounts_t": "2020 p.15",
                                           "t_printed": "39 of 47"})
    assert own == [15, 29] and other == {"prev_table": [29]}


# --- the build refuses what the rules do not allow (mutation checks) ---------------------------------------------------

def test_the_build_refuses_an_excluded_record_a_reading_calls_valid(monkeypatch):
    reads = rb.load_readings()
    bad = [(rid, dict(e, verdict="valid") if rid == "Q3" else e) for rid, e in reads["4747_2024"]]
    with pytest.raises(SystemExit, match="rule 1 needs both readings"):
        rb.entry_for("4747_2024", bad, "excluded")


def test_the_build_refuses_a_label_clause_the_verdicts_do_not_show(monkeypatch):
    h = dict(rb.HISTORY_RESTATED)
    h["382_2021"] = (["unexplained_history_move", "label_disagreement"], h["382_2021"][1])
    monkeypatch.setattr(rb, "HISTORY_RESTATED", h)
    with pytest.raises(SystemExit, match="label_disagreement"):
        rb.entry_for("382_2021", rb.load_readings()["382_2021"], "history_restated")
    h["382_2022"] = (["unexplained_history_move"], h["382_2022"][1])
    with pytest.raises(SystemExit, match="label_disagreement"):
        rb.entry_for("382_2022", rb.load_readings()["382_2022"], "history_restated")


def test_the_build_refuses_an_outcome_list_that_is_not_the_records_read(monkeypatch):
    o = dict(rb.OUTCOMES)
    del o["510_2015"]
    monkeypatch.setattr(rb, "OUTCOMES", o)
    with pytest.raises(SystemExit, match="83"):
        rb.build()
    o["9999_2020"] = ("7", "stands", "none")
    with pytest.raises(SystemExit, match="not the records read"):
        rb.build()


@pytest.mark.parametrize("bucket,key,change", [
    ("excluded", "4747_2024", "no-decision"), ("excluded", "4747_2024", "one-reading"),
    ("excluded", "4747_2024", "same-reader-twice"), ("excluded", "4747_2024", "reader-says-valid"),
    ("excluded", "4747_2024", "no-pages"), ("excluded", "4747_2024", "reading-no-pages"),
    ("excluded", "4747_2024", "no-quote"), ("excluded", "4747_2024", "condition-flipped"),
    ("excluded", "4747_2024", "previous-base-reconciles"), ("excluded", "4747_2024", "condition-no-facts"),
    ("history_restated", "382_2022", "no-clauses"), ("history_restated", "382_2022", "unknown-clause"),
    ("history_restated", "382_2022", "no-facts"), ("history_restated", "382_2022", "label-same-class"),
])
def test_the_loader_refuses_an_entry_without_its_evidence(tmp_path, bucket, key, change):
    reg = _register()
    e = reg[bucket][key]
    if change == "no-decision":
        e["decision"] = ""
    elif change == "one-reading":
        e["readings"] = e["readings"][:1]
    elif change == "same-reader-twice":
        e["readings"][1]["reader"] = e["readings"][0]["reader"]
    elif change == "reader-says-valid":
        e["readings"][1]["verdict"] = "valid"
    elif change == "no-pages":
        e["pages"] = []
    elif change == "reading-no-pages":
        e["readings"][0]["pages"] = []
    elif change == "no-quote":
        e["quote"] = " "
    elif change == "condition-flipped":
        e["conditions"]["year_t_fails_accounts"]["holds"] = False
    elif change == "previous-base-reconciles":
        e["conditions"]["previous_base_reconciles"]["holds"] = True
    elif change == "condition-no-facts":
        e["conditions"]["control_ties"]["facts"] = ""
    elif change == "no-clauses":
        e["clauses"] = []
    elif change == "unknown-clause":
        e["clauses"] = ["looks_odd"]
    elif change == "no-facts":
        e["facts"] = None
    elif change == "label-same-class":
        e["readings"][1]["verdict"] = e["readings"][0]["verdict"]
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks"):
        ra.load_restated_base(p)
    # the unmutated register loads
    assert sorted(ra.load_restated_base()) == sorted(EXCLUDED)


def test_a_record_cannot_be_both_excluded_and_listed(tmp_path):
    reg = _register()
    reg["history_restated"]["4747_2024"] = copy.deepcopy(reg["history_restated"]["382_2022"])
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="both excluded and listed"):
        ra.load_restated_base(p)


# --- the loader ---------------------------------------------------------------------------------------------------------

def test_the_primary_removes_the_five_records_with_a_named_countable_reason(loaded):
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    for key in EXCLUDED:
        r = prim["by_key"][key]
        assert r["data_quality_tag"] == ra.RESTATED_BASE_TAG == "RESTATED_BASE_TABLE", key
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, key
        entry = prim["log"]["syndicate_%s.json" % key]
        assert entry["status"] == ra.RESTATED_BASE_TAG and "data/restated_base_excluded.json" in entry["reason"]
        assert old["by_key"][key]["data_quality_tag"] == "RELIABLE" and old["by_key"][key]["s_raw_a"] is not None
    assert prim["counters"]["restated_base_excluded"] == 5
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.RESTATED_BASE_TAG) == 5
    assert set(EXCLUDED) <= _ws(old["records"]) and not set(EXCLUDED) & _ws(prim["records"])
    assert len(_ws(prim["records"])) == 643


def test_the_listed_records_stay_in_the_primary_with_their_figure(loaded):
    prim = loaded[ra.MATURE_COHORT_OUTCOME]
    ws = _ws(prim["records"])
    for key in _register()["history_restated"]:
        assert key in ws and prim["by_key"][key]["data_quality_tag"] == "RELIABLE", key


def test_the_672_construction_does_not_read_the_register(loaded, monkeypatch, tmp_path):
    old = loaded[ra.PRECEDENCE_672_OUTCOME]
    assert "restated_base_excluded" not in old["counters"]
    assert not any(e["status"] == ra.RESTATED_BASE_TAG for e in old["log"].values())
    monkeypatch.setattr(ra, "RESTATED_BASE_REGISTER", tmp_path / "missing.json")
    records, counters, log, files = ra.load_and_classify(ra.PRECEDENCE_672_OUTCOME)
    assert len(records) == len(old["records"]) and "restated_base_excluded" not in counters
    with pytest.raises(FileNotFoundError):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_an_entry_that_reaches_no_record_stops_the_run(monkeypatch):
    """A record in run-off (1206/2019) never reaches the exclusion step: an entry for it stops the run; an entry whose
    filing is not in the corpus read has nothing to exclude."""
    real = ra.load_restated_base()
    extra = dict(real)
    extra["1206_2019"] = real["4747_2024"]
    monkeypatch.setattr(ra, "load_restated_base", lambda path=None, e=extra: e)
    with pytest.raises(ValueError, match="1206_2019"):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_a_non_gross_record_the_register_names_stops_the_run(monkeypatch):
    real = ra.load_restated_base()
    extra = dict(real)
    extra["1218_2015"] = real["4747_2024"]
    monkeypatch.setattr(ra, "load_restated_base", lambda path=None, e=extra: e)
    with pytest.raises(ValueError, match="1218_2015"):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_a_mistyped_key_in_either_bucket_stops_the_primary_load(monkeypatch):
    real = ra.restated_register_keys()
    assert len(real) == 30
    for bogus in ("9999_2032", "4747_2042"):
        monkeypatch.setattr(ra, "restated_register_keys", lambda path=None, b=bogus: real + [b])
        with pytest.raises(ValueError, match=r"data/restated_base_excluded.json: 1 key\(s\).*%s" % bogus):
            ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_the_register_is_a_hashed_raw_byte_input():
    assert str(ra.RESTATED_BASE_REGISTER) in ra.source_files_for_hash([])
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/restated_base_excluded.json -text" in fh.read().splitlines()
