r"""The exchange-rate rule of the primary sample (the author's decision of 22 October 2026, rule B).

A record leaves the primary sample when (a) its development table is not retranslated between the year t-1 and year t
reports across a sterling/dollar move of 5% or more, and (b) the filing's own gross claims-outstanding roll-forward
prints an exchange line of at least 5% of the opening gross claims outstanding. data/fx_untranslated_excluded.json holds
the four records both conditions hold for (2468/2016, 5151/2016, 5151/2017, 1897/2016), the nine candidates two
readers (F1, F2) found to fail a condition and, from round 2 (23 October 2026), 97 more two readers (an X-arm and a
Y-arm reader) read and kept, four of them as undeterminable; src/build_fx_untranslated_excluded.py builds it from the
archived readings.
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
#: round 5 (23 October 2026): rule 2 of the round-5 decision rules (the author's rule B) on the readings P2 and Q1
ROUND5 = {"3000_2022": 8.01}
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


def test_the_register_holds_the_four_excluded_and_the_read_and_kept():
    reg = _register()
    round2 = set(reg["_population"]["round2"]["records_are"])
    assert set(reg["excluded"]) == set(EXCLUDED) | set(ROUND5) and set(reg["read_and_kept"]) == set(KEPT) | round2
    assert len(round2) == 97 and not round2 & (set(KEPT) | set(EXCLUDED))
    for bucket, want in (("excluded", EXCLUDED), ("read_and_kept", KEPT)):
        for key, pct in want.items():
            e = reg[bucket][key]
            assert e["fx_line_pct_of_opening"] == pct, key
            assert [r["reader"] for r in e["readings"]] == ["F1", "F2"], key
    for key, pct in ROUND5.items():
        e = reg["excluded"][key]
        assert e["fx_line_pct_of_opening"] == pct and [r["reader"] for r in e["readings"]] == ["P2", "Q1"], key
    assert reg["_population"]["round5"]["records_excluded"] == sorted(ROUND5)
    assert ra.load_fx_untranslated_excluded().keys() == set(EXCLUDED) | set(ROUND5)
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


def test_the_round_5_entry_rests_on_verbatim_snippets_of_both_readings():
    """3000/2022: each reading's R, exchange line and page are snippets of the archived round-5 reading, both readers give
    the same figures, the line is 8.0% of R, and the table is not retranslated (its history is, its end-2021 reserves are
    not); the readers' own verdict is kept beside the rule's."""
    e = _register()["excluded"]["3000_2022"]
    assert e["opening_gross_claims_outstanding_m"] == 1146.474 and e["fx_line_gross_m"] == 91.879
    assert e["table_retranslated"] is False and "rule B" in e["decision"]
    for r in e["readings"]:
        with io.open(os.path.join(HERE, *r["source"].split("/")), encoding="utf-8") as fh:
            text = json.dumps(json.load(fh)["3000_2022"], ensure_ascii=False)
        for field in ("opening_gross_claims_outstanding", "fx_line_gross"):
            assert r[field]["quote"] in text, (r["reader"], field)
        assert r["cells_compared"] in text and r["table_exchange_basis"] in text, r["reader"]
        assert r["reader_verdict"] == "restated_base" and r["verdict"] == "exclude"
    ev = bf.build_evidence()
    assert set(ev["excluded"]["3000_2022"]["mixed_base_cells"]) == {"P2", "Q1"}


@pytest.mark.parametrize("field,old,new", [("opening", "1,146,474'", "1,146,475'"), ("fx_line", "91,879'", "91,897'")])
def test_the_round_5_build_refuses_a_snippet_that_is_not_the_readers(monkeypatch, field, old, new):
    """Mutation check: a snippet edited away from the archived reading stops the build."""
    snip = json.loads(json.dumps(bf.ROUND5_SNIPPETS))
    page, quote, fig = snip["3000_2022"]["P2"][field]
    snip["3000_2022"]["P2"][field] = [page, quote.replace(old, new), fig.replace(old.rstrip("'"), new.rstrip("'"))]
    monkeypatch.setattr(bf, "ROUND5_SNIPPETS", snip)
    with pytest.raises(SystemExit, match="snippet is not in the archived reading"):
        bf.build_all()


def test_the_round_5_build_refuses_readers_who_disagree_on_the_line(monkeypatch):
    snip = json.loads(json.dumps(bf.ROUND5_SNIPPETS))
    page, quote, fig = snip["3000_2022"]["Q1"]["fx_line"]
    snip["3000_2022"]["Q1"]["fx_line"] = [page, quote, "1,146,474"]
    monkeypatch.setattr(bf, "ROUND5_SNIPPETS", snip)
    with pytest.raises(SystemExit, match="disagree on R or the exchange line"):
        bf.build_all()


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
    assert set(ra.load_fx_untranslated_excluded(p)) == set(EXCLUDED) | set(ROUND5)


def test_a_record_cannot_be_both_excluded_and_kept(tmp_path):
    reg = _register()
    reg["read_and_kept"]["2468_2016"] = copy.deepcopy(reg["read_and_kept"]["2468_2017"])
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="2468_2016"):
        ra.load_fx_untranslated_excluded(p)


# --- round 2 (23 October 2026): 97 records read twice by an X-arm and a Y-arm reader, all kept -----------------------

def _round2_archive():
    """{key: [(reader, entry), ...]} straight from the archived round-2 readings (not from the register)."""
    out = {}
    for arm in "XY":
        for i in range(1, 9):
            rid = "%s%d" % (arm, i)
            with io.open(os.path.join(str(bf.ROUND2), "readings", "%s.json" % rid), encoding="utf-8") as fh:
                for name, e in json.load(fh).items():
                    if name.endswith("|exchange_line"):
                        out.setdefault(e["key"], []).append((rid, e))
    return out


def _comparison_in_archive(raw):
    """True when an archived round-2 reading's own retranslation check compared cells of the two reports (its `checked`
    is true or begins 'yes')."""
    c = (raw.get("retranslation") or {}).get("checked")
    return c is True or (isinstance(c, str) and c.strip().lower().startswith("yes"))


def test_round_2_keeps_all_97_and_records_the_reason_each_reading_gives():
    """Driven by the archived readings, not by the register: the 97 records have one X-arm and one Y-arm reading each,
    no reader says exclude, the reason follows the readers' own figures (no line, under 5% of R, or 5% or more with the
    table retranslated or not testable), and the four undeterminable records are those the Claude analysis session named."""
    reg = _register()
    arch = _round2_archive()
    assert len(arch) == 97 == bf.ROUND2_RECORDS
    reasons = {}
    for key, pairs in arch.items():
        assert sorted(p[0][0] for p in pairs) == ["X", "Y"], key
        assert all(e["verdict"] in ("keep", "undeterminable") for _r, e in pairs), key
        lines = [e["fx_line"]["value_m"] if isinstance(e["fx_line"], dict) else None for _r, e in pairs]
        opens = [e["R"]["value_m"] for _r, e in pairs]
        assert abs(opens[0] - opens[1]) <= 0.0015, key
        e = reg["read_and_kept"][key]
        if lines[0] is None:
            assert lines[1] is None and e["reason"] == "no_fx_line_printed", key
        else:
            assert abs(abs(lines[0]) - abs(lines[1])) <= 0.0015, key
            pct = abs(lines[0]) / opens[0] * 100
            if pct < 5.0:
                assert e["reason"] == "fx_line_under_5pct", key
            elif (any(x["verdict"] == "undeterminable" for _r, x in pairs)
                  or not all(_comparison_in_archive(x) for _r, x in pairs)):
                # derived here from the archived readings' own verdicts and checks, not from the builder's functions
                assert e["reason"] == "undeterminable_kept", key
            else:
                assert e["reason"] == "table_retranslated" and all(p[1]["verdict"] == "keep" for p in pairs), key
        reasons[e["reason"]] = reasons.get(e["reason"], 0) + 1
    assert reasons == {"fx_line_under_5pct": 78, "no_fx_line_printed": 5, "table_retranslated": 10,
                       "undeterminable_kept": 4}
    assert reg["_population"]["round2"]["reasons"] == reasons
    # the pin is intended: these are the four records the readers' verdicts and checks leave undeterminable
    undet = sorted(k for k, e in reg["read_and_kept"].items() if e.get("reason") == "undeterminable_kept")
    assert set(undet) == {"457_2015", "1301_2015", "4711_2017", "6105_2015"}
    assert set(reg["_population"]["round2"]["undeterminable_kept"]) == set(undet) == set(bf.UNDETERMINABLE_NOTE)
    for key in undet:
        e = reg["read_and_kept"][key]
        assert abs(e["fx_line_pct_of_opening"]) >= 5.0 and e["table_retranslated"] is None, key
        assert e["decision"].startswith("decision of the Claude analysis session, 23 October 2026"), key
        assert e["session_decision"].strip(), key
    for key, e in reg["read_and_kept"].items():
        if e.get("reason") == "table_retranslated":
            assert e["table_retranslated"] is True and abs(e["fx_line_pct_of_opening"]) >= 5.0, key
    assert not any(e["decision"].startswith("excluded") for e in reg["read_and_kept"].values())


def test_every_round_2_reading_carries_its_pages_and_a_quote_for_r_and_the_line():
    reg = _register()
    for key in reg["_population"]["round2"]["records_are"]:
        e = reg["read_and_kept"][key]
        assert e["pages"] and e["quote"].strip() and len(e["readings"]) == 2, key
        assert sorted(r["reader"][0] for r in e["readings"]) == ["X", "Y"], key
        for r in e["readings"]:
            assert r["pages"] and all(isinstance(p, int) and p >= 1 for p in r["pages"]), (key, r["reader"])
            for cell in ("opening_gross_claims_outstanding", "fx_line_gross"):
                assert r[cell]["quote"].strip(), (key, r["reader"], cell)
            assert isinstance(r["opening_gross_claims_outstanding"]["page"], int), key
            if e["fx_line_gross_m"] is not None:
                assert isinstance(r["fx_line_gross"]["page"], int), key
                assert abs(abs(r["fx_line_gross"]["value_m"]) - abs(e["fx_line_gross_m"])) <= 0.0015, key


def test_the_two_sign_conventions_are_recorded_beside_the_reading_that_differs():
    """1225/2015 and 727/2015: one reader prints the line as a liability (negative) and the other positive; the entry
    takes the X reader's sign and the Y reading keeps the value it read."""
    reg = _register()
    for key in ("1225_2015", "727_2015"):
        e = reg["read_and_kept"][key]
        y = [r for r in e["readings"] if r["reader"][0] == "Y"][0]["fx_line_gross"]
        assert y["printed_value_m"] == -e["fx_line_gross_m"] and y["value_m"] == e["fx_line_gross_m"], key
        assert "opposite sign" in y["sign_note"]


@pytest.mark.parametrize("key,change", [
    ("1301_2016", "retranslated-flag-false"), ("1301_2016", "retranslated-flag-missing"),
    ("1301_2016", "line-under-5pct"), ("1301_2016", "reader-says-undeterminable"),
    ("1301_2016", "reader-says-exclude"),
    ("457_2015", "flag-true"), ("457_2015", "line-under-5pct"), ("457_2015", "reader-says-exclude"),
    ("457_2015", "reader-says-nonsense"), ("1084_2015", "reason-undeterminable-with-small-line")])
def test_the_loader_refuses_a_round_2_kept_entry_without_its_evidence(tmp_path, key, change):
    """Mutation check on the two new reasons: each change makes the loader name the record."""
    reg = _register()
    e = reg["read_and_kept"][key]
    if change == "retranslated-flag-false":
        e["table_retranslated"] = False
    elif change == "retranslated-flag-missing":
        del e["table_retranslated"]
    elif change == "line-under-5pct":
        e["fx_line_gross_m"] = 0.01 * e["opening_gross_claims_outstanding_m"]
        e["fx_line_pct_of_opening"] = 1.0
        for r in e["readings"]:
            r["fx_line_gross"]["value_m"] = e["fx_line_gross_m"]
    elif change == "reader-says-undeterminable":
        e["readings"][0]["verdict"] = "undeterminable"      # allowed only for undeterminable_kept
    elif change == "reader-says-exclude":
        e["readings"][0]["verdict"] = "exclude"
    elif change == "flag-true":
        e["table_retranslated"] = True
    elif change == "reader-says-nonsense":
        e["readings"][0]["verdict"] = "probably"
    else:
        e["reason"] = "undeterminable_kept"
        e["table_retranslated"] = None
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match=key):
        ra.load_fx_untranslated_excluded(p)
    p.write_text(json.dumps(_register()), encoding="utf-8")
    assert set(ra.load_fx_untranslated_excluded(p)) == set(EXCLUDED) | set(ROUND5)


# --- the loader ----------------------------------------------------------------------------------------------------------

def test_the_primary_removes_the_five_records_with_a_named_countable_reason(loaded):
    prim, old = loaded[ra.MATURE_COHORT_OUTCOME], loaded[ra.PRECEDENCE_672_OUTCOME]
    for key in list(EXCLUDED) + list(ROUND5):
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
    assert prim["counters"]["fx_untranslated_excluded"] == 5
    assert sum(1 for r in prim["records"] if r["data_quality_tag"] == ra.FX_UNTRANSLATED_TAG) == 5
    out = set(EXCLUDED) | set(ROUND5)
    assert out - {"5151_2016"} <= _ws(old["records"]) and not out & _ws(prim["records"])


def test_the_kept_candidates_stay_in_the_primary(loaded):
    ws = _ws(loaded[ra.MATURE_COHORT_OUTCOME]["records"])
    for key in KEPT:
        assert key in ws, key
    # round 2: the 97 records read twice and kept, the four undeterminable ones among them, are in the primary's sample,
    # unless another rule takes them out: 4242/2022 was excluded under rule 1 of the round-5 decision rules (its exchange
    # line is under 5% of R, so rule B keeps it; data/restated_base_excluded.json excluded it) until review 8 moved it to
    # rule 3, a corrected figure (data/mature_cohort_figures.json), so it is in the primary's sample again and no
    # kept record is in the restated-base register's excluded bucket
    prim = loaded[ra.MATURE_COHORT_OUTCOME]
    restated = ra.load_restated_base()
    for key in _register()["_population"]["round2"]["records_are"]:
        if key in restated:
            assert prim["by_key"][key]["data_quality_tag"] == ra.RESTATED_BASE_TAG, key
            continue
        assert key in ws, key
    assert sorted(set(restated) & set(_register()["read_and_kept"])) == []
    assert "4242_2022" in ws and "4242_2022" in _register()["read_and_kept"]


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
    """A register that claims an exclusion the loader did not make stops the run when the filing is in the corpus: here
    a record in run-off, which never reaches the exclusion step. An entry whose filing is not in the corpus read has
    nothing to exclude and is not an error (a smaller corpus, or a test's synthetic one)."""
    real = ra.load_fx_untranslated_excluded()
    extra = dict(real)
    extra["1206_2019"] = real["2468_2016"]
    monkeypatch.setattr(ra, "load_fx_untranslated_excluded", lambda path=None, e=extra: e)
    with pytest.raises(ValueError, match="1206_2019"):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)
    extra = dict(real)
    extra["9999_2020"] = real["2468_2016"]
    monkeypatch.setattr(ra, "load_fx_untranslated_excluded", lambda path=None, e=extra: e)
    records, counters, log, files = ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)
    assert counters["fx_untranslated_excluded"] == 5


def test_a_non_gross_or_take_on_record_the_register_names_stops_the_run(monkeypatch):
    """An entry for a record that reaches the exclusion step but is not a reliable gross record of the primary (here
    1218/2015, on a net basis) stops the run at that step."""
    real = ra.load_fx_untranslated_excluded()
    extra = dict(real)
    extra["1218_2015"] = real["2468_2016"]
    monkeypatch.setattr(ra, "load_fx_untranslated_excluded", lambda path=None, e=extra: e)
    with pytest.raises(ValueError, match="1218_2015"):
        ra.load_and_classify(ra.MATURE_COHORT_OUTCOME)


def test_the_register_is_a_hashed_raw_byte_input():
    assert str(ra.FX_UNTRANSLATED_REGISTER) in ra.source_files_for_hash([])
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/fx_untranslated_excluded.json -text" in fh.read().splitlines()


# --- every register key names a real filing (review of 23 October 2026, l1) ----------------------------------------

def _keys_without_a_file(entries, data_dir=None):
    """The register's keys (excluded and read_and_kept) with no extraction file `syndicate_<key>.json` in the corpus."""
    data_dir = ra.DATA_DIR if data_dir is None else data_dir
    return sorted(k for k in entries if not os.path.isfile(os.path.join(str(data_dir), "syndicate_%s.json" % k)))


def test_every_key_of_the_register_has_its_extraction_file():
    """The loader's stale-entry guard looks only at entries whose filing is in the corpus read, so a mistyped key (a
    wrong syndicate or year) would be ignored on the real corpus. This test closes that: on the committed corpus every
    key of both buckets is a filing that exists."""
    reg = _register()
    keys = list(reg["excluded"]) + list(reg["read_and_kept"])
    assert len(keys) == 111 and len(set(keys)) == 111      # 4 excluded and 9 kept in round 1, 97 kept in round 2,
    #                                                          1 excluded in round 5
    assert _keys_without_a_file(keys) == []
    assert set(ra.load_fx_untranslated_excluded()) == set(reg["excluded"])      # the loader applies the excluded bucket
    for k in keys:
        assert os.path.isfile(os.path.join(str(ra.DATA_DIR), "syndicate_%s.json" % k)), k


@pytest.mark.parametrize("bucket,old,new", [("excluded", "1897_2016", "1897_2061"),
                                            ("excluded", "5151_2017", "5152_2017"),
                                            ("read_and_kept", "4242_2018", "4242_2081")])
def test_a_renamed_key_in_a_temp_copy_of_the_register_is_found_to_have_no_file(tmp_path, bucket, old, new):
    """Mutation check on the test above: the register with one key renamed to a filing that does not exist is caught
    by the same helper, in either bucket."""
    reg = copy.deepcopy(_register())
    reg[bucket][new] = reg[bucket].pop(old)
    path = tmp_path / "fx_untranslated_excluded.json"
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(reg, indent=1) + "\n")
    with io.open(str(path), encoding="utf-8") as fh:
        copied = json.load(fh)
    keys = list(copied["excluded"]) + list(copied["read_and_kept"])
    assert _keys_without_a_file(keys) == [new]


# --- the kept reason is derived from the readers' verdicts and checks (review of 23 October 2026, minor 1) ------------

def _reads_of(key):
    """The two round-2 readings of a record in the register's form, rebuilt from the archived readings."""
    pairs = sorted(_round2_archive()[key], key=lambda p: p[0])
    return [bf.reading_r2(rid, key, e) for rid, e in pairs]


def _kept_entry(key, reads):
    return bf.entry_r2(key, reads, bf.round2_moves()[key])


def test_the_reason_of_every_line_of_5pct_or_more_follows_the_readers_verdicts_and_checks():
    """For the 14 round-2 records with a line of 5% or more of R: table_retranslated exactly when both readers' checks
    compared cells and show them moved, undeterminable_kept exactly when a reader says undeterminable or a check did not
    compare cells. No typed list is consulted."""
    reg = _register()
    n_moved = n_undet = 0
    for key in reg["_population"]["round2"]["records_are"]:
        e = reg["read_and_kept"][key]
        if e["fx_line_gross_m"] is None or abs(e["fx_line_pct_of_opening"]) < 5.0:
            continue
        reads = e["readings"]
        assert bf.kept_reason(e["fx_line_gross_m"], e["fx_line_pct_of_opening"], reads) == e["reason"], key
        if e["reason"] == "table_retranslated":
            n_moved += 1
            assert all(bf.comparison_made(r["table_retranslated_check"]) for r in reads), key
            assert all((bf.reader_moved_cells(key, reads, r["reader"]) or {}).get("pairs_moved")
                       for r in reads), key
            assert all(r["verdict"] == "keep" for r in reads), key
        else:
            n_undet += 1
            assert e["reason"] == "undeterminable_kept", key
            assert (any(r["verdict"] == "undeterminable" for r in reads)
                    or not all(bf.comparison_made(r["table_retranslated_check"]) for r in reads)), key
    assert (n_moved, n_undet) == (10, 4)


def test_a_table_retranslated_entry_needs_each_readers_check_to_show_moved_cells():
    """Mutation check: 1301/2016 with one reader's check giving no cells that moved stops the build, for either reader,
    whatever the check or the note says."""
    key = "1301_2016"
    assert _kept_entry(key, _reads_of(key))["reason"] == "table_retranslated"
    for which in (0, 1):
        for check, note in (({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40", "result": "cells not moved"}, ""),
                            ({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40"}, "the table is not retranslated"),
                            ({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40",
                              "result": "moved (retranslated): every cell is 3 to 6% lower"}, "the cells moved"),
                            ({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40"}, "")):
            reads = _reads_of(key)
            reads[which]["table_retranslated_check"], reads[which]["note"] = check, note
            with pytest.raises(SystemExit, match=key):
                _kept_entry(key, reads)


def test_the_reason_undeterminable_kept_is_derived_not_typed(monkeypatch):
    """Mutation check: 457/2015 read with both checks comparing cells that moved is table_retranslated (the reasons follow
    the readings, not a list of keys), and 1301/2016 with a check that compared no cells is undeterminable and, having no
    note of the session's, stops the build."""
    reads = _reads_of("457_2015")
    assert _kept_entry("457_2015", reads)["reason"] == "undeterminable_kept"
    for r in reads:
        r["verdict"] = "keep"
        r["table_retranslated_check"] = {
            "checked": True,
            "cells_t": "p45 UY2011 one year later 250,000; UY2012 one year later 260,000; UY2013 one year later 270,000",
            "cells_t_minus_1": "p45 UY2011 one year later 229,609; UY2012 one year later 239,000; UY2013 one year later 249,000"}
    # without the cells in MOVED_CELLS the build stops; with them the record is table_retranslated
    with pytest.raises(SystemExit, match="457_2015"):
        _kept_entry("457_2015", reads)
    cells = {"pages": (45, 45), "pairs": tuple(
        (uy, 1, "", a, "UY%s one year later %s" % (uy, a), b, "UY%s one year later %s" % (uy, b))
        for uy, a, b in (("2011", "250,000", "229,609"), ("2012", "260,000", "239,000"), ("2013", "270,000", "249,000")))}
    monkeypatch.setitem(bf.MOVED_CELLS, ("457_2015", reads[0]["reader"]), cells)
    monkeypatch.setitem(bf.MOVED_CELLS, ("457_2015", reads[1]["reader"]), cells)
    assert _kept_entry("457_2015", reads)["reason"] == "table_retranslated"
    # no reader says undeterminable, but neither compared cells (no year t-1 table): condition (a) cannot be tested
    reads = _reads_of("457_2015")
    for r in reads:
        r["verdict"] = "keep"
        r["table_retranslated_check"] = {"checked": "partly", "cells_t_minus_1": "none: no 2014 development table",
                                         "result": "moved (retranslated)"}
    assert _kept_entry("457_2015", reads)["reason"] == "undeterminable_kept"
    reads = _reads_of("1301_2016")
    reads[0]["table_retranslated_check"] = {"checked": False, "cells_t_minus_1": "none: no 2015 table"}
    with pytest.raises(SystemExit, match="1301_2016"):
        _kept_entry("1301_2016", reads)
    reads = _reads_of("1301_2016")
    reads[1]["verdict"] = "undeterminable"
    with pytest.raises(SystemExit, match="1301_2016"):
        _kept_entry("1301_2016", reads)


def test_the_build_refuses_notes_that_are_not_the_derived_records(monkeypatch):
    """The session's notes and the derived undeterminable records must be the same four."""
    monkeypatch.setattr(bf, "UNDETERMINABLE_NOTE", {k: v for k, v in bf.UNDETERMINABLE_NOTE.items() if k != "6105_2015"})
    with pytest.raises(SystemExit):
        bf.build()


#: phrases a reader's prose may hold that a pattern on the words 'moved' and 'retranslated' could read as moved cells
#: (review of 23 October 2026, minor 1); the build never reads prose, so none of them can support a retranslated table
PROSE = ["isn't retranslated", "the table wasn't retranslated", "nothing moved", "nothing was retranslated",
         "none of the cells moved", "neither column moved", "No cell in the table has moved",
         "identical rather than moved", "had not, on this reading, been retranslated",
         "if the table had been retranslated the cells would have moved", "the table is not retranslated",
         "no cells moved between the reports", "cells equal in both reports",
         "moved (retranslated): every cell is 3 to 6% lower", "Cells moved: UY2011 age 1 is 57.8 vs 61.5", ""]

_T = ("2016 p40 gross, GBP m: UY2011 at end of underwriting year 65.0, one year later 57.8, two years later 56.0; "
      "UY2012 at end of underwriting year 40.0, one year later 50.2")
_T1 = ("2015 p41 gross, GBP m: UY2011 at end of underwriting year 66.0, one year later 61.5, two years later 60.1; "
       "UY2012 at end of underwriting year 44.0, one year later 50.1")
_CHECK = {"checked": True, "cells_t": _T, "cells_t_minus_1": _T1,
          "note": "Only two underwriting years precede the year t-1 in this table, so there are two cells for UY2011"}
_EVIDENCE = {"pages": (40, 41), "pairs": (
    ("2011", 1, "", "57.8", "UY2011 at end of underwriting year 65.0, one year later 57.8",
     "61.5", "UY2011 at end of underwriting year 66.0, one year later 61.5"),
    ("2011", 2, "", "56.0", "UY2011 at end of underwriting year 65.0, one year later 57.8, two years later 56.0",
     "60.1", "UY2011 at end of underwriting year 66.0, one year later 61.5, two years later 60.1"),
    ("2012", 1, "", "50.2", "UY2012 at end of underwriting year 40.0, one year later 50.2",
     "50.1", "UY2012 at end of underwriting year 44.0, one year later 50.1"))}
_MOVED = [("2011", 1, "57.8", "61.5"), ("2011", 2, "56.0", "60.1")]


def _pair(*changes, index=0, evidence=None):
    """_EVIDENCE with the pair at `index` replaced by its fields changed ({position: value})."""
    ev = evidence or _EVIDENCE
    p = list(ev["pairs"][index])
    for pos, val in changes:
        p[pos] = val
    return dict(ev, pairs=ev["pairs"][:index] + (tuple(p),) + ev["pairs"][index + 1:])


@pytest.mark.parametrize("text", PROSE)
def test_no_prose_about_moved_cells_supports_a_retranslated_table(text):
    """Whatever a reader's check or note says in words, a table is shown retranslated only by the cells: with no cells
    given, or cells that do not differ, the phrase supports nothing; with cells that moved, the phrase is not consulted."""
    assert bf.shows_moved_cells({"checked": True, "result": text}, _EVIDENCE) is False
    assert bf.shows_moved_cells({"checked": True, "result": text, "note": text}, None) is False
    identical = dict(_CHECK, cells_t_minus_1=_T.replace("p40", "p41"), result=text)
    same = {"pages": (40, 41), "pairs": tuple(
        (uy, age, "", a, st, a, st) for uy, age, _, a, st, _b, _st1 in _EVIDENCE["pairs"])}
    assert bf.shows_moved_cells(identical, same) is False
    assert bf.shows_moved_cells(dict(_CHECK, result=text), _EVIDENCE) is True
    assert bf.shows_moved_cells(dict(_CHECK, result="the table is not retranslated, nothing moved"), _EVIDENCE) is True


@pytest.mark.parametrize("text", PROSE)
def test_the_build_refuses_a_table_retranslated_record_whose_cells_are_not_given_whatever_the_prose(text):
    """Mutation check on the whole route: 1301/2016 with both readers' checks and notes replaced by the phrase and no
    cells stops the build naming the record."""
    key = "1301_2016"
    reads = _reads_of(key)
    for r in reads:
        r["table_retranslated_check"], r["note"] = {"checked": True, "result": text}, text
    with pytest.raises(SystemExit, match=key):
        _kept_entry(key, reads)


def test_the_cells_must_be_the_readers_own_and_differ_by_more_than_rounding():
    assert bf.moved_cell_pairs(_CHECK, _EVIDENCE) == _MOVED
    # a figure the reader's text does not hold, in either report, or a page or year it does not name
    for field, old, new in (("cells_t", "57.8", "57.9"), ("cells_t_minus_1", "61.5", "61.6"), ("cells_t", "p40", "p4"),
                            ("cells_t_minus_1", "p41", "p14"), ("cells_t", "UY2011", "UY2013"),
                            ("cells_t_minus_1", "UY2012", "UY2014")):
        assert old in _CHECK[field]
        assert bf.moved_cell_pairs(dict(_CHECK, **{field: _CHECK[field].replace(old, new)}), _EVIDENCE) == [], (field, new)
    # a difference of one unit in the last printed place is rounding; two units is not
    for new, expected in (("57.7", _MOVED[1:]), ("57.6", [("2011", 1, "57.8", "57.6")] + _MOVED[1:])):
        ev = dict(_EVIDENCE, pairs=tuple(tuple(x.replace("61.5", new) if isinstance(x, str) else x for x in p)
                                         for p in _EVIDENCE["pairs"]))
        assert bf.moved_cell_pairs(dict(_CHECK, cells_t_minus_1=_T1.replace("61.5", new)), ev) == expected, new
    # thousands separators are not part of the figure; a difference of 1 in a whole number is rounding
    chk = {"checked": True, "cells_t": "p1 UY2015 one year later 3,857; UY2016 one year later 3,100; UY2017 one year later 9",
           "cells_t_minus_1": "p2 UY2015 one year later 3,856; UY2016 one year later 3,100; UY2017 one year later 9"}
    ev = {"pages": (1, 2), "pairs": tuple((uy, 1, "", a, "UY%s one year later %s" % (uy, a), b,
                                           "UY%s one year later %s" % (uy, b))
                                          for uy, a, b in (("2015", "3,857", "3,856"), ("2016", "3,100", "3,100"),
                                                           ("2017", "9", "9")))}
    assert bf.moved_cell_pairs(chk, ev) == []
    chk4 = dict(chk, cells_t_minus_1=chk["cells_t_minus_1"].replace("3,856", "4,202"))
    ev4 = _pair((5, "4,202"), (6, "UY2015 one year later 4,202"), evidence=ev)
    assert bf.moved_cell_pairs(chk4, ev4) == [("2015", 1, "3,857", "4,202")]
    # no pairs, or cells that are not text
    assert bf.moved_cell_pairs(_CHECK, {"pages": (40, 41), "pairs": ()}) == []
    assert bf.moved_cell_pairs(dict(_CHECK, cells_t=["57.8"]), _EVIDENCE) == []
    assert bf.moved_cell_pairs({"checked": True}, _EVIDENCE) == []


# --- a pair ties a figure to its underwriting year and age (review of 23 October 2026, round 4) ------------------------

def _check_of(key, rid):
    return dict(next(e for r, e in _round2_archive()[key] if r == rid)["retranslation"])


def _other_arm(key, rid):
    """The other arm's reading of the record, as moved_cell_pairs takes it (for a list anchored on "other_arm")."""
    (oid,) = [r for (k, r) in bf.MOVED_CELLS if k == key and r != rid]
    return {"key": key, "reader": oid, "check": _check_of(key, oid), "evidence": bf.MOVED_CELLS[(key, oid)]}


def _moved(key, rid, check=None, evidence=None, other=True):
    """moved_cell_pairs for a real entry: the reader's check and MOVED_CELLS entry (or the ones given), the record's key
    and the other arm's reading."""
    return bf.moved_cell_pairs(check if check is not None else _check_of(key, rid),
                               evidence if evidence is not None else bf.MOVED_CELLS[(key, rid)], key,
                               _other_arm(key, rid) if other else None)


def test_identical_tables_with_two_cells_of_one_table_paired_are_refused():
    """Attack 1 of the review: the year t-1 text is the year t text, and the entry pairs two cells of that one table (the
    end of the underwriting year with one year later). Both snippets are the reader's own, in the right text and under
    the right year; the age of the second does not match the pair's, so the entry is refused."""
    check = _check_of("5820_2016", "X3")
    check["cells_t_minus_1"] = check["cells_t"].replace("2016 report p42", "2015 report p25")
    honest = bf.MOVED_CELLS[("5820_2016", "X3")]
    assert _moved("5820_2016", "X3") != []
    assert _moved("5820_2016", "X3", check, honest) == []
    # the pair is repeated to reach three cells: three different cells are needed, not three pairs
    misaligned = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "77.6", "UY2011: end of UY 44.7, one year later 77.6"),) * 3}
    assert _moved("5820_2016", "X3", check, misaligned) == []
    assert bf.moved_cell_pairs(check, dict(misaligned, fewer_because="x")) == []
    # the same cell twice is not a move: the figures are equal
    twice = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "44.7", "UY2011: end of UY 44.7"),) * 3}
    assert _moved("5820_2016", "X3", check, twice) == []
    # a positional side whose place in the list is not the pair's age
    pos = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "66.9",
         {"snippet": "UY2011: 38.7, 66.9", "run_start": "UY2011: ", "first_age": 0, "quote": "end of UY 44.7"}),) * 3}
    assert _moved("5820_2016", "X3", None, pos) == []


def test_cells_of_different_underwriting_years_paired_are_refused():
    """Attack 1b of the review: the 2011 cell of one report paired with the 2014 cell of the other."""
    check = _check_of("5820_2016", "X3")
    check["cells_t_minus_1"] = check["cells_t"].replace("2016 report p42", "2015 report p25")
    other_year = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "15.9",
         {"snippet": "UY2014: 15.9", "run_start": "UY2014: ", "first_age": 0, "quote": "end of UY 44.7"}),) * 3}
    assert bf.moved_cell_pairs(check, other_year) == []
    # one snippet naming two years is refused whichever year the pair states
    two = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "15.9",
         "UY2011: end of UY 44.7, one year later 77.6, two years 65.8, three 63.0, four 64.5; UY2014: 15.9"),) * 3}
    assert bf.moved_cell_pairs(check, two) == []


def test_an_age_label_is_not_a_figure():
    """Attack 2 of the review: the figures '12' and '24' of '12 months' and '24 months' in identical tables."""
    check = _check_of("6119_2016", "Y1")
    check["cells_t_minus_1"] = check["cells_t"]
    labels = {"pages": (31, 31), "pairs": (
        ("2014", 1, "gross", "12", "UY2014: 12", "24", "UY2014: 12 months 5,290; 24"),) * 3}
    assert bf.moved_cell_pairs(check, labels) == []
    # the same, listed by position (the figure is the first value of the list)
    pos = {"pages": (31, 31), "pairs": (
        ("2014", 1, "gross", "12",
         {"snippet": "UY2014: 12", "run_start": "UY2014: ", "first_age": 1, "quote": "12 months 5,290"}, "24",
         {"snippet": "UY2014: 12 months 5,290; 24", "run_start": "UY2014: 12 months 5,290; ", "first_age": 1,
          "quote": "12 months 5,290"}),) * 3}
    assert bf.moved_cell_pairs(check, pos) == []
    plain = {"checked": True, "cells_t": "p1 UY2014: 12 months 5,290", "cells_t_minus_1": "p1 UY2014: 24 months 5,290"}
    first = {"pages": (1, 1), "pairs": (
        ("2014", 1, "gross", "12",
         {"snippet": "UY2014: 12", "run_start": "UY2014: ", "first_age": 1, "quote": "12 months 5,290"}, "24",
         {"snippet": "UY2014: 24", "run_start": "UY2014: ", "first_age": 1, "quote": "12 months 5,290"}),) * 3}
    assert bf.moved_cell_pairs(plain, first) == []
    # the same figures where the text really holds a figure of that size are found
    small = {"checked": True, "cells_t": "p1 UY2012: 12 months 12; UY2013: 12 months 13; UY2014: 12 months 14",
             "cells_t_minus_1": "p1 UY2012: 12 months 24; UY2013: 12 months 26; UY2014: 12 months 28"}
    chk = {"pages": (1, 1), "pairs": tuple(
        (uy, 1, "", a, "UY%s: 12 months %s" % (uy, a), b, "UY%s: 12 months %s" % (uy, b))
        for uy, a, b in (("2012", "12", "24"), ("2013", "13", "26"), ("2014", "14", "28")))}
    assert bf.moved_cell_pairs(small, chk) == [("2012", 1, "12", "24"), ("2013", 1, "13", "26"), ("2014", 1, "14", "28")]


def test_a_year_found_only_in_a_date_is_not_an_underwriting_year():
    """Attack 3 of the review: 2015 occurs only in 'as at 31 December 2015', the figures belong to other years."""
    check = {"checked": True, "cells_t": "p10 as at 31 December 2015: UY2013 100.0",
             "cells_t_minus_1": "p9 as at 31 December 2015: UY2013 100.0, UY2014 90.0"}
    ev = {"pages": (10, 9), "pairs": (
        ("2015", 1, "", "100.0", "31 December 2015: UY2013 100.0", "90.0",
         "31 December 2015: UY2013 100.0, UY2014 90.0"),) * 3}
    assert bf.moved_cell_pairs(check, ev) == []
    for snip in ("2015: UY2013 100.0", "December 2015: UY2013 100.0"):
        assert bf.year_marks(snip) == [] or {y for _, y in bf.year_marks(snip)} != {"2015"} or "UY2013" in snip
    assert bf.year_marks("as at 31 December 2015: UY2013 100.0") == [(24, "2013")]
    assert [y for _, y in bf.year_marks("UY2011 one year later 5; YOA 2012 ; 2013 UY ; 2014: 7")] == [
        "2011", "2012", "2013", "2014"]


def test_the_attacks_fail_on_every_real_reading_and_the_real_entries_pass():
    """Each of the 20 entries is found in its own reading. With the year t-1 text replaced by the year t text (identical
    tables), with the two texts swapped, or with every pair's age or year moved by one, the entry is refused."""
    assert len(bf.MOVED_CELLS) == 20
    for (key, rid), ev in bf.MOVED_CELLS.items():
        real = _check_of(key, rid)
        assert len(_moved(key, rid)) >= 1, (key, rid)
        assert len({p[:3] for p in ev["pairs"]}) >= bf.MIN_PAIRS or ev.get("fewer_because"), (key, rid)
        same = dict(real, cells_t_minus_1=real["cells_t"].replace("p%d" % ev["pages"][0], "p%d" % ev["pages"][1]))
        assert _moved(key, rid, same, ev) == [], (key, rid, "identical tables")
        swapped = dict(real, cells_t=real["cells_t_minus_1"], cells_t_minus_1=real["cells_t"])
        assert _moved(key, rid, swapped, dict(ev, pages=ev["pages"][::-1])) == [], (key, rid, "swapped")
        for i, p in enumerate(ev["pairs"]):
            for pos, val in ((1, p[1] + 1), (0, str(int(p[0]) + 1))):
                mutated = dict(ev, pairs=ev["pairs"][:i] + (p[:pos] + (val,) + p[pos + 1:],) + ev["pairs"][i + 1:])
                assert _moved(key, rid, real, mutated) == [], (key, rid, i, pos)
            # either snippet from the other report
            for a, b in ((4, 6), (6, 4)):
                sw = list(p)
                sw[a], sw[b] = p[b], p[a]
                mutated = dict(ev, pairs=ev["pairs"][:i] + (tuple(sw),) + ev["pairs"][i + 1:])
                assert _moved(key, rid, real, mutated) == [], (key, rid, i, "sides swapped")


def test_the_figure_is_a_whole_figure_in_the_readers_text():
    """The snippet's last figure is not part of a longer number, in the snippet or in the text after it."""
    chk = {"checked": True, "cells_t": "p1 UY2011 one year later 157.8; UY2012 one year later 40.0; UY2013 one year later 3.5",
           "cells_t_minus_1": "p1 UY2011 one year later 61.5; UY2012 one year later 41.0; UY2013 one year later 4.5"}
    base = {"pages": (1, 1), "pairs": (
        ("2012", 1, "", "40.0", "UY2012 one year later 40.0", "41.0", "UY2012 one year later 41.0"),
        ("2013", 1, "", "3.5", "UY2013 one year later 3.5", "4.5", "UY2013 one year later 4.5"),
        ("2011", 1, "", "157.8", "UY2011 one year later 157.8", "61.5", "UY2011 one year later 61.5"))}
    assert len(bf.moved_cell_pairs(chk, base)) == 3
    # 57.8 inside 157.8
    inside = _pair((3, "57.8"), (4, "UY2011 one year later 157.8"), index=2, evidence=base)
    assert bf.moved_cell_pairs(chk, inside) == []
    # a snippet that stops short of the figure's end (3.5 read as 3.)
    short = _pair((3, "3"), (4, "UY2013 one year later 3"), index=1, evidence=base)
    assert bf.moved_cell_pairs(chk, short) == []
    cut = _pair((3, "157.8"), (4, "UY2011 one year later 157.") , index=2, evidence=base)
    assert bf.moved_cell_pairs(chk, cut) == []
    # a figure with a different number of decimals is another figure
    assert bf.moved_cell_pairs(dict(chk, cells_t=chk["cells_t"].replace("40.0;", "40.05;")), base) == []
    # a snippet that does not end with the pair's figure (another figure of the same length under the same label)
    wrong = dict(chk, cells_t=chk["cells_t"].replace("UY2012 one year later 40.0", "UY2012 one year later 99.9"))
    assert bf.moved_cell_pairs(wrong, base) == []
    swapped_fig = _pair((3, "99.9"), index=0, evidence=base)
    assert bf.moved_cell_pairs(chk, swapped_fig) == []
    # a snippet that is not in the text, or only in the other report's text
    assert bf.moved_cell_pairs(dict(chk, cells_t=chk["cells_t"].replace("UY2012 one year", "UY2012  one year")), base) == []
    other = _pair((4, "UY2012 one year later 41.0"), (3, "41.0"), index=0, evidence=base)
    assert bf.moved_cell_pairs(chk, other) == []


def test_unlabelled_values_are_counted_by_position_and_need_the_readers_words():
    chk = {"checked": True, "cells_t": "p1 UY2011: end of UY 10.0, one year later 12.0; UY2012: 20.0 / 24.0 / 26.0 / 27.0",
           "cells_t_minus_1": "p2 UY2011: 9.0 / 11.0; UY2012: 18.0 / 22.0 / 24.0 / 25.0; UY2013: 31.0 / 33.0",
           "result": "UY2011 end of UY 9.0 -> 10.0; one year later 11.0 -> 12.0; UY2012 age 2 is 26.0 vs 24.0"}

    def side(n, vals, quote="UY2011 end of UY 9.0 -> 10.0", first=0, text="UY2012: ", start="UY2012: "):
        return {"snippet": text + " / ".join(vals[:n]), "run_start": start, "first_age": first, "quote": quote}

    t = ["20.0", "24.0", "26.0", "27.0"]
    t1 = ["18.0", "22.0", "24.0", "25.0"]
    q12 = "age 2 is 26.0 vs 24.0"       # the reader's words for UY2012, under its year marker in the result
    ev = {"pages": (1, 2), "pairs": (
        ("2011", 0, "", "10.0", "UY2011: end of UY 10.0", "9.0", side(1, ["9.0"], text="UY2011: ", start="UY2011: ")),
        ("2011", 1, "", "12.0", "UY2011: end of UY 10.0, one year later 12.0", "11.0",
         side(2, ["9.0", "11.0"], text="UY2011: ", start="UY2011: ")),
        ("2012", 2, "", "26.0", side(3, t, quote=q12), "24.0", side(3, t1, quote=q12)))}
    assert len(bf.moved_cell_pairs(chk, ev)) == 3
    ok = ev["pairs"][2]
    for label, change in (
            ("place 3 for age 2", ((1, 3),)),
            ("figure of the next place", ((3, "27.0"), (4, side(4, t, quote=q12)))),
            ("the first age 1", ((6, dict(ok[6], first_age=1)),)),
            ("a quote that is not the reader's", ((6, dict(ok[6], quote="UY2011 end of UY 9.5 -> 10.0")),)),
            ("an empty quote", ((6, dict(ok[6], quote="")),)),
            ("no quote", ((6, {k: v for k, v in ok[6].items() if k != "quote"}),)),
            ("a quote that labels no age", ((6, dict(ok[6], quote="UY2012: 18.0 / 22.0")),)),
            ("a run_start that ends inside the list", ((6, dict(ok[6], run_start="UY2012: 18.0 / ")),)),
            ("a run_start that is not the snippet's start", ((6, dict(ok[6], run_start="UY2011: ")),)),
            ("a run_start without the year", ((6, dict(ok[6], run_start=": ", snippet=": " + ok[6]["snippet"][8:])),))):
        mutated = dict(ev, pairs=ev["pairs"][:2] + (_pair(*change, evidence={"pairs": (ok,)})["pairs"][0],))
        assert bf.moved_cell_pairs(chk, mutated) == [], label
    # a list that starts in the middle of the reader's list (run_start ends at a separator or at a figure) is refused
    # even where the places then add up to the pair's age
    for first, start in ((1, "UY2012: 18.0 / "), (1, "UY2012: 18.0 /")):
        mid = dict(ok[6], run_start=start, first_age=first, quote="one year later 12.0")
        assert bf.moved_cell_pairs(chk, _pair((6, mid), index=2, evidence=ev)) == [], start
    spaced = dict(chk, cells_t_minus_1=chk["cells_t_minus_1"].replace("UY2012: 18.0 / 22.0 / 24.0 / 25.0", "UY2012 18.0 22.0 24.0"),
                  )
    sp = dict(ok[6], snippet="UY2012 18.0 22.0 24.0", run_start="UY2012 18.0 22.0 ", first_age=2, quote="age 2 is 26.0 vs 24.0")
    assert bf.moved_cell_pairs(spaced, _pair((6, sp), index=2, evidence=ev)) == []
    # a list with a label inside it is a labelled snippet, not a positional one
    labelled = _pair((6, "UY2012: 18.0 / 22.0 / 24.0"), index=2, evidence=ev)
    assert bf.moved_cell_pairs(chk, labelled) == []


def test_the_series_of_a_pair_is_in_its_snippet():
    chk = {"checked": True,
           "cells_t": "p1 UY2014: end of UY 100, 12 months later 120; cumulative paid at end of UY 10; at 12 months 20",
           "cells_t_minus_1": "p1 UY2014: end of UY 90, 12 months later 110; cumulative paid at end of UY 7; at 12 months 18"}
    pairs = (
        ("2014", 0, "estimate", "100", "UY2014: end of UY 100", "90", "UY2014: end of UY 90"),
        ("2014", 1, "estimate", "120", "UY2014: end of UY 100, 12 months later 120", "110",
         "UY2014: end of UY 90, 12 months later 110"),
        ("2014", 0, "paid", "10", "UY2014: end of UY 100, 12 months later 120; cumulative paid at end of UY 10",
         "7", "UY2014: end of UY 90, 12 months later 110; cumulative paid at end of UY 7"),
        ("2014", 1, "paid", "20", "UY2014: end of UY 100, 12 months later 120; cumulative paid at end of UY 10; at 12 months 20",
         "18", "UY2014: end of UY 90, 12 months later 110; cumulative paid at end of UY 7; at 12 months 18"))
    ev = {"pages": (1, 1), "pairs": pairs}
    assert len(bf.moved_cell_pairs(chk, ev)) == 4
    # a paid pair whose snippets are the estimate cells (12 months later 120 / 110), an estimate pair that names paid; each
    # of the four keeps three different cells, so only the series refuses it
    assert bf.moved_cell_pairs(chk, _pair((2, "paid"), index=1, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "net"), index=1, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "estimate"), index=3, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "gross"), index=3, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, ""), index=3, evidence=ev)) == []


def test_fewer_than_three_pairs_need_the_readers_own_reason():
    """The readers' brief asks for at least three cells: an entry with fewer carries the reader's words for it."""
    few = dict(_EVIDENCE, pairs=_EVIDENCE["pairs"][:2])
    assert bf.moved_cell_pairs(_CHECK, few) == []
    reason = _CHECK["note"]
    assert bf.moved_cell_pairs(_CHECK, dict(few, fewer_because=reason)) == _MOVED
    for bad in ("only one underwriting year precedes the year t-1", "", "   ", None, (), "UY2011 at end of underwriting year 65.0",
                "p40"):
        assert bf.moved_cell_pairs(_CHECK, dict(few, fewer_because=bad)) == [], bad
    # a real entry: 1492/2017 holds two pairs, and loses them with the reason removed or altered
    for k in (("1492_2017", "X5"), ("1492_2017", "Y5"), ("6119_2016", "Y1")):
        ev = bf.MOVED_CELLS[k]
        assert len(ev["pairs"]) == 2 and ev["fewer_because"]
        real = _check_of(*k)
        assert _moved(*k) != []
        assert _moved(*k, real, {x: y for x, y in ev.items() if x != "fewer_because"}) == []
        assert _moved(*k, real, dict(ev, fewer_because=ev["fewer_because"] + " (and more)")) == []
    assert sum(len(e["pairs"]) < 3 for e in bf.MOVED_CELLS.values()) == 3


def test_the_alignment_of_1301_2016_x8_is_recorded_as_the_sessions_choice_with_the_readers_words():
    ev = bf.MOVED_CELLS[("1301_2016", "X8")]
    real = _check_of("1301_2016", "X8")
    assert "the alignment is the session's choice" in ev["alignment"] and "differ under either alignment" in ev["alignment"]
    assert bf.moved_cell_pairs(real, ev) != []
    assert all(q in real["stated_basis"] for q in ev["alignment_quotes"])
    assert "either way no cell for UY2011 to UY2014 is unchanged" in " ".join(ev["alignment_quotes"])
    assert bf.moved_cell_pairs(real, dict(ev, alignment_quotes=("either way every cell is unchanged",))) == []
    assert bf.moved_cell_pairs(real, dict(ev, alignment="")) == []
    assert bf.moved_cell_pairs(real, dict(ev, alignment_quotes=())) == []
    # no other entry claims an alignment
    assert [k for k, e in bf.MOVED_CELLS.items() if "alignment" in e] == [("1301_2016", "X8")]


def test_the_evidence_of_every_table_retranslated_reading_is_found_in_the_readers_cells():
    """The 20 entries of MOVED_CELLS are each found in the archived reading's own cells, with at least three pairs (or
    the reader's reason for fewer), and at least one pair moved."""
    reg = _register()
    keys = {(k, r["reader"]) for k, e in reg["read_and_kept"].items() if e.get("reason") == "table_retranslated"
            for r in e["readings"]}
    assert keys == set(bf.MOVED_CELLS) and len(keys) == 20
    for k, e in reg["read_and_kept"].items():
        if e.get("reason") != "table_retranslated":
            continue
        for r in e["readings"]:
            ev = bf.MOVED_CELLS[(k, r["reader"])]
            moved = _moved(k, r["reader"], r["table_retranslated_check"], ev)
            assert len(moved) == len(ev["pairs"]) >= 2, (k, r["reader"])
            assert len(ev["pairs"]) >= bf.MIN_PAIRS or ev.get("fewer_because"), (k, r["reader"])


def test_the_build_refuses_moved_cells_that_are_not_those_of_the_table_retranslated_readings(monkeypatch):
    """MOVED_CELLS must be exactly the table_retranslated readings: one missing, or one extra, stops the build."""
    full = dict(bf.MOVED_CELLS)
    monkeypatch.setattr(bf, "MOVED_CELLS", {k: v for k, v in full.items() if k != ("3902_2023", "X3")})
    with pytest.raises(SystemExit):
        bf.build()
    extra = dict(full)
    extra[("457_2015", "X6")] = full[("3902_2023", "Y3")]
    monkeypatch.setattr(bf, "MOVED_CELLS", extra)
    with pytest.raises(SystemExit):
        bf.build()
    monkeypatch.setattr(bf, "MOVED_CELLS", full)
    assert bf.build()["read_and_kept"]["3902_2023"]["reason"] == "table_retranslated"


def test_a_check_that_compared_no_cells_shows_none():
    for checked in (False, "partly", "no: cannot compare", None):
        assert bf.shows_moved_cells(dict(_CHECK, checked=checked), _EVIDENCE) is False
    assert bf.shows_moved_cells(None, _EVIDENCE) is False and bf.shows_moved_cells("moved", _EVIDENCE) is False


# --- review 5 (23 October 2026): the anchors of an unlabelled list, the row, the series, the count, the figure -------------
# Every attack of the review is a test that must refuse, built so that ONLY the guard it is about refuses it (the other
# pairs are good, and a control with the guard satisfied is accepted).

_RT = "UY2011 one year later 57.8; UY2012 one year later 50.2; UY2013 one year later 60.0"
_RT1 = "UY2011 one year later 61.5; UY2012 one year later 50.1; UY2013 one year later 70.0"
_REASON = "Only two underwriting years precede the year t-1 in this table, so there are two cells for UY2011"


def _g(uy, a, b, age=1, label="one year later", series=""):
    """A labelled pair: 'UY2011 one year later 57.8' against 'UY2011 one year later 61.5'."""
    return (uy, age, series, a, "UY%s %s %s" % (uy, label, a), b, "UY%s %s %s" % (uy, label, b))


_ROWS = (_g("2011", "57.8", "61.5"), _g("2012", "50.2", "50.1"), _g("2013", "60.0", "70.0"))
_ROWS_MOVED = [("2011", 1, "57.8", "61.5"), ("2013", 1, "60.0", "70.0")]


def _syn(t, t1, pairs, key=None, other=None, **extra):
    """moved_cell_pairs over a synthetic check (pages p1 and p2); `extra` goes into the entry (fewer_because, ...)."""
    check = {"checked": True, "cells_t": "p1 " + t, "cells_t_minus_1": "p2 " + t1, "note": _REASON, "result": extra.pop("result", "")}
    return bf.moved_cell_pairs(check, dict({"pages": (1, 2), "pairs": tuple(pairs)}, **extra), key, other)


def _only(pairs, index, pair):
    return pairs[:index] + (pair,) + pairs[index + 1:]


def test_the_synthetic_control_is_accepted():
    assert _syn(_RT, _RT1, _ROWS) == _ROWS_MOVED


# 1. the fallback anchor is gone (B1, B2) -----------------------------------------------------------------------------

_ANCHOR_T = "UY2011 one year later 5.0; UY2012 one year later 6.0; UY2014: 49.4 / 99.9"
_ANCHOR_T1 = "UY2011 one year later 4.0; UY2012 one year later 5.0; UY2014: 40.4 / 90.9"
_ANCHOR_RESULT = "UY2014 one year 86.7 -> 80.1; UY2014 one year 49.4 -> 40.4"


def _anchored(quote, first_age=1, **spec):
    """A UY2014 list [49.4, 99.9] (and [40.4, 90.9]) read from `first_age`, anchored on `quote` (and `spec`)."""
    side = lambda snip: dict({"snippet": snip, "run_start": "UY2014: ", "first_age": first_age, "quote": quote}, **spec)  # noqa: E731
    return _syn(_ANCHOR_T, _ANCHOR_T1, (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
                                        ("2014", first_age + 1, "", "99.9", side("UY2014: 49.4 / 99.9"), "90.9",
                                         side("UY2014: 40.4 / 90.9"))), result=_ANCHOR_RESULT)


def test_a_list_is_anchored_by_a_label_of_one_of_its_own_figures_and_by_nothing_else():
    """B1 and B2 of review 5: the old fallback accepted a first age that ANY labelled figure of the reader's quote had, in
    any row. The quote must label a figure of this very list at the age its place gives."""
    assert len(_anchored("one year 49.4 -> 40.4")) == 3                    # 49.4 is the list's first value, age 1
    # the same underwriting year's quote, labelling figures that are not in the list (86.7 at age 1): no anchor
    assert _anchored("one year 86.7 -> 80.1") == []
    # the list read one age earlier, against the same quote: 49.4 would be age 0, the quote says 1
    assert _anchored("one year 49.4 -> 40.4", first_age=0) == []
    # nothing says what the list's first age is
    assert _anchored("") == [] and _anchored(None) == []
    assert _anchored("one year 49.4 -> 40.4", anchor="nothing") == []


def test_shifted_first_ages_on_the_real_readings_are_refused():
    """B1 (identical tables) and B2 (the real 5820/2016 X3 cells) of review 5, as the review ran them."""
    check = _check_of("5820_2016", "X3")
    same = dict(check, cells_t_minus_1=check["cells_t"].replace("2016 report p42", "2015 report p25"))

    def side(snip, run_start, first_age, quote):
        return {"snippet": snip, "run_start": run_start, "first_age": first_age, "quote": quote}

    b1 = {"pages": (42, 25), "pairs": (
        ("2012", 2, "", "45.2", side("UY2012: 27.4, 45.2", "UY2012: ", 1, "one year later 77.6"),
         "58.5", side("UY2012: 27.4, 45.2, 58.5", "UY2012: ", 0, "end of UY 44.7")),
        ("2013", 2, "", "53.8", side("UY2013: 18.4, 53.8", "UY2013: ", 1, "one year later 77.6"),
         "60.3", side("UY2013: 18.4, 53.8, 60.3", "UY2013: ", 0, "end of UY 44.7")),
        ("2014", 1, "", "15.9", side("UY2014: 15.9", "UY2014: ", 1, "one year later 77.6"),
         "40.8", side("UY2014: 15.9, 40.8", "UY2014: ", 0, "end of UY 44.7")))}
    assert _moved("5820_2016", "X3", same, b1) == []
    b2 = {"pages": (42, 25), "pairs": (
        ("2012", 1, "", "27.4", side("UY2012: 27.4", "UY2012: ", 1, "one year later 77.6"),
         "40.6", side("UY2012: 24.0, 40.6", "UY2012: ", 0, "end of UY 44.7")),
        ("2013", 1, "", "18.4", side("UY2013: 18.4", "UY2013: ", 1, "one year later 77.6"),
         "48.2", side("UY2013: 16.4, 48.2", "UY2013: ", 0, "end of UY 44.7")),
        ("2014", 1, "", "15.9", side("UY2014: 15.9", "UY2014: ", 1, "one year later 77.6"),
         "36.1", side("UY2014: 13.8, 36.1", "UY2014: ", 0, "end of UY 44.7")))}
    assert _moved("5820_2016", "X3", None, b2) == []


def test_a_label_under_another_underwriting_years_marker_anchors_nothing():
    """The quote labels the list's own first value (13.0 at age 0), but under UY2011's marker in the reader's text: it is
    another row's label, which happens to hold the same figure. Under UY2012's marker it anchors."""
    t = "UY2011 one year later 5.0; UY2012: 13.0 / 24.0 / 26.0; UY2013 one year later 7.0"
    t1 = "UY2011 one year later 4.0; UY2012: 12.0 / 22.0 / 24.0; UY2013 one year later 6.0"
    result = "UY2011 age 0 is 13.0 vs 12.0; UY2012 age 1 is 24.0 vs 22.0"

    def run(quote):
        side = lambda snip: {"snippet": snip, "run_start": "UY2012: ", "first_age": 0, "quote": quote}  # noqa: E731
        return _syn(t, t1, (_g("2011", "5.0", "4.0"),
                            ("2012", 1, "", "24.0", side("UY2012: 13.0 / 24.0"), "22.0", side("UY2012: 12.0 / 22.0")),
                            _g("2013", "7.0", "6.0")), result=result)
    assert len(run("age 1 is 24.0 vs 22.0")) == 3
    assert run("age 0 is 13.0 vs 12.0") == []


def test_the_sixteen_sides_the_old_fallback_alone_passed_are_anchored_on_the_other_arm():
    """The 16 positional sides (1301/2017 Y1 UY2013 age 0 and UY2014 age 1; 5678/2016 Y1 paid age 0; the eight sides of
    5820/2016 X3; 5820/2017 Y4 UY2012 age 0) that passed only through the fallback are anchored on the other arm's reading
    of the same filing, page, underwriting year, series and figure; without it, or with the quote the fallback took, they
    are refused."""
    old_quote = {("1301_2017", "Y1"): "end of UY 29.5", ("5678_2016", "Y1"): "end of UY 962",
                 ("5820_2016", "X3"): "end of UY 44.7", ("5820_2017", "Y4"): "end 42.0"}
    total = 0
    for (key, rid), quote in old_quote.items():
        ev = bf.MOVED_CELLS[(key, rid)]
        weak = [(i, w) for i, p in enumerate(ev["pairs"]) for w in (4, 6)
                if isinstance(p[w], dict) and p[w].get("anchor") == "other_arm"]
        total += len(weak)
        assert _moved(key, rid) != []
        assert _moved(key, rid, other=False) == [], (key, rid)
        back = list(ev["pairs"])
        for i, w in weak:
            p = list(back[i])
            p[w] = {k: v for k, v in p[w].items() if k != "anchor"} | {"quote": quote}
            back[i] = tuple(p)
        assert _moved(key, rid, evidence=dict(ev, pairs=tuple(back))) == [], (key, rid, "the fallback's quote")
        # the other arm's reading of another record, of another page, or no longer bearing its own entry out
        other = _other_arm(key, rid)
        real = _check_of(key, rid)
        assert bf.moved_cell_pairs(real, ev, key, dict(other, key="1301_2016")) == []
        assert bf.moved_cell_pairs(real, ev, key, dict(other, evidence=dict(other["evidence"], pages=(1, 2)))) == []
        broken = dict(other["check"], cells_t=other["check"]["cells_t"].replace("p%d" % other["evidence"]["pages"][0], "p9"))
        assert bf.moved_cell_pairs(real, ev, key, dict(other, check=broken)) == []
        assert bf.moved_cell_pairs(real, ev, None, other) == []
        # a figure the other arm gives at another age
        i, w = weak[0]
        p = list(ev["pairs"][i])
        p[w] = dict(p[w], first_age=p[w]["first_age"] + 1)
        p[1] = p[1] + 1
        assert _moved(key, rid, evidence=dict(ev, pairs=_only(ev["pairs"], i, tuple(p)))) == [], (key, rid, "another age")
    assert total == 16


def test_the_other_arms_reading_gives_every_value_of_its_lists_at_the_age_of_its_place():
    """The other arm's list [20.0, 24.0, 26.0] read from age 0 (its 26.0 labelled age 2) gives 24.0 at age 1, though its
    own pair is the age-2 cell: a list of ours ending at 24.0 is anchored on that, at that age and no other, and only where
    the other arm read the same pages."""
    t = "UY2011 one year later 5.0; UY2012 one year later 6.0; UY2013: 20.0 / 24.0 / 26.0"
    t1 = "UY2011 one year later 4.0; UY2012 one year later 5.0; UY2013: 18.0 / 22.0 / 24.0"
    key, quote = "9_2016", "age 2 is 26.0 vs 24.0"

    def pos(snip, first=0, **how):
        return dict({"snippet": snip, "run_start": "UY2013: ", "first_age": first}, **how)

    def arm(pages=(1, 2), cells_t1=t1):
        check = {"checked": True, "cells_t": "p1 " + t, "cells_t_minus_1": "p2 " + cells_t1, "result": "UY2013 " + quote}
        pairs = (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
                 ("2013", 2, "", "26.0", pos("UY2013: 20.0 / 24.0 / 26.0", quote=quote), "24.0",
                  pos("UY2013: 18.0 / 22.0 / 24.0", quote=quote)))
        return {"key": key, "reader": "Y9", "check": check, "evidence": {"pages": pages, "pairs": pairs}}

    def ours(age=1, first=0, pages=(1, 2), other=None, snips=("UY2013: 20.0 / 24.0", "UY2013: 18.0 / 22.0")):
        check = {"checked": True, "cells_t": "p1 " + t, "cells_t_minus_1": "p2 " + t1}
        pairs = (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
                 ("2013", age, "", "24.0", pos(snips[0], first, anchor="other_arm"), "22.0",
                  pos(snips[1], first, anchor="other_arm")))
        return bf.moved_cell_pairs(check, {"pages": pages, "pairs": pairs}, key, other)
    assert arm()["evidence"]["pairs"][2][1] == 2
    assert len(ours(other=arm())) == 3                      # 24.0 at age 1, the middle value of the other arm's list
    assert ours() == [] and ours(other=None) == []
    assert ours(age=2, first=1, other=arm()) == []          # the same list read from age 1: the other arm says age 1
    # the other arm read other pages (its check names p1 and p9 as well as the entry's pages)
    other_pages = arm(pages=(1, 9), cells_t1=t1 + " p9")
    assert bf._evaluate(other_pages["check"], other_pages["evidence"], key, None) is not None
    assert ours(other=other_pages) == []


def test_no_anchor_but_a_place_label_and_the_other_arm_exists():
    """Review 6, finding 4: the 'row_label' anchor (a labelled later value of the same row) was used by no entry and is
    removed; an entry that names it, or any anchor not listed, is refused whatever its cells say."""
    assert bf.ANCHORS == ("place_label", "other_arm")
    assert not hasattr(bf, "_row_label_anchor")
    assert all(s.get("anchor", "place_label") in bf.ANCHORS for ev in bf.MOVED_CELLS.values() for p in ev["pairs"]
               for s in (p[4], p[6]) if isinstance(s, dict))
    t = "UY2011 one year later 5.0; UY2012: 20.0 / 24.0 / three years later 27.0; UY2013 one year later 7.0"
    t1 = "UY2011 one year later 4.0; UY2012: 18.0 / 22.0 / three years later 25.0; UY2013 one year later 6.0"

    def run(anchor):
        side = lambda snip: {"snippet": snip, "run_start": "UY2012: ", "first_age": 1, "anchor": anchor}  # noqa: E731
        return _syn(t, t1, (_g("2011", "5.0", "4.0"),
                            ("2012", 2, "", "24.0", side("UY2012: 20.0 / 24.0"), "22.0", side("UY2012: 18.0 / 22.0")),
                            _g("2013", "7.0", "6.0")))
    assert run("row_label") == [] and run("anything") == [] and run("place_label") == []


# 2. the snippet is one row (B3, B3b, B11) ------------------------------------------------------------------------------

def test_a_snippet_that_runs_into_another_row_is_refused_on_the_real_readings():
    """B3 of review 5: UY2011's 'Total' row of 4020/2016 X5 runs on into '2010 and prior', and the figure of that row is
    attributed to UY2011. B3b: the same on identical tables."""
    ev = bf.MOVED_CELLS[("4020_2016", "X5")]
    attack = ("2011", 1, "", "614,673",
              "UY2011: 1 year 102,660; 2 years 182,455; 3 years 196,129. 2010 and prior: 1 year 614,673",
              "526,914", "UY2011: 1 year 88,920; 2 years 158,760; 3 years 170,228. 2010 and prior: 1 year 526,914")
    assert ev["pairs"][4][0] == "2011"
    assert _moved("4020_2016", "X5") != []
    assert _moved("4020_2016", "X5", evidence=dict(ev, pairs=_only(ev["pairs"], 4, attack))) == []
    check = _check_of("4020_2016", "X5")
    same = dict(check, cells_t_minus_1=check["cells_t"].replace("p42", "p44"))
    ident = {"pages": (42, 44), "pairs": (
        ("2013", 1, "", "111,919", "UY2013: 1 year 111,919", "111,919", "UY2013: 1 year 111,919"),
        ("2012", 1, "", "116,352", "UY2012: 1 year 116,352", "116,352", "UY2012: 1 year 116,352"),
        ("2011", 1, "", "102,660", "UY2011: 1 year 102,660", "614,673",
         "UY2011: 1 year 102,660; 2 years 182,455; 3 years 196,129. 2010 and prior: 1 year 614,673"))}
    assert _moved("4020_2016", "X5", same, ident) == []
    honest = _only(ident["pairs"], 2, ("2011", 1, "", "102,660", "UY2011: 1 year 102,660", "102,661", "UY2011: 1 year 102,660"))
    assert _moved("4020_2016", "X5", same, dict(ident, pairs=honest)) == []        # equal cells: nothing moved, but valid


def test_a_snippet_starts_at_its_year_marker_and_a_series_word_may_come_first():
    assert _syn(_RT, _RT1, _ROWS) == _ROWS_MOVED
    bad = ("2011", 1, "", "57.8", "the table UY2011 one year later 57.8", "61.5", "UY2011 one year later 61.5")
    assert _syn("the table " + _RT, _RT1, _only(_ROWS, 0, bad)) == []
    paid = ("2011", 1, "paid", "57.8", "paid UY2011 one year later 57.8", "61.5", "paid UY2011 one year later 61.5")
    assert _syn("paid " + _RT, "paid " + _RT1, _only(_ROWS, 0, paid)) == _ROWS_MOVED


def test_a_part_after_a_row_break_must_begin_with_an_age_label():
    """'; ' and '. ' end a cell; what follows is another cell of the row only if it is labelled with an age ('two years
    later', 'cumulative paid at end of UY', 'Net: 12 months'), not another row's label ('other', 'total', '2010 and prior')."""
    row = "UY2011: one year later 57.8; two years later 9.0"
    row1 = "UY2011: one year later 61.5; two years later 8.0"
    good = ("2011", 2, "", "9.0", row, "8.0", row1)
    assert _syn(row + "; " + _RT.split("; ", 1)[1], row1 + "; " + _RT1.split("; ", 1)[1], (good,) + _ROWS[1:]) != []
    for junk in ("other two years later 9.0", "Note two years later 9.0", "UY2011 other two years later 9.0"):
        bad_t = "UY2011: one year later 57.8; %s" % junk
        bad = ("2011", 2, "", "9.0", bad_t, "8.0", row1)
        assert _syn(bad_t + "; " + _RT.split("; ", 1)[1], row1 + "; " + _RT1.split("; ", 1)[1], (bad,) + _ROWS[1:]) == [], junk
    # a sentence break
    sent = "UY2011: one year later 57.8. Other two years later 9.0"
    assert _syn(sent + "; " + _RT.split("; ", 1)[1], row1 + "; " + _RT1.split("; ", 1)[1],
                (("2011", 2, "", "9.0", sent, "8.0", row1),) + _ROWS[1:]) == []


def test_a_snippet_holds_no_other_year_number_no_prior_earlier_or_total_row():
    """B11 of review 5: '2012 one year later 66.0' (a bare row label, not a marker) inside a UY2011 snippet, so that
    UY2012's cell is read as UY2011's."""
    t = "UY2011 one year later 57.8 2012 one year later 66.0; " + _RT.split("; ", 1)[1]
    bad = ("2011", 1, "", "66.0", "UY2011 one year later 57.8 2012 one year later 66.0", "61.5", "UY2011 one year later 61.5")
    assert _syn(t, _RT1, (bad,) + _ROWS[1:]) == []
    assert _syn(t, _RT1, (_ROWS[0],) + _ROWS[1:]) == _ROWS_MOVED                # the same text, the honest pair
    for word in ("total", "prior", "earlier", "Total"):
        snip = "UY2011 %s one year later 57.8" % word
        bad = ("2011", 1, "", "57.8", snip, "61.5", "UY2011 one year later 61.5")
        assert _syn("%s; %s" % (snip, _RT.split("; ", 1)[1]), _RT1, (bad,) + _ROWS[1:]) == [], word
    # a year inside a date is not a marker, and is another year number
    snip = "UY2011 as at 31 December 2015 one year later 57.8"
    bad = ("2011", 1, "", "57.8", snip, "61.5", "UY2011 one year later 61.5")
    assert _syn("%s; %s" % (snip, _RT.split("; ", 1)[1]), _RT1, (bad,) + _ROWS[1:]) == []


def test_a_gloss_after_the_year_marker_may_name_a_year_but_hold_no_cell():
    """'YOA 2015 (the only underwriting year before t-1 = 2016): At end ...' is the reader's gloss on the marker (1492/2017
    X5). A parenthesis after the marker that carries a cell is another row hidden in it."""
    g = "UY2011 (the only underwriting year before t-1 = 2016): one year later 57.8"
    pair = ("2011", 1, "", "57.8", g, "61.5", "UY2011 one year later 61.5")
    assert _syn(g + "; " + _RT.split("; ", 1)[1], _RT1, (pair,) + _ROWS[1:]) == _ROWS_MOVED
    hidden = "UY2011 (2012 one year later 66.0): one year later 57.8"
    pair = ("2011", 1, "", "57.8", hidden, "61.5", "UY2011 one year later 61.5")
    assert _syn(hidden + "; " + _RT.split("; ", 1)[1], _RT1, (pair,) + _ROWS[1:]) == []
    later = "UY2011 one year later 57.8 (2012 one year later 66.0)"
    pair = ("2011", 1, "", "66.0", later, "61.5", "UY2011 one year later 61.5")
    assert _syn(later + "; " + _RT.split("; ", 1)[1], _RT1, (pair,) + _ROWS[1:]) == []


def test_a_cross_row_snippet_claiming_one_underwriting_year_is_refused_by_the_year_guard_alone():
    """UY2011's snippet runs on into UY2012's marker and takes UY2012's cell ('UY2012: one year later 27.4') for its own.
    There is no row break, no bare year and no other word in it, so only the guard that a snippet names its own
    underwriting year and no other refuses it."""
    t = "UY2011 one year later 57.8 UY2012: one year later 27.4; UY2013 one year later 60.0; UY2014 one year later 8.0"
    t1 = _RT1 + "; UY2014 one year later 9.0"
    snip = "UY2011 one year later 57.8 UY2012: one year later 27.4"
    assert bf.year_marks(snip) == [(0, "2011"), (27, "2012")]
    bad = ("2011", 1, "", "27.4", snip, "61.5", "UY2011 one year later 61.5")
    rest = (_g("2013", "60.0", "70.0"), _g("2014", "8.0", "9.0"))
    assert _syn(t, t1, (bad,) + rest) == []
    # the honest cell of UY2012 is found under UY2012, and the other pairs stand
    fixed = ("2012", 1, "", "27.4", "UY2012: one year later 27.4", "50.1", "UY2012 one year later 50.1")
    assert _syn(t, t1, (fixed,) + rest) == [("2012", 1, "27.4", "50.1"), ("2013", 1, "60.0", "70.0"), ("2014", 1, "8.0", "9.0")]


# 3. the start of a list (B8, B8b, B8c) -------------------------------------------------------------------------------

def test_a_list_starts_at_its_year_marker_or_a_series_word_not_at_a_label_or_a_page_number():
    """B8 of review 5: run_start 'UY2011: p' makes the page number '40' a list value; B8b/B8c: a total
    ('total gross outstanding 2,418') is taken as an age-0 cell. A positional run_start (with ' :' stripped) ends with the
    year marker or a series word (paid, net, gross, estimate)."""
    quote = ("UY2011 end of UY 40", "UY2011 end of UY 45")      # the reader's words labelling the list's value at age 0

    def run(start, snip, fig="40", t="UY2011: p40; UY2012 one year later 6.0; UY2013 one year later 7.0"):
        side = {"snippet": snip, "run_start": start, "first_age": 0, "quote": quote}
        side1 = dict(side, snippet=snip.replace("40", "45"))
        words = "; x: " + "; ".join(quote)
        return _syn(t + words, t.replace("40", "45").replace("6.0", "5.0").replace("7.0", "6.0") + words,
                    (("2011", 0, "", fig, side, "45", side1), _g("2012", "6.0", "5.0"), _g("2013", "7.0", "6.0")))
    assert len(run("UY2011: ", "UY2011: 40", t="UY2011: 40; UY2012 one year later 6.0; UY2013 one year later 7.0")) == 3
    assert run("UY2011: p", "UY2011: p40") == []                                        # B8
    assert run("UY2011 outstanding ", "UY2011 outstanding 40", t="UY2011 outstanding 40; UY2012 one year later 6.0; "
                                                                  "UY2013 one year later 7.0") == []
    assert run("UY2011 total gross outstanding ", "UY2011 total gross outstanding 40",
               t="UY2011 total gross outstanding 40; UY2012 one year later 6.0; UY2013 one year later 7.0") == []   # B8b
    # the real 5678/2016 X1 'UY2014 total gross outstanding 2,418', as a labelled and as a positional age-0 cell (B8c)
    ev = bf.MOVED_CELLS[("5678_2016", "X1")]
    total = ("2014", 0, "estimate", "2,418", "UY2014 total gross outstanding 2,418", "1,609",
             "UY2014 total gross outstanding 1,609")
    assert _moved("5678_2016", "X1") != []
    assert _moved("5678_2016", "X1", evidence=dict(ev, pairs=_only(ev["pairs"], 0, total))) == []
    pos = {"snippet": "UY2014 total gross outstanding 2,418", "run_start": "UY2014 total gross outstanding ",
           "first_age": 0, "quote": "end of UY 962"}
    pos1 = {"snippet": "UY2014 total gross outstanding 1,609", "run_start": "UY2014 total gross outstanding ",
            "first_age": 0, "quote": "end of UY 962"}
    assert _moved("5678_2016", "X1", evidence=dict(ev, pairs=_only(ev["pairs"], 0, ("2014", 0, "estimate", "2,418", pos,
                                                                                    "1,609", pos1)))) == []
    # a list that follows a series word ('paid UY2014 19', 'Net: 3,936') is a list
    assert _moved("5678_2016", "Y1") != [] and _moved("6119_2016", "X1") != []
    assert any(isinstance(p[4], dict) and p[4]["run_start"] == "paid UY2014 " for p in bf.MOVED_CELLS[("5678_2016", "Y1")]["pairs"])
    assert any(isinstance(p[6], dict) and p[6]["run_start"].endswith("Net: ") for p in bf.MOVED_CELLS[("6119_2016", "X1")]["pairs"])


# 4. the series (B4) --------------------------------------------------------------------------------------------------------

def test_a_pair_with_no_series_is_read_as_estimate_and_its_snippets_name_neither_paid_nor_net():
    """B4 of review 5: series '' disabled the tie, so an estimate cell (962) was paired with a paid cell (19)."""
    t = "UY2014: estimate at end of UY 962; 12 months later 2,362; cumulative paid at end of UY 19; at 12 months 515"
    t1 = "UY2014: estimate at end of UY 859; 12 months later 2,051; cumulative paid at end of UY 16; at 12 months 441"
    est0 = ("2014", 0, "estimate", "962", "UY2014: estimate at end of UY 962", "859", "UY2014: estimate at end of UY 859")
    est1 = ("2014", 1, "estimate", "2,362", "UY2014: estimate at end of UY 962; 12 months later 2,362", "2,051",
            "UY2014: estimate at end of UY 859; 12 months later 2,051")
    paid0 = ("2014", 0, "paid", "19", t.split("; at 12")[0], "16", t1.split("; at 12")[0])
    assert len(_syn(t, t1, (est0, est1, paid0))) == 3
    as_blank = paid0[:2] + ("",) + paid0[3:]
    assert _syn(t, t1, (est0, est1, as_blank)) == []
    for series in ("estimate", "gross"):
        assert _syn(t, t1, (est0, est1, paid0[:2] + (series,) + paid0[3:])) == [], series
    assert _syn(t, t1, (est0, est1, paid0[:2] + ("net",) + paid0[3:])) == []
    # B4 as the review ran it: identical tables, an estimate cell against a paid cell, series ''
    mixed = ("2014", 0, "", "962", "UY2014: estimate at end of UY 962", "19", t.split("; at 12")[0])
    assert _syn(t, t, (est0[:5] + ("962", est0[4]), est1[:5] + ("2,362", est1[4]), mixed)) == []


# 5. the count (B5, B6) -------------------------------------------------------------------------------------------------

def test_three_different_cells_are_needed_not_three_pairs():
    """B5 of review 5: one pair repeated reached the minimum of three. Distinct (underwriting year, age, series) cells are
    counted, and fewer than three need the reader's own reason."""
    repeated = (_ROWS[0], _ROWS[0], _ROWS[1])
    assert _syn(_RT, _RT1, repeated) == []
    two = (_ROWS[0], _ROWS[1])
    assert _syn(_RT, _RT1, two) == []
    assert _syn(_RT, _RT1, two, fewer_because=_REASON) == [("2011", 1, "57.8", "61.5")]
    # the 6119/2016 Y1 of the review with its reason removed and a pair repeated
    ev = dict(bf.MOVED_CELLS[("6119_2016", "Y1")])
    ev.pop("fewer_because")
    assert _moved("6119_2016", "Y1", evidence=dict(ev, pairs=ev["pairs"] + (ev["pairs"][0],))) == []


def test_the_reason_for_fewer_cells_is_a_reason_and_the_report_holds_no_more_years_than_the_entry_uses():
    """B6 of review 5: any verbatim substring ('p31') was accepted as the reader's reason. A reason is a sentence that
    says why (only / single / precedes / older), and the year t cells hold no more underwriting years before t-1 than the
    entry uses; no pair is of an underwriting year from t-1 on."""
    two = (_ROWS[0], _ROWS[1])
    for bad in ("p1", "UY2011 one year later 57.8", "one year later 57.8; UY2012", "Only two years"):
        assert _syn(_RT, _RT1, two, key="9_2016", fewer_because=bad) == [], bad
    ev = dict(bf.MOVED_CELLS[("6119_2016", "Y1")], fewer_because="p31")
    assert _moved("6119_2016", "Y1", evidence=ev) == []
    # the year t cells hold UY2011, UY2012 and UY2013 before t-1 = 2015, the entry uses two of them
    assert _syn(_RT, _RT1, two, key="9_2016", fewer_because=_REASON) == []
    # with t-1 = 2012 only UY2011 precedes it, and the entry uses it: one cell, and the reader's reason, are enough
    assert _syn(_RT, _RT1, (_ROWS[0],), key="9_2013", fewer_because=_REASON) == [("2011", 1, "57.8", "61.5")]
    one = ("2011", 1, "", "57.8", "UY2011 one year later 57.8", "61.5", "UY2011 one year later 61.5")
    one_age2 = ("2011", 2, "", "9.0", "UY2011 one year later 57.8; two years later 9.0", "8.0",
                "UY2011 one year later 61.5; two years later 8.0")
    t = "UY2011 one year later 57.8; two years later 9.0; UY2012 one year later 50.2"
    t1 = "UY2011 one year later 61.5; two years later 8.0; UY2012 one year later 50.1"
    assert len(_syn(t, t1, (one, one_age2), key="9_2013", fewer_because=_REASON)) == 2
    assert _syn(t, t1, (one, one_age2), key="9_2012", fewer_because=_REASON) == []     # UY2011 is t-1: from t-1 on
    for y, ok in (("2014", True), ("2015", False), ("2016", False)):
        rows = tuple(_g(str(int(y) - i), "5.0", "4.0") for i in range(3))
        tt = "; ".join("UY%s one year later 5.0" % p[0] for p in rows)
        tt1 = "; ".join("UY%s one year later 4.0" % p[0] for p in rows)
        assert bool(_syn(tt, tt1, rows, key="9_2016")) is ok, y            # t-1 = 2015: the newest year may be 2014


# 6. the figure (B7), the labels (B13) ------------------------------------------------------------------------------------

def test_a_percentage_is_not_a_cell():
    """B7 of review 5: 'one year later 12%' is a percentage, taken as the cell 12."""
    for pct in ("12%", "12 %"):
        bad = ("2011", 1, "", "12", "UY2011 one year later 12", "5", "UY2011 one year later 5")
        t = "UY2011 one year later %s; %s" % (pct, _RT.split("; ", 1)[1])
        t1 = "UY2011 one year later 5%; " + _RT1.split("; ", 1)[1]
        assert _syn(t, t1, (bad,) + _ROWS[1:]) == [], pct
    plain = _syn("UY2011 one year later 12; " + _RT.split("; ", 1)[1], "UY2011 one year later 5; " + _RT1.split("; ", 1)[1],
                 (("2011", 1, "", "12", "UY2011 one year later 12", "5", "UY2011 one year later 5"),) + _ROWS[1:])
    assert plain == [("2011", 1, "12", "5"), ("2013", 1, "60.0", "70.0")]
    assert [m.group(1) for m in bf.FIGURE.finditer("5.0 12% 7 % 8 9.5")] == ["5.0", "8", "9.5"]


def test_a_bare_word_is_an_age_label_only_inside_the_readers_sequence_of_labels():
    """B13 of review 5: 'of the five 62.6' is prose, not the cell at age 5. 'end', 'three', 'four' and 'five' are labels
    after a separator or the row's year marker ('UY2011: end 44.7; ...; three 63.0'), as the real entries use them, and
    the full forms ('three years later') are labels anywhere."""
    assert bf.trailing_age("UY2011 of the five ") is None and bf.trailing_age("UY2011 the end ") is None
    assert bf.trailing_age("UY2011 of the three years later ") == 3
    assert bf.trailing_age("UY2011: ") is None and bf.trailing_age("UY2011: end 44.7; one year later 77.6; ") is None
    assert bf.trailing_age("UY2011: end ") == 0 and bf.trailing_age("UY2011 At end ") == 0
    assert bf.trailing_age("UY2011: end 44.7; one year later 77.6; two years later 65.8; three ") == 3
    assert bf.trailing_age("UY2011 At end 42.0 / one year later 72.1 / four ") == 4
    assert bf.trailing_age("UY2011 five ") == 5
    assert bf.labelled_ages(("of the five 62.6",)) == {}
    assert bf.labelled_ages(("end 42.0 vs 44.7",)) == {"42.0": {0}, "44.7": {0}}
    assert bf.labelled_ages(("UY2011; five 62.6",)) == {"62.6": {5}}
    pair = ("2011", 5, "", "62.6", "UY2011 of the five 62.6", "66.4", "UY2011 five 66.4")
    rows = (pair, _g("2012", "1.0", "2.0"), _g("2013", "3.0", "4.0"))
    t = "UY2011 of the five 62.6; UY2012 one year later 1.0; UY2013 one year later 3.0"
    t1 = "UY2011 five 66.4; UY2012 one year later 2.0; UY2013 one year later 4.0"
    assert _syn(t, t1, rows) == []
    assert len(_syn(t.replace("of the five", "four 60.0; five"), t1, (pair[:4] + ("UY2011 four 60.0; five 62.6",) + pair[5:],) + rows[1:])) == 3
    # the real entries that use bare labels still stand
    assert _moved("5820_2017", "X4") != [] and _moved("5820_2017", "Y4") != []


def test_the_readers_own_first_column_is_age_1_where_the_table_has_no_end_of_year_column():
    """6119/2016 and 3902/2023 print '12 months' / '1 year' as their first column: age 1, no age 0. The pairs take it so."""
    for key, rid in (("6119_2016", "X1"), ("6119_2016", "Y1"), ("3902_2023", "X3"), ("3902_2023", "Y3")):
        ev = bf.MOVED_CELLS[(key, rid)]
        assert min(p[1] for p in ev["pairs"]) == 1 and _moved(key, rid) != [], (key, rid)
        zero = tuple(p[:1] + (0,) + p[2:] for p in ev["pairs"])
        assert _moved(key, rid, evidence=dict(ev, pairs=zero)) == [], (key, rid)


# 7. the evidence file records the gate and the anchors; the register (a hashed input) holds none of it -----------------

def _evidence():
    with io.open(str(bf.EVIDENCE), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_evidence_file_equals_its_rebuild_and_the_check_mode_reports_both_files(tmp_path, monkeypatch, capsys):
    with io.open(str(bf.EVIDENCE), encoding="utf-8", newline="") as fh:
        assert fh.read() == bf.dumps(bf.build_evidence())
    assert bf.main([]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["data/fx_untranslated_excluded.json equals its rebuild",
                   "data/fx_untranslated_excluded_evidence.json equals its rebuild"]
    # an evidence file that differs, or is missing, fails the check; so does a register that differs
    for text in ("{}\n", None):
        fake = tmp_path / ("evidence.json" if text is not None else "missing" + os.sep + "evidence.json")
        if text is not None:
            fake.write_text(text, encoding="utf-8")
        monkeypatch.setattr(bf, "EVIDENCE", fake)
        assert bf.main([]) == 1
        out = capsys.readouterr().out
        assert "equals its rebuild" in out and "evidence.json differs from its rebuild" in out
        monkeypatch.undo()
    fake = tmp_path / "register.json"
    fake.write_text(json.dumps(_register()), encoding="utf-8")        # the same content, other bytes
    monkeypatch.setattr(bf, "REGISTER", fake)
    assert bf.main([]) == 1
    assert "register.json differs from its rebuild" in capsys.readouterr().out


def test_write_mode_writes_both_files_with_the_committed_bytes(tmp_path, monkeypatch, capsys):
    reg, ev = tmp_path / "register.json", tmp_path / "evidence.json"
    monkeypatch.setattr(bf, "REGISTER", reg)
    monkeypatch.setattr(bf, "EVIDENCE", ev)
    assert bf.main(["--write"]) == 0 and len(capsys.readouterr().out.splitlines()) == 2
    with io.open(os.path.join(HERE, "data", "fx_untranslated_excluded.json"), "rb") as fh:
        assert reg.read_bytes() == fh.read()
    with io.open(os.path.join(HERE, "data", "fx_untranslated_excluded_evidence.json"), "rb") as fh:
        assert ev.read_bytes() == fh.read()
    assert bf.main([]) == 0


def test_the_register_holds_no_evidence_and_the_build_refuses_one_that_would_put_some_in(monkeypatch):
    """The register is a hashed input of the run identifier: it holds neither the gate record, nor the provenance of the cells,
    nor the sentence about the gate, whichever way the builder is changed."""
    reg = _register()
    assert not bf.register_defects(reg) and bf.RULE_ADDITION not in reg["_rule"]
    assert "_moved_cells_gate" not in reg and all("moved_cells" not in e for b in ("excluded", "read_and_kept")
                                                  for e in reg[b].values())
    ev = _evidence()
    assert ev["_rule_addition"] == bf.RULE_ADDITION and "_moved_cells_gate" in bf.RULE_ADDITION
    assert set(ev["read_and_kept"]) == {k for k, e in reg["read_and_kept"].items() if e.get("reason") == "table_retranslated"}
    with io.open(os.path.join(HERE, "src", "run_analysis.py"), encoding="utf-8") as _fh:
        _run_analysis_text = _fh.read()
    assert "fx_untranslated_excluded_evidence" not in _run_analysis_text
    # a builder that leaves the provenance in the entries, puts the gate in, or adds the sentence to the rule
    monkeypatch.setattr(bf, "split_evidence", lambda out: (out, {}))
    with pytest.raises(SystemExit, match="the register would not be the loader-facing bytes: .*read_and_kept/"):
        bf.build()
    monkeypatch.undo()
    real = bf.split_evidence

    def with_gate(out):
        reg, evidence = real(out)
        return dict(reg, _moved_cells_gate=bf.GATE), evidence
    monkeypatch.setattr(bf, "split_evidence", with_gate)
    with pytest.raises(SystemExit, match="loader-facing bytes: _moved_cells_gate"):
        bf.build()
    monkeypatch.undo()
    monkeypatch.setattr(bf, "RULE", bf.RULE + " " + bf.RULE_ADDITION)
    with pytest.raises(SystemExit, match="loader-facing bytes: _rule holds the sentence"):
        bf.build()


def test_the_evidence_file_is_a_raw_byte_file_in_gitattributes_beside_the_register():
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert lines.index("data/fx_untranslated_excluded_evidence.json -text") == lines.index(
        "data/fx_untranslated_excluded.json -text") + 1


def test_the_evidence_file_says_what_the_cells_gate_proves_and_what_it_does_not():
    reg = _evidence()
    gate = reg["_moved_cells_gate"]
    assert gate == bf.GATE
    assert "quoted verbatim" in gate["proves"] and "underwriting year" in gate["proves"]
    assert "more than one unit in the last printed place" in gate["proves"]
    assert "That free-text notes can be parsed into a table" in gate["does_not_prove"]
    assert "rests on the two independent readers" in gate["does_not_prove"]
    hand = gate["checked_by_hand"]
    assert hand["readings"] == 20 and len(hand["reviews"]) == 2
    assert all(r.startswith("review ") and "23 October 2026" in r for r in hand["reviews"])
    assert "review 4" in hand["reviews"][0] and "review 5" in hand["reviews"][1]
    assert "_moved_cells_gate" in reg["_rule_addition"]
    assert "does not prove that free-text notes can be parsed into a table" in bf.__doc__


def test_the_evidence_file_records_how_each_table_retranslated_reading_was_tied_to_its_cells():
    reg = _register()
    evidence = _evidence()["read_and_kept"]
    others = total = 0
    for key, e in reg["read_and_kept"].items():
        if e.get("reason") != "table_retranslated":
            assert key not in evidence, key
            continue
        assert sorted(evidence[key]["moved_cells"]) == sorted(r["reader"] for r in e["readings"]), key
        for r in e["readings"]:
            rec = evidence[key]["moved_cells"][r["reader"]]
            ev = bf.MOVED_CELLS[(key, r["reader"])]
            assert rec["pages"] == list(ev["pages"]) and rec["pairs"] == len(ev["pairs"]) == rec["pairs_moved"], (key, r["reader"])
            assert rec["distinct_pairs"] == len({p[:3] for p in ev["pairs"]})
            assert sum(rec["sides"].values()) == 2 * rec["pairs"]
            assert set(rec["sides"]) <= {"labelled"} | set(bf.ANCHORS)
            assert (rec["other_arm_reader"] is not None) == ("other_arm" in rec["sides"])
            others += rec["sides"].get("other_arm", 0)
            total += 1
    assert total == 20 and others == 16
    # the four readings with a list anchored on the other arm, and the arm they name
    named = {(k, r): rec["other_arm_reader"] for k, e in evidence.items()
             for r, rec in e["moved_cells"].items() if rec["other_arm_reader"]}
    assert named == {("1301_2017", "Y1"): "X1", ("5678_2016", "Y1"): "X1", ("5820_2016", "X3"): "Y3",
                     ("5820_2017", "Y4"): "X4"}


def test_a_table_retranslated_record_whose_other_arm_no_longer_bears_its_entry_out_stops_the_build():
    """1301/2017 Y1's UY2013 and UY2014 sides stand on X1's reading: damage X1's cells and the build stops, naming both."""
    key = "1301_2017"
    reads = _reads_of(key)
    assert _kept_entry(key, reads)["reason"] == "table_retranslated"
    assert [r["reader"] for r in reads] == ["X1", "Y1"]
    reads[0]["table_retranslated_check"] = dict(reads[0]["table_retranslated_check"],
                                                cells_t=reads[0]["table_retranslated_check"]["cells_t"].replace("49.9", "49.8"))
    with pytest.raises(SystemExit, match=r"1301_2017.*X1, Y1"):
        _kept_entry(key, reads)
    assert bf.reader_moved_cells(key, reads, "Y1") is None


# --- review 6 (23 October 2026): series aliases, the series of a row, the anchors' series and sign, the tie of a quote -------

def test_series_aliases_are_one_series_and_a_cell_is_entered_once():
    """Review 6, C1, C1b and C1c: the two real cells of 6119/2016 Y1 (1492/2017 X5), entered again under the aliases ''
    and 'estimate' ('gross'), reached three 'different' cells without the reader's reason. '', 'estimate' and 'gross' are one
    series, a series is one of those or 'paid' or 'net', and two pairs on one cell are refused."""
    ev = dict(bf.MOVED_CELLS[("6119_2016", "Y1")])
    ev.pop("fewer_because")
    p0 = ev["pairs"][0]
    assert p0[2] == "gross" and _moved("6119_2016", "Y1", evidence=ev) == []
    for series in ("", "estimate", "gross"):
        again = ev["pairs"] + (p0[:2] + (series,) + p0[3:],)
        assert _moved("6119_2016", "Y1", evidence=dict(ev, pairs=again)) == [], series                   # C1, C1b
    ev2 = dict(bf.MOVED_CELLS[("1492_2017", "X5")])
    ev2.pop("fewer_because")
    q0 = ev2["pairs"][0]
    assert _moved("1492_2017", "X5", evidence=dict(ev2, pairs=ev2["pairs"] + (q0[:2] + ("gross",) + q0[3:],))) == []   # C1c
    # four pairs on three cells: the count is three, and the entry is refused for the pair that enters a cell twice
    assert len(_syn(_RT, _RT1, _ROWS)) == 2
    assert _syn(_RT, _RT1, _ROWS + (_g("2011", "57.8", "61.5", series="estimate"),)) == []
    assert _syn(_RT, _RT1, _ROWS + (_g("2011", "57.8", "61.5", series="gross"),)) == []
    # a series that is not one of the five
    for series in ("Gross", "ESTIMATE", "paid claims", None, 0):
        assert _syn(_RT, _RT1, _only(_ROWS, 0, _g("2011", "57.8", "61.5", series=series))) == [], series


def test_the_series_follows_the_row_the_snippet_is_in():
    """Review 6, A1 and A1b: 5678/2016 Y1's paid cells, trimmed of the 'paid ' that comes before the snippet in the text
    ('paid UY2014 19 / 515'), claimed as the series '' or 'estimate'. The series is tested against the snippet and the
    words before it back to the row's start; a paid pair may take its 'paid' from there."""
    ev = bf.MOVED_CELLS[("5678_2016", "Y1")]
    side = lambda snip: {"snippet": snip, "run_start": "UY2014 ", "first_age": 0, "quote": "12 months 441 -> 515"}  # noqa: E731
    trimmed = ("2014", 1, "", "515", side("UY2014 19 / 515"), "441", side("UY2014 16 / 441"))
    assert ev["pairs"][3][2] == "paid" and _moved("5678_2016", "Y1") != []
    assert _moved("5678_2016", "Y1", evidence=dict(ev, pairs=_only(ev["pairs"], 3, trimmed))) == []                  # A1
    assert _moved("5678_2016", "Y1", evidence=dict(ev, pairs=ev["pairs"] + (trimmed[:2] + ("estimate",) + trimmed[3:],))) == []   # A1b
    # the same trimmed cells as the paid series they are
    as_paid = _only(ev["pairs"], 3, trimmed[:2] + ("paid",) + trimmed[3:])
    assert len(_moved("5678_2016", "Y1", evidence=dict(ev, pairs=as_paid))) == 4
    # a paid or net pair with no paid or net anywhere in its row, a gross pair with one before it
    t = "UY2011 one year later 5.0; UY2012 one year later 6.0; paid UY2013 one year later 7.0"
    t1 = "UY2011 one year later 4.0; UY2012 one year later 5.0; paid UY2013 one year later 6.0"
    assert len(_syn(t, t1, (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"), _g("2013", "7.0", "6.0", series="paid")))) == 3
    for series in ("", "estimate", "gross", "net"):
        assert _syn(t, t1, (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"), _g("2013", "7.0", "6.0", series=series))) == [], series
    assert _syn(t, t1, (_g("2011", "5.0", "4.0", series="paid"), _g("2012", "6.0", "5.0"),
                        _g("2013", "7.0", "6.0", series="paid"))) == []


def test_the_other_arms_figure_is_taken_under_its_own_series():
    """Review 6, finding 3 (mutation N4): a figure the other arm gives as a paid cell does not anchor the same figure of
    ours as the gross estimate, nor the other way round; '', 'estimate' and 'gross' are one series."""
    key, quote = "9_2016", "age 2 is 26.0 vs 24.0"
    t_other = "UY2011 one year later 5.0; UY2012 one year later 6.0; %sUY2013: 20.0 / 24.0 / 26.0"
    t1_other = "UY2011 one year later 4.0; UY2012 one year later 5.0; %sUY2013: 18.0 / 22.0 / 24.0"

    def arm(series, word):
        side = lambda snip: {"snippet": snip, "run_start": word + "UY2013: ", "first_age": 0, "quote": quote}  # noqa: E731
        check = {"checked": True, "cells_t": "p1 " + t_other % word, "cells_t_minus_1": "p2 " + t1_other % word,
                 "result": "UY2013 " + word + quote}
        pairs = (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
                 ("2013", 2, series, "26.0", side(word + "UY2013: 20.0 / 24.0 / 26.0"), "24.0",
                  side(word + "UY2013: 18.0 / 22.0 / 24.0")))
        return {"key": key, "reader": "Y9", "check": check, "evidence": {"pages": (1, 2), "pairs": pairs}}

    def ours(series, word, other):
        side = lambda snip: {"snippet": snip, "run_start": word + "UY2013: ", "first_age": 0, "anchor": "other_arm"}  # noqa: E731
        check = {"checked": True, "cells_t": "p1 " + t_other % word, "cells_t_minus_1": "p2 " + t1_other % word}
        pairs = (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
                 ("2013", 1, series, "24.0", side(word + "UY2013: 20.0 / 24.0"), "22.0", side(word + "UY2013: 18.0 / 22.0")))
        return bf.moved_cell_pairs(check, {"pages": (1, 2), "pairs": pairs}, key, other)
    # the other arm reads the gross estimate, and so do we (in any of its three names)
    for mine in ("", "estimate", "gross"):
        for theirs in ("", "gross"):
            assert len(ours(mine, "", arm(theirs, ""))) == 3, (mine, theirs)
    # the other arm reads paid cells: we claim the same cells as gross, or it reads gross and we claim paid
    assert len(ours("paid", "paid ", arm("paid", "paid "))) == 3
    assert ours("", "paid ", arm("paid", "paid ")) == [] and ours("estimate", "paid ", arm("paid", "paid ")) == []
    assert ours("paid", "paid ", arm("", "paid ")) == []                  # the other arm calls its cells gross
    # the same numbers in a gross row and a paid row of the same year: the other arm gave the gross row only, and ours is the
    # paid row, whose snippet names paid
    both_t, both_t1 = t_other % "" + "; paid UY2013: 20.0 / 24.0", t1_other % "" + "; paid UY2013: 18.0 / 22.0"
    gross_arm = arm("", "")
    gross_arm["check"] = dict(gross_arm["check"], cells_t="p1 " + both_t, cells_t_minus_1="p2 " + both_t1)
    assert bf._evaluate(gross_arm["check"], gross_arm["evidence"], key) is not None
    paid = lambda snip: {"snippet": snip, "run_start": "paid UY2013: ", "first_age": 0, "anchor": "other_arm"}  # noqa: E731
    mine = {"checked": True, "cells_t": "p1 " + both_t, "cells_t_minus_1": "p2 " + both_t1}
    pairs = (_g("2011", "5.0", "4.0"), _g("2012", "6.0", "5.0"),
             ("2013", 1, "paid", "24.0", paid("paid UY2013: 20.0 / 24.0"), "22.0", paid("paid UY2013: 18.0 / 22.0")))
    assert bf.moved_cell_pairs(mine, {"pages": (1, 2), "pairs": pairs}, key, gross_arm) == []
    pairs = _only(pairs, 2, pairs[2][:2] + ("",) + pairs[2][3:4] + ({"snippet": "UY2013: 20.0 / 24.0", "run_start": "UY2013: ",
                                                                      "first_age": 0, "anchor": "other_arm"},)
                  + pairs[2][5:6] + ({"snippet": "UY2013: 18.0 / 22.0", "run_start": "UY2013: ", "first_age": 0,
                                      "anchor": "other_arm"},))
    assert len(bf.moved_cell_pairs(mine, {"pages": (1, 2), "pairs": pairs}, key, gross_arm)) == 3      # the gross row, as read


def test_a_negative_first_age_anchors_nothing():
    """Review 6, A5b: first_age -1 on a duplicated value (50.2 at ages 0 and 1) with the other arm labelled."""
    oth = {"checked": True,
           "cells_t": "p1 UY2011 end 50.2, one year later 50.2, two years later 49.0; UY2012 one year later 1.0; UY2013 one year later 2.0",
           "cells_t_minus_1": "p2 UY2011 end 50.2, one year later 50.2, two years later 48.0; UY2012 one year later 1.5; UY2013 one year later 2.5"}
    oev = {"pages": (1, 2), "pairs": (
        ("2011", 2, "", "49.0", "UY2011 end 50.2, one year later 50.2, two years later 49.0",
         "48.0", "UY2011 end 50.2, one year later 50.2, two years later 48.0"),
        _g("2012", "1.0", "1.5"), _g("2013", "2.0", "2.5"))}
    mine = {"checked": True, "cells_t": "p1 UY2011: 50.2, 50.2, 49.0; UY2012 one year later 1.0; UY2013 one year later 2.0",
            "cells_t_minus_1": "p2 UY2011: 50.2, 50.2, 48.0; UY2012 one year later 1.5; UY2013 one year later 2.5"}
    other = {"key": "1_2016", "reader": "Z", "check": oth, "evidence": oev}

    def run(first_t, first_t1, snip_t, snip_t1, age):
        side = lambda snip, first: {"snippet": snip, "run_start": "UY2011: ", "first_age": first, "anchor": "other_arm"}  # noqa: E731
        pairs = (("2011", age, "", "50.2", side(snip_t, first_t), "50.2", side(snip_t1, first_t1)),
                 _g("2012", "1.0", "1.5"), _g("2013", "2.0", "2.5"))
        return bf.moved_cell_pairs(mine, {"pages": (1, 2), "pairs": pairs}, "1_2016", other)
    assert bf.moved_cell_pairs(oth, oev, "1_2016") != []
    assert len(run(0, 0, "UY2011: 50.2", "UY2011: 50.2", 0)) == 2         # age 0, first_age 0: the other arm gives 50.2 there
    # first_age -1 puts the second 50.2 of the list at age 0, where the other arm has a 50.2 too
    assert run(-1, 0, "UY2011: 50.2, 50.2", "UY2011: 50.2", 0) == []
    assert run(-1, -1, "UY2011: 50.2, 50.2", "UY2011: 50.2, 50.2", 0) == []


def test_the_other_arms_vs_figure_is_the_other_reports_not_its_own_cell():
    """Review 6, A6: in 'UY2011 end 31.0 vs 30.0' the label belongs to 31.0; 30.0 is the other report's figure and is not
    assigned the age by the other arm's reading."""
    oth = {"checked": True,
           "cells_t": "p1 UY2011 end 30.0, one year later 55.0; UY2012 one year later 1.0; UY2013 one year later 2.0",
           "cells_t_minus_1": "p2 UY2011 end 31.0 vs 30.0, one year later 57.0; UY2012 one year later 1.5; UY2013 one year later 2.5"}
    oev = {"pages": (1, 2), "pairs": (
        ("2011", 1, "", "55.0", "UY2011 end 30.0, one year later 55.0", "57.0", "UY2011 end 31.0 vs 30.0, one year later 57.0"),
        _g("2012", "1.0", "1.5"), _g("2013", "2.0", "2.5"))}
    given = bf._assignments("1_2016", {"key": "1_2016", "reader": "Z", "check": oth, "evidence": oev})
    assert ("2011", "gross", 0, "31.0") in given["t1"] and ("2011", "gross", 0, "30.0") not in given["t1"]
    assert ("2011", "gross", 0, "30.0") in given["t"]
    # the labelled_ages of a quote still gives both figures of an 'x vs y' the label (the place_label of a reader's quote)
    assert bf.labelled_ages(("end 31.0 vs 30.0",)) == {"31.0": {0}, "30.0": {0}}


def test_a_quote_anchors_a_list_only_through_one_row_of_its_year_and_series():
    """Review 6, attack 9 D and attack 8 C2: the label sits after the UY2011 marker in the reader's text, but in another
    row ('2010 and prior:', 'total'), in another report ('in the 2014 report'), after a row break, or in another series
    ('paid'). It anchors nothing; the label of the list's own row does."""
    t1 = "p2 UY2011 end 31.0, one year later 57.0, two years later 60.0. UY2012 one year later 1.5. UY2013 one year later 2.5"
    rows = "UY2012 one year later 1.0. UY2013 one year later 2.0"

    def run(t, quote="two years later 55.0", **more):
        ev = {"pages": (1, 2), "pairs": (
            ("2011", 2, "", "55.0", {"snippet": "UY2011: 30.0 / 55.0", "run_start": "UY2011: ", "first_age": 1, "quote": quote},
             "60.0", "UY2011 end 31.0, one year later 57.0, two years later 60.0"),
            _g("2012", "1.0", "1.5"), _g("2013", "2.0", "2.5"))}
        return bf.moved_cell_pairs(dict({"checked": True, "cells_t": "p1 " + t, "cells_t_minus_1": t1}, **more), ev, "1_2016")
    # the control: the list, and the reader's words about it under its own marker (in the result)
    assert len(run("UY2011: 30.0 / 55.0. " + rows, result="UY2011 moved: two years later 55.0 was 60.0")) == 3
    for label, t in (
            ("another row, not year-marked", "UY2011: 30.0 / 55.0; 2010 and prior: two years later 55.0. " + rows),
            ("a total", "UY2011: 30.0 / 55.0; total two years later 55.0. " + rows),
            ("another report", "UY2011: 30.0 / 55.0 (in the 2014 report two years later 55.0). " + rows),
            ("another series", "UY2011: 30.0 / 55.0; paid two years later 55.0. " + rows),
            ("the whole account", "UY2011: 30.0 / 55.0; the whole account two years later 55.0. " + rows),
            ("after a sentence", "UY2011: 30.0 / 55.0. Two years later 55.0. " + rows)):
        assert run(t) == [], label
    # the same words in prose fields (attack 8 C2c, C2d)
    plain = "UY2011: 30.0 / 55.0. " + rows
    assert run(plain, comparison="UY2011 moved: the 2015 report's two years later 55.0 was 57.0") == []
    assert run(plain, comparison="UY2011 moved: in the 2015 report two years later 55.0 was 57.0") == []
    assert run(plain, comparison="UY2011 total: two years later 55.0") == []
    assert run(plain, comparison="UY2011 paid: two years later 55.0") == []
    # and a paid list is anchored by words of its own series, not by the gross estimate's
    assert len(run(plain, comparison="UY2011 moved: two years later 55.0")) == 3


def test_a_figure_quoted_from_another_report_inside_parentheses_is_not_a_cell():
    """Review 6, A2: the year t cells quote the 2014 report's figures in parentheses; identical tables, and the t side takes
    the quoted figures as year t cells."""
    c = {"checked": True,
         "cells_t": "2016 report p40: UY2011 one year later 61.5 (as printed in the 2014 report: UY2011 one year later 70.0); "
                    "UY2012 one year later 50.0 (2014 report: UY2012 one year later 58.0); UY2013 one year later 60.0 "
                    "(2014 report: UY2013 one year later 66.0)",
         "cells_t_minus_1": "2015 report p41: UY2011 one year later 61.5; UY2012 one year later 50.0; UY2013 one year later 60.0"}
    pairs = tuple(_g(uy, a, b) for uy, a, b in (("2011", "70.0", "61.5"), ("2012", "58.0", "50.0"), ("2013", "66.0", "60.0")))
    assert bf.moved_cell_pairs(c, {"pages": (40, 41), "pairs": pairs}, "1_2016") == []
    # the figures outside the parentheses are the report's own cells
    own = tuple(_g(uy, a, a) for uy, a in (("2011", "61.5"), ("2012", "50.0"), ("2013", "60.0")))
    assert bf.moved_cell_pairs(c, {"pages": (40, 41), "pairs": own}, "1_2016") == []        # equal: nothing moved, but accepted
    assert bf._evaluate(c, {"pages": (40, 41), "pairs": own}, "1_2016") is not None
    # the limits the gate admits (the evidence file names them)
    does_not = _evidence()["_moved_cells_gate"]["does_not_prove"]
    assert "attack 9 D" in does_not and "attack A2" in does_not and "review 6" in does_not
