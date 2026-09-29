"""The transfer operator's two modes, declared once.

The paper's HEADLINE operator is the size-only one: the concentration exponent gamma is zero in
the transfer, so the scale

    sigma(R, H) = sqrt(sd_undiv^2 + sd_div^2 * [(R/R_ref)(1/H)^gamma]^{2(k-1)})

does not depend on the Herfindahl index at all. It is built from the adopted fit, which does
estimate gamma, by setting gamma to zero in every retained posterior draw (and in the posterior
mean); k, the floor sd_undiv, the diversifiable scale sd_div and the two tail indices keep their
fitted values. It is not a refit, and the paper says so.

The fitted exponent survives as the concentration OVERLAY, a labelled sensitivity.

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
import numpy as np

SIZE_ONLY = "size_only"
OVERLAY = "overlay"
#: the operator behind every headline figure (the author's decision of 29 September 2026)
HEADLINE = SIZE_ONLY
#: the operator reported beside it as a labelled sensitivity
SENSITIVITY = OVERLAY
MODES = (SIZE_ONLY, OVERLAY)

ROLE = {SIZE_ONLY: "headline", OVERLAY: "sensitivity"}

CONSTRUCTION = {
    SIZE_ONLY: ("size-only operator: gamma = 0 in the transfer, set to zero in every retained posterior draw "
                "(and in the posterior mean) of the adopted gamma-inclusive fit; k, sigma_undiv, sigma_div, "
                "nu_clean and nu_RITC keep their fitted values; not a refit. sigma does not depend on H, so "
                "the concentration channel of any decomposition is exactly zero"),
    OVERLAY: ("concentration overlay: the fitted concentration exponent gamma (each posterior draw, or the "
              "posterior mean) in the transfer; a labelled sensitivity, not the headline"),
}


def check(mode):
    """The mode, or ValueError: a typo must not silently select an operator."""
    if mode not in MODES:
        raise ValueError("operator mode must be one of %s, not %r" % (MODES, mode))
    return mode


def params(p, mode):
    """A copy of the parameter mapping `p` with gamma as `mode` uses it.

    `p` may hold posterior means (floats) or posterior draws (arrays); the size-only mode
    replaces gamma by an exact zero of the same shape, and leaves every other entry untouched.
    """
    check(mode)
    if "gamma" not in p:
        raise KeyError("the parameter mapping carries no gamma to set")
    q = dict(p)
    if mode == SIZE_ONLY:
        g = q["gamma"]
        q["gamma"] = np.zeros(np.shape(g), dtype=float) if np.ndim(g) else 0.0
    return q


def gamma_in_force(fitted_gamma, mode):
    """The concentration exponent the transfer applies under `mode`."""
    check(mode)
    return 0.0 if mode == SIZE_ONLY else float(fitted_gamma)


def stamp(mode):
    """The keys a producer writes beside figures computed under `mode`."""
    check(mode)
    return {"operator": mode, "operator_role": ROLE[mode],
            "operator_construction": CONSTRUCTION[mode]}
