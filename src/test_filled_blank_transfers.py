"""A figure a route filled after both models refused it for a transfer is in the regime or excluded (R221, M02).

1856/2018 and 3268/2020 each took on another syndicate's older reserves in the report year. Both extraction models
left the development figure blank and gave the transfer as the reason; the triangle route filled the blank; and
neither record reached the assumed-business regime, because no scanner could see 1856/2018's sentence and the RITC
scan dated 3268/2020's to another year. The models' own words were evidence that the regime's sources did not
read. This test holds every working-sample record to them: where every model's blank was filled by a route and
every model's notes blame a transfer, the record is in the regime (assumed_business.py) or is excluded from the
sample by the take-on register.
"""
import glob
import io
import json
import os
import re

import assumed_business as ab

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRANSFER = re.compile(r"\bRITC\b|reinsur\w*[- ]to[- ]close|\btransferr?(?:ed|ing|s)?\b|\bquota[- ]?shares?\b|\bQS\b|"
                      r"\bLPTs?\b|loss portfolio|portfolio transfer|\bnovat\w*|\bcommut\w*|\btake[- ]?on\b|"
                      r"\btaken on\b", re.I)
REASON = re.compile(r"distort\w*|unreliab\w*|not reliab\w*|unsuitab\w*|could not|cannot|can't|not possible|"
                    r"\bnull\b|excluded?|not (?:be )?(?:used|usable|extracted|comparable|meaningful|derived)|"
                    r"contaminat\w*|\bdue to\b|\bbecause\b|owing to|as a result|affect\w*|impact\w*|"
                    r"not reflect\w*|inflat\w*|misleading", re.I)


def _sentences(text):
    flat = re.sub(r"\s+", " ", text or "").strip()
    return [s for s in re.split(r"(?<=[.;])\s+(?=[A-Z(\"'])", flat) if s]


def blamed_on_a_transfer(record):
    """Every model block's blank was filled by a route, and every model's notes blame a transfer for it."""
    models = record.get("models") or {}
    if len(models) < 2:
        return False
    for block in models.values():
        if (block.get("_pyd_route") or {}).get("note") != "filled a blank model value":
            return False
        if not any(TRANSFER.search(s) and REASON.search(s) for s in _sentences(block.get("data_quality_notes"))):
            return False
    return True


def _working_sample():
    ex = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))
    return {"%s_%s" % (o["syndicate"], o["year"]) for o in ex["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}


def _blamed():
    out = set()
    for path in glob.glob(os.path.join(HERE, "pdf_extraction", "syndicate_*_*.json")):
        stem = os.path.basename(path)[len("syndicate_"):-len(".json")]
        if blamed_on_a_transfer(json.load(io.open(path, encoding="utf-8"))):
            out.add(stem)
    return out


def test_the_detector_sees_the_records_that_escaped():
    """Control: the census that found 1856/2018 and 3268/2020 finds them here too."""
    assert {"1856_2018", "3268_2020"} <= _blamed()


def test_the_detector_needs_both_models_and_a_reason():
    filled = {"_pyd_route": {"note": "filled a blank model value"}}
    blamed = dict(filled, data_quality_notes="The RITC from Syndicate 1955 distorts the claims development table.")
    mention = dict(filled, data_quality_notes="The syndicate accepted an RITC in the year.")
    assert blamed_on_a_transfer({"models": {"a": blamed, "b": blamed}})
    assert not blamed_on_a_transfer({"models": {"a": blamed, "b": mention}})
    assert not blamed_on_a_transfer({"models": {"a": blamed, "b": dict(blamed, _pyd_route={"note": "x"})}})


def test_every_such_working_sample_record_is_in_the_regime_or_excluded():
    takeon = json.load(io.open(os.path.join(HERE, "data", "takeon_not_development.json"), encoding="utf-8"))
    excluded = {k for k in takeon if not k.startswith("_")}
    regime = ab.keys()
    loose = sorted(k for k in _blamed() & _working_sample() if k not in regime and k not in excluded)
    assert loose == [], loose
