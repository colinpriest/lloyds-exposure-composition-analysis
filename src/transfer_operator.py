"""The transfer operator's two modes, declared once, each with its own fit.

The paper's HEADLINE operator is the size-only one: the concentration exponent gamma is zero, so the scale

    sigma(R, H) = sqrt(sd_undiv^2 + sd_div^2 * [(R/R_ref)(1/H)^gamma]^{2(k-1)})

does not depend on the Herfindahl index at all. Since the author's decision of 10 October 2026 (option B) it
is built from the headline fit, which has gamma fixed at 0 IN THE LIKELIHOOD (calibrate_dispersion_ritc.py):
k, the floor sd_undiv, the diversifiable scale sd_div and the two tail indices are that fit's own posterior.
It is a refit, not a zeroing. (Until then it was built by setting gamma to zero in every retained draw of the
gamma-inclusive fit while k, sd_undiv, sd_div and the tail indices kept the values that fit gave them; that
construction is retired, and survives only behind retired_zeroing=True for the one script that measures the
bridge from it, check_gamma_free_fit.py.)

The fitted exponent survives as the concentration OVERLAY, a labelled sensitivity, built from the gamma-free
fit (calibrate_dispersion_ritc_gamma_free.py): its fitted gamma and its own k, sigma and nu.

SOURCE names each mode's calibration and draws, and load_draws(mode) / load_calibration(mode) read them, so a
producer cannot apply one mode to the other's fit by accident; params() refuses the mix-ups it can see (the
size-only operator on draws that carry a fitted gamma, the overlay on draws whose gamma is identically 0).

Why this module exists. Until the review of 29 September 2026 (MAT-1) the paper, the tool and
the README all called the size-only operator the default while every headline vignette figure --
the worked examples, Table 7, the Shapley split, the Vignette 2 change -- was computed with the
overlay. A reader running the tool at its defaults got 0.298 where the paper printed 0.280. Each
producer typed its own gamma, so nothing could say which operator a number came from. Every
producer of a transferred stress now takes its operator from here and writes the key
"operator" beside its figures (stamp()), and src/test_operator_binding.py holds each headline
output to HEADLINE.

Import this; do not retype the construction.
"""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

SIZE_ONLY = "size_only"
OVERLAY = "overlay"
#: the operator behind every headline figure (the author's decision of 29 September 2026)
HEADLINE = SIZE_ONLY
#: the operator reported beside it as a labelled sensitivity
SENSITIVITY = OVERLAY
MODES = (SIZE_ONLY, OVERLAY)

ROLE = {SIZE_ONLY: "headline", OVERLAY: "sensitivity"}

_SD = Path(__file__).resolve().parent.parent
#: mode -> (calibration JSON, posterior draws): the headline gamma = 0 fit, and the gamma-free fit for the overlay
SOURCE = {
    SIZE_ONLY: (_SD / "model" / "dispersion_calibration_ritc.json",
                _SD / "model" / "dispersion_posterior_draws_ritc.npz"),
    OVERLAY: (_SD / "model" / "dispersion_calibration_ritc_gamma_free.json",
              _SD / "model" / "dispersion_posterior_draws_ritc_gamma_free.npz"),
}
#: the operator parameters load_draws returns by default
OPERATOR_KEYS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")

CONSTRUCTION = {
    SIZE_ONLY: ("size-only operator: gamma fixed at 0 in the likelihood (the headline fit); a refit, not a "
                "zeroing: k, sigma_undiv, sigma_div, nu_clean and nu_RITC are that fit's own posterior. sigma does "
                "not depend on H, so the concentration channel of any decomposition is exactly zero"),
    OVERLAY: ("concentration overlay: the gamma-free fit, its fitted concentration exponent gamma (each posterior "
              "draw, or the posterior mean) and its own k, sigma_undiv, sigma_div and nu; a labelled sensitivity, "
              "not the headline"),
}

#: the scripts that may build the RETIRED size-only construction (the gamma-free fit with gamma zeroed in its
#: draws), each with its reason; params(..., retired_zeroing=True) refuses any other caller
RETIRED_ZEROING_DECLARED = {
    "check_gamma_free_fit.py": ("the bridge from the figures the paper printed before option B: the gamma-free fit "
                                "with gamma zeroed in its draws, beside the headline gamma = 0 fit"),
}


def check(mode):
    """The mode, or ValueError: a typo must not silently select an operator."""
    if mode not in MODES:
        raise ValueError("operator mode must be one of %s, not %r" % (MODES, mode))
    return mode


def _gamma_is_zero(g):
    return bool(np.all(np.asarray(g, dtype=float) == 0.0))


def _caller_file(depth=2):
    """The file name of the function `depth` frames up (2: the caller of the function that calls this)."""
    return os.path.basename(sys._getframe(depth).f_code.co_filename)


def params(p, mode, retired_zeroing=False):
    """A copy of the parameter mapping `p` checked for, and with gamma as, `mode` uses it.

    `p` may hold posterior means (floats) or posterior draws (arrays), and must come from the mode's own fit
    (SOURCE): the size-only mode needs the headline fit, whose gamma is identically 0, and returns it with gamma
    as an exact float zero of the same shape; the overlay needs the gamma-free fit, whose gamma is not. Each
    refuses the other's fit, because applying a mode to the wrong fit is the silent mix-up this module exists to
    stop. retired_zeroing=True (size-only only, and only from a script in RETIRED_ZEROING_DECLARED) builds the
    retired construction instead: gamma set to zero in the gamma-free fit's draws.
    """
    check(mode)
    if "gamma" not in p:
        raise KeyError("the parameter mapping carries no gamma to set")
    g = p["gamma"]
    zero = _gamma_is_zero(g)
    if retired_zeroing:
        caller = _caller_file()
        if mode != SIZE_ONLY:
            raise ValueError("retired_zeroing is a size-only construction, not an overlay")
        if caller not in RETIRED_ZEROING_DECLARED:
            raise ValueError("%s may not build the retired zeroing construction: only %s declare it"
                             % (caller, sorted(RETIRED_ZEROING_DECLARED)))
        if zero:
            raise ValueError("the retired zeroing construction starts from the gamma-free fit; these draws' gamma "
                             "is already identically 0")
    elif mode == SIZE_ONLY and not zero:
        raise ValueError("the size-only operator is the gamma = 0 fit's (%s); these parameters carry a fitted gamma "
                         "(the gamma-free fit's?), and zeroing it is the retired construction"
                         % SOURCE[SIZE_ONLY][1].name)
    elif mode == OVERLAY and zero:
        raise ValueError("the overlay applies the gamma-free fit's fitted gamma (%s); these parameters have gamma "
                         "identically 0 (the headline fit's?)" % SOURCE[OVERLAY][1].name)
    q = dict(p)
    if mode == SIZE_ONLY:
        q["gamma"] = np.zeros(np.shape(g), dtype=float) if np.ndim(g) else 0.0
    return q


def gamma_in_force(fitted_gamma, mode):
    """The concentration exponent the transfer applies under `mode`, from that mode's own fit: 0 for the size-only
    operator (whose fit has gamma = 0), the gamma-free fit's gamma for the overlay. A mismatched fit is refused, as
    in params()."""
    check(mode)
    if mode == SIZE_ONLY:
        if float(fitted_gamma) != 0.0:
            raise ValueError("the size-only operator's fit has gamma = 0, not %r" % (fitted_gamma,))
        return 0.0
    if float(fitted_gamma) == 0.0:
        raise ValueError("the overlay needs the gamma-free fit's gamma, not 0")
    return float(fitted_gamma)


def load_calibration(mode):
    """The calibration JSON of `mode`'s own fit (SOURCE)."""
    check(mode)
    with io.open(SOURCE[mode][0], encoding="utf-8") as _fh:
        return json.load(_fh)


def load_draws(mode, keys=OPERATOR_KEYS):
    """(draws, reference size, H floor, H ceiling) of `mode`'s own fit (SOURCE): `draws` maps each of `keys` to
    its posterior draws. A missing file raises; there is no fallback to another fit."""
    check(mode)
    z = np.load(SOURCE[mode][1])
    draws = {k: z[k] for k in keys}
    if mode == SIZE_ONLY and not _gamma_is_zero(draws.get("gamma", 0.0)):
        raise ValueError("%s carries a fitted gamma: it is not the gamma = 0 headline fit" % SOURCE[mode][1])
    if mode == OVERLAY and "gamma" in draws and _gamma_is_zero(draws["gamma"]):
        raise ValueError("%s has gamma identically 0: it is not the gamma-free fit" % SOURCE[mode][1])
    return draws, float(z["reference_size"][0]), float(z["hhi_floor"][0]), float(z["hhi_ceil"][0])


def stamp(mode):
    """The keys a producer writes beside figures computed under `mode`."""
    check(mode)
    return {"operator": mode, "operator_role": ROLE[mode],
            "operator_construction": CONSTRUCTION[mode]}
