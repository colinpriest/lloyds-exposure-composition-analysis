#!/usr/bin/env python3
"""The restated-base register (round 5 of the filing readings; decision rules of 23 October 2026, a decision of the Claude
analysis session).

  * data/restated_base_excluded.json equals its rebuild from the archived readings (src/build_restated_base_excluded.py);
  * every one of the round's 83 records has one rule and one outcome, and each outcome is in the register that carries
    it: rule 1 here ('excluded'), rule 2 in data/fx_untranslated_excluded.json, rules 3 and 4 in
    data/mature_cohort_figures.json, rule 5 in data/opening_reserves_takeon_base.json, rule 5b here ('takeon_unmeasurable',
    or 'history_restated' for a take-on bounded at or below 10% of R), rule 6 here ('history_restated');
  * rule 5b (the round-7 readings U1, U2): 1110/2022, whose unprinted take-on could exceed 10% of R, leaves the primary
    under the bucket 'takeon_unmeasurable' with a tag of its own; 1458/2024, bounded at 8.0%, and 3500/2023 stay and are
    listed;
  * the loader removes the four records of rule 1 from the primary with a named, countable tag, and the 672 construction
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

#: rule 1; 4242/2022 left it for rule 3 after review 8 (the previous report's base reconciles once the merged '2016 & Prior'
#: column is set aside)
EXCLUDED = ["780_2016", "2689_2023", "4747_2024", "6134_2022"]
CORRECTED = {"318_2024": "printed_table_error", "1274_2016": "printed_table_error", "1609_2024": "printed_table_error",
             "2232_2020": "previous_report_base", "4242_2022": "previous_report_base"}
TAKEON_IN_R = ["1686_2021", "1856_2024", "1884_2021", "2488_2019", "3000_2016", "3500_2022", "3500_2023", "4000_2022",
               "4444_2018", "4444_2023"]
#: rule 5b (after the round-7 readings U1, U2): the take-on leaves the primary (1110/2022), or the filing bounds it at or
#: below 10% of R and the record is listed (1458/2024)
UNMEASURABLE = ["1110_2022"]
BOUNDED = ["1458_2024"]


def adj_keys_of_rule_6_alone(adj):
    """The records whose only rule is rule 6, or rules 5 and 6 for a take-on already in the register (3000/2016)."""
    return [k for k, a in adj.items() if a["rule"] == "6" or k == "3000_2016"]


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
    assert counts == {"corrected": 4, "corrected_least_certain": 1, "excluded": 5, "least_certain": 24, "stands": 37,
                      "take_on_base": 7, "take_on_base_and_least_certain": 3, "take_on_bounded_least_certain": 1,
                      "take_on_unmeasurable": 1}
    assert reg["_population"]["outcomes"] == dict(sorted(counts.items()))
    assert sorted(reg["excluded"], key=rb.order_key) == sorted(EXCLUDED, key=rb.order_key)
    assert sorted(k for k, a in adj.items() if a["rule"] == "1") == sorted(reg["excluded"])
    assert sorted(k for k, a in adj.items() if "6" in a["rule"]) == sorted(reg["history_restated"])
    assert sorted(k for k, a in adj.items() if a["rule"] == "5b") == sorted(reg["takeon_unmeasurable"]) == UNMEASURABLE
    assert len(reg["history_restated"]) == 29
    assert sorted(set(reg["history_restated"]) - set(adj_keys_of_rule_6_alone(adj))) == [
        "1274_2016", "1458_2024", "3500_2022", "3500_2023"]


def test_each_outcome_is_in_the_register_that_carries_it():
    reg = _register()
    adj = reg["_adjudicated"]
    fx = ra.load_fx_untranslated_excluded()
    mature = ra.load_mature_cohort_figures()
    takeon = ra.load_takeon_base()
    assert [k for k, a in adj.items() if a["rule"] == "2"] == ["3000_2022"] and "3000_2022" in fx
    for k, by in CORRECTED.items():
        assert adj[k]["outcome"].startswith("corrected") and mature[k]["displaced"]["by"] == by, k
    assert sorted(k for k, a in adj.items() if a["rule"] in ("3", "4", "4 and 6")) == sorted(CORRECTED)
    # 1274/2016's corrected figure is the session's derivation, so it is also listed (clause derived_correction)
    assert adj["1274_2016"]["outcome"] == "corrected_least_certain" and mature["1274_2016"]["correction"]["derived_figure_m"]
    assert reg["history_restated"]["1274_2016"]["clauses"] == ["derived_correction"]
    assert sorted(k for k, a in adj.items() if a["outcome"].startswith("take_on_base")) == sorted(TAKEON_IN_R)
    for k in TAKEON_IN_R:
        assert k in takeon, k
    # rule 5b: no printed amount in either reading (U1, U2), so no take-on base; the filing's share of R decides
    for k in UNMEASURABLE + BOUNDED:
        assert k not in takeon and k not in ra.load_takeon_register(), k
    assert adj["1110_2022"]["outcome"] == "take_on_unmeasurable" and "1110_2022" in reg["takeon_unmeasurable"]
    assert adj["1458_2024"]["outcome"] == "take_on_bounded_least_certain"
    assert reg["history_restated"]["1458_2024"]["clauses"] == ["take_on_base_bounded"]
    assert reg["history_restated"]["3500_2023"]["clauses"] == ["take_on_table_unreconciled"]
    assert adj["3500_2023"]["outcome"] == "take_on_base_and_least_certain" and "3500_2023" in takeon
    # 3500/2022 joined 3500/2023 on the list after review 8, on the same all-prior-years scope; R already holds its RITCs
    assert reg["history_restated"]["3500_2022"]["clauses"] == ["take_on_table_unreconciled"]
    assert adj["3500_2022"]["outcome"] == "take_on_base_and_least_certain" and "3500_2022" in takeon
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


def test_the_take_on_readings_are_the_archived_round_7_readings_and_none_prints_an_amount():
    reg = _register()
    for bucket, key in (("takeon_unmeasurable", "1110_2022"), ("history_restated", "1458_2024")):
        t = reg[bucket][key]["take_on"]
        assert [r["reader"] for r in t["readings"]] == ["U1", "U2"], key
        assert t["amount_printed"] is False and t["threshold_pct_of_R"] == 10.0
        for r in t["readings"]:
            with io.open(os.path.join(HERE, *r["source"].split("/")), encoding="utf-8") as fh:
                arch = json.load(fh)[key]
            assert r["source"].endswith("round5/readings/%s.json" % r["reader"])
            assert r["gross_transferred_in"] == arch["gross_transferred_in"], (key, r["reader"])
            assert r["gross_transferred_in"]["value_m"] is None and r["pages"], (key, r["reader"])
            assert r["opening_R"]["value_m"] == t["opening_R_m"], (key, r["reader"])
        assert key in reg["_adjudicated"] and {"U1", "U2"} <= set(reg["_adjudicated"][key]["readers"]), key
    # the share of R that decides the rule: above 10% for the take-on that leaves, at or below for the one that stays
    assert reg["takeon_unmeasurable"]["1110_2022"]["take_on"]["pct_of_R"] > 10.0
    assert reg["takeon_unmeasurable"]["1110_2022"]["take_on"]["amount_kind"] == "indicated"
    assert reg["history_restated"]["1458_2024"]["take_on"]["pct_of_R"] == 8.0
    assert reg["history_restated"]["1458_2024"]["take_on"]["amount_kind"] == "upper_bound"
    assert rb.TAKEON_THRESHOLD_PCT == ra.TAKEON_UNMEASURABLE_THRESHOLD_PCT == 10.0
    # the archive holds the amended rules with rule 5b and the round-7 brief
    with io.open(os.path.join(HERE, rb.ROUND5, "rules.md"), encoding="utf-8") as fh:
        rules = fh.read()
    assert "5b." in rules and "10% of the opening gross claims outstanding R" in rules
    assert os.path.exists(os.path.join(HERE, rb.ROUND5, "briefs", "brief_r7.md"))


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


@pytest.mark.parametrize("bucket,key,change", [
    ("takeon_unmeasurable", "1110_2022", "no-take-on"), ("takeon_unmeasurable", "1110_2022", "share-below-threshold"),
    ("takeon_unmeasurable", "1110_2022", "share-at-threshold"), ("takeon_unmeasurable", "1110_2022", "amount-printed"),
    ("takeon_unmeasurable", "1110_2022", "kind-upper-bound"), ("takeon_unmeasurable", "1110_2022", "one-take-on-reading"),
    ("takeon_unmeasurable", "1110_2022", "same-reader-twice"), ("takeon_unmeasurable", "1110_2022", "reading-prints-value"),
    ("takeon_unmeasurable", "1110_2022", "reading-no-pages"), ("takeon_unmeasurable", "1110_2022", "share-not-the-amount"),
    ("takeon_unmeasurable", "1110_2022", "no-facts"), ("takeon_unmeasurable", "1110_2022", "no-decision"),
    ("takeon_unmeasurable", "1110_2022", "no-pages"),
    ("history_restated", "1458_2024", "no-take-on"), ("history_restated", "1458_2024", "share-above-threshold"),
    ("history_restated", "1458_2024", "kind-indicated"), ("history_restated", "1458_2024", "amount-printed"),
    ("history_restated", "1458_2024", "one-take-on-reading"),
])
def test_the_loader_refuses_a_rule_5b_entry_that_does_not_show_its_share_of_r(tmp_path, bucket, key, change):
    """Mutation checks of rule 5b: an unmeasurable take-on must show a share of R above 10% and a bounded one at or below
    it, the amount unprinted, and two readings of the amount from distinct readers."""
    reg = _register()
    e = reg[bucket][key]
    t = e["take_on"]
    if change == "no-take-on":
        del e["take_on"]
    elif change == "share-below-threshold":
        t["amount_m"], t["pct_of_R"] = 20.0, round(100 * 20.0 / t["opening_R_m"], 1)
    elif change == "share-at-threshold":
        t["amount_m"], t["pct_of_R"] = 0.1 * t["opening_R_m"], 10.0
    elif change == "share-above-threshold":
        t["amount_m"], t["pct_of_R"] = 0.12 * t["opening_R_m"], 12.0
    elif change == "amount-printed":
        t["amount_printed"] = True
    elif change in ("kind-upper-bound", "kind-indicated"):
        t["amount_kind"] = "upper_bound" if change == "kind-upper-bound" else "indicated"
    elif change == "one-take-on-reading":
        t["readings"] = t["readings"][:1]
    elif change == "same-reader-twice":
        t["readings"][1]["reader"] = t["readings"][0]["reader"]
    elif change == "reading-prints-value":
        t["readings"][0]["gross_transferred_in"]["value_m"] = 50.0
    elif change == "reading-no-pages":
        t["readings"][0]["pages"] = []
    elif change == "share-not-the-amount":
        t["pct_of_R"] = 50.0
    elif change == "no-facts":
        e["facts"] = ""
    elif change == "no-decision":
        e["decision"] = ""
    elif change == "no-pages":
        e["pages"] = []
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks"):
        ra.load_restated_base(p)
    with pytest.raises(ValueError, match="lacks"):
        ra.load_takeon_unmeasurable(p)
    # the unmutated register loads, and the loader returns the right bucket
    assert sorted(ra.load_takeon_unmeasurable()) == UNMEASURABLE


def test_a_listed_take_on_without_the_bounded_clause_needs_no_take_on_object(tmp_path):
    """3500/2023's clause is take_on_table_unreconciled: it carries no amount, because R already holds its take-on."""
    reg = _register()
    assert "take_on" not in reg["history_restated"]["3500_2023"]
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    assert sorted(ra.load_takeon_unmeasurable(p)) == UNMEASURABLE


def test_the_build_refuses_a_take_on_on_the_wrong_side_of_the_threshold(monkeypatch):
    """Mutation checks of the builder: the same take-on in the other bucket is refused, and so is a missing round-7 reader."""
    reads = rb.load_readings()
    with pytest.raises(SystemExit, match="not above the 10%"):
        rb.take_on_block("1458_2024", reads["1458_2024"], "takeon_unmeasurable")
    amounts = dict(rb.TAKEON_AMOUNT)
    amounts["1458_2024"] = dict(amounts["1458_2024"], amount_m=250.0)
    monkeypatch.setattr(rb, "TAKEON_AMOUNT", amounts)
    with pytest.raises(SystemExit, match="above the 10%"):
        rb.entry_for("1458_2024", reads["1458_2024"], "history_restated")
    one = [(rid, e) for rid, e in reads["1458_2024"] if rid != "U2"]
    with pytest.raises(SystemExit, match="needs the readings of both"):
        rb.take_on_block("1458_2024", one, "history_restated")
    printed = [(rid, dict(e, gross_transferred_in=dict(e["gross_transferred_in"], value_m=9.0)) if rid == "U1" else e)
               for rid, e in reads["1458_2024"]]
    monkeypatch.setattr(rb, "TAKEON_AMOUNT", {"1458_2024": rb.TAKEON_AMOUNT["1458_2024"]})
    with pytest.raises(SystemExit, match="prints a transferred gross amount"):
        rb.take_on_block("1458_2024", printed, "history_restated")


def test_a_record_cannot_be_both_excluded_and_listed(tmp_path):
    reg = _register()
    reg["history_restated"]["4747_2024"] = copy.deepcopy(reg["history_restated"]["382_2022"])
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="both excluded and listed"):
        ra.load_restated_base(p)


# --- the loader ---------------------------------------------------------------------------------------------------------

def test_the_primary_removes_the_four_records_with_a_named_countable_reason(loaded):
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    for key in EXCLUDED:
        r = prim["by_key"][key]
        assert r["data_quality_tag"] == ra.RESTATED_BASE_TAG == "RESTATED_BASE_TABLE", key
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, key
        entry = prim["log"]["syndicate_%s.json" % key]
        assert entry["status"] == ra.RESTATED_BASE_TAG and "data/restated_base_excluded.json" in entry["reason"]
        assert old["by_key"][key]["data_quality_tag"] == "RELIABLE" and old["by_key"][key]["s_raw_a"] is not None
    assert prim["counters"]["restated_base_excluded"] == len(EXCLUDED) == 4
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.RESTATED_BASE_TAG) == 4
    assert set(EXCLUDED) <= _ws(old["records"]) and not set(EXCLUDED) & _ws(prim["records"])
    assert len(_ws(prim["records"])) == 643
    # 4242/2022 (rule 3 after review 8) is in the primary at the previous report's base: -80.015m USD
    r = prim["by_key"]["4242_2022"]
    assert r["data_quality_tag"] == "RELIABLE" and r["pyd_basis_source"] == "mature-cohort-figure:register"
    assert "4242_2022" in _ws(prim["records"]) and r["pyd_gbp_m"] == pytest.approx(-66.254037, abs=1e-6)


def test_the_primary_removes_the_unmeasurable_take_on_with_its_own_countable_tag(loaded):
    """Rule 5b: 1110/2022 leaves the primary with the tag TAKEON_BASE_UNMEASURABLE, a counter and a ledger reason of
    its own; the 672 keeps the record, with the figure and the tag it always had; the take-on is in no take-on register."""
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    assert ra.TAKEON_UNMEASURABLE_TAG == "TAKEON_BASE_UNMEASURABLE" != ra.RESTATED_BASE_TAG != ra.TAKEON_TAG
    for key in UNMEASURABLE:
        r = prim["by_key"][key]
        assert r["data_quality_tag"] == ra.TAKEON_UNMEASURABLE_TAG, key
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, key
        entry = prim["log"]["syndicate_%s.json" % key]
        assert entry["status"] == ra.TAKEON_UNMEASURABLE_TAG and "rule 5b" in entry["reason"]
        assert "data/restated_base_excluded.json" in entry["reason"]
        o = old["by_key"][key]
        assert o["data_quality_tag"] == "RELIABLE" and o["s_raw_a"] is not None and o["pyd_gbp_m"] == 9.082
        # the opening reserves are the filing's own (no acquired reserves added): the take-on is not measured
        assert r["opening_reserves_gbp_m"] == o["opening_reserves_gbp_m"] == 221.885
    assert prim["counters"]["takeon_base_unmeasurable_excluded"] == len(UNMEASURABLE)
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.TAKEON_UNMEASURABLE_TAG) == len(UNMEASURABLE)
    assert set(UNMEASURABLE) <= _ws(old["records"]) and not set(UNMEASURABLE) & _ws(prim["records"])
    # the bounded take-on stays, with its figure, and the divisor is the filing's opening reserves
    r = prim["by_key"]["1458_2024"]
    assert r["data_quality_tag"] == "RELIABLE" and r["pyd_gbp_m"] == pytest.approx(-26.5618, abs=1e-4)
    assert prim["counters"]["restated_base_excluded"] == 4


def test_the_new_tag_reaches_the_ledgers_unusable_severity_step_and_the_missingness_exclusions():
    """Rule 5b's tag is a step of the disposition ledger and the missingness partition like the other primary tags: the
    reconciliation counts it at the unusable-severity step, the classifier gives it a scientific-exclusion detail, both
    generated documents describe it, and the missingness sensitivity leaves the record out."""
    import build_current_results as bcr
    import generate_data_audit as gda
    import missingness_check as MC
    rows = [{"file": "a", "detail": "takeon_base_unmeasurable"}, {"file": "b", "detail": "restated_base_table"}]
    ledger = [{"file": "a", "disposition": "CORPUS:" + ra.TAKEON_UNMEASURABLE_TAG},
              {"file": "b", "disposition": "CORPUS:" + ra.RESTATED_BASE_TAG}]
    out = MC.basis_exclusions_reconciliation(rows, ledger, {"to_working_sample": {"net_or_unstated_basis": 0,
                                                                                  "unusable_severity": 2}})
    assert out["unusable_severity_components"] == {"restated_base_table": 1, "takeon_base_unmeasurable": 1}
    for fname, needles in (("missingness_check.py", ['obs.get("data_quality_tag") == "%s"' % ra.TAKEON_UNMEASURABLE_TAG,
                                                      '"scientific_exclusion", "takeon_base_unmeasurable"']),
                           ("check_missingness_sensitivity.py", ['"%s"' % ra.TAKEON_UNMEASURABLE_TAG])):
        with io.open(os.path.join(HERE, "src", fname), encoding="utf-8") as fh:
            src = fh.read()
        for needle in needles:
            assert needle in src, (fname, needle)
    for words in (bcr.SCIENTIFIC_DETAIL_WORDS, gda.SCIENTIFIC_DETAIL_WORDS):
        assert "rule 5b" in words["takeon_base_unmeasurable"]


def test_the_listed_records_stay_in_the_primary_with_their_figure(loaded):
    prim = loaded[ra.MATURE_COHORT_OUTCOME]
    ws = _ws(prim["records"])
    for key in _register()["history_restated"]:
        assert key in ws and prim["by_key"][key]["data_quality_tag"] == "RELIABLE", key


def test_the_672_construction_does_not_read_the_register(loaded, monkeypatch, tmp_path):
    old = loaded[ra.PRECEDENCE_672_OUTCOME]
    assert "restated_base_excluded" not in old["counters"]
    assert "takeon_base_unmeasurable_excluded" not in old["counters"]
    assert not any(e["status"] in (ra.RESTATED_BASE_TAG, ra.TAKEON_UNMEASURABLE_TAG) for e in old["log"].values())
    monkeypatch.setattr(ra, "RESTATED_BASE_REGISTER", tmp_path / "missing.json")
    records, counters, log, files = ra.load_and_classify(ra.PRECEDENCE_672_OUTCOME)
    assert len(records) == len(old["records"]) and "restated_base_excluded" not in counters
    assert "takeon_base_unmeasurable_excluded" not in counters
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
    """The per-record guard of the exclusion step (run_analysis.py, `if basis_key in restated_register and not restated:
    raise`) has its own message, and the test reads it: the later stale-entry check (an entry that reached no record) also
    names the key, so a match on the key alone would pass with the guard disabled (mutation-checked: disabling the guard
    fails this test)."""
    real = ra.load_restated_base()
    extra = dict(real)
    extra["1218_2015"] = real["4747_2024"]
    monkeypatch.setattr(ra, "load_restated_base", lambda path=None, e=extra: e)
    with pytest.raises(ValueError) as err:
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)
    msg = str(err.value)
    assert msg.startswith("data/restated_base_excluded.json: 1218_2015 is no reliable gross record of the primary "
                          "sample at the exclusion step (basis "), msg
    assert "reached no" not in msg and "stale" not in msg.lower(), msg


def test_an_unmeasurable_entry_that_reaches_no_reliable_gross_record_stops_the_run(monkeypatch):
    """The stale-entry guard of rule 5b: a record outside the sample (1206/2019 in run-off) or not gross (1218/2015)
    cannot be named in the takeon_unmeasurable bucket."""
    real = ra.load_takeon_unmeasurable()
    for bogus in ("1206_2019", "1218_2015"):
        extra = dict(real)
        extra[bogus] = real["1110_2022"]
        monkeypatch.setattr(ra, "load_takeon_unmeasurable", lambda path=None, e=extra: e)
        with pytest.raises(ValueError, match=bogus):
            ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_a_record_cannot_be_both_unmeasurable_and_excluded_or_listed(tmp_path):
    for other in ("excluded", "history_restated"):
        reg = _register()
        if other == "excluded":
            reg[other]["1110_2022"] = copy.deepcopy(reg["excluded"]["4747_2024"])
        else:
            reg[other]["1110_2022"] = copy.deepcopy(reg["history_restated"]["382_2022"])
        p = tmp_path / ("reg_%s.json" % other)
        p.write_text(json.dumps(reg), encoding="utf-8")
        with pytest.raises(ValueError, match="1110_2022.*both"):
            ra.load_takeon_unmeasurable(p)


def test_a_mistyped_key_in_either_bucket_stops_the_primary_load(monkeypatch):
    real = ra.restated_register_keys()
    assert len(real) == 34 and "1110_2022" in real
    for bogus in ("9999_2032", "4747_2042"):
        monkeypatch.setattr(ra, "restated_register_keys", lambda path=None, b=bogus: real + [b])
        with pytest.raises(ValueError, match=r"data/restated_base_excluded.json: 1 key\(s\).*%s" % bogus):
            ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_the_register_is_a_hashed_raw_byte_input():
    assert str(ra.RESTATED_BASE_REGISTER) in ra.source_files_for_hash([])
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/restated_base_excluded.json -text" in fh.read().splitlines()


# --- the decisions after review 8 (decision of the Claude analysis session, 23 October 2026) -------------------------------

def _round5_text(name):
    with io.open(os.path.join(HERE, rb.ROUND5, name), encoding="utf-8") as fh:
        return fh.read()


def test_rule_1s_control_clause_is_exact_in_the_rules_the_register_and_the_adjudication():
    """rules.md, the register's _rule text and the adjudication state the exact clause (within 5%, or within 10% when the
    same basis gap explains both years and the year t miss is at least three times the control's), say it was made exact
    on 23 October after review 8 and changed no outcome but 4242/2022's, and name what was added after the rules were
    written."""
    rules, adj = _round5_text("rules.md"), _round5_text("adjudication.md")
    clause = "within 5%, or within 10% when the same basis gap explains"
    flat = " ".join(rules.split())
    for text in (flat, " ".join(adj.split())):
        assert "Rules 1 to 7 were written before the adjudication" in text
        assert "rule 5b" in text and "take-on clause" in text and "exact control clause" in text
    assert "ties when it is " + clause in flat and "at least three times the control's" in flat
    assert "made exact on 23 October 2026, after review 8, and re-applied to every record" in flat
    assert "changed no outcome but 4242/2022's" in flat
    assert "Expected: 2689/2023, 4747/2024, 6134/2022, 780/2016" in flat
    reg_rule = _register()["_rule"]
    for needle in ("within 10% when the same basis gap explains both years", "at least three times the control's",
                   "Rules 1 to 7 were written before the adjudication", "rule 5b, rule 6's take-on clause",
                   "rule 1's exact control clause", "changing no outcome but 4242/2022's"):
        assert needle in reg_rule, needle
    doc = " ".join(rb.__doc__.split())
    assert "Rules 1 to 7 were written before the adjudication" in doc and "rule 5b" in doc
    assert "take_on_table_unreconciled" in doc and "rule 1's exact control clause" in doc
    # the adjudication's third line says the same (the sentence wraps in the generator, so read it flat)
    first = adj.splitlines()[2]
    assert "rules 1 to 7 were written before the adjudication" in first and "exact control clause" in first
    with io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8") as fh:
        prov = " ".join(fh.read().split())
    assert "Rules 1 to 7 were written before the adjudication" in prov and "exact control clause" in prov


def test_the_two_rule_1_records_that_need_the_ten_percent_clause_record_the_control_miss_its_basis_and_the_ratio():
    reg = _register()
    c780 = reg["excluded"]["780_2016"]["conditions"]["control_ties"]["facts"]
    for needle in ("control miss +9.5%", "'2010 & prior'", "basis", "+79.8%", "8.4 times", "within 10%", "at least three times"):
        assert needle in c780, needle
    c4747 = reg["excluded"]["4747_2024"]["conditions"]["control_ties"]["facts"]
    for needle in ("control miss -7.2%", "38,860", "Basis reason", "-81.9%", "11.4 times", "within 10%", "at least three times"):
        assert needle in c4747, needle
    # the ratios are the readings' own: 79.8 / 9.5 and 81.9 / 7.2
    assert round(79.8 / 9.5, 1) == 8.4 and round(81.9 / 7.2, 1) == 11.4 and 79.8 >= 3 * 9.5 and 81.9 >= 3 * 7.2
    # the other two keep the plain 5% clause
    for k in ("2689_2023", "6134_2022"):
        assert "within 5%; met" in reg["excluded"][k]["conditions"]["control_ties"]["facts"], k


@pytest.mark.parametrize("key,needles", [
    ("2232_2017", ("not met", "+7.4%", "1.4 times", "2.7 times", "22.2%")),
    ("2488_2016", ("not met", "+38.3%", "over 10%", "1.6 times", "ties (-3.3%")),
    ("382_2021", ("not met", "-6.9%", "-8.7%", "1.3 times")),
    ("1967_2017", ("not met", "+4.0%", "+1.7%", "-7.6%")),
    ("1729_2023", ("not met", "-0.4%", "-27.3%")),
])
def test_the_records_rule_1_does_not_reach_under_the_exact_clause_say_why_and_stay_least_certain(key, needles):
    e = _register()["history_restated"][key]
    assert "exact control clause" in e["facts"] and "stays least certain" in e["facts"], key
    for needle in needles:
        assert needle in e["facts"], (key, needle)


def test_the_ratios_the_five_entries_state_are_the_readings_own():
    """The multiples the entries quote follow from the percentages in their readings (the control's against the year t's)."""
    assert round(10.5 / 7.4, 1) == 1.4 and round(20.1 / 7.4, 1) == 2.7 and round(3 * 7.4, 1) == 22.2
    assert round(59.5 / 38.3, 1) == 1.6 and round(8.7 / 6.9, 1) == 1.3


def test_3500_2022_joins_the_list_with_the_lpt_placement_conflict_and_the_share_of_r():
    e = _register()["history_restated"]["3500_2022"]
    assert e["clauses"] == ["take_on_table_unreconciled"] and "take_on" not in e
    f = e["facts"]
    for needle in ("-389.8m", "-293.1m", "-26.4m", "266.7m", "P6", "ninth", "293.8m", "67.1m", "388.7m", "9.1%",
                   "rule 5b would list the record too", "3,955.045m"):
        assert needle in f, needle
    assert round(100 * (293.8 + 67.1) / 3955.045, 1) == 9.1 and round(100 * 388.7 / 3955.045, 1) == 9.8
    assert round(-291.756 - 98.057, 1) == -389.8
    assert [r["reader"] for r in e["readings"]] == ["P6", "Q7"]
    assert "3500_2022" in ra.load_takeon_base()


def test_2001_2016_stays_listed_because_its_move_is_over_one_percent_of_r():
    """Decision 6: the restated move, as a share of R (1,601.0m opening gross claims outstanding), is over 1% on every
    measure, so rule 6 is met and the record stays on the list (it is not moved to 'stands')."""
    reg = _register()
    assert "2001_2016" in reg["history_restated"] and reg["_adjudicated"]["2001_2016"]["outcome"] == "least_certain"
    f = reg["history_restated"]["2001_2016"]["facts"]
    for needle in ("1,601.0m", "16.01m", "24.9m (1.56% of R)", "16.7m (1.04% of R)", "2.60%", "1.4% of R", "rule 6 is met",
                   "stays on the list"):
        assert needle in f, needle
    R = 1601.0
    falls = (786.4 - 761.5, 821.4 - 804.7)
    assert [round(100 * x / R, 2) for x in falls] == [1.56, 1.04] and all(x > 0.01 * R for x in falls)
    assert round(100 * sum(falls) / R, 2) == 2.60 and 0.02 * 1089.5 > 0.01 * R
