"""The README's stamped headline fit is the formatting of the calibration's unrounded posterior means.

src/record_tests.py stamps the README's "Headline fit" clause from model/dispersion_calibration_ritc.json. It read
the params block, whose means are rounded to 3 dp, and formatted them again to 2 dp: nu_ritc 5.7446 was stored as
5.745 and printed 5.75, where the paper and the tool print 5.74 (round 62's verification, N-V-A-1). The stamp now
formats the top-level, unrounded means. These tests hold the function to that on a record built so the two
roundings differ, and the committed README to the unrounded values, each formatted independently of the function.

Run:  python -m pytest src/test_readme_stamp.py -q
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import record_tests as RT  # noqa: E402

CALIBRATION = os.path.join(HERE, "model", "dispersion_calibration_ritc.json")
README = os.path.join(HERE, "README.md")
FORMATS = (("k", "k", "%.2f"), ("gamma", "gamma", "%.2f"), ("sd_undiv", "sigma_undiv", "%.3f"),
           ("nu_clean", "nu_clean", "%.2f"), ("nu_ritc", "nu_ritc", "%.2f"))


def _flat(text):
    return " ".join(text.split())


def test_the_headline_fit_is_formatted_from_the_unrounded_means():
    """A record whose 3-dp copies round the other way at 2 dp: only the unrounded values give the right text."""
    cal = {"k": 0.58213, "gamma": 0.44291, "sd_undiv": 0.0326914, "nu_clean": 4.777346, "nu_ritc": 5.744582,
           "posterior_prob": {"nu_ritc_lt_nu_clean": 0.496},
           "params": {"k": {"mean": 0.582}, "gamma": {"mean": 0.443}, "sd_undiv": {"mean": 0.033},
                      "nu_clean": {"mean": 4.777}, "nu_ritc": {"mean": 5.745}}}
    text = _flat(RT.headline_fit_text(cal))
    assert "`nu_ritc ≈ 5.74`" in text, text
    for got in ("`k ≈ 0.58`", "`gamma ≈ 0.44`", "`sigma_undiv ≈ 0.033`", "`nu_clean ≈ 4.78`",
                "`P(nu_ritc < nu_clean) = 0.50`"):
        assert got in text, got


def test_the_committed_readme_carries_the_unrounded_headline_fit():
    cal = json.load(io.open(CALIBRATION, encoding="utf-8"))
    readme = _flat(io.open(README, encoding="utf-8").read())
    assert _flat(RT.headline_fit_text(cal)) in readme, "README is not stamped: run python src/record_tests.py --stamp"
    for key, label, fmt in FORMATS:
        assert "`%s ≈ %s`" % (label, fmt % cal[key]) in readme, (label, cal[key])
    assert "`P(nu_ritc < nu_clean) = %.2f`" % cal["posterior_prob"]["nu_ritc_lt_nu_clean"] in readme
    assert "Headline fit (n=%d gross-basis" % cal["n"] in readme
