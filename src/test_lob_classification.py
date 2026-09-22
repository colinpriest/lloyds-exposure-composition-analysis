"""An energy class is Energy, and "non-marine" is never Marine (R221, M03's mapping census, 21 September 2026).

classify_lob tried "marine" before "energy", so "Energy - Non Marine" and every other energy-headed label, and
"Non-marine treaty reinsurance", mapped to Marine. The taxonomy keeps Energy as its own category, and Lloyd's
classes offshore (marine) and onshore (non-marine) energy together as Energy.
"""
import glob
import io
import json
import os
import re

import numpy as np
import pytest

import run_analysis as ra

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENERGY, MARINE = ra.LOB_INDEX["Energy"], ra.LOB_INDEX["Marine"]


@pytest.mark.parametrize("label", ["Energy - Non Marine", "Energy non-marine", "Energy-non marine",
                                   "Energy - Non- marine", "Direct insurance: Energy - Non Marine",
                                   "Energy - Marine", "Energy marine", "Energy-Marine and Non Marine", "Energy"])
def test_an_energy_class_is_energy(label):
    assert ra.classify_lob(label) == ENERGY


def test_non_marine_reinsurance_is_not_marine():
    assert ra.classify_lob("Non-marine treaty reinsurance") == ra.LOB_INDEX["Aggregate"]


@pytest.mark.parametrize("label, name", [("Marine", "Marine"), ("Marine hull", "Marine"), ("Cargo", "Marine"),
                                         ("Marine & Energy", "Marine"),
                                         ("Fire and Other damage to Property", "Property"),
                                         ("Third party liability", "Casualty"), ("Aviation", "Aviation"),
                                         ("Reinsurance acceptances", "Aggregate")])
def test_the_other_rules_are_unchanged(label, name):
    assert ra.classify_lob(label) == ra.LOB_INDEX[name]


def test_no_committed_mix_reads_energy_or_non_marine_as_marine():
    """Every class label in the committed records' mixes."""
    labels = set()
    for path in glob.glob(os.path.join(HERE, "pdf_extraction", "syndicate_*_*.json")):
        d = json.load(io.open(path, encoding="utf-8"))
        mixes = [(d.get("_adobe_lob") or {}).get("gross_premium_mix") or []]
        for m in (d.get("models") or {}).values():
            mixes += [m.get("gross_premium_mix") or [], (m.get("_adobe_lob") or {}).get("gross_premium_mix") or []]
        labels |= {str(e.get("line_of_business") or "").strip() for mix in mixes for e in mix}
    assert len(labels) > 100
    wrong = sorted(lab for lab in labels
                   if (re.search(r"non[\s-]*marine", lab, re.I) or re.match(r"(?i)^(?:direct insurance\s*:\s*)?energy\b",
                                                                        lab)) and ra.classify_lob(lab) == MARINE)
    assert wrong == [], wrong


def test_1856_2018s_complete_table_through_the_loaders_weights():
    """Page 27 of 1856/2018's filing (Note 2, 2018, GBP000): seven classes, 143,968 in all, 120,770 of it
    reinsurance. Through the loader's own mapping, floor and HHI the complete table gives 0.697; the three
    classes the text fallback read gave the 0.416 Table 9 printed."""
    mix = [("Marine", 74), ("Aviation", 4490), ("Energy-Marine", 1376), ("Energy Non-Marine", 4390),
           ("Fire and Other damage to Property", 6520), ("Third party liability", 6348), ("Reinsurance", 120770)]
    gpm = [{"line_of_business": k, "amount_gbp_m": v / 1000.0} for k, v in mix]
    total = sum(v for _, v in mix) / 1000.0
    assert total == pytest.approx(143.968)
    w, source = ra.build_weight_vector(gpm, total)
    assert source == "premium_mix"
    w, _ = ra.apply_weight_floor(w, floor=ra.ANALYSIS_CONFIG["lob_weight_floor"])
    assert ra.compute_hhi(w) == pytest.approx(0.6966, abs=5e-4)
    part = [e for e in gpm if e["line_of_business"] in ("Fire and Other damage to Property",
                                                        "Third party liability", "Energy-Marine")]
    w3, _ = ra.build_weight_vector(part, sum(e["amount_gbp_m"] for e in part))
    w3, _ = ra.apply_weight_floor(w3, floor=ra.ANALYSIS_CONFIG["lob_weight_floor"])
    assert abs(ra.compute_hhi(w3) - 0.416) > 0.001      # Energy-Marine is Energy now, not Marine
