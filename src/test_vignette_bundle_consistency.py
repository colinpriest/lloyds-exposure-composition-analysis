"""Each committed vignette bundle is one run's: its tables, snippet and figure data agree with its JSON and metadata.json
(24 October 2026; widened 26 October 2026 after the review of final review 2's fixes, R4 4).

A regeneration's outputs were once copied back into the repository only in part: 29 of vignette 2's files kept the
earlier sample's figures while its metadata.json recorded the new fit, and only a recorded pass's comparison caught it.
These tests read the committed files of vignettes/vignette-1 and vignettes/vignette-2 and fail when a bundle mixes two
runs. What they check, and nothing more:

  * the size multiplier: worked_example_size_mismatch.json's size multiplier follows from the fit metadata.json records
    (the floor operator at gamma 0), and worked_example_mix_mismatch.json's gamma in force is the gamma-free fit's
    gamma metadata.json records;
  * the worked examples' tables: each worked_example_*.csv prints, stage by stage, the severity and multiplier its own
    JSON records (raw donor S_raw and 1; after size S_size_adjusted and size_multiplier; after concentration S_adj and
    concentration_multiplier), and donor_selection.csv names each JSON's donor with its size, ratio, HHI, distance and
    log size ratio;
  * the adjusted VaR99.5: recomputed here from the working sample (adopted_model.load_sample, the 643 donors the bundle
    transfers) with the fit metadata.json records, at each target size the bundle names (vignette 1: target_profile.json;
    vignette 2: metadata.json's old and new profiles), it is the VaR99.5 that distribution_stats.csv,
    decomposition_summary.csv, tail_support_bootstrap.csv, distribution_plot_data.csv's series and summary_snippet.md
    carry, and in vignette 2 also old_to_new_change_decomposition.csv, old_to_new_waterfall_data.csv and
    profile_transition_distribution.csv; the raw VaR99.5, the size effect and the donor count likewise;
  * the copies: every numeric cell of each summary table's .tex is its .csv cell to the places the .tex prints (four
    for every severity, multiplier, VaR and effect; donor_selection's amounts print one), and its .xlsx is its .csv
    cell for cell.

They do not read the PDF or PNG figures, the README, or the larger tables' .tex and .xlsx (distribution_plot_data,
tail_exceedance_plot_data, profile_transition_distribution), which reproduce.py --verify compares by hash against the
run report.
"""
import csv
import json
import math
import os
import re
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import adopted_model as am  # noqa: E402
import pool_quantile  # noqa: E402

VIGNETTES = ("vignette-1", "vignette-2")
#: the summary tables whose .csv, .tex and .xlsx each bundle writes
SUMMARY_TABLES = {
    "vignette-1": ("worked_example_size_mismatch", "worked_example_mix_mismatch", "donor_selection",
                   "distribution_stats", "decomposition_summary", "tail_support_bootstrap"),
    "vignette-2": ("worked_example_size_mismatch", "worked_example_mix_mismatch", "donor_selection",
                   "distribution_stats", "decomposition_summary", "tail_support_bootstrap",
                   "old_to_new_change_decomposition", "old_to_new_waterfall_data"),
}
#: a .csv prints six decimal places, so a cell is the unrounded value to 5e-7
CSV_TOL = 5.01e-7
#: a .tex cell rounds the unrounded value to the places it prints (four for the severities, multipliers and VaRs, one
#: for an amount in GBP m, none for a count), and the .csv rounds the same value to six
def _tex_tol(cell):
    places = len(cell.split(".", 1)[1]) if "." in cell else 0
    return 0.5 * 10.0 ** -places + 5.01e-7


def _path(vig, name):
    return os.path.join(ROOT, "vignettes", vig, name)


def _load(vig, name):
    with open(_path(vig, name), encoding="utf-8") as fh:
        return json.load(fh)


def _csv(vig, base):
    with open(_path(vig, base + ".csv"), encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def _rows(vig, base):
    with open(_path(vig, base + ".csv"), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _num(cell):
    """A cell's number, or None for text (an observation id such as '2001_2017' is text, not 20012017)."""
    if not isinstance(cell, str) or "_" in cell:
        return None
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


def _size_multiplier(meta, r_target, r_donor):
    """sd(R_target) / sd(R_donor) under the recorded fit, sd(R) = sqrt(u^2 + d^2 (R/R_ref)^(2(k-1)))."""
    k, u, d = (meta["pooling_exponent_k"], meta["undiversifiable_scale_floor"],
               meta["diversifiable_scale_at_reference"])
    ref = meta["reference_size"]

    def sd(r):
        return np.sqrt(u * u + d * d * (np.asarray(r, float) / ref) ** (2 * (k - 1)))

    return sd(r_target) / sd(r_donor)


@pytest.fixture(scope="module")
def sample():
    S, R = am.load_sample()[:2]
    return S, R


def _var995(values):
    return pool_quantile.var_q(np.asarray(values, float), 0.995)


def _anchors(vig, sample):
    """The bundle's VaR99.5 figures recomputed from the working sample and metadata.json's fit: {'raw', <label>: adj}."""
    S, R = sample
    meta = _load(vig, "metadata.json")
    assert meta["concentration_exponent_gamma_in_force"] == 0.0 and meta["operator"] == "size_only", vig
    out = {"raw": _var995(S), "n": len(S)}
    if vig == "vignette-1":
        sizes = {"target": _load(vig, "target_profile.json")["reserve_size"]}
    else:
        profs = {p["profile_id"]: p["reserve_size"] for p in meta["target_profiles"]}
        sizes = {"old": profs["v2_old_profile"], "new": profs["v2_new_profile"]}
    for label, t in sizes.items():
        out[label] = _var995(S * _size_multiplier(meta, t, R))
    return out


def _close(got, want, tol, what, source="its JSON and metadata give"):
    assert got is not None and abs(got - want) <= tol, "%s: the bundle carries %r, %s %.7f" % (what, got, source, want)


# --- the JSON worked examples against metadata.json --------------------------------------------------------------------

@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_size_worked_example_follows_the_bundles_own_fit(vig):
    meta = _load(vig, "metadata.json")
    size = _load(vig, "worked_example_size_mismatch.json")
    m = float(_size_multiplier(meta, size["target_reserve_size"], size["donor_reserve_size"]))
    assert abs(round(m, 6) - size["size_multiplier"]) <= 1e-6, (
        "%s: worked_example_size_mismatch.json records a size multiplier of %.6f, but the fit in its own "
        "metadata.json gives %.6f: the bundle mixes two runs" % (vig, size["size_multiplier"], m))


@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_mix_worked_example_uses_the_bundles_own_gamma_free_fit(vig):
    meta = _load(vig, "metadata.json")
    mix = _load(vig, "worked_example_mix_mismatch.json")
    assert mix["gamma_in_force"] == meta["concentration_exponent_gamma_fitted"], (
        "%s: worked_example_mix_mismatch.json applies gamma %r, but its metadata.json records the gamma-free fit's "
        "%r: the bundle mixes two runs" % (vig, mix["gamma_in_force"], meta["concentration_exponent_gamma_fitted"]))


def test_the_size_multiplier_is_not_one_so_the_check_has_force():
    """The donor and the target differ in size in both vignettes, so a stale fit moves the multiplier."""
    for vig in VIGNETTES:
        size = _load(vig, "worked_example_size_mismatch.json")
        assert abs(size["size_multiplier"] - 1.0) > 0.01, vig


# --- the worked examples' tables against their JSON ---------------------------------------------------------------------

@pytest.mark.parametrize("vig", VIGNETTES)
@pytest.mark.parametrize("kind", ("size", "mix"))
def test_the_worked_example_table_prints_its_jsons_severities_and_multipliers(vig, kind):
    base = "worked_example_%s_mismatch" % kind
    js = _load(vig, base + ".json")
    want = [("raw donor", js["S_raw"], 1.0),
            ("after size", js["S_size_adjusted"], js["size_multiplier"]),
            ("after concentration (adjusted)", js["S_adj"], js["concentration_multiplier"])]
    rows = _rows(vig, base)
    assert [r["stage"] for r in rows] == [w[0] for w in want], (vig, base)
    for r, (stage, sev, mult) in zip(rows, want):
        _close(_num(r["severity"]), sev, CSV_TOL, "%s %s.csv %s severity" % (vig, base, stage))
        _close(_num(r["multiplier"]), mult, CSV_TOL, "%s %s.csv %s multiplier" % (vig, base, stage))


@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_donor_selection_names_each_worked_examples_donor(vig):
    rows = {r["selection_type"]: r for r in _rows(vig, "donor_selection")}
    assert set(rows) == {"size_mismatch", "mix_mismatch"}, vig
    for kind in ("size", "mix"):
        js, r = _load(vig, "worked_example_%s_mismatch.json" % kind), rows["%s_mismatch" % kind]
        assert r["observation_id"] == js["donor_observation_id"], (vig, kind)
        for col, field, tol in (("opening_reserves", "donor_reserve_size", CSV_TOL),
                                ("signed_pyd_ratio", "donor_signed_pyd_ratio", CSV_TOL),
                                ("hhi", "donor_hhi", 5.01e-6),
                                ("hellinger_distance", "hellinger_distance", CSV_TOL),
                                ("log_reserve_ratio_to_target", "log_reserve_ratio_to_target", CSV_TOL)):
            _close(_num(r[col]), js[field], tol, "%s donor_selection.csv %s %s" % (vig, kind, col))


# --- the adjusted VaR99.5 against metadata.json's fit ------------------------------------------------------------------

@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_summary_tables_carry_the_var995_the_bundles_fit_gives(vig, sample):
    a = _anchors(vig, sample)
    stats = {r["distribution_label"]: r for r in _rows(vig, "distribution_stats")}
    boot = {(r["distribution_label"], r["metric"]): r for r in _rows(vig, "tail_support_bootstrap")}
    dec = {r["metric"]: r for r in _rows(vig, "decomposition_summary")}["var995"]
    _close(_num(stats["Raw market"]["var995"]), a["raw"], CSV_TOL, vig + " distribution_stats raw")
    _close(_num(boot[("Raw market", "VaR99.5")]["point_estimate"]), a["raw"], CSV_TOL, vig + " bootstrap raw")
    assert int(stats["Raw market"]["n_total"]) == a["n"], vig
    if vig == "vignette-1":
        adj = a["target"]
        _close(_num(stats["Adjusted target"]["var995"]), adj, CSV_TOL, vig + " distribution_stats adjusted")
        _close(_num(boot[("Adjusted target", "VaR99.5")]["point_estimate"]), adj, CSV_TOL, vig + " bootstrap adjusted")
        _close(_num(dec["raw_metric"]), a["raw"], CSV_TOL, vig + " decomposition raw")
        _close(_num(dec["size_adjusted_metric"]), adj, CSV_TOL, vig + " decomposition size-adjusted")
        _close(_num(dec["fully_adjusted_metric"]), adj, CSV_TOL, vig + " decomposition fully adjusted")
        _close(_num(dec["size_effect"]), adj - a["raw"], CSV_TOL, vig + " decomposition size effect")
        _close(_num(dec["concentration_effect"]), 0.0, 0.0, vig + " decomposition concentration effect")
    else:
        old, new = a["old"], a["new"]
        _close(_num(stats["Adjusted old profile"]["var995"]), old, CSV_TOL, vig + " distribution_stats old")
        _close(_num(stats["Adjusted new profile"]["var995"]), new, CSV_TOL, vig + " distribution_stats new")
        _close(_num(boot[("Adjusted new profile", "VaR99.5")]["point_estimate"]), new, CSV_TOL, vig + " bootstrap new")
        for base in ("decomposition_summary", "old_to_new_change_decomposition"):
            d = {r["metric"]: r for r in _rows(vig, base)}["var995"]
            _close(_num(d["old_profile_metric"]), old, CSV_TOL, "%s %s old" % (vig, base))
            _close(_num(d["new_profile_metric"]), new, CSV_TOL, "%s %s new" % (vig, base))
            _close(_num(d["size_change_effect"]), new - old, CSV_TOL, "%s %s size effect" % (vig, base))
            _close(_num(d["concentration_change_effect"]), 0.0, 0.0, "%s %s concentration effect" % (vig, base))
        bars = {r["bar"]: r for r in _rows(vig, "old_to_new_waterfall_data")}
        assert list(bars) == ["Old VaR99.5", "Size effect", "Concentration effect", "New VaR99.5"], vig
        for bar, value, bottom in (("Old VaR99.5", old, 0.0), ("Size effect", new - old, old),
                                   ("Concentration effect", 0.0, new), ("New VaR99.5", new, 0.0)):
            _close(_num(bars[bar]["value"]), value, CSV_TOL, "%s waterfall %s value" % (vig, bar))
            _close(_num(bars[bar]["bottom"]), bottom, CSV_TOL, "%s waterfall %s bottom" % (vig, bar))


@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_figure_data_are_the_distributions_the_bundles_fit_gives(vig, sample):
    """distribution_plot_data.csv's series (and vignette 2's profile_transition_distribution.csv) are the 643 donors'
    values, whose VaR99.5 is the recomputed one."""
    a = _anchors(vig, sample)
    series = {}
    for r in _rows(vig, "distribution_plot_data"):
        series.setdefault(r["series"], []).append(float(r["value"]))
    labels = {"Raw market": "raw"}
    labels.update({"Adjusted target": "target"} if vig == "vignette-1" else
                  {"Adjusted old profile": "old", "Adjusted new profile": "new"})
    assert set(series) == set(labels), vig
    for label, key in labels.items():
        assert len(series[label]) == a["n"], (vig, label)
        _close(_var995(series[label]), a[key], CSV_TOL, "%s distribution_plot_data %s" % (vig, label))
    if vig == "vignette-2":
        rows = _rows(vig, "profile_transition_distribution")
        assert len(rows) == a["n"], vig
        for col, key in (("S_raw", "raw"), ("S_adj_old", "old"), ("S_adj_new", "new")):
            _close(_var995([float(r[col]) for r in rows]), a[key], CSV_TOL,
                   "%s profile_transition_distribution %s" % (vig, col))


@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_summary_snippet_states_the_var995_the_bundles_fit_gives(vig, sample):
    a = _anchors(vig, sample)
    with open(_path(vig, "summary_snippet.md"), encoding="utf-8") as fh:
        text = fh.read()
    adj = a["target"] if vig == "vignette-1" else a["new"]
    num, sgn = r"(\d+\.\d{4})", r"([+-]\d+\.\d{4})"
    effect = adj - a["raw"] if vig == "vignette-1" else a["new"] - a["old"]
    # every statement of each figure, not only the first: the snippet states the raw-to-adjusted VaR99.5 twice
    want = [(r"Transferring (\d+) market donor observations", ("%d" % a["n"],)),
            (r"The donor pool comprises (\d+) observations", ("%d" % a["n"],)),
            (r"VaR99\.5 \(%s raw vs %s adjusted\)" % (num, num), ("%.4f" % a["raw"], "%.4f" % adj)),
            (r"size effect of " + sgn, ("%+.4f" % effect,)),
            (r"concentration effect of " + sgn, ("+0.0000",))]
    if vig == "vignette-2":
        want.append((r"\(%s adjusted to the old profile vs %s adjusted to the new\)" % (num, num),
                     ("%.4f" % a["old"], "%.4f" % a["new"])))
    for pattern, expected in want:
        found = [m if isinstance(m, tuple) else (m,) for m in re.findall(pattern, text)]
        assert found, "%s summary_snippet.md has no %r" % (vig, pattern)
        for f in found:
            assert f == expected, "%s summary_snippet.md states %r where its JSON and metadata give %r" % (
                vig, f, expected)
    # and it states no four-place figure the bundle's fit does not give
    allowed = {e for _p, exp in want for e in exp if "." in e}
    allowed |= {e.lstrip("+-") for e in allowed}
    for f in re.findall(r"[+-]?\d+\.\d{4}(?!\d)", text):
        assert f in allowed, "%s summary_snippet.md states %s, which its JSON and metadata do not give" % (vig, f)


# --- the .tex and .xlsx copies against the .csv -------------------------------------------------------------------------

def _tex_rows(vig, base):
    with open(_path(vig, base + ".tex"), encoding="utf-8") as fh:
        body = fh.read().split("\\midrule", 1)[1].split("\\bottomrule", 1)[0]
    return [[c.strip() for c in line.strip().rstrip("\\").split(" & ")] for line in body.strip().splitlines()]


@pytest.mark.parametrize("vig,base", [(v, b) for v in VIGNETTES for b in SUMMARY_TABLES[v]])
def test_the_tex_table_is_its_csv(vig, base):
    rows, tex = _csv(vig, base)[1:], _tex_rows(vig, base)
    assert len(tex) == len(rows) and rows, (vig, base)
    checked = 0
    for i, (c, t) in enumerate(zip(rows, tex)):
        assert len(t) == len(c), (vig, base, i)
        for j, (cc, tc) in enumerate(zip(c, t)):
            x = _num(cc)
            if x is None:
                continue
            assert "." in tc or float(x).is_integer(), (vig, base, i, j, tc, cc)
            if base != "donor_selection" and "." in tc:
                assert len(tc.split(".", 1)[1]) == 4, (vig, base, i, j, tc)
            _close(_num(tc), x, _tex_tol(tc), "%s %s.tex row %d col %d" % (vig, base, i, j), "its .csv gives")
            checked += 1
    assert checked >= len(rows), (vig, base)


@pytest.mark.parametrize("vig,base", [(v, b) for v in VIGNETTES for b in SUMMARY_TABLES[v]])
def test_the_xlsx_table_is_its_csv(vig, base):
    import openpyxl  # requirements.lock pins it; a missing package fails the test, it does not skip it
    wb = openpyxl.load_workbook(_path(vig, base + ".xlsx"), read_only=True, data_only=True)
    try:
        xl = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()
    rows = _csv(vig, base)
    assert len(xl) == len(rows), (vig, base)
    for i, (c, x) in enumerate(zip(rows, xl)):
        assert len(x) >= len(c) and all(v is None for v in x[len(c):]), (vig, base, i)
        for j, cc in enumerate(c):
            v, n = x[j], _num(cc)
            if n is None or isinstance(v, str):
                assert ("" if v is None else str(v)) == cc, (vig, base, i, j, v, cc)
            else:
                assert v is not None and math.isclose(float(v), n, rel_tol=0, abs_tol=1e-12), (vig, base, i, j, v, cc)
