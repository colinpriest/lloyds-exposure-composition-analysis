"""Each committed vignette bundle agrees with its own metadata.json (24 October 2026).

A regeneration's outputs were once copied back into the repository only in part: 29 of vignette 2's files kept the
earlier sample's figures while its metadata.json recorded the new fit, and only a recorded pass's comparison caught it.
These tests read the committed files and fail when a bundle mixes two runs: the size-mismatch worked example's size
multiplier must follow from the fit metadata.json records (the floor operator at gamma 0), and the mix-mismatch
overlay's gamma in force must be the gamma-free fit metadata.json records.
"""
import json
import math
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIGNETTES = ("vignette-1", "vignette-2")


def _load(vig, name):
    with open(os.path.join(ROOT, "vignettes", vig, name), encoding="utf-8") as fh:
        return json.load(fh)


def _size_multiplier(meta, r_target, r_donor):
    """sd(R_target) / sd(R_donor) under the recorded fit, sd(R) = sqrt(u^2 + d^2 (R/R_ref)^(2(k-1)))."""
    k, u, d = (meta["pooling_exponent_k"], meta["undiversifiable_scale_floor"],
               meta["diversifiable_scale_at_reference"])
    ref = meta["reference_size"]

    def sd(r):
        return math.sqrt(u * u + d * d * (r / ref) ** (2 * (k - 1)))

    return sd(r_target) / sd(r_donor)


@pytest.mark.parametrize("vig", VIGNETTES)
def test_the_size_worked_example_follows_the_bundles_own_fit(vig):
    meta = _load(vig, "metadata.json")
    size = _load(vig, "worked_example_size_mismatch.json")
    m = _size_multiplier(meta, size["target_reserve_size"], size["donor_reserve_size"])
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
