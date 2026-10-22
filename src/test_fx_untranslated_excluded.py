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
            assert all(bf.shows_moved_cells(r["table_retranslated_check"], bf.MOVED_CELLS.get((key, r["reader"])))
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
            "cells_t": "p45 UY2012 one year later 250,000; UY2013 one year later 260,000; UY2014 one year later 270,000",
            "cells_t_minus_1": "p45 UY2012 one year later 229,609; UY2013 one year later 239,000; UY2014 one year later 249,000"}
    # without the cells in MOVED_CELLS the build stops; with them the record is table_retranslated
    with pytest.raises(SystemExit, match="457_2015"):
        _kept_entry("457_2015", reads)
    cells = {"pages": (45, 45), "pairs": tuple(
        (uy, 1, "", a, "UY%s one year later %s" % (uy, a), b, "UY%s one year later %s" % (uy, b))
        for uy, a, b in (("2012", "250,000", "229,609"), ("2013", "260,000", "239,000"), ("2014", "270,000", "249,000")))}
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
_CHECK = {"checked": True, "cells_t": _T, "cells_t_minus_1": _T1}
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


def test_identical_tables_with_two_cells_of_one_table_paired_are_refused():
    """Attack 1 of the review: the year t-1 text is the year t text, and the entry pairs two cells of that one table (the
    end of the underwriting year with one year later). Both snippets are the reader's own, in the right text and under
    the right year; the age of the second does not match the pair's, so the entry is refused."""
    check = _check_of("5820_2016", "X3")
    check["cells_t_minus_1"] = check["cells_t"].replace("2016 report p42", "2015 report p25")
    honest = bf.MOVED_CELLS[("5820_2016", "X3")]
    assert bf.moved_cell_pairs(_check_of("5820_2016", "X3"), honest) != []
    assert bf.moved_cell_pairs(check, honest) == []
    misaligned = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "77.6", "UY2011: end of UY 44.7, one year later 77.6"),) * 3}
    assert bf.moved_cell_pairs(check, misaligned) == []
    # the same cell twice is not a move: the figures are equal
    twice = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "44.7", "UY2011: end of UY 44.7"),) * 3}
    assert bf.moved_cell_pairs(check, twice) == []
    # a positional side whose place in the list is not the pair's age
    pos = {"pages": (42, 25), "pairs": (
        ("2011", 0, "", "44.7", "UY2011: end of UY 44.7", "66.9",
         {"snippet": "UY2011: 38.7, 66.9", "run_start": "UY2011: ", "first_age": 0, "quote": "end of UY 44.7"}),) * 3}
    assert bf.moved_cell_pairs(_check_of("5820_2016", "X3"), pos) == []


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
    small = {"checked": True, "cells_t": "p1 UY2014: 12 months 12", "cells_t_minus_1": "p1 UY2014: 12 months 24"}
    chk = {"pages": (1, 1), "pairs": (("2014", 1, "", "12", "UY2014: 12 months 12", "24", "UY2014: 12 months 24"),) * 3}
    assert bf.moved_cell_pairs(small, chk) == [("2014", 1, "12", "24")] * 3


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
        assert len(bf.moved_cell_pairs(real, ev)) >= 1, (key, rid)
        assert len(ev["pairs"]) >= bf.MIN_PAIRS or ev.get("fewer_because"), (key, rid)
        same = dict(real, cells_t_minus_1=real["cells_t"].replace("p%d" % ev["pages"][0], "p%d" % ev["pages"][1]))
        assert bf.moved_cell_pairs(same, ev) == [], (key, rid, "identical tables")
        swapped = dict(real, cells_t=real["cells_t_minus_1"], cells_t_minus_1=real["cells_t"])
        assert bf.moved_cell_pairs(swapped, dict(ev, pages=ev["pages"][::-1])) == [], (key, rid, "swapped")
        for i, p in enumerate(ev["pairs"]):
            for pos, val in ((1, p[1] + 1), (0, str(int(p[0]) + 1))):
                mutated = dict(ev, pairs=ev["pairs"][:i] + (p[:pos] + (val,) + p[pos + 1:],) + ev["pairs"][i + 1:])
                assert bf.moved_cell_pairs(real, mutated) == [], (key, rid, i, pos)
            # either snippet from the other report
            for a, b in ((4, 6), (6, 4)):
                sw = list(p)
                sw[a], sw[b] = p[b], p[a]
                mutated = dict(ev, pairs=ev["pairs"][:i] + (tuple(sw),) + ev["pairs"][i + 1:])
                assert bf.moved_cell_pairs(real, mutated) == [], (key, rid, i, "sides swapped")


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
    ev = {"pages": (1, 2), "pairs": (
        ("2011", 0, "", "10.0", "UY2011: end of UY 10.0", "9.0", side(1, ["9.0"], text="UY2011: ", start="UY2011: ")),
        ("2011", 1, "", "12.0", "UY2011: end of UY 10.0, one year later 12.0", "11.0",
         side(2, ["9.0", "11.0"], text="UY2011: ", start="UY2011: ")),
        ("2012", 2, "", "26.0", side(3, t), "24.0", side(3, t1)))}
    assert len(bf.moved_cell_pairs(chk, ev)) == 3
    ok = ev["pairs"][2]
    for label, change in (
            ("place 3 for age 2", ((1, 3),)),
            ("figure of the next place", ((3, "27.0"), (4, side(4, t)))),
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
           "cells_t_minus_1": "p1 UY2014: end of UY 90, 12 months later 110; cumulative paid at end of UY 9; at 12 months 18"}
    pairs = (
        ("2014", 0, "estimate", "100", "UY2014: end of UY 100", "90", "UY2014: end of UY 90"),
        ("2014", 1, "estimate", "120", "UY2014: end of UY 100, 12 months later 120", "110",
         "UY2014: end of UY 90, 12 months later 110"),
        ("2014", 1, "paid", "20", "UY2014: end of UY 100, 12 months later 120; cumulative paid at end of UY 10; at 12 months 20",
         "18", "UY2014: end of UY 90, 12 months later 110; cumulative paid at end of UY 9; at 12 months 18"))
    ev = {"pages": (1, 1), "pairs": pairs}
    assert len(bf.moved_cell_pairs(chk, ev)) == 3
    # a paid pair whose snippets are the estimate cells (12 months later 120 / 110), an estimate pair that names paid
    assert bf.moved_cell_pairs(chk, _pair((2, "paid"), index=1, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "net"), index=1, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "estimate"), index=2, evidence=ev)) == []
    assert bf.moved_cell_pairs(chk, _pair((2, "gross"), index=2, evidence=ev)) == []


def test_fewer_than_three_pairs_need_the_readers_own_reason():
    """The readers' brief asks for at least three cells: an entry with fewer carries the reader's words for it."""
    few = dict(_EVIDENCE, pairs=_EVIDENCE["pairs"][:2])
    assert bf.moved_cell_pairs(_CHECK, few) == []
    reason = "UY2011 at end of underwriting year 65.0"
    assert bf.moved_cell_pairs(_CHECK, dict(few, fewer_because=reason)) == _MOVED
    for bad in ("only one underwriting year precedes the year t-1", "", "   ", None, ()):
        assert bf.moved_cell_pairs(_CHECK, dict(few, fewer_because=bad)) == [], bad
    # a real entry: 1492/2017 holds two pairs, and loses them with the reason removed or altered
    for k in (("1492_2017", "X5"), ("1492_2017", "Y5"), ("6119_2016", "Y1")):
        ev = bf.MOVED_CELLS[k]
        assert len(ev["pairs"]) == 2 and ev["fewer_because"]
        real = _check_of(*k)
        assert bf.moved_cell_pairs(real, ev) != []
        assert bf.moved_cell_pairs(real, {x: y for x, y in ev.items() if x != "fewer_because"}) == []
        assert bf.moved_cell_pairs(real, dict(ev, fewer_because=ev["fewer_because"] + " (and more)")) == []
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
            moved = bf.moved_cell_pairs(r["table_retranslated_check"], ev)
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
