"""The donor pool: one definition for the vignettes, the tools and every producer that transfers from it.

The pool is the capital-eligible donors, which are the gross-basis working sample (model/exposure_results.json's
observations that carry a severity, an opening reserve and a concentration: adopted_model.load_sample selects the same
records, and src/test_donor_pool.py holds the two equal). Each donor is carried at the precision the shipped tool
(distortion_tool.html) embeds: the severity to 8 decimals, the opening reserves to 2, the concentration to 6.

Why this module exists. vignette_uncertainty.py and every producer that transfers from the pool used to read the pool out
of distortion_tool.html, a file run_analysis.py rewrites near the END of a manifest pass. A single pass therefore computed
the headline interval on the pool of the PREVIOUS pass while every refit used the new sample. The pool is now built from
model/exposure_results.json, which the loader step writes before any calibration, by the function that also builds the
tool's own donor fields (run_analysis.generate_distortion_tool takes donor_fields from here), so the tool and the producers
carry one definition, and src/test_donor_pool.py holds the tool's pool equal to this one.
"""
import io
import json
from pathlib import Path

import assumed_business

SD = Path(__file__).resolve().parent.parent
EXPOSURE = SD / "model" / "exposure_results.json"
#: the precision the shipped tool carries each field at (decimal places)
SEVERITY_DP, RESERVES_DP, HHI_DP = 8, 2, 6


def is_donor(o):
    """Whether a record (an observation of exposure_results.json, or a loader record) is a donor: it carries a severity,
    an opening reserve above zero and a concentration. A record the loader sets aside has no severity, so it is not."""
    opening = o.get("opening_reserves_gbp_m")
    return (o.get("s_raw_a") is not None and opening is not None and opening > 0 and o.get("hhi") is not None)


def donor_fields(o, ritc_keys=None):
    """The donor's fields every consumer of the pool reads, at the shipped tool's precision, in the tool's order:
    syndicate, year, opening reserves, severity, concentration and the assumed-business flag (1 where the syndicate-year is
    in assumed_business.keys(), the deterministic RITC scan and the confirmed inward transfers)."""
    keys = assumed_business.keys() if ritc_keys is None else ritc_keys
    return {"syndicate": o["syndicate"], "year": o["year"],
            "opening_reserves_gbp_m": round(o["opening_reserves_gbp_m"], RESERVES_DP),
            "s_raw_a": round(o["s_raw_a"], SEVERITY_DP),
            "hhi": round(o.get("hhi", 0), HHI_DP),
            "ritc": 1 if "%s_%s" % (o["syndicate"], o["year"]) in keys else 0}


def from_observations(observations):
    """[donor fields]: the donors among `observations`, in their order."""
    keys = assumed_business.keys()
    return [donor_fields(o, keys) for o in observations if is_donor(o)]


def from_exposure_results(path=None):
    """The donor pool from model/exposure_results.json (the loader step's output), as donor-field dicts."""
    keys = assumed_business.keys()
    with io.open(str(path or EXPOSURE), encoding="utf-8") as fh:
        return [donor_fields(o, keys) for o in json.load(fh)["observations"] if is_donor(o)]
