#!/usr/bin/env python3
"""The frozen fold map (data/fold_map.json, read by oos_validation.fold_assignment).

Decision of the Claude analysis session, 26 October 2026: every cross-validation and every backtest takes its folds from
one map of the 118 syndicates, dealt once on the 643-record sample. A population that lacks some syndicates (the primary
without 2008, the primary without Syndicate 1991) simply has fewer; no syndicate moves to another fold.

  * the map states its rule, its sample and its commit, and is exactly that rule on its own 118 syndicates;
  * fold_assignment reads it: the folds are its positions mod k (k = 5 and k = 10), a syndicate absent from it is refused,
    a sample with fewer syndicates takes it restricted, and a redealt map is a different assignment (the fixture shows
    that dropping one syndicate moves others under a fresh deal);
  * every producer that assigns folds goes through fold_assignment: none retypes the dealing rule (a scan of src/, so a new
    producer is covered without being listed);
  * the primary's backtest and the influence record's primary row are one assignment (the dealing, on the real loader's
    data, is in test_exclusion_influence.py; the stored records' agreement is there too, once the regeneration has run).

Run:  python -m pytest src/test_fold_map.py -q
"""
import glob
import io
import json
import os
import re
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import adopted_model as am  # noqa: E402
import oos_validation as OV  # noqa: E402


def read_map():
    with io.open(os.path.join(HERE, "data", "fold_map.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_map_states_its_rule_its_sample_and_its_commit():
    d = read_map()
    assert d["n_syndicates"] == 118 == len(d["position"])
    assert "dealt out in turn" in d["dealing_rule"] and "mod k" in d["dealing_rule"]
    assert "643-record" in d["dealt_on"]["sample"] and "118 syndicates" in d["dealt_on"]["sample"]
    assert re.match(r"^[0-9a-f]{8}\b", d["dealt_on"]["analysis_commit"]) and d["dealt_on"]["date"] == "26 October 2026"
    assert "decision of the Claude analysis session" in d["dealt_on"]["decision"]
    assert "never redealt" in d["_purpose"] and "refused" in d["_purpose"]


def test_the_map_is_its_rule_on_its_own_syndicates():
    d = read_map()
    pos = {int(s): p for s, p in d["position"].items()}
    assert pos == OV.deal_positions(pos)
    assert sorted(pos.values()) == list(range(118))
    assert OV.load_fold_map() == pos


@pytest.mark.parametrize("k", [5, 10])
def test_fold_assignment_is_the_maps_positions_mod_k(k):
    pos = OV.load_fold_map()
    syn = np.array(sorted(pos) * 2)
    assert OV.fold_assignment(syn, k).tolist() == [pos[int(s)] % k for s in syn.tolist()]
    assert OV.fold_assignment(syn[:5]).tolist() == [pos[int(s)] % OV.K for s in syn[:5].tolist()]


def test_a_syndicate_absent_from_the_map_is_refused_and_named():
    pos = OV.load_fold_map()
    with pytest.raises(ValueError, match=r"not in the frozen fold map.*99999"):
        OV.fold_assignment(np.array([sorted(pos)[0], 99999]), 10)
    # a stand-in map is honoured, and refuses too
    with pytest.raises(ValueError, match="not in the frozen fold map"):
        OV.fold_assignment(np.array([1, 2]), 10, fold_map={1: 0})


def test_a_sample_with_fewer_syndicates_takes_the_map_restricted_and_no_syndicate_moves():
    pos = OV.load_fold_map()
    everyone = np.array(sorted(pos))
    for drop in (everyone[0], everyone[3], everyone[60]):
        rest = everyone[everyone != drop]
        assert OV.fold_assignment(rest, 10).tolist() == OV.fold_assignment(everyone, 10)[everyone != drop].tolist()
        # a fresh deal on the remaining syndicates is another assignment: the property is the map's, not the rule's
        fresh = OV.deal_positions(rest)
        assert [fresh[int(s)] % 10 for s in rest.tolist()] != OV.fold_assignment(rest, 10).tolist() or drop == everyone[-1]


def test_the_real_working_sample_is_inside_the_map_and_takes_it():
    syn = am.load_sample()[4]
    assert set(syn.tolist()) <= set(OV.load_fold_map())
    pos = OV.load_fold_map()
    assert OV.fold_assignment(syn, 10).tolist() == [pos[int(s)] % 10 for s in syn.tolist()]


def _sources():
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "src", "*.py"))):
        name = os.path.basename(path)
        if name.startswith("test_") or name == "fold_test_support.py":
            continue
        with io.open(path, encoding="utf-8") as fh:
            out.append((name, fh.read()))
    return out


def test_no_producer_retypes_the_dealing_rule():
    """The dealing rule (enumerate the sorted syndicates, position mod k) lives in oos_validation.deal_positions and the
    map. A producer that deals its own folds would redeal whenever its sample changed."""
    bad = []
    for name, src in _sources():
        if name == "oos_validation.py":
            continue
        for ln in src.splitlines():
            code = ln.split("#")[0]
            if re.search(r"\bi\s*%\s*(K|k|n_folds|k_folds)\b", code) and re.search(r"enumerate|fold", code):
                bad.append("%s: %s" % (name, ln.strip()))
    assert bad == [], bad


def test_every_producer_that_cross_validates_by_syndicate_calls_fold_assignment():
    """Every source that takes the cross-validation constant K from oos_validation, or builds ten backtest folds, assigns
    them through fold_assignment: found from the sources, not from a list."""
    needs = []
    for name, src in _sources():
        if name == "oos_validation.py":
            continue
        takes_k = re.search(r"from oos_validation import[^\n]*\bK\b", src) is not None or "K_HONEST" in src
        if takes_k and not re.search(r"fold_assignment\(", src):          # a call, not only an import
            needs.append(name)
    assert needs == [], needs
    names = {n for n, s in _sources() if re.search(r"fold_assignment\(", s)}
    for must in ("check_operator_backtest.py", "check_full_model_cv.py", "check_pooling_cv.py",
                 "check_pooling_cv_extended.py", "check_cv_clustered_se.py", "check_floor_large_syndicates.py",
                 "check_long_tail_share.py", "oos_size_only.py", "oos_validation.py", "check_exclusion_influence.py"):
        assert must in names, must
    # the cohort-depth backtest and the diagnosis go through the backtest's helper
    assert "BT.fold_assignment" in dict(_sources())["check_cohort_depth_sensitivity.py"]
    assert "BT.fold_assignment" in dict(_sources())["check_small_book_diagnosis.py"]


def test_the_backtest_and_the_cross_validations_share_one_helper():
    import check_operator_backtest as BT
    assert BT.fold_assignment is OV.fold_assignment
