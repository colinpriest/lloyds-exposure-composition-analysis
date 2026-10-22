r"""The primary outcome (the owner's decision, 22 October 2026, option c) and the 672 sensitivity.

The paper's outcome is Equation (1)'s gross movement over the underwriting years u <= t-2. The extraction's two sign-only
precedence rules (the provisions sign-disagreement override, and the model-agreement veto) replaced a printed gross
triangle's mature-cohort figure with a broader one because the two had opposite signs. The owner decided that a valid
mature-cohort triangle figure is never replaced for its sign alone, that the consistently scoped sample is the primary,
and that the 672-record construction stays reproducible as a sensitivity. data/mature_cohort_figures.json holds every
displaced gross triangle of the corpus (built by src/build_mature_cohort_figures.py from the stored grids, the
extraction's estimator at the pin, and the readings of 22 October 2026 in
results/extraction_error_rate/mature-cohort/); the loader adopts
its figures under ANALYSIS_CONFIG["outcome"] "mature_cohort", and "precedence_672" ignores it.

These tests hold the register to the corpus (every displaced gross triangle is in it, with a figure or a reason), to
its rebuild and to the readings; the loader's guard to every block; the primary to the adjudication's 653 records and
figures; and the sensitivity to the 672.

Run:  python -m pytest src/test_mature_cohort_outcome.py -q
"""
import copy
import csv
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402
import build_mature_cohort_figures as bm  # noqa: E402

EVIDENCE = os.path.join(HERE, "results", "extraction_error_rate", "mature-cohort")


def _json(*parts):
    with io.open(os.path.join(HERE, *parts), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def register():
    return {k: v for k, v in _json("data", "mature_cohort_figures.json").items() if not k.startswith("_")}


@pytest.fixture(scope="module")
def decisions():
    with io.open(os.path.join(EVIDENCE, "decisions.csv"), encoding="utf-8", newline="") as fh:
        return {r["key"]: r for r in csv.DictReader(fh)}


def _working_sample(records):
    return {"%s_%s" % (r["syndicate"], r["year"]): r for r in records
            if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["hhi"] is not None
            and r["pyd_basis"] == "gross"}


@pytest.fixture(scope="module")
def loaded():
    out = {}
    for outcome in ra.OUTCOMES:
        records, counters, log, files = ra.load_and_classify(outcome)
        status = {}
        for e in log:
            status.setdefault(e["file"][len("syndicate_"):-len(".json")], e)
        out[outcome] = {"records": records, "counters": counters, "log": log, "status": status,
                        "by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records},
                        "ws": _working_sample(records)}
    return out


# --- the register, against the corpus ---------------------------------------------------------------------------------

def test_every_displaced_gross_triangle_of_the_corpus_is_in_the_register_with_a_figure_or_a_reason(register):
    """Driven by the corpus, not by the register: every record with a block whose stored gross RAG triangle a
    sign-only precedence rule displaced (bm.population) has an entry, and every entry is such a record."""
    pop = bm.population()
    assert len(pop) >= 100
    assert sorted(set(pop) - set(register)) == []
    assert sorted(set(register) - set(pop)) == []
    for key, entry in register.items():
        assert (entry["figure_m"] is not None) != (entry.get("reason") is not None), key
        if entry["figure_m"] is None:
            assert entry["reason"] in ra.MATURE_COHORT_NO_FIGURE_REASONS and entry["reason_evidence"].strip(), key
        assert entry["displaced"]["blocks"] == pop[key], key


def test_the_corpus_rule_reads_both_precedence_rules_and_only_gross_triangles():
    tri = {"type": "gross", "underwriting_years": [2018, 2019, 2020]}
    assert bm.displaced_by({"_rag_triangle": tri, "_pyd_route": {"source": "rag_provisions"}}) == ("sign_override",)
    assert bm.displaced_by({"_rag_triangle": tri, "_pyd_route": {"source": "rag_provisions_text"}}) == (
        "sign_override",)
    veto = "[RAG PYD NOT APPLIED: deterministic figure +1.000m has the opposite sign]"
    assert bm.displaced_by({"_rag_triangle": tri, "data_quality_notes": veto,
                            "_pyd_route": {"source": "model_reading"}}) == ("veto",)
    assert bm.displaced_by({"_rag_triangle": tri, "data_quality_notes": veto.replace("RAG", "CODE")}) == ("veto",)
    assert bm.displaced_by({"_rag_triangle": dict(tri, type="net"), "_pyd_route": {"source": "rag_provisions"}}) == ()
    assert bm.displaced_by({"_rag_triangle": dict(tri, underwriting_years=[]),
                            "_pyd_route": {"source": "rag_provisions"}}) == ()
    assert bm.displaced_by({"_rag_triangle": tri, "_pyd_route": {"source": "rag_triangle"}}) == ()


def test_the_register_loads_with_its_evidence_and_counts(register):
    loaded = ra.load_mature_cohort_figures()
    assert loaded == register
    figures = [k for k, e in register.items() if e["figure_m"] is not None]
    assert len(register) == 110 and len(figures) == 85
    by_status = {}
    for e in register.values():
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    assert by_status == {"primary": 82, "excluded_takeon_not_development": 3, "no_figure": 25}


def test_the_register_equals_its_rebuild_from_the_pinned_extraction():
    """The figures are the extraction's own estimator's, read from the pinned commit (build_mature_cohort_figures.py);
    the rest of each entry is rebuilt from the committed evidence. Skipped only when no extraction checkout is there."""
    if not os.path.exists(os.path.join(bm.extraction_root(), "test_gemini.py")):
        pytest.skip("no extraction repository at %s: set LLOYDS_EXTRACTION_REPO to the extraction repository, or "
                    "this cross-repository check does not run" % bm.extraction_root())
    with io.open(str(bm.REGISTER), encoding="utf-8", newline="") as fh:
        assert fh.read() == bm.dumps(bm.build())


def test_each_figure_is_its_readings_and_its_decision(register, decisions):
    """A figure entry carries every reading of 22 October 2026 for the record, each giving the figure from the printed
    table (the readings files), and the adjudication's figure (decisions.csv)."""
    files = {rid: _json("results", "extraction_error_rate", "mature-cohort", "readings", "%s.json" % rid)
             for rid in bm.READERS}
    for key, entry in register.items():
        if entry["figure_m"] is None:
            continue
        own = [r for r in entry["readings"] if r["kind"] == "reading"]
        assert own, key
        assert sorted(r["reader"] for r in own) == sorted(rid for rid in bm.READERS if key in files[rid]), key
        for r in own:
            assert abs(float(files[r["reader"]][key]["recomputed_mature_figure_m"]) - entry["figure_m"]) <= 0.0015
            assert r["cells"] == files[r["reader"]][key]["cells"]
        dec = decisions[key]
        assert dec["key"] == key
        if dec["figure_used_report_ccy_m"]:
            assert abs(float(dec["figure_used_report_ccy_m"]) - entry["figure_m"]) <= 0.0006, key
        assert entry["decision"].startswith("decision of the Claude analysis session, 22 October 2026"), key
        assert "owner's decision, 22 October 2026 (option c)" in entry["decision"], key
    assert set(k for k, e in register.items() if e["figure_m"] is not None) | {"6134_2023"} == set(decisions)


def test_where_one_reader_read_a_record_the_second_reading_is_named_for_what_it_is(register):
    kinds = {}
    for key, e in register.items():
        if e["figure_m"] is None:
            continue
        ks = tuple(sorted(r["kind"] for r in e["readings"]))
        kinds[ks] = kinds.get(ks, 0) + 1
        for r in e["readings"]:
            if r["kind"] == "extraction_table_read":
                assert "stored grid" in r["reader"] and "compute_pyd_from_triangle" in r["reader"]
                assert sum(1 for x in e["readings"] if x["kind"] == "reading") == 1, key
    assert sum(n for ks, n in kinds.items() if "extraction_table_read" in ks) == 43


# --- the register's contract ----------------------------------------------------------------------------------------

def _figure_entry(register):
    return copy.deepcopy(register["382_2021"])


@pytest.mark.parametrize("change", [
    "no-readings", "one-reading", "no-reader-reading", "reading-off-figure", "reading-no-pages", "reading-no-cells",
    "reading-bad-kind", "bad-displacer", "no-displaced-figure", "figure-kind", "net", "no-years", "no-pages",
    "no-quote", "no-decision", "text-figure", "no-figure-key"])
def test_the_register_refuses_an_entry_without_its_evidence(tmp_path, register, change):
    e = _figure_entry(register)
    if change == "no-readings":
        e["readings"] = []
    elif change == "one-reading":
        e["readings"] = e["readings"][:1]
    elif change == "no-reader-reading":
        for r in e["readings"]:
            r["kind"] = "extraction_table_read"
    elif change == "reading-off-figure":
        e["readings"][1]["figure_m"] = e["figure_m"] + 0.01
    elif change == "reading-no-pages":
        e["readings"][0]["pages"] = []
    elif change == "reading-no-cells":
        e["readings"][1]["cells"] = " "
    elif change == "reading-bad-kind":
        e["readings"][1]["kind"] = "hearsay"
    elif change == "bad-displacer":
        e["displaced"]["by"] = "loss_ratio"
    elif change == "no-displaced-figure":
        e["displaced"]["figure_m"] = None
    elif change == "figure-kind":
        e["figure_kind"] = "stated"
    elif change == "net":
        e["basis"] = "net"
    elif change == "no-years":
        e["triangle"]["underwriting_years"] = []
    elif change == "no-pages":
        e["pages"] = []
    elif change == "no-quote":
        e["quote"] = ""
    elif change == "no-decision":
        e["decision"] = ""
    elif change == "text-figure":
        e["figure_m"] = "20.409"
    elif change == "no-figure-key":
        del e["figure_m"]
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"9999_2021": e}), encoding="utf-8")
    with pytest.raises(ValueError, match="9999_2021"):
        ra.load_mature_cohort_figures(p)
    p.write_text(json.dumps({"9999_2021": _figure_entry(register)}), encoding="utf-8")
    assert set(ra.load_mature_cohort_figures(p)) == {"9999_2021"}


@pytest.mark.parametrize("change", ["no-reason", "unknown-reason", "a-figure-kind", "aggregated-without-readings"])
def test_the_register_refuses_an_entry_without_a_figure_and_its_reason(tmp_path, register, change):
    e = copy.deepcopy(register["6134_2023" if change == "aggregated-without-readings" else "3002_2017"])
    if change == "no-reason":
        del e["reason"]
    elif change == "unknown-reason":
        e["reason"] = "the sign looked wrong"
    elif change == "a-figure-kind":
        e["figure_kind"] = "triangle"
    else:
        e["readings"] = e["readings"][:1]
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"9999_2021": e}), encoding="utf-8")
    with pytest.raises(ValueError, match="9999_2021"):
        ra.load_mature_cohort_figures(p)


# --- apply_mature_cohort_figure: the guard, on every block -----------------------------------------------------------

def _record(key):
    return _json("pdf_extraction", "syndicate_%s.json" % key)


@pytest.mark.parametrize("key", ["382_2024", "382_2021"], ids=["sign-override", "veto"])
def test_the_figure_is_applied_with_its_route_percentage_and_direction(register, key):
    data = _record(key)
    blocks = [data["models"][m] for m in sorted(data["models"])]
    cm = blocks[0]
    entry = register[key]
    out = ra.apply_mature_cohort_figure(cm, entry, key, blocks=blocks)
    assert out is not cm and cm["prior_year_development_gbp_m"] == entry["displaced"]["figure_m"]
    assert out["prior_year_development_gbp_m"] == entry["figure_m"]
    assert out["prior_year_development_pct"] == pytest.approx(100 * entry["figure_m"] / cm["opening_reserves_gbp_m"])
    assert out["_pyd_route"]["source"] == ra.MATURE_COHORT_SOURCE and out["_pyd_route"]["basis"] == "gross"
    assert out["_pyd_route"]["displaced_by"] == entry["displaced"]["by"]
    assert out["direction"] == ("strengthening" if entry["figure_m"] > 0 else "release")
    assert "MATURE-COHORT FIGURE" in out["data_quality_notes"]
    assert ra.pyd_basis(out, key, {key: {"basis": "net", "source": "x"}}) == (
        "gross", "mature-cohort-figure:register", "")
    assert ra.pyd_cohort_scope(out) == (ra.COHORT_ENFORCED, "triangle")
    assert ra.figure_route(out) is out["_pyd_route"] and ra.declares_provision_movement(out) is None


def _defects():
    return {
        "no-triangle": lambda b: b.pop("_rag_triangle"),
        "net-triangle": lambda b: b["_rag_triangle"].update(type="net"),
        "other-years": lambda b: b["_rag_triangle"].update(underwriting_years=b["_rag_triangle"][
            "underwriting_years"][1:]),
        "other-page": lambda b: b["_rag_triangle"].update(source_page=(b["_rag_triangle"]["source_page"] or 0) + 1),
        "triangle-stands": lambda b: b.update(_pyd_route={"source": "rag_triangle", "triangle_type": "gross"}),
        "code-triangle-stands": lambda b: b.update(_pyd_route={"source": "code_triangle"}),
    }


@pytest.mark.parametrize("which", ["adopted", "other"])
@pytest.mark.parametrize("defect", sorted(_defects()))
@pytest.mark.parametrize("key", ["382_2024", "382_2021"], ids=["sign-override", "veto"])
def test_the_guard_refuses_unless_every_block_shows_the_displaced_gross_triangle(register, key, defect, which):
    data = _record(key)
    blocks = [data["models"][m] for m in sorted(data["models"])]
    target = blocks[0] if which == "adopted" else blocks[1]
    _defects()[defect](target)
    with pytest.raises(ValueError, match=r"%s's figure displaced by" % key):
        ra.apply_mature_cohort_figure(blocks[0], register[key], key, blocks=blocks)


def test_the_guard_reads_the_rule_that_displaced_the_triangle(register):
    # sign override: the provisions route must be there
    data = _record("382_2024")
    blocks = [data["models"][m] for m in sorted(data["models"])]
    blocks[1]["_pyd_route"] = {"source": "model_reading"}
    with pytest.raises(ValueError, match="not the sign-disagreement override's provisions route"):
        ra.apply_mature_cohort_figure(blocks[0], register["382_2024"], "382_2024", blocks=blocks)
    # veto: the veto note must record this triangle's figure
    data = _record("382_2021")
    blocks = [data["models"][m] for m in sorted(data["models"])]
    blocks[1]["data_quality_notes"] = blocks[1]["data_quality_notes"].replace("+20.409m", "+20.909m")
    with pytest.raises(ValueError, match="notes record no veto of the RAG figure"):
        ra.apply_mature_cohort_figure(blocks[0], register["382_2021"], "382_2021", blocks=blocks)
    # the displaced figure must be the adopted block's
    data = _record("382_2021")
    blocks = [data["models"][m] for m in sorted(data["models"])]
    blocks[0]["prior_year_development_gbp_m"] = -9.0
    with pytest.raises(ValueError, match="not the displaced"):
        ra.apply_mature_cohort_figure(blocks[0], register["382_2021"], "382_2021", blocks=blocks)


def test_the_records_blocks_are_required(register):
    data = _record("382_2021")
    cm = data["models"][sorted(data["models"])[0]]
    with pytest.raises(TypeError):
        ra.apply_mature_cohort_figure(cm, register["382_2021"], "382_2021")
    with pytest.raises(ValueError, match="blocks=None"):
        ra.apply_mature_cohort_figure(cm, register["382_2021"], "382_2021", blocks=None)
    with pytest.raises(ValueError, match="without it"):
        ra.apply_mature_cohort_figure(cm, register["382_2021"], "382_2021", blocks=[dict(cm)])
    with pytest.raises(ValueError, match="no figure to apply"):
        ra.apply_mature_cohort_figure(cm, register["3002_2017"], "382_2021", blocks=[cm])


def test_every_committed_figure_passes_the_guard_on_every_block(register):
    for key, entry in register.items():
        if entry["figure_m"] is None:
            continue
        data = _record(key)
        blocks = [b for _m, b in sorted(data["models"].items()) if isinstance(b, dict)]
        assert len(blocks) == 2, key
        for b in blocks:
            assert ra.mature_cohort_block_defect(b, entry) is None, (key, ra.mature_cohort_block_defect(b, entry))


@pytest.mark.parametrize("reason,mutate,words", [
    ("confirmed_figure_register", None, "has no entry for it"),
    ("triangle_figure_stands", lambda cm: cm.update(_pyd_route={"source": "model_reading"}), "a triangle's figure"),
    ("no_mature_cohort", lambda cm: cm.update(_rag_triangle={"underwriting_years": [2015, 2016]}),
     "has no mature cohort")])
def test_a_reason_the_record_contradicts_stops_the_run(reason, mutate, words):
    cm = {"_pyd_route": {"source": "code_triangle"}, "_rag_triangle": {"underwriting_years": [2019, 2020]}}
    if mutate:
        mutate(cm)
    with pytest.raises(ValueError, match=words):
        ra.check_no_figure_reason("9999_2020", {"reason": reason}, {}, cm, {})


def test_the_committed_reasons_hold_on_their_records(register):
    confirmed = ra.load_pyd_confirmed_figures()
    for key, entry in register.items():
        if entry["figure_m"] is not None:
            continue
        data = _record(key)
        cm = data["models"][bm.canonical_key(data)]
        ra.check_no_figure_reason(key, entry, data, cm, confirmed)
        if entry["reason"] == "confirmed_figure_register":
            assert key in confirmed


# --- the take-on registers' entries for the mature-cohort figure -----------------------------------------------------

def test_take_on_entries_for_the_mature_cohort_figure_apply_only_under_the_primary():
    base, takeons = ra.load_takeon_base(), ra.load_takeon_register()
    scoped_base = sorted(k for k, v in base.items() if v.get(ra.FIGURE_ROUTE_KEY))
    scoped_takeons = sorted(k for k, v in takeons.items() if v.get(ra.FIGURE_ROUTE_KEY))
    assert scoped_base == ["1686_2021", "3000_2016", "4000_2022"]
    assert scoped_takeons == ["1084_2022", "1861_2020", "2001_2022"]
    for reg, scoped in ((base, scoped_base), (takeons, scoped_takeons)):
        assert set(ra.scoped_to_outcome(reg, ra.MATURE_COHORT_OUTCOME)) == set(reg)
        assert set(ra.scoped_to_outcome(reg, ra.PRECEDENCE_672_OUTCOME)) == set(reg) - set(scoped)
    for key in scoped_base:
        e = base[key]
        assert e["takeon_m"] >= 0.05 * e["opening_reserves_m"] and len(e["readings"]) == 2
        assert e["decision"].startswith("decision of the Claude analysis session, 22 October 2026")


def test_an_entry_naming_the_mature_cohort_figure_is_refused_for_a_block_without_it(tmp_path):
    with pytest.raises(ValueError, match="describes the step of the mature_cohort_triangle figure"):
        ra.require_figure_route({"_pyd_route": {"source": "model_reading"}},
                                {ra.FIGURE_ROUTE_KEY: ra.MATURE_COHORT_SOURCE}, "9999_2020", "register")
    ra.require_figure_route({"_pyd_route": {"source": ra.MATURE_COHORT_SOURCE}},
                            {ra.FIGURE_ROUTE_KEY: ra.MATURE_COHORT_SOURCE}, "9999_2020", "register")
    ra.require_figure_route({"_pyd_route": {"source": "model_reading"}}, {}, "9999_2020", "register")
    entry = dict(ra.load_takeon_register()["1084_2022"], figure_route="rag_triangle")
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"9999_2022": entry}), encoding="utf-8")
    with pytest.raises(ValueError, match="9999_2022"):
        ra.load_takeon_register(p)


# --- the loader under each outcome ----------------------------------------------------------------------------------

def test_the_outcome_is_the_primary_by_default_and_must_be_known():
    assert ra.ANALYSIS_CONFIG["outcome"] == ra.MATURE_COHORT_OUTCOME == ra.OUTCOMES[0]
    assert ra.OUTCOMES == ("mature_cohort", "precedence_672")
    with pytest.raises(ValueError, match="not one of"):
        ra.load_and_classify("both")


def test_the_sensitivity_is_the_672_construction(loaded):
    s = loaded["precedence_672"]
    assert len(s["ws"]) == 672 and len({r["syndicate"] for r in s["ws"].values()}) == 118
    scopes = [r["pyd_cohort_scope"] for r in s["ws"].values()]
    assert scopes.count(ra.COHORT_ENFORCED) == 571 and len(scopes) - 571 == 101
    assert "mature_cohort_figures_applied" not in s["counters"]
    assert not any(r["pyd_basis_source"].startswith("mature-cohort") for r in s["records"])
    assert ra.NO_MATURE_COHORT_FIGURE_TAG not in {e["status"] for e in s["log"]}


def test_the_primary_is_the_adjudications_653_with_their_figures(loaded, decisions):
    p, s = loaded["mature_cohort"], loaded["precedence_672"]
    enforced_672 = {k for k, r in s["ws"].items() if r["pyd_cohort_scope"] == ra.COHORT_ENFORCED}
    primary_decided = {k for k, r in decisions.items() if r["final_status"].startswith("primary")}
    assert len(enforced_672) == 571 and len(primary_decided) == 82
    assert set(p["ws"]) == enforced_672 | primary_decided and len(p["ws"]) == 653
    assert all(r["pyd_cohort_scope"] == ra.COHORT_ENFORCED for r in p["ws"].values())
    for k in enforced_672:
        assert p["ws"][k]["pyd_gbp_m"] == s["ws"][k]["pyd_gbp_m"] and p["ws"][k]["s_raw_a"] == s["ws"][k]["s_raw_a"]
    for k in primary_decided:
        assert abs(p["ws"][k]["pyd_gbp_m"] - float(decisions[k]["figure_used_gbp_m"])) <= 0.0006, k
        assert p["ws"][k]["pyd_basis_source"] == "mature-cohort-figure:register", k
    assert p["counters"]["mature_cohort_figures_applied"] == 85


def test_the_non_triangle_records_and_the_transactions_leave_the_primary(loaded):
    p, s = loaded["mature_cohort"], loaded["precedence_672"]
    left = set(s["ws"]) - set(p["ws"])
    tags = {k: p["status"][k]["status"] for k in left}
    assert len(left) == 43
    assert sorted(k for k, t in tags.items() if t == ra.TAKEON_TAG) == ["1084_2022", "2001_2022"]
    nomature = sorted(k for k, t in tags.items() if t == ra.NO_MATURE_COHORT_FIGURE_TAG)
    assert len(nomature) == 41 and "6134_2023" in nomature
    # the 40 whose figure is no triangle's: each is disclosed in the sensitivity and keeps no severity here
    for k in nomature:
        assert p["by_key"][k]["s_raw_a"] is None and p["by_key"][k]["pyd_pct"] is None
        assert p["by_key"][k]["pyd_gbp_m"] is None
    assert sorted(set(p["ws"]) - set(s["ws"])) == sorted(
        k for k in p["ws"] if p["ws"][k]["pyd_basis_source"] == "mature-cohort-figure:register"
        and s["by_key"].get(k, {}).get("data_quality_tag") != "RELIABLE")
    assert len(set(p["ws"]) - set(s["ws"])) == 24
    assert p["status"]["1861_2020"]["status"] == ra.TAKEON_TAG


def test_the_take_on_bases_apply_to_the_primary_only(loaded):
    p, s = loaded["mature_cohort"], loaded["precedence_672"]
    base = ra.load_takeon_base()
    for key in ("1686_2021", "3000_2016", "4000_2022"):
        e = base[key]
        r = p["ws"][key]
        rate = r["fx_rate_usd_per_gbp"] or 1.0
        assert r["opening_reserves_gbp_m"] == pytest.approx((e["opening_reserves_m"] + e["takeon_m"]) / rate)
        assert s["by_key"][key]["opening_reserves_gbp_m"] == pytest.approx(e["opening_reserves_m"] / rate)
    assert p["counters"]["takeon_base_applied"] == s["counters"]["takeon_base_applied"] + 3


def test_the_six_transfer_records_were_read_twice_and_need_no_entry(loaded):
    """Item 1 of the adjudication's changes outside the 86: two readings each
    (results/extraction_error_rate/mature-cohort/readings/T1.json
    and T2.json) find no year-t take-on in the step. None is in a take-on register, and each keeps its figure under
    both outcomes."""
    keys = ("3330_2018", "3500_2018", "1884_2022", "1884_2023", "1971_2022", "1971_2023")
    t1, t2 = (_json("results", "extraction_error_rate", "mature-cohort", "readings", "%s.json" % r)
              for r in ("T1", "T2"))
    base, takeons = ra.load_takeon_base(), ra.load_takeon_register()
    p, s = loaded["mature_cohort"], loaded["precedence_672"]
    for key in keys:
        assert t1[key]["verdict"] == t2[key]["verdict"] == "no_effect", key
        assert t1[key]["pages"] and t2[key]["pages"]
        assert key not in base and key not in takeons, key
        assert key in p["ws"] and key in s["ws"], key
        assert p["ws"][key]["pyd_gbp_m"] == s["ws"][key]["pyd_gbp_m"], key
        assert p["ws"][key]["opening_reserves_gbp_m"] == s["ws"][key]["opening_reserves_gbp_m"], key


def test_the_new_tag_reaches_the_ledgers_unusable_severity_step(loaded, tmp_path):
    p = loaded["mature_cohort"]
    ra.assign_event_groups(p["records"], min_events=3)
    _meta, subsets = ra.build_subsets(p["records"])
    ra.compute_eligibility(p["records"], subsets)
    flow = ra.build_disposition_ledger(p["log"], p["records"], str(tmp_path / "ledger.csv"))
    assert flow["working_sample"] == 653 and flow["working_sample_equals_eligible_for_capital"] is True
    n = sum(1 for r in p["records"] if r["data_quality_tag"] == ra.NO_MATURE_COHORT_FIGURE_TAG)
    assert n == p["counters"]["no_mature_cohort_figure_unusable"] == 56
    assert all(r["eligible_for_capital"] is False for r in p["records"]
               if r["data_quality_tag"] == ra.NO_MATURE_COHORT_FIGURE_TAG)


def test_the_register_is_a_hashed_raw_byte_input():
    assert str(ra.MATURE_COHORT_FIGURES) in ra.source_files_for_hash([])
    with io.open(os.path.join(HERE, ".gitattributes"), encoding="utf-8") as fh:
        assert "data/mature_cohort_figures.json -text" in fh.read().splitlines()


def test_the_missingness_ledger_places_the_new_tag_at_the_unusable_severity_step():
    import build_current_results as bcr
    import generate_data_audit as gda
    import missingness_check as MC
    rows = [{"file": "a", "detail": "no_mature_cohort_figure"},
            {"file": "b", "detail": "gross_development_unavailable"}]
    ledger = [{"file": "a", "disposition": "CORPUS:" + ra.NO_MATURE_COHORT_FIGURE_TAG},
              {"file": "b", "disposition": "CORPUS:INCOMPLETE"}]
    out = MC.basis_exclusions_reconciliation(rows, ledger, {"to_working_sample": {"net_or_unstated_basis": 0,
                                                                                  "unusable_severity": 2}})
    assert out["unusable_severity_components"] == {"gross_development_unavailable": 1, "no_mature_cohort_figure": 1}
    with io.open(os.path.join(HERE, "src", "missingness_check.py"), encoding="utf-8") as _fh:
        src = _fh.read()
    assert 'obs.get("data_quality_tag") == "%s"' % ra.NO_MATURE_COHORT_FIGURE_TAG in src
    assert '"scientific_exclusion", "no_mature_cohort_figure"' in src
    for words in (bcr.SCIENTIFIC_DETAIL_WORDS, gda.SCIENTIFIC_DETAIL_WORDS):
        assert "mature-cohort" in words["no_mature_cohort_figure"]
