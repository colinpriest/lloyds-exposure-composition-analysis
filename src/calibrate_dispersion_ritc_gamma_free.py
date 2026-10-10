"""Calibrate the gamma-free fit: the adopted two-regime model with the concentration exponent gamma fitted.

The headline fit (calibrate_dispersion_ritc.py) fixes gamma at 0 in the likelihood (the author's decision of
10 October 2026, option B). This script fits the same specification with gamma ~ HalfNormal(1)
(adopted_model.scale_block(gamma_prior="halfnormal")): data, priors, sampler, seed and output format are those
of the headline calibration before option B, so its files are what that calibration wrote then, byte for byte
for the draws. It is

  - the concentration overlay's only source (transfer_operator.SOURCE[OVERLAY]): the overlay applies this fit's
    fitted gamma with its own k, sigma_undiv, sigma_div and nu, a labelled sensitivity;
  - the subject of check_gamma_free_fit.py, which sets it beside the headline;
  - where P(gamma > 0.05) is read (posterior_prob and prior_prob carry gamma_gt_0.05 here, not in the headline).

Writes dispersion_calibration_ritc_gamma_free.json and dispersion_posterior_draws_ritc_gamma_free.npz.

Usage:  python src/calibrate_dispersion_ritc_gamma_free.py
"""
import sys
from pathlib import Path

from calibrate_dispersion_ritc import fit_and_write

SD = Path(__file__).resolve().parent.parent
OUT = SD / "model" / "dispersion_calibration_ritc_gamma_free.json"
DRAWS = SD / "model" / "dispersion_posterior_draws_ritc_gamma_free.npz"


def main():
    fit_and_write("halfnormal", OUT, DRAWS)


if __name__ == "__main__":
    sys.exit(main())
