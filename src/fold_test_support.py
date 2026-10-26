"""Test support: folds for tests on SYNTHETIC syndicates.

oos_validation.fold_assignment reads the frozen fold map (data/fold_map.json) and refuses a syndicate that is not in it,
which a made-up syndicate never is. A test that runs the backtest, the cross-validations or a producer on synthetic
syndicates calls deal_on_the_fly(monkeypatch), which makes fold_assignment deal the sorted syndicates it is given in turn
(oos_validation.deal_positions, the rule the map was dealt by), as it did before the map was frozen.

Never for a test that reads a real sample or a committed record: those must see the frozen map, which is what they test.
A module of src/ and not a conftest.py, so that a test file run alone finds it.
"""
import sys

import oos_validation as OV

#: the modules that import fold_assignment by name, which a patch of oos_validation alone would not reach
IMPORTERS = ("check_operator_backtest", "check_cohort_depth_sensitivity", "check_exclusion_influence",
             "check_small_book_diagnosis")


def deal_on_the_fly(monkeypatch):
    """Make fold_assignment deal the syndicates it is given (a pytest.MonkeyPatch, the fixture or one made for a
    module-scope fixture, which the caller undoes)."""
    real = OV.fold_assignment

    def deal(syn, k=OV.K, fold_map=None):
        return real(syn, k, OV.deal_positions(syn) if fold_map is None else fold_map)

    monkeypatch.setattr(OV, "fold_assignment", deal)
    for name in IMPORTERS:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "fold_assignment"):
            monkeypatch.setattr(mod, "fold_assignment", deal)
