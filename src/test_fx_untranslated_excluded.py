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
    assert set(reg["excluded"]) == set(EXCLUDED) and set(reg["read_and_kept"]) == set(KEPT) | round2
    assert len(round2) == 97 and not round2 & (set(KEPT) | set(EXCLUDED))
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
    assert set(ra.load_fx_untranslated_excluded(p)) == set(EXCLUDED)


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
    # round 2: the 97 records read twice and kept, the four undeterminable ones among them, are in the primary's sample
    for key in _register()["_population"]["round2"]["records_are"]:
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
    assert counters["fx_untranslated_excluded"] == 4


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
    assert len(keys) == 110 and len(set(keys)) == 110      # 4 excluded, 9 kept in round 1 and 97 kept in round 2
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
            assert all(bf.shows_moved_cells(r["table_retranslated_check"], r["note"]) for r in reads), key
            assert all(r["verdict"] == "keep" for r in reads), key
        else:
            n_undet += 1
            assert e["reason"] == "undeterminable_kept", key
            assert (any(r["verdict"] == "undeterminable" for r in reads)
                    or not all(bf.comparison_made(r["table_retranslated_check"]) for r in reads)), key
    assert (n_moved, n_undet) == (10, 4)


def test_a_table_retranslated_entry_needs_each_readers_check_to_show_moved_cells():
    """Mutation check: 1301/2016 with one reader's check saying the cells did not move (or saying nothing about them)
    stops the build, for either reader."""
    key = "1301_2016"
    assert _kept_entry(key, _reads_of(key))["reason"] == "table_retranslated"
    for which in (0, 1):
        for check, note in (({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40", "result": "cells not moved"}, ""),
                            ({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40"}, "the table is not retranslated"),
                            ({"checked": True, "cells_t": "p40", "cells_t_minus_1": "p40"}, "")):
            reads = _reads_of(key)
            reads[which]["table_retranslated_check"], reads[which]["note"] = check, note
            with pytest.raises(SystemExit, match=key):
                _kept_entry(key, reads)


def test_the_reason_undeterminable_kept_is_derived_not_typed():
    """Mutation check: 457/2015 read with both checks comparing cells that moved is table_retranslated (the reasons follow
    the readings, not a list of keys), and 1301/2016 with a check that compared no cells is undeterminable and, having no
    note of the session's, stops the build."""
    reads = _reads_of("457_2015")
    assert _kept_entry("457_2015", reads)["reason"] == "undeterminable_kept"
    for r in reads:
        r["verdict"] = "keep"
        r["table_retranslated_check"] = {"checked": True, "cells_t": "p45", "cells_t_minus_1": "p45",
                                         "result": "moved (retranslated): 229,609 -> 250,000"}
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


@pytest.mark.parametrize("text,want", [
    ("moved (retranslated): every cell is 3 to 6% lower", True),
    ("Cells moved: UY2011 age 1 is 57.8 vs 61.5", True),
    ("(cells moved by 8% to 12%; not identical, so retranslated)", True),
    ("the table is not retranslated", False),
    ("no cells moved between the reports", False),
    ("cells equal in both reports", False),
    ("", False)])
def test_shows_moved_cells_reads_a_sentence_and_its_negation(text, want):
    assert bf.shows_moved_cells({"checked": True, "result": text}) is want


def test_a_check_that_compared_no_cells_shows_none():
    for checked in (False, "partly", "no: cannot compare", None):
        assert bf.shows_moved_cells({"checked": checked, "result": "moved (retranslated)"}) is False
    assert bf.shows_moved_cells(None) is False and bf.shows_moved_cells("moved") is False
    assert bf.comparison_made({"checked": "yes, 2017 against 2016"}) and bf.comparison_made({"checked": True})
