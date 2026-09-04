#!/usr/bin/env python3
"""
Lloyd's Exposure Composition Analysis
=====================================
Reads syndicate JSON extractions, classifies data quality, computes LoB weights,
severity distributions, runs statistical analyses (N0-N4), and emits exposure_results.json.

Spec version: 2.0
Dependencies: Python 3.9+, numpy (no pandas/scipy/statsmodels/sklearn)
"""

import json
import glob
import hashlib
import math
import sys
import uuid
import re
import csv as _csv_mod
import subprocess as _subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict, Counter
from typing import Any, Optional

import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; import matplotlib.ticker as mticker

try:
    from openpyxl import Workbook as _XlWorkbook
    _HAS_XLSX = True
except ImportError:
    _HAS_XLSX = False

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SPEC_VERSION = "2.0"
SCRIPT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SCRIPT_DIR / "pdf_extraction"
OUTPUT_FILE = SCRIPT_DIR / "model" / "exposure_results.json"

# ─────────────────────────────────────────────────────────────────────────────
# FX conversion to GBP (single-currency dataset) — see docs/fx-conversion.md
#
# Each report's presentation currency comes from currency_scan.json
# (provenance-backed: statement page/heading/quote, or unit headers, or the
# dual-LLM field for scanned PDFs). USD-presented reports are converted to GBP
# at the reporting-date spot rate — the last Fed H.10 business-day rate on or
# before 31 December of the reporting year (fx_rates_h10.json):
#     GBP = USD / (USD per GBP)
# Ratios (pyd_pct, LoB weights, HHI, severities S = PYD/reserves) are
# currency-invariant; the conversion affects monetary levels only.
# ─────────────────────────────────────────────────────────────────────────────

FX_RATES_FILE = SCRIPT_DIR / "model" / "fx_rates_h10.json"
CURRENCY_SCAN_FILE = DATA_DIR / "currency_scan.json"


def _load_fx_tables():
    try:
        with open(CURRENCY_SCAN_FILE, encoding="utf-8") as f:
            cs = json.load(f)
        with open(FX_RATES_FILE, encoding="utf-8") as f:
            fx = json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"FX inputs missing ({e.filename}); run src/currency_scan.py --pdf-dir "
            "<extraction repo>/syndicate_reports/pdfs and src/fetch_h10_rates.py first "
            "(see docs/fx-conversion.md)") from e
    currencies = {k: v["currency"] for k, v in cs["reports"].items()}
    rates = {int(y): r for y, r in fx["year_end_rates"].items()}
    return currencies, rates, cs, fx


FX_CURRENCIES, FX_RATES, FX_SCAN_META, FX_H10_META = _load_fx_tables()


def _convert_gbp_m_fields(obj, rate):
    """Recursively divide every numeric *_gbp_m field by the USD/GBP rate."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_gbp_m") and isinstance(v, (int, float)):
                obj[k] = v / rate
            else:
                _convert_gbp_m_fields(v, rate)
    elif isinstance(obj, list):
        for v in obj:
            _convert_gbp_m_fields(v, rate)


def apply_fx_conversion(data, cm, fname):
    """Convert a USD-presented report's monetary fields to GBP IN PLACE (the
    loaded JSON is never written back), covering the canonical model record and
    the deterministic _adobe_lob block. Returns the fx info recorded on the
    parsed record. Raises on any currency other than GBP/USD (those require
    explicit instructions per the research direction)."""
    key = fname.replace("syndicate_", "").replace(".json", "")
    currency = FX_CURRENCIES.get(key, "UNDETERMINED")
    if currency in ("GBP", "UNDETERMINED"):
        return {"report_currency": currency, "fx_applied": False,
                "fx_rate_usd_per_gbp": None, "fx_rate_date": None}
    if currency != "USD":
        raise RuntimeError(f"{fname}: unhandled report currency {currency!r} — "
                           "non-GBP/USD reports need explicit instructions")
    year = int(key.rsplit("_", 1)[1])
    ri = FX_RATES.get(year)
    if ri is None:
        raise RuntimeError(f"{fname}: no H.10 year-end USD/GBP rate for {year}")
    rate = ri["usd_per_gbp"]
    _convert_gbp_m_fields(cm, rate)
    if isinstance(data.get("_adobe_lob"), (dict, list)):
        _convert_gbp_m_fields(data["_adobe_lob"], rate)
    return {"report_currency": "USD", "fx_applied": True,
            "fx_rate_usd_per_gbp": rate, "fx_rate_date": ri["date_used"]}

LOB_NAMES = [
    "Property",              # 0
    "Casualty",              # 1
    "Marine",                # 2
    "Energy",                # 3
    "Motor",                 # 4
    "Aviation",              # 5
    "Reinsurance — Property",  # 6
    "Reinsurance — Casualty",  # 7
    "Reinsurance — Specialty", # 8
    "Professional Lines",    # 9
    "Accident & Health",     # 10
    "Cyber",                 # 11
    "Aggregate",             # 12
]
N_LOBS = len(LOB_NAMES)
LOB_INDEX = {name: i for i, name in enumerate(LOB_NAMES)}

# Priority-ordered keyword matching rules: (priority, lob_index, keywords)
# Lower priority number = higher precedence
LOB_KEYWORD_RULES = [
    (1,  6,  ["reinsurance property", "property treaty", "property reinsurance"]),
    (2,  7,  ["reinsurance casualty", "casualty treaty", "casualty reinsurance"]),
    (3,  8,  ["reinsurance specialty", "specialty treaty", "specialty reinsurance"]),
    (4,  9,  ["professional", "d&o", "directors", "e&o", "pi", "financial lines"]),
    (5,  10, ["accident", "health", "a&h", "personal accident"]),
    (6,  5,  ["aviation"]),
    (7,  11, ["cyber"]),
    (8,  0,  ["property", "fire", "damage to property"]),
    (9,  1,  ["casualty", "third party liability", "liability"]),
    (10, 2,  ["marine", "hull", "cargo", "transit"]),
    (11, 3,  ["energy"]),
    (12, 4,  ["motor"]),
    (13, 12, ["aggregate", "miscellaneous", "other", "whole account", "reinsurance"]),
]

# LoB beta coefficients are estimated from data in analysis_n3 (James-Stein shrinkage).
# No hardcoded priors — the shrinkage target is the observation-weighted mean of estimated LoB betas.
LOB_BETA_COEFFICIENTS = {}  # populated after N3 analysis
OVERALL_BETA_DEFAULT = 0.0  # populated after N3 analysis
REFERENCE_SIZE = 500.0

CAUSE_RULES = [
    ("covid",              ["covid", "pandemic"]),
    ("ogden",              ["ogden"]),
    ("natural_cat",        ["catastrophe", "cat", "hurricane", "flood", "earthquake", "wildfire", "storm", "typhoon"]),
    ("man_made",           ["man-made", "explosion",  "collision"]),  # "fire" standalone handled specially
    ("social_inflation",   ["social inflation", "litigation", "nuclear verdict"]),
    ("economic_inflation", ["economic inflation", "claims cost", "cost inflation"]),
    ("large_loss",         ["large loss", "large claim"]),
    ("court_rulings",      ["court", "ruling", "legal"]),
    ("ibnr",               ["ibnr", "incurred but not reported"]),
    ("regulatory",         ["regulatory", "regulation", "solvency"]),
    ("methodology",        ["methodology", "reserving approach", "assumption"]),
    ("geopolitical",       ["geopolitical", "sanctions", "war"]),
    ("reinsurance",        ["reinsurance", "recoveries"]),
    ("adverse_dev",        ["adverse", "deterioration", "prior year", "strengthening"]),
]

TEST_PORTFOLIOS = [
    {"name": "Prop-heavy £200m",
     "weights": {"Property": 0.60, "Casualty": 0.20, "Marine": 0.10, "Professional Lines": 0.10},
     "size": 200},
    {"name": "Prop-heavy £500m",
     "weights": {"Property": 0.60, "Casualty": 0.20, "Marine": 0.10, "Professional Lines": 0.10},
     "size": 500},
    {"name": "Prop-heavy £2bn",
     "weights": {"Property": 0.60, "Casualty": 0.20, "Marine": 0.10, "Professional Lines": 0.10},
     "size": 2000},
    {"name": "Cas-heavy £200m",
     "weights": {"Property": 0.15, "Casualty": 0.50, "Professional Lines": 0.20, "Reinsurance — Casualty": 0.15},
     "size": 200},
    {"name": "Cas-heavy £500m",
     "weights": {"Property": 0.15, "Casualty": 0.50, "Professional Lines": 0.20, "Reinsurance — Casualty": 0.15},
     "size": 500},
    {"name": "Cas-heavy £2bn",
     "weights": {"Property": 0.15, "Casualty": 0.50, "Professional Lines": 0.20, "Reinsurance — Casualty": 0.15},
     "size": 2000},
]

HELLINGER_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0]

ANALYSIS_CONFIG = {
    "lob_weight_floor": 0.01,
    "lob_severity_cap": 5.0,
    "reserve_min_for_n3": 5.0,
    "min_events_for_fe": 3,
    "min_obs_per_lob": 10,
    "reference_size_m": REFERENCE_SIZE,
    "market_reference_mix": "equal_weighted",
    "sign_correction_rule": "trust_direction_field",
    "movement_allocation_fallback": "proportional_to_lob_weights",
    "bootstrap_replicates": 500,
    "bootstrap_seed": 42,
    "leave_out_iterations": 200,
    "leave_out_fraction": 0.10,
    "primary_estimator": "RE-GLS with syndicate random intercepts",
    "winsorisation": "none",
    "lob_coefficients": "data-driven (James-Stein shrinkage from N3)",
    "overall_beta_default": "data-driven (observation-weighted mean of LoB betas)",
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def safe_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def percentile_linear(arr, q):
    """Linear interpolation percentile (like numpy default)."""
    if len(arr) == 0:
        return None
    a = np.array(sorted(arr), dtype=float)
    return float(np.percentile(a, q))


def var_at(arr, level):
    """VaR at given level (e.g. 0.99) using linear interpolation."""
    if len(arr) == 0:
        return None
    a = np.sort(np.array(arr, dtype=float))
    return float(np.percentile(a, level * 100))


def tvar_at(arr, level):
    """TVaR (Expected Shortfall) at given level."""
    if len(arr) == 0:
        return None
    a = np.sort(np.array(arr, dtype=float))
    threshold = np.percentile(a, level * 100)
    exceedances = a[a >= threshold]
    if len(exceedances) == 0:
        return float(threshold)
    return float(np.mean(exceedances))


def hellinger_distance(p, q):
    """Hellinger distance between two weight vectors."""
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    # Normalise
    sp = p.sum()
    sq = q.sum()
    if sp > 0:
        p = p / sp
    if sq > 0:
        q = q / sq
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def compute_hhi(weights):
    """HHI from weight vector."""
    w = np.array(weights, dtype=float)
    s = w.sum()
    if s <= 0:
        return 1.0
    w = w / s
    return float(np.sum(w ** 2))


def hash_file_contents(paths):
    """SHA256 of concatenated file contents for provenance."""
    h = hashlib.sha256()
    for p in sorted(paths):
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def hash_script():
    """SHA256 of this script."""
    h = hashlib.sha256()
    with open(__file__, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def median_val(arr):
    if not arr:
        return None
    return float(np.median(arr))


def mean_val(arr):
    if not arr:
        return None
    return float(np.mean(arr))


def std_val(arr):
    if not arr:
        return None
    if len(arr) < 2:
        return 0.0
    return float(np.std(arr, ddof=1))


def cv_pct(arr):
    """Coefficient of variation as percentage."""
    if not arr or len(arr) < 2:
        return None
    m = np.mean(arr)
    if abs(m) < 1e-15:
        return None
    return float(np.std(arr, ddof=1) / abs(m) * 100)


# ─────────────────────────────────────────────────────────────────────────────
# LoB classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_lob(lob_name: str) -> int:
    """Map a LoB name string to standard LoB index using priority keyword rules."""
    name_lower = lob_name.lower().strip()
    for _priority, lob_idx, keywords in LOB_KEYWORD_RULES:
        for kw in keywords:
            if kw in name_lower:
                return lob_idx
    return 12  # Default to Aggregate


# ──────────────────────────────────────────────
# Basis of the prior-year development figure (round 51 of the paper review)
# ──────────────────────────────────────────────
# The extraction prompt asks for the GROSS movement and falls back to a net
# figure only when no gross source exists, flagging the fallback in
# data_quality_notes; the deterministic triangle pass then overrides the model's
# figure with the triangle-derived one whenever a triangle parses, whatever its
# basis. Severity divides the figure by GROSS opening reserves, so a net figure
# understates it. The basis is therefore assigned explicitly, from structured
# evidence first and a committed adjudication register second, and only a
# gross-basis observation enters the working sample.
PYD_BASIS_REGISTER = SCRIPT_DIR / "data" / "pyd_basis_register.json"
OVERRIDE_TAG = re.compile(
    r"\[(?:RAG|CODE|RAG DIRECTION) OVERRIDE: (?:Model|LLM) said PYD=(-?\d+(?:\.\d+)?)[^\]]*?"
    r"(?:RAG triangle computed|but code computed) \+?(-?\d+(?:\.\d+)?)")


def load_pyd_basis_register():
    with open(PYD_BASIS_REGISTER, "r", encoding="utf-8") as f:
        reg = json.load(f)
    return {k: v for k, v in reg.items() if not k.startswith("_")}


def pyd_basis(cm, key, register):
    """(basis, source) for the development figure of one extraction model block.

    basis is "gross", "net" or "unknown". In order:
      1. a pipeline override tag whose computed value is the recorded figure:
         the figure is triangle-derived and carries the triangle's basis
         (_rag_triangle.type, else _claims_triangle.type; a loss-ratio triangle
         has no basis of its own and falls through);
      2. the adjudication register (data/pyd_basis_register.json), which quotes
         the extraction note it rests on;
      3. a net claims triangle in the record, which the pipeline treats as
         authoritative for the figure;
      4. otherwise gross, the basis the prompt defines the field on: a default in
         the absence of contrary evidence, labelled as such, not a confirmation.
    """
    notes = cm.get("data_quality_notes") or ""
    pyd = safe_float(cm.get("prior_year_development_gbp_m"))
    tags = OVERRIDE_TAG.findall(notes)
    if tags and pyd is not None:
        computed = safe_float(tags[-1][1])
        if computed is not None and abs(abs(computed) - abs(pyd)) <= max(0.01, 0.005 * abs(pyd)):
            t = ((cm.get("_rag_triangle") or {}).get("type")
                 or (cm.get("_claims_triangle") or {}).get("type"))
            if t == "gross":
                return "gross", "triangle-override:gross"
            if t == "net":
                return "net", "triangle-override:net"
    if key in register:
        return register[key]["basis"], "register:" + register[key]["source"]
    if (cm.get("_claims_triangle") or {}).get("type") == "net":
        return "net", "net-triangle"
    return "gross", "prompt-default-gross"


def build_weight_vector(gross_premium_mix, gpw_gbp_m):
    """
    Build 13-element LoB weight vector from gross_premium_mix.
    Read priority: _adobe_lob.gross_premium_mix → model-level gross_premium_mix.
    Returns (weights, weight_source) where weight_source is 'premium_mix' or 'none'.
    """
    weights = np.zeros(N_LOBS, dtype=float)
    weight_source = "none"

    if gross_premium_mix and len(gross_premium_mix) > 0 and gpw_gbp_m is not None and gpw_gbp_m > 0:
        for entry in gross_premium_mix:
            lob_name = entry.get("line_of_business", "")
            amount = safe_float(entry.get("amount_gbp_m"))
            if amount is not None and amount > 0:
                idx = classify_lob(lob_name)
                weights[idx] += amount
        total = weights.sum()
        # Reject if all weight landed in Aggregate (index 12) — likely a misparse
        # (e.g. reserves movement table instead of LoB segmentation)
        non_agg_weight = total - weights[12] if len(weights) > 12 else total
        if total > 0 and non_agg_weight > 0:
            weights = weights / total
            weight_source = "premium_mix"
        else:
            weights = np.zeros(N_LOBS, dtype=float)

    return weights, weight_source


def apply_weight_floor(weights, floor=0.01):
    """Apply minimum floor to non-zero weights, re-normalise. Returns (new_weights, floor_count)."""
    w = weights.copy()
    total = w.sum()
    if total <= 0:
        return w, 0
    w = w / total

    nonzero_mask = w > 0
    floor_count = 0
    for i in range(N_LOBS):
        if w[i] > 0 and w[i] < floor:
            floor_count += 1
            w[i] = floor

    total = w.sum()
    if total > 0:
        w = w / total
    return w, floor_count


# ─────────────────────────────────────────────────────────────────────────────
# Cause classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_cause(primary_causes, standardized_narrative):
    """Classify cause category from primary_causes and narrative."""
    text_parts = []
    if primary_causes:
        text_parts.extend(primary_causes if isinstance(primary_causes, list) else [primary_causes])
    if standardized_narrative:
        text_parts.append(str(standardized_narrative))
    text = " ".join(text_parts).lower()

    # Special handling for "fire" standalone in man_made
    for category, keywords in CAUSE_RULES:
        for kw in keywords:
            if kw in text:
                return category
        # Special: man_made includes standalone "fire"
        if category == "man_made":
            # Check standalone fire (word boundary)
            if re.search(r'\bfire\b', text):
                return "man_made"

    return "uncategorised"


# ─────────────────────────────────────────────────────────────────────────────
# Data Loading and Classification
# ─────────────────────────────────────────────────────────────────────────────

def load_and_classify():
    """Load all syndicate JSON files, classify, and return parsed records."""
    pattern = str(DATA_DIR / "syndicate_*.json")
    files = sorted(glob.glob(pattern))
    log(f"Found {len(files)} syndicate JSON files")

    records = []
    counters = {
        "total_files": len(files),
        "excluded": 0,
        "skipped": 0,
        "in_runoff": 0,
        "reliable": 0,
        "incomplete": 0,
        "sign_flips": 0,
        "cap_binding_pos": 0,
        "cap_binding_neg": 0,
        "lob_floor_count": 0,
        "no_reserves": 0,
        "proportional_allocation_count": 0,
        "reserve_source_dist": defaultdict(int),
        "weight_source_dist": defaultdict(int),
        "cap_binding_by_year": defaultdict(int),
        "lob_floor_by_year": defaultdict(int),
        "fx_converted": 0,
        "fx_currency_dist": defaultdict(int),
        "net_basis_excluded": 0,
        "unknown_basis_excluded": 0,
        "pyd_basis_source_dist": defaultdict(int),
        "pyd_basis_by_source": defaultdict(lambda: defaultdict(int)),
    }
    classification_log = []
    basis_register = load_pyd_basis_register()

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        fname = Path(fpath).name

        # A.2.3 Step 1: EXCLUDED
        if data.get("excluded") is True or data.get("manual_override_status") == "excluded":
            counters["excluded"] += 1
            classification_log.append({"file": fname, "status": "EXCLUDED"})
            continue

        # A.2.3 Step 2: SKIPPED
        models = data.get("models")
        has_models = models is not None and len(models) > 0
        if not has_models and (data.get("first_year_syndicate") or data.get("reason") or data.get("no_triangle_data")):
            counters["skipped"] += 1
            classification_log.append({"file": fname, "status": "SKIPPED"})
            continue

        if not has_models:
            # No models and no skip reason — treat as INCOMPLETE
            counters["incomplete"] += 1
            classification_log.append({"file": fname, "status": "INCOMPLETE", "reason": "no models"})
            continue

        # A.2.2 Model resolution
        validation = data.get("validation", {})
        model_keys = sorted(models.keys())
        canonical_key = None

        if validation.get("passed") is True:
            canonical_key = model_keys[0]
        else:
            # Find model with non-null pyd_pct
            candidates = []
            for mk in model_keys:
                m = models[mk]
                if m.get("prior_year_development_pct") is not None:
                    candidates.append((mk, m.get("prior_year_movement_confidence", 0) or 0))
            if len(candidates) == 1:
                canonical_key = candidates[0][0]
            elif len(candidates) > 1:
                canonical_key = max(candidates, key=lambda x: x[1])[0]
            # else: no candidate → INCOMPLETE

        if canonical_key is None:
            counters["incomplete"] += 1
            classification_log.append({"file": fname, "status": "INCOMPLETE", "reason": "no model with pyd_pct"})
            continue

        cm = models[canonical_key]

        # FX: single-currency (GBP) dataset — convert USD-presented reports at
        # the reporting-date H.10 spot rate before any downstream computation
        fx_info = apply_fx_conversion(data, cm, fname)
        counters["fx_currency_dist"][fx_info["report_currency"]] += 1
        if fx_info["fx_applied"]:
            counters["fx_converted"] += 1

        # A.2.3 Step 3: Classify
        pyd_pct = safe_float(cm.get("prior_year_development_pct"))
        gpw = safe_float(cm.get("gross_premiums_written_gbp_m"))
        # Read priority: _adobe_lob (deterministic extraction) → model-level (LLM fallback)
        adobe_lob = cm.get("_adobe_lob") or data.get("_adobe_lob") or {}
        gpm = adobe_lob.get("gross_premium_mix") or cm.get("gross_premium_mix", []) or []
        opening = safe_float(cm.get("opening_reserves_gbp_m"))

        has_reliable_pyd = pyd_pct is not None
        has_reliable_premium = len(gpm) > 0 and gpw is not None and gpw > 0
        is_runoff = has_reliable_pyd and not has_reliable_premium and gpw is not None and gpw == 0
        is_reliable = has_reliable_pyd and (has_reliable_premium or is_runoff)

        if is_runoff:
            counters["in_runoff"] += 1
            classification_log.append({"file": fname, "status": "IN RUNOFF"})
            continue

        # A.2.3 Step 3: Discard records with null/zero opening reserves
        if opening is None or opening <= 0.1:
            counters["no_reserves"] += 1
            classification_log.append({"file": fname, "status": "NO_RESERVES"})
            continue

        # A.2.3 Step 3b: the development figure must be on the gross basis the
        # reserves are on; a net or unknown-basis figure is recorded but excluded
        basis_key = "%s_%s" % (cm.get("syndicate", data.get("syndicate")),
                               cm.get("year", data.get("year")))
        basis, basis_source = pyd_basis(cm, basis_key, basis_register)
        counters["pyd_basis_source_dist"][basis_source.split(":")[0]] += 1
        counters["pyd_basis_by_source"][basis_source.split(":")[0]][basis] += 1
        if is_reliable and basis != "gross":
            is_reliable = False
            if basis == "net":
                dq_tag = "NET_BASIS"
                counters["net_basis_excluded"] += 1
            else:
                dq_tag = "UNKNOWN_BASIS"
                counters["unknown_basis_excluded"] += 1
            classification_log.append({"file": fname, "status": dq_tag,
                                       "basis_source": basis_source})
        elif is_reliable:
            dq_tag = "RELIABLE"
            counters["reliable"] += 1
            classification_log.append({"file": fname, "status": dq_tag})
        else:
            dq_tag = "INCOMPLETE"
            counters["incomplete"] += 1
            classification_log.append({"file": fname, "status": dq_tag})

        # A.2.5 Parse record
        syndicate = cm.get("syndicate") if cm.get("syndicate") is not None else data.get("syndicate")
        year = cm.get("year") if cm.get("year") is not None else data.get("year")
        if syndicate is None or year is None:
            log(f"  WARNING: {fname} has missing syndicate ({syndicate}) or year ({year}) — please fix this source file")
            counters["incomplete"] += 1
            classification_log.append({"file": fname, "status": "INCOMPLETE", "reason": "missing syndicate/year"})
            continue
        pyd_gbp_m = safe_float(cm.get("prior_year_development_gbp_m"))
        direction = cm.get("direction", "").lower().strip() if cm.get("direction") else None
        lob_movements = cm.get("lob_movements", []) or []
        primary_causes = cm.get("primary_causes", []) or []
        narrative = cm.get("standardized_narrative", "") or ""
        named_events = cm.get("named_events", []) or []
        confidence = safe_float(cm.get("prior_year_movement_confidence"))

        # Sign correction
        sign_flipped = False
        if pyd_gbp_m is not None and pyd_pct is not None and direction:
            # Determine expected sign from direction
            if direction == "release":
                expected_sign = -1  # release = negative development
            elif direction in ("strengthening", "adverse"):
                expected_sign = 1
            else:
                expected_sign = None

            if expected_sign is not None:
                pyd_sign = 1 if pyd_pct > 0 else (-1 if pyd_pct < 0 else 0)
                if pyd_sign != 0 and pyd_sign != expected_sign:
                    pyd_gbp_m = -pyd_gbp_m
                    sign_flipped = True
                    counters["sign_flips"] += 1

        # Opening reserves (always > 0 at this point — no_reserves filtered above)
        counters["reserve_source_dist"]["available"] += 1

        # Build LoB weight vector
        weights, weight_source = build_weight_vector(gpm, gpw)
        counters["weight_source_dist"][weight_source] += 1

        # Apply weight floor
        weights, fc = apply_weight_floor(weights)
        if fc > 0:
            counters["lob_floor_count"] += fc
            counters["lob_floor_by_year"][str(year)] = counters["lob_floor_by_year"].get(str(year), 0) + fc

        # Severity computation
        s_raw_a = None
        if (opening is not None and opening > 0 and pyd_gbp_m is not None
                and basis == "gross"):
            s_raw_a = pyd_gbp_m / opening

        # LoB-level severity
        lob_severity = np.zeros(N_LOBS, dtype=float)
        lob_severity_computed = False

        if opening is not None and opening > 0 and pyd_gbp_m is not None and weights.sum() > 0:
            # Step 1: LoB-level reserves R_l = R * max(w_l, 0.01) for non-zero weight LoBs
            r_lob = np.zeros(N_LOBS, dtype=float)
            for l in range(N_LOBS):
                if weights[l] > 0:
                    r_lob[l] = opening * max(weights[l], 0.01)

            # Step 2: Map lob_movements to standard LoBs
            movement_map = defaultdict(list)
            for mv in lob_movements:
                lob_name = mv.get("line_of_business", "")
                idx = classify_lob(lob_name)
                amt = safe_float(mv.get("amount_gbp_m"))
                mv_dir = (mv.get("direction", "") or "").lower().strip()
                # Sign the amount based on direction
                if amt is not None:
                    if mv_dir == "release" and amt > 0:
                        amt = -amt
                    elif mv_dir in ("strengthening", "adverse") and amt < 0:
                        amt = -amt
                movement_map[idx].append(amt)

            all_null = all(
                all(a is None for a in amounts)
                for amounts in movement_map.values()
            ) if movement_map else True

            if all_null and movement_map:
                # Proportional allocation
                counters["proportional_allocation_count"] += 1
                for l in range(N_LOBS):
                    if weights[l] > 0:
                        m_l = pyd_gbp_m * weights[l]
                        if r_lob[l] > 0:
                            lob_severity[l] = m_l / r_lob[l]
                        else:
                            lob_severity[l] = 0.0
                lob_severity_computed = True
            elif not all_null:
                # Sum known movements per LoB
                observed_lobs_with_amounts = set()
                for idx, amounts in movement_map.items():
                    total_amt = sum(a for a in amounts if a is not None)
                    if any(a is not None for a in amounts):
                        observed_lobs_with_amounts.add(idx)
                        if r_lob[idx] > 0:
                            lob_severity[idx] = total_amt / r_lob[idx]
                lob_severity_computed = True
            else:
                # No movements at all → proportional
                counters["proportional_allocation_count"] += 1
                for l in range(N_LOBS):
                    if weights[l] > 0:
                        m_l = pyd_gbp_m * weights[l]
                        if r_lob[l] > 0:
                            lob_severity[l] = m_l / r_lob[l]
                lob_severity_computed = True

            # Cap at ±5.0
            for l in range(N_LOBS):
                if lob_severity[l] > 5.0:
                    lob_severity[l] = 5.0
                    counters["cap_binding_pos"] += 1
                    counters["cap_binding_by_year"][str(year)] = counters["cap_binding_by_year"].get(str(year), 0) + 1
                elif lob_severity[l] < -5.0:
                    lob_severity[l] = -5.0
                    counters["cap_binding_neg"] += 1
                    counters["cap_binding_by_year"][str(year)] = counters["cap_binding_by_year"].get(str(year), 0) + 1

        # Reconstructed severity Raw-B
        s_raw_b = None
        if lob_severity_computed and weights.sum() > 0 and basis == "gross":
            s_raw_b = float(np.sum(weights * lob_severity))

        # Concentration
        hhi = compute_hhi(weights) if weights.sum() > 0 else None
        diversification = (1.0 - hhi) if hhi is not None else None
        complexity = (opening * diversification) if (opening is not None and diversification is not None) else None

        # Cause classification
        cause_category = classify_cause(primary_causes, narrative)

        record = {
            "syndicate": syndicate,
            "year": year,
            "opening_reserves_gbp_m": opening,
            "pyd_gbp_m": pyd_gbp_m,
            "pyd_pct": pyd_pct,
            "direction": direction,
            "gpw_gbp_m": gpw,
            "gross_premium_mix": gpm,
            "lob_movements": lob_movements,
            "primary_causes": primary_causes,
            "standardized_narrative": narrative,
            "named_events": named_events,
            "confidence": confidence,
            "data_quality_tag": dq_tag,
            "pyd_basis": basis,
            "pyd_basis_source": basis_source,
            "weight_source": weight_source,
            "sign_flipped": sign_flipped,
            "weights": weights.tolist(),
            "lob_severity": lob_severity.tolist(),
            "lob_severity_computed": lob_severity_computed,
            "s_raw_a": s_raw_a,
            "s_raw_b": s_raw_b,
            "hhi": hhi,
            "diversification": diversification,
            "complexity": complexity,
            "cause_category": cause_category,
            "model_key": canonical_key,
            "source_file": fname,
            "report_currency": fx_info["report_currency"],
            "fx_applied": fx_info["fx_applied"],
            "fx_rate_usd_per_gbp": fx_info["fx_rate_usd_per_gbp"],
            "fx_rate_date": fx_info["fx_rate_date"],
        }
        records.append(record)

    return records, counters, classification_log, files


# ─────────────────────────────────────────────────────────────────────────────
# Event groups
# ─────────────────────────────────────────────────────────────────────────────

def assign_event_groups(records, min_events=3):
    """Assign event_group_id to each record. Pool small groups."""
    group_counts = defaultdict(int)
    for r in records:
        gid = f"{r['year']}_{r['cause_category']}"
        group_counts[gid] += 1

    for r in records:
        gid = f"{r['year']}_{r['cause_category']}"
        if group_counts[gid] < min_events:
            r["event_group_id"] = f"{r['year']}_pooled"
        else:
            r["event_group_id"] = gid


# ─────────────────────────────────────────────────────────────────────────────
# Subsets
# ─────────────────────────────────────────────────────────────────────────────

def build_subsets(records):
    """Build subset definitions and filter records."""
    subsets = {}

    def make_subset(name, recs):
        if not recs:
            return {"n_observations": 0, "n_syndicates": 0, "year_range": None, "syndicates_per_year": None}
        years = [r["year"] for r in recs]
        syndicates = set(r["syndicate"] for r in recs)
        by_year = defaultdict(set)
        for r in recs:
            by_year[r["year"]].add(r["syndicate"])
        counts = [len(v) for v in by_year.values()]
        return {
            "n_observations": len(recs),
            "n_syndicates": len(syndicates),
            "year_range": [min(years), max(years)],
            "syndicates_per_year": {
                "min": min(counts),
                "median": float(np.median(counts)),
                "max": max(counts),
            }
        }

    dense = [r for r in records if 2014 <= r["year"] <= 2019]
    mid = [r for r in records if 2020 <= r["year"] <= 2023]
    full = [r for r in records if 2014 <= r["year"] <= 2023]
    year_2024 = [r for r in records if r["year"] == 2024]

    # Balanced subsets
    full_syndicates = defaultdict(set)
    for r in full:
        full_syndicates[r["syndicate"]].add(r["year"])

    balanced_k8 = [r for r in full if len(full_syndicates[r["syndicate"]]) >= 8]
    balanced_k6 = [r for r in full if len(full_syndicates[r["syndicate"]]) >= 6]
    balanced_all = [r for r in full if len(full_syndicates[r["syndicate"]]) >= 10]

    subsets["DENSE"] = make_subset("DENSE", dense)
    subsets["MID"] = make_subset("MID", mid)
    subsets["FULL"] = make_subset("FULL", full)
    subsets["BALANCED_K8"] = make_subset("BALANCED_K8", balanced_k8)
    subsets["BALANCED_K6"] = make_subset("BALANCED_K6", balanced_k6)
    subsets["BALANCED_ALL"] = make_subset("BALANCED_ALL", balanced_all)
    subsets["YEAR_2024"] = make_subset("YEAR_2024", year_2024)

    return subsets, {
        "DENSE": dense, "MID": mid, "FULL": full,
        "BALANCED_K8": balanced_k8, "BALANCED_K6": balanced_k6,
        "BALANCED_ALL": balanced_all, "YEAR_2024": year_2024,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Eligibility masks
# ─────────────────────────────────────────────────────────────────────────────

def compute_eligibility(records, subset_records):
    dense = subset_records["DENSE"]
    full = subset_records["FULL"]
    dense_set = set(id(r) for r in dense)
    full_set = set(id(r) for r in full)

    counts = {
        "eligible_for_distribution": 0,
        "eligible_for_boxplot_reserves": 0,
        "eligible_for_n1": 0,
        "eligible_for_n3": 0,
        "eligible_for_capital": 0,
        "eligible_for_persona": 0,
    }

    for r in records:
        rid = id(r)
        pyd = r["pyd_pct"]
        opening = r["opening_reserves_gbp_m"]

        r["eligible_for_distribution"] = pyd is not None
        r["eligible_for_boxplot_reserves"] = pyd is not None and opening is not None and opening > 0
        r["eligible_for_n1"] = pyd is not None and rid in dense_set
        r["eligible_for_n3"] = (opening is not None and opening > 5 and pyd is not None and rid in dense_set)
        # A capital-eligible donor carries a gross-basis severity: records whose
        # development is on a net or unstated basis have no s_raw_a and are not
        # transferred (the basis rule in pyd_basis()).
        r["eligible_for_capital"] = (pyd is not None and r["lob_severity_computed"]
                                     and r.get("pyd_basis") == "gross")
        r["eligible_for_persona"] = (rid in full_set and opening is not None and opening > 0
                                      and r["weight_source"] != "none")

        for k in counts:
            if r[k]:
                counts[k] += 1

    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Exposure adjustment
# ─────────────────────────────────────────────────────────────────────────────

def portfolio_weights_vector(spec):
    """Convert portfolio spec weights dict to 13-element vector."""
    w = np.zeros(N_LOBS, dtype=float)
    for lob_name, val in spec.items():
        if lob_name in LOB_INDEX:
            w[LOB_INDEX[lob_name]] = val
    return w


def mix_standardise(lob_severity, target_weights):
    """S_std = sum(w_q_l * s_il)"""
    return float(np.sum(np.array(target_weights) * np.array(lob_severity)))


def composite_beta(target_weights, lob_coefficients=None):
    """Composite beta from LoB-specific coefficients and target weights."""
    coeffs = lob_coefficients or LOB_BETA_COEFFICIENTS
    fallback = OVERALL_BETA_DEFAULT
    beta = 0.0
    for i, name in enumerate(LOB_NAMES):
        beta += target_weights[i] * coeffs.get(name, fallback)
    return beta


# Dispersion model parameters (robust Bayesian pooling) — loaded from
# dispersion_calibration.json by load_dispersion_calibration().  New form:
#   {k, gamma, nu, reference_size, reference_hhi, hhi_floor, hhi_ceil, params, ...}
COMBINED_MODEL = None


def load_dispersion_calibration(path=None):
    """Load the persisted Bayesian pooling calibration into COMBINED_MODEL (Option-A operator).

    Returns the loaded dict, or None if the calibration file is absent (the operator then
    falls back to identity).  The calibration is produced offline by calibrate_dispersion.py;
    re-run that whenever the underlying data change.
    """
    global COMBINED_MODEL
    if path:
        path = Path(path)
    else:
        # Prefer the RITC tail-regime calibration (adds nu_clean/nu_ritc for the shape-aware
        # operator); fall back to the plain floor calibration if it is absent.
        ritc_path = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
        path = ritc_path if ritc_path.exists() else (SCRIPT_DIR / "model" / "dispersion_calibration.json")
    if not path.exists():
        log(f"  WARNING: {path.name} not found — run calibrate_dispersion.py; transfer operator disabled")
        COMBINED_MODEL = None
        return None
    cal = json.loads(path.read_text(encoding="utf-8"))
    COMBINED_MODEL = {
        "k": cal["k"],
        "gamma": cal["gamma"],
        "nu": cal.get("nu"),                     # = nu_clean under the RITC regime
        "nu_clean": cal.get("nu_clean"),         # clean-composition tail index
        "nu_ritc": cal.get("nu_ritc"),           # heavier RITC-year tail index
        "lambda_ritc": cal.get("lambda_ritc"),   # log tail-weight shift (>0 => RITC heavier)
        "beta_ritc": cal.get("beta_ritc"),       # RITC scale term: fitted in the likelihood, omitted by the operator
        "sd_undiv": cal.get("sd_undiv", 0.0),   # undiversifiable floor
        "sd_div": cal.get("sd_div", 1.0),        # diversifiable SCALE at reference
                                                 # (Student-t scale, not an SD:
                                                 #  the variance may not exist)
        "reference_size": cal.get("reference_size", REFERENCE_SIZE),
        "reference_hhi": cal.get("reference_hhi", 0.4),
        "hhi_floor": cal.get("hhi_floor", 0.01),
        "hhi_ceil": cal.get("hhi_ceil", 1.0),
        "params": cal.get("params", {}),
        "posterior_prob": cal.get("posterior_prob", {}),
        "n": cal.get("n"),
        "source": path.name,
    }
    return COMBINED_MODEL


def dispersion_adjustment(r_target, hhi_target, r_obs, hhi_obs):
    """Option-A transfer multiplier from the robust Bayesian pooling model.

    Returns sigma(r_target, hhi_target) / sigma(r_obs, hhi_obs) — the SCALE ratio, not
    an SD ratio: sigma is the Student-t scale parameter and the fitted tail puts
    little mass above nu=3, so the variance need not exist — so that
    multiplying an observed severity by this factor transfers it to the target
    (size, concentration) profile.  The operator *is* the fitted dispersion model, which
    carries an undiversifiable scale floor plus a diversifiable power term:

        sigma(R, H) = sqrt( sd_undiv^2 + sd_div^2 * [ (R/R_ref) (1/H)^gamma ]^{2(k-1)} )

    where sd_undiv is the undiversifiable floor (dispersion of an arbitrarily large,
    diversified book), sd_div the diversifiable scale at the reference, k the pooling
    exponent and gamma the effective-line (n_eff = 1/H) concentration exponent.  When
    sd_undiv = 0 this reduces to the pure power ratio (R_t/R_o)^(k-1) (H_o/H_t)^(gamma(k-1)).
    There is no line-level projection, and no NEW reporting-year shock is drawn for
    the target: no eta_t is fitted or applied for it. The donor's realised year
    disturbance is still carried across, because this ratio multiplies a raw
    severity -- for a clean donor S_i = exp(eta_t)*sigma_i*eps_i maps to
    exp(eta_t)*sigma_q*eps_i, so the year effect survives, rescaled.
    The location is fixed at zero in the FIT, which is not the same as removing it from
    the transfer: this ratio multiplies a raw severity, so a donor's realised level is
    carried across, scaled by the same ratio. See check_operator_properties.py, which
    tests exactly that.
    """
    if COMBINED_MODEL is None:
        return 1.0

    k = COMBINED_MODEL["k"]
    gamma = COMBINED_MODEL["gamma"]
    su = COMBINED_MODEL.get("sd_undiv", 0.0)
    sd = COMBINED_MODEL.get("sd_div", 1.0)
    ref = COMBINED_MODEL.get("reference_size", REFERENCE_SIZE)
    lo = COMBINED_MODEL.get("hhi_floor", 0.01)
    hi = COMBINED_MODEL.get("hhi_ceil", 1.0)

    def sigma_sys(R, H):
        H = min(max(H if H is not None else hi, lo), hi)
        reff_rel = (max(R, 1e-9) / ref) * (1.0 / H) ** gamma
        return math.sqrt(su * su + sd * sd * reff_rel ** (2.0 * (k - 1.0)))

    denom = sigma_sys(r_obs, hhi_obs)
    return sigma_sys(r_target, hhi_target) / denom if denom > 0 else 1.0


def size_factor(r_q, beta_w):
    """Legacy size adjustment factor — kept for backward compatibility."""
    if r_q is None or r_q <= 0:
        return 1.0
    if COMBINED_MODEL is not None:
        # Use combined model with median HHI as reference
        ref_hhi = COMBINED_MODEL.get("reference_hhi", 0.4)
        return dispersion_adjustment(r_q, ref_hhi, REFERENCE_SIZE, ref_hhi)
    return (r_q / REFERENCE_SIZE) ** beta_w


def compute_reference_mean(records):
    """Compute the market reference mean PYD% and test whether it differs from zero.

    Returns (mu, is_significant, t_stat, p_value) where:
    - mu = sample mean if significantly different from zero (p < 0.05), else 0.0
    - The test determines whether standardised distributions should be centred on
      the sample mean or on zero.
    """
    pyd_pcts = [r["pyd_pct"] for r in records if r.get("pyd_pct") is not None]
    if len(pyd_pcts) < 2:
        return 0.0, False, 0.0, 1.0
    arr = np.array(pyd_pcts, dtype=float)
    n = len(arr)
    mean = float(np.mean(arr))
    se = float(np.std(arr, ddof=1) / np.sqrt(n))
    if se == 0:
        return mean, False, 0.0, 1.0
    t_stat = mean / se
    # Two-sided p-value (normal approximation, valid for large n)
    z = abs(t_stat)
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2))))
    is_sig = p_val < 0.05
    mu = mean if is_sig else 0.0
    return mu, is_sig, float(t_stat), float(p_val)


def recentre_standardised(std_values, raw_values, mu):
    """Re-centre standardised values so their mean equals mu.

    Standardisation (mix + size adjustment) changes dispersion but should not shift
    the mean, since ANOVA shows means do not vary significantly by size or complexity.
    This function removes the spurious mean shift introduced by the nonlinear
    size adjustment (Jensen's inequality) and LoB reweighting.

    S_recentred_i = S_std_i - mean(S_std) + mu
    """
    if not std_values:
        return std_values
    arr = np.array(std_values, dtype=float)
    std_mean = float(np.mean(arr))
    shift = mu - std_mean
    return [float(v + shift) for v in arr]


def compute_four_distributions(records, target_weights, target_size, target_hhi=None, eligible_key="eligible_for_capital"):
    """Compute naive, mix-only, size-only, full severity distributions.

    Uses the combined dispersion model (size + HHI) when available.
    target_hhi: HHI of the target portfolio. If None, computed from target_weights.
    """
    tw = np.array(target_weights, dtype=float)
    if target_hhi is None:
        target_hhi = float(np.sum((tw / max(tw.sum(), 1e-10)) ** 2))

    naive = []
    concentration_only = []
    size_only = []
    full_adj = []

    for r in records:
        if not r.get(eligible_key, False):
            continue
        s_a = r["s_raw_a"]
        if s_a is None:
            continue

        # Option-A transfer: scale the raw severity from observed (R_obs, HHI_obs) to the
        # target (R_target, HHI_target) via the pooling operator.  No line-level projection.
        r_obs = r.get("opening_reserves_gbp_m") or REFERENCE_SIZE
        hhi_obs = r.get("hhi") or target_hhi
        lam_size = dispersion_adjustment(target_size, hhi_obs, r_obs, hhi_obs)   # size only
        lam_conc = dispersion_adjustment(r_obs, target_hhi, r_obs, hhi_obs)      # concentration only
        lam_full = dispersion_adjustment(target_size, target_hhi, r_obs, hhi_obs)  # size + concentration

        naive.append(s_a)
        concentration_only.append(max(s_a * lam_conc, -1.0))
        size_only.append(max(s_a * lam_size, -1.0))
        full_adj.append(max(s_a * lam_full, -1.0))

    return naive, concentration_only, size_only, full_adj


def compute_capital_metrics(naive, concentration_only, size_only, full_adj):
    """Compute VaR/TVaR at 99%/99.5% and a size vs concentration Shapley decomposition."""
    result = {}
    for label, arr in [("naive", naive), ("concentration_only", concentration_only),
                       ("size_only", size_only), ("full", full_adj)]:
        result[label] = {
            "n": len(arr),
            "var_99": var_at(arr, 0.99),
            "var_995": var_at(arr, 0.995),
            "tvar_99": tvar_at(arr, 0.99),
            "tvar_995": tvar_at(arr, 0.995),
        }

    # Shapley (size vs concentration)
    shapley = {}
    for metric in ["var_99", "var_995", "tvar_99", "tvar_995"]:
        v_n = result["naive"].get(metric)
        v_c = result["concentration_only"].get(metric)
        v_s = result["size_only"].get(metric)
        v_f = result["full"].get(metric)
        if all(v is not None for v in [v_n, v_c, v_s, v_f]):
            concentration_effect = 0.5 * ((v_c - v_n) + (v_f - v_s))
            size_effect = 0.5 * ((v_s - v_n) + (v_f - v_c))
            shapley[metric] = {
                "concentration_effect": concentration_effect,
                "size_effect": size_effect,
                "total_effect": concentration_effect + size_effect,
            }
        else:
            shapley[metric] = {"concentration_effect": None, "size_effect": None, "total_effect": None}

    # Add flat convenience keys for HTML viewer
    shapley["concentration_995"] = shapley["var_995"]["concentration_effect"]
    shapley["size_995"] = shapley["var_995"]["size_effect"]
    shapley["concentration_99"] = shapley["var_99"]["concentration_effect"]
    shapley["size_99"] = shapley["var_99"]["size_effect"]

    result["shapley"] = shapley
    return result


# ─────────────────────────────────────────────────────────────────────────────
# OLS / RE-GLS helpers
# ─────────────────────────────────────────────────────────────────────────────

def local_quantile_regression(x, y, taus=(0.10, 0.90), n_grid=60, k_neighbours=None):
    """Non-parametric kernel-weighted local quantile regression.

    Uses adaptive bandwidth: at each grid point, the bandwidth is the distance
    to the k-th nearest neighbour, so the kernel always captures a fixed number
    of data points regardless of local density.

    Returns list of dicts: [{x, q10, q90, median}, ...].
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)

    # Default: use ~30% of data at each point (smooth but adaptive)
    if k_neighbours is None:
        k_neighbours = max(15, int(0.30 * n))
    k_neighbours = min(k_neighbours, n - 1)

    # Epanechnikov kernel
    def epan(u):
        return np.where(np.abs(u) <= 1, 0.75 * (1 - u ** 2), 0.0)

    # Weighted quantile via sorted cumulative weights
    def weighted_quantile(values, weights, tau):
        idx = np.argsort(values)
        sv, sw = values[idx], weights[idx]
        cum = np.cumsum(sw)
        if cum[-1] <= 0:
            return float(np.percentile(values, tau * 100))
        cum /= cum[-1]
        j = min(int(np.searchsorted(cum, tau)), len(sv) - 1)
        return float(sv[j])

    # Grid: spaced by data density (percentiles of x)
    grid = np.percentile(x, np.linspace(2, 98, n_grid))

    results = []
    for x0 in grid:
        # Adaptive bandwidth: distance to k-th nearest neighbour
        dists = np.abs(x - x0)
        sorted_dists = np.sort(dists)
        local_bw = float(sorted_dists[k_neighbours])
        if local_bw <= 0:
            local_bw = float(sorted_dists[-1]) / 2

        w = epan((x - x0) / local_bw)
        if np.count_nonzero(w) < 3:
            continue
        point = {"x": float(x0)}
        for tau in taus:
            point[f"q{int(tau*100)}"] = weighted_quantile(y, w, tau)
        point["median"] = weighted_quantile(y, w, 0.5)
        results.append(point)

    return results


def ols_fit(X, y):
    """OLS via numpy least squares. Returns (beta, residuals, hat_matrix_diag)."""
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    try:
        beta, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        beta = np.zeros(X.shape[1])
        residuals = y.copy()
    resid = y - X @ beta
    return beta, resid


def ols_with_se(X, y):
    """OLS with standard errors."""
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n, k = X.shape
    beta, resid = ols_fit(X, y)
    if n <= k:
        se = np.full(k, np.nan)
        return beta, se, resid
    sigma2 = np.sum(resid ** 2) / (n - k)
    try:
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        se = np.full(k, np.nan)
    return beta, se, resid



def cluster_robust_se(X, y, beta, cluster_ids):
    """Cluster-robust (CR1) standard errors."""
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n, k = X.shape
    resid = y - X @ beta
    clusters = np.unique(cluster_ids)
    G = len(clusters)

    try:
        XtX_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return np.full(k, np.nan)

    meat = np.zeros((k, k))
    for c in clusters:
        mask = cluster_ids == c
        Xc = X[mask]
        ec = resid[mask]
        score = Xc.T @ ec  # k x 1
        meat += np.outer(score, score)

    # Small sample correction
    correction = G / (G - 1) * (n - 1) / (n - k)
    V = XtX_inv @ meat @ XtX_inv * correction
    diag_V = np.diag(V)
    se = np.sqrt(np.maximum(diag_V, 0.0))
    return se


def re_gls(y, X_fe, syndicate_ids, event_ids=None):
    """
    Random-effects GLS with syndicate random intercepts and optional event fixed effects.
    Returns dict with beta, se, cluster_se, sigma2_u, sigma2_e, theta.
    """
    n = len(y)
    y = np.array(y, dtype=float)
    X_fe = np.array(X_fe, dtype=float)
    if X_fe.ndim == 1:
        X_fe = X_fe.reshape(-1, 1)

    # Build design matrix with event dummies if needed
    if event_ids is not None:
        unique_events = sorted(set(event_ids))
        if len(unique_events) > 1:
            event_dummies = np.zeros((n, len(unique_events) - 1))
            event_map = {e: i for i, e in enumerate(unique_events)}
            for j in range(n):
                idx = event_map[event_ids[j]]
                if idx > 0:
                    event_dummies[j, idx - 1] = 1.0
            X_full = np.column_stack([X_fe, event_dummies])
        else:
            X_full = X_fe.copy()
    else:
        X_full = X_fe.copy()

    # Add intercept
    X_full = np.column_stack([np.ones(n), X_full])
    k = X_full.shape[1]

    # Step 1: Preliminary OLS
    beta_ols, resid_ols = ols_fit(X_full, y)

    # Between-within decomposition for variance components
    unique_synd = sorted(set(syndicate_ids))
    synd_map = {s: i for i, s in enumerate(unique_synd)}
    n_synd = len(unique_synd)

    # Group means of residuals
    group_sum = defaultdict(float)
    group_count = defaultdict(int)
    for j in range(n):
        s = syndicate_ids[j]
        group_sum[s] += resid_ols[j]
        group_count[s] += 1

    # Within variance
    ssw = 0.0
    for j in range(n):
        s = syndicate_ids[j]
        group_mean = group_sum[s] / group_count[s]
        ssw += (resid_ols[j] - group_mean) ** 2

    df_within = max(n - n_synd - k + 1, 1)
    sigma2_e = ssw / df_within

    # Between variance
    ssb = 0.0
    grand_mean = np.mean(resid_ols)
    for s in unique_synd:
        gm = group_sum[s] / group_count[s]
        ssb += group_count[s] * (gm - grand_mean) ** 2

    n_bar = n / n_synd if n_synd > 0 else 1
    sigma2_u = max((ssb / max(n_synd - 1, 1) - sigma2_e) / n_bar, 0.0)

    # Step 2: Compute theta
    theta = {}
    for s in unique_synd:
        ni = group_count[s]
        if sigma2_e + ni * sigma2_u > 0:
            theta[s] = 1.0 - math.sqrt(sigma2_e / (sigma2_e + ni * sigma2_u))
        else:
            theta[s] = 0.0

    # Step 3: Quasi-demean
    y_tilde = np.zeros(n)
    X_tilde = np.zeros_like(X_full)
    for j in range(n):
        s = syndicate_ids[j]
        th = theta[s]
        ni = group_count[s]
        y_bar = group_sum[s] / ni  # Note: this is residual mean, need y/X means
        y_tilde[j] = y[j]
        X_tilde[j] = X_full[j]

    # Need proper quasi-demeaning with y and X group means
    y_group_sum = defaultdict(float)
    X_group_sum = defaultdict(lambda: np.zeros(k))
    for j in range(n):
        s = syndicate_ids[j]
        y_group_sum[s] += y[j]
        X_group_sum[s] += X_full[j]

    for j in range(n):
        s = syndicate_ids[j]
        th = theta[s]
        ni = group_count[s]
        y_tilde[j] = y[j] - th * (y_group_sum[s] / ni)
        X_tilde[j] = X_full[j] - th * (X_group_sum[s] / ni)

    # Step 4: OLS on quasi-demeaned
    beta_gls, resid_gls = ols_fit(X_tilde, y_tilde)

    # Step 5: Standard errors and cluster-robust SEs
    n_gls, k_gls = X_tilde.shape
    if n_gls > k_gls:
        sigma2_gls = np.sum(resid_gls ** 2) / (n_gls - k_gls)
        try:
            cov_gls = sigma2_gls * np.linalg.inv(X_tilde.T @ X_tilde)
            se_gls = np.sqrt(np.maximum(np.diag(cov_gls), 0.0))
        except np.linalg.LinAlgError:
            se_gls = np.full(k_gls, np.nan)
    else:
        se_gls = np.full(k_gls, np.nan)

    synd_arr = np.array([syndicate_ids[j] for j in range(n)])
    cluster_se_gls = cluster_robust_se(X_tilde, y_tilde, beta_gls, synd_arr)

    return {
        "beta": beta_gls,
        "se": se_gls,
        "cluster_se": cluster_se_gls,
        "sigma2_u": sigma2_u,
        "sigma2_e": sigma2_e,
        "theta": theta,
        "n": n,
        "k": k,
        "n_fe": X_fe.shape[1],
    }


# ─────────────────────────────────────────────────────────────────────────────
# N0: Sampling Robustness
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n0(records, subset_records):
    """N0 — Sampling Robustness on DENSE subset."""
    log("N0: Sampling Robustness")
    dense = [r for r in subset_records["DENSE"] if r["eligible_for_n3"]]
    if len(dense) < 10:
        log("  N0: Too few observations, skipping")
        return {"status": "insufficient_data", "n": len(dense)}

    rng = np.random.RandomState(42)
    syndicates = sorted(set(r["syndicate"] for r in dense))
    n_leave_out = max(1, int(len(syndicates) * 0.10))

    point_p95 = []
    point_beta = []
    point_var995 = []

    # Get arrays for point estimate
    y_all = np.array([r["s_raw_a"] for r in dense if r["s_raw_a"] is not None], dtype=float)
    if len(y_all) == 0:
        return {"status": "no_severity_data"}

    point_p95_val = float(np.percentile(y_all, 95))
    # Point beta from simple OLS: s = a + b*ln(R)
    y_reg = []
    x_reg = []
    for r in dense:
        if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0:
            y_reg.append(r["s_raw_a"])
            x_reg.append(math.log(r["opening_reserves_gbp_m"]))
    if len(y_reg) > 2:
        X_mat = np.column_stack([np.ones(len(x_reg)), x_reg])
        beta_point, _, _ = ols_with_se(X_mat, np.array(y_reg))
        point_beta_val = float(beta_point[1])
    else:
        point_beta_val = None

    point_var995_val = float(np.percentile(y_all, 99.5)) if len(y_all) >= 20 else None

    leave_out_p95 = []
    leave_out_beta = []
    leave_out_var995 = []

    for _iter in range(200):
        left_out = set(rng.choice(syndicates, size=n_leave_out, replace=False))
        subset = [r for r in dense if r["syndicate"] not in left_out]

        y_sub = [r["s_raw_a"] for r in subset if r["s_raw_a"] is not None]
        if len(y_sub) < 5:
            continue

        leave_out_p95.append(float(np.percentile(y_sub, 95)))

        y_r = []
        x_r = []
        for r in subset:
            if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0:
                y_r.append(r["s_raw_a"])
                x_r.append(math.log(r["opening_reserves_gbp_m"]))
        if len(y_r) > 2:
            X_m = np.column_stack([np.ones(len(x_r)), x_r])
            b, _, _ = ols_with_se(X_m, np.array(y_r))
            leave_out_beta.append(float(b[1]))

        if len(y_sub) >= 20:
            leave_out_var995.append(float(np.percentile(y_sub, 99.5)))

    # Bootstrap CV
    boot_p95 = []
    boot_beta = []
    boot_var995 = []
    for _b in range(500):
        idx = rng.choice(len(dense), size=len(dense), replace=True)
        boot = [dense[i] for i in idx]
        y_b = [r["s_raw_a"] for r in boot if r["s_raw_a"] is not None]
        if len(y_b) < 5:
            continue
        boot_p95.append(float(np.percentile(y_b, 95)))

        y_r = []
        x_r = []
        for r in boot:
            if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0:
                y_r.append(r["s_raw_a"])
                x_r.append(math.log(r["opening_reserves_gbp_m"]))
        if len(y_r) > 2:
            X_m = np.column_stack([np.ones(len(x_r)), x_r])
            b, _, _ = ols_with_se(X_m, np.array(y_r))
            boot_beta.append(float(b[1]))

        if len(y_b) >= 20:
            boot_var995.append(float(np.percentile(y_b, 99.5)))

    def stability_flag(lo_cv, bs_cv):
        if lo_cv is None or bs_cv is None:
            return "unknown"
        max_cv = max(lo_cv, bs_cv)
        if max_cv < 5:
            return "stable"
        elif max_cv < 15:
            return "moderate"
        else:
            return "unstable"

    lo_cv_p95 = cv_pct(leave_out_p95)
    bs_cv_p95 = cv_pct(boot_p95)
    lo_cv_beta = cv_pct(leave_out_beta)
    bs_cv_beta = cv_pct(boot_beta)
    lo_cv_var = cv_pct(leave_out_var995)
    bs_cv_var = cv_pct(boot_var995)

    return {
        "status": "completed",
        "n_observations": len(dense),
        "n_syndicates": len(syndicates),
        "leave_out_iterations": 200,
        "bootstrap_replicates": 500,
        "metrics": {
            "p95_slope": {
                "point_estimate": point_p95_val,
                "leave_out_cv_pct": lo_cv_p95,
                "bootstrap_cv_pct": bs_cv_p95,
                "stability": stability_flag(lo_cv_p95, bs_cv_p95),
            },
            "beta": {
                "point_estimate": point_beta_val,
                "leave_out_cv_pct": lo_cv_beta,
                "bootstrap_cv_pct": bs_cv_beta,
                "stability": stability_flag(lo_cv_beta, bs_cv_beta),
            },
            "var_995": {
                "point_estimate": point_var995_val,
                "leave_out_cv_pct": lo_cv_var,
                "bootstrap_cv_pct": bs_cv_var,
                "stability": stability_flag(lo_cv_var, bs_cv_var),
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# N1: Tail Trend
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n1(records, subset_records):
    """N1 — Tail Trend on DENSE subset (eligible_for_n1)."""
    log("N1: Tail Trend")
    eligible = [r for r in records if r.get("eligible_for_n1", False) and r["s_raw_a"] is not None]
    if len(eligible) < 10:
        return {"status": "insufficient_data"}

    # Market reference mix = equal-weighted average of DENSE weight vectors
    dense_weights = [np.array(r["weights"]) for r in subset_records["DENSE"]
                     if r["weight_source"] != "none"]
    if dense_weights:
        market_mix = np.mean(dense_weights, axis=0)
        # Normalise
        s = market_mix.sum()
        if s > 0:
            market_mix = market_mix / s
    else:
        market_mix = np.ones(N_LOBS) / N_LOBS

    # Reference size for standardisation = median reserves in DENSE
    dense_reserves = [r["opening_reserves_gbp_m"] for r in subset_records["DENSE"]
                      if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
    ref_size_std = float(np.median(dense_reserves)) if dense_reserves else REFERENCE_SIZE
    ref_hhi_std = float(np.median([r["hhi"] for r in subset_records["DENSE"]
                                    if r.get("hhi") is not None])) if subset_records["DENSE"] else 0.4

    # Reference mean: test whether market mean differs from zero
    mu_ref, mu_sig, mu_t, mu_p = compute_reference_mean(eligible)
    mu_sev = mu_ref / 100.0

    # Per-year 95th percentile of raw and standardised (mix + size + HHI, re-centred)
    years = sorted(set(r["year"] for r in eligible))
    p95_raw_by_year = {}
    p95_std_by_year = {}

    # First pass: compute all standardised values to get mean for re-centring
    all_std_vals = []
    all_raw_vals = []
    for r in eligible:
        if r["s_raw_a"] is not None:
            all_raw_vals.append(r["s_raw_a"])
        if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["opening_reserves_gbp_m"] > 0:
            r_obs = r["opening_reserves_gbp_m"]
            hhi_obs = r.get("hhi") or ref_hhi_std
            adj = dispersion_adjustment(ref_size_std, ref_hhi_std, r_obs, hhi_obs)
            all_std_vals.append(r["s_raw_a"] * adj)
        elif r["s_raw_a"] is not None:
            all_std_vals.append(r["s_raw_a"])

    std_shift = mu_sev - float(np.mean(all_std_vals)) if all_std_vals else 0.0

    for yr in years:
        yr_recs = [r for r in eligible if r["year"] == yr]
        raw_vals = [r["s_raw_a"] for r in yr_recs if r["s_raw_a"] is not None]
        std_vals = []
        for r in yr_recs:
            if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["opening_reserves_gbp_m"] > 0:
                r_obs = r["opening_reserves_gbp_m"]
                hhi_obs = r.get("hhi") or ref_hhi_std
                adj = dispersion_adjustment(ref_size_std, ref_hhi_std, r_obs, hhi_obs)
                std_vals.append(r["s_raw_a"] * adj + std_shift)
            elif r["s_raw_a"] is not None:
                std_vals.append(r["s_raw_a"])
        if raw_vals:
            p95_raw_by_year[yr] = float(np.percentile(raw_vals, 95))
        if std_vals:
            p95_std_by_year[yr] = float(np.percentile(std_vals, 95))

    # RE-GLS: s_it = α + β ln(R_it) + δ·t + u_i + γ_e + ε_it
    y_list = []
    x_lnr = []
    x_t = []
    synd_ids = []
    event_ids = []
    for r in eligible:
        if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0:
            y_list.append(r["s_raw_a"])
            x_lnr.append(math.log(r["opening_reserves_gbp_m"]))
            x_t.append(float(r["year"]))
            synd_ids.append(r["syndicate"])
            event_ids.append(r.get("event_group_id", f"{r['year']}_pooled"))

    if len(y_list) < 5:
        return {"status": "insufficient_data"}

    X_fe = np.column_stack([x_lnr, x_t])
    result = re_gls(np.array(y_list), X_fe, synd_ids, event_ids)

    # delta is the time trend coefficient (index 2 in beta: [intercept, ln_R, t, ...event dummies])
    delta = float(result["beta"][2]) if len(result["beta"]) > 2 else None
    delta_se = float(result["cluster_se"][2]) if len(result["cluster_se"]) > 2 else None

    # Bootstrap CI for delta
    rng = np.random.RandomState(42)
    unique_synd = sorted(set(synd_ids))
    boot_deltas = []
    for _b in range(500):
        boot_synds = rng.choice(unique_synd, size=len(unique_synd), replace=True)
        boot_y = []
        boot_x = []
        boot_t = []
        boot_s = []
        boot_e = []
        for bs in boot_synds:
            for j in range(len(y_list)):
                if synd_ids[j] == bs:
                    boot_y.append(y_list[j])
                    boot_x.append(x_lnr[j])
                    boot_t.append(x_t[j])
                    boot_s.append(bs)
                    boot_e.append(event_ids[j])
        if len(boot_y) < 5:
            continue
        try:
            X_b = np.column_stack([boot_x, boot_t])
            res_b = re_gls(np.array(boot_y), X_b, boot_s, boot_e)
            if len(res_b["beta"]) > 2:
                boot_deltas.append(float(res_b["beta"][2]))
        except Exception:
            continue

    boot_ci = None
    if boot_deltas:
        boot_ci = [float(np.percentile(boot_deltas, 2.5)), float(np.percentile(boot_deltas, 97.5))]

    return {
        "status": "completed",
        "n": len(y_list),
        "p95_raw_by_year": {str(k): v for k, v in p95_raw_by_year.items()},
        "p95_std_by_year": {str(k): v for k, v in p95_std_by_year.items()},
        "delta": delta,
        "delta_cluster_se": delta_se,
        "delta_bootstrap_ci_95": boot_ci,
        "beta_ln_R": float(result["beta"][1]) if len(result["beta"]) > 1 else None,
        "standardisation_reference_size_m": ref_size_std,
        "standardisation_mix": "equal-weighted DENSE average",
    }


# ─────────────────────────────────────────────────────────────────────────────
# N2: Mean Excess Function
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n2(records, subset_records):
    """N2 — Mean Excess Function."""
    log("N2: Mean Excess Function")
    eligible = [r for r in records if r.get("eligible_for_distribution", False)]
    raw_pos = [r["s_raw_a"] for r in eligible if r["s_raw_a"] is not None and r["s_raw_a"] > 0]

    # Market mix for standardisation
    dense_weights = [np.array(r["weights"]) for r in subset_records["DENSE"]
                     if r["weight_source"] != "none"]
    if dense_weights:
        market_mix = np.mean(dense_weights, axis=0)
        s = market_mix.sum()
        if s > 0:
            market_mix /= s
    else:
        market_mix = np.ones(N_LOBS) / N_LOBS

    # Reference size for standardisation = median reserves in DENSE
    dense_reserves = [r["opening_reserves_gbp_m"] for r in subset_records["DENSE"]
                      if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
    ref_size_std = float(np.median(dense_reserves)) if dense_reserves else REFERENCE_SIZE
    ref_hhi_std = float(np.median([r["hhi"] for r in subset_records["DENSE"]
                                    if r.get("hhi") is not None])) if subset_records["DENSE"] else 0.4

    # Reference mean for re-centring
    mu_ref, _, _, _ = compute_reference_mean(eligible)
    mu_sev = mu_ref / 100.0

    # Compute all standardised values first for re-centring
    all_std = []
    for r in eligible:
        if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["opening_reserves_gbp_m"] > 0:
            r_obs = r["opening_reserves_gbp_m"]
            hhi_obs = r.get("hhi") or ref_hhi_std
            adj = dispersion_adjustment(ref_size_std, ref_hhi_std, r_obs, hhi_obs)
            all_std.append(r["s_raw_a"] * adj)
        elif r["s_raw_a"] is not None:
            all_std.append(r["s_raw_a"])

    std_shift = mu_sev - float(np.mean(all_std)) if all_std else 0.0

    std_pos = []
    for r in eligible:
        if r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["opening_reserves_gbp_m"] > 0:
            r_obs = r["opening_reserves_gbp_m"]
            hhi_obs = r.get("hhi") or ref_hhi_std
            adj = dispersion_adjustment(ref_size_std, ref_hhi_std, r_obs, hhi_obs)
            v = r["s_raw_a"] * adj + std_shift
            if v > 0:
                std_pos.append(v)
        elif r["s_raw_a"] is not None and r["s_raw_a"] > 0:
            std_pos.append(r["s_raw_a"])

    def mean_excess_data(values, min_exc=5):
        if len(values) < min_exc:
            return []
        arr = np.sort(np.array(values))
        result = []
        for q in range(5, 86):
            threshold = float(np.percentile(arr, q))
            exceedances = arr[arr > threshold]
            if len(exceedances) >= min_exc:
                me = float(np.mean(exceedances - threshold))
                result.append({
                    "percentile": q,
                    "threshold": threshold,
                    "mean_excess": me,
                    "n_exceedances": int(len(exceedances)),
                })
        return result

    return {
        "status": "completed",
        "raw": {
            "n_positive": len(raw_pos),
            "mean_excess_function": mean_excess_data(raw_pos),
        },
        "mix_standardised": {
            "n_positive": len(std_pos),
            "mean_excess_function": mean_excess_data(std_pos),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# N3: Size-Severity Elasticity
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n3(records, subset_records):
    """N3 — Size-Severity Elasticity."""
    log("N3: Size-Severity Elasticity")
    eligible = [r for r in records if r.get("eligible_for_n3", False) and r["s_raw_a"] is not None]
    if len(eligible) < 10:
        return {"status": "insufficient_data", "n": len(eligible)}

    y = np.array([r["s_raw_a"] for r in eligible], dtype=float)
    ln_R = np.array([math.log(r["opening_reserves_gbp_m"]) for r in eligible], dtype=float)
    synd_ids = [r["syndicate"] for r in eligible]
    event_ids = [r.get("event_group_id", f"{r['year']}_pooled") for r in eligible]
    n = len(y)

    # Primary: RE-GLS
    X_fe = ln_R.reshape(-1, 1)
    primary = re_gls(y, X_fe, synd_ids, event_ids)
    primary_beta = float(primary["beta"][1]) if len(primary["beta"]) > 1 else None
    primary_se = float(primary["cluster_se"][1]) if len(primary["cluster_se"]) > 1 else None

    # M0: Baseline OLS
    X_m0 = np.column_stack([np.ones(n), ln_R])
    beta_m0, se_m0, resid_m0 = ols_with_se(X_m0, y)

    # M1: OLS + event FE
    unique_events = sorted(set(event_ids))
    event_map = {e: i for i, e in enumerate(unique_events)}
    if len(unique_events) > 1:
        event_dummies = np.zeros((n, len(unique_events) - 1))
        for j in range(n):
            idx = event_map[event_ids[j]]
            if idx > 0:
                event_dummies[j, idx - 1] = 1.0
        X_m1 = np.column_stack([np.ones(n), ln_R, event_dummies])
    else:
        X_m1 = np.column_stack([np.ones(n), ln_R])
    beta_m1, se_m1, resid_m1 = ols_with_se(X_m1, y)

    # M2: Log-scale ln(|S|) with event FE (|S| > 0 only)
    nz_mask = np.abs(y) > 0
    if nz_mask.sum() > 5:
        ln_abs_y = np.log(np.abs(y[nz_mask]))
        ln_R_m2 = ln_R[nz_mask]
        synd_m2 = synd_ids[nz_mask] if isinstance(synd_ids, np.ndarray) else np.array(synd_ids)[nz_mask]
        ev_m2 = [event_ids[j] for j in range(n) if nz_mask[j]]
        unique_ev_m2 = sorted(set(ev_m2))
        ev_map_m2 = {e: i for i, e in enumerate(unique_ev_m2)}
        n_m2 = int(nz_mask.sum())
        if len(unique_ev_m2) > 1:
            ev_dum_m2 = np.zeros((n_m2, len(unique_ev_m2) - 1))
            for j in range(n_m2):
                idx = ev_map_m2[ev_m2[j]]
                if idx > 0:
                    ev_dum_m2[j, idx - 1] = 1.0
            X_m2 = np.column_stack([np.ones(n_m2), ln_R_m2, ev_dum_m2])
        else:
            X_m2 = np.column_stack([np.ones(n_m2), ln_R_m2])
        beta_m2, se_m2_ols, resid_m2_raw = ols_with_se(X_m2, ln_abs_y)
        se_m2 = cluster_robust_se(X_m2, ln_abs_y, beta_m2, synd_m2)
    else:
        beta_m2 = np.array([np.nan, np.nan])
        se_m2 = np.array([np.nan, np.nan])

    # M3: Variance-scale ln(S²) with event FE (|S| > 0 only)
    if nz_mask.sum() > 5:
        ln_sq_y = 2.0 * np.log(np.abs(y[nz_mask]))  # ln(S²) = 2*ln(|S|)
        if len(unique_ev_m2) > 1:
            X_m3 = np.column_stack([np.ones(n_m2), ln_R_m2, ev_dum_m2])
        else:
            X_m3 = np.column_stack([np.ones(n_m2), ln_R_m2])
        beta_m3, se_m3_ols, resid_m3_raw = ols_with_se(X_m3, ln_sq_y)
        se_m3 = cluster_robust_se(X_m3, ln_sq_y, beta_m3, synd_m2)
    else:
        beta_m3 = np.array([np.nan, np.nan])
        se_m3 = np.array([np.nan, np.nan])

    # M1-balanced (BALANCED_K8)
    balanced_k8 = set(id(r) for r in subset_records["BALANCED_K8"])
    elig_balanced = [r for r in eligible if id(r) in balanced_k8]
    if len(elig_balanced) > 5:
        y_b = np.array([r["s_raw_a"] for r in elig_balanced], dtype=float)
        ln_R_b = np.array([math.log(r["opening_reserves_gbp_m"]) for r in elig_balanced], dtype=float)
        X_b = np.column_stack([np.ones(len(y_b)), ln_R_b])
        beta_mb, se_mb, _ = ols_with_se(X_b, y_b)
    else:
        beta_mb = np.array([np.nan, np.nan])
        se_mb = np.array([np.nan, np.nan])

    # Non-parametric quantile curves (Epanechnikov kernel-weighted local quantile regression)
    quantile_bins = local_quantile_regression(ln_R, y, taus=(0.10, 0.90), n_grid=30)

    # Compute AIC, BIC, significance for each frequentist model
    def _model_info_criteria(resid_vec, n_obs, k_params):
        rss = float(np.sum(resid_vec ** 2))
        if rss <= 0 or n_obs <= 0:
            return None, None, rss
        aic = n_obs * math.log(rss / n_obs) + 2 * k_params
        bic = n_obs * math.log(rss / n_obs) + k_params * math.log(n_obs)
        return float(aic), float(bic), rss

    def _sig_marker(p):
        if p is None:
            return ""
        if p < 0.001:
            return "***"
        if p < 0.01:
            return "**"
        if p < 0.05:
            return "*"
        if p < 0.10:
            return "\u2020"
        return ""

    def _p_from_beta_se(b, s):
        if b is None or s is None or s <= 0:
            return None
        z = abs(b / s)
        return 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))

    aic_m0, bic_m0, rss_m0 = _model_info_criteria(resid_m0, n, X_m0.shape[1])
    aic_m1, bic_m1, rss_m1 = _model_info_criteria(resid_m1, n, X_m1.shape[1])
    # M2 uses log-absolute-severity subset (|S| > 0)
    if nz_mask.sum() > 5:
        resid_m2 = ln_abs_y - X_m2 @ beta_m2
        aic_m2, bic_m2, rss_m2 = _model_info_criteria(resid_m2, n_m2, X_m2.shape[1])
    else:
        aic_m2, bic_m2 = None, None
    # M3 uses log-squared-severity subset (same observations as M2)
    if nz_mask.sum() > 5:
        resid_m3 = ln_sq_y - X_m3 @ beta_m3
        aic_m3, bic_m3, rss_m3 = _model_info_criteria(resid_m3, n_m2, X_m3.shape[1])
    else:
        aic_m3, bic_m3 = None, None
    if len(elig_balanced) > 5:
        resid_mb = y_b - X_b @ beta_mb
        aic_mb, bic_mb, rss_mb = _model_info_criteria(resid_mb, len(y_b), X_b.shape[1])
    else:
        aic_mb, bic_mb = None, None

    p_m0 = _p_from_beta_se(float(beta_m0[1]), float(se_m0[1]))
    p_m1 = _p_from_beta_se(float(beta_m1[1]), float(se_m1[1]))
    p_m2 = _p_from_beta_se(float(beta_m2[1]), float(se_m2[1]))
    p_m3 = _p_from_beta_se(float(beta_m3[1]), float(se_m3[1]))
    p_mb = _p_from_beta_se(float(beta_mb[1]), float(se_mb[1]))

    return {
        "status": "completed",
        "n": n,
        "primary_re_gls": {
            "beta": primary_beta,
            "cluster_se": primary_se,
            "sigma2_u": primary["sigma2_u"],
            "sigma2_e": primary["sigma2_e"],
        },
        "frequentist_comparisons": {
            "M0_baseline_ols": {"beta": float(beta_m0[1]), "se": float(se_m0[1]), "p_value": p_m0, "significant": p_m0 is not None and p_m0 < 0.05, "sig_marker": _sig_marker(p_m0), "aic": aic_m0, "bic": bic_m0},
            "M1_ols_event_fe": {"beta": float(beta_m1[1]), "se": float(se_m1[1]), "p_value": p_m1, "significant": p_m1 is not None and p_m1 < 0.05, "sig_marker": _sig_marker(p_m1), "aic": aic_m1, "bic": bic_m1},
            "M2_log_scale": {"beta": float(beta_m2[1]), "se": float(se_m2[1]), "p_value": p_m2, "significant": p_m2 is not None and p_m2 < 0.05, "sig_marker": _sig_marker(p_m2), "aic": aic_m2, "bic": bic_m2},
            "M3_variance_scale": {"beta": float(beta_m3[1]), "se": float(se_m3[1]), "p_value": p_m3, "significant": p_m3 is not None and p_m3 < 0.05, "sig_marker": _sig_marker(p_m3), "aic": aic_m3, "bic": bic_m3},
            "M1_balanced_k8": {"beta": float(beta_mb[1]), "se": float(se_mb[1]), "n": len(elig_balanced), "p_value": p_mb, "significant": p_mb is not None and p_mb < 0.05, "sig_marker": _sig_marker(p_mb), "aic": aic_mb, "bic": bic_mb},
        },
        "quantile_bins": quantile_bins,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Power-law dispersion model:  Y = A + B * x^C
# ─────────────────────────────────────────────────────────────────────────────

def fit_power_dispersion(x, y_sq, label="", n_grid_c=200, c_range=(-0.99, -0.01),
                         winsorise_pct=95, n_bins_diagnostic=20):
    """Fit  Y = A + B * x^C  where Y = s^2, x > 0.

    c_range controls the search: (-0.99, -0.01) for decreasing (size model),
    (0.01, 2.0) for increasing (concentration model).

    Winsorises y_sq at winsorise_pct to reduce outlier influence.
    Also fits on binned means as a robustness check.

    Returns dict with {A, B, C, rss, r_squared, n, fitted_curve, label,
                       binned_fit, winsorise_cap}.
    """
    mask = x > 0
    x_f = x[mask]
    y_raw = y_sq[mask]
    n = len(x_f)

    # Winsorise: cap y_sq at the winsorise_pct percentile
    cap = float(np.percentile(y_raw, winsorise_pct))
    y_f = np.minimum(y_raw, cap)
    if n < 10:
        return {"status": "insufficient", "label": label, "n": n}

    c_grid = np.linspace(c_range[0], c_range[1], n_grid_c)
    best_rss = np.inf
    best_c = float(np.mean(c_range))
    best_ab = (0.0, 0.0)
    rss_profile = {}  # c → rss for profile CI

    for c in c_grid:
        xc = x_f ** c
        X = np.column_stack([np.ones(n), xc])
        beta, resid = ols_fit(X, y_f)
        if beta[1] <= 0 or beta[0] < -1e-6:
            continue
        rss = float(np.sum(resid ** 2))
        rss_profile[float(c)] = rss
        if rss < best_rss:
            best_rss = rss
            best_c = float(c)
            best_ab = (max(0.0, float(beta[0])), float(beta[1]))

    if np.isinf(best_rss):
        return {"status": "no_valid_fit", "label": label, "n": n}

    A, B = best_ab
    C = best_c

    # Compute R² and standard errors
    ss_tot = float(np.sum((y_f - np.mean(y_f)) ** 2))
    r_sq = 1.0 - best_rss / ss_tot if ss_tot > 0 else 0.0

    # SEs and p-values for A and B (conditional on C)
    xc_opt = x_f ** C
    X_opt = np.column_stack([np.ones(n), xc_opt])
    _, se_opt, resid_opt = ols_with_se(X_opt, y_f)
    se_A = float(se_opt[0]) if not np.isnan(se_opt[0]) else None
    se_B = float(se_opt[1]) if not np.isnan(se_opt[1]) else None

    def _p_from_t(b, se, df):
        if se is None or se <= 0 or df <= 0:
            return None
        t = abs(b / se)
        # Two-sided p-value from t-distribution approximated via normal for large df
        return 2 * (1 - 0.5 * (1 + math.erf(t / math.sqrt(2))))

    df = n - 3  # A, B, C
    p_A = _p_from_t(A, se_A, df)
    p_B = _p_from_t(B, se_B, df)

    # Profile likelihood CI for C (95%):
    # Threshold: RSS(C) ≤ RSS_min + sigma² × chi²(1, 0.95)
    # where sigma² = RSS_min / (n - 3) and chi²(1, 0.95) = 3.84
    c_ci_lo, c_ci_hi = None, None
    c_ci_note = None
    p_C = None
    if rss_profile:
        sigma2_hat = best_rss / max(n - 3, 1)
        threshold = best_rss + sigma2_hat * 3.84
        valid_cs = sorted([c for c, r in rss_profile.items() if r <= threshold])
        if valid_cs:
            c_ci_lo = valid_cs[0]
            c_ci_hi = valid_cs[-1]
            # Check if CI is truncated by constraint violations
            # (no valid fits exist beyond the CI bounds)
            all_valid_cs = sorted(rss_profile.keys())
            if c_ci_hi == all_valid_cs[-1] and c_ci_hi <= C + 0.005:
                # Upper bound is at or near the constraint boundary
                c_ci_note = "upper bound constrained (A\u22650 binding)"
            if c_ci_lo == all_valid_cs[0] and c_ci_lo >= C - 0.005:
                c_ci_note = "lower bound constrained"

        # Likelihood ratio test vs null (no x effect = mean-only model)
        rss_null = float(np.sum((y_f - np.mean(y_f)) ** 2))
        if best_rss > 0 and rss_null > best_rss:
            lr_stat = n * math.log(rss_null / best_rss)
            p_C = 2 * (1 - 0.5 * (1 + math.erf(math.sqrt(lr_stat) / math.sqrt(2))))

    # Fitted curve for plotting (50 points across x range)
    x_curve = np.linspace(float(x_f.min()), float(x_f.max()), 50)
    y_curve = A + B * x_curve ** C
    fitted_curve = [{"x": float(xv), "y": float(yv)} for xv, yv in zip(x_curve, y_curve)]

    # ── Primary estimator: binned means ────────────────────────
    # Fit on decile-averaged s² — robust to heavy tails, consistent with Bartlett
    binned_A, binned_B, binned_C = A, B, C  # fallback to observation-level
    binned_r_sq = r_sq
    bin_points = []
    if n >= 30:
        bin_edges = np.percentile(x_f, np.linspace(0, 100, n_bins_diagnostic + 1))
        bin_edges[-1] += 0.01
        bin_x, bin_y, bin_n = [], [], []
        for b in range(n_bins_diagnostic):
            bmask = (x_f >= bin_edges[b]) & (x_f < bin_edges[b + 1])
            if bmask.sum() >= 3:
                bin_x.append(float(np.mean(x_f[bmask])))
                bin_y.append(float(np.mean(y_f[bmask])))
                bin_n.append(int(bmask.sum()))
        if len(bin_x) >= 4:
            bx = np.array(bin_x)
            by = np.array(bin_y)
            best_brss = np.inf
            best_bc = float(np.mean(c_range))
            best_bab = (0.0, 0.0)
            brss_profile = {}
            for c in np.linspace(c_range[0], c_range[1], n_grid_c):
                Xb = np.column_stack([np.ones(len(bx)), bx ** c])
                bb, bresid = ols_fit(Xb, by)
                if bb[1] <= 0 or bb[0] < -1e-6:
                    continue
                brss = float(np.sum(bresid ** 2))
                brss_profile[float(c)] = brss
                if brss < best_brss:
                    best_brss = brss
                    best_bc = float(c)
                    best_bab = (max(0.0, float(bb[0])), float(bb[1]))
            if not np.isinf(best_brss):
                ss_tot_b = float(np.sum((by - np.mean(by)) ** 2))
                binned_A, binned_B, binned_C = best_bab[0], best_bab[1], best_bc
                binned_r_sq = 1.0 - best_brss / ss_tot_b if ss_tot_b > 0 else 0.0
                bin_points = [{"x": bx[i], "y": by[i], "n": bin_n[i]} for i in range(len(bx))]

                # Update profile CI from binned fit
                sigma2_b = best_brss / max(len(bx) - 3, 1)
                threshold_b = best_brss + sigma2_b * 3.84
                valid_bcs = sorted([c for c, r in brss_profile.items() if r <= threshold_b])
                if valid_bcs:
                    c_ci_lo = valid_bcs[0]
                    c_ci_hi = valid_bcs[-1]
                    c_ci_note = None
                    all_valid_bcs = sorted(brss_profile.keys())
                    if c_ci_hi == all_valid_bcs[-1] and c_ci_hi <= best_bc + 0.01:
                        c_ci_note = "upper bound constrained (A\u22650 binding)"
                    if c_ci_lo == all_valid_bcs[0] and c_ci_lo >= best_bc - 0.01:
                        c_ci_note = "lower bound at grid edge"

                # SEs for binned A, B
                Xb_opt = np.column_stack([np.ones(len(bx)), bx ** best_bc])
                _, se_b_opt, _ = ols_with_se(Xb_opt, by)
                se_A = float(se_b_opt[0]) if not np.isnan(se_b_opt[0]) else None
                se_B = float(se_b_opt[1]) if not np.isnan(se_b_opt[1]) else None
                p_A = _p_from_t(binned_A, se_A, max(len(bx) - 3, 1))
                p_B = _p_from_t(binned_B, se_B, max(len(bx) - 3, 1))

                # Re-derive p_C from binned LR test
                rss_null_b = float(np.sum((by - np.mean(by)) ** 2))
                if best_brss > 0 and rss_null_b > best_brss:
                    lr_b = len(bx) * math.log(rss_null_b / best_brss)
                    p_C = 2 * (1 - 0.5 * (1 + math.erf(math.sqrt(lr_b) / math.sqrt(2))))

    # Use binned parameters as primary
    A, B, C = binned_A, binned_B, binned_C
    r_sq_primary = binned_r_sq

    # Recompute fitted curve from primary (binned) parameters
    x_curve = np.linspace(float(x_f.min()), float(x_f.max()), 50)
    y_curve = A + B * x_curve ** C
    fitted_curve = [{"x": float(xv), "y": float(yv)} for xv, yv in zip(x_curve, y_curve)]

    return {
        "status": "fitted",
        "label": label,
        "n": n,
        "A": A, "se_A": se_A, "p_A": p_A,
        "B": B, "se_B": se_B, "p_B": p_B,
        "C": C, "c_ci_95": [c_ci_lo, c_ci_hi], "c_ci_note": c_ci_note, "p_C": p_C,
        "rss": best_rss,
        "r_squared": r_sq_primary,
        "r_squared_obs": r_sq,
        "winsorise_cap": cap,
        "n_bins": len(bin_points),
        "bin_points": bin_points,
        "fitted_curve": fitted_curve,
        "interpretation": {
            "undiversifiable_floor": A,
            "diversifiable_scale": B,
            "power": C,
            "half_life": float(0.5 ** (1.0 / C)) if C != 0 else None,
        },
    }


def fit_joint_power_dispersion(HHI, R, y_sq, n_grid=80):
    """Fit  Y = A + B1 * HHI^C1 + B2 * R^C2  via profile over (C1, C2).

    C1 > 0 (concentration increases variance), C2 < 0 (size decreases variance).
    For each (C1, C2) pair, the model is linear in (A, B1, B2).
    """
    mask = (HHI > 0) & (R > 0)
    H_f, R_f, y_f = HHI[mask], R[mask], y_sq[mask]
    n = len(y_f)
    if n < 20:
        return {"status": "insufficient", "n": n}

    c1_grid = np.linspace(0.01, 2.0, n_grid)   # HHI: C1 > 0
    c2_grid = np.linspace(-0.99, -0.01, n_grid)  # R: C2 < 0
    best_rss = np.inf
    best_c1, best_c2 = 0.5, -0.5
    best_params = (0.0, 0.0, 0.0)
    # Collect marginal RSS profiles for C1 and C2
    rss_by_c1 = {}  # c1 → best RSS over all c2
    rss_by_c2 = {}  # c2 → best RSS over all c1

    for c1 in c1_grid:
        hc = H_f ** c1
        for c2 in c2_grid:
            rc = R_f ** c2
            X = np.column_stack([np.ones(n), hc, rc])
            beta, resid = ols_fit(X, y_f)
            if beta[1] <= 0 or beta[2] <= 0 or beta[0] < -1e-6:
                continue
            rss = float(np.sum(resid ** 2))
            # Track marginal profiles
            c1_key = float(c1)
            c2_key = float(c2)
            if c1_key not in rss_by_c1 or rss < rss_by_c1[c1_key]:
                rss_by_c1[c1_key] = rss
            if c2_key not in rss_by_c2 or rss < rss_by_c2[c2_key]:
                rss_by_c2[c2_key] = rss
            if rss < best_rss:
                best_rss = rss
                best_c1, best_c2 = c1_key, c2_key
                best_params = (max(0.0, float(beta[0])), float(beta[1]), float(beta[2]))

    if np.isinf(best_rss):
        return {"status": "no_valid_fit", "n": n}

    A, B1, B2 = best_params
    ss_tot = float(np.sum((y_f - np.mean(y_f)) ** 2))
    r_sq = 1.0 - best_rss / ss_tot if ss_tot > 0 else 0.0

    # SEs and p-values for A, B1, B2 at optimal (C1, C2)
    X_opt = np.column_stack([np.ones(n), H_f ** best_c1, R_f ** best_c2])
    _, se_opt, _ = ols_with_se(X_opt, y_f)
    se_A = float(se_opt[0]) if not np.isnan(se_opt[0]) else None
    se_B1 = float(se_opt[1]) if not np.isnan(se_opt[1]) else None
    se_B2 = float(se_opt[2]) if not np.isnan(se_opt[2]) else None

    def _p_t(b, se):
        if se is None or se <= 0: return None
        t = abs(b / se)
        return 2 * (1 - 0.5 * (1 + math.erf(t / math.sqrt(2))))

    p_A = _p_t(A, se_A)
    p_B1 = _p_t(B1, se_B1)
    p_B2 = _p_t(B2, se_B2)

    # Profile CIs for C1 and C2
    sigma2_hat = best_rss / max(n - 5, 1)  # 5 params: A, B1, B2, C1, C2
    threshold = best_rss + sigma2_hat * 3.84

    def _profile_ci(rss_profile, best_c):
        valid = sorted([c for c, r in rss_profile.items() if r <= threshold])
        ci_lo, ci_hi, note = None, None, None
        if valid:
            ci_lo, ci_hi = valid[0], valid[-1]
            all_valid = sorted(rss_profile.keys())
            if ci_hi == all_valid[-1] and ci_hi <= best_c + 0.01:
                note = "upper bound constrained"
            if ci_lo == all_valid[0] and ci_lo >= best_c - 0.01:
                note = "lower bound constrained"
        return ci_lo, ci_hi, note

    c1_ci_lo, c1_ci_hi, c1_note = _profile_ci(rss_by_c1, best_c1)
    c2_ci_lo, c2_ci_hi, c2_note = _profile_ci(rss_by_c2, best_c2)

    # LR test for overall model vs null (mean-only)
    rss_null = float(np.sum((y_f - np.mean(y_f)) ** 2))
    p_model = None
    if best_rss > 0 and rss_null > best_rss:
        lr = n * math.log(rss_null / best_rss)
        p_model = 2 * (1 - 0.5 * (1 + math.erf(math.sqrt(lr) / math.sqrt(2))))

    return {
        "status": "fitted",
        "n": n,
        "A": A, "se_A": se_A, "p_A": p_A,
        "B1": B1, "se_B1": se_B1, "p_B1": p_B1,
        "B2": B2, "se_B2": se_B2, "p_B2": p_B2,
        "C1": best_c1, "c1_ci_95": [c1_ci_lo, c1_ci_hi], "c1_ci_note": c1_note,
        "C2": best_c2, "c2_ci_95": [c2_ci_lo, c2_ci_hi], "c2_ci_note": c2_note,
        "p_model": p_model,
        "rss": best_rss,
        "r_squared": r_sq,
    }


def fit_joint_power_no_intercept(HHI, R, y_sq, n_grid=80):
    """Fit  Y = B1 * HHI^C1 + B2 * R^C2  (no intercept — no undiversifiable floor).

    Same profile approach but with 2 linear params (B1, B2) instead of 3.
    """
    mask = (HHI > 0) & (R > 0)
    H_f, R_f, y_f = HHI[mask], R[mask], y_sq[mask]
    n = len(y_f)
    if n < 20:
        return {"status": "insufficient", "n": n}

    c1_grid = np.linspace(0.01, 2.0, n_grid)
    c2_grid = np.linspace(-0.99, -0.01, n_grid)
    best_rss = np.inf
    best_c1, best_c2 = 0.5, -0.5
    best_params = (0.0, 0.0)
    rss_by_c1, rss_by_c2 = {}, {}

    for c1 in c1_grid:
        hc = H_f ** c1
        for c2 in c2_grid:
            rc = R_f ** c2
            # No intercept: X has only two columns
            X = np.column_stack([hc, rc])
            beta, resid = ols_fit(X, y_f)
            if beta[0] <= 0 or beta[1] <= 0:
                continue
            rss = float(np.sum(resid ** 2))
            c1k, c2k = float(c1), float(c2)
            if c1k not in rss_by_c1 or rss < rss_by_c1[c1k]:
                rss_by_c1[c1k] = rss
            if c2k not in rss_by_c2 or rss < rss_by_c2[c2k]:
                rss_by_c2[c2k] = rss
            if rss < best_rss:
                best_rss = rss
                best_c1, best_c2 = c1k, c2k
                best_params = (float(beta[0]), float(beta[1]))

    if np.isinf(best_rss):
        return {"status": "no_valid_fit", "n": n}

    B1, B2 = best_params
    ss_tot = float(np.sum((y_f - np.mean(y_f)) ** 2))
    r_sq = 1.0 - best_rss / ss_tot if ss_tot > 0 else 0.0

    # SEs and p-values
    X_opt = np.column_stack([H_f ** best_c1, R_f ** best_c2])
    _, se_opt, _ = ols_with_se(X_opt, y_f)
    se_B1 = float(se_opt[0]) if not np.isnan(se_opt[0]) else None
    se_B2 = float(se_opt[1]) if not np.isnan(se_opt[1]) else None

    def _p_t(b, se):
        if se is None or se <= 0: return None
        t = abs(b / se)
        return 2 * (1 - 0.5 * (1 + math.erf(t / math.sqrt(2))))

    p_B1 = _p_t(B1, se_B1)
    p_B2 = _p_t(B2, se_B2)

    # Profile CIs
    sigma2_hat = best_rss / max(n - 4, 1)  # 4 params: B1, B2, C1, C2
    threshold = best_rss + sigma2_hat * 3.84

    def _profile_ci(rss_profile, best_c):
        valid = sorted([c for c, r in rss_profile.items() if r <= threshold])
        ci_lo, ci_hi, note = None, None, None
        if valid:
            ci_lo, ci_hi = valid[0], valid[-1]
            all_valid = sorted(rss_profile.keys())
            if ci_hi == all_valid[-1] and ci_hi <= best_c + 0.01:
                note = "upper bound constrained"
            if ci_lo == all_valid[0] and ci_lo >= best_c - 0.01:
                note = "lower bound constrained"
        return ci_lo, ci_hi, note

    c1_ci_lo, c1_ci_hi, c1_note = _profile_ci(rss_by_c1, best_c1)
    c2_ci_lo, c2_ci_hi, c2_note = _profile_ci(rss_by_c2, best_c2)

    # LR test vs null
    rss_null = float(np.sum((y_f - np.mean(y_f)) ** 2))
    p_model = None
    if best_rss > 0 and rss_null > best_rss:
        lr = n * math.log(rss_null / best_rss)
        p_model = 2 * (1 - 0.5 * (1 + math.erf(math.sqrt(lr) / math.sqrt(2))))

    return {
        "status": "fitted",
        "n": n,
        "B1": B1, "se_B1": se_B1, "p_B1": p_B1,
        "B2": B2, "se_B2": se_B2, "p_B2": p_B2,
        "C1": best_c1, "c1_ci_95": [c1_ci_lo, c1_ci_hi], "c1_ci_note": c1_note,
        "C2": best_c2, "c2_ci_95": [c2_ci_lo, c2_ci_hi], "c2_ci_note": c2_note,
        "p_model": p_model,
        "rss": best_rss,
        "r_squared": r_sq,
    }


# ─────────────────────────────────────────────────────────────────────────────
# N6: Joint Composition — Sequential size→HHI adjustment pipeline
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n6(records, disp_r_result):
    """N6 — Joint composition: fit HHI dispersion on size-adjusted residuals.

    Pipeline:
      1. Use the size power-law model (s² = A_R + B_R·R^C_R) to compute
         expected variance for each observation's reserve size.
      2. Scale each observation to a reference size:
         s²_adj = s² × V(R_ref) / V(R_i)
      3. Fit the mix power-law: s²_adj = A_H + B_H·H^C_H
         This isolates the incremental HHI effect after size is removed.
    """
    log("N6: Joint Composition (size-adjusted HHI dispersion)")

    if not disp_r_result or disp_r_result.get("status") != "fitted":
        return {"status": "no_size_model"}

    A_R = disp_r_result["A"]
    B_R = disp_r_result["B"]
    C_R = disp_r_result["C"]

    # Exclude HHI≥0.99 (single-LoB reporters — structural break, not true concentration)
    eligible = [r for r in records
                if r.get("eligible_for_n3", False)
                and r["s_raw_a"] is not None
                and r.get("hhi") is not None
                and r.get("hhi", 1.0) < 0.99
                and r.get("weight_source") != "none"
                and r.get("opening_reserves_gbp_m") is not None
                and r["opening_reserves_gbp_m"] > 0]
    if len(eligible) < 20:
        return {"status": "insufficient_data", "n": len(eligible)}

    y = np.array([r["s_raw_a"] for r in eligible], dtype=float)
    R = np.array([r["opening_reserves_gbp_m"] for r in eligible], dtype=float)
    HHI = np.array([max(r["hhi"], 0.01) for r in eligible], dtype=float)
    div = 1.0 - HHI  # (1-HHI) for display
    y_sq = y ** 2

    # ── HHI vs R correlation ─────────────────────────────────────
    # Pearson (linear) correlation
    pearson_r = float(np.corrcoef(div, R)[0, 1])
    n_corr = len(eligible)
    # t-test for pearson
    if abs(pearson_r) < 1.0 and n_corr > 2:
        t_pearson = pearson_r * math.sqrt((n_corr - 2) / (1 - pearson_r ** 2))
        p_pearson = 2 * (1 - 0.5 * (1 + math.erf(abs(t_pearson) / math.sqrt(2))))
    else:
        t_pearson, p_pearson = None, None

    # Spearman (rank) correlation
    rank_div = np.argsort(np.argsort(div)).astype(float)
    rank_R = np.argsort(np.argsort(R)).astype(float)
    spearman_r = float(np.corrcoef(rank_div, rank_R)[0, 1])
    if abs(spearman_r) < 1.0 and n_corr > 2:
        t_spearman = spearman_r * math.sqrt((n_corr - 2) / (1 - spearman_r ** 2))
        p_spearman = 2 * (1 - 0.5 * (1 + math.erf(abs(t_spearman) / math.sqrt(2))))
    else:
        t_spearman, p_spearman = None, None

    hhi_r_correlation = {
        "pearson_r": pearson_r, "p_pearson": p_pearson,
        "spearman_r": spearman_r, "p_spearman": p_spearman,
        "n": n_corr,
        "scatter_points": [{"x": float(div[i]), "y": float(R[i]),
                            "syndicate": eligible[i]["syndicate"], "year": eligible[i]["year"]}
                           for i in range(len(eligible))],
    }

    # ── Univariate model comparison ────────────────────────────
    # Fit size-only and HHI-only models on raw s² to see which explains more
    log("  Fitting univariate size model on raw s²")
    univar_size = fit_power_dispersion(R, y_sq, label="Univariate size (R)", c_range=(-0.99, -0.01))
    log("  Fitting univariate HHI model on raw s²")
    univar_hhi = fit_power_dispersion(HHI, y_sq, label="Univariate HHI", c_range=(0.01, 2.0))

    univariate_comparison = {}
    if univar_size.get("status") == "fitted" and univar_hhi.get("status") == "fitted":
        # Observation-level R² for fair comparison
        r2_size = univar_size.get("r_squared_obs", univar_size.get("r_squared", 0.0))
        r2_hhi = univar_hhi.get("r_squared_obs", univar_hhi.get("r_squared", 0.0))
        # AIC approximation: n*ln(RSS/n) + 2k, k=3 for A+B+C
        n_obs = len(y_sq)
        # Compute RSS from observation-level fit
        fitted_size_vals = univar_size["A"] + univar_size["B"] * R ** univar_size["C"]
        cap_s = univar_size["winsorise_cap"]
        y_sq_w_s = np.minimum(y_sq, cap_s)
        rss_size = float(np.sum((y_sq_w_s - fitted_size_vals) ** 2))
        fitted_hhi_vals = univar_hhi["A"] + univar_hhi["B"] * HHI ** univar_hhi["C"]
        cap_h = univar_hhi["winsorise_cap"]
        y_sq_w_h = np.minimum(y_sq, cap_h)
        rss_hhi = float(np.sum((y_sq_w_h - fitted_hhi_vals) ** 2))
        aic_size = n_obs * math.log(rss_size / n_obs) + 6 if rss_size > 0 else float('inf')
        aic_hhi = n_obs * math.log(rss_hhi / n_obs) + 6 if rss_hhi > 0 else float('inf')
        better = "size" if r2_size > r2_hhi else "hhi"
        univariate_comparison = {
            "size_r2_obs": r2_size,
            "size_r2_binned": univar_size.get("r_squared", 0.0),
            "size_aic": aic_size,
            "size_p_C": univar_size.get("p_C"),
            "hhi_r2_obs": r2_hhi,
            "hhi_r2_binned": univar_hhi.get("r_squared", 0.0),
            "hhi_aic": aic_hhi,
            "hhi_p_C": univar_hhi.get("p_C"),
            "better_univariate": better,
            "r2_difference": abs(r2_size - r2_hhi),
        }
        log(f"  Univariate comparison: size R²={r2_size:.4f}, HHI R²={r2_hhi:.4f} → {better} explains more")

    # Step 1: Predicted variance at each observation's size
    V_obs = A_R + B_R * R ** C_R
    V_obs = np.maximum(V_obs, 1e-10)  # floor to avoid division by zero

    # Step 2: Predicted variance at reference size
    V_ref = A_R + B_R * REFERENCE_SIZE ** C_R

    # Step 3: Size-adjusted squared severity
    y_sq_adj = y_sq * (V_ref / V_obs)

    # Step 4: Fit HHI power-law on size-adjusted s² (C>0: concentration increases variance)
    log("  Fitting HHI power-law on size-adjusted s²")
    disp_h_adj = fit_power_dispersion(HHI, y_sq_adj, label="Concentration (after size adjustment)", c_range=(0.01, 2.0))

    # Also compute scatter data for the chart — use (1-HHI) for x-axis display
    scatter_points = [{
        "x": float(1.0 - HHI[i]),
        "y_raw_sq": float(y_sq[i]),
        "y_adj_sq": float(y_sq_adj[i]),
        "syndicate": eligible[i]["syndicate"],
        "year": eligible[i]["year"],
        "reserves": float(R[i]),
    } for i in range(len(eligible))]

    # Non-parametric quantile curves on size-adjusted s² (x-axis = 1-HHI for display)
    div = 1.0 - HHI
    quantile_bins_adj = local_quantile_regression(div, y_sq_adj, taus=(0.10, 0.90), n_grid=60)

    # Transform for display: negate C for diversification convention, flip curve to (1-HHI)
    if disp_h_adj.get("status") == "fitted":
        disp_h_adj["display_C"] = -disp_h_adj["C"]
        if disp_h_adj.get("c_ci_95") and disp_h_adj["c_ci_95"][0] is not None:
            disp_h_adj["display_c_ci_95"] = [-disp_h_adj["c_ci_95"][1], -disp_h_adj["c_ci_95"][0]]
        # Flip the constraint note when negating
        note = disp_h_adj.get("c_ci_note")
        if note:
            disp_h_adj["display_c_ci_note"] = note.replace("upper bound", "lower bound") if "upper bound" in note else note.replace("lower bound", "upper bound") if "lower bound" in note else note
        if disp_h_adj.get("fitted_curve"):
            disp_h_adj["fitted_curve_display"] = [
                {"x": 1.0 - p["x"], "y": p["y"]} for p in reversed(disp_h_adj["fitted_curve"])
            ]

    # Variance reduction attribution
    var_raw = float(np.var(y_sq))
    var_after_size = float(np.var(y_sq_adj))
    var_explained_by_size_pct = (1.0 - var_after_size / var_raw) * 100 if var_raw > 0 else 0.0

    var_after_hhi = None
    var_explained_by_hhi_pct = None
    if disp_h_adj.get("status") == "fitted":
        fitted_h = disp_h_adj["A"] + disp_h_adj["B"] * HHI ** disp_h_adj["C"]
        resid_after_hhi = y_sq_adj - fitted_h
        var_after_hhi = float(np.var(resid_after_hhi))
        var_explained_by_hhi_pct = (1.0 - var_after_hhi / var_after_size) * 100 if var_after_size > 0 else 0.0

    # ── Alternative pipeline: HHI-first, then size ──────────────
    # Step A: Fit HHI power-law on raw s² (no size adjustment)
    log("  Alternative pipeline: HHI first, then size on residuals")
    disp_h_raw = fit_power_dispersion(HHI, y_sq, label="Concentration (raw, HHI-first)", c_range=(0.01, 2.0))

    hhi_first_result = {}
    if disp_h_raw.get("status") == "fitted":
        # Step B: Compute HHI-adjusted s² (scale to reference HHI = median)
        median_hhi_ref = float(np.median(HHI))
        V_hhi_obs = disp_h_raw["A"] + disp_h_raw["B"] * HHI ** disp_h_raw["C"]
        V_hhi_obs = np.maximum(V_hhi_obs, 1e-10)
        V_hhi_ref_val = disp_h_raw["A"] + disp_h_raw["B"] * median_hhi_ref ** disp_h_raw["C"]
        y_sq_hhi_adj = y_sq * (V_hhi_ref_val / V_hhi_obs)

        # Step C: Fit size power-law on HHI-adjusted residuals
        log("  Fitting size power-law on HHI-adjusted s²")
        disp_r_on_hhi_resid = fit_power_dispersion(R, y_sq_hhi_adj, label="Size (after HHI adjustment)", c_range=(-0.99, -0.01))

        # Variance attribution for HHI-first pipeline
        var_after_hhi_first = float(np.var(y_sq_hhi_adj))
        var_explained_by_hhi_first_pct = (1.0 - var_after_hhi_first / var_raw) * 100 if var_raw > 0 else 0.0

        var_after_size_second = None
        var_explained_by_size_second_pct = None
        if disp_r_on_hhi_resid.get("status") == "fitted":
            fitted_r_second = disp_r_on_hhi_resid["A"] + disp_r_on_hhi_resid["B"] * R ** disp_r_on_hhi_resid["C"]
            resid_after_size_second = y_sq_hhi_adj - fitted_r_second
            var_after_size_second = float(np.var(resid_after_size_second))
            var_explained_by_size_second_pct = (1.0 - var_after_size_second / var_after_hhi_first) * 100 if var_after_hhi_first > 0 else 0.0

        # Transform for display
        if disp_h_raw.get("status") == "fitted":
            disp_h_raw["display_C"] = -disp_h_raw["C"]
            if disp_h_raw.get("c_ci_95") and disp_h_raw["c_ci_95"][0] is not None:
                disp_h_raw["display_c_ci_95"] = [-disp_h_raw["c_ci_95"][1], -disp_h_raw["c_ci_95"][0]]
            note = disp_h_raw.get("c_ci_note")
            if note:
                disp_h_raw["display_c_ci_note"] = note.replace("upper bound", "lower bound") if "upper bound" in note else note.replace("lower bound", "upper bound") if "lower bound" in note else note
            if disp_h_raw.get("fitted_curve"):
                disp_h_raw["fitted_curve_display"] = [
                    {"x": 1.0 - p["x"], "y": p["y"]} for p in reversed(disp_h_raw["fitted_curve"])
                ]

        # Scatter points for HHI-adjusted plot
        hhi_first_scatter = [{
            "x": float(R[i]),
            "y_raw_sq": float(y_sq[i]),
            "y_adj_sq": float(y_sq_hhi_adj[i]),
            "syndicate": eligible[i]["syndicate"],
            "year": eligible[i]["year"],
            "hhi": float(HHI[i]),
        } for i in range(len(eligible))]

        hhi_first_result = {
            "disp_h_raw": disp_h_raw,
            "disp_r_on_residuals": disp_r_on_hhi_resid,
            "reference_hhi": median_hhi_ref,
            "scatter_points": hhi_first_scatter,
            "variance_attribution": {
                "var_raw_sq": var_raw,
                "var_after_hhi_adj": var_after_hhi_first,
                "pct_explained_by_hhi": float(var_explained_by_hhi_first_pct),
                "var_after_size_adj": var_after_size_second,
                "pct_explained_by_size": var_explained_by_size_second_pct,
            },
        }

    # ── Ordering comparison ────────────────────────────────────
    ordering_comparison = {}
    total_explained_size_first = None
    total_explained_hhi_first = None
    if var_raw > 0:
        if var_after_hhi is not None:
            total_explained_size_first = (1.0 - var_after_hhi / var_raw) * 100
        if hhi_first_result and hhi_first_result.get("variance_attribution", {}).get("var_after_size_adj") is not None:
            total_explained_hhi_first = (1.0 - hhi_first_result["variance_attribution"]["var_after_size_adj"] / var_raw) * 100

    if total_explained_size_first is not None and total_explained_hhi_first is not None:
        diff = total_explained_size_first - total_explained_hhi_first
        if abs(diff) < 1.0:
            recommendation = "equivalent"
            rec_reason = "Both orderings explain similar total variance (difference < 1pp). Either pipeline is acceptable."
        elif diff > 0:
            recommendation = "size_first"
            rec_reason = "Size-first explains more total variance, suggesting size is the dominant effect and should be removed first for cleaner HHI estimation."
        else:
            recommendation = "hhi_first"
            rec_reason = "HHI-first explains more total variance, suggesting concentration is the dominant effect and should be removed first for cleaner size estimation."

        ordering_comparison = {
            "total_explained_size_first": total_explained_size_first,
            "total_explained_hhi_first": total_explained_hhi_first,
            "difference_pp": diff,
            "recommendation": recommendation,
            "recommendation_reason": rec_reason,
            "size_first_incremental_size": float(var_explained_by_size_pct),
            "size_first_incremental_hhi": float(var_explained_by_hhi_pct) if var_explained_by_hhi_pct is not None else None,
            "hhi_first_incremental_hhi": float(hhi_first_result["variance_attribution"]["pct_explained_by_hhi"]) if hhi_first_result else None,
            "hhi_first_incremental_size": float(hhi_first_result["variance_attribution"]["pct_explained_by_size"]) if hhi_first_result and hhi_first_result["variance_attribution"].get("pct_explained_by_size") is not None else None,
        }
        log(f"  Ordering comparison: size-first={total_explained_size_first:.1f}%, hhi-first={total_explained_hhi_first:.1f}% → {recommendation}")

    # Compute combined model metrics
    median_hhi = float(np.median(HHI))
    combined_model = None
    if disp_h_adj.get("status") == "fitted":
        A_H = disp_h_adj["A"]
        B_H = disp_h_adj["B"]
        C_H = disp_h_adj["C"]
        # V_hhi at reference (median) HHI
        v_hhi_ref = A_H + B_H * median_hhi ** C_H
        combined_model = {
            "size": {"A": A_R, "B": B_R, "C": C_R},
            "hhi": {"A": A_H, "B": B_H, "C": C_H},
            "reference_size": REFERENCE_SIZE,
            "reference_hhi": median_hhi,
            "v_hhi_ref": v_hhi_ref,
            "formula": "s2(R, HHI) = V_size(R) * V_hhi(HHI) / V_hhi(HHI_ref)",
        }

    return {
        "status": "completed",
        "n": len(eligible),
        "hhi_r_correlation": hhi_r_correlation,
        "size_model_used": {"A": A_R, "B": B_R, "C": C_R},
        "reference_size": REFERENCE_SIZE,
        "median_hhi": median_hhi,
        "disp_h_adjusted": disp_h_adj,
        "combined_model": combined_model,
        "scatter_points": scatter_points,
        "quantile_bins_adj": quantile_bins_adj,
        "variance_attribution": {
            "var_raw_sq": var_raw,
            "var_after_size_adj": var_after_size,
            "pct_explained_by_size": float(var_explained_by_size_pct),
            "var_after_hhi_adj": var_after_hhi,
            "pct_explained_by_hhi": var_explained_by_hhi_pct,
        },
        "univariate_comparison": univariate_comparison,
        "hhi_first": hhi_first_result,
        "ordering_comparison": ordering_comparison,
    }


# ─────────────────────────────────────────────────────────────────────────────
# N5: Exposure Composition — HHI Diversification + LoB Shrinkage Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n5(records):
    """N5 — Exposure composition: HHI diversification scaling + LoB dispersion."""
    log("N5: Exposure Composition (HHI + LoB Dispersion)")

    # ── HHI diversification scatter ──────────────────────────────
    # Exclude HHI≥0.99 (single-LoB reporters — structural break, not true concentration)
    eligible = [r for r in records
                if r.get("eligible_for_n3", False)
                and r["s_raw_a"] is not None
                and r.get("hhi") is not None
                and r.get("hhi", 1.0) < 0.99
                and r.get("weight_source") != "none"]
    if len(eligible) < 10:
        return {"status": "insufficient_data", "n": len(eligible)}

    y = np.array([r["s_raw_a"] for r in eligible], dtype=float)
    div = np.array([1.0 - r["hhi"] for r in eligible], dtype=float)  # (1 - HHI)
    abs_y = np.abs(y)
    n = len(y)

    # Direction: OLS of severity on (1-HHI)
    X_dir = np.column_stack([np.ones(n), div])
    beta_dir, se_dir, resid_dir = ols_with_se(X_dir, y)

    # Dispersion: OLS of |severity| on (1-HHI)
    X_disp = np.column_stack([np.ones(n), div])
    beta_disp, se_disp, resid_disp = ols_with_se(X_disp, abs_y)

    def _p(b, s):
        if s <= 0: return None
        z = abs(b / s)
        return 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))

    p_dir = _p(float(beta_dir[1]), float(se_dir[1]))
    p_disp = _p(float(beta_disp[1]), float(se_disp[1]))

    # Non-parametric quantile curves for (1-HHI) scatter
    hhi_quantile_bins = local_quantile_regression(div, y, taus=(0.10, 0.90), n_grid=60)

    scatter_points = [{
        "x": float(1.0 - r["hhi"]),
        "y": r["s_raw_a"],
        "syndicate": r["syndicate"],
        "year": r["year"],
    } for r in eligible]

    # ── Power-law dispersion models ──────────────────────────────
    # Y = s², the per-observation variance proxy
    y_sq = y ** 2
    # Use HHI (concentration) with C>0 — avoids singularity at H=0
    # s² = A + B·HHI^C: concentrated portfolios (HHI→1) have high variance,
    # diversified (HHI→0) approach floor A.
    HHI = np.array([r["hhi"] for r in eligible], dtype=float)
    HHI = np.maximum(HHI, 0.01)  # floor to avoid 0^C
    R = np.array([r["opening_reserves_gbp_m"] for r in eligible], dtype=float)

    log("  Fitting power-law dispersion: single-factor HHI (concentration)")
    disp_h = fit_power_dispersion(HHI, y_sq, label="Mix concentration (HHI)", c_range=(0.01, 2.0))
    # Transform for display: negate C for diversification convention, flip curve to (1-HHI)
    if disp_h.get("status") == "fitted":
        disp_h["display_C"] = -disp_h["C"]
        if disp_h.get("c_ci_95") and disp_h["c_ci_95"][0] is not None:
            disp_h["display_c_ci_95"] = [-disp_h["c_ci_95"][1], -disp_h["c_ci_95"][0]]
        note = disp_h.get("c_ci_note")
        if note:
            disp_h["display_c_ci_note"] = note.replace("upper bound", "lower bound") if "upper bound" in note else note.replace("lower bound", "upper bound") if "lower bound" in note else note
        if disp_h.get("fitted_curve"):
            disp_h["fitted_curve_display"] = [
                {"x": 1.0 - p["x"], "y": p["y"]} for p in reversed(disp_h["fitted_curve"])
            ]
    log("  Fitting power-law dispersion: single-factor R")
    disp_r = fit_power_dispersion(R, y_sq, label="Size diversification (R = reserves)")
    log("  Fitting power-law dispersion: joint HHI + R")
    disp_joint = fit_joint_power_dispersion(HHI, R, y_sq)
    log("  Fitting power-law dispersion: joint no-intercept HHI + R")
    disp_joint_noint = fit_joint_power_no_intercept(HHI, R, y_sq)

    # ── Per-LoB dispersion parameters ──────────────────────────
    # Model: s² ≈ Σ_ℓ w_ℓ · σ²_ℓ  (linear in weights, σ²_ℓ ≥ 0)
    # Estimates per-LoB variance contribution via NNLS (non-negative least squares)
    log("  Estimating per-LoB dispersion parameters")
    W = np.array([r["weights"] for r in eligible], dtype=float)  # n × L
    # Winsorise y_sq for LoB estimation too
    cap_lob = float(np.percentile(y_sq, 95))
    y_sq_w = np.minimum(y_sq, cap_lob)

    # NNLS: min ||W·σ² - y_sq||² s.t. σ² ≥ 0
    # Use iterative projection: start with OLS, clamp negatives to 0, re-fit
    try:
        from scipy.optimize import nnls
        sigma2_lob, nnls_resid = nnls(W, y_sq_w)
    except ImportError:
        # Fallback: simple OLS with clamping
        beta_lob, _ = ols_fit(W, y_sq_w)
        sigma2_lob = np.maximum(beta_lob, 0.0)
        nnls_resid = float(np.sum((y_sq_w - W @ sigma2_lob) ** 2))

    # R² for the LoB model
    ss_tot_lob = float(np.sum((y_sq_w - np.mean(y_sq_w)) ** 2))
    fitted_lob = W @ sigma2_lob
    ss_res_lob = float(np.sum((y_sq_w - fitted_lob) ** 2))
    r_sq_lob = 1.0 - ss_res_lob / ss_tot_lob if ss_tot_lob > 0 else 0.0

    lob_dispersion = []
    for l in range(N_LOBS):
        n_active = int(np.sum(W[:, l] > 0))
        lob_dispersion.append({
            "lob": LOB_NAMES[l],
            "sigma2": float(sigma2_lob[l]),
            "n_active": n_active,
        })

    # Check stability: compare single-factor params to joint
    stability_flags = []
    if disp_h.get("status") == "fitted" and disp_joint.get("status") == "fitted":
        if disp_joint.get("C1") is not None and disp_h.get("C") is not None:
            c1_shift = abs(disp_joint["C1"] - disp_h["C"])
            if c1_shift > 0.3:
                stability_flags.append(f"C1 shifted by {c1_shift:.2f} from single to joint — possible collinearity")
    if disp_r.get("status") == "fitted" and disp_joint.get("status") == "fitted":
        if disp_joint.get("C2") is not None and disp_r.get("C") is not None:
            c2_shift = abs(disp_joint["C2"] - disp_r["C"])
            if c2_shift > 0.3:
                stability_flags.append(f"C2 shifted by {c2_shift:.2f} from single to joint — possible collinearity")

    return {
        "status": "completed",
        "n": n,
        "hhi_direction": {
            "beta": float(beta_dir[1]), "se": float(se_dir[1]), "p_value": p_dir,
            "intercept": float(beta_dir[0]),
        },
        "hhi_scatter_points": scatter_points,
        "hhi_quantile_bins": hhi_quantile_bins,
        "dispersion_models": {
            "single_h": disp_h,
            "single_r": disp_r,
            "joint": disp_joint,
            "joint_no_intercept": disp_joint_noint,
            "stability_flags": stability_flags,
        },
        "lob_dispersion": {
            "parameters": lob_dispersion,
            "r_squared": r_sq_lob,
            "model": "s² ≈ Σ w_ℓ · σ²_ℓ (NNLS, winsorised at p95)",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# N4: Capital Distortion (Shapley) + Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def analysis_n4(records, subset_records):
    """N4 — Capital Distortion with Shapley decomposition and bootstrap."""
    log("N4: Capital Distortion (Shapley)")
    eligible = [r for r in records if r.get("eligible_for_capital", False)]
    if len(eligible) < 20:
        return {"status": "insufficient_data", "n": len(eligible)}

    # Market reference mix
    dense_weights = [np.array(r["weights"]) for r in subset_records["DENSE"]
                     if r["weight_source"] != "none"]
    if dense_weights:
        market_mix = np.mean(dense_weights, axis=0)
        s = market_mix.sum()
        if s > 0:
            market_mix /= s
    else:
        market_mix = np.ones(N_LOBS) / N_LOBS

    results = {"test_portfolios": {}, "market_reference_mix": market_mix.tolist()}

    # Test portfolios
    for tp in TEST_PORTFOLIOS:
        tw = portfolio_weights_vector(tp["weights"])
        tw_sum = tw.sum()
        if tw_sum > 0:
            tw = tw / tw_sum
        naive, mix_only, size_only, full_adj = compute_four_distributions(eligible, tw, tp["size"])
        metrics = compute_capital_metrics(naive, mix_only, size_only, full_adj)
        results["test_portfolios"][tp["name"]] = metrics
        results["test_portfolios"][tp["name"]]["target_weights"] = tp["weights"]
        results["test_portfolios"][tp["name"]]["size"] = tp["size"]

    # Bootstrap
    log("  N4: Bootstrap (500 replicates)")
    rng = np.random.RandomState(42)
    unique_synd = sorted(set(r["syndicate"] for r in eligible if r["syndicate"] is not None))

    boot_results = {tp["name"]: defaultdict(list) for tp in TEST_PORTFOLIOS}

    for b in range(500):
        if b % 100 == 0:
            log(f"    Bootstrap replicate {b}/500")
        boot_synds = rng.choice(unique_synd, size=len(unique_synd), replace=True)
        # Build bootstrap sample
        synd_to_recs = defaultdict(list)
        for r in eligible:
            synd_to_recs[r["syndicate"]].append(r)

        boot_sample = []
        for bs in boot_synds:
            boot_sample.extend(synd_to_recs[bs])

        for tp in TEST_PORTFOLIOS:
            tw = portfolio_weights_vector(tp["weights"])
            tw_sum = tw.sum()
            if tw_sum > 0:
                tw = tw / tw_sum
            b_naive, b_mix, b_size, b_full = compute_four_distributions(
                boot_sample, tw, tp["size"], eligible_key="eligible_for_capital")
            if len(b_naive) < 5:
                continue
            for label, arr in [("naive", b_naive), ("concentration_only", b_mix),
                               ("size_only", b_size), ("full", b_full)]:
                for metric_name, func, level in [
                    ("var_99", var_at, 0.99), ("var_995", var_at, 0.995),
                    ("tvar_99", tvar_at, 0.99), ("tvar_995", tvar_at, 0.995),
                ]:
                    key = f"{label}_{metric_name}"
                    val = func(arr, level)
                    if val is not None:
                        boot_results[tp["name"]][key].append(val)

    # Add bootstrap CIs to results
    for tp_name in boot_results:
        results["test_portfolios"][tp_name]["bootstrap_ci"] = {}
        for key, vals in boot_results[tp_name].items():
            if vals:
                results["test_portfolios"][tp_name]["bootstrap_ci"][key] = {
                    "ci_2_5": float(np.percentile(vals, 2.5)),
                    "ci_97_5": float(np.percentile(vals, 97.5)),
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                }

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Local-Donor Sensitivity (A.5.8)
# ─────────────────────────────────────────────────────────────────────────────

def analysis_local_donor(records, subset_records):
    """Local-Donor Sensitivity analysis."""
    log("Local-Donor Sensitivity")
    eligible = [r for r in records if r.get("eligible_for_capital", False)]
    if len(eligible) < 10:
        return {"status": "insufficient_data"}

    # Only £500m test portfolios
    tp_500 = [tp for tp in TEST_PORTFOLIOS if tp["size"] == 500]
    results = {}

    for tp in tp_500:
        tw = portfolio_weights_vector(tp["weights"])
        tw_sum = tw.sum()
        if tw_sum > 0:
            tw = tw / tw_sum
        # Size+HHI of the target portfolio
        tp_hhi = float(compute_hhi(tw))

        sensitivity = []
        for h_max in HELLINGER_THRESHOLDS:
            donors = []
            for r in eligible:
                w_s = np.array(r["weights"], dtype=float)
                h = hellinger_distance(w_s, tw)
                if h <= h_max:
                    donors.append(r)

            if len(donors) < 5:
                sensitivity.append({
                    "h_max": h_max,
                    "n_donors": len(donors),
                    "var_995_raw": None,
                    "var_995_adjusted": None,
                })
                continue

            raw_sev = [r["s_raw_a"] for r in donors if r["s_raw_a"] is not None]
            adj_sev = []
            for r in donors:
                if r["lob_severity_computed"]:
                    s_mix = float(np.sum(tw * np.array(r["lob_severity"])))
                    # Per-donor adjustment: scale from donor's observed size/HHI
                    # to target portfolio size/HHI (consistent with compute_four_distributions)
                    r_obs = r.get("opening_reserves_gbp_m") or REFERENCE_SIZE
                    hhi_obs = r.get("hhi") or tp_hhi
                    adj = dispersion_adjustment(tp["size"], tp_hhi, r_obs, hhi_obs)
                    adj_sev.append(s_mix * adj)

            sensitivity.append({
                "h_max": h_max,
                "n_donors": len(donors),
                "var_995_raw": var_at(raw_sev, 0.995) if len(raw_sev) >= 5 else None,
                "var_995_adjusted": var_at(adj_sev, 0.995) if len(adj_sev) >= 5 else None,
            })

        results[tp["name"]] = sensitivity

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Personas (A.6)
# ─────────────────────────────────────────────────────────────────────────────

def analysis_personas(records, subset_records):
    """Persona analysis."""
    log("Personas")
    full = [r for r in subset_records["FULL"] if r.get("eligible_for_persona", False)]
    if len(full) < 10:
        return {"status": "insufficient_data"}

    # Collect reserves and HHI
    reserves = [r["opening_reserves_gbp_m"] for r in full if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
    hhis = [r["hhi"] for r in full if r["hhi"] is not None]
    divs = [1.0 - h for h in hhis]

    if not reserves or not hhis:
        return {"status": "insufficient_data"}

    median_reserves = float(np.median(reserves))
    p5_reserves = float(np.percentile(reserves, 5))
    p95_reserves = float(np.percentile(reserves, 95))
    median_div = float(np.median(divs))

    personas = {}

    # A.6.1 Definitions — derive target HHI and LoB weights from 10 size-nearest neighbours
    def size_neighbours(target_size, n_neighbours=10):
        """Find n_neighbours nearest by reserves. Returns (median_hhi, avg_weights, median_lob_count)."""
        candidates = [(abs(r["opening_reserves_gbp_m"] - target_size), r)
                       for r in full
                       if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0
                       and r.get("hhi") is not None and r.get("weight_source") != "none"]
        candidates.sort(key=lambda x: x[0])
        nn = [x[1] for x in candidates[:n_neighbours]]
        if not nn:
            return float(np.median(hhis)), np.ones(N_LOBS) / N_LOBS, N_LOBS
        nn_hhis = [r["hhi"] for r in nn]
        nn_weights = [np.array(r["weights"]) for r in nn]
        avg_w = np.mean(nn_weights, axis=0)
        s = avg_w.sum()
        if s > 0:
            avg_w /= s
        nn_lob_counts = [int(np.sum(np.array(r["weights"]) > 0.01)) for r in nn]
        return float(np.median(nn_hhis)), avg_w, int(np.median(nn_lob_counts))

    def prune_to_n_lobs(weights, n_lobs):
        """Zero out the smallest LoBs to keep only n_lobs active, then renormalise."""
        w = weights.copy()
        if np.sum(w > 0) <= n_lobs:
            return w
        sorted_indices = np.argsort(w)
        n_to_zero = len(w) - n_lobs
        w[sorted_indices[:n_to_zero]] = 0.0
        s = w.sum()
        if s > 0:
            w /= s
        return w

    def adjust_weights_to_hhi(weights, target_hhi):
        """Blend weights toward/away from uniform to hit target HHI.

        HHI(alpha*w + (1-alpha)*u) = alpha^2 * (HHI(w) - 1/N) + 1/N
        Preserves relative LoB proportions.
        """
        w = weights.copy()
        s = w.sum()
        if s > 0:
            w /= s
        u = np.ones(N_LOBS) / N_LOBS
        hw = compute_hhi(w)

        # Already at target?
        if abs(hw - target_hhi) < 0.001:
            return w

        denom = hw - 1.0 / N_LOBS
        if abs(denom) < 1e-10:
            return w  # weights are already uniform, can't adjust

        alpha_sq = (target_hhi - 1.0 / N_LOBS) / denom
        if alpha_sq < 0:
            alpha_sq = 0.0  # target more uniform than uniform — clamp
        elif alpha_sq > 4.0:
            alpha_sq = 4.0  # cap to avoid extreme concentration
        alpha = math.sqrt(alpha_sq)

        adjusted = alpha * w + (1 - alpha) * u
        s = adjusted.sum()
        if s > 0:
            adjusted /= s
        return adjusted

    def hhi_neighbours(target_hhi, n_neighbours=10):
        """Find n_neighbours nearest by HHI. Returns (avg_weights, median_lob_count)."""
        candidates = [(abs(r["hhi"] - target_hhi), r)
                       for r in full
                       if r.get("hhi") is not None and r.get("weight_source") != "none"]
        candidates.sort(key=lambda x: x[0])
        nn = [x[1] for x in candidates[:n_neighbours]]
        if not nn:
            return np.ones(N_LOBS) / N_LOBS, N_LOBS
        nn_weights = [np.array(r["weights"]) for r in nn]
        avg_w = np.mean(nn_weights, axis=0)
        s = avg_w.sum()
        if s > 0:
            avg_w /= s
        nn_lob_counts = [int(np.sum(np.array(r["weights"]) > 0.01)) for r in nn]
        return avg_w, int(np.median(nn_lob_counts))

    def build_persona_weights(raw_weights, lob_count, target_hhi):
        """Prune then adjust to target HHI."""
        return adjust_weights_to_hhi(prune_to_n_lobs(raw_weights, lob_count), target_hhi)

    # ── Typical: market-wide medians ──────────────────────────
    median_hhi = float(np.median(hhis))
    all_weights = [np.array(r["weights"]) for r in full if r["weight_source"] != "none"]
    active_lob_counts = [int(np.sum(w > 0.01)) for w in all_weights]
    median_lob_count = int(np.median(active_lob_counts)) if active_lob_counts else N_LOBS
    if all_weights:
        typical_weights_raw = np.mean(all_weights, axis=0)
        s = typical_weights_raw.sum()
        if s > 0:
            typical_weights_raw /= s
    else:
        typical_weights_raw = np.ones(N_LOBS) / N_LOBS
    typical_weights = build_persona_weights(typical_weights_raw, median_lob_count, median_hhi)

    # ── Small/Large: 10 nearest neighbours by reserve size ────
    small_hhi, small_weights_raw, small_lob_count = size_neighbours(p5_reserves)
    large_hhi, large_weights_raw, large_lob_count = size_neighbours(p95_reserves)
    small_weights = build_persona_weights(small_weights_raw, small_lob_count, small_hhi)
    large_weights = build_persona_weights(large_weights_raw, large_lob_count, large_hhi)

    # ── Diversified/Undiversified: 10 nearest neighbours by HHI
    p5_hhi = float(np.percentile(hhis, 5))
    p95_hhi = float(np.percentile(hhis, 95))

    div_weights_raw, div_lob_count = hhi_neighbours(p5_hhi)
    diversified_weights = build_persona_weights(div_weights_raw, div_lob_count, p5_hhi)

    undiv_weights_raw, undiv_lob_count = hhi_neighbours(p95_hhi)
    undiversified_weights = build_persona_weights(undiv_weights_raw, undiv_lob_count, p95_hhi)

    persona_defs = {
        "typical": {"reserves": median_reserves, "hhi": median_hhi, "diversification": 1.0 - median_hhi},
        "small": {"reserves": p5_reserves, "hhi": small_hhi, "diversification": 1.0 - small_hhi},
        "large": {"reserves": p95_reserves, "hhi": large_hhi, "diversification": 1.0 - large_hhi},
        "diversified": {"reserves": median_reserves, "hhi": p5_hhi, "diversification": 1.0 - p5_hhi},
        "undiversified": {"reserves": median_reserves, "hhi": p95_hhi, "diversification": 1.0 - p95_hhi},
    }

    persona_weights = {
        "typical": typical_weights,
        "small": small_weights,
        "large": large_weights,
        "diversified": diversified_weights,
        "undiversified": undiversified_weights,
    }

    # A.6.3 Nearest syndicates
    all_reserves = sorted([r["opening_reserves_gbp_m"] for r in full
                           if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0])
    all_hhi = sorted([r["hhi"] for r in full if r.get("hhi") is not None])

    def percentile_rank(value, sorted_values):
        """Compute the percentile rank of value in sorted_values (0 to 1)."""
        if not sorted_values:
            return 0.5
        n = len(sorted_values)
        count = sum(1 for v in sorted_values if v <= value)
        return count / n

    eligible_capital = [r for r in records if r.get("eligible_for_capital", False)]

    for pname in ["typical", "small", "large", "diversified", "undiversified"]:
        pw = persona_weights[pname]
        pr = persona_defs[pname]["reserves"]
        p_hhi = persona_defs[pname]["hhi"]

        pctile_r_persona = percentile_rank(pr, all_reserves)
        pctile_h_persona = percentile_rank(p_hhi, all_hhi)

        # Compute composite distance for all eligible_for_persona records
        distances = []
        for r in full:
            if r["opening_reserves_gbp_m"] is None or r["opening_reserves_gbp_m"] <= 0:
                continue
            if r["weight_source"] == "none":
                continue
            pctile_r_i = percentile_rank(r["opening_reserves_gbp_m"], all_reserves)
            pctile_h_i = percentile_rank(r["hhi"], all_hhi)
            d = 0.4 * abs(pctile_r_i - pctile_r_persona) + 0.6 * abs(pctile_h_i - pctile_h_persona)
            distances.append((d, r))

        distances.sort(key=lambda x: x[0])

        # Select 3 closest, no duplicate syndicates (keep closest year)
        nearest = []
        seen_syndicates = set()
        for d, r in distances:
            if r["syndicate"] not in seen_syndicates:
                nearest.append({
                    "syndicate": r["syndicate"],
                    "year": r["year"],
                    "distance": d,
                    "reserves_m": r.get("opening_reserves_gbp_m"),
                    "hhi": r.get("hhi"),
                    "diversification": 1.0 - r["hhi"] if r.get("hhi") is not None else None,
                    "lob_weights": {LOB_NAMES[i]: float(r["weights"][i]) for i in range(N_LOBS) if r["weights"][i] > 0},
                })
                seen_syndicates.add(r["syndicate"])
                if len(nearest) >= 3:
                    break

        nearest_syndicate_ids = [n["syndicate"] for n in nearest]

        # A.6.4 Histograms
        # (b) All years for nearest 3 syndicates in FULL
        nearest_recs = [r for r in subset_records["FULL"] if r["syndicate"] in nearest_syndicate_ids]
        nearest_sev = [r["pyd_pct"] for r in nearest_recs if r["pyd_pct"] is not None]

        # (c) Residual-based rescaling to persona
        # Step 4a: raw residuals = PYD% - market mean PYD%
        market_raw = [r["pyd_pct"] for r in subset_records["FULL"] if r["pyd_pct"] is not None]
        mu_ref_pct, _, _, _ = compute_reference_mean(subset_records["FULL"])

        # Step 4b-c: rescale each residual from observed (R, HHI) to target (R, HHI)
        persona_residuals = []
        multipliers = []
        for r in subset_records["FULL"]:
            if r["pyd_pct"] is None:
                continue
            raw_residual = r["pyd_pct"] - mu_ref_pct
            r_obs = r.get("opening_reserves_gbp_m")
            hhi_obs = r.get("hhi")
            if r_obs and r_obs > 0 and hhi_obs is not None:
                m = dispersion_adjustment(pr, p_hhi, r_obs, hhi_obs)
            else:
                m = 1.0
            persona_residual = raw_residual * m
            # Persona PYD% = mean + rescaled residual, capped at -100%
            persona_pyd = max(mu_ref_pct + persona_residual, -100.0)
            persona_residuals.append(persona_pyd)
            multipliers.append(m)

        market_std = persona_residuals

        def histogram_bins(values, bin_width=2.0):
            if not values:
                return {"bins": [], "counts": [], "bin_width": bin_width}
            arr = np.array(values)
            lo = math.floor(arr.min() / bin_width) * bin_width
            hi = math.ceil(arr.max() / bin_width) * bin_width
            edges = np.arange(lo, hi + bin_width, bin_width)
            counts, _ = np.histogram(arr, bins=edges)
            bin_centers = [(edges[i] + edges[i+1]) / 2 for i in range(len(counts))]
            return {
                "bins": [float(b) for b in bin_centers],
                "counts": [int(c) for c in counts],
                "bin_width": bin_width,
            }

        # Capital metrics — use persona's target HHI, not HHI implied by weights
        naive, mix_only, size_only, full_adj = compute_four_distributions(
            eligible_capital, pw, pr, target_hhi=p_hhi)
        capital = compute_capital_metrics(naive, mix_only, size_only, full_adj)

        def distribution_stats(values):
            if not values:
                return {}
            arr = np.array(values, dtype=float)
            return {
                "n": len(arr),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                "p10": float(np.percentile(arr, 10)),
                "p75": float(np.percentile(arr, 75)),
                "p90": float(np.percentile(arr, 90)),
                "p99": float(np.percentile(arr, 99)),
                "p995": float(np.percentile(arr, 99.5)),
            }

        # Step 5: multiplier diagnostics
        multiplier_stats = distribution_stats(multipliers) if multipliers else {}

        # Kish's effective sample size
        kish_n_eff = None
        if multipliers:
            m_arr = np.array(multipliers)
            sum_m = float(np.sum(m_arr))
            sum_m2 = float(np.sum(m_arr ** 2))
            kish_n_eff = (sum_m ** 2) / sum_m2 if sum_m2 > 0 else len(multipliers)

        # Leptokurtosis: excess kurtosis of raw vs rescaled residuals
        raw_residuals = [r["pyd_pct"] - mu_ref_pct for r in subset_records["FULL"] if r["pyd_pct"] is not None]
        rescaled_residuals = [market_std[i] - mu_ref_pct for i in range(len(market_std))]
        raw_kurtosis = None
        rescaled_kurtosis = None
        if len(raw_residuals) > 3:
            rr = np.array(raw_residuals)
            sd_rr = float(np.std(rr, ddof=1))
            if sd_rr > 0:
                raw_kurtosis = float(np.mean(((rr - np.mean(rr)) / sd_rr) ** 4) - 3.0)
        if len(rescaled_residuals) > 3:
            sr = np.array(rescaled_residuals)
            sd_sr = float(np.std(sr, ddof=1))
            if sd_sr > 0:
                rescaled_kurtosis = float(np.mean(((sr - np.mean(sr)) / sd_sr) ** 4) - 3.0)

        # Tail concentration diagnostics
        nn_syndicate_years = set()
        for ns in nearest:
            nn_syndicate_years.add((ns["syndicate"], ns["year"]))

        # Build paired list: (rescaled_pyd, multiplier, is_nearest_neighbour)
        paired = []
        idx = 0
        for r in subset_records["FULL"]:
            if r["pyd_pct"] is None:
                continue
            is_nn = (r["syndicate"], r["year"]) in nn_syndicate_years
            paired.append((market_std[idx], multipliers[idx], is_nn))
            idx += 1

        # Top 10% of rescaled distribution
        top_10pct_threshold = float(np.percentile([p[0] for p in paired], 90)) if paired else 0
        top_10pct = [p for p in paired if p[0] >= top_10pct_threshold]
        n_top10 = len(top_10pct)

        # Proportion of top 10% from nearest neighbours
        nn_in_top10 = sum(1 for p in top_10pct if p[2])
        pct_top10_from_nn = (nn_in_top10 / n_top10 * 100) if n_top10 > 0 else 0.0

        # Proportion of top 10% with multiplier > 1.5 (manufactured tail)
        manufactured_in_top10 = sum(1 for p in top_10pct if p[1] > 1.5)
        pct_top10_manufactured = (manufactured_in_top10 / n_top10 * 100) if n_top10 > 0 else 0.0

        # Reference kurtosis: lognormal (positive values) and t-distribution (all values)
        pos_raw = [v for v in raw_residuals if v > 0]
        lognormal_kurtosis = None
        if len(pos_raw) > 10:
            ln_vals = np.log(np.array(pos_raw))
            sigma_ln = float(np.std(ln_vals, ddof=1))
            if sigma_ln > 0:
                # Excess kurtosis of lognormal = exp(4*sigma^2) + 2*exp(3*sigma^2) + 3*exp(2*sigma^2) - 6
                lognormal_kurtosis = float(math.exp(4 * sigma_ln ** 2) + 2 * math.exp(3 * sigma_ln ** 2) + 3 * math.exp(2 * sigma_ln ** 2) - 6)

        t_dist_kurtosis = None
        t_dist_df = None
        if raw_kurtosis is not None and raw_kurtosis > 0:
            # For t-distribution: excess kurtosis = 6/(df-4) for df>4
            # Solve: df = 4 + 6/kurtosis
            if raw_kurtosis > 0:
                t_dist_df = 4.0 + 6.0 / raw_kurtosis
                t_dist_kurtosis = raw_kurtosis  # by construction matches raw

        # Positive tail histogram data (top 10% of raw and rescaled)
        raw_p90 = float(np.percentile(market_raw, 90)) if market_raw else 0
        tail_raw = [v for v in market_raw if v >= raw_p90]
        rescaled_p90 = float(np.percentile(market_std, 90)) if market_std else 0
        tail_rescaled = [v for v in market_std if v >= rescaled_p90]

        tail_diagnostics = {
            "kish_n_eff": kish_n_eff,
            "raw_excess_kurtosis": raw_kurtosis,
            "rescaled_excess_kurtosis": rescaled_kurtosis,
            "lognormal_excess_kurtosis": lognormal_kurtosis,
            "t_dist_df": t_dist_df,
            "n_top10_pct": n_top10,
            "nn_in_top10_pct": nn_in_top10,
            "pct_top10_from_nn": pct_top10_from_nn,
            "manufactured_in_top10": manufactured_in_top10,
            "pct_top10_manufactured": pct_top10_manufactured,
            "tail_histogram_raw": histogram_bins(tail_raw, bin_width=2.0),
            "tail_histogram_rescaled": histogram_bins(tail_rescaled, bin_width=2.0),
        }

        personas[pname] = {
            "definition": persona_defs[pname],
            "weights": pw.tolist(),
            "lob_weights": {LOB_NAMES[i]: float(pw[i]) for i in range(N_LOBS) if pw[i] > 0},
            "hhi": p_hhi,
            "nearest_syndicates": nearest,
            "histogram_nearest": histogram_bins(nearest_sev),
            "histogram_b": histogram_bins(nearest_sev),
            "histogram_market_raw": histogram_bins(market_raw),
            "histogram_market_standardised": histogram_bins(market_std),
            "histogram_c": {
                "raw": histogram_bins(market_raw),
                "standardised": histogram_bins(market_std),
            },
            "histogram_multipliers": histogram_bins(multipliers, bin_width=0.1) if multipliers else {},
            "multiplier_stats": multiplier_stats,
            "tail_diagnostics": tail_diagnostics,
            "market_pyd_stats": {
                "raw": distribution_stats(market_raw),
                "standardised": distribution_stats(market_std),
            },
            "capital": capital,
        }

    return {"status": "completed", "personas": personas}


def _binary_search_blend(w, u, target_hhi, max_iter=100):
    """Binary search for alpha in [0,1] to achieve target HHI."""
    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        alpha = (lo + hi) / 2
        blended = alpha * w + (1 - alpha) * u
        hhi = compute_hhi(blended)
        if hhi < target_hhi:
            lo = alpha
        else:
            hi = alpha
    alpha = (lo + hi) / 2
    return alpha * w + (1 - alpha) * u


# ─────────────────────────────────────────────────────────────────────────────
# Distribution overview
# ─────────────────────────────────────────────────────────────────────────────

def compute_distribution_overview(records):
    """Compute distribution statistics and histogram for the Distribution tab."""
    eligible = [r for r in records if r.get("eligible_for_distribution", False)]
    pyd_pcts = [r["pyd_pct"] for r in eligible if r["pyd_pct"] is not None]

    if not pyd_pcts:
        return {"pyd_histogram": {}, "stats": {}}

    arr = np.array(pyd_pcts, dtype=float)

    # Stats block matching what the viewer expects
    stats = {
        "n": len(pyd_pcts),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "q995": float(np.percentile(arr, 99.5)),
        "p5": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "median_reserves": float(np.median([
            r["opening_reserves_gbp_m"] for r in eligible
            if r.get("opening_reserves_gbp_m") is not None and r["opening_reserves_gbp_m"] > 0
        ])) if any(r.get("opening_reserves_gbp_m") and r["opening_reserves_gbp_m"] > 0 for r in eligible) else None,
    }

    # PYD % histogram with 5pp bins
    bin_lo = int(math.floor(arr.min() / 5.0)) * 5
    bin_hi = int(math.ceil(arr.max() / 5.0)) * 5
    bin_edges = list(range(bin_lo, bin_hi + 5, 5))
    bins = []
    counts = []
    overflow_count = 0
    for i in range(len(bin_edges) - 1):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        label = f"{lo}% to {hi}%"
        if i == len(bin_edges) - 2:
            cnt = int(np.sum((arr >= lo) & (arr <= hi)))
        else:
            cnt = int(np.sum((arr >= lo) & (arr < hi)))
        bins.append(lo)
        counts.append(cnt)

    pyd_histogram = {
        "bins": bins,
        "counts": counts,
        "overflow_count": overflow_count,
        "bin_width": 5,
    }

    return {"pyd_histogram": pyd_histogram, "stats": stats}


def _boxplot_entry(values, label):
    """Compute a single boxplot entry from values."""
    arr = np.array(values, dtype=float)
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    whisker_lo = float(max(arr.min(), q1 - 1.5 * iqr))
    whisker_hi = float(min(arr.max(), q3 + 1.5 * iqr))
    outliers = [float(v) for v in arr if v < whisker_lo or v > whisker_hi]
    return {
        "label": str(label),
        "n": len(values),
        "min": whisker_lo,
        "q1": q1,
        "median": float(np.median(arr)),
        "q3": q3,
        "max": whisker_hi,
        "mean": float(np.mean(arr)),
        "outliers": outliers,
    }


def compute_boxplot_data(records):
    """Boxplot data by reserves decile, HHI decile, complexity decile, and year."""
    eligible = [r for r in records if r.get("eligible_for_boxplot_reserves", False) and r["pyd_pct"] is not None]
    if not eligible:
        return {}

    def decile_boxplots(key_fn, label_fn):
        """Group eligible records into deciles by key_fn and compute boxplots."""
        keyed = [(key_fn(r), r) for r in eligible if key_fn(r) is not None]
        if len(keyed) < 10:
            return []
        keyed.sort(key=lambda x: x[0])
        n = len(keyed)
        dec_size = n // 10
        result = []
        for d in range(10):
            start = d * dec_size
            end = (d + 1) * dec_size if d < 9 else n
            subset = keyed[start:end]
            vals = [r["pyd_pct"] for _, r in subset]
            if len(vals) < 2:
                continue
            lo_key = subset[0][0]
            hi_key = subset[-1][0]
            result.append(_boxplot_entry(vals, label_fn(d + 1, lo_key, hi_key)))
        return result

    by_reserves = decile_boxplots(
        lambda r: r.get("opening_reserves_gbp_m"),
        lambda d, lo, hi: f"D{d} ({lo:.0f}-{hi:.0f})"
    )
    by_hhi = decile_boxplots(
        lambda r: r.get("hhi"),
        lambda d, lo, hi: f"D{d} ({lo:.2f}-{hi:.2f})"
    )
    by_complexity = decile_boxplots(
        lambda r: r.get("complexity"),
        lambda d, lo, hi: f"D{d} ({lo:.0f}-{hi:.0f})"
    )

    # By year
    years = sorted(set(r["year"] for r in eligible))
    by_year = []
    for yr in years:
        yr_vals = [r["pyd_pct"] for r in eligible if r["year"] == yr]
        if len(yr_vals) < 2:
            continue
        by_year.append(_boxplot_entry(yr_vals, str(yr)))

    # Compute decile tests (ANOVA F-test and Bartlett's test)
    def _decile_groups(key_fn):
        """Return list of groups (each a list of pyd_pct values) by decile."""
        keyed = [(key_fn(r), r) for r in eligible if key_fn(r) is not None]
        if len(keyed) < 10:
            return []
        keyed.sort(key=lambda x: x[0])
        n_k = len(keyed)
        dec_size = n_k // 10
        groups = []
        for d in range(10):
            start = d * dec_size
            end = (d + 1) * dec_size if d < 9 else n_k
            vals = [r["pyd_pct"] for _, r in keyed[start:end] if r["pyd_pct"] is not None]
            if len(vals) >= 2:
                groups.append(vals)
        return groups

    def _anova_f_test(groups):
        """One-way ANOVA F-test without scipy."""
        if len(groups) < 2:
            return None, None
        k = len(groups)
        all_vals = []
        for g in groups:
            all_vals.extend(g)
        N = len(all_vals)
        if N <= k:
            return None, None
        grand_mean = sum(all_vals) / N
        ss_between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in groups)
        ss_within = sum(sum((v - sum(g) / len(g)) ** 2 for v in g) for g in groups)
        df1 = k - 1
        df2 = N - k
        if ss_within == 0 or df2 == 0:
            return None, None
        F = (ss_between / df1) / (ss_within / df2)
        # Approximate p-value: for large df2, F*df1 ~ chi2(df1), use normal approx
        # Using the fact that for large samples, sqrt(2*F*df1) - sqrt(2*df1 - 1) ~ N(0,1)
        try:
            x = F * df1
            z = math.sqrt(2 * x) - math.sqrt(2 * df1 - 1) if df1 > 0.5 else 0
            p = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
        except (ValueError, ZeroDivisionError):
            p = None
        return float(F), p

    def _bartlett_test(groups):
        """Bartlett's test for equal variances without scipy."""
        if len(groups) < 2:
            return None, None
        k = len(groups)
        ns = [len(g) for g in groups]
        N = sum(ns)
        if N <= k or any(n < 2 for n in ns):
            return None, None
        vars_ = [float(np.var(g, ddof=1)) for g in groups]
        # Filter out zero variances
        if any(v <= 0 for v in vars_):
            return None, None
        pooled_var = sum((n - 1) * v for n, v in zip(ns, vars_)) / (N - k)
        if pooled_var <= 0:
            return None, None
        numerator = (N - k) * math.log(pooled_var) - sum((n - 1) * math.log(v) for n, v in zip(ns, vars_))
        C = 1.0 + 1.0 / (3.0 * (k - 1)) * (sum(1.0 / (n - 1) for n in ns) - 1.0 / (N - k))
        if C == 0:
            return None, None
        chi2 = numerator / C
        # Approximate p-value: chi2 with k-1 df, use normal approx for large df
        df = k - 1
        try:
            z = math.sqrt(2 * chi2) - math.sqrt(2 * df - 1) if df > 0.5 else 0
            p = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
        except (ValueError, ZeroDivisionError):
            p = None
        return float(chi2), p

    def _compute_decile_test(key_fn):
        groups = _decile_groups(key_fn)
        if not groups:
            return {}
        f_val, f_p = _anova_f_test(groups)
        chi2, b_p = _bartlett_test(groups)
        vars_ = [float(np.var(g, ddof=1)) for g in groups if len(g) >= 2]
        pos_vars = [v for v in vars_ if v > 0]
        variance_ratio = max(pos_vars) / min(pos_vars) if len(pos_vars) >= 2 else None
        return {
            "anova_f": f_val,
            "anova_p": float(f_p) if f_p is not None else None,
            "variance_ratio": float(variance_ratio) if variance_ratio is not None else None,
            "bartlett_chi2": chi2,
            "bartlett_p": float(b_p) if b_p is not None else None,
        }

    decile_tests = {
        "by_reserves_decile": _compute_decile_test(lambda r: r.get("opening_reserves_gbp_m")),
        "by_hhi_decile": _compute_decile_test(lambda r: r.get("hhi")),
        "by_complexity_decile": _compute_decile_test(lambda r: r.get("complexity")),
    }

    return {
        "by_reserves_decile": by_reserves,
        "by_hhi_decile": by_hhi,
        "by_complexity_decile": by_complexity,
        "by_year": by_year,
        "decile_tests": decile_tests,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Worked Example
# ─────────────────────────────────────────────────────────────────────────────

def worked_example(records):
    """Generate a worked example with two syndicates from the same event year.

    Selects a year with enough syndicates, then picks two with contrasting
    reserve sizes and differing LoB compositions.  Computes raw, mix-standardised,
    and fully-adjusted severity for a target portfolio.
    """
    candidates = [r for r in records
                  if r["data_quality_tag"] == "RELIABLE" and r["s_raw_a"] is not None
                  and r["lob_severity_computed"] and r["weight_source"] == "premium_mix"
                  and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
    # Identify syndicates excluded by the stricter candidate filters
    candidate_keys = {(r["syndicate"], r["year"]) for r in candidates}
    excluded = []
    for r in records:
        if (r["syndicate"], r["year"]) not in candidate_keys:
            reasons = []
            if r["data_quality_tag"] != "RELIABLE":
                reasons.append(f"data_quality={r['data_quality_tag']}")
            if r["s_raw_a"] is None:
                reasons.append("missing_severity")
            if not r["lob_severity_computed"]:
                reasons.append("no_lob_severity")
            if r["weight_source"] != "premium_mix":
                reasons.append(f"weight_source={r['weight_source']}")
            if r["opening_reserves_gbp_m"] is None or r["opening_reserves_gbp_m"] <= 0:
                reasons.append("missing_reserves")
            excluded.append({
                "syndicate": r["syndicate"],
                "year": r["year"],
                "reasons": reasons,
            })

    if len(candidates) < 2:
        return None

    # Group by year and pick the year with the most candidates
    from collections import defaultdict
    by_year = defaultdict(list)
    for r in candidates:
        by_year[r["year"]].append(r)

    # Pick the year with the widest reserve range among years with >= 5 syndicates
    best_year = None
    best_range = 0
    for yr, recs in by_year.items():
        if len(recs) < 5:
            continue
        recs_sorted = sorted(recs, key=lambda r: r["opening_reserves_gbp_m"])
        rng = recs_sorted[-1]["opening_reserves_gbp_m"] - recs_sorted[0]["opening_reserves_gbp_m"]
        if rng > best_range:
            best_range = rng
            best_year = yr

    if best_year is None:
        # Fallback: use all candidates regardless of year
        pool = candidates
        event_year = None
    else:
        pool = by_year[best_year]
        event_year = best_year

    pool.sort(key=lambda r: r["opening_reserves_gbp_m"])
    syn_a = pool[0]   # smallest
    syn_b = pool[-1]   # largest

    n_syndicates_in_event = len(pool)

    # Target portfolio: use the £500m property-heavy test portfolio
    target_tp = TEST_PORTFOLIOS[1]  # Prop-heavy £500m
    target_weights = portfolio_weights_vector(target_tp["weights"])
    tw_sum = target_weights.sum()
    if tw_sum > 0:
        target_weights = target_weights / tw_sum
    target_size = target_tp["size"]
    target_hhi = float(compute_hhi(target_weights))

    def syn_record(r):
        w = np.array(r["weights"], dtype=float)
        s_lob = np.array(r["lob_severity"], dtype=float)
        hhi_obs = float(compute_hhi(w))

        # Mix-standardised severity: project donor's LoB severities onto target weights
        s_mix = float(np.sum(target_weights * s_lob))

        # Size-adjustment factor
        adj_factor = dispersion_adjustment(target_size, target_hhi,
                                           r["opening_reserves_gbp_m"], hhi_obs)

        # Fully-adjusted severity
        s_adjusted = s_mix * adj_factor

        return {
            "syndicate": r["syndicate"],
            "year": r["year"],
            "reserves_m": r["opening_reserves_gbp_m"],
            "hhi": hhi_obs,
            "lob_weights": r["weights"],
            "s_lob": r["lob_severity"],
            "s_raw_a": r["s_raw_a"],
            "s_mix": s_mix,
            "size_adj_factor": adj_factor,
            "s_adjusted": s_adjusted,
            "pyd_gbp_m": r["pyd_gbp_m"],
            "pyd_pct": r["pyd_pct"],
            "direction": r["direction"],
        }

    return {
        "event_year": event_year,
        "n_syndicates_in_event": n_syndicates_in_event,
        "syndicate_a": syn_record(syn_a),
        "syndicate_b": syn_record(syn_b),
        "target_portfolio": {
            "name": target_tp["name"],
            "size_m": target_size,
            "hhi": target_hhi,
            "weights": {LOB_NAMES[i]: float(target_weights[i])
                        for i in range(N_LOBS) if target_weights[i] > 0},
            "weights_vector": target_weights.tolist(),
        },
        "lob_coefficients": {name: LOB_BETA_COEFFICIENTS.get(name, OVERALL_BETA_DEFAULT) for name in LOB_NAMES},
        "reference_size_m": REFERENCE_SIZE,
        "lob_names": LOB_NAMES,
        "excluded_syndicates": [e for e in excluded if e["year"] == event_year] if event_year else excluded,
        "n_total_in_year": len([r for r in records if r["year"] == event_year]) if event_year else len(records),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def compute_diagnostics(counters, records):
    """Compile diagnostic counters."""
    n_kept = len(records)
    total = counters["total_files"]

    sign_flip_pct = (counters["sign_flips"] / n_kept * 100) if n_kept > 0 else 0
    cap_total = counters["cap_binding_pos"] + counters["cap_binding_neg"]
    cap_pct = (cap_total / n_kept * 100) if n_kept > 0 else 0
    lob_floor_pct = (counters["lob_floor_count"] / n_kept * 100) if n_kept > 0 else 0

    diagnostics = {
        "sign_flips": counters["sign_flips"],
        "sign_flip_pct": round(sign_flip_pct, 2),
        "sign_flip_warning": sign_flip_pct > 5.0,
        "cap_binding": {
            "pos": counters["cap_binding_pos"],
            "neg": counters["cap_binding_neg"],
            "pct": round(cap_pct, 2),
            "by_year": dict(counters["cap_binding_by_year"]),
        },
        "lob_floor": {
            "count": counters["lob_floor_count"],
            "pct": round(lob_floor_pct, 2),
            "by_year": dict(counters["lob_floor_by_year"]),
        },
        "no_reserves_filtered": counters["no_reserves"],
        "reserve_source_dist": dict(counters["reserve_source_dist"]),
        "weight_source_dist": dict(counters["weight_source_dist"]),
        "proportional_allocation_count": counters["proportional_allocation_count"],
        "yearly_observation_counts": dict(sorted(Counter(r["year"] for r in records).items())),
    }

    near_zero_pyd = []
    for r in records:
        if r.get("pyd_pct") is not None and abs(r["pyd_pct"]) < 0.05:
            near_zero_pyd.append({
                "syndicate": r["syndicate"],
                "year": r["year"],
                "pyd_pct": r["pyd_pct"],
                "pyd_gbp_m": r.get("pyd_gbp_m"),
                "opening_reserves_gbp_m": r.get("opening_reserves_gbp_m"),
                "direction": r.get("direction"),
                "data_quality_tag": r.get("data_quality_tag"),
            })
    diagnostics["near_zero_pyd"] = near_zero_pyd
    diagnostics["near_zero_pyd_count"] = len(near_zero_pyd)

    # Single-LoB reporters (HHI ≥ 0.99) — excluded from HHI analysis
    single_lob_records = []
    for r in records:
        if r.get("hhi") is not None and r["hhi"] >= 0.99:
            # Identify which LoB got all the weight
            weights = r.get("weights", [])
            dominant_lob = None
            for i, w in enumerate(weights):
                if w > 0.5 and i < len(LOB_NAMES):
                    dominant_lob = LOB_NAMES[i]
                    break
            # Count raw LoB entries from extraction
            gpm = r.get("gross_premium_mix", [])
            n_gpm_entries = len(gpm) if gpm else 0
            single_lob_records.append({
                "syndicate": r["syndicate"],
                "year": r["year"],
                "hhi": r["hhi"],
                "opening_reserves_gbp_m": r.get("opening_reserves_gbp_m"),
                "pyd_pct": r.get("pyd_pct"),
                "weight_source": r.get("weight_source"),
                "dominant_lob": dominant_lob,
                "n_extracted_entries": n_gpm_entries,
                "data_quality_tag": r.get("data_quality_tag"),
            })
    diagnostics["single_lob_records"] = single_lob_records
    diagnostics["single_lob_count"] = len(single_lob_records)

    if sign_flip_pct > 5.0:
        log(f"  WARNING: Sign flip rate {sign_flip_pct:.1f}% exceeds 5% threshold")

    return diagnostics


# ─────────────────────────────────────────────────────────────────────────────
# Observations table
# ─────────────────────────────────────────────────────────────────────────────

def build_observations(records):
    """Build compact observations array for output."""
    obs = []
    for r in records:
        obs.append({
            "syndicate": r["syndicate"],
            "year": r["year"],
            "opening_reserves_gbp_m": r["opening_reserves_gbp_m"],
            "pyd_gbp_m": r["pyd_gbp_m"],
            "pyd_pct": r["pyd_pct"],
            "direction": r["direction"],
            "gpw_gbp_m": r["gpw_gbp_m"],
            "s_raw_a": r["s_raw_a"],
            "s_raw_b": r["s_raw_b"],
            "hhi": r["hhi"],
            "diversification": r["diversification"],
            "complexity": r["complexity"],
            "cause_category": r["cause_category"],
            "event_group_id": r.get("event_group_id"),
            "data_quality_tag": r["data_quality_tag"],
            "pyd_basis": r["pyd_basis"],
            "pyd_basis_source": r["pyd_basis_source"],
            "weight_source": r["weight_source"],
            "weights": r["weights"],
            "confidence": r["confidence"],
            "sign_flipped": r["sign_flipped"],
            "report_currency": r["report_currency"],
            "fx_applied": r["fx_applied"],
            "fx_rate_usd_per_gbp": r["fx_rate_usd_per_gbp"],
            "fx_rate_date": r["fx_rate_date"],
        })
    return obs


# ─────────────────────────────────────────────────────────────────────────────
# Paper-pack generation (LaTeX tables + matplotlib figures)
# ─────────────────────────────────────────────────────────────────────────────

_PP_RAW_COL   = '#2166ac'
_PP_STD_COL   = '#b2182b'
_PP_FAV_COL   = '#27ae60'
_PP_ADV_COL   = '#e74c3c'
_PP_DPI       = 150


def _pp_dir() -> Path:
    d = SCRIPT_DIR / "paper_pack"
    d.mkdir(exist_ok=True)
    return d


def _sig_stars(p):
    """Return significance marker string."""
    if p is None:
        return ""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "\\dag"
    return ""


def _fmt(v, fmt=".2f"):
    """Safely format a numeric value."""
    if v is None:
        return "--"
    try:
        return f"{float(v):{fmt}}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v, decimals=1):
    if v is None:
        return "--"
    try:
        return f"{float(v):.{decimals}f}\\%"
    except (TypeError, ValueError):
        return str(v)


def _fmt_gbp(v, decimals=1):
    if v is None:
        return "--"
    try:
        return f"\\pounds{float(v):,.{decimals}f}m"
    except (TypeError, ValueError):
        return str(v)


def _wrap_table(body: str, caption: str, label: str, colspec: str) -> str:
    return (
        "\\begin{table}[htbp]\n"
        "\\centering\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{tab:{label}}}\n"
        f"\\begin{{tabular}}{{{colspec}}}\n"
        "\\toprule\n"
        f"{body}"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )


def _write_tex(fname: str, content: str):
    path = _pp_dir() / fname
    path.write_text(content, encoding="utf-8")


def _safe_get(d, *keys, default=None):
    """Nested dict access with default."""
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        else:
            return default
    return cur


# ── Table generators ─────────────────────────────────────────────────────────

def _gen_table1(results):
    meta = results.get("meta", {})
    subs = results.get("subsets", {})
    dense = subs.get("DENSE", {})
    mid = subs.get("MID", {})
    bal = subs.get("BALANCED_K8", {})

    years = meta.get("years_covered", [])
    yr_str = f"{min(years)}--{max(years)}" if years else "--"
    dense_spy = _safe_get(dense, "syndicates_per_year", default={})
    mid_spy = _safe_get(mid, "syndicates_per_year", default={})

    rows = [
        ("Years covered", yr_str),
        ("Total observations", _fmt(meta.get("total_observations"), ",.0f")),
        ("Unique syndicates", _fmt(meta.get("unique_syndicates"), ",.0f")),
        ("Syndicates/year (dense)", f"{_fmt(dense_spy.get('min'),'.0f')}--{_fmt(dense_spy.get('max'),'.0f')} (med {_fmt(dense_spy.get('median'),'.0f')})"),
        ("Syndicates/year (mid)", f"{_fmt(mid_spy.get('min'),'.0f')}--{_fmt(mid_spy.get('max'),'.0f')} (med {_fmt(mid_spy.get('median'),'.0f')})"),
        ("Balanced-panel syndicates", _fmt(_safe_get(bal, "n_syndicates"), ".0f")),
        ("Median reserves", _fmt_gbp(meta.get("median_reserves"))),
        ("LoB categories", _fmt(len(meta.get("lob_categories", LOB_NAMES)), ".0f")),
    ]
    body = " & ".join(["\\textbf{Metric}", "\\textbf{Value}"]) + " \\\\\n\\midrule\n"
    for m, v in rows:
        body += f"{m} & {v} \\\\\n"
    _write_tex("table1_corpus_coverage.tex", _wrap_table(body, "Corpus coverage summary", "corpus_coverage", "lr"))


def _gen_table2(results):
    samp = _safe_get(results, "robustness", "sampling", default={})
    rows_data = [
        ("$p_{95}$ trend slope", samp.get("p95_slope", {})),
        ("Size elasticity $\\beta$", samp.get("beta", {})),
        ("VaR$_{99.5\\%}$", samp.get("var_995", {})),
    ]
    body = "\\textbf{Metric} & \\textbf{Estimate} & \\textbf{CV (\\%)} & \\textbf{Stability} \\\\\n\\midrule\n"
    for label, d in rows_data:
        est = _fmt(d.get("estimate"), ".4f")
        lo_cv = _fmt(_safe_get(d, "leave_out_cv"), ".2f")
        bo_cv = _fmt(_safe_get(d, "boot_cv"), ".2f")
        cv_str = f"{lo_cv} / {bo_cv}"
        stab = d.get("stability", "--")
        body += f"{label} & {est} & {cv_str} & {stab} \\\\\n"
    _write_tex("table2_sampling_sensitivity.tex",
               _wrap_table(body, "Sampling sensitivity analysis", "sampling_sensitivity", "lrrl"))


def _gen_table3(results):
    primary = _safe_get(results, "size_scaling", "primary", default={})
    freq = _safe_get(results, "size_scaling", "frequentist_comparison", default=[])

    def _spec_row(label, beta, se, p_v, notes):
        return (f"{label} & {_fmt(beta,'.4f')}{_sig_stars(p_v)} "
                f"& {_fmt(se,'.4f')} & {_fmt(p_v,'.4f')} & {notes} \\\\\n")

    # Build lookup from spec name to entry
    freq_by_name = {s.get("spec", ""): s for s in freq}

    # Total n from primary estimator (DENSE subset with reserves > 5)
    n_dense = _fmt(primary.get("n"), ".0f")
    n_syndicates = _fmt(primary.get("n_syndicates"), ".0f")

    body = "\\textbf{Specification} & $\\hat{\\beta}$ & \\textbf{Std.\\ err.} & \\textbf{$p$-value} & \\textbf{Notes} \\\\\n\\midrule\n"

    # Panel A: Signed mean-shift estimand
    body += "\\multicolumn{5}{l}{\\textbf{Panel A: Signed mean-shift estimand} ($S$ on $\\log R$)} \\\\\n\\midrule\n"
    p_val = primary.get("p_value")
    body += _spec_row("RE-GLS (signed PYD ratio)", primary.get("beta"), primary.get("se"), p_val,
                      f"$n={n_dense}$, {n_syndicates} syndicates")

    # M0 and M1 use same n as primary dense subset
    for spec_name, notes in [("Mean shift (OLS, no controls)", f"$n={n_dense}$"),
                              ("Mean shift (OLS + event FE)", f"$n={n_dense}$"),
                              ("Mean shift (balanced panel)", "balanced subset")]:
        s = freq_by_name.get(spec_name, {})
        if s:
            body += _spec_row(spec_name, s.get("beta"), s.get("se"), s.get("p_value"), notes)

    # Panel B: Dispersion estimands
    body += "\\midrule\n"
    body += "\\multicolumn{5}{l}{\\textbf{Panel B: Dispersion estimands}} \\\\\n\\midrule\n"

    panel_b = [("Absolute severity (log-scale)", "Log absolute severity ($\\log |S|$)", "primary dispersion specification"),
               ("Severity variance (log-scale)", "Log squared severity ($\\log S^2$)", "supplementary scale specification")]
    for old_name, new_label, notes in panel_b:
        s = freq_by_name.get(old_name, {})
        if s:
            body += _spec_row(new_label, s.get("beta"), s.get("se"), s.get("p_value"), notes)

    _write_tex("table3_size_severity.tex",
               _wrap_table(body, "Size effects under alternative reserve-movement estimands", "size_severity", "lrrrp{4cm}"))


def _gen_table4(results):
    ports = _safe_get(results, "capital_impact", "portfolios", default=[])
    body = ("\\textbf{Portfolio} & \\textbf{Raw} & \\textbf{Mix-adj.} & "
            "\\textbf{Full adj.} & \\textbf{Mix effect} & \\textbf{Size effect} \\\\\n\\midrule\n")
    for p in ports:
        raw = _safe_get(p, "naive", "var_995", default=None)
        mix = _safe_get(p, "concentration_only", "var_995", default=None)
        full = _safe_get(p, "full", "var_995", default=None)
        mix_eff = (float(mix) - float(raw)) if (mix is not None and raw is not None) else None
        size_eff = (float(full) - float(mix)) if (full is not None and mix is not None) else None
        body += (f"{p.get('name','--')} & {_fmt(raw,'.4f')} & {_fmt(mix,'.4f')} & "
                 f"{_fmt(full,'.4f')} & {_fmt(mix_eff,'.4f')} & {_fmt(size_eff,'.4f')} \\\\\n")
    _write_tex("table4_var_decomposition.tex",
               _wrap_table(body, "VaR$_{99.5\\%}$ decomposition by portfolio", "var_decomposition", "lrrrrr"))


def _gen_table5(results):
    we = results.get("worked_example", {})
    if not we:
        return
    sa = we.get("syndicate_a", {})
    sb = we.get("syndicate_b", {})
    tp = we.get("target_portfolio", {})
    lob_names = we.get("lob_names", LOB_NAMES)
    event_year = we.get("event_year")
    n_syn = we.get("n_syndicates_in_event")

    # Panel A: Event identification
    body = "\\multicolumn{3}{l}{\\textbf{Panel A: Event identification}} \\\\\n\\midrule\n"
    body += f"Event year & \\multicolumn{{2}}{{l}}{{{event_year or '--'}}} \\\\\n"
    n_total = we.get("n_total_in_year")
    excl = we.get("excluded_syndicates", [])
    if n_total and n_total != n_syn:
        body += f"Syndicates observed & \\multicolumn{{2}}{{l}}{{{n_syn} of {n_total}\\textsuperscript{{a}}}} \\\\\n"
    else:
        body += f"Syndicates observed & \\multicolumn{{2}}{{l}}{{{n_syn or '--'}}} \\\\\n"
    body += "\\midrule\n"

    # Panel B: Source syndicates
    body += "\\multicolumn{3}{l}{\\textbf{Panel B: Source syndicates}} \\\\\n\\midrule\n"
    body += " & \\textbf{Syndicate A} & \\textbf{Syndicate B} \\\\\n\\midrule\n"
    body += f"Syndicate & {sa.get('syndicate','--')} & {sb.get('syndicate','--')} \\\\\n"
    body += f"Reserves (\\pounds m) & {_fmt(sa.get('reserves_m'),'.1f')} & {_fmt(sb.get('reserves_m'),'.1f')} \\\\\n"
    body += f"HHI & {_fmt(sa.get('hhi'),'.3f')} & {_fmt(sb.get('hhi'),'.3f')} \\\\\n"

    # LoB weights (only non-zero rows)
    w_a = sa.get("lob_weights", [])
    w_b = sb.get("lob_weights", [])
    for i, name in enumerate(lob_names):
        wa_v = w_a[i] if i < len(w_a) else 0
        wb_v = w_b[i] if i < len(w_b) else 0
        if wa_v > 0.005 or wb_v > 0.005:
            body += f"  $w$ {name} & {_fmt(wa_v, '.3f')} & {_fmt(wb_v, '.3f')} \\\\\n"

    # LoB-level severities (only non-zero rows)
    body += "\\midrule\n"
    s_a = sa.get("s_lob", [])
    s_b = sb.get("s_lob", [])
    for i, name in enumerate(lob_names):
        sa_v = s_a[i] if i < len(s_a) else 0
        sb_v = s_b[i] if i < len(s_b) else 0
        wa_v = w_a[i] if i < len(w_a) else 0
        wb_v = w_b[i] if i < len(w_b) else 0
        if wa_v > 0.005 or wb_v > 0.005:
            body += f"  $s_\\ell$ {name} & {_fmt(sa_v, '.4f')} & {_fmt(sb_v, '.4f')} \\\\\n"

    body += "\\midrule\n"
    body += f"$S^{{\\mathrm{{raw}}}}$ & {_fmt(sa.get('s_raw_a'),'.4f')} & {_fmt(sb.get('s_raw_a'),'.4f')} \\\\\n"
    body += f"PYD (\\%) & {_fmt_pct(sa.get('pyd_pct'))} & {_fmt_pct(sb.get('pyd_pct'))} \\\\\n"
    body += f"Direction & {sa.get('direction','--')} & {sb.get('direction','--')} \\\\\n"

    # Panel C: Target portfolio
    body += "\\midrule\n"
    body += "\\multicolumn{3}{l}{\\textbf{Panel C: Target portfolio}} \\\\\n\\midrule\n"
    tp_name = tp.get("name", "--")
    body += f"Portfolio & \\multicolumn{{2}}{{l}}{{{tp_name}}} \\\\\n"
    body += f"Target size (\\pounds m) & \\multicolumn{{2}}{{l}}{{{_fmt(tp.get('size_m'),'.0f')}}} \\\\\n"
    body += f"Target HHI & \\multicolumn{{2}}{{l}}{{{_fmt(tp.get('hhi'),'.3f')}}} \\\\\n"
    tp_w = tp.get("weights", {})
    for lob_name, wt in tp_w.items():
        if wt > 0.005:
            body += f"  $w^q$ {lob_name} & \\multicolumn{{2}}{{l}}{{{_fmt(wt, '.3f')}}} \\\\\n"

    # Build footnote listing excluded syndicates and reasons
    footnote = ""
    if excl:
        reason_map = {
            "data_quality=INCOMPLETE": "incomplete data",
            "missing_severity": "missing severity",
            "no_lob_severity": "no LoB severity",
            "missing_reserves": "missing reserves",
        }
        parts = []
        for e in excl:
            reasons_nice = []
            for reason in e["reasons"]:
                if reason.startswith("weight_source="):
                    reasons_nice.append(f"weight source = {reason.split('=',1)[1]}")
                elif reason.startswith("data_quality="):
                    reasons_nice.append(reason_map.get(reason, reason.split('=',1)[1]))
                else:
                    reasons_nice.append(reason_map.get(reason, reason))
            parts.append(f"{e['syndicate']} ({', '.join(reasons_nice)})")
        footnote = (
            "\\vspace{2pt}\\par\\noindent\\textsuperscript{a}\\footnotesize "
            f"{n_total - n_syn} syndicates excluded: {'; '.join(parts)}.\n"
        )

    tex = _wrap_table(body, "Worked example --- event detail", "worked_example_event", "lrr")
    if footnote:
        # Insert footnote before \end{table}
        tex = tex.replace("\\end{table}\n", footnote + "\\end{table}\n")
    _write_tex("table5_worked_example_event.tex", tex)


def _gen_table6(results):
    we = results.get("worked_example", {})
    if not we:
        return
    sa = we.get("syndicate_a", {})
    sb = we.get("syndicate_b", {})

    body = " & \\textbf{Syndicate A} & \\textbf{Syndicate B} \\\\\n\\midrule\n"
    body += f"$S^{{\\mathrm{{raw}}}}$ (portfolio-level) & {_fmt(sa.get('s_raw_a'),'.4f')} & {_fmt(sb.get('s_raw_a'),'.4f')} \\\\\n"
    body += f"$S^{{\\mathrm{{mix}}}}$ (mix-standardised) & {_fmt(sa.get('s_mix'),'.4f')} & {_fmt(sb.get('s_mix'),'.4f')} \\\\\n"
    body += f"Size-adjustment factor $\\lambda$ & {_fmt(sa.get('size_adj_factor'),'.4f')} & {_fmt(sb.get('size_adj_factor'),'.4f')} \\\\\n"
    body += f"$S^{{\\mathrm{{adj}}}}$ (fully adjusted) & {_fmt(sa.get('s_adjusted'),'.4f')} & {_fmt(sb.get('s_adjusted'),'.4f')} \\\\\n"

    _write_tex("table6_worked_example_summary.tex",
               _wrap_table(body, "Worked example --- adjustment summary", "worked_example_summary", "lrr"))


def _gen_table7(results):
    personas = results.get("personas", {})
    persona_order = ["typical", "small", "large", "diversified", "undiversified"]

    for variant in ("raw", "standardised"):
        body = ("\\textbf{Persona} & $n$ & \\textbf{Mean} & \\textbf{Median} & "
                "\\textbf{Std} & $p_{10}$ & $p_{90}$ & $p_{99.5}$ \\\\\n\\midrule\n")
        for pk in persona_order:
            pd_ = _safe_get(personas, pk, "market_pyd_stats", variant, default={})
            body += (f"{pk.title()} & {_fmt(pd_.get('n'),'.0f')} & {_fmt(pd_.get('mean'),'.4f')} & "
                     f"{_fmt(pd_.get('median'),'.4f')} & {_fmt(pd_.get('std'),'.4f')} & "
                     f"{_fmt(pd_.get('p10'),'.4f')} & {_fmt(pd_.get('p90'),'.4f')} & "
                     f"{_fmt(pd_.get('p995'),'.4f')} \\\\\n")
        cap = f"Persona PYD\\% summary statistics ({variant})"
        lbl = f"persona_pyd_{variant}"
        _write_tex(f"table7_persona_pyd_stats_{variant}.tex",
                   _wrap_table(body, cap, lbl, "lrrrrrrr"))


def _gen_table8(results):
    personas = results.get("personas", {})
    persona_order = ["typical", "small", "large", "diversified", "undiversified"]
    # Attempt to discover keys from first persona with tail_diagnostics
    sample_td = None
    for pk in persona_order:
        sample_td = _safe_get(personas, pk, "tail_diagnostics", default=None)
        if sample_td and isinstance(sample_td, dict):
            break
    if not sample_td:
        _write_tex("table8_persona_tail_diagnostics.tex",
                   "% No persona tail diagnostics data available.\n")
        return

    keys = list(sample_td.keys()) if isinstance(sample_td, dict) else []
    header = "\\textbf{Persona}"
    for k in keys:
        header += f" & \\textbf{{{k.replace('_',' ')}}}"
    header += " \\\\\n\\midrule\n"
    body = header
    for pk in persona_order:
        td = _safe_get(personas, pk, "tail_diagnostics", default={})
        row = pk.title()
        for k in keys:
            row += f" & {_fmt(td.get(k),'.4f')}"
        body += row + " \\\\\n"
    ncols = "l" + "r" * len(keys)
    _write_tex("table8_persona_tail_diagnostics.tex",
               _wrap_table(body, "Persona tail diagnostics", "persona_tail_diag", ncols))


def _gen_table9(results):
    subs = results.get("subsets", {})
    body = "\\textbf{Subset} & \\textbf{Obs.} & \\textbf{Syndicates} & \\textbf{Year range} \\\\\n\\midrule\n"
    for name, info in subs.items():
        yr = info.get("year_range", [])
        yr_str = f"{yr[0]}--{yr[1]}" if isinstance(yr, (list, tuple)) and len(yr) >= 2 else str(yr)
        body += (f"{name} & {_fmt(info.get('n_observations'),'.0f')} & "
                 f"{_fmt(info.get('n_syndicates'),'.0f')} & {yr_str} \\\\\n")
    _write_tex("table9_corpus_summary.tex",
               _wrap_table(body, "Corpus subsets summary", "corpus_summary", "lrrr"))


def _gen_table10(results):
    meta = results.get("meta", {})
    kept = _safe_get(meta, "kept", "count", default=0)
    disc = _safe_get(meta, "discarded", default={})
    disc_count = disc.get("count", 0)
    total = kept + disc_count if kept and disc_count else meta.get("total_files", 0)
    reasons = disc.get("reasons", {})
    body = "\\textbf{Category} & \\textbf{Count} & \\textbf{\\%} \\\\\n\\midrule\n"
    pct_k = (kept / total * 100) if total else 0
    body += f"Kept & {kept} & {_fmt(pct_k,'.1f')}\\% \\\\\n"
    pct_d = (disc_count / total * 100) if total else 0
    body += f"Discarded (total) & {disc_count} & {_fmt(pct_d,'.1f')}\\% \\\\\n"
    for reason, cnt in reasons.items():
        pct_r = (cnt / total * 100) if total else 0
        body += f"\\quad {reason.replace('_',' ')} & {cnt} & {_fmt(pct_r,'.1f')}\\% \\\\\n"
    _write_tex("table10_data_quality.tex",
               _wrap_table(body, "Data quality breakdown", "data_quality", "lrr"))


def _gen_table11(results):
    stats = _safe_get(results, "distribution", "stats", default={})
    if not stats:
        stats = _safe_get(results, "meta", "reserve_histogram", "stats", default={})
    rows = [
        ("Min", _fmt_gbp(stats.get("min"))),
        ("Max", _fmt_gbp(stats.get("max"))),
        ("Mean", _fmt_gbp(stats.get("mean"))),
        ("Median", _fmt_gbp(stats.get("median"))),
        ("Std dev", _fmt_gbp(stats.get("std"))),
        ("Skewness", _fmt(stats.get("skewness"), ".2f")),
        ("$p_{10}$", _fmt_gbp(stats.get("p10"))),
        ("$p_{90}$", _fmt_gbp(stats.get("p90"))),
    ]
    body = "\\textbf{Statistic} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table11_reserves_distribution.tex",
               _wrap_table(body, "Opening reserves distribution", "reserves_dist", "lr"))


def _gen_table12(results):
    bp = _safe_get(results, "distribution", "boxplots", default={})
    body = "\\textbf{Grouping} & \\textbf{Groups} & \\textbf{Notes} \\\\\n\\midrule\n"
    for key in ("by_reserves_decile", "by_hhi_decile", "by_complexity_decile"):
        data = bp.get(key, [])
        n_groups = len(data) if isinstance(data, list) else "--"
        body += f"{key.replace('_',' ').replace('by ','').title()} & {n_groups} & See figures \\\\\n"
    _write_tex("table12_decile_tests.tex",
               _wrap_table(body, "Decile grouping summary", "decile_tests", "lrl"))


def _gen_table13(results):
    primary = _safe_get(results, "size_scaling", "primary", default={})
    ci = primary.get("ci_95", [None, None])
    ci_lo = ci[0] if isinstance(ci, (list, tuple)) and len(ci) >= 2 else None
    ci_hi = ci[1] if isinstance(ci, (list, tuple)) and len(ci) >= 2 else None
    rows = [
        ("$\\hat{\\beta}$", _fmt(primary.get("beta"), ".4f")),
        ("Std.\\ error", _fmt(primary.get("se"), ".4f")),
        ("$p$-value", _fmt(primary.get("p_value"), ".4f")),
        ("95\\% CI lower", _fmt(ci_lo, ".4f")),
        ("95\\% CI upper", _fmt(ci_hi, ".4f")),
        ("$n$ (obs)", _fmt(primary.get("n"), ".0f")),
        ("$n$ (syndicates)", _fmt(primary.get("n_syndicates"), ".0f")),
    ]
    body = "\\textbf{Parameter} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table13_primary_re_gls.tex",
               _wrap_table(body, "Primary RE-GLS estimator", "primary_re_gls", "lr"))


def _gen_table14(results):
    freq = _safe_get(results, "size_scaling", "frequentist_comparison", default=[])
    disp_specs = [s for s in freq if s.get("spec", "") in ("M2", "M3")]
    body = ("\\textbf{Spec} & $\\hat{\\beta}$ & \\textbf{Std.\\ err.} & "
            "\\textbf{$p$-value} & \\textbf{AIC} & \\textbf{BIC} \\\\\n\\midrule\n")
    labels = {"M2": "Absolute severity (log)", "M3": "Severity variance (log)"}
    for s in disp_specs:
        p_v = s.get("p_value")
        body += (f"{labels.get(s.get('spec',''), s.get('spec',''))} & "
                 f"{_fmt(s.get('beta'),'.4f')}{_sig_stars(p_v)} & "
                 f"{_fmt(s.get('se'),'.4f')} & {_fmt(p_v,'.4f')} & "
                 f"{_fmt(s.get('aic'),'.1f')} & {_fmt(s.get('bic'),'.1f')} \\\\\n")
    if not disp_specs:
        body += "\\multicolumn{6}{c}{No dispersion model specs available} \\\\\n"
    _write_tex("table14_dispersion_models.tex",
               _wrap_table(body, "Dispersion model specifications", "dispersion_models", "lrrrrr"))


def _gen_table15(results):
    direction = _safe_get(results, "exposure_composition", "hhi_scatter", "direction", default={})
    rows = [
        ("$\\hat{\\beta}$ (HHI direction)", _fmt(direction.get("beta"), ".4f")),
        ("Std.\\ error", _fmt(direction.get("se"), ".4f")),
        ("$p$-value", f"{_fmt(direction.get('p_value'),'.4f')}{_sig_stars(direction.get('p_value'))}"),
    ]
    body = "\\textbf{Parameter} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table15_direction_test.tex",
               _wrap_table(body, "HHI direction test", "direction_test", "lr"))


def _gen_table16(results):
    sh = _safe_get(results, "exposure_composition", "dispersion_models", "single_h", default={})
    rows = [
        ("$A$", _fmt(sh.get("A"), ".4f")),
        ("$B$", _fmt(sh.get("B"), ".4f")),
        ("$C$", _fmt(sh.get("C"), ".4f")),
        ("$R^2$", _fmt(sh.get("r_squared"), ".4f")),
    ]
    body = "\\textbf{Parameter} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table16_power_law_hhi.tex",
               _wrap_table(body, "Power-law HHI dispersion ($\\sigma^2 = A + B \\cdot \\mathrm{HHI}^C$)", "power_law_hhi", "lr"))


def _gen_table17(results):
    corr = _safe_get(results, "joint_composition", "hhi_r_correlation", default={})
    rows = [
        ("Pearson $r$", _fmt(corr.get("pearson_r"), ".4f")),
        ("Spearman $r$", _fmt(corr.get("spearman_r"), ".4f")),
        ("$p$ (Pearson)", f"{_fmt(corr.get('p_pearson'),'.4f')}{_sig_stars(corr.get('p_pearson'))}"),
        ("$p$ (Spearman)", f"{_fmt(corr.get('p_spearman'),'.4f')}{_sig_stars(corr.get('p_spearman'))}"),
        ("$n$", _fmt(corr.get("n"), ".0f")),
    ]
    body = "\\textbf{Metric} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table17_correlation.tex",
               _wrap_table(body, "Diversification vs.\\ reserve size correlation", "correlation", "lr"))


def _gen_table18(results):
    va = _safe_get(results, "joint_composition", "variance_attribution", default={})
    rows = [
        ("Raw $\\sigma^2$", _fmt(va.get("var_raw_sq"), ".6f")),
        ("After size adjustment", _fmt(va.get("var_after_size_adj"), ".6f")),
        ("\\% explained by size", _fmt_pct(va.get("pct_explained_by_size"))),
        ("After HHI adjustment", _fmt(va.get("var_after_hhi_adj"), ".6f")),
        ("\\% explained by HHI", _fmt_pct(va.get("pct_explained_by_hhi"))),
    ]
    body = "\\textbf{Stage} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table18_variance_attribution.tex",
               _wrap_table(body, "Variance attribution", "variance_attribution", "lr"))


def _gen_table19(results):
    dh = _safe_get(results, "joint_composition", "disp_h_adjusted", default={})
    rows = [
        ("$A$", _fmt(dh.get("A"), ".4f")),
        ("$B$", _fmt(dh.get("B"), ".4f")),
        ("$C$", _fmt(dh.get("C"), ".4f")),
        ("$R^2$", _fmt(dh.get("r_squared"), ".4f")),
    ]
    body = "\\textbf{Parameter} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table19_hhi_dispersion_adjusted.tex",
               _wrap_table(body, "HHI dispersion after size adjustment", "hhi_disp_adj", "lr"))


def _gen_table20(results):
    ritc_path = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
    cal_path = ritc_path if ritc_path.exists() else (SCRIPT_DIR / "model" / "dispersion_calibration.json")
    cal = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else {}
    has_ritc = cal.get("nu_clean") is not None
    body = "\\textbf{Parameter} & \\textbf{Value} \\\\\n\\midrule\n"
    body += f"Pooling exponent $k$ & {_fmt(cal.get('k'),'.4f')} \\\\\n"
    body += f"Concentration exponent $\\gamma$ & {_fmt(cal.get('gamma'),'.4f')} \\\\\n"
    body += f"Undiversifiable floor $\\sigma_{{\\text{{undiv}}}}$ & {_fmt(cal.get('sd_undiv'),'.4f')} \\\\\n"
    body += f"Diversifiable scale (reference) $\\sigma_{{\\text{{div}}}}$ & {_fmt(cal.get('sd_div'),'.4f')} \\\\\n"
    if has_ritc:
        body += f"Tail index $\\nu_{{\\text{{clean}}}}$ (clean) & {_fmt(cal.get('nu_clean'),'.3f')} \\\\\n"
        body += f"Tail index $\\nu_{{\\text{{RITC}}}}$ (RITC) & {_fmt(cal.get('nu_ritc'),'.3f')} \\\\\n"
    else:
        body += f"Tail index $\\nu$ & {_fmt(cal.get('nu'),'.3f')} \\\\\n"
    body += "\\midrule\n"
    op = ("$S_{\\mathrm{adj}} = \\sigma(R_t,H_t)\\,F^{-1}_{\\nu_t}(F_{\\nu_s}(S_{\\mathrm{src}}/\\sigma(R_s,H_s)))$ "
          "(shape-aware: $\\nu_s$ is the donor's regime and $\\nu_t$ the selected target "
          "regime --- a clean target de-RITCs RITC donors, an RITC-affected target maps "
          "clean donors into the heavier regime, and preserving each donor's regime "
          "makes the map the identity; nests the pure rescale when $\\nu_s=\\nu_t$)"
          if has_ritc else
          "$S_{\\mathrm{adj}} = S_{\\mathrm{src}}\\,\\sigma(R_t,H_t)/\\sigma(R_s,H_s)$")
    body += ("\\multicolumn{2}{p{11cm}}{Transfer operator (the fitted base scale "
             "law and tail indices, applied; the fitted RITC scale multiplier is "
             "deliberately omitted --- a measured $\\sim$3\\% simplification): "
             f"{op} with "
             "$\\sigma(R,H)=\\sqrt{\\sigma_{\\text{undiv}}^2+\\sigma_{\\text{div}}^2[(R/R_{\\text{ref}})(1/H)^{\\gamma}]^{2(k-1)}}$.} \\\\\n")
    rs = cal.get("reference_size")
    if rs is not None:
        body += f"\\multicolumn{{2}}{{l}}{{Reference size: {_fmt(rs,'.1f')}}} \\\\\n"
    _write_tex("table20_combined_model.tex",
               _wrap_table(body, "Dispersion scaling operator (robust Bayesian pooling)", "combined_model", "lr"))


def _gen_table4b(results):
    """VaR 99.5% decomposition by persona portfolio."""
    personas = results.get("personas", {})
    persona_order = ["typical", "small", "large", "diversified", "undiversified"]
    body = ("\\textbf{Persona} & \\textbf{Reserves} & \\textbf{HHI} & "
            "\\textbf{Raw} & \\textbf{Conc.-adj.} & "
            "\\textbf{Full adj.} & \\textbf{Conc. effect} & \\textbf{Size effect} \\\\\n\\midrule\n")
    for pname in persona_order:
        p = personas.get(pname, {})
        cap = p.get("capital", {})
        defn = p.get("definition", {})
        reserves = defn.get("reserves")
        hhi = defn.get("hhi")
        raw = _safe_get(cap, "naive", "var_995", default=None)
        mix = _safe_get(cap, "concentration_only", "var_995", default=None)
        full = _safe_get(cap, "full", "var_995", default=None)
        mix_eff = (float(mix) - float(raw)) if (mix is not None and raw is not None) else None
        size_eff = (float(full) - float(mix)) if (full is not None and mix is not None) else None
        body += (f"{pname.capitalize()} & {_fmt_gbp(reserves)} & {_fmt(hhi,'.3f')} & "
                 f"{_fmt(raw,'.4f')} & {_fmt(mix,'.4f')} & "
                 f"{_fmt(full,'.4f')} & {_fmt(mix_eff,'.4f')} & {_fmt(size_eff,'.4f')} \\\\\n")
    _write_tex("table4b_var_decomposition_personas.tex",
               _wrap_table(body, "VaR$_{99.5\\%}$ decomposition by persona portfolio",
                           "var_decomposition_personas", "lrrrrrr r"))


def _gen_table22(results):
    """Univariate model comparison: size-only vs HHI-only on raw s²."""
    uc = _safe_get(results, "joint_composition", "univariate_comparison", default={})
    if not uc:
        return
    rows = [
        ("$R^2$ (observation)", _fmt(uc.get("size_r2_obs"), ".4f"), _fmt(uc.get("hhi_r2_obs"), ".4f")),
        ("$R^2$ (vigintile means)", _fmt(uc.get("size_r2_binned"), ".4f"), _fmt(uc.get("hhi_r2_binned"), ".4f")),
        ("AIC", _fmt(uc.get("size_aic"), ".1f"), _fmt(uc.get("hhi_aic"), ".1f")),
        ("$p$ (LR test)", f"{_fmt(uc.get('size_p_C'),'.6f')}{_sig_stars(uc.get('size_p_C'))}",
         f"{_fmt(uc.get('hhi_p_C'),'.6f')}{_sig_stars(uc.get('hhi_p_C'))}"),
    ]
    body = "\\textbf{Metric} & \\textbf{Size model ($R$)} & \\textbf{HHI model} \\\\\n\\midrule\n"
    for label, v1, v2 in rows:
        body += f"{label} & {v1} & {v2} \\\\\n"
    body += "\\midrule\n"
    better = uc.get("better_univariate", "--")
    r2_diff = _fmt(uc.get("r2_difference"), ".4f")
    body += f"\\multicolumn{{3}}{{l}}{{Better univariate: \\textbf{{{better}}} ($\\Delta R^2 = {r2_diff}$)}} \\\\\n"
    _write_tex("table22_univariate_comparison.tex",
               _wrap_table(body, "Univariate model comparison: size vs.\\ HHI", "univariate_comparison", "lrr"))


def _gen_table23(results):
    """Variance attribution for HHI-first pipeline."""
    va = _safe_get(results, "joint_composition", "hhi_first", "variance_attribution", default={})
    if not va:
        return
    rows = [
        ("Raw $\\sigma^2$", _fmt(va.get("var_raw_sq"), ".6f")),
        ("After HHI adjustment", _fmt(va.get("var_after_hhi_adj"), ".6f")),
        ("\\% explained by HHI", _fmt_pct(va.get("pct_explained_by_hhi"))),
        ("After size adjustment", _fmt(va.get("var_after_size_adj"), ".6f")),
        ("\\% explained by size", _fmt_pct(va.get("pct_explained_by_size"))),
    ]
    body = "\\textbf{Stage} & \\textbf{Value} \\\\\n\\midrule\n"
    for label, val in rows:
        body += f"{label} & {val} \\\\\n"
    _write_tex("table23_variance_attribution_hhi_first.tex",
               _wrap_table(body, "Variance attribution (HHI-first pipeline)", "variance_attribution_hhi_first", "lr"))


def _gen_table24(results):
    """Pipeline ordering comparison and recommendation."""
    oc = _safe_get(results, "joint_composition", "ordering_comparison", default={})
    if not oc:
        return
    body = ("\\textbf{Pipeline} & \\textbf{Step 1 (\\%)} & \\textbf{Step 2 (\\%)} "
            "& \\textbf{Total (\\%)} \\\\\n\\midrule\n")
    body += (f"Size $\\to$ HHI & {_fmt_pct(oc.get('size_first_incremental_size'))} "
             f"& {_fmt_pct(oc.get('size_first_incremental_hhi'))} "
             f"& {_fmt_pct(oc.get('total_explained_size_first'))} \\\\\n")
    body += (f"HHI $\\to$ Size & {_fmt_pct(oc.get('hhi_first_incremental_hhi'))} "
             f"& {_fmt_pct(oc.get('hhi_first_incremental_size'))} "
             f"& {_fmt_pct(oc.get('total_explained_hhi_first'))} \\\\\n")
    body += "\\midrule\n"
    diff = oc.get("difference_pp")
    rec = oc.get("recommendation", "--")
    reason = oc.get("recommendation_reason", "")
    body += f"\\multicolumn{{4}}{{l}}{{Difference: {_fmt(abs(diff) if diff is not None else None, '.1f')} pp}} \\\\\n"
    body += f"\\multicolumn{{4}}{{l}}{{Recommendation: \\textbf{{{rec}}}}} \\\\\n"
    body += f"\\multicolumn{{4}}{{p{{12cm}}}}{{{reason}}} \\\\\n"
    _write_tex("table24_ordering_comparison.tex",
               _wrap_table(body, "Pipeline ordering comparison", "ordering_comparison", "lrrr"))


def _gen_table21(results):
    ports = _safe_get(results, "capital_impact", "portfolios", default=[])
    body = ("\\textbf{Portfolio} & \\textbf{Size} & \\textbf{HHI} & "
            "\\textbf{VaR$_{99\\%}$ (naive)} & \\textbf{VaR$_{99.5\\%}$ (naive)} & "
            "\\textbf{VaR$_{99\\%}$ (full)} & \\textbf{VaR$_{99.5\\%}$ (full)} \\\\\n\\midrule\n")
    for p in ports:
        name = p.get("name", "--")
        size = _fmt(p.get("size"), ".0f")
        # Compute HHI from target_weights if available
        tw = p.get("target_weights", {})
        if isinstance(tw, dict):
            hhi = sum(v * v for v in tw.values()) if tw else None
        else:
            hhi = sum(w * w for w in tw) if tw else None
        body += (f"{name} & {size} & {_fmt(hhi,'.4f')} & "
                 f"{_fmt(_safe_get(p,'naive','var_99'),'.4f')} & "
                 f"{_fmt(_safe_get(p,'naive','var_995'),'.4f')} & "
                 f"{_fmt(_safe_get(p,'full','var_99'),'.4f')} & "
                 f"{_fmt(_safe_get(p,'full','var_995'),'.4f')} \\\\\n")
    _write_tex("table21_test_portfolios.tex",
               _wrap_table(body, "Test portfolios and capital impact", "test_portfolios", "lrrrrrr"))


def _gen_table25(results):
    """Local-donor sensitivity: one table per £500m test portfolio."""
    ld = _safe_get(results, "robustness", "local_donor", default={})
    if not ld:
        return
    for port_key, rows_data in ld.items():
        if not isinstance(rows_data, list) or not rows_data:
            continue
        body = ("\\textbf{$h_{\\max}$} & \\textbf{$n$ donors} & "
                "\\textbf{VaR$_{99.5\\%}$ (raw)} & \\textbf{VaR$_{99.5\\%}$ (adj.)} \\\\\n\\midrule\n")
        for r in rows_data:
            h = _fmt(r.get("h_max"), ".2f")
            nd = _fmt(r.get("n_donors"), ".0f")
            raw = _fmt(r.get("var_995_raw"), ".4f") if r.get("var_995_raw") is not None else ("$<5$" if r.get("n_donors", 0) > 0 else "--")
            adj = _fmt(r.get("var_995_adjusted"), ".4f") if r.get("var_995_adjusted") is not None else ("$<5$" if r.get("n_donors", 0) > 0 else "--")
            body += f"{h} & {nd} & {raw} & {adj} \\\\\n"
        safe_key = port_key.lower().replace(" ", "_").replace("£", "").replace("—", "_")
        label = f"local_donor_{safe_key}"
        caption = f"Local-donor sensitivity: {port_key}"
        _write_tex(f"table25_local_donor_{safe_key}.tex",
                   _wrap_table(body, caption, label, "rrrr"))


# ── Figure generators ────────────────────────────────────────────────────────

def _setup_ax(ax, xlabel="", ylabel="", title=""):
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    if title:
        ax.set_title(title, fontsize=13)
    ax.tick_params(labelsize=10)
    ax.grid(True, alpha=0.3)


def _save_fig(fig, fname):
    path = _pp_dir() / fname
    fig.tight_layout()
    fig.savefig(str(path), dpi=_PP_DPI, bbox_inches='tight')
    plt.close(fig)


def _gen_fig_yearly_observations(results):
    """Bar chart of observation counts per year."""
    yobs = _safe_get(results, "meta", "yearly_observations", default={})
    if not yobs:
        yobs = _safe_get(results, "data_quality", "yearly_observation_counts", default={})
    if not yobs:
        return
    years = sorted(yobs.keys())
    year_ints = [int(y) for y in years]
    counts = [yobs[y] for y in years]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(year_ints, counts, color=_PP_RAW_COL)
    ax.set_ylim(bottom=0)
    ax.set_xticks(year_ints)
    for yi, c in zip(year_ints, counts):
        ax.text(yi, c + 0.5, str(c), ha='center', va='bottom', fontsize=9)
    _setup_ax(ax, "", "Observation Count", "Yearly Observation Count")
    _save_fig(fig, "fig_yearly_observations.png")


def _gen_fig2(results):
    """p95 trend lines (raw and standardised) with regressions."""
    tt = results.get("tail_trends", {})
    fig, ax = plt.subplots(figsize=(10, 6))

    for variant, color, label in [("raw", _PP_RAW_COL, "Raw"), ("standardised", _PP_STD_COL, "Standardised")]:
        annual = _safe_get(tt, "annual_p95", variant, default=[])
        if not annual:
            continue
        years = [d["year"] for d in annual]
        vals = [d["value"] for d in annual]
        ax.plot(years, vals, 'o-', color=color, label=label, markersize=5)

        reg = _safe_get(tt, "regression", variant, default={})
        if reg.get("slope") is not None and reg.get("intercept") is not None:
            xs = np.array(years, dtype=float)
            ys = reg["intercept"] + reg["slope"] * xs
            ax.plot(xs, ys, '--', color=color, alpha=0.7,
                    label=f"{label} trend (slope={reg['slope']:.4f})")

    _setup_ax(ax, "Year", "$p_{95}$ severity", "95th-percentile severity trends")
    ax.legend(fontsize=10)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _save_fig(fig, "fig2_p95_trends.png")


def _gen_fig3(results):
    """Mean-excess plot."""
    td = results.get("tail_diagnostics", {})
    fig, ax = plt.subplots(figsize=(10, 6))

    for variant, color, label in [("raw", _PP_RAW_COL, "Raw"), ("standardised", _PP_STD_COL, "Standardised")]:
        me = _safe_get(td, "mean_excess", variant, default={})
        if not me:
            me_list = td.get(variant, [])
            if isinstance(me_list, list) and me_list:
                thresh = [d.get("threshold", 0) for d in me_list]
                vals = [d.get("mean_excess", 0) for d in me_list]
            else:
                continue
        else:
            thresh = me.get("thresholds", [])
            vals = me.get("values", [])
        if thresh and vals:
            ax.plot(thresh, vals, 'o-', color=color, label=label, markersize=4)

    _setup_ax(ax, "Threshold", "Mean excess", "Mean-excess function")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig3_mean_excess.png")


def _gen_fig4(results):
    """Size-severity log-log scatter."""
    ss = results.get("size_scaling", {})
    scatter = ss.get("scatter_data", {})
    points = scatter.get("points", [])
    fig, ax = plt.subplots(figsize=(10, 6))

    if points:
        xs = [p.get("x", p.get("log_reserves", 0)) for p in points]
        ys = [p.get("y", p.get("severity", 0)) for p in points]
        ax.scatter(xs, ys, alpha=0.3, s=15, color=_PP_RAW_COL, label="Observations")

        reg_line = scatter.get("regression_line", {})
        if reg_line:
            rx = reg_line.get("x", [])
            ry = reg_line.get("y", [])
            if rx and ry:
                ax.plot(rx, ry, '-', color=_PP_ADV_COL, linewidth=2, label="Fitted")
        elif ss.get("primary", {}).get("beta") is not None:
            primary = ss["primary"]
            xarr = np.linspace(min(xs), max(xs), 100)
            # Simple linear: y = a + beta * x
            mean_y = np.mean(ys)
            mean_x = np.mean(xs)
            intercept = mean_y - primary["beta"] * mean_x
            yarr = intercept + primary["beta"] * xarr
            ax.plot(xarr, yarr, '-', color=_PP_ADV_COL, linewidth=2,
                    label=f"$\\beta$={primary['beta']:.4f}")

    _setup_ax(ax, "log(Reserves)", "Severity", "Size--severity relationship")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig4_size_severity_loglog.png")


def _gen_fig5(results):
    """VaR decomposition grouped bar chart (Shapley effects)."""
    ports = _safe_get(results, "capital_impact", "portfolios", default=[])
    if not ports:
        return
    names = [p.get("name", f"P{i}") for i, p in enumerate(ports)]
    mix_99 = []
    size_99 = []
    mix_995 = []
    size_995 = []
    for p in ports:
        shapley = p.get("shapley", {})
        v99 = shapley.get("var_99", {})
        v995 = shapley.get("var_995", {})
        mix_995.append(float(v995.get("concentration_effect", 0)))
        size_995.append(float(v995.get("size_effect", 0)))
        mix_99.append(float(v99.get("concentration_effect", 0)))
        size_99.append(float(v99.get("size_effect", 0)))

    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width / 2, mix_995, width, label="Concentration effect (VaR 99.5%)", color=_PP_RAW_COL)
    ax.bar(x + width / 2, size_995, width, label="Size effect (VaR 99.5%)", color=_PP_STD_COL)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=9)
    _setup_ax(ax, "", "Effect on VaR", "Shapley VaR 99.5% decomposition")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig5_var_decomposition.png")


def _gen_fig6(results):
    """LoB elasticities dot plot."""
    lob_el = _safe_get(results, "size_scaling", "lob_elasticities", default=None)
    if not lob_el:
        (_pp_dir() / "fig6_lob_elasticities_NOTE.txt").write_text(
            "No lob_elasticities data available in size_scaling.\n", encoding="utf-8")
        return
    names = [e.get("lob", f"LoB {i}") for i, e in enumerate(lob_el)]
    betas = [e.get("beta", 0) for e in lob_el]
    ci_lo = [e.get("ci_lo", e.get("beta", 0)) for e in lob_el]
    ci_hi = [e.get("ci_hi", e.get("beta", 0)) for e in lob_el]
    errs = [[b - lo for b, lo in zip(betas, ci_lo)],
            [hi - b for b, hi in zip(betas, ci_hi)]]
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(names))
    ax.errorbar(betas, y, xerr=errs, fmt='o', color=_PP_RAW_COL, capsize=4)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
    _setup_ax(ax, "$\\beta$ (elasticity)", "", "LoB-level severity elasticities")
    _save_fig(fig, "fig6_lob_elasticities.png")


def _gen_fig_persona_overlays(results):
    """Per-persona raw vs standardised PYD histograms."""
    personas = results.get("personas", {})
    for pk in ["typical", "small", "large", "diversified", "undiversified"]:
        pd_ = personas.get(pk, {})
        hist = pd_.get("histogram_c", pd_.get("histogram_market_raw", {}))
        if not hist:
            continue
        fig, ax = plt.subplots(figsize=(10, 6))

        # Try multiple data formats: histogram_c may have {raw:{bins,counts}, standardised:{bins,counts}}
        if isinstance(hist, dict):
            raw_data = hist.get("raw", {})
            std_data = hist.get("standardised", {})
            if isinstance(raw_data, dict) and raw_data.get("bins") and raw_data.get("counts"):
                bins_r = raw_data["bins"]
                counts_r = raw_data["counts"]
                bw = raw_data.get("bin_width", bins_r[1] - bins_r[0] if len(bins_r) > 1 else 1)
                ax.bar(bins_r[:len(counts_r)], counts_r, width=bw * 0.8,
                       alpha=0.5, color=_PP_RAW_COL, label="Raw")
            if isinstance(std_data, dict) and std_data.get("bins") and std_data.get("counts"):
                bins_s = std_data["bins"]
                counts_s = std_data["counts"]
                bw = std_data.get("bin_width", bins_s[1] - bins_s[0] if len(bins_s) > 1 else 1)
                ax.bar(bins_s[:len(counts_s)], counts_s, width=bw * 0.8,
                       alpha=0.5, color=_PP_STD_COL, label="Standardised")
            # Fallback: flat format with bins/raw_counts/standardised_counts at top level
            elif hist.get("bins") and (hist.get("raw_counts") or hist.get("counts")):
                bins = hist["bins"]
                raw_c = hist.get("raw_counts", hist.get("counts", []))
                std_c = hist.get("standardised_counts", [])
                centers = [(bins[i] + bins[i + 1]) / 2 for i in range(len(bins) - 1)] if len(bins) == len(raw_c) + 1 else bins[:len(raw_c)]
                if raw_c:
                    ax.bar(centers, raw_c, width=(centers[1] - centers[0]) * 0.8 if len(centers) > 1 else 0.1,
                           alpha=0.5, color=_PP_RAW_COL, label="Raw")
                if std_c:
                    ax.bar(centers[:len(std_c)], std_c, width=(centers[1] - centers[0]) * 0.8 if len(centers) > 1 else 0.1,
                           alpha=0.5, color=_PP_STD_COL, label="Standardised")

        _setup_ax(ax, "PYD %", "Count", f"Persona: {pk.title()} --- PYD distribution")
        if ax.get_legend_handles_labels()[1]:
            ax.legend(fontsize=10)
        _save_fig(fig, f"fig_persona_overlay_{pk}.png")


def _gen_fig_pyd_distribution(results):
    """Overall PYD histogram."""
    hist = _safe_get(results, "distribution", "pyd_histogram", default={})
    bins = hist.get("bins", [])
    counts = hist.get("counts", [])
    fig, ax = plt.subplots(figsize=(10, 6))
    if bins and counts:
        centers = [(bins[i] + bins[i + 1]) / 2 for i in range(len(bins) - 1)] if len(bins) == len(counts) + 1 else bins[:len(counts)]
        width = (centers[1] - centers[0]) * 0.9 if len(centers) > 1 else 0.1
        ax.bar(centers, counts, width=width, color=_PP_RAW_COL, alpha=0.7)
    _setup_ax(ax, "PYD %", "Frequency", "PYD distribution")
    _save_fig(fig, "fig_pyd_distribution.png")


def _gen_fig_boxplots(results):
    """Box plots by year, reserves decile, HHI decile."""
    bp = _safe_get(results, "distribution", "boxplots", default={})

    for key, fname, xlabel in [
        ("by_year", "fig_boxplot_year.png", "Year"),
        ("by_reserves_decile", "fig_boxplot_reserves.png", "Reserves decile"),
        ("by_hhi_decile", "fig_boxplot_hhi.png", "HHI decile"),
    ]:
        data = bp.get(key, [])
        if not data:
            # Try alternative location for by_year
            if key == "by_year":
                data = _safe_get(results, "overview", "boxplots_by_year", default=[])
            if not data:
                continue
        fig, ax = plt.subplots(figsize=(12, 6))
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                labels = [str(d.get("label", d.get("year", d.get("decile", i)))) for i, d in enumerate(data)]
                box_data = [d.get("values", d.get("data", [])) for d in data]
                if box_data and box_data[0]:
                    ax.boxplot(box_data, labels=labels, patch_artist=True,
                               boxprops=dict(facecolor=_PP_RAW_COL, alpha=0.3))
                else:
                    # Maybe summary stats format
                    medians = [d.get("median", 0) for d in data]
                    ax.bar(range(len(medians)), medians, color=_PP_RAW_COL, alpha=0.6)
                    ax.set_xticks(range(len(labels)))
                    ax.set_xticklabels(labels)
        _setup_ax(ax, xlabel, "PYD %", f"PYD by {xlabel.lower()}")
        if len(str(labels[0] if data else "")) <= 4:
            ax.tick_params(axis='x', rotation=45)
        _save_fig(fig, fname)


def _gen_fig_size_pyd(results):
    """Size vs PYD scatter with 10th/90th percentile curves."""
    ss = results.get("size_scaling", {})
    scatter = ss.get("scatter_data", {})
    points = scatter.get("points", [])
    if not points:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    xs = [p.get("x", p.get("log_reserves", 0)) for p in points]
    ys = [p.get("y", p.get("severity", 0)) for p in points]
    ax.scatter(xs, ys, alpha=0.25, s=15, color='#bdbdbd', label="Observations")

    # Overlay 10th/90th percentile curves
    qb = scatter.get("quantile_bins", [])
    if qb:
        qx = [b["x"] for b in qb]
        q90 = [b["q90"] for b in qb]
        q10 = [b["q10"] for b in qb]
        ax.plot(qx, q90, '--o', color=_PP_ADV_COL, linewidth=1.5, markersize=4,
                markerfacecolor='none', label="90th percentile")
        ax.plot(qx, q10, '--o', color=_PP_ADV_COL, linewidth=1.5, markersize=4,
                markerfacecolor='none', label="10th percentile")

    _setup_ax(ax, "Log(Reserve Size)", "PYD Severity", "Size vs PYD Severity")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_size_pyd.png")


def _lowess_smooth(xs, ys, frac=0.2):
    """Gaussian-kernel weighted local smoother.

    For each evaluation point, weights nearby observations with a Gaussian
    kernel (bandwidth = frac * x-range) and returns the weighted mean.
    The result is evaluated on a fine grid for a smooth curve.
    """
    xs_a = np.asarray(xs, dtype=float)
    ys_a = np.asarray(ys, dtype=float)
    order = np.argsort(xs_a)
    xs_a, ys_a = xs_a[order], ys_a[order]
    x_grid = np.linspace(xs_a[0], xs_a[-1], 200)
    h = frac * (xs_a[-1] - xs_a[0])
    if h <= 0:
        return [], []
    cy = []
    for xg in x_grid:
        w = np.exp(-0.5 * ((xs_a - xg) / h) ** 2)
        cy.append(float(np.average(ys_a, weights=w)))
    return x_grid.tolist(), cy


def _gen_fig_size_abs_pyd(results):
    """Scatter: log(Reserve Size) vs |PYD %|  with non-parametric trend."""
    ss = results.get("size_scaling", {})
    points = ss.get("scatter_data", {}).get("points", [])
    pts = [p for p in points if p.get("pyd_pct") is not None]
    if len(pts) < 10:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    xs = [p["x"] for p in pts]  # already log(reserves)
    ys = [abs(p["pyd_pct"]) for p in pts]
    ax.scatter(xs, ys, alpha=0.25, s=15, color='#bdbdbd')
    # Trend line
    cx, cy = _lowess_smooth(xs, ys)
    if len(cx) >= 3:
        ax.plot(cx, cy, '-', color=_PP_ADV_COL, linewidth=2.5, label="Smoothed trend")
        ax.legend(fontsize=10)
    _setup_ax(ax, "log(Reserve Size)", "|PYD %|",
              "Reserve size vs absolute PYD severity")
    _save_fig(fig, "fig_size_abs_pyd.png")


def _gen_fig_diversification_abs_pyd(results):
    """Scatter: Diversification (1 - HHI) vs |PYD %|  with non-parametric trend."""
    ss = results.get("size_scaling", {})
    points = ss.get("scatter_data", {}).get("points", [])
    pts = [p for p in points if p.get("pyd_pct") is not None and p.get("hhi") is not None]
    if len(pts) < 10:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    xs = [1.0 - p["hhi"] for p in pts]
    ys = [abs(p["pyd_pct"]) for p in pts]
    ax.scatter(xs, ys, alpha=0.25, s=15, color='#bdbdbd')
    # Trend line
    cx, cy = _lowess_smooth(xs, ys)
    if len(cx) >= 3:
        ax.plot(cx, cy, '-', color=_PP_ADV_COL, linewidth=2.5, label="Smoothed trend")
        ax.legend(fontsize=10)
    _setup_ax(ax, "Diversification $(1 - \\mathrm{HHI})$", "|PYD %|",
              "Diversification vs absolute PYD severity")
    _save_fig(fig, "fig_diversification_abs_pyd.png")


def _gen_fig_power_law_size(results):
    """Power-law dispersion curve for size."""
    sm = _safe_get(results, "joint_composition", "size_model_used", default={})
    A = sm.get("A")
    B = sm.get("B")
    C = sm.get("C")
    if A is None or B is None or C is None:
        return
    fig, ax = plt.subplots(figsize=(10, 6))

    # Overlay scatter if available
    scatter_pts = _safe_get(results, "joint_composition", "scatter_points", default=[])
    if scatter_pts:
        rx = [p.get("reserves", p.get("x", 0)) for p in scatter_pts]
        ry = [p.get("var_sq", p.get("y", 0)) for p in scatter_pts]
        ax.scatter(rx, ry, alpha=0.3, s=15, color=_PP_RAW_COL, label="Observations")

    r_range = np.linspace(50, 5000, 200)
    s2 = float(A) + float(B) * r_range ** float(C)
    ax.plot(r_range, s2, '-', color=_PP_ADV_COL, linewidth=2,
            label=f"$\\sigma^2 = {A:.4f} + {B:.4f} \\cdot R^{{{C:.4f}}}$")
    _setup_ax(ax, "Reserves (£m)", "$\\sigma^2$", "Power-law size dispersion")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_power_law_size.png")


def _gen_fig_hhi_severity(results):
    """HHI scatter: diversification vs severity with 10th/90th percentile curves."""
    hs = _safe_get(results, "exposure_composition", "hhi_scatter", default={})
    pts = hs.get("points", [])
    if not pts:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    xs = [p.get("x", p.get("diversification", 0)) for p in pts]
    ys = [p.get("y", p.get("severity", 0)) for p in pts]
    ax.scatter(xs, ys, alpha=0.25, s=15, color='#bdbdbd', label="Observations")

    # Overlay 10th/90th percentile curves
    qb = hs.get("quantile_bins", [])
    if qb:
        qx = [b["x"] for b in qb]
        q90 = [b["q90"] for b in qb]
        q10 = [b["q10"] for b in qb]
        ax.plot(qx, q90, '--o', color=_PP_ADV_COL, linewidth=1.5, markersize=4,
                markerfacecolor='none', label="90th percentile")
        ax.plot(qx, q10, '--o', color=_PP_ADV_COL, linewidth=1.5, markersize=4,
                markerfacecolor='none', label="10th percentile")

    _setup_ax(ax, "Diversification (1 \u2212 HHI)", "PYD Severity",
              "Diversification vs PYD Severity")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_hhi_severity.png")


def _gen_fig_power_law_hhi(results):
    """Power-law HHI dispersion curve."""
    sh = _safe_get(results, "exposure_composition", "dispersion_models", "single_h", default={})
    A = sh.get("A")
    B = sh.get("B")
    C = sh.get("C")
    if A is None or B is None or C is None:
        return
    fig, ax = plt.subplots(figsize=(10, 6))

    # Overlay quantile bins if available
    qb = _safe_get(results, "exposure_composition", "hhi_scatter", "quantile_bins", default=[])
    if qb:
        bx = [b.get("hhi_mid", b.get("x", 0)) for b in qb]
        by = [b.get("var_sq", b.get("y", 0)) for b in qb]
        ax.scatter(bx, by, s=60, color=_PP_RAW_COL, zorder=5, label="Quantile bins")

    hhi_range = np.linspace(0.05, 1.0, 200)
    s2 = float(A) + float(B) * hhi_range ** float(C)
    ax.plot(hhi_range, s2, '-', color=_PP_ADV_COL, linewidth=2,
            label=f"$\\sigma^2 = {A:.4f} + {B:.4f} \\cdot \\mathrm{{HHI}}^{{{C:.4f}}}$")
    _setup_ax(ax, "HHI", "$\\sigma^2$", "Power-law HHI dispersion")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_power_law_hhi.png")


def _gen_fig_diversification_reserves(results):
    """Scatter: diversification vs reserve size."""
    pts = _safe_get(results, "joint_composition", "hhi_r_correlation", "scatter_points", default=[])
    if not pts:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    xs = [p.get("x", p.get("diversification", 0)) for p in pts]
    ys = [p.get("y", p.get("reserves", 0)) for p in pts]
    ax.scatter(xs, ys, alpha=0.3, s=15, color=_PP_RAW_COL)
    _setup_ax(ax, "Diversification (1 - HHI)", "Reserves (£m)", "Diversification vs reserve size")
    _save_fig(fig, "fig_diversification_reserves.png")


def _gen_fig_size_adjusted_hhi(results):
    """Size-adjusted dispersion vs diversification."""
    pts = _safe_get(results, "joint_composition", "scatter_points", default=[])
    dh = _safe_get(results, "joint_composition", "disp_h_adjusted", default={})

    fig, ax = plt.subplots(figsize=(10, 6))
    if pts:
        xs = [p.get("diversification", p.get("x", 0)) for p in pts]
        ys = [p.get("adj_var_sq", p.get("y", 0)) for p in pts]
        ax.scatter(xs, ys, alpha=0.3, s=15, color=_PP_RAW_COL, label="Observations")

    A = dh.get("A")
    B = dh.get("B")
    C = dh.get("C")
    if A is not None and B is not None and C is not None:
        hhi_range = np.linspace(0.05, 1.0, 200)
        s2 = float(A) + float(B) * hhi_range ** float(C)
        ax.plot(hhi_range, s2, '-', color=_PP_ADV_COL, linewidth=2, label="Adjusted model")

    _setup_ax(ax, "Diversification", "Size-adjusted $\\sigma^2$",
              "Size-adjusted dispersion vs diversification")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_size_adjusted_hhi.png")


def _gen_fig_hhi_adjusted_size(results):
    """HHI-adjusted dispersion vs reserve size (HHI-first pipeline)."""
    hf = _safe_get(results, "joint_composition", "hhi_first", default={})
    pts = hf.get("scatter_points", [])
    dr = hf.get("disp_r_on_residuals", {})

    fig, ax = plt.subplots(figsize=(10, 6))
    if pts:
        xs = [p.get("x", 0) for p in pts]
        ys = [p.get("y_adj_sq", 0) for p in pts]
        ax.scatter(xs, ys, alpha=0.3, s=15, color='#6610f2', label="Observations")

    A = dr.get("A")
    B = dr.get("B")
    C = dr.get("C")
    if A is not None and B is not None and C is not None:
        r_range = np.linspace(max(min(p.get("x", 1) for p in pts), 1) if pts else 1,
                              max(p.get("x", 1) for p in pts) if pts else 5000, 200)
        s2 = float(A) + float(B) * r_range ** float(C)
        ax.plot(r_range, s2, '-', color='#e74c3c', linewidth=2, label="Fitted model")

    # Plot bin points if available
    bp = dr.get("bin_points", [])
    if bp:
        bx = [p["x"] for p in bp]
        by = [p["y"] for p in bp]
        ax.scatter(bx, by, s=50, color='#e74c3c', zorder=5, label="Bin means")

    _setup_ax(ax, "Opening Reserves (£m)", "HHI-adjusted $\\sigma^2$",
              "HHI-adjusted dispersion vs reserve size")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_hhi_adjusted_size.png")


def _gen_fig_capital_decomposition(results):
    """Stacked/grouped bar: naive → mix_adj → full_adj for VaR 99.5%."""
    ports = _safe_get(results, "capital_impact", "portfolios", default=[])
    if not ports:
        return
    names = [p.get("name", f"P{i}") for i, p in enumerate(ports)]
    naive_vals = [float(_safe_get(p, "naive", "var_995", default=0)) for p in ports]
    mix_vals = [float(_safe_get(p, "concentration_only", "var_995", default=0)) for p in ports]
    full_vals = [float(_safe_get(p, "full", "var_995", default=0)) for p in ports]

    x = np.arange(len(names))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width, naive_vals, width, label="Naive", color='#bdbdbd')
    ax.bar(x, mix_vals, width, label="Mix-adjusted", color=_PP_RAW_COL)
    ax.bar(x + width, full_vals, width, label="Fully adjusted", color=_PP_STD_COL)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=9)
    _setup_ax(ax, "", "VaR 99.5%", "Capital impact decomposition (VaR 99.5%)")
    ax.legend(fontsize=10)
    _save_fig(fig, "fig_capital_decomposition.png")


# ── Extended table generators (A/B/C/D) ──────────────────────────────────────

def _gen_table26(results):
    """A1 — Tail sample support."""
    ts = results.get("tail_support", {})
    if not ts:
        return
    body = ("\\textbf{Portfolio} & \\textbf{$n$} & \\textbf{Adverse} "
            "& \\textbf{Tail (99\\%)} & \\textbf{Tail (99.5\\%)} \\\\\n\\midrule\n")
    for name, d in ts.items():
        body += (f"{name} & {d['n_total']} & {d['n_adverse']} "
                 f"& {d['n_tail_99']} & {d['n_tail_995']} \\\\\n")
    _write_tex("table26_tail_sample_support.tex",
               _wrap_table(body, "Tail sample support for capital analysis",
                           "tail_sample_support", "lrrrr"))


def _gen_table27(results):
    """A2 — Tail capital sensitivity across subsets."""
    tcs = results.get("tail_capital_sensitivity", {})
    if not tcs:
        return
    # Collect all portfolio names from first non-error subset
    port_names = []
    for sname, sdata in tcs.items():
        if isinstance(sdata, dict) and "status" not in sdata:
            port_names = list(sdata.keys())
            break
    if not port_names:
        return
    body = "\\textbf{Subset} & \\textbf{$n$} & \\textbf{VaR$_{99.5}$ (naive)} & \\textbf{VaR$_{99.5}$ (adj.)} \\\\\n"
    for pname in port_names:
        body += f"\\midrule\n\\multicolumn{{4}}{{l}}{{\\textbf{{{pname}}}}} \\\\\n\\midrule\n"
        for sname in ["DENSE", "FULL", "BALANCED_K8", "BALANCED_K6"]:
            sdata = tcs.get(sname, {})
            if "status" in sdata:
                body += f"{sname} & -- & -- & -- \\\\\n"
                continue
            pd = sdata.get(pname, {})
            body += (f"{sname} & {_fmt(pd.get('n'),'.0f')} "
                     f"& {_fmt(pd.get('var_995_naive'),'.4f')} "
                     f"& {_fmt(pd.get('var_995_full'),'.4f')} \\\\\n")
    _write_tex("table27_tail_capital_sensitivity.tex",
               _wrap_table(body, "Tail capital sensitivity across sample variants",
                           "tail_capital_sensitivity", "lrrr"))


def _gen_table28(results):
    """A3 — Bootstrap VaR uncertainty bands."""
    ports = _safe_get(results, "capital_impact", "portfolios", default=[])
    if not ports:
        return
    body = ("\\textbf{Portfolio} & \\textbf{VaR$_{99.5}$ (adj.)} "
            "& \\textbf{95\\% CI lower} & \\textbf{95\\% CI upper} "
            "& \\textbf{VaR$_{99}$ (adj.)} "
            "& \\textbf{95\\% CI lower} & \\textbf{95\\% CI upper} \\\\\n\\midrule\n")
    for p in ports:
        name = p.get("name", "--")
        var_995 = _safe_get(p, "full", "var_995")
        var_99 = _safe_get(p, "full", "var_99")
        bci = p.get("boot_ci", {})
        ci_995 = bci.get("full_var_995", [None, None])
        ci_99 = bci.get("full_var_99", [None, None])
        if not isinstance(ci_995, list) or len(ci_995) < 2:
            ci_995 = [None, None]
        if not isinstance(ci_99, list) or len(ci_99) < 2:
            ci_99 = [None, None]
        body += (f"{name} & {_fmt(var_995,'.4f')} "
                 f"& {_fmt(ci_995[0],'.4f')} & {_fmt(ci_995[1],'.4f')} "
                 f"& {_fmt(var_99,'.4f')} "
                 f"& {_fmt(ci_99[0],'.4f')} & {_fmt(ci_99[1],'.4f')} \\\\\n")
    _write_tex("table28_bootstrap_var.tex",
               _wrap_table(body, "Bootstrap VaR estimates with 95\\% confidence intervals",
                           "bootstrap_var", "lrrrrrr"))


def _gen_table29(results):
    """B1 — Reserve-base source audit."""
    dq = results.get("data_quality", {})
    rsd = dq.get("reserve_source_dist", {})
    total = sum(rsd.values())
    body = "\\textbf{Source} & \\textbf{Count} & \\textbf{\\%} \\\\\n\\midrule\n"
    for src, cnt in sorted(rsd.items()):
        pct = cnt / total * 100 if total > 0 else 0
        body += f"Opening reserves ({src}) & {cnt} & {_fmt(pct,'.1f')}\\% \\\\\n"
    body += f"\\midrule\nTotal & {total} & 100.0\\% \\\\\n"
    _write_tex("table29_reserve_source_audit.tex",
               _wrap_table(body, "Reserve-base source audit",
                           "reserve_source_audit", "lrr"))


def _gen_table30(results):
    """B2 — LoB weight source audit."""
    dq = results.get("data_quality", {})
    wsd = dq.get("weight_source_dist", {})
    total = sum(wsd.values())
    label_map = {
        "premium_mix": "Direct premium-mix disclosure",
        "none": "Unavailable (proportional allocation)",
    }
    body = "\\textbf{Source} & \\textbf{Count} & \\textbf{\\%} \\\\\n\\midrule\n"
    for src, cnt in sorted(wsd.items(), key=lambda x: -x[1]):
        label = label_map.get(src, src)
        pct = cnt / total * 100 if total > 0 else 0
        body += f"{label} & {cnt} & {_fmt(pct,'.1f')}\\% \\\\\n"
    body += f"\\midrule\nTotal & {total} & 100.0\\% \\\\\n"
    _write_tex("table30_lob_weight_source_audit.tex",
               _wrap_table(body, "LoB weight source audit",
                           "lob_weight_source_audit", "lrr"))


def _gen_table31(results):
    """B3 — PYD source audit."""
    psd = results.get("pyd_source_dist", {})
    total = sum(psd.values())
    label_map = {
        "structured_table": "Structured table (LoB-level amounts)",
        "triangle_or_proportional": "Triangle / proportional allocation",
        "narrative_only": "Narrative extraction only",
    }
    body = "\\textbf{Source} & \\textbf{Count} & \\textbf{\\%} \\\\\n\\midrule\n"
    for src in ["structured_table", "triangle_or_proportional", "narrative_only"]:
        cnt = psd.get(src, 0)
        label = label_map.get(src, src)
        pct = cnt / total * 100 if total > 0 else 0
        body += f"{label} & {cnt} & {_fmt(pct,'.1f')}\\% \\\\\n"
    body += f"\\midrule\nTotal & {total} & 100.0\\% \\\\\n"
    _write_tex("table31_pyd_source_audit.tex",
               _wrap_table(body, "PYD severity source audit",
                           "pyd_source_audit", "lrr"))


def _gen_table32(results):
    """B4 — Dual-model disagreement workflow note."""
    dms = results.get("dual_model_stats", {})
    total = dms.get("total_files", 0)
    dual = dms.get("dual_model_files", 0)
    single = dms.get("single_model_files", 0)
    disagree = dms.get("material_disagreements", 0)
    threshold = dms.get("disagreement_threshold_pp", 0.5)

    content = (
        "\\begin{table}[htbp]\n"
        "\\centering\n"
        "\\caption{Dual-model disagreement workflow}\n"
        "\\label{tab:dual_model}\n"
        "\\begin{tabular}{lr}\n"
        "\\toprule\n"
        "\\textbf{Metric} & \\textbf{Value} \\\\\n"
        "\\midrule\n"
        f"Total source files & {total} \\\\\n"
        f"Dual-model files & {dual} \\\\\n"
        f"Single-model files & {single} \\\\\n"
        f"Material disagreements ($>$ {threshold}pp) & {disagree} \\\\\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\smallskip\n\n"
        "\\begin{minipage}{0.9\\textwidth}\\small\n"
        "Each syndicate-year report was independently processed by two extraction models "
        "(Gemini 2.5 Flash and GPT-5 Mini). The key field compared was "
        "\\texttt{prior\\_year\\_development\\_pct}. A disagreement was classified as "
        f"material when the absolute difference exceeded {threshold}\\,pp. "
        f"Of {dual} dual-model files, {disagree} exhibited material disagreement. "
        "Where both models agreed within tolerance, the higher-confidence extraction "
        "was selected as canonical. For material disagreements, the model with "
        "higher \\texttt{prior\\_year\\_movement\\_confidence} was preferred; "
        "manual adjudication was applied only when confidence scores were tied "
        "or when the validation step flagged structural inconsistencies.\n"
        "\\end{minipage}\n"
        "\\end{table}\n"
    )
    _write_tex("table32_dual_model_workflow.tex", content)


def _gen_table33(results):
    """C1 — Exclusion table by reason and year."""
    cl = results.get("classification_summary", {})
    by_reason_year = cl.get("by_reason_year", {})
    by_reason_total = cl.get("by_reason_total", {})
    years = cl.get("years", [])
    if not years or not by_reason_total:
        return
    # Filter to exclusion reasons (not RELIABLE/INCOMPLETE which are kept)
    excl_reasons = [r for r in by_reason_total.keys()
                    if r not in ("RELIABLE", "INCOMPLETE")]
    if not excl_reasons:
        return
    n_cols = len(years) + 1
    colspec = "l" + "r" * n_cols
    body = "\\textbf{Reason} & " + " & ".join(f"\\textbf{{{y}}}" for y in years) + " & \\textbf{Total} \\\\\n\\midrule\n"
    for reason in sorted(excl_reasons):
        yr_data = by_reason_year.get(reason, {})
        row = [str(yr_data.get(y, 0)) for y in years]
        total = by_reason_total.get(reason, 0)
        body += f"{reason} & " + " & ".join(row) + f" & {total} \\\\\n"
    # Total row
    totals_by_year = []
    for y in years:
        t = sum(by_reason_year.get(r, {}).get(y, 0) for r in excl_reasons)
        totals_by_year.append(str(t))
    grand_total = sum(by_reason_total.get(r, 0) for r in excl_reasons)
    body += "\\midrule\nTotal excluded & " + " & ".join(totals_by_year) + f" & {grand_total} \\\\\n"
    _write_tex("table33_exclusions_by_year.tex",
               _wrap_table(body, "Exclusions by reason and year",
                           "exclusions_by_year", colspec))


def _gen_table34(results):
    """C2 — Subset comparison table."""
    sp = results.get("subset_profiles", {})
    if not sp:
        return
    body = ("\\textbf{Subset} & \\textbf{$n$} & \\textbf{Syndicates} "
            "& \\textbf{Years} & \\textbf{Med.\\ reserves} & \\textbf{Med.\\ HHI} "
            "& \\textbf{Natural cat \\%} & \\textbf{COVID \\%} \\\\\n\\midrule\n")
    for sname in ["DENSE", "FULL", "BALANCED_K8", "BALANCED_K6"]:
        sd = sp.get(sname, {})
        if not sd:
            continue
        egs = sd.get("event_group_shares", {})
        nat_cat = _fmt(egs.get("natural_cat", 0), ".1f")
        covid = _fmt(egs.get("covid", 0), ".1f")
        body += (f"{sname} & {sd.get('n_obs','--')} & {sd.get('n_syndicates','--')} "
                 f"& {sd.get('year_range','--')} "
                 f"& {_fmt_gbp(sd.get('median_reserves'))} "
                 f"& {_fmt(sd.get('median_hhi'),'.3f')} "
                 f"& {nat_cat}\\% & {covid}\\% \\\\\n")
    _write_tex("table34_subset_comparison.tex",
               _wrap_table(body, "Subset comparison: DENSE, FULL, and balanced panels",
                           "subset_comparison", "lrrllrrr"))


def _gen_table35(results):
    """C3 — Size-dispersion robustness."""
    dr = results.get("dispersion_robustness", {})
    if not dr:
        return
    body = ("\\textbf{Specification} & \\textbf{$n$} & $\\hat{\\beta}$ "
            "& \\textbf{SE} & \\textbf{$p$-value} \\\\\n\\midrule\n")
    for key in ["primary", "pre_2020_only", "persistent_only"]:
        d = dr.get(key, {})
        if not d:
            continue
        label = d.get("label", key)
        body += (f"{label} & {_fmt(d.get('n'),'.0f')} "
                 f"& {_fmt(d.get('beta'),'.4f')}{_sig_stars(d.get('p_value'))} "
                 f"& {_fmt(d.get('se'),'.4f')} "
                 f"& {_fmt(d.get('p_value'),'.4f')} \\\\\n")
    _write_tex("table35_dispersion_robustness.tex",
               _wrap_table(body, "Size--dispersion robustness: restricted samples",
                           "dispersion_robustness", "lrrrr"))


def _gen_table36(results):
    """D1 — Event-group categories and counts."""
    ega = _safe_get(results, "size_scaling", "event_group_audit", default=[])
    if not ega:
        return
    body = ("\\textbf{Event group} & \\textbf{Year} & \\textbf{Cause} "
            "& \\textbf{$n$} & \\textbf{Pooled?} \\\\\n\\midrule\n")
    for eg in ega:
        eg_id = eg.get("event_group_id", "")
        parts = eg_id.split("_", 1)
        year = parts[0] if len(parts) >= 1 else "--"
        cause = parts[1] if len(parts) >= 2 else "--"
        pooled = "Yes" if eg.get("pooled") else "No"
        body += (f"{eg_id} & {year} & {cause} "
                 f"& {eg.get('n_syndicates','--')} & {pooled} \\\\\n")
    _write_tex("table36_event_groups.tex",
               _wrap_table(body, "Event-group categories and counts",
                           "event_groups", "llrlr"))


def _gen_table38(results):
    """A.x — Robust Bayesian pooling dispersion calibration (posterior summaries)."""
    ritc_path = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
    cal_path = ritc_path if ritc_path.exists() else (SCRIPT_DIR / "model" / "dispersion_calibration.json")
    if not cal_path.exists():
        _write_tex("table38_dispersion_calibration.tex",
                   "% dispersion_calibration.json not found --- run calibrate_dispersion.py\n")
        return
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    has_ritc = "nu_clean" in cal.get("params", {})
    p = cal.get("params", {})
    pp = cal.get("posterior_prob", {})
    diag = cal.get("diagnostics", {})

    def _row(sym, key, desc, fmt=".3f"):
        r = p.get(key, {})
        return (f"{sym} & {_fmt(r.get('mean'), fmt)} & {_fmt(r.get('sd'), fmt)} "
                f"& [{_fmt(r.get('hdi_2.5'), fmt)},\\; {_fmt(r.get('hdi_97.5'), fmt)}] & {desc} \\\\\n")

    body = ("\\textbf{Parameter} & \\textbf{Posterior mean} & \\textbf{SD} "
            "& \\textbf{95\\% HDI} & \\textbf{Interpretation} \\\\\n\\midrule\n")
    nu_formula = ("$\\nu_{it}=\\nu_{\\text{clean}}$ (clean) or $\\nu_{\\text{clean}}e^{-\\lambda_{\\text{RITC}}}$ (RITC)"
                  if has_ritc else "$\\nu$")
    body += ("\\multicolumn{5}{p{15cm}}{\\textbf{Model:} "
             f"$S \\sim t_{{\\nu}}(0,\\sigma)$ with {nu_formula}, "
             "$\\sigma = \\sqrt{\\sigma_{\\text{undiv}}^2 + \\sigma_{\\text{div}}^2\\,[(R/R_{\\text{ref}})(1/H)^{\\gamma}]^{2(k-1)}}\\cdot e^{s_t}$"
             + (" $\\cdot\\, e^{\\beta_{\\text{RITC}}\\mathbf{1}_{\\text{RITC}}}$ (fitted scale multiplier; the transfer operator omits it)"
                if has_ritc else "")
             + f" \\quad ($n = {cal.get('n')}$, {cal.get('n_years')} reporting years)}} \\\\\n\\midrule\n")
    body += _row("$k$", "k", "diversifiable-term pooling exponent ($\\tfrac12$=finite-variance "
                 "independent $\\sqrt N$, $1$=comonotonic)")
    body += _row("$\\gamma$", "gamma", "concentration (effective-line $1/H$) exponent")
    body += _row("$\\sigma_{\\text{undiv}}$", "sd_undiv", "undiversifiable floor (very-large-book dispersion)", ".4f")
    body += _row("$\\sigma_{\\text{div}}$", "sd_div", "diversifiable scale at reference ($\\pounds500$m, single-line)", ".4f")
    if has_ritc:
        body += _row("$\\nu_{\\text{clean}}$", "nu_clean", "Student-$t$ tail index, clean regime", ".2f")
        body += _row("$\\nu_{\\text{RITC}}$", "nu_ritc", "Student-$t$ tail index, RITC regime (heavier)", ".2f")
        body += _row("$\\lambda_{\\text{RITC}}$", "lambda_ritc", "log tail-weight shift ($>0\\Rightarrow$ RITC heavier)", ".3f")
        body += _row("$\\beta_{\\text{RITC}}$", "beta_ritc", "RITC scale term, omitted from the operator (not shown to be 0)", ".3f")
    else:
        body += _row("$\\nu$", "nu", "Student-$t$ tail index (heavy tails)", ".2f")
    body += _row("$\\tau_s$", "tau_s", "reporting-year shared-shock SD (log-scale)")
    body += "\\midrule\n"
    # P(k<1) and P(k>1/2) are one by construction on the bracketed support and are
    # not printed as evidence (round 51; the unconstrained refit carries them)
    if has_ritc:
        body += (f"\\multicolumn{{5}}{{l}}{{$P(k<1)$, $P(k>\\tfrac12)$: one by construction on the "
                 f"bracketed support, not evidence;\\quad "
                 f"$P(\\nu_{{\\text{{RITC}}}}<\\nu_{{\\text{{clean}}}}) = {_fmt(pp.get('nu_ritc_lt_nu_clean'),'.2f')}$,\\quad "
                 f"$P(\\nu_{{\\text{{clean}}}}<2) = {_fmt(pp.get('nu_clean_lt_2'),'.2f')}$,\\quad "
                 f"$P(\\nu_{{\\text{{RITC}}}}<2) = {_fmt(pp.get('nu_ritc_lt_2'),'.2f')}$}} \\\\\n")
    else:
        body += (f"\\multicolumn{{5}}{{l}}{{$P(k<1)$: one by construction on the bracketed "
                 f"support, not evidence;\\quad "
                 f"$P(\\gamma>0.05) = {_fmt(pp.get('gamma_gt_0.05'),'.2f')}$,\\quad "
                 f"$P(\\sigma_{{\\text{{undiv}}}}>0.005) = {_fmt(pp.get('sd_undiv_gt_0.005'),'.2f')}$,\\quad "
                 f"$P(\\nu<2) = {_fmt(pp.get('nu_lt_2'),'.2f')}$}} \\\\\n")
    body += "\\midrule\n"
    body += ("\\multicolumn{5}{p{15cm}}{Fitted by Hamiltonian Monte Carlo (NUTS, 4 chains, "
             "1500 post-warmup draws each) with $\\mu=0$ fixed. "
             f"Convergence: max $\\hat R = {_fmt(diag.get('max_rhat'),'.2f')}$, "
             f"min bulk-ESS $= {_fmt(diag.get('min_ess_bulk'),'.0f')}$, "
             f"{diag.get('divergences','?')} divergences. "
             "The pooling exponent $k$ is constrained to $[0.5,1]$ via a logistic transform; "
             "$\\gamma\\ge0$ via a half-normal prior. The undiversifiable variance share at "
             "the reference has a uniform (Beta$(1,1)$) prior, so the share is estimated "
             "conditional on fitting the floored specification rather than shrunk toward "
             "zero; comparison with the floorless specification does not identify the "
             "asymptotic floor. Concentration enters through the "
             "effective line count $n_{\\text{eff}} = 1/H$, well-defined for single-line "
             "reporters ($H=1$).} \\\\\n")

    _write_tex("table38_dispersion_calibration.tex",
               _wrap_table(body, "Robust Bayesian pooling dispersion calibration",
                           "dispersion_calibration", "lrrrp{4cm}"))


def _gen_table37(results):
    """D2 — Event-group operational definition note."""
    content = (
        "\\begin{table}[htbp]\n"
        "\\centering\n"
        "\\caption{Event-group assignment: operational definitions}\n"
        "\\label{tab:event_group_ops}\n"
        "\\begin{tabular}{lp{10cm}}\n"
        "\\toprule\n"
        "\\textbf{Aspect} & \\textbf{Definition} \\\\\n"
        "\\midrule\n"
        "Assignment fields & Each observation is assigned an event-group ID "
        "formed as \\texttt{\\{year\\}\\_\\{cause\\_category\\}}, where "
        "\\texttt{cause\\_category} is derived from the extracted "
        "\\texttt{primary\\_causes} and \\texttt{standardized\\_narrative} fields "
        "via keyword matching (e.g.\\ ``covid'', ``ogden'', ``natural\\_cat''). \\\\\n"
        "\\midrule\n"
        "Pooling rule & Event groups with fewer than 3 syndicate-year observations "
        "are merged into a year-level pooled group (\\texttt{\\{year\\}\\_pooled}). "
        "This ensures each group has sufficient mass for within-group variation "
        "to be estimable in the RE-GLS model. \\\\\n"
        "\\midrule\n"
        "Minimum count & $n_{\\min} = 3$. Groups with $n < 3$ are pooled. \\\\\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )
    _write_tex("table37_event_group_definitions.tex", content)


# ── Main paper-pack orchestrator ─────────────────────────────────────────────

def generate_paper_pack(results, records):
    """Generate all LaTeX tables and matplotlib figures for the paper pack."""
    log("=" * 60)
    log("Generating paper pack...")
    pp = _pp_dir()
    log(f"  Output directory: {pp}")

    table_generators = [
        ("Table 1: Corpus coverage", _gen_table1),
        ("Table 2: Sampling sensitivity", _gen_table2),
        ("Table 3: Size-severity specs", _gen_table3),
        ("Table 4: VaR decomposition", _gen_table4),
        ("Table 5: Worked example event", _gen_table5),
        ("Table 6: Worked example summary", _gen_table6),
        ("Table 7: Persona PYD stats", _gen_table7),
        ("Table 8: Persona tail diagnostics", _gen_table8),
        ("Table 9: Corpus summary", _gen_table9),
        ("Table 10: Data quality", _gen_table10),
        ("Table 11: Reserves distribution", _gen_table11),
        ("Table 12: Decile tests", _gen_table12),
        ("Table 13: Primary RE-GLS", _gen_table13),
        ("Table 14: Dispersion models", _gen_table14),
        ("Table 15: Direction test", _gen_table15),
        ("Table 16: Power-law HHI", _gen_table16),
        ("Table 17: Correlation", _gen_table17),
        ("Table 18: Variance attribution", _gen_table18),
        ("Table 19: HHI dispersion adjusted", _gen_table19),
        ("Table 20: Combined model", _gen_table20),
        ("Table 21: Test portfolios", _gen_table21),
        ("Table 4b: VaR personas", _gen_table4b),
        ("Table 22: Univariate comparison", _gen_table22),
        ("Table 23: HHI-first variance attribution", _gen_table23),
        ("Table 24: Ordering comparison", _gen_table24),
        ("Table 25: Local-donor sensitivity", _gen_table25),
        ("Table 26: Tail sample support", _gen_table26),
        ("Table 27: Tail capital sensitivity", _gen_table27),
        ("Table 28: Bootstrap VaR", _gen_table28),
        ("Table 29: Reserve source audit", _gen_table29),
        ("Table 30: LoB weight source audit", _gen_table30),
        ("Table 31: PYD source audit", _gen_table31),
        ("Table 32: Dual-model workflow", _gen_table32),
        ("Table 33: Exclusions by year", _gen_table33),
        ("Table 34: Subset comparison", _gen_table34),
        ("Table 35: Dispersion robustness", _gen_table35),
        ("Table 36: Event groups", _gen_table36),
        ("Table 37: Event-group definitions", _gen_table37),
        ("Table 38: Dispersion calibration", _gen_table38),
    ]

    figure_generators = [
        ("Fig 1: Yearly observations", _gen_fig_yearly_observations),
        ("Fig 2: p95 trends", _gen_fig2),
        ("Fig 3: Mean excess", _gen_fig3),
        ("Fig 4: Size-severity log-log", _gen_fig4),
        ("Fig 5: VaR decomposition bars", _gen_fig5),
        ("Fig 6: LoB elasticities", _gen_fig6),
        ("Fig: Persona overlays", _gen_fig_persona_overlays),
        ("Fig: PYD distribution", _gen_fig_pyd_distribution),
        ("Fig: Boxplots", _gen_fig_boxplots),
        ("Fig: Size vs PYD", _gen_fig_size_pyd),
        ("Fig: Size vs |PYD%|", _gen_fig_size_abs_pyd),
        ("Fig: Diversification vs |PYD%|", _gen_fig_diversification_abs_pyd),
        ("Fig: Power-law size", _gen_fig_power_law_size),
        ("Fig: HHI severity", _gen_fig_hhi_severity),
        ("Fig: Power-law HHI", _gen_fig_power_law_hhi),
        ("Fig: Diversification vs reserves", _gen_fig_diversification_reserves),
        ("Fig: Size-adjusted HHI", _gen_fig_size_adjusted_hhi),
        ("Fig: HHI-adjusted size", _gen_fig_hhi_adjusted_size),
        ("Fig: Capital decomposition", _gen_fig_capital_decomposition),
    ]

    n_ok = 0
    n_fail = 0

    for label, fn in table_generators:
        try:
            fn(results)
            log(f"  [OK] {label}")
            n_ok += 1
        except Exception as e:
            log(f"  [FAIL] {label}: {e}")
            n_fail += 1

    for label, fn in figure_generators:
        try:
            fn(results)
            log(f"  [OK] {label}")
            n_ok += 1
        except Exception as e:
            log(f"  [FAIL] {label}: {e}")
            n_fail += 1

    log(f"Paper pack complete: {n_ok} succeeded, {n_fail} failed.")
    log("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Vignette Generation
# ─────────────────────────────────────────────────────────────────────────────

VIGNETTE_1_TARGET = {
    "vignette_id": "v1_new_entrant",
    "profile_id": "v1_target",
    "profile_label": "New diversified syndicate (\u00a3500m)",
    "reserve_size": 500.0,
    "lob_weights": {
        "Property": 0.25, "Casualty": 0.20, "Marine": 0.15,
        "Professional Lines": 0.15, "Reinsurance \u2014 Property": 0.10,
        "Accident & Health": 0.10, "Cyber": 0.05,
    },
}

VIGNETTE_2_OLD = {
    "vignette_id": "v2_post_exit",
    "profile_id": "v2_old_profile",
    "profile_label": "Pre-exit diversified syndicate (\u00a3800m)",
    "reserve_size": 800.0,
    "lob_weights": {
        "Property": 0.30, "Casualty": 0.25, "Marine": 0.15,
        "Professional Lines": 0.15, "Reinsurance \u2014 Property": 0.10,
        "Energy": 0.05,
    },
}

VIGNETTE_2_NEW = {
    "vignette_id": "v2_post_exit",
    "profile_id": "v2_new_profile",
    "profile_label": "Post-exit concentrated syndicate (\u00a3650m)",
    "reserve_size": 650.0,
    "lob_weights": {
        "Property": 0.35, "Casualty": 0.30,
        "Professional Lines": 0.18, "Reinsurance \u2014 Property": 0.12,
        "Energy": 0.05,
    },
    "dropped_lob_name": "Marine",
    "dropped_lob_old_weight": 0.15,
    "narrative_reason_label": "Exit of Marine after weak profitability",
}

VIGNETTE_SETTINGS = {
    "donor_subset": "FULL",
    "bootstrap_reps": 500,
    "bootstrap_confidence_level": 0.95,
    "quantile_method": "linear",
    "kde_bandwidth_rule": "scott",
    "random_seed": 42,
    "include_2024": True,
    "adverse_tail_threshold_rule": "positive_signed_ratio",
    "distribution_plot_mode": "histogram_plus_kde",
}

_VIG_COLORS = {"raw": "#2166ac", "adj": "#b2182b", "adj_old": "#b2182b", "adj_new": "#e08214"}


def _size_lambda(R_target, R_donor):
    """Size-only transfer multiplier (R_target/R_donor)^(k-1) from the pooling model.

    Equivalent to dispersion_adjustment with HHI held fixed (concentration cancels)."""
    if COMBINED_MODEL is None or R_donor is None or R_donor <= 0:
        return 1.0
    k = COMBINED_MODEL["k"]
    return (max(R_target, 1e-9) / max(R_donor, 1e-9)) ** (k - 1.0)


def _vig_weights_vec(lob_weights_dict):
    """Convert LoB weights dict to normalised 13-element vector."""
    w = portfolio_weights_vector(lob_weights_dict)
    s = w.sum()
    if s > 0:
        w = w / s
    return w


def _vig_hhi(weights_vec):
    """HHI from normalised weight vector."""
    return float(np.sum(weights_vec ** 2))




def _vig_donor_pool(records):
    """Build eligible donor pool for vignettes and the distortion tool.

    Uses the same ``eligible_for_capital`` flag as the main capital analysis
    (N4) so that the raw distribution is identical in both contexts.  Two
    additional guards are applied:
      - opening reserves must be strictly positive (needed for log-ratio),
      - s_raw_a must be non-None (compute_four_distributions applies this
        filter internally, so we replicate it here for consistency).
    """
    pool = []
    for r in records:
        if not r.get("eligible_for_capital", False):
            continue
        if r.get("s_raw_a") is None:
            continue
        opening = r.get("opening_reserves_gbp_m")
        if opening is None or opening <= 0:
            continue
        pool.append(r)
    return pool


def _select_size_donor(pool, tw, t_size, t_hhi):
    """Select donor maximising |log(R_i / R_q)| with HHI tolerance."""
    scored = []
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        hhi_i = r.get("hhi") or _vig_hhi(np.array(r["weights"], dtype=float))
        lr = abs(math.log(R_i / t_size))
        hd = abs(hhi_i - t_hhi)
        scored.append((r, lr, hd))
    if not scored:
        return None
    adverse = [(r, lr, hd) for r, lr, hd in scored if r["s_raw_a"] > 0]
    cands = adverse if adverse else scored
    hhi_ok = [(r, lr, hd) for r, lr, hd in cands if hd <= 0.05]
    if hhi_ok:
        hhi_ok.sort(key=lambda x: -x[1])
        return hhi_ok[0][0]
    cands.sort(key=lambda x: -x[1])
    top10 = cands[:10]
    top10.sort(key=lambda x: x[2])
    return top10[0][0]


def _select_mix_donor(pool, tw, t_size, t_hhi):
    """Select donor maximising Hellinger distance with size tolerance."""
    scored = []
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        w_i = np.array(r["weights"], dtype=float)
        hd = hellinger_distance(tw, w_i)
        rr = R_i / t_size
        lr = abs(math.log(R_i / t_size))
        scored.append((r, hd, rr, lr))
    if not scored:
        return None
    adverse = [(r, hd, rr, lr) for r, hd, rr, lr in scored if r["s_raw_a"] > 0]
    cands = adverse if adverse else scored
    size_ok = [(r, hd, rr, lr) for r, hd, rr, lr in cands if 0.67 <= rr <= 1.5]
    if size_ok:
        size_ok.sort(key=lambda x: -x[1])
        return size_ok[0][0]
    cands.sort(key=lambda x: -x[1])
    top10 = cands[:10]
    top10.sort(key=lambda x: x[3])
    return top10[0][0]


def _worked_detail(donor, tw, t_size, t_hhi, vignette_id, profile_id):
    """Option-A worked example: transfer one donor severity to the target (size, HHI).

    The transfer is S_adj = S_raw * dispersion_adjustment(t_size, t_hhi, R_i, hhi_i),
    decomposed into a size step (HHI held at the donor's) and a concentration step
    (HHI moved to target).  There is no line-level projection under Option A.
    """
    R_i = donor["opening_reserves_gbp_m"]
    w_i = np.array(donor["weights"], dtype=float)
    hhi_i = donor.get("hhi") or _vig_hhi(w_i)
    S_raw = donor["s_raw_a"]

    lam_size = dispersion_adjustment(t_size, hhi_i, R_i, hhi_i)   # size only (HHI cancels)
    lam_full = dispersion_adjustment(t_size, t_hhi, R_i, hhi_i)   # size + concentration
    lam_conc = lam_full / lam_size if lam_size != 0 else 1.0
    S_size = S_raw * lam_size
    S_adj = S_raw * lam_full

    def _pct(delta, base):
        return round(delta / abs(base) * 100, 2) if base != 0 else None

    return {
        "vignette_id": vignette_id,
        "target_profile_id": profile_id,
        "donor_observation_id": f"{donor['syndicate']}_{donor['year']}",
        "donor_syndicate_id": donor["syndicate"],
        "donor_report_year": donor["year"],
        "donor_reserve_size": R_i,
        "donor_hhi": round(hhi_i, 6),
        "donor_signed_pyd_amount": donor.get("pyd_gbp_m"),
        "donor_signed_pyd_ratio": S_raw,
        "target_reserve_size": t_size,
        "target_hhi": round(t_hhi, 6),
        "S_raw": round(S_raw, 6),
        "S_size_adjusted": round(S_size, 6),
        "S_adj": round(S_adj, 6),
        "size_multiplier": round(lam_size, 6),
        "concentration_multiplier": round(lam_conc, 6),
        "total_multiplier": round(lam_full, 6),
        "raw_to_size_abs": round(S_size - S_raw, 6),
        "size_to_adj_abs": round(S_adj - S_size, 6),
        "raw_to_adj_abs": round(S_adj - S_raw, 6),
        "raw_to_size_pct": _pct(S_size - S_raw, S_raw),
        "size_to_adj_pct": _pct(S_adj - S_size, S_size),
        "raw_to_adj_pct": _pct(S_adj - S_raw, S_raw),
        "hellinger_distance": round(hellinger_distance(tw, w_i), 6),
        "log_reserve_ratio_to_target": round(math.log(R_i / t_size), 6),
    }


def _compute_target_dists(pool, tw, t_size):
    """Option-A transfer of every donor onto target (t_size, HHI(tw)).

    Returns (raw, size_adjusted, fully_adjusted, obs_ids): the raw severity, the
    size-only-adjusted severity, and the size+concentration-adjusted severity.
    """
    t_hhi = _vig_hhi(tw)
    raw, mix, adj = [], [], []
    obs_ids = []
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        if R_i is None or R_i <= 0:
            continue
        S_raw = r["s_raw_a"]
        if S_raw is None:
            continue
        hhi_i = r.get("hhi") or _vig_hhi(np.array(r["weights"], dtype=float))
        S_size = S_raw * dispersion_adjustment(t_size, hhi_i, R_i, hhi_i)   # size only
        S_adj = S_raw * dispersion_adjustment(t_size, t_hhi, R_i, hhi_i)    # size + concentration
        raw.append(S_raw)
        mix.append(S_size)
        adj.append(S_adj)
        obs_ids.append(f"{r['syndicate']}_{r['year']}")
    return raw, mix, adj, obs_ids


def _dist_stats(arr, label):
    """Compute distribution statistics."""
    a = np.array(arr, dtype=float)
    n = len(a)
    if n == 0:
        return {"distribution_label": label, "n_total": 0}
    return {
        "distribution_label": label,
        "n_total": n,
        "n_adverse": int(np.sum(a > 0)),
        "mean": round(float(np.mean(a)), 6),
        "standard_deviation": round(float(np.std(a, ddof=1)), 6) if n > 1 else 0.0,
        "q75": round(float(np.percentile(a, 75)), 6),
        "var99": round(float(np.percentile(a, 99)), 6),
        "var995": round(float(np.percentile(a, 99.5)), 6),
    }


def _bootstrap_ci(pool, tw, t_size, B=500, seed=42, conf=0.95):
    """Bootstrap CIs for VaR99/VaR99.5 with syndicate-level resampling."""
    t_hhi = _vig_hhi(tw)
    synd_map = defaultdict(list)
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        if R_i is None or R_i <= 0 or r["s_raw_a"] is None:
            continue
        hhi_i = r.get("hhi") or _vig_hhi(np.array(r["weights"], dtype=float))
        synd_map[r["syndicate"]].append({
            "S_raw": r["s_raw_a"],
            "S_adj": r["s_raw_a"] * dispersion_adjustment(t_size, t_hhi, R_i, hhi_i),
        })
    sids = list(synd_map.keys())
    n_s = len(sids)
    if n_s < 5:
        return None
    rng = np.random.RandomState(seed)
    b_raw99, b_raw995, b_adj99, b_adj995 = [], [], [], []
    for _ in range(B):
        idx = rng.choice(n_s, size=n_s, replace=True)
        rs, as_ = [], []
        for i in idx:
            for o in synd_map[sids[i]]:
                rs.append(o["S_raw"])
                as_.append(o["S_adj"])
        if len(rs) < 10:
            continue
        b_raw99.append(float(np.percentile(rs, 99)))
        b_raw995.append(float(np.percentile(rs, 99.5)))
        b_adj99.append(float(np.percentile(as_, 99)))
        b_adj995.append(float(np.percentile(as_, 99.5)))
    alpha = (1 - conf) / 2
    lo, hi = alpha * 100, (1 - alpha) * 100

    def _ci(a):
        if len(a) < 10:
            return (None, None)
        return (round(float(np.percentile(a, lo)), 6), round(float(np.percentile(a, hi)), 6))

    return {
        "raw_var99": _ci(b_raw99), "raw_var995": _ci(b_raw995),
        "adj_var99": _ci(b_adj99), "adj_var995": _ci(b_adj995),
        "B": len(b_raw99), "confidence_level": conf,
    }


def _shapley_v1(pool, tw, t_size):
    """Shapley decomposition into size and concentration effects for V1 (Option A)."""
    t_hhi = _vig_hhi(tw)
    raw, szo, czo, adj = [], [], [], []
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        if R_i is None or R_i <= 0 or r["s_raw_a"] is None:
            continue
        S_raw = r["s_raw_a"]
        hhi_i = r.get("hhi") or _vig_hhi(np.array(r["weights"], dtype=float))
        raw.append(S_raw)
        szo.append(S_raw * dispersion_adjustment(t_size, hhi_i, R_i, hhi_i))  # size only
        czo.append(S_raw * dispersion_adjustment(R_i, t_hhi, R_i, hhi_i))     # concentration only
        adj.append(S_raw * dispersion_adjustment(t_size, t_hhi, R_i, hhi_i))  # both
    result = {}
    for mn, q in [("q75", 75), ("var99", 99), ("var995", 99.5)]:
        vr = float(np.percentile(raw, q))
        vs = float(np.percentile(szo, q))
        vc = float(np.percentile(czo, q))
        va = float(np.percentile(adj, q))
        se = 0.5 * ((vs - vr) + (va - vc))
        ce = 0.5 * ((vc - vr) + (va - vs))
        result[mn] = {
            "metric": mn, "raw_metric": round(vr, 6),
            "size_adjusted_metric": round(vs, 6),
            "fully_adjusted_metric": round(va, 6),
            "size_effect": round(se, 6), "concentration_effect": round(ce, 6),
        }
    return result


def _shapley_v2(pool, old_w, new_w, old_size, new_size):
    """Shapley decomposition for V2: size-change vs concentration-change (old->new, Option A)."""
    old_hhi = _vig_hhi(old_w)
    new_hhi = _vig_hhi(new_w)
    oo, on, no, nn = [], [], [], []
    for r in pool:
        R_i = r["opening_reserves_gbp_m"]
        if R_i is None or R_i <= 0 or r["s_raw_a"] is None:
            continue
        S_raw = r["s_raw_a"]
        hhi_i = r.get("hhi") or _vig_hhi(np.array(r["weights"], dtype=float))
        oo.append(S_raw * dispersion_adjustment(old_size, old_hhi, R_i, hhi_i))
        on.append(S_raw * dispersion_adjustment(old_size, new_hhi, R_i, hhi_i))
        no.append(S_raw * dispersion_adjustment(new_size, old_hhi, R_i, hhi_i))
        nn.append(S_raw * dispersion_adjustment(new_size, new_hhi, R_i, hhi_i))
    result = {}
    for mn, q in [("q75", 75), ("var99", 99), ("var995", 99.5)]:
        voo = float(np.percentile(oo, q))
        von = float(np.percentile(on, q))
        vno = float(np.percentile(no, q))
        vnn = float(np.percentile(nn, q))
        se = 0.5 * ((vno - voo) + (vnn - von))
        ce = 0.5 * ((von - voo) + (vnn - vno))
        result[mn] = {
            "metric": mn, "old_profile_metric": round(voo, 6),
            "new_profile_metric": round(vnn, 6),
            "concentration_change_effect": round(ce, 6), "size_change_effect": round(se, 6),
        }
    return result


# ── Vignette output writers ──────────────────────────────────────────────────

def _vig_write_table(out_dir, basename, rows, fieldnames, caption="", label=""):
    """Write a table in CSV, XLSX, and LaTeX formats."""
    # CSV
    with _open_w(out_dir / f"{basename}.csv", "w", newline="", encoding="utf-8") as f:
        w = _csv_mod.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    # XLSX
    if _HAS_XLSX:
        wb = _XlWorkbook()
        ws = wb.active
        ws.title = basename[:31]
        ws.append(fieldnames)
        for row in rows:
            ws.append([row.get(k, "") for k in fieldnames])
        _save_workbook_with_retry(wb, out_dir / f"{basename}.xlsx")
    # LaTeX
    ncols = len(fieldnames)
    hdr = " & ".join(f"\\textbf{{{h}}}" for h in fieldnames) + " \\\\"
    body_lines = []
    for row in rows:
        cells = []
        for k in fieldnames:
            v = row.get(k, "")
            if isinstance(v, float):
                cells.append(f"{v:.4f}" if abs(v) < 100 else f"{v:.1f}")
            else:
                cells.append(str(v))
        body_lines.append(" & ".join(cells) + " \\\\")
    tex = (
        "\\begin{table}[htbp]\n\\centering\n"
        + (f"\\caption{{{caption}}}\n" if caption else "")
        + (f"\\label{{tab:{label}}}\n" if label else "")
        + f"\\begin{{tabular}}{{{'l' * ncols}}}\n\\toprule\n"
        + hdr + "\n\\midrule\n"
        + "\n".join(body_lines) + "\n"
        + "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    with _open_w(out_dir / f"{basename}.tex", "w", encoding="utf-8") as f:
        f.write(tex)


def _save_with_retry(fig, path, attempts=4, **kw):
    """savefig that retries a transient Windows lock (OSError errno 22 on a file
    the indexer still holds) instead of aborting a multi-hour run."""
    import time
    for i in range(attempts):
        try:
            fig.savefig(path, **kw)
            return
        except OSError as e:
            if getattr(e, "errno", None) != 22 or i == attempts - 1:
                raise
            time.sleep(1.5 * (i + 1))


def _open_w(path, mode="w", attempts=4, **kw):
    """open() for writing that retries the transient Windows lock (errno 22)."""
    import time
    for i in range(attempts):
        try:
            return open(path, mode, **kw)
        except OSError as e:
            if getattr(e, "errno", None) != 22 or i == attempts - 1:
                raise
            time.sleep(1.5 * (i + 1))


def _save_workbook_with_retry(wb, path, attempts=4):
    import time
    for i in range(attempts):
        try:
            wb.save(path)
            return
        except OSError as e:
            if getattr(e, "errno", None) != 22 or i == attempts - 1:
                raise
            time.sleep(1.5 * (i + 1))


VIGNETTE_README = (
    "# Vignette workings\n\n"
    "Generated by `src/run_analysis.py`. The `worked_example_size_mismatch.*` and "
    "`worked_example_mix_mismatch.*` files are donor-selection illustrations: the donor "
    "with the largest size mismatch inside a concentration tolerance, and the donor with the "
    "largest Hellinger mix distance inside a size tolerance. They are NOT the paper's Table 7 "
    "worked example, which `src/worked_example_donor.py` writes to "
    "`results/worked_example_donors.json`.\n")


def _vig_write_readme(out_dir):
    with _open_w(out_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(VIGNETTE_README)


def _vig_save_fig(fig, out_dir, basename):
    """Save figure as PNG and PDF."""
    _save_with_retry(fig, out_dir / f"{basename}.png", dpi=_PP_DPI, bbox_inches="tight")
    _save_with_retry(fig, out_dir / f"{basename}.pdf", bbox_inches="tight",
                     metadata={"CreationDate": None})
    plt.close(fig)


# ── Vignette figure generators ───────────────────────────────────────────────

def _vig_distribution_plot(out_dir, series, subtitle, basename):
    """Histogram + KDE distribution plot with vertical quantile markers."""
    fig, ax = plt.subplots(figsize=(10, 5))
    all_vals = []
    for label, vals, color in series:
        arr = np.array(vals, dtype=float)
        all_vals.extend(vals)
        ax.hist(arr, bins=40, density=True, alpha=0.25, color=color, label=f"{label} (hist)")
        # KDE (Scott's rule)
        n = len(arr)
        if n > 1:
            std = float(np.std(arr, ddof=1))
            bw = 1.06 * std * n ** (-0.2) if std > 0 else 0.1
            x_grid = np.linspace(float(arr.min()) - 3 * bw, float(arr.max()) + 3 * bw, 300)
            kde = np.zeros_like(x_grid)
            for v in arr:
                kde += np.exp(-0.5 * ((x_grid - v) / bw) ** 2) / (bw * math.sqrt(2 * math.pi))
            kde /= n
            ax.plot(x_grid, kde, color=color, lw=2, label=f"{label} (KDE)")
        # Markers
        markers = [
            ("mean", float(np.mean(arr)), "--"),
            ("Q75", float(np.percentile(arr, 75)), "-."),
            ("VaR99", float(np.percentile(arr, 99)), ":"),
            ("VaR99.5", float(np.percentile(arr, 99.5)), "-"),
        ]
        for mlabel, mval, mstyle in markers:
            ax.axvline(mval, color=color, ls=mstyle, lw=1, alpha=0.7)
    ax.set_xlabel("Signed PYD ratio")
    ax.set_ylabel("Density")
    ax.set_title("Distribution of signed PYD ratio: raw vs adjusted")
    if subtitle:
        ax.set_title(f"Distribution of signed PYD ratio\n{subtitle}", fontsize=10)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _vig_save_fig(fig, out_dir, basename)
    # Save plot data
    plot_data_rows = []
    for label, vals, _ in series:
        arr = np.array(vals, dtype=float)
        for i, v in enumerate(sorted(arr)):
            plot_data_rows.append({"series": label, "index": i, "value": round(v, 6)})
    _vig_write_table(out_dir, f"{basename}_data", plot_data_rows,
                     ["series", "index", "value"],
                     f"Underlying data for {basename}", f"{basename}_data")


def _vig_tail_plot(out_dir, series, basename):
    """Tail exceedance (empirical survivor) plot on adverse side only."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, vals, color in series:
        arr = np.array(vals, dtype=float)
        pos = np.sort(arr[arr > 0])
        if len(pos) == 0:
            continue
        n = len(pos)
        exceedance = np.arange(n, 0, -1) / n
        ax.step(pos, exceedance, where="post", color=color, lw=2, label=label)
        # Mark VaR99 and VaR99.5 from full distribution
        full_sorted = np.sort(arr)
        v99 = float(np.percentile(full_sorted, 99))
        v995 = float(np.percentile(full_sorted, 99.5))
        ax.axvline(v99, color=color, ls=":", lw=1, alpha=0.7)
        ax.axvline(v995, color=color, ls="--", lw=1, alpha=0.7)
        ax.text(v99, 0.02, "99%", fontsize=7, color=color, rotation=90, va="bottom")
        ax.text(v995, 0.02, "99.5%", fontsize=7, color=color, rotation=90, va="bottom")
    ax.set_xlabel("Signed PYD ratio (adverse side only)")
    ax.set_ylabel("Exceedance probability")
    ax.set_title("Tail exceedance plot")
    ax.set_yscale("log")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")
    fig.tight_layout()
    _vig_save_fig(fig, out_dir, basename)
    # Save plot data
    plot_data_rows = []
    for label, vals, _ in series:
        arr = np.array(vals, dtype=float)
        pos = np.sort(arr[arr > 0])
        n = len(pos)
        for i, v in enumerate(pos):
            plot_data_rows.append({
                "series": label, "value": round(float(v), 6),
                "exceedance_probability": round((n - i) / n, 6),
            })
    _vig_write_table(out_dir, f"{basename}_data", plot_data_rows,
                     ["series", "value", "exceedance_probability"],
                     f"Underlying data for {basename}", f"{basename}_data")


def _vig_waterfall_plot(out_dir, old_val, size_eff, mix_eff, new_val, metric_label, basename):
    """Waterfall chart for V2 old→new decomposition."""
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [f"Old {metric_label}", "Size effect", "Concentration effect", f"New {metric_label}"]
    values = [old_val, size_eff, mix_eff, new_val]
    colors = ["#2166ac", "#66c2a5", "#fc8d62", "#b2182b"]
    bottoms = [0, old_val, old_val + size_eff, 0]
    bar_vals = [old_val, size_eff, mix_eff, new_val]
    ax.bar(labels, bar_vals, bottom=bottoms, color=colors, edgecolor="black", lw=0.5)
    for i, (lbl, bv, bt) in enumerate(zip(labels, bar_vals, bottoms)):
        ax.text(i, bt + bv + 0.002, f"{bv:.4f}", ha="center", va="bottom", fontsize=9)
    # Connector lines
    for i in range(2):
        top = bottoms[i] + bar_vals[i]
        ax.plot([i + 0.4, i + 0.6], [top, top], color="gray", lw=0.8)
    ax.set_ylabel(metric_label)
    ax.set_title(f"Profile transition decomposition: {metric_label}")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    _vig_save_fig(fig, out_dir, basename)
    # Save plot data
    plot_data = [{"bar": labels[i], "value": round(values[i], 6), "bottom": round(bottoms[i], 6)}
                 for i in range(4)]
    _vig_write_table(out_dir, f"{basename}_data", plot_data,
                     ["bar", "value", "bottom"],
                     f"Underlying data for {basename}", f"{basename}_data")


# ── Vignette metadata and snippet generators ─────────────────────────────────

DETERMINISTIC_RUN_ID = None


def _vig_metadata(vignette_id, target_specs, settings):
    """Generate metadata JSON for a vignette run."""
    git_hash = "unknown"
    try:
        result = _subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(SCRIPT_DIR))
        if result.returncode == 0:
            git_hash = result.stdout.strip()
    except Exception:
        pass
    cm = COMBINED_MODEL if COMBINED_MODEL else {}
    return {
        "run_id": DETERMINISTIC_RUN_ID or str(uuid.uuid4()),
        "spec_version": "2.0",
        "paper_version_label": "revised",
        "git_commit_or_hash": git_hash,
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": settings["random_seed"],
        "donor_subset": settings["donor_subset"],
        "include_2024": settings["include_2024"],
        "bootstrap_reps": settings["bootstrap_reps"],
        "bootstrap_confidence_level": settings["bootstrap_confidence_level"],
        "quantile_method": settings["quantile_method"],
        "kde_bandwidth_rule": settings["kde_bandwidth_rule"],
        "operator": "option_A_pooling: S_adj = S_raw * (R_t/R_o)^(k-1) * (H_o/H_t)^(gamma*(k-1))",
        "pooling_exponent_k": cm.get("k"),
        "concentration_exponent_gamma": cm.get("gamma"),
        "tail_index_nu": cm.get("nu"),
        "reference_size": cm.get("reference_size"),
        "distribution_plot_mode": settings["distribution_plot_mode"],
        "environment_python_version": sys.version,
        "environment_package_lock_hash": hashlib.md5(
            (SCRIPT_DIR / "requirements.txt").read_bytes()).hexdigest()
            if (SCRIPT_DIR / "requirements.txt").exists() else None,
        "vignette_id": vignette_id,
        "target_profiles": target_specs,
    }


def _vig_snippet(vignette_id, raw_stats, adj_stats, decomp, pool_n,
                 ts99_raw, ts995_raw, ts99_adj, ts995_adj, extra=""):
    """Generate 100-150 word narrative snippet."""
    # Determine direction
    v99_raw = raw_stats["var99"]
    v99_adj = adj_stats["var99"]
    v995_raw = raw_stats["var995"]
    v995_adj = adj_stats["var995"]
    direction = "increases" if v995_adj > v995_raw else "decreases"

    # Biggest quantile change
    label_to_key = {"Q75": "q75", "VaR99": "var99", "VaR99.5": "var995"}
    changes = {
        "Q75": abs(adj_stats["q75"] - raw_stats["q75"]),
        "VaR99": abs(v99_adj - v99_raw),
        "VaR99.5": abs(v995_adj - v995_raw),
    }
    biggest = max(changes, key=changes.get)
    biggest_key = label_to_key[biggest]

    # Concentration vs size dominance
    d995 = decomp.get("var995", {})
    conc_eff = abs(d995.get("concentration_effect", d995.get("concentration_change_effect", 0)))
    size_eff = abs(d995.get("size_effect", d995.get("size_change_effect", 0)))
    dominant = "concentration adjustment" if conc_eff > size_eff else "size adjustment"

    lines = [
        f"Transferring {pool_n} market donor observations onto the target portfolio basis "
        f"{direction} the adverse tail of the signed PYD ratio distribution. ",
        f"The largest absolute change occurs at {biggest} "
        f"({raw_stats.get(biggest_key, 0):.4f} raw vs "
        f"{adj_stats.get(biggest_key, 0):.4f} adjusted). ",
        f"The {dominant} dominates the distortion at VaR99.5 "
        f"(concentration effect {d995.get('concentration_effect', d995.get('concentration_change_effect', 0)):.4f}, "
        f"size effect {d995.get('size_effect', d995.get('size_change_effect', 0)):.4f}). ",
        f"The donor pool comprises {pool_n} observations with "
        f"{raw_stats['n_adverse']} adverse outcomes. ",
        f"Tail support: {ts99_adj} observations beyond VaR99, "
        f"{ts995_adj} beyond VaR99.5 on the adjusted distribution. ",
        extra,
        f"For this target and this donor library, the comparison illustrates how "
        f"naive pooling of market reserve movements would misstate the transferred "
        f"1-in-200; it does not establish the target syndicate's true 1-in-200 "
        f"reserve risk. "
        f"Basis: these figures apply the size and concentration scale ratio only. "
        f"The manuscript's headline stresses additionally apply the RITC tail-regime "
        f"quantile map, so they are not the same quantity and will not match "
        f"(V1 VaR99.5 is 0.393 there).",
    ]
    return "".join(lines).strip()


# ── Vignette 1 orchestrator ──────────────────────────────────────────────────

def _generate_vignette_1(pool, records):
    """Generate all Vignette 1 outputs."""
    log("  Generating Vignette 1: new entrant...")
    out_dir = SCRIPT_DIR / "vignettes" / "vignette-1"
    out_dir.mkdir(parents=True, exist_ok=True)
    tgt = VIGNETTE_1_TARGET
    tw = _vig_weights_vec(tgt["lob_weights"])
    t_size = tgt["reserve_size"]
    t_hhi = _vig_hhi(tw)
    vid = tgt["vignette_id"]
    pid = tgt["profile_id"]

    # 1) Target profile card
    n_total = len(pool)
    raw_vals, mix_vals, adj_vals, obs_ids = _compute_target_dists(pool, tw, t_size)
    n_adverse = sum(1 for v in raw_vals if v > 0)
    ts99 = max(1, int(math.ceil(len(raw_vals) * 0.01)))
    ts995 = max(1, int(math.ceil(len(raw_vals) * 0.005)))
    ts99_adj = max(1, int(math.ceil(len(adj_vals) * 0.01)))
    ts995_adj = max(1, int(math.ceil(len(adj_vals) * 0.005)))

    profile_card = {
        "vignette_id": vid, "profile_id": pid,
        "profile_label": tgt["profile_label"],
        "reserve_size": t_size,
        "lob_weights_json": tgt["lob_weights"],
        "hhi": round(t_hhi, 6),
        "donor_subset": VIGNETTE_SETTINGS["donor_subset"],
        "donor_count": n_total,
        "adverse_donor_count": n_adverse,
        "tail_support_count_var99": ts99,
        "tail_support_count_var995": ts995,
    }
    with _open_w(out_dir / "target_profile.json", "w", encoding="utf-8") as f:
        json.dump(profile_card, f, indent=2)
    # Target profile table
    card_row = {k: v for k, v in profile_card.items() if k != "lob_weights_json"}
    for lob, wt in tgt["lob_weights"].items():
        card_row[f"w_{lob}"] = wt
    card_fields = list(card_row.keys())
    _vig_write_table(out_dir, "target_profile_table", [card_row], card_fields,
                     "Target profile card", "v1_target_profile")

    # 2) Donor selection
    size_donor = _select_size_donor(pool, tw, t_size, t_hhi)
    mix_donor = _select_mix_donor(pool, tw, t_size, t_hhi)
    _vig_write_readme(out_dir)
    donor_sel_rows = []
    for sel_type, donor in [("size_mismatch", size_donor), ("mix_mismatch", mix_donor)]:
        if donor is None:
            continue
        w_d = np.array(donor["weights"], dtype=float)
        donor_sel_rows.append({
            "selection_type": sel_type,
            "observation_id": f"{donor['syndicate']}_{donor['year']}",
            "syndicate_id": donor["syndicate"],
            "report_year": donor["year"],
            "opening_reserves": donor["opening_reserves_gbp_m"],
            "signed_pyd_amount": donor.get("pyd_gbp_m"),
            "signed_pyd_ratio": donor["s_raw_a"],
            "hhi": donor.get("hhi") or _vig_hhi(w_d),
            "hellinger_distance": round(hellinger_distance(tw, w_d), 6),
            "log_reserve_ratio_to_target": round(math.log(donor["opening_reserves_gbp_m"] / t_size), 6),
            "selection_reason": f"Max {'|log(R_i/R_q)|' if sel_type == 'size_mismatch' else 'Hellinger distance'} "
                                f"within {'HHI' if sel_type == 'size_mismatch' else 'size'} tolerance",
        })
    ds_fields = ["selection_type", "observation_id", "syndicate_id", "report_year",
                 "opening_reserves", "signed_pyd_amount", "signed_pyd_ratio",
                 "hhi", "hellinger_distance", "log_reserve_ratio_to_target", "selection_reason"]
    _vig_write_table(out_dir, "donor_selection", donor_sel_rows, ds_fields,
                     "Donor selection for worked examples", "v1_donor_selection")

    # 3) Worked examples
    for sel_type, donor in [("size_mismatch", size_donor), ("mix_mismatch", mix_donor)]:
        if donor is None:
            continue
        detail = _worked_detail(donor, tw, t_size, t_hhi, vid, pid)
        # Write JSON with full detail
        with _open_w(out_dir / f"worked_example_{sel_type}.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, indent=2)
        # Write size/concentration decomposition table (Option A; no line-level projection)
        we_row = {
            "stage": ["raw donor", "after size", "after concentration (adjusted)"],
            "severity": [detail["S_raw"], detail["S_size_adjusted"], detail["S_adj"]],
            "multiplier": [1.0, detail["size_multiplier"], detail["concentration_multiplier"]],
        }
        we_rows = [{"stage": we_row["stage"][i], "severity": we_row["severity"][i],
                    "multiplier": we_row["multiplier"][i]} for i in range(3)]
        _vig_write_table(out_dir, f"worked_example_{sel_type}", we_rows,
                         ["stage", "severity", "multiplier"],
                         f"Worked example: {sel_type.replace('_', ' ')} donor --- size/concentration transfer",
                         f"v1_we_{sel_type}")

    # 4) Distribution stats
    raw_stats = _dist_stats(raw_vals, "Raw market")
    adj_stats = _dist_stats(adj_vals, "Adjusted target")
    # Delta row
    delta_row = {"distribution_label": "raw\u2192adjusted delta"}
    for k in ["mean", "standard_deviation", "q75", "var99", "var995"]:
        if k in raw_stats and k in adj_stats:
            delta_row[k] = round(adj_stats[k] - raw_stats[k], 6)
            delta_row[f"{k}_pct"] = round((adj_stats[k] - raw_stats[k]) / abs(raw_stats[k]) * 100, 2) if raw_stats[k] != 0 else None
    stat_fields = ["distribution_label", "n_total", "n_adverse",
                   "mean", "standard_deviation", "q75", "var99", "var995"]
    _vig_write_table(out_dir, "distribution_stats",
                     [raw_stats, adj_stats, delta_row], stat_fields,
                     "Distribution statistics: raw vs adjusted", "v1_dist_stats")

    # 5) Bootstrap + tail support
    boot = _bootstrap_ci(pool, tw, t_size,
                         B=VIGNETTE_SETTINGS["bootstrap_reps"],
                         seed=VIGNETTE_SETTINGS["random_seed"],
                         conf=VIGNETTE_SETTINGS["bootstrap_confidence_level"])
    boot_rows = []
    for dist_label, var_key_prefix in [("Raw market", "raw"), ("Adjusted target", "adj")]:
        stats = raw_stats if var_key_prefix == "raw" else adj_stats
        for metric, var_key in [("VaR99", f"{var_key_prefix}_var99"), ("VaR99.5", f"{var_key_prefix}_var995")]:
            ci = boot[var_key] if boot else (None, None)
            # tail support count
            arr = np.array(raw_vals if var_key_prefix == "raw" else adj_vals, dtype=float)
            pt = stats["var99"] if metric == "VaR99" else stats["var995"]
            tsc = int(np.sum(arr >= pt))
            boot_rows.append({
                "distribution_label": dist_label,
                "metric": metric,
                "point_estimate": pt,
                "ci_lower": ci[0],
                "ci_upper": ci[1],
                "tail_support_count": tsc,
                "bootstrap_reps": VIGNETTE_SETTINGS["bootstrap_reps"],
                "confidence_level": VIGNETTE_SETTINGS["bootstrap_confidence_level"],
            })
    boot_fields = ["distribution_label", "metric", "point_estimate",
                   "ci_lower", "ci_upper", "tail_support_count",
                   "bootstrap_reps", "confidence_level"]
    _vig_write_table(out_dir, "tail_support_bootstrap", boot_rows, boot_fields,
                     "Bootstrap confidence intervals and tail support", "v1_boot")

    # 6) Decomposition summary
    decomp = _shapley_v1(pool, tw, t_size)
    decomp_rows = [decomp[mn] for mn in ["q75", "var99", "var995"]]
    decomp_fields = ["metric", "raw_metric", "size_adjusted_metric",
                     "fully_adjusted_metric", "size_effect", "concentration_effect"]
    _vig_write_table(out_dir, "decomposition_summary", decomp_rows, decomp_fields,
                     "Shapley decomposition of the pure-rescale change: size and "
                     "concentration effects (no tail-regime step is applied in this "
                     "supplementary basis, so two players are the complete decomposition; "
                     "the manuscript's raw-to-adjusted decomposition adds the tail-regime "
                     "player)", "v1_decomp")

    # 7) Distribution plot
    subtitle = (f"Donor pool: {VIGNETTE_SETTINGS['donor_subset']} subset, "
                f"n={len(raw_vals)}, adverse={sum(1 for v in raw_vals if v > 0)}")
    _vig_distribution_plot(out_dir, [
        ("Raw market", raw_vals, _VIG_COLORS["raw"]),
        ("Adjusted target", adj_vals, _VIG_COLORS["adj"]),
    ], subtitle, "distribution_plot")

    # 8) Tail exceedance plot
    _vig_tail_plot(out_dir, [
        ("Raw market", raw_vals, _VIG_COLORS["raw"]),
        ("Adjusted target", adj_vals, _VIG_COLORS["adj"]),
    ], "tail_exceedance_plot")

    # 9) Summary snippet
    snippet = _vig_snippet(vid, raw_stats, adj_stats, decomp, len(raw_vals),
                           ts99, ts995, ts99_adj, ts995_adj)
    with _open_w(out_dir / "summary_snippet.md", "w", encoding="utf-8") as f:
        f.write(snippet)

    # 10) Metadata
    meta = _vig_metadata(vid, [tgt], VIGNETTE_SETTINGS)
    with _open_w(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    log(f"  Vignette 1 complete: {len(raw_vals)} donors, {len(list(out_dir.iterdir()))} files")


# ── Vignette 2 orchestrator ──────────────────────────────────────────────────

def _generate_vignette_2(pool, records):
    """Generate all Vignette 2 outputs."""
    log("  Generating Vignette 2: post-exit...")
    out_dir = SCRIPT_DIR / "vignettes" / "vignette-2"
    out_dir.mkdir(parents=True, exist_ok=True)
    old = VIGNETTE_2_OLD
    new = VIGNETTE_2_NEW
    old_w = _vig_weights_vec(old["lob_weights"])
    new_w = _vig_weights_vec(new["lob_weights"])
    old_size = old["reserve_size"]
    new_size = new["reserve_size"]
    old_hhi = _vig_hhi(old_w)
    new_hhi = _vig_hhi(new_w)
    vid = old["vignette_id"]

    # 1) Target transition card
    transition = {
        "vignette_id": vid,
        "old_profile_label": old["profile_label"],
        "new_profile_label": new["profile_label"],
        "old_reserve_size": old_size,
        "new_reserve_size": new_size,
        "old_lob_weights_json": old["lob_weights"],
        "new_lob_weights_json": new["lob_weights"],
        "old_hhi": round(old_hhi, 6),
        "new_hhi": round(new_hhi, 6),
        "dropped_lob_name": new["dropped_lob_name"],
        "dropped_lob_old_weight": new["dropped_lob_old_weight"],
        "reserve_size_pct_change": round((new_size - old_size) / old_size * 100, 2),
        "hhi_change": round(new_hhi - old_hhi, 6),
        "narrative_reason_label": new["narrative_reason_label"],
        "donor_subset": VIGNETTE_SETTINGS["donor_subset"],
        "donor_count": len(pool),
        "adverse_donor_count": sum(1 for r in pool if r["s_raw_a"] is not None and r["s_raw_a"] > 0),
    }
    with _open_w(out_dir / "target_transition.json", "w", encoding="utf-8") as f:
        json.dump(transition, f, indent=2)
    # Transition table
    trans_row = {k: v for k, v in transition.items()
                 if k not in ("old_lob_weights_json", "new_lob_weights_json")}
    trans_fields = list(trans_row.keys())
    _vig_write_table(out_dir, "target_transition_table", [trans_row], trans_fields,
                     "Target profile transition card", "v2_transition")

    # 2) Donor selection (relative to NEW profile)
    size_donor = _select_size_donor(pool, new_w, new_size, new_hhi)
    mix_donor = _select_mix_donor(pool, new_w, new_size, new_hhi)
    _vig_write_readme(out_dir)
    donor_sel_rows = []
    for sel_type, donor in [("size_mismatch", size_donor), ("mix_mismatch", mix_donor)]:
        if donor is None:
            continue
        w_d = np.array(donor["weights"], dtype=float)
        donor_sel_rows.append({
            "selection_type": sel_type,
            "observation_id": f"{donor['syndicate']}_{donor['year']}",
            "syndicate_id": donor["syndicate"],
            "report_year": donor["year"],
            "opening_reserves": donor["opening_reserves_gbp_m"],
            "signed_pyd_amount": donor.get("pyd_gbp_m"),
            "signed_pyd_ratio": donor["s_raw_a"],
            "hhi": donor.get("hhi") or _vig_hhi(w_d),
            "hellinger_distance": round(hellinger_distance(new_w, w_d), 6),
            "log_reserve_ratio_to_target": round(math.log(donor["opening_reserves_gbp_m"] / new_size), 6),
            "selection_reason": f"Max {'|log(R_i/R_q)|' if sel_type == 'size_mismatch' else 'Hellinger distance'} "
                                f"within {'HHI' if sel_type == 'size_mismatch' else 'size'} tolerance",
        })
    ds_fields = ["selection_type", "observation_id", "syndicate_id", "report_year",
                 "opening_reserves", "signed_pyd_amount", "signed_pyd_ratio",
                 "hhi", "hellinger_distance", "log_reserve_ratio_to_target", "selection_reason"]
    _vig_write_table(out_dir, "donor_selection", donor_sel_rows, ds_fields,
                     "Donor selection for worked examples (new profile)", "v2_donor_selection")

    # 3) Worked examples (relative to NEW profile)
    for sel_type, donor in [("size_mismatch", size_donor), ("mix_mismatch", mix_donor)]:
        if donor is None:
            continue
        detail = _worked_detail(donor, new_w, new_size, new_hhi, vid, new["profile_id"])
        with _open_w(out_dir / f"worked_example_{sel_type}.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, indent=2)
        we_rows = [
            {"stage": "raw donor", "severity": detail["S_raw"], "multiplier": 1.0},
            {"stage": "after size", "severity": detail["S_size_adjusted"], "multiplier": detail["size_multiplier"]},
            {"stage": "after concentration (adjusted)", "severity": detail["S_adj"], "multiplier": detail["concentration_multiplier"]},
        ]
        _vig_write_table(out_dir, f"worked_example_{sel_type}", we_rows,
                         ["stage", "severity", "multiplier"],
                         f"Worked example: {sel_type.replace('_', ' ')} donor --- size/concentration transfer",
                         f"v2_we_{sel_type}")

    # 4) Compute distributions: raw, adj_old, adj_new
    raw_vals, mix_old, adj_old, _ = _compute_target_dists(pool, old_w, old_size)
    _, mix_new, adj_new, obs_ids = _compute_target_dists(pool, new_w, new_size)

    # 5) Profile transition distribution table (per-donor)
    ptd_rows = []
    for i, oid in enumerate(obs_ids):
        if i < len(raw_vals):
            ptd_rows.append({
                "donor_observation_id": oid,
                "S_raw": round(raw_vals[i], 6),
                "S_size_old": round(mix_old[i], 6),
                "S_adj_old": round(adj_old[i], 6),
                "S_size_new": round(mix_new[i], 6),
                "S_adj_new": round(adj_new[i], 6),
            })
    ptd_fields = ["donor_observation_id", "S_raw", "S_size_old", "S_adj_old", "S_size_new", "S_adj_new"]
    _vig_write_table(out_dir, "profile_transition_distribution", ptd_rows, ptd_fields,
                     "Before/after target-basis transformation", "v2_ptd")

    # 6) Distribution stats
    raw_stats = _dist_stats(raw_vals, "Raw market")
    old_stats = _dist_stats(adj_old, "Adjusted old profile")
    new_stats = _dist_stats(adj_new, "Adjusted new profile")
    delta_row = {"distribution_label": "delta old\u2192new"}
    for k in ["mean", "standard_deviation", "q75", "var99", "var995"]:
        if k in old_stats and k in new_stats:
            delta_row[k] = round(new_stats[k] - old_stats[k], 6)
    stat_fields = ["distribution_label", "n_total", "n_adverse",
                   "mean", "standard_deviation", "q75", "var99", "var995"]
    _vig_write_table(out_dir, "distribution_stats",
                     [raw_stats, old_stats, new_stats, delta_row], stat_fields,
                     "Distribution statistics: raw vs adjusted old vs adjusted new",
                     "v2_dist_stats")

    # 7) Bootstrap + tail support (for new profile)
    boot = _bootstrap_ci(pool, new_w, new_size,
                         B=VIGNETTE_SETTINGS["bootstrap_reps"],
                         seed=VIGNETTE_SETTINGS["random_seed"],
                         conf=VIGNETTE_SETTINGS["bootstrap_confidence_level"])
    boot_rows = []
    for dist_label, var_key_prefix, arr, stats in [
        ("Raw market", "raw", raw_vals, raw_stats),
        ("Adjusted new profile", "adj", adj_new, new_stats),
    ]:
        for metric, var_key in [("VaR99", f"{var_key_prefix}_var99"), ("VaR99.5", f"{var_key_prefix}_var995")]:
            ci = boot[var_key] if boot else (None, None)
            a = np.array(arr, dtype=float)
            pt = stats["var99"] if metric == "VaR99" else stats["var995"]
            tsc = int(np.sum(a >= pt))
            boot_rows.append({
                "distribution_label": dist_label,
                "metric": metric,
                "point_estimate": pt,
                "ci_lower": ci[0], "ci_upper": ci[1],
                "tail_support_count": tsc,
                "bootstrap_reps": VIGNETTE_SETTINGS["bootstrap_reps"],
                "confidence_level": VIGNETTE_SETTINGS["bootstrap_confidence_level"],
            })
    boot_fields = ["distribution_label", "metric", "point_estimate",
                   "ci_lower", "ci_upper", "tail_support_count",
                   "bootstrap_reps", "confidence_level"]
    _vig_write_table(out_dir, "tail_support_bootstrap", boot_rows, boot_fields,
                     "Bootstrap confidence intervals and tail support", "v2_boot")

    # 8) V2 Shapley decomposition (old→new)
    decomp_v2 = _shapley_v2(pool, old_w, new_w, old_size, new_size)
    decomp_rows = [decomp_v2[mn] for mn in ["q75", "var99", "var995"]]
    decomp_fields = ["metric", "old_profile_metric", "new_profile_metric",
                     "concentration_change_effect", "size_change_effect"]
    _vig_write_table(out_dir, "decomposition_summary", decomp_rows, decomp_fields,
                     "Shapley decomposition: old to new profile (the tail regime is "
                     "common to both legs of this paired change, so size and "
                     "concentration are the complete decomposition)", "v2_decomp")

    # Also write old_to_new_change_decomposition (same data, explicit name from manifest)
    _vig_write_table(out_dir, "old_to_new_change_decomposition", decomp_rows, decomp_fields,
                     "Old-to-new profile change decomposition", "v2_change_decomp")

    # 9) Distribution plot (3 series)
    subtitle = (f"Donor pool: {VIGNETTE_SETTINGS['donor_subset']} subset, "
                f"n={len(raw_vals)}, adverse={sum(1 for v in raw_vals if v > 0)}")
    _vig_distribution_plot(out_dir, [
        ("Raw market", raw_vals, _VIG_COLORS["raw"]),
        ("Adjusted old profile", adj_old, _VIG_COLORS["adj_old"]),
        ("Adjusted new profile", adj_new, _VIG_COLORS["adj_new"]),
    ], subtitle, "distribution_plot")

    # 10) Tail exceedance plot (3 series)
    _vig_tail_plot(out_dir, [
        ("Raw market", raw_vals, _VIG_COLORS["raw"]),
        ("Adjusted old profile", adj_old, _VIG_COLORS["adj_old"]),
        ("Adjusted new profile", adj_new, _VIG_COLORS["adj_new"]),
    ], "tail_exceedance_plot")

    # 11) Waterfall plot
    d995 = decomp_v2["var995"]
    _vig_waterfall_plot(out_dir,
                        d995["old_profile_metric"],
                        d995["size_change_effect"],
                        d995["concentration_change_effect"],
                        d995["new_profile_metric"],
                        "VaR99.5", "old_to_new_waterfall")

    # 12) Summary snippet
    snippet = _vig_snippet(vid, raw_stats, new_stats, decomp_v2, len(raw_vals),
                           max(1, int(math.ceil(len(raw_vals) * 0.01))),
                           max(1, int(math.ceil(len(raw_vals) * 0.005))),
                           max(1, int(math.ceil(len(adj_new) * 0.01))),
                           max(1, int(math.ceil(len(adj_new) * 0.005))),
                           extra=f"The profile transition from {old['profile_label']} to "
                                 f"{new['profile_label']} reflects {new['narrative_reason_label']}. ")
    with _open_w(out_dir / "summary_snippet.md", "w", encoding="utf-8") as f:
        f.write(snippet)

    # 13) Metadata
    meta = _vig_metadata(vid, [old, new], VIGNETTE_SETTINGS)
    with _open_w(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    log(f"  Vignette 2 complete: {len(raw_vals)} donors, {len(list(out_dir.iterdir()))} files")


def generate_vignettes(records):
    """Generate all vignette output bundles."""
    if COMBINED_MODEL is None:
        log("  WARNING: COMBINED_MODEL not available, skipping vignettes")
        return
    log("=" * 60)
    log("Generating vignettes...")
    pool = _vig_donor_pool(records)
    log(f"  Donor pool: {len(pool)} observations")
    if len(pool) < 10:
        log("  WARNING: Insufficient donors for vignettes, skipping")
        return
    _generate_vignette_1(pool, records)
    _generate_vignette_2(pool, records)
    log("Vignette generation complete.")
    log("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Distortion Tool — interactive HTML data export
# ─────────────────────────────────────────────────────────────────────────────

def generate_distortion_tool(records, run_id):
    """Build the standalone distortion-tool HTML with embedded donor data.

    Uses the same donor pool as the vignettes (_vig_donor_pool) so that
    the donor count is identical across all supplementary artifacts.  The
    exported operator is the shape-aware dispersion transfer (size,
    concentration, floor, and the tail regime): each donor is quantile-mapped
    from its own Student-t index onto the user-selected target regime (clean
    by default -- de-RITC-ing RITC donors -- or RITC-affected, or a diagnostic
    that preserves each donor's regime), then rescaled.  The tool's Shapley
    decomposition treats tail regime, size and concentration as three players
    over all eight coalitions.
    """
    if COMBINED_MODEL is None:
        log("  WARNING: COMBINED_MODEL not available, skipping distortion tool")
        return

    pool = _vig_donor_pool(records)
    log(f"Generating distortion tool ({len(pool)} donors)...")

    # per-donor RITC flag from the dual-LLM scan (keyed {syndicate}_{year})
    ritc_occ = set()
    ritc_path = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
    if ritc_path.exists():
        _rs = json.loads(ritc_path.read_text(encoding="utf-8"))
        ritc_occ = {kk for kk, vv in _rs.items() if vv.get("ritc_occurred")}

    donors = []
    for r in pool:
        donors.append({
            "syndicate": r["syndicate"],
            "year": r["year"],
            "opening_reserves_gbp_m": round(r["opening_reserves_gbp_m"], 2),
            "s_raw_a": round(r["s_raw_a"], 8),
            "hhi": round(r.get("hhi", 0), 6),
            "weights": [round(w, 6) for w in r["weights"]],
            "lob_severity": [round(s, 6) for s in r["lob_severity"]],
            "direction": r.get("direction"),
            "pyd_gbp_m": round(r.get("pyd_gbp_m", 0) or 0, 2),
            "data_quality_tag": r.get("data_quality_tag"),
            "ritc": 1 if f"{r['syndicate']}_{r['year']}" in ritc_occ else 0,
        })

    tool_data = {
        "run_id": run_id,
        "lob_names": LOB_NAMES,
        "pooling_model": {
            "k": COMBINED_MODEL["k"],
            "gamma": COMBINED_MODEL["gamma"],
            "nu": COMBINED_MODEL.get("nu"),
            "nu_clean": COMBINED_MODEL.get("nu_clean"),
            "nu_ritc": COMBINED_MODEL.get("nu_ritc"),
            "sd_undiv": COMBINED_MODEL.get("sd_undiv", 0.0),
            "sd_div": COMBINED_MODEL.get("sd_div", 1.0),
            "reference_size": COMBINED_MODEL.get("reference_size"),
            "hhi_floor": COMBINED_MODEL.get("hhi_floor", 0.01),
            "hhi_ceil": COMBINED_MODEL.get("hhi_ceil", 1.0),
            "formula": ("S_adj = sigma(R_t,H_t) * Finv_nu_t( F_nu_s( S_raw/sigma(R_o,H_o) ) ); "
                        "sigma=sqrt(sd_undiv^2 + sd_div^2*[(R/ref)(1/H)^gamma]^{2(k-1)}); "
                        "nu_s=nu_ritc if donor is RITC else nu_clean; nu_t is the "
                        "user-selected target regime (clean default, RITC-affected, or "
                        "preserve-donor-regime diagnostic). The identity when nu_s=nu_t."),
            "decomposition": ("three-factor Shapley over tail regime, reserve size and "
                              "concentration; all eight coalitions; contributions sum "
                              "exactly to target minus raw"),
        },
        "eligibility": {
            "base_flag": "eligible_for_capital",
            "additional_filters": ["s_raw_a is not None", "opening_reserves > 0"],
        },
        "n_donors": len(donors),
        "donors": donors,
    }

    tool_json = json.dumps(tool_data, ensure_ascii=False)

    # Build standalone HTML: template + inlined Chart.js + embedded data
    html_template = SCRIPT_DIR / "assets" / "_distortion_tool_template.html"
    chartjs_path = SCRIPT_DIR / "assets" / "chart.umd.min.js"
    html_out = SCRIPT_DIR / "distortion_tool.html"

    if not html_template.exists():
        log(f"  WARNING: template {html_template} not found, skipping distortion tool HTML")
        return

    html = html_template.read_text(encoding="utf-8")

    # Inline Chart.js for fully offline use
    if chartjs_path.exists():
        chartjs_src = chartjs_path.read_text(encoding="utf-8")
        html = html.replace(
            '<script>/* Chart.js v4.5.1 — inlined for offline use */</script>',
            f'<script>/* Chart.js v4.5.1 — inlined for offline use */\n{chartjs_src}\n</script>'
        )

    # Embed donor data
    html = html.replace(
        "// __EMBEDDED_DATA_PLACEHOLDER__",
        f"const EMBEDDED_DATA = {tool_json};"
    )

    with open(html_out, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  Distortion tool: {html_out} ({len(donors)} donors, {len(html)//1024} KB)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("Lloyd's Exposure Composition Analysis")
    log("=" * 60)

    # The run identifier is derived from the data and code hashes once they are
    # known (below), so a rerun of the same commit on the same data reproduces it;
    # a fresh UUID per run made every regenerated output differ from the record.
    run_id = None
    timestamp = datetime.now(timezone.utc).isoformat()

    # Load and classify
    log("Loading and classifying data...")
    records, counters, classification_log, file_paths = load_and_classify()
    log(f"  Total files: {counters['total_files']}")
    log(f"  Excluded: {counters['excluded']}")
    log(f"  Skipped: {counters['skipped']}")
    log(f"  In Runoff: {counters['in_runoff']}")
    log(f"  No Reserves: {counters['no_reserves']}")
    log(f"  Reliable: {counters['reliable']}")
    log(f"  Incomplete: {counters['incomplete']}")
    log(f"  Kept (Reliable + Incomplete): {len(records)}")

    # Assign event groups
    assign_event_groups(records, min_events=3)

    # Build subsets
    log("Building subsets...")
    subset_meta, subset_records = build_subsets(records)
    for name, meta in subset_meta.items():
        log(f"  {name}: {meta['n_observations']} obs, {meta['n_syndicates']} syndicates")

    # Eligibility
    log("Computing eligibility masks...")
    eligibility_counts = compute_eligibility(records, subset_records)
    for k, v in eligibility_counts.items():
        log(f"  {k}: {v}")

    # Source data hash
    source_hash = hash_file_contents(file_paths)
    code_hash = hash_script()
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                            "lloyds-exposure-composition:%s:%s:%s" % (SPEC_VERSION, source_hash, code_hash)))
    global DETERMINISTIC_RUN_ID
    DETERMINISTIC_RUN_ID = run_id

    # Distribution overview
    log("Computing distribution overview...")
    dist_overview = compute_distribution_overview(records)
    boxplot_data = compute_boxplot_data(records)

    # Observations
    observations = build_observations(records)

    # Run analyses
    n0_result = analysis_n0(records, subset_records)
    n1_result = analysis_n1(records, subset_records)
    n2_result = analysis_n2(records, subset_records)
    n3_result = analysis_n3(records, subset_records)

    n5_result = analysis_n5(records)
    # N6 needs the single-R dispersion model from N5
    disp_r = n5_result.get("dispersion_models", {}).get("single_r", {}) if n5_result else {}
    n6_result = analysis_n6(records, disp_r)

    # Load the robust Bayesian pooling calibration (Option-A transfer operator) for
    # all downstream standardisations (capital, tail, personas, worked example, vignettes).
    load_dispersion_calibration()
    if COMBINED_MODEL is not None:
        log(f"  Dispersion calibration: k={COMBINED_MODEL['k']:.3f}, gamma={COMBINED_MODEL['gamma']:.3f}, "
            f"nu={COMBINED_MODEL['nu']:.2f} (n={COMBINED_MODEL['n']})")

    n4_result = analysis_n4(records, subset_records)
    donor_result = analysis_local_donor(records, subset_records)
    persona_result = analysis_personas(records, subset_records)
    we = worked_example(records)

    # Diagnostics
    diagnostics = compute_diagnostics(counters, records)

    # Meta
    meta = {
        "total_files": counters["total_files"],
        "kept": {"count": len(records)},
        "discarded": {
            "count": counters["excluded"] + counters["skipped"] + counters["in_runoff"] + counters["no_reserves"],
            "reasons": {
                "excluded": counters["excluded"],
                "skipped": counters["skipped"],
                "in_runoff": counters["in_runoff"],
                "no_reserves": counters["no_reserves"],
            }
        },
        "years_covered": sorted(set(r["year"] for r in records)),
        "total_observations": len(records),
        "unique_syndicates": len(set(r["syndicate"] for r in records)),
        "n_syndicates": len(set(r["syndicate"] for r in records)),
        "balanced_panel_k8": subset_meta.get("BALANCED_K8", {}).get("n_syndicates", 0),
        "median_reserves": float(np.median([r["opening_reserves_gbp_m"] for r in records if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0])) if records else None,
        "lob_categories": LOB_NAMES,
        "lob_names": LOB_NAMES,
        "obs_2024": len([r for r in records if r["year"] == 2024]),
        "yearly_observations": dict(sorted(Counter(r["year"] for r in records).items())),
        "reliable": counters["reliable"],
        "incomplete": counters["incomplete"],
        "no_reserves": counters["no_reserves"],
        "net_basis_excluded": counters["net_basis_excluded"],
        "unknown_basis_excluded": counters["unknown_basis_excluded"],
        "pyd_basis_source_dist": dict(counters["pyd_basis_source_dist"]),
        "pyd_basis_by_source": {s: dict(b) for s, b in counters["pyd_basis_by_source"].items()},
        "syndicates": sorted(set(r["syndicate"] for r in records)),
    }

    # Histograms for opening reserves and HHI
    reserve_vals = [r["opening_reserves_gbp_m"] for r in records if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
    hhi_vals = [r["hhi"] for r in records if r.get("hhi") is not None]
    def _summary_stats(arr):
        n = len(arr)
        mu = float(np.mean(arr))
        sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        skew = float(np.mean(((arr - mu) / sd) ** 3)) if sd > 0 and n > 2 else 0.0
        return {
            "min": float(np.min(arr)), "max": float(np.max(arr)),
            "mean": mu, "median": float(np.median(arr)),
            "std": sd, "skewness": skew,
            "p10": float(np.percentile(arr, 10)),
            "p90": float(np.percentile(arr, 90)),
            "n": n,
        }

    if reserve_vals:
        r_arr = np.array(reserve_vals)
        r_edges = np.linspace(0, min(float(np.percentile(r_arr, 98)), float(r_arr.max())), 21)
        r_counts, _ = np.histogram(r_arr, bins=r_edges)
        meta["reserve_histogram"] = {
            "bins": [float((r_edges[i] + r_edges[i+1]) / 2) for i in range(len(r_counts))],
            "counts": [int(c) for c in r_counts],
            "overflow": int(np.sum(r_arr > r_edges[-1])),
            "stats": _summary_stats(r_arr),
        }
    if hhi_vals:
        h_arr = np.array(hhi_vals)
        h_edges = np.linspace(0, 1, 21)
        h_counts, _ = np.histogram(h_arr, bins=h_edges)
        meta["hhi_histogram"] = {
            "bins": [float((h_edges[i] + h_edges[i+1]) / 2) for i in range(len(h_counts))],
            "counts": [int(c) for c in h_counts],
            "stats": _summary_stats(h_arr),
        }

    # Overview with cause distribution
    cause_dist = defaultdict(int)
    for r in records:
        cause_dist[r["cause_category"]] += 1
    direction_dist = defaultdict(int)
    for r in records:
        d = r["direction"] or "unknown"
        direction_dist[d] += 1

    overview = {
        "distribution": dist_overview,
        "boxplots_by_year": boxplot_data,
        "cause_distribution": dict(cause_dist),
        "direction_distribution": dict(direction_dist),
    }

    # ── Reshape results to match spec schema ──

    # eligibility: spec expects {mask_name: {n: int, mask_indices: [...]}}
    eligibility_shaped = {}
    for k, v in eligibility_counts.items():
        indices = [i for i, r in enumerate(records) if r.get(k, False)]
        eligibility_shaped[k] = {"n": v, "mask_indices": indices}

    # Reference mean test
    mu_ref, mu_sig, mu_t, mu_p = compute_reference_mean(records)

    # distribution: spec expects {pyd_histogram, stats, boxplots}
    dist_block = {
        "pyd_histogram": dist_overview.get("pyd_histogram", {}),
        "stats": dist_overview.get("stats", {}),
        "boxplots": boxplot_data,
        "reference_mean_test": {
            "mean_pyd_pct": mu_ref if mu_sig else float(np.mean([r["pyd_pct"] for r in records if r.get("pyd_pct") is not None])),
            "reference_mean_pyd_pct": mu_ref,
            "is_significant": mu_sig,
            "t_statistic": mu_t,
            "p_value": mu_p,
            "interpretation": f"Market mean PYD% {'differs' if mu_sig else 'does not differ'} significantly from zero (t={mu_t:.2f}, p={mu_p:.4f}). Standardised distributions are re-centred to {'the sample mean' if mu_sig else 'zero'}.",
        },
    }

    # size_scaling: reshape primary_re_gls → primary, add scatter_data, event_group_audit
    scatter_points = []
    event_audit = {}
    for r in records:
        if r.get("eligible_for_n3") and r["s_raw_a"] is not None and r["opening_reserves_gbp_m"] and r["opening_reserves_gbp_m"] > 5:
            scatter_points.append({
                "x": math.log(r["opening_reserves_gbp_m"]),
                "y": r["s_raw_a"],
                "syndicate": r["syndicate"],
                "year": r["year"],
                "cause": r["cause_category"],
                "pyd_pct": r["pyd_pct"],
                "hhi": r.get("hhi"),
            })
        eg = r.get("event_group_id")
        if eg:
            if eg not in event_audit:
                event_audit[eg] = {"event_group_id": eg, "syndicates": set(), "pooled": "_pooled" in eg}
            event_audit[eg]["syndicates"].add(r["syndicate"])

    event_group_audit = []
    for eg_id, info in sorted(event_audit.items()):
        event_group_audit.append({
            "event_group_id": eg_id,
            "n_syndicates": len(info["syndicates"]),
            "pooled": info["pooled"],
        })

    size_scaling_shaped = {}
    if n3_result and n3_result.get("status") == "completed":
        re_gls_data = n3_result.get("primary_re_gls", {})
        p_val = None
        beta_val = re_gls_data.get("beta")
        se_val = re_gls_data.get("cluster_se")
        if beta_val is not None and se_val is not None and se_val > 0:
            from math import erf, sqrt
            z = abs(beta_val / se_val)
            p_val = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))

        size_scaling_shaped = {
            "primary": {
                "model": "RE-GLS (syndicate RE + event FE)",
                "beta": beta_val,
                "se": se_val,
                "p_value": p_val,
                "ci_95": [beta_val - 1.96 * se_val, beta_val + 1.96 * se_val] if beta_val is not None and se_val is not None else None,
                "sigma_u": re_gls_data.get("sigma2_u"),
                "sigma_eps": re_gls_data.get("sigma2_e"),
                "n": n3_result.get("n"),
                "n_syndicates": len(set(r["syndicate"] for r in records if r.get("eligible_for_n3"))),
                "n_events": len(set(r.get("event_group_id") for r in records if r.get("eligible_for_n3"))),
            },
            "frequentist_comparison": [],
            "scatter_data": {
                "points": scatter_points,
                "regression_line": {"slope": beta_val, "intercept": re_gls_data.get("intercept")},
                "quantile_bins": n3_result.get("quantile_bins", []),
            },
            "event_group_audit": event_group_audit,
        }

        # Reshape frequentist comparisons to list format
        freq_map = n3_result.get("frequentist_comparisons", {})
        spec_names = [("M0_baseline_ols", "Mean shift (OLS, no controls)"),
                      ("M1_ols_event_fe", "Mean shift (OLS + event FE)"),
                      ("M2_log_scale", "Absolute severity (log-scale)"),
                      ("M3_variance_scale", "Severity variance (log-scale)"),
                      ("M1_balanced_k8", "Mean shift (balanced panel)")]
        for key, spec_name in spec_names:
            fc = freq_map.get(key, {})
            b = fc.get("beta")
            s = fc.get("se")
            pv = fc.get("p_value")
            if pv is None and b is not None and s is not None and s > 0:
                z = abs(b / s)
                pv = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))
            entry = {"spec": spec_name, "beta": b, "se": s, "p_value": pv,
                     "significant": fc.get("significant", pv is not None and pv < 0.05),
                     "sig_marker": fc.get("sig_marker", ""),
                     "aic": fc.get("aic"), "bic": fc.get("bic")}
            if "n" in fc:
                entry["n"] = fc["n"]
            size_scaling_shaped["frequentist_comparison"].append(entry)

    else:
        size_scaling_shaped = n3_result or {}

    # exposure_composition: N5 result (LoB shrinkage + HHI diversification)
    exposure_comp_shaped = {}
    if n5_result and n5_result.get("status") == "completed":
        exposure_comp_shaped = {
            "hhi_scatter": {
                "points": n5_result.get("hhi_scatter_points", []),
                "quantile_bins": n5_result.get("hhi_quantile_bins", []),
                "direction": n5_result.get("hhi_direction", {}),
            },
            "dispersion_models": n5_result.get("dispersion_models", {}),
            "lob_dispersion": n5_result.get("lob_dispersion", {}),
        }

    # joint_composition: N6 result (sequential size→HHI pipeline)
    joint_comp_shaped = {}
    if n6_result and n6_result.get("status") == "completed":
        joint_comp_shaped = {
            "hhi_r_correlation": n6_result.get("hhi_r_correlation", {}),
            "size_model_used": n6_result.get("size_model_used", {}),
            "reference_size": n6_result.get("reference_size"),
            "disp_h_adjusted": n6_result.get("disp_h_adjusted", {}),
            "scatter_points": n6_result.get("scatter_points", []),
            "quantile_bins_adj": n6_result.get("quantile_bins_adj", []),
            "variance_attribution": n6_result.get("variance_attribution", {}),
            "median_hhi": n6_result.get("median_hhi"),
            "combined_model": n6_result.get("combined_model"),
            "univariate_comparison": n6_result.get("univariate_comparison", {}),
            "hhi_first": n6_result.get("hhi_first", {}),
            "ordering_comparison": n6_result.get("ordering_comparison", {}),
        }

    # capital_impact: reshape test_portfolios dict → portfolios list
    capital_shaped = {"portfolios": []}
    if n4_result and "test_portfolios" in n4_result:
        for tp_name, tp_data in n4_result["test_portfolios"].items():
            entry = {"name": tp_name}
            for dist_key in ["naive", "concentration_only", "size_only", "full"]:
                if dist_key in tp_data:
                    entry[dist_key] = tp_data[dist_key]
            if "shapley" in tp_data:
                entry["shapley"] = tp_data["shapley"]
            if "target_weights" in tp_data:
                entry["target_weights"] = tp_data["target_weights"]
            if "size" in tp_data:
                entry["size"] = tp_data["size"]
            if "bootstrap_ci" in tp_data:
                bci_raw = tp_data["bootstrap_ci"]
                bci = {}
                for bk, bv in bci_raw.items():
                    if isinstance(bv, dict):
                        bci[bk] = [bv.get("ci_2_5"), bv.get("ci_97_5")]
                    else:
                        bci[bk] = bv
                entry["boot_ci"] = bci
                # Add specific keys expected by HTML viewer
                entry["boot_ci"]["var_995"] = bci.get("full_var_995")
                entry["boot_ci"]["var_99"] = bci.get("full_var_99")
            capital_shaped["portfolios"].append(entry)
        capital_shaped["market_reference_mix"] = n4_result.get("market_reference_mix")

    # robustness: reshape
    robustness_shaped = {
        "sampling": {},
        "local_donor": {},
    }
    if n0_result and n0_result.get("status") == "completed":
        metrics = n0_result.get("metrics", {})
        robustness_shaped["sampling"] = {}
        for mk, mv in metrics.items():
            robustness_shaped["sampling"][mk] = {
                "estimate": mv.get("point_estimate"),
                "leave_out_cv": mv.get("leave_out_cv_pct"),
                "boot_cv": mv.get("bootstrap_cv_pct"),
                "stability": mv.get("stability"),
            }
    if donor_result and isinstance(donor_result, dict):
        for dk, dv in donor_result.items():
            if dk == "status":
                continue
            safe_key = dk.lower().replace(" ", "_").replace("£", "").replace("—", "_")
            robustness_shaped["local_donor"][safe_key] = dv

    # personas: unwrap status wrapper
    personas_shaped = {}
    if isinstance(persona_result, dict):
        if "personas" in persona_result:
            personas_shaped = persona_result["personas"]
        elif "status" not in persona_result:
            personas_shaped = persona_result

    # tail_trends: reshape to spec format
    tail_trends_shaped = {}
    if n1_result and n1_result.get("status") == "completed":
        raw_p95 = n1_result.get("p95_raw_by_year", {})
        std_p95 = n1_result.get("p95_std_by_year", {})

        # Compute OLS regression on p95 series for the regression summary table
        def _p95_regression(p95_dict):
            if len(p95_dict) < 2:
                return {"slope": None, "intercept": None, "r_squared": None, "p_value": None, "boot_ci": None}
            years_arr = np.array(sorted(p95_dict.keys(), key=int), dtype=float)
            vals_arr = np.array([p95_dict[str(int(y))] for y in years_arr], dtype=float)
            X = np.column_stack([np.ones(len(years_arr)), years_arr])
            try:
                beta, _, _, _ = np.linalg.lstsq(X, vals_arr, rcond=None)
                pred = X @ beta
                ss_res = float(np.sum((vals_arr - pred) ** 2))
                ss_tot = float(np.sum((vals_arr - np.mean(vals_arr)) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                n = len(vals_arr)
                if n > 2 and ss_res > 0:
                    se_slope = math.sqrt(ss_res / (n - 2) / np.sum((years_arr - np.mean(years_arr)) ** 2))
                    t_stat = beta[1] / se_slope if se_slope > 0 else 0
                    from math import erf, sqrt as msqrt
                    p_val = 2 * (1 - 0.5 * (1 + erf(abs(t_stat) / msqrt(2))))
                else:
                    se_slope = None
                    p_val = None
                return {"slope": float(beta[1]), "intercept": float(beta[0]), "r_squared": float(r2),
                        "se": se_slope, "p_value": p_val, "boot_ci": None}
            except Exception:
                return {"slope": None, "intercept": None, "r_squared": None, "p_value": None, "boot_ci": None}

        raw_reg = _p95_regression(raw_p95)
        std_reg = _p95_regression(std_p95)

        # Bootstrap CIs for p95 regression slopes
        rng_p95 = np.random.RandomState(42)

        def _boot_p95_slope(p95_dict, rng, B=500):
            years = sorted(p95_dict.keys(), key=int)
            if len(years) < 3:
                return None
            year_arr = np.array([int(y) for y in years], dtype=float)
            val_arr = np.array([p95_dict[str(int(y))] for y in year_arr], dtype=float)
            slopes = []
            for _ in range(B):
                idx = rng.choice(len(year_arr), size=len(year_arr), replace=True)
                Xb = np.column_stack([np.ones(len(idx)), year_arr[idx]])
                yb = val_arr[idx]
                try:
                    b, _, _, _ = np.linalg.lstsq(Xb, yb, rcond=None)
                    slopes.append(float(b[1]))
                except Exception:
                    continue
            if len(slopes) >= 10:
                return [float(np.percentile(slopes, 2.5)), float(np.percentile(slopes, 97.5))]
            return None

        raw_reg["boot_ci"] = _boot_p95_slope(raw_p95, rng_p95)
        std_reg["boot_ci"] = _boot_p95_slope(std_p95, rng_p95)

        slope_reduction = None
        if raw_reg["slope"] is not None and std_reg["slope"] is not None and raw_reg["slope"] != 0:
            slope_reduction = (1.0 - std_reg["slope"] / raw_reg["slope"]) * 100.0

        tail_trends_shaped = {
            "annual_p95": {
                "raw": [{"year": int(yr), "value": v} for yr, v in sorted(raw_p95.items())],
                "standardised": [{"year": int(yr), "value": v} for yr, v in sorted(std_p95.items())],
            },
            "regression": {
                "raw": raw_reg,
                "standardised": std_reg,
                "slope_reduction_pct": slope_reduction,
            },
            "panel_trend": {
                "delta": n1_result.get("delta"),
                "se": n1_result.get("delta_cluster_se"),
                "boot_ci_95": n1_result.get("delta_bootstrap_ci_95"),
            },
            "slope_reduction_pct": slope_reduction,
            "inference_note": "Annual p95 shown for intuition; inference based on full-panel RE-GLS model.",
        }
    else:
        tail_trends_shaped = n1_result or {}

    # tail_diagnostics: flatten mean_excess_function arrays to top level
    tail_diag_shaped = {}
    if n2_result and n2_result.get("status") == "completed":
        tail_diag_shaped = {
            "mean_excess": {
                "raw": {
                    "thresholds": [p["threshold"] for p in n2_result.get("raw", {}).get("mean_excess_function", [])],
                    "values": [p["mean_excess"] for p in n2_result.get("raw", {}).get("mean_excess_function", [])],
                },
                "standardised": {
                    "thresholds": [p["threshold"] for p in n2_result.get("mix_standardised", {}).get("mean_excess_function", [])],
                    "values": [p["mean_excess"] for p in n2_result.get("mix_standardised", {}).get("mean_excess_function", [])],
                },
            },
            "raw": n2_result.get("raw", {}).get("mean_excess_function", []),
            "mix_standardised": n2_result.get("mix_standardised", {}).get("mean_excess_function", []),
        }
    else:
        tail_diag_shaped = n2_result or {}

    # ── Extended paper-pack data ──────────────────────────────────────────────

    # A.2  Tail capital sensitivity across subsets
    log("Computing tail capital sensitivity across subsets...")
    tail_capital_sensitivity = {}
    for subset_name in ["DENSE", "FULL", "BALANCED_K8", "BALANCED_K6"]:
        sub_recs = subset_records.get(subset_name, [])
        sub_eligible = [r for r in sub_recs if r.get("eligible_for_capital", False)]
        if len(sub_eligible) < 10:
            tail_capital_sensitivity[subset_name] = {"status": "insufficient_data", "n": len(sub_eligible)}
            continue
        sub_result = {}
        for tp in TEST_PORTFOLIOS:
            tw = portfolio_weights_vector(tp["weights"])
            tw_sum = tw.sum()
            if tw_sum > 0:
                tw = tw / tw_sum
            naive, mix_only, size_only, full_adj = compute_four_distributions(sub_eligible, tw, tp["size"])
            sub_result[tp["name"]] = {
                "n": len(naive),
                "var_99_naive": var_at(naive, 0.99),
                "var_995_naive": var_at(naive, 0.995),
                "var_99_full": var_at(full_adj, 0.99),
                "var_995_full": var_at(full_adj, 0.995),
            }
        tail_capital_sensitivity[subset_name] = sub_result

    # A.1  Tail sample support
    log("Computing tail sample support...")
    tail_support = {}
    for tp in TEST_PORTFOLIOS:
        tw = portfolio_weights_vector(tp["weights"])
        tw_sum = tw.sum()
        if tw_sum > 0:
            tw = tw / tw_sum
        eligible_cap = [r for r in records if r.get("eligible_for_capital", False)]
        naive_sev = [r["s_raw_a"] for r in eligible_cap if r["s_raw_a"] is not None]
        n_total = len(naive_sev)
        n_adverse = sum(1 for s in naive_sev if s > 0)
        tail_support[tp["name"]] = {
            "n_total": n_total,
            "n_adverse": n_adverse,
            "n_tail_99": max(1, int(math.ceil(n_total * 0.01))),
            "n_tail_995": max(1, int(math.ceil(n_total * 0.005))),
        }

    # C.1  Classification log summary by reason and year
    log("Summarising classification log...")
    cl_summary = {"by_reason_year": {}, "by_reason_total": {}}
    for entry in classification_log:
        status = entry["status"]
        fname = entry.get("file", "")
        # Extract year from filename (syndicate_XXXX_YYYY.json)
        yr = None
        parts = fname.replace(".json", "").split("_")
        if len(parts) >= 3:
            try:
                yr = int(parts[-1])
            except ValueError:
                pass
        if status not in cl_summary["by_reason_total"]:
            cl_summary["by_reason_total"][status] = 0
            cl_summary["by_reason_year"][status] = {}
        cl_summary["by_reason_total"][status] += 1
        if yr is not None:
            yr_str = str(yr)
            cl_summary["by_reason_year"][status][yr_str] = cl_summary["by_reason_year"][status].get(yr_str, 0) + 1
    cl_summary["years"] = sorted(set(
        yr for by_yr in cl_summary["by_reason_year"].values() for yr in by_yr.keys()
    ))

    # C.2  Subset profiles for comparison table
    log("Computing subset profiles...")
    subset_profiles = {}
    for subset_name in ["DENSE", "FULL", "BALANCED_K8", "BALANCED_K6"]:
        sub_recs = subset_records.get(subset_name, [])
        if not sub_recs:
            continue
        reserves = [r["opening_reserves_gbp_m"] for r in sub_recs
                    if r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 0]
        hhis = [r["hhi"] for r in sub_recs if r.get("hhi") is not None]
        eg_counts = defaultdict(int)
        for r in sub_recs:
            eg = r.get("event_group_id", "")
            # Extract cause part (after year_)
            cause = "_".join(eg.split("_")[1:]) if "_" in eg else eg
            eg_counts[cause] += 1
        total_eg = sum(eg_counts.values())
        eg_shares = {k: round(v / total_eg * 100, 1) if total_eg > 0 else 0 for k, v in eg_counts.items()}
        sub_years = sorted(set(r["year"] for r in sub_recs))
        subset_profiles[subset_name] = {
            "n_obs": len(sub_recs),
            "n_syndicates": len(set(r["syndicate"] for r in sub_recs)),
            "years": sub_years,
            "year_range": f"{min(sub_years)}--{max(sub_years)}",
            "median_reserves": float(np.median(reserves)) if reserves else None,
            "median_hhi": float(np.median(hhis)) if hhis else None,
            "event_group_shares": eg_shares,
        }

    # C.3  Size-dispersion robustness
    log("Computing size-dispersion robustness checks...")
    dispersion_robustness = {}
    # (a) Exclude post-2020 observations
    pre2020 = [r for r in records if r["year"] <= 2019 and r.get("eligible_for_n3")]
    if len(pre2020) >= 20:
        sev_vals = [r["s_raw_a"] for r in pre2020 if r["s_raw_a"] is not None]
        log_abs = [(math.log(abs(r["s_raw_a"])), math.log(r["opening_reserves_gbp_m"]))
                   for r in pre2020 if r["s_raw_a"] is not None and abs(r["s_raw_a"]) > 1e-6
                   and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 5]
        if len(log_abs) >= 10:
            y_la = np.array([p[0] for p in log_abs])
            x_la = np.array([p[1] for p in log_abs])
            X_la = np.column_stack([np.ones(len(x_la)), x_la])
            beta_la, res_la, _, _ = np.linalg.lstsq(X_la, y_la, rcond=None)
            ss_res = float(np.sum((y_la - X_la @ beta_la) ** 2))
            n_la = len(y_la)
            se_la = math.sqrt(ss_res / (n_la - 2) / np.sum((x_la - np.mean(x_la)) ** 2)) if n_la > 2 and np.sum((x_la - np.mean(x_la))**2) > 0 else None
            p_la = None
            if se_la and se_la > 0:
                z = abs(beta_la[1] / se_la)
                p_la = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
            dispersion_robustness["pre_2020_only"] = {
                "n": n_la, "beta": float(beta_la[1]), "se": se_la, "p_value": p_la,
                "label": "Pre-2020 only (dense period)",
            }
    # (b) Exclude intermittent reporters (only syndicates with ≥6 years)
    synd_year_counts = defaultdict(int)
    for r in records:
        synd_year_counts[r["syndicate"]] += 1
    persistent = [r for r in records if synd_year_counts[r["syndicate"]] >= 6 and r.get("eligible_for_n3")]
    if len(persistent) >= 20:
        log_abs_p = [(math.log(abs(r["s_raw_a"])), math.log(r["opening_reserves_gbp_m"]))
                     for r in persistent if r["s_raw_a"] is not None and abs(r["s_raw_a"]) > 1e-6
                     and r["opening_reserves_gbp_m"] is not None and r["opening_reserves_gbp_m"] > 5]
        if len(log_abs_p) >= 10:
            y_p = np.array([p[0] for p in log_abs_p])
            x_p = np.array([p[1] for p in log_abs_p])
            X_p = np.column_stack([np.ones(len(x_p)), x_p])
            beta_p, _, _, _ = np.linalg.lstsq(X_p, y_p, rcond=None)
            ss_res_p = float(np.sum((y_p - X_p @ beta_p) ** 2))
            n_p = len(y_p)
            se_p = math.sqrt(ss_res_p / (n_p - 2) / np.sum((x_p - np.mean(x_p)) ** 2)) if n_p > 2 and np.sum((x_p - np.mean(x_p))**2) > 0 else None
            p_p = None
            if se_p and se_p > 0:
                z = abs(beta_p[1] / se_p)
                p_p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
            dispersion_robustness["persistent_only"] = {
                "n": n_p, "beta": float(beta_p[1]), "se": se_p, "p_value": p_p,
                "label": "Persistent reporters only ($\\geq 6$ years)",
            }
    # (c) Include the primary specification for comparison
    freq_map_r = n3_result.get("frequentist_comparisons", {}) if n3_result else {}
    m2 = freq_map_r.get("M2_log_scale", {})
    if m2:
        p_m2 = m2.get("p_value")
        if p_m2 is None and m2.get("beta") is not None and m2.get("se") is not None and m2["se"] > 0:
            z = abs(m2["beta"] / m2["se"])
            p_m2 = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
        dispersion_robustness["primary"] = {
            "n": m2.get("n") or (n3_result.get("n") if n3_result else None),
            "beta": m2.get("beta"), "se": m2.get("se"), "p_value": p_m2,
            "label": "Primary (DENSE, all reporters)",
        }

    # B  Data-construction audit
    log("Computing data-construction audit...")
    # PYD source: check if lob_movements present (structured), triangle, or proportional
    pyd_source_dist = {"structured_table": 0, "triangle_or_proportional": 0, "narrative_only": 0}
    for r in records:
        if r.get("lob_movements") and len(r["lob_movements"]) > 0:
            has_amounts = any(m.get("amount_gbp_m") is not None for m in r["lob_movements"])
            if has_amounts:
                pyd_source_dist["structured_table"] += 1
            else:
                pyd_source_dist["triangle_or_proportional"] += 1
        else:
            pyd_source_dist["triangle_or_proportional"] += 1

    # Dual-model stats
    dual_model_stats = {
        "total_files": len(file_paths),
        "dual_model_files": 0,
        "single_model_files": 0,
        "material_disagreements": 0,
        "disagreement_threshold_pp": 0.5,
        "human_intervention_count": 0,
    }
    for fpath in file_paths:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            models = data.get("models", {})
            if len(models) >= 2:
                dual_model_stats["dual_model_files"] += 1
                pyd_vals = []
                for mk, m in models.items():
                    pv = m.get("prior_year_development_pct")
                    if pv is not None:
                        pyd_vals.append(float(pv))
                if len(pyd_vals) >= 2 and abs(pyd_vals[0] - pyd_vals[1]) > 0.5:
                    dual_model_stats["material_disagreements"] += 1
            else:
                dual_model_stats["single_model_files"] += 1
        except Exception:
            dual_model_stats["single_model_files"] += 1

    # Assemble results bundle
    results = {
        "spec_version": SPEC_VERSION,
        "analysis_run_id": run_id,
        "analysis_timestamp": timestamp,
        "source_data_hash": source_hash,
        "analysis_code_hash": code_hash,
        "analysis_config": ANALYSIS_CONFIG,
        "meta": meta,
        "dispersion_calibration": COMBINED_MODEL,
        "eligibility": eligibility_shaped,
        "subsets": subset_meta,
        "observations": observations,
        "overview": overview,
        "distribution": dist_block,
        "tail_trends": tail_trends_shaped,
        "tail_diagnostics": tail_diag_shaped,
        "size_scaling": size_scaling_shaped,
        "exposure_composition": exposure_comp_shaped,
        "joint_composition": joint_comp_shaped,
        "capital_impact": capital_shaped,
        "robustness": robustness_shaped,
        "personas": personas_shaped,
        "worked_example": we,
        "data_quality": diagnostics,
        "tail_support": tail_support,
        "tail_capital_sensitivity": tail_capital_sensitivity,
        "classification_summary": cl_summary,
        "subset_profiles": subset_profiles,
        "dispersion_robustness": dispersion_robustness,
        "pyd_source_dist": pyd_source_dist,
        "dual_model_stats": dual_model_stats,
        "fx_conversion": {
            "policy": ("Single-currency (GBP) dataset: USD-presented reports "
                       "converted at the reporting-date spot rate (last Fed H.10 "
                       "business-day rate on or before 31 December of the "
                       "reporting year); GBP = USD / (USD per GBP). "
                       "See docs/fx-conversion.md."),
            "fx_source": FX_H10_META["source"],
            "rate_selection_rule": FX_H10_META["selection_rule"],
            "year_end_rates_used": FX_H10_META["year_end_rates"],
            "currency_provenance_method": FX_SCAN_META["method"],
            "currency_scan_file": "pdf_extraction/currency_scan.json",
            "n_reports_by_currency": dict(counters["fx_currency_dist"]),
            "n_converted": counters["fx_converted"],
        },
    }

    # Write output
    log(f"Writing results to {OUTPUT_FILE}")

    def _sanitise_for_json(obj):
        """Recursively replace inf/nan with None in nested dicts/lists."""
        if isinstance(obj, dict):
            return {k: _sanitise_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitise_for_json(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                v = float(obj)
                if math.isnan(v) or math.isinf(v):
                    return None
                return v
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    results = _sanitise_for_json(results)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, cls=NumpyEncoder)

    generate_paper_pack(results, records)

    generate_vignettes(records)

    generate_distortion_tool(records, run_id)

    log(f"Done. Output: {OUTPUT_FILE}")
    log(f"Run ID: {run_id}")


if __name__ == "__main__":
    main()
