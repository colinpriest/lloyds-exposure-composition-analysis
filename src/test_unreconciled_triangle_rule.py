r"""The rule gross_triangle_does_not_reconcile, and the repairs of 13 October 2026 (data/pyd_confirmed_figures.json).

The author decided on 13 October 2026 to exclude 4020/2017 under a new rule: a record whose printed gross development
triangle does not reconcile to the filing's own totals carries no severity and leaves the working sample, unless a
precedence rule (the provisions sign-disagreement override, or the model-agreement veto) puts another figure in the
triangle's place. 4020/2017's latest diagonal, 2,006.546m, does not reconcile to the same note's gross total of
latest estimates, 1,935.876m (the net table ties), and its older columns repeat the 2016 report's triangle one column
over. Its adopted route is the gross triangle; its stated gross movement (+8.718m, which covers all prior years, year
t-1 included) and the models' reading share the triangle's sign, so neither precedence rule applies. The register
records the rule with the failed reconciliation; the loader keeps the figure on the gross basis, computes no
severity, and tags the record GROSS_TRIANGLE_DOES_NOT_RECONCILE at the unusable-severity step, and it refuses an entry
under the rule for a record whose adopted route is not a triangle's (a precedence rule put another figure there). The
triangle-table census of the same day (results/extraction_error_rate/triangle-table-scan/) found no other
working-sample record whose table fails a total the filing prints for it.

The same decision repaired four figures read from the filing's net table as gross (1274/2022, 1274/2023, 4472/2022,
4472/2023) to the printed gross triangle, and registered 1218/2015, whose filing prints only net figures, on the net
basis. Each entry's figure is the readings' own, read here from the readings files the entry names.

Run:  python -m pytest src/test_unreconciled_triangle_rule.py -q
"""
import io
import json
import os
import re
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402
import missingness_check as MC  # noqa: E402
import build_current_results as bcr  # noqa: E402
import generate_data_audit as gda  # noqa: E402

RULE = "gross_triangle_does_not_reconcile"
TAG = "GROSS_TRIANGLE_DOES_NOT_RECONCILE"
EVIDENCE = {"pages": [41, 42], "quote": "Total claims 1,935,876", "readings": ["reading A", "reading B"],
            "source": "test"}
ENTRY = dict(EVIDENCE, figure_m=None, figure_kind=None, basis="gross", rule=RULE,
             reconciliation={"latest_diagonal_m": 2006.546, "gross_total_of_latest_estimates_m": 1935.876})
DROP = object()


def _entry(change):
    out = json.loads(json.dumps(ENTRY))
    for k, v in change.items():
        if v is DROP:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def _register(tmp_path, reg):
    p = tmp_path / "confirmed.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    return p


# --- the register ----------------------------------------------------------------------------------------------------

def test_an_entry_under_the_rule_loads(tmp_path):
    assert ra.UNRECONCILED_TRIANGLE_RULE == RULE and ra.UNRECONCILED_TRIANGLE_TAG == TAG
    assert set(ra.load_pyd_confirmed_figures(_register(tmp_path, {"9999_2017": ENTRY}))) == {"9999_2017"}


@pytest.mark.parametrize("change", [
    {"rule": "gross_triangle_is_odd"}, {"figure_m": 21.188}, {"figure_m": DROP}, {"figure_kind": "triangle"},
    {"basis": "net"}, {"basis": "unknown"}, {"reconciliation": DROP},
    {"reconciliation": {"latest_diagonal_m": 2006.546}},
    {"reconciliation": {"latest_diagonal_m": "2006.546", "gross_total_of_latest_estimates_m": 1935.876}},
    # a reconciliation that holds (within 2%) cannot carry the rule
    {"reconciliation": {"latest_diagonal_m": 1950.0, "gross_total_of_latest_estimates_m": 1935.876}},
    {"readings": ["reading A"]}, {"quote": " "}],
    ids=["unknown-rule", "a-figure", "no-figure-key", "a-figure-kind", "net", "unknown", "no-reconciliation",
         "half-a-reconciliation", "text-diagonal", "reconciles", "one-reading", "no-quote"])
def test_the_register_refuses_an_entry_the_rule_cannot_rest_on(tmp_path, change):
    with pytest.raises(ValueError, match="9999_2017"):
        ra.load_pyd_confirmed_figures(_register(tmp_path, {"9999_2017": _entry(change)}))


TRIANGLE_ROUTE = {"source": "rag_triangle", "value": 21.188, "model_value": 8.718, "triangle_type": "gross"}


def test_the_rule_keeps_the_figure_and_records_itself_on_the_route():
    block = {"prior_year_development_gbp_m": 21.188, "prior_year_development_pct": 4.14,
             "opening_reserves_gbp_m": 512.293, "data_quality_notes": "triangle", "_pyd_route": TRIANGLE_ROUTE}
    out = ra.apply_confirmed_figure(block, ENTRY)
    assert out is not block and block["data_quality_notes"] == "triangle"
    assert (out["prior_year_development_gbp_m"], out["prior_year_development_pct"]) == (21.188, 4.14)
    assert out["_pyd_route"] == {"source": ra.CONFIRMED_FIGURE_SOURCE, "value": None, "figure_kind": None,
                                 "basis": "gross", "rule": RULE, "register": "data/pyd_confirmed_figures.json"}
    assert "2,006.546m" in out["data_quality_notes"] and "1,935.876m" in out["data_quality_notes"]
    assert ra.pyd_basis(out, "9999_2017", {"9999_2017": {"basis": "net", "source": "x"}}) == (
        "gross", "confirmed-figure:register", "")


@pytest.mark.parametrize("source", sorted(ra.UNRECONCILED_TRIANGLE_ROUTE_SOURCES))
def test_the_rule_applies_on_either_triangle_route(source):
    block = {"prior_year_development_gbp_m": 21.188, "opening_reserves_gbp_m": 512.293,
             "_pyd_route": dict(TRIANGLE_ROUTE, source=source)}
    assert ra.apply_confirmed_figure(block, ENTRY, "9999_2017")["_pyd_route"]["rule"] == RULE


@pytest.mark.parametrize("route", [
    {"source": "rag_provisions", "value": -8.718, "model_value": -8.718},
    {"source": "rag_provisions_text", "value": -8.718},
    {"source": "model_reading", "value": 8.718, "stated": True},
    {"source": None}, None],
    ids=["provisions-override", "provisions-text", "models-reading-after-a-veto", "no-source", "no-route"])
def test_the_rule_yields_to_a_precedence_rule(route):
    """The paper's rule (App 2.2): a record whose printed gross triangle does not reconcile carries no severity UNLESS a
    precedence rule (the provisions sign-disagreement override, or the model-agreement veto) puts another figure in the
    triangle's place. The extraction applies those rules, and the adopted route shows their outcome, so an entry under
    the rule for a record whose route is not a triangle's is refused, naming the record and the route."""
    block = {"prior_year_development_gbp_m": 8.718, "opening_reserves_gbp_m": 512.293}
    if route is not None:
        block["_pyd_route"] = route
    with pytest.raises(ValueError, match=r"9999_2017.*%s" % RULE) as err:
        ra.apply_confirmed_figure(block, ENTRY, "9999_2017")
    assert repr((route or {}).get("source")) in str(err.value)
    # without a key the block's own syndicate and year name the record
    with pytest.raises(ValueError, match="1234_2019"):
        ra.apply_confirmed_figure(dict(block, syndicate=1234, year=2019), ENTRY)


# --- the loader, on the real record ----------------------------------------------------------------------------------

RECORDS = ("4020_2017", "4020_2016", "4472_2022")


def _load(factory, confirmed):
    d = factory.mktemp("records")
    for key in RECORDS:
        shutil.copy(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), str(d))
    reg = factory.mktemp("registers")
    cpath = reg / "confirmed.json"
    cpath.write_text(json.dumps(confirmed), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ra, "DATA_DIR", d)
        mp.setattr(ra, "PYD_CONFIRMED_FIGURES", cpath)
        records, counters, log, files = ra.load_and_classify()
    finally:
        mp.undo()
    assert len(files) == len(RECORDS)
    ra.assign_event_groups(records, min_events=3)
    _meta, subsets = ra.build_subsets(records)
    ra.compute_eligibility(records, subsets)
    return {"by_key": {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}, "records": records,
            "counters": counters, "log": log}


@pytest.fixture(scope="module")
def committed():
    with io.open(str(ra.PYD_CONFIRMED_FIGURES), encoding="utf-8") as _fh:
        return json.load(_fh)


@pytest.fixture(scope="module")
def ruled(tmp_path_factory, committed):
    return _load(tmp_path_factory, {k: committed[k] for k in ("4020_2017", "4472_2022")})


@pytest.fixture(scope="module")
def control(tmp_path_factory):
    return _load(tmp_path_factory, {"_purpose": "empty"})


def test_the_loader_keeps_the_record_in_the_corpus_without_a_severity(ruled, control, tmp_path):
    was, now = control["by_key"]["4020_2017"], ruled["by_key"]["4020_2017"]
    assert was["data_quality_tag"] == "RELIABLE" and was["s_raw_a"] == pytest.approx(21.188 / 512.293, rel=1e-3)
    assert was["eligible_for_capital"] is True
    assert now["data_quality_tag"] == TAG
    assert now["pyd_basis"] == "gross" and now["pyd_basis_source"] == "confirmed-figure:register"
    assert now["pyd_pct"] is None and now["pyd_gbp_m"] is None and now["s_raw_a"] is None
    assert now["eligible_for_capital"] is False
    assert ruled["counters"]["unreconciled_triangle_unusable"] == 1
    assert control["counters"]["unreconciled_triangle_unusable"] == 0
    entries = [e for e in ruled["log"] if e["file"] == "syndicate_4020_2017.json"]
    assert len(entries) == 1 and entries[0]["status"] == TAG and RULE in entries[0]["reason"]
    # the neighbouring year is untouched
    assert ruled["by_key"]["4020_2016"]["s_raw_a"] == control["by_key"]["4020_2016"]["s_raw_a"]
    flow = ra.build_disposition_ledger(ruled["log"], ruled["records"], str(tmp_path / "ledger.csv"))
    base = ra.build_disposition_ledger(control["log"], control["records"], str(tmp_path / "ledger0.csv"))
    assert flow["corpus"] == base["corpus"]
    assert flow["to_working_sample"]["unusable_severity"] == base["to_working_sample"]["unusable_severity"] + 1
    assert flow["working_sample"] == base["working_sample"] - 1
    assert flow["working_sample_equals_eligible_for_capital"] is True


def test_the_loader_adopts_the_registered_gross_figure_over_the_superseded_net_narrative(ruled, control):
    """4472/2022's data/pyd_basis_register.json entry (a net narrative figure, superseded) is not read for it: the
    confirmed figure's basis is read first."""
    assert "4472_2022" in ra.load_pyd_basis_register()
    was, now = control["by_key"]["4472_2022"], ruled["by_key"]["4472_2022"]
    assert was["pyd_gbp_m"] == pytest.approx(-1.5)
    assert now["pyd_gbp_m"] == pytest.approx(122.3)
    assert (now["pyd_basis"], now["pyd_basis_source"]) == ("gross", "confirmed-figure:register")
    assert now["direction"] == "strengthening" and now["eligible_for_capital"] is True
    assert now["s_raw_a"] == pytest.approx(122.3 / 3291.5)


def test_the_missingness_ledger_places_the_rule_at_the_unusable_severity_step():
    rows = [{"file": "a", "detail": "gross_triangle_does_not_reconcile"},
            {"file": "b", "detail": "gross_development_unavailable"}]
    ledger = [{"file": "a", "disposition": "CORPUS:" + TAG}, {"file": "b", "disposition": "CORPUS:INCOMPLETE"}]
    out = MC.basis_exclusions_reconciliation(rows, ledger, {"to_working_sample": {"net_or_unstated_basis": 0,
                                                                                  "unusable_severity": 2}})
    assert out["unusable_severity_components"] == {"gross_development_unavailable": 1,
                                                   "gross_triangle_does_not_reconcile": 1}
    with io.open(os.path.join(HERE, "src", "missingness_check.py"), encoding="utf-8") as _fh:
        src = _fh.read()
    assert 'obs.get("data_quality_tag") == "%s"' % TAG in src
    assert '"scientific_exclusion", "gross_triangle_does_not_reconcile"' in src
    for words in (bcr.SCIENTIFIC_DETAIL_WORDS, gda.SCIENTIFIC_DETAIL_WORDS):
        assert "does not reconcile" in words["gross_triangle_does_not_reconcile"]


# --- the committed register ------------------------------------------------------------------------------------------

#: the decisions of 13 October 2026: figure, basis, kind and the readings files each entry names
DECIDED = {
    "1274_2022": (8.96, "gross", "triangle", ("repair-reader-A.json", "repair-reader-B.json", "repair-reader-C.json")),
    "1274_2023": (87.073, "gross", "triangle", ("first-batch-1.json", "second-readings.json")),
    "4472_2022": (122.3, "gross", "triangle", ("first-batch-4.json", "second-readings.json")),
    "4472_2023": (311.2, "gross", "triangle", ("repair-reader-A.json", "repair-reader-B.json")),
    "1218_2015": (-0.46, "net", "triangle", ("repair-reader-A.json", "repair-reader-B.json")),
}


@pytest.mark.parametrize("key", sorted(DECIDED))
def test_each_decision_is_registered_with_the_readings_own_figure(committed, key):
    figure, basis, kind, files = DECIDED[key]
    entry = committed[key]
    assert (entry["figure_m"], entry["basis"], entry["figure_kind"]) == (figure, basis, kind)
    assert entry["decision"].startswith("owner's decision, 13 October 2026")
    cited = re.findall(r"results/extraction_error_rate/[\w./-]+\.json", " ".join(entry["readings"]))
    assert sorted(os.path.basename(c) for c in cited) == sorted(files)
    for path in cited:
        with io.open(os.path.join(HERE, path), encoding="utf-8") as _fh:
            rows = json.load(_fh)
        hit = [r for r in rows if r["stem"] == "syndicate_" + key]
        assert len(hit) == 1, (path, key)
        expected = figure if basis == "gross" else None
        assert hit[0]["filing_figure_m"] == expected, (path, key)
    assert ra.load_pyd_confirmed_figures()[key] == entry


def test_4020_2017_is_registered_under_the_rule_and_is_the_censuss_only_failed_reconciliation(committed):
    """The rule generalises over the census: every working-sample record whose used table fails a gross total of
    latest estimates the filing prints is registered under it, and 4020/2017 is the only one."""
    entry = committed["4020_2017"]
    assert entry["rule"] == RULE and entry["figure_m"] is None and entry["basis"] == "gross"
    rec = entry["reconciliation"]
    assert (rec["latest_diagonal_m"], rec["gross_total_of_latest_estimates_m"]) == (2006.546, 1935.876)
    with io.open(os.path.join(HERE, "results", "extraction_error_rate", "triangle-table-scan",
                                          "triangle-table-scan.json"), encoding="utf-8") as _fh:
        scan = json.load(_fh)
    failing = sorted(r["stem"].replace("syndicate_", "") for r in scan["records"]
                     if r.get("i_g") is not None and not r["detail"].get("diagonal_to_I_g")
                     and not r["detail"].get("diagonal_to_I_n"))
    assert failing == ["4020_2017"]
    ruled = sorted(k for k, v in committed.items() if not k.startswith("_") and v.get("rule") == RULE)
    assert ruled == failing
    census = {r["stem"]: r for r in scan["records"]}["syndicate_4020_2017"]
    assert census["class"] == "C" and census["d_used"] == rec["latest_diagonal_m"]
    assert census["i_g"] == rec["gross_total_of_latest_estimates_m"]


def test_no_precedence_rule_replaced_the_triangle_of_a_record_under_the_rule(committed):
    """Every record registered under the rule carries the triangle's own figure in every block: its adopted route is a
    triangle's, so neither the provisions sign-disagreement override nor the model-agreement veto applies, and the
    loader's refusal (test_the_rule_yields_to_a_precedence_rule) is never reached on the committed records."""
    ruled = sorted(k for k, v in committed.items() if not k.startswith("_") and v.get("rule") == RULE)
    assert ruled == ["4020_2017"]
    for key in ruled:
        with io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key), encoding="utf-8") as _fh:
            rec = json.load(_fh)
        routes = [m.get("_pyd_route") or {} for m in rec["models"].values()]
        assert routes and all(r.get("source") in ra.UNRECONCILED_TRIANGLE_ROUTE_SOURCES for r in routes), key
    # 4020/2017: the triangle's +21.188m, beside the models' +8.718m of the same sign (no override, no veto)
    assert {(r["value"], r["model_value"]) for r in routes} == {(21.188, 8.718)}
    assert "covers all prior years" in committed["4020_2017"]["decision"]
    assert "unless a precedence rule" in committed["4020_2017"]["decision"]


def test_the_rule_is_documented_where_the_exclusions_are_listed():
    with io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8") as _fh:
        text = _fh.read()
    flat = " ".join(text.split())
    assert "`gross_triangle_does_not_reconcile`" in flat and "4020/2017" in flat
