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
    mistyped key; the register is a hashed raw-byte input of the run identifier;
  * rule 4b's outcomes follow mechanically from the round-8 scan's answers and the readings' own incurred misses
    (round8/rule_4b_scan.json; mutation-checked by flipping hand answers).

Run:  python -m pytest src/test_restated_base_excluded.py -q
"""
import copy
import io
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_restated_base_excluded as rb  # noqa: E402
import run_analysis as ra  # noqa: E402

#: rule 1; 4242/2022 left it for rule 3 after review 8 (the previous report's base reconciles once the merged '2016 & Prior'
#: column is set aside), 780/2016 for rule 6 and 4747/2024 for rule 4b after the round-8 readings
RULE_1 = ["2689_2023", "6134_2022"]
#: rule 4b (24 October 2026): 4747/2024, and 2232/2017, which the rule-4b population scan found
RULE_4B = ["2232_2017", "4747_2024"]
EXCLUDED = RULE_1 + RULE_4B
#: 1609/2024's rule-4 correction was REVERSED on 26 October 2026 (round 10: Z9, Z10); 3330/2018 (rule 3) and 3330/2017 (the
#: accounts' roll-forward, derived) are the census's figure changes, in data/mature_cohort_figures.json
CORRECTED = {"318_2024": "printed_table_error", "1274_2016": "printed_table_error",
             "2232_2020": "previous_report_base", "4242_2022": "previous_report_base"}
#: rule 8, the source-history rule (26 October 2026): the 11 records the census set aside
SET_ASIDE = ["1084_2018", "1416_2024", "1884_2021", "2008_2023", "3000_2016", "3500_2021", "3500_2022", "3500_2023",
             "6111_2017", "6111_2018", "6131_2021"]
#: the records the census adds to rule 6's list that were not among the 83 (6118/2018 was already on it; 1609/2024, whose
#: correction was reversed, and 1686/2021, a take-on whose rule 5 holds, are among the 83)
CENSUS_LISTED_NEW = ["1110_2020", "1254_2023", "3330_2017"]
TAKEON_IN_R = ["1686_2021", "1856_2024", "1884_2021", "2488_2019", "3000_2016", "3500_2022", "3500_2023", "4000_2022",
               "4444_2018", "4444_2023"]
#: rule 5b (after the round-7 readings U1, U2): the take-on leaves the primary (1110/2022), or the filing bounds it at or
#: below 10% of R and the record is listed (1458/2024)
UNMEASURABLE = ["1110_2022"]
BOUNDED = ["1458_2024"]


def adj_keys_of_rule_6_alone(adj):
    """The records whose only rule is rule 6."""
    return [k for k, a in adj.items() if a["rule"] == "6"]


def _register():
    with io.open(str(rb.REGISTER), encoding="utf-8") as fh:
        return json.load(fh)


def _archived(reader, key):
    """A record's reading as archived verbatim under round5/readings/ (not the register's copy)."""
    with io.open(os.path.join(HERE, rb.ROUND5, "readings", reader + ".json"), encoding="utf-8") as fh:
        return json.load(fh)[key]


def _archived8(reader):
    """A round-8 reading file as archived verbatim under round8/readings/ (Z8 keys records by the filing's name)."""
    with io.open(os.path.join(str(rb.READINGS8), reader + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def _pct(value):
    """A reading's percentage: a number, or the signed number a diff_pct string leads with ('+79.8 (294.7 vs ...')."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(re.match(r"\s*([+-]?\d+(?:\.\d+)?)", value).group(1))


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
    assert counts == {"corrected": 3, "corrected_least_certain": 1, "correction_reversed_least_certain": 1,
                      "excluded": 5, "least_certain": 24, "stands": 36, "stands_then_set_aside": 1, "take_on_base": 5,
                      "take_on_base_and_least_certain": 1, "take_on_base_and_set_aside": 4,
                      "take_on_bounded_least_certain": 1, "take_on_unmeasurable": 1}
    assert reg["_population"]["outcomes"] == dict(sorted(counts.items()))
    assert sorted(reg["excluded"], key=rb.order_key) == sorted(EXCLUDED, key=rb.order_key)
    assert sorted(k for k, a in adj.items() if a["rule"] in ("1", "4b")) == sorted(reg["excluded"])
    assert {k: e["rule"] for k, e in reg["excluded"].items()} == {**{k: "1" for k in RULE_1}, **{k: "4b" for k in RULE_4B}}
    assert all(adj[k]["rule"] == e["rule"] for k, e in reg["excluded"].items())
    # 780/2016 is back under rule 6 after the round-8 readings
    assert adj["780_2016"] == {"rule": "6", "outcome": "least_certain", "where": adj["780_2016"]["where"],
                               "readers": ["P6", "Q5", "Z7", "Z8"]}
    # the round-5 records on rule 6's list, and the four the census adds (they were not among the 83)
    assert sorted(k for k, a in adj.items() if "6" in a["rule"]) == sorted(set(reg["history_restated"]) - set(CENSUS_LISTED_NEW))
    assert not set(CENSUS_LISTED_NEW) & set(adj)
    assert sorted(k for k, a in adj.items() if a["rule"] == "5b") == sorted(reg["takeon_unmeasurable"]) == UNMEASURABLE
    assert len(reg["history_restated"]) == 31
    assert sorted(set(reg["history_restated"]) - set(adj_keys_of_rule_6_alone(adj))) == [
        "1110_2020", "1254_2023", "1274_2016", "1458_2024", "1609_2024", "1686_2021", "3330_2017"]
    # 3000/2016, 3500/2022 and 3500/2023 left rule 6's list for rule 8's excluded set
    assert sorted(reg["source_history_set_aside"]) == sorted(SET_ASIDE) and not set(SET_ASIDE) & set(reg["history_restated"])


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
    # 3000/2016, 3500/2022 and 3500/2023: rule 5 holds (R already holds their take-ons) and rule 8 sets them aside
    for k in ("1884_2021", "3000_2016", "3500_2022", "3500_2023"):
        assert adj[k]["outcome"] == "take_on_base_and_set_aside" and adj[k]["rule"] == "5 and 8", k
        assert k in takeon and k in reg["source_history_set_aside"] and k not in reg["history_restated"], k
        assert k in reg["source_history_set_aside"], k
    for k in ("3000_2016", "3500_2022", "3500_2023"):
        assert reg["source_history_set_aside"][k]["earlier_listing"]["rule"] == "6", k
    assert adj["1416_2024"]["outcome"] == "stands_then_set_aside"
    assert adj["1686_2021"]["outcome"] == "take_on_base_and_least_certain" and "1686_2021" in takeon
    assert reg["history_restated"]["1686_2021"]["clauses"] == ["census_residual_concern"]
    assert reg["source_history_set_aside"]["3500_2023"]["earlier_listing"]["clauses"] == ["take_on_table_unreconciled"]
    assert reg["source_history_set_aside"]["3500_2022"]["earlier_listing"]["clauses"] == ["take_on_table_unreconciled"]
    # 1609/2024: the rule-4 correction is reversed, the record stays at the printed figure and is listed
    assert adj["1609_2024"]["outcome"] == "correction_reversed_least_certain" and "1609_2024" not in mature
    assert reg["history_restated"]["1609_2024"]["clauses"] == ["orientation_outside_evidence"]
    # the records that stand are in no bucket of this register and in no correction
    for k, a in adj.items():
        if a["outcome"] == "stands":
            assert k not in reg["excluded"] and k not in reg["history_restated"] and k not in fx, k
            assert k not in reg["source_history_set_aside"], k
            assert (mature.get(k) or {}).get("correction") is None, k


def test_every_entry_rests_on_two_readings_with_the_year_t_filings_pages_and_the_archived_verdicts():
    reg = _register()
    for bucket in ra.RESTATED_BUCKETS:
        for k, e in reg[bucket].items():
            assert ra._restated_entry_gaps(e, bucket) == [], k
            census = bucket == ra.SOURCE_HISTORY_BUCKET or k in CENSUS_LISTED_NEW or k == "1686_2021"
            for r in e["readings"]:
                with io.open(os.path.join(HERE, *r["source"].split("/")), encoding="utf-8") as fh:
                    arch = json.load(fh)[k]
                if census:
                    # a round-9 reading: the archived entry verbatim (its own verdict field, which may be absent)
                    assert r["verdict_as_read"] == arch.get("verdict") and r["pages_as_read"] == arch.get("pages"), (
                        k, r["reader"])
                    assert r["source"].endswith("round9/readings/%s.json" % r["reader"]), (k, r["reader"])
                    continue
                assert r["verdict"] == arch["verdict"] and r["pages_as_read"] == arch["pages"], (k, r["reader"])
                assert set(r["pages"]) <= set(rb._ints(arch["pages"] if isinstance(arch["pages"], list)
                                                       else list(arch["pages"].values()))), (k, r["reader"])
            day = "26" if census else ("24" if (k in RULE_4B or k in rb.ROUND8_RULE6) else "23")
            assert e["decision"].startswith("decision of the Claude analysis session, %s October 2026" % day), k
            # the round-8 control readings are the archive's, verbatim
            for r in e.get("control_readings", []):
                with io.open(os.path.join(HERE, *r["source"].split("/")), encoding="utf-8") as fh:
                    arch = json.load(fh)
                arch = arch.get(k) or arch["syndicate_" + k]
                assert r["source"].endswith("round8/readings/%s.json" % r["reader"]), (k, r["reader"])
                assert r["control_diff_pct"] == arch["control_diff_pct"], (k, r["reader"])
    for k in ("780_2016", "4747_2024"):
        b = "excluded" if k in RULE_4B else "history_restated"
        assert [r["reader"] for r in reg[b][k]["control_readings"]] == ["Z7", "Z8"], k
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
    bad = [(rid, dict(e, verdict="valid") if rid == "Q5" else e) for rid, e in reads["6134_2022"]]
    with pytest.raises(SystemExit, match="rule 1 needs both readings"):
        rb.entry_for("6134_2022", bad, "excluded")
    # rule 4b rests on the facts both readings report, not their labels: 2232/2017's P3 reads 'valid'
    assert rb.entry_for("2232_2017", reads["2232_2017"], "excluded")["verdicts"] == {"P3": "valid",
                                                                                    "Q4": "restated_base"}


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
    ("excluded", "6134_2022", "no-decision"), ("excluded", "6134_2022", "one-reading"),
    ("excluded", "6134_2022", "same-reader-twice"), ("excluded", "6134_2022", "reader-says-valid"),
    ("excluded", "6134_2022", "no-pages"), ("excluded", "6134_2022", "reading-no-pages"),
    ("excluded", "6134_2022", "no-quote"), ("excluded", "6134_2022", "condition-flipped"),
    ("excluded", "6134_2022", "previous-base-reconciles"), ("excluded", "6134_2022", "condition-no-facts"),
    ("excluded", "6134_2022", "no-rule"), ("excluded", "6134_2022", "rule-4b-on-rule-1-conditions"),
    ("excluded", "4747_2024", "no-rule"), ("excluded", "4747_2024", "unknown-rule"),
    ("excluded", "4747_2024", "rule-1-on-rule-4b-conditions"), ("excluded", "4747_2024", "control-ties"),
    ("excluded", "4747_2024", "paid-does-not-fall"), ("excluded", "2232_2017", "previous-base-reconciles"),
    ("excluded", "2232_2017", "condition-flipped"), ("excluded", "2232_2017", "paid-fall-no-facts"),
    ("excluded", "2232_2017", "one-reading"),
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
    elif change == "no-rule":
        del e["rule"]
    elif change == "unknown-rule":
        e["rule"] = "4c"
    elif change in ("rule-4b-on-rule-1-conditions", "rule-1-on-rule-4b-conditions"):
        e["rule"] = "4b" if e["rule"] == "1" else "1"
    elif change == "control-ties":
        e["conditions"]["control_ties"]["holds"] = True
    elif change == "paid-does-not-fall":
        e["conditions"]["cumulative_paid_falls_unexplained"]["holds"] = False
    elif change == "paid-fall-no-facts":
        e["conditions"]["cumulative_paid_falls_unexplained"]["facts"] = " "
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
    """Only the clause take_on_base_bounded (1458/2024) carries a take-on object: 382/2022's clause is
    unexplained_history_move, and 3500/2023 (take_on_table_unreconciled until the census) is set aside now, with R holding
    its take-on."""
    reg = _register()
    assert "take_on" not in reg["history_restated"]["382_2022"]
    assert "take_on" in reg["history_restated"]["1458_2024"]
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
    """The two records of rule 1 and the two of rule 4b leave the primary with the tag RESTATED_BASE_TABLE, counted, each
    with its own rule's reason in the ledger; 780/2016 is back at +24.9m USD as printed."""
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    for key in EXCLUDED:
        r = prim["by_key"][key]
        assert r["data_quality_tag"] == ra.RESTATED_BASE_TAG == "RESTATED_BASE_TABLE", key
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, key
        entry = prim["log"]["syndicate_%s.json" % key]
        assert entry["status"] == ra.RESTATED_BASE_TAG and "data/restated_base_excluded.json" in entry["reason"]
        rule = "4b" if key in RULE_4B else "1"
        assert entry["reason"] == ra.RESTATED_LOG_REASON[rule] and ("rule %s of the round-5" % rule) in entry["reason"]
        assert old["by_key"][key]["data_quality_tag"] == "RELIABLE" and old["by_key"][key]["s_raw_a"] is not None
    assert prim["counters"]["restated_base_excluded"] == len(EXCLUDED) == 4
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.RESTATED_BASE_TAG) == 4
    assert set(EXCLUDED) <= _ws(old["records"]) and not set(EXCLUDED) & _ws(prim["records"])
    # 643 until rule 8: the census set 11 records aside (the primary is 632)
    assert len(_ws(prim["records"])) == 632
    # 4242/2022 (rule 3 after review 8) is in the primary at the previous report's base: -80.015m USD
    r = prim["by_key"]["4242_2022"]
    assert r["data_quality_tag"] == "RELIABLE" and r["pyd_basis_source"] == "mature-cohort-figure:register"
    assert "4242_2022" in _ws(prim["records"]) and r["pyd_gbp_m"] == pytest.approx(-66.254037, abs=1e-6)
    # 780/2016 (rule 6 after the round-8 readings) is in the primary at M as printed, +24.9m USD
    r = prim["by_key"]["780_2016"]
    assert "780_2016" in _ws(prim["records"]) and r["data_quality_tag"] == "RELIABLE"
    assert r["pyd_gbp_m"] == pytest.approx(ra.load_mature_cohort_figures()["780_2016"]["figure_gbp_m"], abs=1e-6)
    assert ra.load_mature_cohort_figures()["780_2016"]["figure_m"] == 24.9


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
    assert prim["counters"]["source_history_set_aside"] == 11


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
    assert len(real) == 47 and "1110_2022" in real and "6131_2021" in real
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


def test_rule_1s_control_clause_is_exact_and_moved_no_record_on_23_october():
    """rules.md, the register's _rule text, the build's docstring, the adjudication and data-provenance.md state the exact
    clause (within 5%, or within 10% when the same basis gap explains both years and the year t miss is at least three
    times the control's), say that on 23 October it moved no record and that, applied to the round-8 readings, it takes
    780/2016 and 4747/2024 out of rule 1, state the incurred-first rule, and name what was added after the rules were
    written. No text may say the clause changed or kept an outcome, or that it decided no record (final review 2, R4 F1
    and F2; the review of the fixes, items 1 and 4)."""
    rules, adj = _round5_text("rules.md"), _round5_text("adjudication.md")
    flat, adj_flat = " ".join(rules.split()), " ".join(adj.split())
    reg_rule = " ".join(_register()["_rule"].split())
    doc = " ".join(rb.__doc__.split())
    with io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8") as fh:
        prov = " ".join(fh.read().split())
    texts = {"rules.md": flat, "adjudication.md": adj_flat, "_rule": reg_rule, "docstring": doc, "provenance": prov}
    for name, text in texts.items():
        assert "Rules 1 to 7 were written before the adjudication" in text or "rules 1 to 7 were written before the " \
            "adjudication" in text, name
        assert "exact control clause" in text and "rule 4b" in text.lower(), name
        low = text.lower()
        assert "on 23 october" in low and "moved no record" in low, name
        assert "takes 780/2016 and 4747/2024 out of rule 1" in text, name
        assert "4242/2022" in text, name
        assert "incurred first" in low and "a paid cell m does not use cannot make m unmeasured" in low, name
        assert "paid where computable" not in text, name
        for retracted in ("no outcome but 4242", "meet it only through its 10% branch", "changed no outcome",
                          "decided no record"):
            assert retracted not in text, (name, retracted)
    assert "ties when it is within 5%, or within 10% when the same basis gap explains" in flat
    assert "at least three times the control's" in flat
    assert "Expected: 2689/2023, 6134/2022 (both tie within 5%)" in flat
    assert "within 10% when the same basis gap explains both years" in reg_rule
    # 780/2016's two ratios (Z7 on the percentages, Z8 on the absolute misses) are both disclosed
    for name in ("rules.md", "provenance"):
        assert "0.6 times the control's on the percentages" in texts[name] and "0.81" in texts[name], name
    first = adj.splitlines()[2]
    assert "rules 1 to 7 were written before the adjudication" in first and "exact control clause" in first


def test_the_round_8_readings_put_both_ten_percent_records_outside_the_clause():
    """Z7 and Z8 (round 8) agree: 4747/2024's control misses by -7.2% with no shared basis gap, and 780/2016's year t miss
    is under its control's, so neither meets the 10% branch; the register quotes the figures from the archived readings
    (not literals)."""
    reg = _register()
    z7, z8 = (_archived8(r) for r in ("Z7", "Z8"))
    for key in ("780_2016", "4747_2024"):
        a, b = z7[key], z8["syndicate_" + key]
        for z in (a, b):
            c, t = abs(_pct(z["control_diff_pct"])), abs(_pct(z["year_t_diff_pct"]))
            assert 5 < c <= 10, (key, c)
            # the 10% branch needs a shared basis gap AND a year t miss three times the control's
            shared = z.get("shared_basis_gap") or z["item3_shared_basis_gap"]["answer"]
            assert shared != "yes" or t < 3 * c, key
            assert shared == "no" or t < 3 * c, key
    e4747 = reg["excluded"]["4747_2024"]
    assert e4747["rule"] == "4b" and e4747["conditions"]["control_ties"]["holds"] is False
    f = e4747["conditions"]["control_ties"]["facts"]
    assert "%+.1f%%" % z7["4747_2024"]["control_diff_pct"] in f and "no shared basis gap (Z7, Z8)" in f
    assert z7["4747_2024"]["item3_shared_basis_gap"]["answer"] == z8["syndicate_4747_2024"]["shared_basis_gap"] == "no"
    f780 = reg["history_restated"]["780_2016"]["facts"]
    c, t = z7["780_2016"]["control_diff_pct"], z7["780_2016"]["year_t_diff_pct"]
    for needle in ("%+.1f%%" % c, "%+.1f%%" % t, "%.1f times" % (t / c), "Rule 1's exact control clause: not met",
                   "+24.9m USD", "Rule 4b: not met"):
        assert needle in f780, needle
    assert reg["history_restated"]["780_2016"]["clauses"] == ["unexplained_history_move"]
    assert [r["m_recomputed_m"] for r in reg["history_restated"]["780_2016"]["readings"]] == [24.9, 24.9]


@pytest.mark.parametrize("key,cells", [
    ("4747_2024", ("213", "4,843", "4,164", "5,883")),
    ("2232_2017", ("19,393", "22,799", "43,200", "47,658")),
])
def test_a_rule_4b_record_shows_the_paid_fall_both_readings_print(key, cells):
    """Rule 4b (i): both readings print the year t table's cumulative paid and the year t-1 report's for the same year;
    the entry quotes the cells, and every cell it quotes is in each of the record's archived readings."""
    e = _register()["excluded"][key]
    f = e["conditions"]["cumulative_paid_falls_unexplained"]["facts"]
    for cell in cells:
        assert cell in f, (key, cell)
    for r in e["readings"]:
        text = json.dumps(_archived(r["reader"], key), ensure_ascii=False)
        for cell in cells:
            assert re.search(r"(?<![\d,])%s(?![\d,])" % re.escape(cell), text), (key, r["reader"], cell)
    assert [c for c, want in rb.CONDITIONS_4B] == [c for c, want in ra.RESTATED_CONDITIONS_4B]
    assert {c: v["holds"] for c, v in e["conditions"].items()} == dict(ra.RESTATED_CONDITIONS_4B)


def test_2232_2017_meets_rule_4b_narrowly_and_the_scan_found_it():
    """2232/2017's (ii) is narrow: -10.5% in both readings; its UY2012 paid fall (x0.851) is beyond the x0.918-0.939
    retranslation Q4 measures on the same columns; the previous report's base gives the same cells; the scan found it."""
    e = _register()["excluded"]["2232_2017"]
    p3, q4 = _archived("P3", "2232_2017"), _archived("Q4", "2232_2017")
    assert p3["incurred_test"]["diff_pct"] == q4["incurred_test"]["diff_pct"] == -10.5
    assert "-10.5%" in e["conditions"]["year_t_fails_accounts"]["facts"] and "narrowly" in e["conditions"][
        "year_t_fails_accounts"]["facts"]
    assert round(19393 / 22799, 3) == 0.851 < 0.918 and "0.918-0.939" in q4["cells_check"]
    assert "x0.851" in e["conditions"]["cumulative_paid_falls_unexplained"]["facts"]
    assert "rule_4b_scan.json" in e["found_by"]
    ctl = _pct(re.search(r"([+-]\d+(?:\.\d+)?)%\s*$", p3["incurred_test"]["prev_control"]).group(1))
    f = e["conditions"]["control_ties"]["facts"]
    assert "%+.1f%%" % ctl in f and "%.1f times it" % (abs(p3["incurred_test"]["diff_pct"]) / ctl) in f
    with io.open(os.path.join(HERE, rb.ROUND5, "rules.md"), encoding="utf-8") as fh:
        rules = " ".join(fh.read().split())
    assert "4b. **A table its own cells prove inconsistent" in rules
    assert "It decides two records" in rules and "2232/2017 (rule 6, least certain, until the scan found it)" in rules
    assert "(ii) is narrow" in rules


def _incurred_t(reading):
    """A reading's year t implied gross incurred miss, in per cent, wherever it gives one (the readers name the field in
    several ways), else None."""
    inc = reading.get("incurred_test")
    cands = []
    if isinstance(inc, dict):
        for f in ("diff_pct", "t_diff_pct", "diff_pct_t", "diff_pct_t_gross"):
            cands.append(inc.get(f))
        for f in ("year_t", "t"):
            if isinstance(inc.get(f), dict):
                cands.append(inc[f].get("diff_pct"))
    for f in ("year_t_diff_pct",):
        cands.append(reading.get(f))
    for c in cands:
        if isinstance(c, (int, float)) and not isinstance(c, bool):
            return float(c)
    return None


def test_the_rule_4b_scan_answers_every_structural_hit_with_its_cells():
    """round8/rule_4b_scan.json answers every one of the 83 records once. The scan is structural: in every reading it
    compares the paid cells quoted against each other, and every record with a falling pair (or a passage reporting a
    fall) is answered under 'read' with those pairs, reader by reader; the rest are 'no_fall_reported' and have none. An
    answer that finds the fall on the cells quotes them, and each reading it rests on quotes both. The records it decides
    are the register's rule-4b entries, and each answer's outcome names the record's rule in the register."""
    reg = _register()
    adj = reg["_adjudicated"]
    with io.open(str(rb.RULE_4B_SCAN), encoding="utf-8") as fh:
        scan = json.load(fh)
    sys.path.insert(0, str(rb.ROUND8))
    try:
        import scan_rule_4b as S
    finally:
        sys.path.remove(str(rb.ROUND8))
    hits = S.scan()
    assert set(hits) == set(adj) and len(adj) == 83
    structural = {k: {r: [list(p) for p in v] for r, v in h["structural"].items()} for k, h in hits.items()
                  if h["structural"]}
    flagged = {k for k, h in hits.items() if h["structural"] or h["text"]}
    assert len(structural) >= 20, "the structural pass finds the falling pairs the readings quote"
    for k, by_reader in structural.items():
        assert k in scan["read"] and scan["read"][k]["structural_hits"] == by_reader, k
    assert set(scan["read"]) >= flagged
    assert sorted(scan["no_fall_reported"]) == sorted(set(adj) - set(scan["read"]))
    assert not set(scan["no_fall_reported"]) & flagged
    for k in set(scan["read"]) - set(structural):
        assert "structural_hits" not in scan["read"][k], k
    assert sorted(scan["decides"]) == sorted(RULE_4B) == sorted(k for k, e in reg["excluded"].items() if e["rule"] == "4b")
    reads = S.readings()
    for k, ans in scan["read"].items():
        assert ans["readings"] == adj[k]["readers"], k
        tail = ans["outcome"].split("->")[-1]
        assert ("rule %s" % adj[k]["rule"]) in tail or ("rules %s" % adj[k]["rule"]) in tail, k
        assert ans["outcome"].startswith("CHANGED") == (k in ("780_2016", "2232_2017", "4747_2024")), k
        if ans["i"].startswith("yes") or k == "780_2016":
            later, earlier = ans["cells"]
            assert later in ans["i"] and earlier in ans["i"], k
            quoting = [r for r, e in reads[k].items()
                       if all(re.search(r"(?<![\d.,])%s(?!\d|,\d|\.\d)" % re.escape(c), json.dumps(e, ensure_ascii=False))
                              for c in (later, earlier))]
            assert len(quoting) >= 2, (k, quoting)
    assert "quotes both cells" in scan["_reports_standard"]
    for k in ("2232_2017", "2488_2016", "382_2021", "1967_2017", "1729_2023", "780_2016", "2468_2020", "1274_2022",
              "435_2016", "1218_2016", "1084_2016"):
        assert k in scan["read"], k
    # 1274/2022: (i) holds on its stale UY2016 cell, (ii) fails on incurred; it stands
    a = scan["read"]["1274_2022"]
    assert a["i"].startswith("yes") and a["ii"].startswith("no on incurred") and a["cells"] == ["279,946", "397,367"]
    assert "stale" in a["stale_cell"] and adj["1274_2022"]["outcome"] == "stands"
    # 780/2016 meets (i) on three of its four readings, said once and the same way
    assert scan["read"]["780_2016"]["i"].startswith("on three of the four readings")


def test_condition_ii_is_read_on_incurred_wherever_a_reading_gives_it():
    """Incurred first (24 October 2026): every exclusion under rules 1 and 4b whose readings give an implied incurred
    miss rests on it (each such miss is over 10%, and the entry's accounts facts quote one), and no record whose readings'
    incurred misses are all within 10% is excluded under either rule, however its paid test reads (1274/2022: paid
    +33.4%, incurred +0.25%, stands)."""
    reg = _register()
    reads = rb.load_readings()
    for k, e in reg["excluded"].items():
        incs = [x for x in (_incurred_t(r) for _rid, r in reads[k]) if x is not None]
        if not incs:
            continue
        assert all(abs(x) > 10 for x in incs), (k, incs)
        f = e["conditions"]["year_t_fails_accounts"]["facts"]
        assert any("%+.1f%%" % x in f or "%.1f%%" % abs(x) in f for x in incs), (k, incs)
    assert {k for k, e in reg["excluded"].items()} >= {"4747_2024", "2232_2017", "6134_2022"}
    for k, a in reg["_adjudicated"].items():
        incs = [x for x in (_incurred_t(r) for _rid, r in reads[k]) if x is not None]
        if incs and all(abs(x) <= 10 for x in incs):
            assert not (a["outcome"] == "excluded" and a["rule"] in ("1", "4b")), (k, incs)
    incs = [_incurred_t(r) for _rid, r in reads["1274_2022"]]
    assert incs == [0.25, 0.25] and reg["_adjudicated"]["1274_2022"]["outcome"] == "stands"


def _scan_answer(text):
    """A rule-4b scan answer read as it begins: 'yes...' (or, for (i), 'on three of the four readings...') holds,
    'no...' or 'not both...' fails, an absent answer is None; any other form is 'unread', which the test refuses where
    the answer decides."""
    if text is None:
        return None
    t = text.strip()
    if t.startswith("yes") or re.match(r"on (two|three|four) of the (three|four) readings", t):
        return True
    if t.startswith("no"):
        return False
    return "unread"


def test_rule_4b_outcomes_follow_from_the_readings_incurred_misses():
    """Rule 4b's outcome, derived mechanically (the review of final review 2's fixes, R4 6). For every record the scan
    reads: rule 4b reaches it only where rule 1's control does not tie ('yes...') and (i) holds. For each such record
    (780/2016, 2232/2017, 4747/2024), the (ii) answer states the incurred miss (the first signed percentage after the
    word 'incurred'), at least two readings give an implied incurred miss and each is the stated one to the places it is
    stated to (Z8's -81.87 is -81.9), (ii) is answered 'yes' exactly when |miss| > 10%, (iii) is
    answered wherever (ii) holds, and the record leaves the primary under rule 4b exactly when (ii) and (iii) both hold,
    in the scan's outcome, its 'decides' list and the register. So a hand answer flipped from 'no' to 'yes' (or a stated
    miss the readings do not give) fails here."""
    with io.open(str(rb.RULE_4B_SCAN), encoding="utf-8") as fh:
        scan = json.load(fh)
    adj = _register()["_adjudicated"]
    reads = rb.load_readings()
    reached, decided = [], []
    for k, a in scan["read"].items():
        is_4b = adj[k]["rule"] == "4b"
        assert ("rule 4b" in a["outcome"].split("->")[-1]) == is_4b, (k, a["outcome"])
        assert is_4b == (adj[k]["rule"] == "4b" and adj[k]["outcome"] == "excluded"), k
        ctl = _scan_answer(a["control_does_not_tie"])
        assert ctl in (None, True, False), (k, a["control_does_not_tie"])
        if ctl is not True:
            assert not is_4b, "%s: rule 4b reaches only a record whose control does not tie" % k
            continue
        i = _scan_answer(a["i"])
        assert i in (True, False), (k, a["i"])
        if not i:
            assert not is_4b, "%s: rule 4b needs (i)" % k
            continue
        reached.append(k)
        m = re.search(r"incurred[^%]*?([+-]\d+(?:\.\d+)?)%", a["ii"] or "")
        assert m, "%s: (ii) does not state the incurred miss first: %r" % (k, a["ii"])
        stated = float(m.group(1))
        places = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
        incs = [(rid, _incurred_t(r)) for rid, r in reads[k] if rid in a["readings"]]
        given = [(rid, x) for rid, x in incs if x is not None]
        assert len(given) >= 2, "%s: incurred first needs the readings' incurred miss: %r" % (k, incs)
        for rid, x in given:
            assert abs(x - stated) <= 0.5 * 10.0 ** -places + 1e-9, (
                "%s: (ii) states %+.*f%% but %s's implied incurred miss is %+g%%" % (k, places, stated, rid, x))
        fails = abs(stated) > 10.0
        assert _scan_answer(a["ii"]) is fails, (
            "%s: (ii) is answered %r with an incurred miss of %+g%%" % (k, a["ii"].split(":")[0], stated))
        iii = _scan_answer(a["iii"])
        if fails:
            assert iii in (True, False), "%s: (ii) holds, so (iii) must be answered: %r" % (k, a["iii"])
        out = fails and iii is True
        assert is_4b == out, "%s: (ii) %s, (iii) %r, but the outcome is %r" % (k, fails, a["iii"], a["outcome"])
        if out:
            decided.append(k)
    assert sorted(reached) == ["2232_2017", "4747_2024", "780_2016"], reached
    assert sorted(decided) == sorted(scan["decides"]) == sorted(RULE_4B)



@pytest.mark.parametrize("key,needles", [
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
    """The multiples the entries quote follow from the percentages in their archived readings (the year t miss against
    the control's), read from the readings' diff_pct fields; 2232/2017's control has no diff_pct field, so it is read
    from the end of P3's prev_control working, where the reader states it (2232/2017 is a rule-4b entry now; its control
    facts carry the multiple)."""
    reg = _register()["history_restated"]
    p3 = _archived("P3", "2232_2017")
    inc_t = _pct(p3["incurred_test"]["diff_pct"])
    ctl = _pct(re.search(r"([+-]\d+(?:\.\d+)?)%\s*$", p3["incurred_test"]["prev_control"]).group(1))
    f = _register()["excluded"]["2232_2017"]["conditions"]["control_ties"]["facts"]
    for needle in ("%+.1f%%" % ctl, "%.1f times it" % (abs(inc_t) / ctl), "incurred %+.1f%%" % inc_t):
        assert needle in f, ("2232_2017", needle)
    assert abs(inc_t) < 3 * ctl
    p6 = _archived("P6", "2488_2016")["incurred_test"]
    t, c = _pct(p6["diff_pct"]), _pct(p6["prev_diff_pct"])
    assert "%+.1f%%" % c in reg["2488_2016"]["facts"] and "%.1f times" % (t / c) in reg["2488_2016"]["facts"]
    p1 = _archived("P1", "382_2021")["incurred_test"]
    t, c = _pct(p1["year_t"]["diff_pct"]), _pct(p1["year_t_minus_1_control"]["diff_pct"])
    assert "%+.1f%%" % c in reg["382_2021"]["facts"] and "%+.1f%%" % t in reg["382_2021"]["facts"]
    assert "%.1f times" % (t / c) in reg["382_2021"]["facts"]


@pytest.mark.parametrize("key,reader,year", [
    ("4444_2017", "Z6", 2017), ("382_2023", "Q1", 2023), ("1947_2022", "P2", 2022), ("2001_2017", "P8", 2017),
    ("1910_2018", "P8", 2018), ("6118_2018", "Q4", 2018),
])
def test_a_cross_report_paid_proxy_miss_is_set_aside_with_its_reason(key, reader, year):
    """A year t paid miss over 10% that rests on a cross-report proxy (the year t table prints no end-(t-1) payments, so
    the base comes from the year t-1 report) is set aside, and the entry says so with the reading's own figure (final
    review 2, R4 F8: only 4444/2017's and 1967/2017's entries said so)."""
    f = _register()["history_restated"][key]["facts"]
    paid = _pct(_archived(reader, key)["paid_test"]["diff_pct"])
    assert abs(paid) > 10
    assert "paid %+.1f%%" % paid in f, (key, paid)
    assert "is a cross-report proxy because the %d table prints no end-%d payments" % (year, year - 1) in f, key


def test_every_rule_6_entry_states_any_paid_miss_over_ten_percent_its_readings_report():
    """Generalises the test above: a rule-6 entry (clauses unexplained_history_move or label_disagreement only) whose
    reading reports a year t paid miss over 10% quotes that figure, so the entry has to say why rule 1 does not take it."""
    reg = _register()
    seen = []
    for key, e in reg["history_restated"].items():
        if not set(e["clauses"]) <= {"unexplained_history_move", "label_disagreement"}:
            continue
        for rd in e["readings"]:
            pt = rd.get("paid_test")
            v = pt.get("diff_pct") if isinstance(pt, dict) else None
            if isinstance(v, str) and not re.match(r"\s*[+-]?\d", v):
                v = None
            if v is None or abs(_pct(v)) <= 10:
                continue
            seen.append(key)
            assert "%+.1f%%" % _pct(v) in e["facts"], (key, rd["reader"], v)
    assert {"382_2023", "1947_2022", "2001_2017", "1910_2018", "6118_2018", "4444_2017"} <= set(seen)


def test_3500_2022_keeps_its_earlier_listing_with_the_lpt_placement_conflict_and_the_share_of_r():
    """3500/2022 was listed under rule 6 (take_on_table_unreconciled, review 8) until the census set it aside under rule 8; its
    earlier listing and round-5 readings are kept in the entry."""
    e = _register()["source_history_set_aside"]["3500_2022"]["earlier_listing"]
    assert e["clauses"] == ["take_on_table_unreconciled"] and "take_on" not in e
    f = e["facts"]
    for needle in ("-389.8m", "-293.1m", "-26.4m", "266.7m", "P6", "ninth", "293.8m", "67.1m", "388.7m", "9.1%",
                   "rule 5b would list the record too", "3,955.045m"):
        assert needle in f, needle
    assert round(100 * (293.8 + 67.1) / 3955.045, 1) == 9.1 and round(100 * 388.7 / 3955.045, 1) == 9.8
    assert round(-291.756 - 98.057, 1) == -389.8
    assert [r["reader"] for r in e["round5_readings"]] == ["P6", "Q7"]
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



# --- rule 8, the source-history rule (26 October 2026): the census, the register, the loader's one mask --------------------

ROUND9 = os.path.join(HERE, "results", "extraction_error_rate", "mature-cohort", "round9")


def _round9_text(*parts):
    with io.open(os.path.join(ROUND9, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_rule_8_is_in_rules_md_with_its_exact_text_date_label_and_the_post_hoc_disclosure():
    rules = _round5_text("rules.md")
    i = rules.index("8. **Source history: leaves the primary**")
    text = " ".join(rules[i:].split())
    assert "added 26 October 2026" in text
    assert "recommendation of the Codex analysis, adopted on Colin's instruction of 26 October 2026 and applied by the Claude analysis session" in text
    assert "found during Codex's tail investigation of 6131/2021, after the results were seen (post hoc)" in text
    assert "chosen without any outcome value, size or sign" in text
    # the exact text of the rule, word for word
    assert '"' + rb.CODEX_RULE_TEXT + '"' in text
    for needle in ("overlapping claims history, gross/net mixing or cohort reassignment through closure",
                   "regardless of the outcome's size or sign", "ordinary internal RITC", "funds-withheld arrangement",
                   "unusual business, youth or SPA status is not sufficient by itself", "FX or accounting scope differs",
                   "source_history_unresolved", "../round9/population.md", "11 records"):
        assert needle in text, needle
    # the register carries the same text, label and disclosure
    meta = _register()["_source_history"]
    assert meta["rule_text"] == rb.CODEX_RULE_TEXT and "post hoc" in meta["found"]
    assert meta["label"].startswith("recommendation of the Codex analysis, adopted on Colin's instruction of 26 October 2026")
    assert "26 October 2026" in meta["rule"]


def test_the_census_population_and_criteria_are_archived_beside_the_rule():
    pop = json.loads(_round9_text("population.json"))
    md = _round9_text("population.md")
    assert pop["totals"]["selected_core"] == 81 and pop["totals"]["selected_host_side"] == 20
    assert pop["totals"]["selected_core_syndicates"] == 48 and pop["primary"]["records"] == 643
    assert len(pop["selected"]) == 81 and len(pop["selected_host_side"]) == 20 and len(pop["touched_out"]) == 254
    assert pop["totals"]["neither"] == 288 and sum(pop["totals"]["by_criterion_core"].values()) == 86
    for needle in ("S1 SPA vehicle", "S2 Inward closure", "S3 Outward closure", "S5", "S6", "outcome value",
                   "Selected, core (S1-S6)", "Selected, host side (H, conditional)"):
        assert needle in md, needle
    assert "81 core" in _round9_text("adjudication.md")
    for name in ("briefs/brief_r9.md", "briefs/brief_r10.md", "criteria.md", "depth/audit.md", "depth/second_reading.md"):
        assert os.path.exists(os.path.join(ROUND9, *name.split("/"))), name
    for rid in rb.CENSUS_READERS:
        assert os.path.exists(os.path.join(ROUND9, "readings", rid + ".json")), rid
    # every set-aside record is in the census population, selected by the criteria its entry shows
    sel = {x["id"]: x for x in pop["selected"]}
    for k, e in _register()["source_history_set_aside"].items():
        assert k in sel and e["census"]["criteria"] == sel[k]["criteria"], k
        assert e["census"]["evidence"] == sel[k]["evidence"], k


def test_the_register_sets_aside_exactly_the_11_census_records_each_on_readings_that_set_it_aside():
    reg = _register()
    sa = reg["source_history_set_aside"]
    assert sorted(sa, key=rb.order_key) == sorted(SET_ASIDE, key=rb.order_key) and len(sa) == 11
    assert reg["_source_history"]["set_aside"] == sorted(SET_ASIDE, key=rb.order_key)
    for k, e in sa.items():
        assert ra._restated_entry_gaps(e, ra.SOURCE_HISTORY_BUCKET) == [], k
        assert e["rule"] == "8" and e["reason_code"] == ra.SOURCE_HISTORY_REASON_CODE == "source_history_unresolved", k
        assert set(e["concern"]) <= set(ra.SOURCE_HISTORY_CONCERNS) and e["concern"], k
        assert sum(1 for v in e["verdicts"].values() if v == "set_aside") >= 2, (k, e["verdicts"])
        assert e["decision"].startswith("decision of the Claude analysis session, 26 October 2026"), k
        assert "recommendation of the Codex analysis, adopted on Colin's instruction of 26 October 2026" in e["decision"], k
        assert all(isinstance(p, int) and p >= 1 for p in e["pages"]) and e["pages"] and e["quote"].strip(), k
    # a decision rests on facts at least two readings report: 3000/2016 is set aside by K3 and the third reading Z13
    assert sa["3000_2016"]["verdicts"] == {"K3": "set_aside", "Z13": "set_aside", "L3": "concern_resolved"}
    for k in SET_ASIDE:
        if k != "3000_2016":
            assert len(sa[k]["verdicts"]) == 2, k


def test_the_loader_refuses_a_set_aside_entry_without_two_readings_that_set_it_aside(tmp_path):
    """Mutation checks of the validator: one reading, a reading that finds the concern resolved, no census criteria, no
    concern, a wrong reason code or rule each stop the load."""
    for change in ("one-reading", "second-reading-resolved", "no-criteria", "no-concern", "unknown-concern",
                   "wrong-code", "wrong-rule", "no-facts", "no-pages", "in-two-buckets"):
        reg = _register()
        e = reg["source_history_set_aside"]["6131_2021"]
        if change == "one-reading":
            e["readings"] = e["readings"][:1]
        elif change == "second-reading-resolved":
            e["readings"][1]["verdict"] = "concern_resolved"
        elif change == "no-criteria":
            e["census"] = {}
        elif change == "no-concern":
            e["concern"] = []
        elif change == "unknown-concern":
            e["concern"] = ["a_size_of_outcome"]
        elif change == "wrong-code":
            e["reason_code"] = "restated_base"
        elif change == "wrong-rule":
            e["rule"] = "6"
        elif change == "no-facts":
            e["facts"] = " "
        elif change == "no-pages":
            e["pages"] = []
        else:
            reg["history_restated"]["6131_2021"] = copy.deepcopy(reg["history_restated"]["382_2022"])
        p = tmp_path / ("reg_%s.json" % change)
        p.write_text(json.dumps(reg), encoding="utf-8")
        with pytest.raises(ValueError):
            ra.load_source_history_set_aside(p)
    # the unmutated register loads, and the loader returns the right bucket
    assert sorted(ra.load_source_history_set_aside(), key=rb.order_key) == sorted(SET_ASIDE, key=rb.order_key)


def test_the_primary_sets_the_11_records_aside_with_one_tag_one_counter_and_no_figure(loaded):
    """The loader reads the bucket as one mask: each record gets the tag SOURCE_HISTORY_SET_ASIDE and no figure (so no
    severity), a ledger reason and one count; the 672 construction keeps all of them, as before. 6131/2020 and the six 1991
    records stay."""
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    assert ra.SOURCE_HISTORY_TAG == "SOURCE_HISTORY_SET_ASIDE"
    with io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8") as fh:
        # the committed loader output at 9c227e7a: the 643-record primary before rule 8
        committed = json.load(fh)["observations"]
    committed_by_key = {"%s_%s" % (o["syndicate"], o["year"]): o for o in committed}
    assert len({ra.SOURCE_HISTORY_TAG, ra.RESTATED_BASE_TAG, ra.TAKEON_UNMEASURABLE_TAG, ra.TAKEON_TAG}) == 4
    for k in SET_ASIDE:
        r = prim["by_key"][k]
        assert r["data_quality_tag"] == ra.SOURCE_HISTORY_TAG, k
        assert r["s_raw_a"] is None and r["pyd_gbp_m"] is None and r["pyd_pct"] is None, k
        entry = prim["log"]["syndicate_%s.json" % k]
        assert entry["status"] == ra.SOURCE_HISTORY_TAG and entry["reason"] == ra.SOURCE_HISTORY_LOG_REASON, k
        assert "rule 8" in entry["reason"] and "data/restated_base_excluded.json" in entry["reason"], k
        o = old["by_key"][k]
        # the 672 construction does not read the register: whatever its own tag, never the set-aside one
        assert o["data_quality_tag"] != ra.SOURCE_HISTORY_TAG, k
        # the mask moves no denominator: R is the committed loader output's (take-on bases included) for every record
        assert r["opening_reserves_gbp_m"] == committed_by_key[k]["opening_reserves_gbp_m"], k
    assert prim["counters"]["source_history_set_aside"] == 11
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.SOURCE_HISTORY_TAG) == 11
    assert "source_history_set_aside" not in old["counters"]
    assert not any(e["status"] == ra.SOURCE_HISTORY_TAG for e in old["log"].values())
    ws_new = _ws(prim["records"])
    ws_old = _ws(committed)
    assert set(SET_ASIDE) <= ws_old and not set(SET_ASIDE) & ws_new
    assert len(ws_new) == 632 and len(ws_old) == 643 and ws_old - ws_new == set(SET_ASIDE)
    # 6131/2020 is read under the same protocol and stays; every 1991 record stays
    assert "6131_2020" in ws_new and prim["by_key"]["6131_2020"]["data_quality_tag"] == "RELIABLE"
    s1991 = sorted(k for k in ws_old if k.startswith("1991_"))
    assert len(s1991) == 6 and set(s1991) <= ws_new, s1991
    # the primary: 632 records of 117 syndicates, 27 of them assumed-business (RITC or a confirmed inward transfer)
    import assumed_business
    occ = assumed_business.keys()
    assert len({prim["by_key"][k]["syndicate"] for k in ws_new}) == 117
    assert len({o["syndicate"] for o in committed if "%s_%s" % (o["syndicate"], o["year"]) in ws_old}) == 118
    assert sum(1 for k in ws_new if k in occ) == 27 and sum(1 for k in ws_old if k in occ) == 33


def test_no_consumer_of_the_loaders_records_can_still_see_a_set_aside_record(loaded):
    """compute_eligibility (eligible_for_capital and every other flag that needs a figure), the donor pool of the vignettes
    and the distributions all start from the figure; a set-aside record has none, so it is in none of them."""
    recs = copy.deepcopy(loaded[ra.MATURE_COHORT_OUTCOME]["records"])
    ra.assign_event_groups(recs, min_events=ra.ANALYSIS_CONFIG["min_events_for_fe"])
    _meta, subsets = ra.build_subsets(recs)
    ra.compute_eligibility(recs, subsets)
    by_key = {"%s_%s" % (r["syndicate"], r["year"]): r for r in recs}
    for k in SET_ASIDE:
        r = by_key[k]
        for flag in ("eligible_for_distribution", "eligible_for_boxplot_reserves", "eligible_for_n1", "eligible_for_n3",
                     "eligible_for_capital"):
            assert not r[flag], (k, flag)
    pool = {"%s_%s" % (r["syndicate"], r["year"]) for r in ra._vig_donor_pool(recs)}
    assert not pool & set(SET_ASIDE)
    assert {"6131_2020", "1991_2018"} <= pool
    # a control: the same consumers do see a record that stays (so the assertions above could have failed)
    assert by_key["6131_2020"]["eligible_for_capital"] and by_key["1458_2024"]["eligible_for_capital"]


def test_every_sample_loader_that_reads_the_loaders_output_drops_a_set_aside_record(loaded, monkeypatch, tmp_path):
    """The producers read model/exposure_results.json with their own filters. Written from the loader's records on fixed
    inputs, each of the sample loaders below returns the same 632 records and none of the 11."""
    import adopted_model
    import calibrate_dispersion_ritc as cdr
    import check_cohort_scope as cs
    import check_missingness_sensitivity as cms
    import oos_validation
    recs = loaded[ra.MATURE_COHORT_OUTCOME]["records"]
    (tmp_path / "model").mkdir()
    out = tmp_path / "model" / "exposure_results.json"
    out.write_text(json.dumps({"observations": recs}, default=float), encoding="utf-8")
    expected = sorted(_ws(recs))
    assert len(expected) == 632 and not set(expected) & set(SET_ASIDE)
    monkeypatch.setattr(adopted_model, "RESULTS", out)
    monkeypatch.setattr(cdr, "RESULTS", out)
    for mod in (cs, cms, oos_validation):
        monkeypatch.setattr(mod, "SD", tmp_path)
    S, R, H, yr, syn, _ritc = adopted_model.load_sample()
    got = {"adopted_model.load_sample": sorted("%s_%s" % (a, b) for a, b in zip(syn, yr))}
    got["calibrate_dispersion_ritc.load_sample"] = sorted(cdr.load_sample()[4])
    got["check_cohort_scope.load"] = sorted(CS_key(o) for o in cs.load())
    got["check_missingness_sensitivity.load_sample"] = sorted(
        str(k).replace("syndicate_", "").replace(".json", "") for k in cms.load_sample()[4])
    for name, keys in got.items():
        assert keys == expected, (name, set(keys) ^ set(expected))
    # oos_validation.load returns no keys: its severities are the same 632
    assert len(oos_validation.load()[0]) == 632
    # a mutation: a producer that kept a set-aside record would fail the comparison above
    leaky = [dict(o, s_raw_a=0.1) if "%s_%s" % (o["syndicate"], o["year"]) == "6131_2021" else o for o in recs]
    out.write_text(json.dumps({"observations": leaky}, default=float), encoding="utf-8")
    _S, _R, _H, yr2, syn2, _r = adopted_model.load_sample()
    assert "6131_2021" in {"%s_%s" % (a, b) for a, b in zip(syn2, yr2)}


def CS_key(o):
    return "%s_%s" % (o["syndicate"], o["year"])


#: the modules that open model/exposure_results.json for something other than a fit sample: they take no selection of their
#: own (the ledgers and documents describe every record; fx_sensitivity and error_rate_propagation take their sample from
#: adopted_model.load_sample or the working-sample stems)
NOT_SAMPLE_LOADERS = {"run_analysis.py", "record_tests.py", "skip_budget.py", "build_current_results.py",
                      "generate_data_audit.py", "missingness_check.py", "error_rate_propagation.py", "fx_sensitivity.py",
                      "build_working_sample.py"}


def test_every_producer_selects_its_sample_on_the_figure_the_mask_blanks():
    """A gate that generalises (not a list of the producers a reviewer named): every source module that opens
    exposure_results.json and is not one of the ledgers or documents selects its observations on s_raw_a being present, the
    field the loader blanks for every record it sets aside, or on the data-quality tag list that includes the rule-8 tag."""
    import glob
    bad = []
    for path in sorted(glob.glob(os.path.join(HERE, "src", "*.py"))):
        name = os.path.basename(path)
        if name.startswith("test_") or name in NOT_SAMPLE_LOADERS:
            continue
        with io.open(path, encoding="utf-8") as fh:
            src = fh.read()
        opens = [ln for ln in src.splitlines() if "exposure_results" in ln
                 and ("open(" in ln or "RESULTS =" in ln or '/ "model"' in ln)]
        if not opens:
            continue
        if not re.search(r"s_raw_a[\"']\]?\)? is not None", src):
            bad.append(name)
    assert bad == [], "producers that do not select on s_raw_a: %s" % bad
    with io.open(os.path.join(HERE, "src", "check_missingness_sensitivity.py"), encoding="utf-8") as fh:
        assert '"%s"' % ra.SOURCE_HISTORY_TAG in fh.read()
    with io.open(os.path.join(HERE, "src", "missingness_check.py"), encoding="utf-8") as fh:
        mc = fh.read()
    assert 'obs.get("data_quality_tag") == "%s"' % ra.SOURCE_HISTORY_TAG in mc
    assert '"CORPUS:%s"' % ra.SOURCE_HISTORY_TAG in mc
    import build_current_results as bcr
    import generate_data_audit as gda
    for words in (bcr.SCIENTIFIC_DETAIL_WORDS, gda.SCIENTIFIC_DETAIL_WORDS):
        assert "rule 8" in words["source_history_set_aside"]


def test_an_entry_that_reaches_no_record_in_the_set_aside_bucket_stops_the_run(monkeypatch):
    """The per-record guard and the stale-entry guard of rule 8: a record in run-off (1206/2019) or not gross (1218/2015)
    cannot be named in the source_history_set_aside bucket."""
    real = ra.load_source_history_set_aside()
    for bogus, msg in (("1206_2019", "1206_2019"), ("1218_2015", "is no reliable gross record")):
        extra = dict(real)
        extra[bogus] = real["6131_2021"]
        monkeypatch.setattr(ra, "load_source_history_set_aside", lambda path=None, e=extra: e)
        with pytest.raises(ValueError, match=msg):
            ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_the_672_construction_does_not_read_the_set_aside_bucket(monkeypatch):
    monkeypatch.setattr(ra, "load_source_history_set_aside", lambda path=None: pytest.fail("the 672 reads the bucket"))
    records, counters, log, files = ra.load_and_classify(ra.PRECEDENCE_672_OUTCOME)
    assert "source_history_set_aside" not in counters
    assert sum(1 for r in records if r["data_quality_tag"] == ra.SOURCE_HISTORY_TAG) == 0


# --- the figures: 3330/2018, 3330/2017, and 1609/2024's reversal ---------------------------------------------------------

def test_3330_2018_is_corrected_under_rule_3_and_3330_2017_is_derived_from_the_accounts_roll_forward(loaded):
    mature = ra.load_mature_cohort_figures()
    e = mature["3330_2018"]
    assert e["figure_m"] == pytest.approx(1.094) and e["displaced"]["by"] == "previous_report_base"
    assert e["displaced"]["figure_m"] == pytest.approx(-1.384) and e["correction"]["figure_as_printed_m"] == -1.384
    assert "rule 3" in e["correction"]["rule"] and "derived_figure_m" not in e["correction"]
    assert [r["reader"] for r in e["readings"]] == ["L4", "Z12"] and all(r["figure_m"] == pytest.approx(1.094) for r in e["readings"])
    assert [t["term"] for t in e["cohort_cells"]["terms"]] == [560.0, 534.0]
    d = mature["3330_2017"]
    assert d["figure_m"] == pytest.approx(0.559) and d["displaced"]["by"] == "accounts_roll_forward"
    assert d["displaced"]["figure_m"] == pytest.approx(-0.99)
    assert d["correction"]["derived_figure_m"] == pytest.approx(0.559) and "DERIVED" in d["correction"]["derivation"]
    assert d["correction"]["cells_used"] == ["14,059", "559", "2,270", "647", "11,701"]
    assert 11701 - 14059 + 2270 + 647 == 559
    for r in d["readings"]:
        assert r["derived_figure_m"] == pytest.approx(0.559) and r["figure_m"] == pytest.approx(-0.99), r["reader"]
        assert set(d["correction"]["cells_used"]) <= set(r["cells_quoted"]), r["reader"]
    # the loader carries them: GBP, so no exchange conversion
    prim = loaded[ra.MATURE_COHORT_OUTCOME]["by_key"]
    assert prim["3330_2018"]["pyd_gbp_m"] == pytest.approx(1.094) and prim["3330_2017"]["pyd_gbp_m"] == pytest.approx(0.559)
    assert prim["3330_2018"]["pyd_basis_source"] == prim["3330_2017"]["pyd_basis_source"] == "mature-cohort-figure:register"
    assert prim["3330_2018"]["opening_reserves_gbp_m"] == pytest.approx(11.701)
    assert prim["3330_2017"]["opening_reserves_gbp_m"] == pytest.approx(14.059)
    # 3330/2017 is on the least-certain list (derived_correction); 3330/2018 is a rule-3 correction and is not
    assert _register()["history_restated"]["3330_2017"]["clauses"] == ["derived_correction"]
    assert "3330_2018" not in _register()["history_restated"]


def test_1609_2024_is_back_at_the_printed_figure_with_the_reversal_and_the_earlier_readings_recorded(loaded):
    mature = ra.load_mature_cohort_figures()
    assert "1609_2024" not in mature
    with io.open(os.path.join(HERE, "data", "mature_cohort_figures.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    rev = raw["_reversed_corrections"]["1609_2024"]
    assert rev["was"]["figure_m"] == 13.935 and rev["now"]["figure_m"] == -0.185 and rev["now"]["figure_at_t_minus_3_m"] == -11.123
    assert "36.2%" in rev["reason"] and "49.6%" in rev["reason"]
    assert any(x.endswith("Z9.json") for x in rev["readings"]) and any(x.endswith("Z10.json") for x in rev["readings"])
    assert [x.rsplit("/", 1)[1] for x in rev["was"]["readings_kept"]] == ["P3.json", "Q2.json", "Z5.json", "Z6.json"]
    r = loaded[ra.MATURE_COHORT_OUTCOME]["by_key"]["1609_2024"]
    assert r["pyd_basis_source"] == "triangle-route:gross" and r["data_quality_tag"] == "RELIABLE"
    rate = ra.FX_RATES[2024]["usd_per_gbp"]
    assert r["pyd_gbp_m"] == pytest.approx(-0.185 / rate, abs=1e-6)
    e = _register()["history_restated"]["1609_2024"]
    assert e["clauses"] == ["orientation_outside_evidence"] and [x["reader"] for x in e["census_readings"]] == ["Z9", "Z10"]
    assert [x["reader"] for x in e["readings"]] == ["P3", "Q2", "Z5", "Z6"]
    assert "REVERSED" in e["facts"] and "49.6% to 36.2%" in e["facts"]
    # the readings the reversal rests on: both round-10 readers read the as-labelled orientation and M = -185 (USD 000)
    for rid in ("Z9", "Z10"):
        with io.open(os.path.join(ROUND9, "readings", rid + ".json"), encoding="utf-8") as fh:
            assert json.load(fh)["1609_2024"]["verdict"] == "as_labelled"
    # 1609/2023 (+8.834m, transposed) is confirmed and unchanged
    assert ra.load_pyd_confirmed_figures()["1609_2023"]["figure_m"] == 8.834


def test_the_census_figure_changes_move_only_three_records_and_no_r_in_the_working_sample(loaded):
    """On fixed inputs (the loader against the committed model/exposure_results.json, the loader's output at 9c227e7a):
    of the 632 records that remain in the working sample, exactly 1609/2024, 3330/2017 and 3330/2018 change their figure, and
    no record's R changes."""
    with io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8") as fh:
        old = {"%s_%s" % (o["syndicate"], o["year"]): o for o in json.load(fh)["observations"]}
    prim = loaded[ra.MATURE_COHORT_OUTCOME]["by_key"]
    moved, r_moved = [], []
    for k in sorted(_ws(loaded[ra.MATURE_COHORT_OUTCOME]["records"])):
        n, o = prim[k], old[k]
        if abs(n["pyd_gbp_m"] - o["pyd_gbp_m"]) > 1e-9:
            moved.append(k)
        if abs(n["opening_reserves_gbp_m"] - o["opening_reserves_gbp_m"]) > 1e-9:
            r_moved.append(k)
    assert moved == ["1609_2024", "3330_2017", "3330_2018"] and r_moved == []


# --- the rule-4b scan, the take-on bases, the outbound register and the least-certain list (census follow-ups) ----------------

def test_2488_2016_is_answered_on_incurred_and_the_scan_answers_follow_the_stated_incurred_miss():
    """2488/2016's (ii) was answered 'no' on a paid bridge although both readings give an implied incurred miss of +59.5%;
    incurred first, (ii) holds. (i) is no (no reading quotes a paid cell falling), so rule 4b does not reach the record and
    no outcome moves. The check generalises: for EVERY scan answer that begins yes or no and states an incurred miss, (ii)
    is yes exactly when the miss is over 10% in absolute value."""
    with io.open(str(rb.RULE_4B_SCAN), encoding="utf-8") as fh:
        scan = json.load(fh)
    reads = rb.load_readings()
    a = scan["read"]["2488_2016"]
    assert a["ii"].startswith("yes") and "+59.5%" in a["ii"] and a["i"].startswith("no")
    assert [_incurred_t(r) for _rid, r in reads["2488_2016"]] == [59.5, 59.5]
    assert a["outcome"] == "unchanged: rule 6, least certain" and "2488_2016" not in scan["decides"]
    adj = _register()["_adjudicated"]
    assert adj["2488_2016"]["outcome"] == "least_certain" and "2488_2016" in _register()["history_restated"]
    # the generalisation, over every answer that states an incurred miss in the form 'incurred ... +x%'
    checked = []
    for k, ans in scan["read"].items():
        ii = ans.get("ii")
        m = re.search(r"incurred[^%]*?([+-]\d+(?:\.\d+)?)%", ii or "")
        if not m or _scan_answer(ii) not in (True, False):
            continue
        checked.append(k)
        assert _scan_answer(ii) is (abs(float(m.group(1))) > 10.0), (k, ii[:80])
    assert "2488_2016" in checked and "2232_2017" in checked and len(checked) >= 15, checked


#: the eight take-on bases the census readings were checked against (rule 5): the amount both readings print and the page
TAKEON_BASE_CHECK = {
    "4444_2018": ("277,329", 277.329, 42, ("K5", "L5")), "4444_2023": ("313,953", 313.953, 45, ("K5", "L5")),
    "3268_2020": ("20,660", 20.66, 30, ("K5", "L5")), "4000_2022": ("181,247", 181.247, 37, ("K6", "L6")),
    "1856_2024": ("96,610", 96.61, 101, ("K4", "L4")), "1686_2021": ("903,214", 903.214, 25, ("K3", "L3")),
    "2488_2019": ("143,759", 143.759, 51, ("K3", "L3")), "3500_2019": ("552,752", 552.752, 30, ("K3", "L3")),
}


def test_the_eight_take_on_bases_hold_the_amounts_and_pages_both_census_readings_print():
    """Rule 5 (R includes the acquired book where the table shows it as if always), checked against the census readings: each
    of the eight records is in data/opening_reserves_takeon_base.json with the amount both readings print (their text carries
    the figure as printed) and the page they cite; the record's R is the filing's opening reserves plus that amount, so no
    record's R changes with the census."""
    base = ra.load_takeon_base()
    for k, (printed, amount, page, readers) in TAKEON_BASE_CHECK.items():
        e = base[k]
        assert e["takeon_m"] == pytest.approx(amount) and page in e["pages"], k
        texts = []
        for rid in readers:
            with io.open(os.path.join(ROUND9, "readings", rid + ".json"), encoding="utf-8") as fh:
                texts.append(json.dumps(json.load(fh)[k], ensure_ascii=False))
        # as printed in thousands, or to one decimal in millions (a reader may round: 903,214 is '903.2m')
        prints = [printed in t or ("%.1fm" % amount) in t or ("%.1f" % amount) in t for t in texts]
        assert any(prints), (k, printed)
        if not all(prints):
            # 1686/2021: only K3 prints the RITC amount; L3 measures M on "the RITC-inclusive base" without printing it
            assert k == "1686_2021" and prints == [True, False] and "RITC-inclusive base" in texts[1], (k, prints)
            assert e["opening_reserves_m"] + e["takeon_m"] == pytest.approx(2076.819)
        assert e["opening_reserves_m"] > 0
    # a control: a wrong amount would not be in the readings
    with io.open(os.path.join(ROUND9, "readings", "K5.json"), encoding="utf-8") as fh:
        assert "277,330" not in json.dumps(json.load(fh)["4444_2018"])


def test_the_outbound_register_settles_the_named_amounts_and_marks_33_not_an_outbound_transfer():
    with io.open(os.path.join(HERE, "data", "outbound_transfer_retained_base.json"), encoding="utf-8") as fh:
        reg = json.load(fh)
    named = reg["named_not_adjusted"]
    for k, amount, page, readers in (("6103_2015", 4.25, 41, ("K7", "L7")), ("6103_2023", 7.172, 52, ("K7", "L7")),
                                     ("3334_2018", 37.982, 34, ("K6", "L6"))):
        e, res = named[k], named[k]["census_resolution"]
        assert (e["amount_m"] if "amount_m" in e else e["amount_gbp_m"]) == amount and res["amount_m"] == amount, k
        assert res["page"] == page == e["page"], k
        assert [x.rsplit("/", 1)[1][:-5] for x in res["readings"]] == list(readers), k
        assert res["decision"].startswith("decision of the Claude analysis session, 26 October 2026"), k
        printed = "{:,.0f}".format(amount * 1000)
        for rid in readers:
            with io.open(os.path.join(ROUND9, "readings", rid + ".json"), encoding="utf-8") as fh:
                assert printed in json.dumps(json.load(fh)[k], ensure_ascii=False), (k, rid, printed)
        assert k not in reg["confirmed"], k
    # the 1 January 2023 date of 6103/2023 rests on one reading (K7), so the entry is not moved to confirmed
    assert "K7 alone dates it" in named["6103_2023"]["census_resolution"]["facts"]
    for k in ("33_2021", "33_2022", "33_2023", "33_2024"):
        e = named[k]
        assert e["not_an_outbound_transfer"] is True and e["counterparty"] == "6104", k
        assert "quota share" in e["census_resolution"]["facts"] and "not an RITC counterparty" in e["census_resolution"]["facts"], k
        with io.open(os.path.join(ROUND9, "readings", "K5.json"), encoding="utf-8") as fh:
            assert "quota-share reinsurer" in json.dumps(json.load(fh)[k], ensure_ascii=False), k


def test_the_least_certain_list_is_derived_from_the_register_and_follows_the_census():
    """check_low_confidence_sensitivity derives the list from the register (never typed): after the census it holds 6118/2018,
    1110/2020, 3330/2017, 1609/2024 and, under rule 6's 1%-of-R clause, 1254/2023 and 1686/2021; 3000/2016, 3500/2022 and
    3500/2023 left it for the excluded set."""
    import check_low_confidence_sensitivity as LC
    import sample_scope as SS
    reg = _register()
    out = LC.restated_records(reg)
    listed = set(out)
    assert {"6118_2018", "1110_2020", "3330_2017", "1609_2024", "1254_2023", "1686_2021"} <= listed
    assert not listed & {"3000_2016", "3500_2022", "3500_2023"} and not listed & set(SET_ASIDE)
    assert sorted(listed) == sorted(reg["history_restated"]) and len(listed) == 31
    # why each census listing is listed: the clause and the facts the entry states
    for k, clause in (("1110_2020", "census_residual_concern"), ("1254_2023", "census_residual_concern"),
                      ("1686_2021", "census_residual_concern"), ("3330_2017", "derived_correction"),
                      ("1609_2024", "orientation_outside_evidence")):
        assert clause in out[k], k
    # the 1%-of-R clause: 1254/2023's restated base (about 23m) against R 55.574m (GBP), and 1686/2021's 2018 row (110m
    # at least) against the take-on-inclusive R of 2,076.8m USD; both over 1%
    assert 23.0 / 55.574 > 0.01 and 110.0 / 2076.819 > 0.01
    assert "1%-of-R" in reg["history_restated"]["1254_2023"]["facts"] or "over 1%" in reg["history_restated"]["1254_2023"]["facts"]
    assert "over rule 6's 1% of R" in reg["history_restated"]["1686_2021"]["facts"]
    assert SS.order_key("1110_2020") < SS.order_key("1254_2023")
