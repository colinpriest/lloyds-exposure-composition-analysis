r"""run_analysis.py: confirmed opening reserves, and a confirmed basis without a figure (PLAN R213, eighth amendment).

Written to src/test_confirmed_openings_and_bases.py, which fails before this patch. Each anchor must match once; line
endings are kept.

    python patch_run_analysis_openings.py
"""
import io
from pathlib import Path

P = Path(r"D:/dev/IME-Lloyds-exposure-composition/src/run_analysis.py")

EDITS = [
    # the register's path, beside the other registers
    ('TAKEON_REGISTER = SCRIPT_DIR / "data" / "takeon_not_development.json"\n',
     'TAKEON_REGISTER = SCRIPT_DIR / "data" / "takeon_not_development.json"\n'
     '#: opening reserves two readings of the filing confirmed, for records whose adopted opening reserves are another\n'
     '#: line of the filing (PLAN R213, eighth amendment; apply_confirmed_opening)\n'
     'OPENING_RESERVES_CONFIRMED = SCRIPT_DIR / "data" / "opening_reserves_confirmed.json"\n'),
    # the run identifier hashes it
    ('    inputs.update(str(p) for p in (PYD_BASIS_REGISTER, PYD_CONFIRMED_FIGURES, TAKEON_REGISTER,\n'
     '                                   assumed_business.RITC_SCAN, assumed_business.TRANSFER_REGISTER))\n',
     '    inputs.update(str(p) for p in (PYD_BASIS_REGISTER, PYD_CONFIRMED_FIGURES, TAKEON_REGISTER,\n'
     '                                   OPENING_RESERVES_CONFIRMED, assumed_business.RITC_SCAN,\n'
     '                                   assumed_business.TRANSFER_REGISTER))\n'),
    # a confirmed-figure entry may carry a net or unknown basis without a figure
    ('    and a "Gross" as an unknown basis, and nothing would say so."""\n'
     '    gaps = _evidence_gaps(entry)\n'
     '    if not _is_number(entry.get("figure_m")):\n',
     '    and a "Gross" as an unknown basis, and nothing would say so.\n'
     '\n'
     '    An entry may carry no figure when the readings established that the adopted figure is not a gross\n'
     '    amount and the filing gives none to put in its place (623/2014 adopted a sum of loss-ratio points,\n'
     '    eighth amendment). It then carries that basis, net or unknown, and no figure_kind: a gross basis\n'
     '    without a figure would change nothing and claim a confirmation."""\n'
     '    gaps = _evidence_gaps(entry)\n'
     '    if "figure_m" in entry and entry["figure_m"] is None:\n'
     '        if entry.get("basis") not in ("net", "unknown"):\n'
     '            gaps.append("a basis of \'net\' or \'unknown\' for an entry without a figure")\n'
     '        if entry.get("figure_kind") is not None:\n'
     '            gaps.append("no figure_kind for an entry without a figure")\n'
     '        return gaps\n'
     '    if not _is_number(entry.get("figure_m")):\n'),
    # the opening register's evidence and loader, after the take-on register's
    ('def load_takeon_register(path=None):\n',
     'def _opening_gaps(entry):\n'
     '    gaps = _evidence_gaps(entry)\n'
     '    if not _is_number(entry.get("opening_reserves_m")) or entry["opening_reserves_m"] <= 0:\n'
     '        gaps.append("a positive numeric opening_reserves_m")\n'
     '    return gaps\n'
     '\n'
     '\n'
     'def load_opening_reserves_confirmed(path=None):\n'
     '    """The opening reserves two readings of the filing confirmed (data/opening_reserves_confirmed.json).\n'
     '    ``path`` defaults to the committed register."""\n'
     '    return _load_evidenced_register(path or OPENING_RESERVES_CONFIRMED, _opening_gaps)\n'
     '\n'
     '\n'
     'def load_takeon_register(path=None):\n'),
    # a figure-less entry keeps the figure; the opening applies on its own copy
    ('    out = copy.deepcopy(cm)\n'
     '    figure = float(entry["figure_m"])\n',
     '    out = copy.deepcopy(cm)\n'
     '    if entry.get("figure_m") is None:\n'
     '        # the readings established the basis and found no figure to adopt: the figure stays, and the\n'
     '        # basis the route carries excludes the record as any net or unknown-basis record is excluded\n'
     '        out["_pyd_route"] = {"source": CONFIRMED_FIGURE_SOURCE, "value": None, "figure_kind": None,\n'
     '                             "basis": entry["basis"], "register": "data/pyd_confirmed_figures.json"}\n'
     '        out["data_quality_notes"] = " ".join(n for n in (\n'
     '            cm.get("data_quality_notes") or "",\n'
     '            "[PYD BASIS ESTABLISHED BY TWO READINGS OF THE FILING: %s, with no figure to adopt; %s kept, "\n'
     '            "register data/pyd_confirmed_figures.json]"\n'
     '            % (entry["basis"], _signed_m(safe_float(cm.get("prior_year_development_gbp_m"))))) if n)\n'
     '        return out\n'
     '    figure = float(entry["figure_m"])\n'),
    ('def pyd_basis(cm, key, register, models=None):\n',
     'def _amount_m(v):\n'
     '    """5,344.064m: the form of the filing\'s own amounts, in millions."""\n'
     '    if v is None:\n'
     '        return "no figure"\n'
     '    return ("{:,.3f}".format(v)).rstrip("0").rstrip(".") + "m"\n'
     '\n'
     '\n'
     'def apply_confirmed_opening(cm, entry):\n'
     '    """A copy of the model block carrying the opening reserves two readings of the filing confirmed (PLAN R213).\n'
     '\n'
     '    The study\'s third sample found 2003/2018\'s adopted opening reserves, 1,659.705m, to be the reinsurers\'\n'
     '    share of claims outstanding at 1 January 2018; the filing\'s gross claims outstanding is 5,344.064m. Severity\n'
     '    is the development figure over the opening reserves, so the record\'s severity was about 3.2 times too large.\n'
     '\n'
     '    The reserves are in the report\'s own currency, like the block\'s fields, and the loader applies them before\n'
     '    apply_fx_conversion rewrites the *_gbp_m fields in place; the copy is deep. The percentage is recomputed on\n'
     '    them. The development figure and its route are left as they are, and the notes say what was replaced.\n'
     '    """\n'
     '    out = copy.deepcopy(cm)\n'
     '    opening = float(entry["opening_reserves_m"])\n'
     '    old = safe_float(cm.get("opening_reserves_gbp_m"))\n'
     '    pyd = safe_float(cm.get("prior_year_development_gbp_m"))\n'
     '    out["opening_reserves_gbp_m"] = opening\n'
     '    out["prior_year_development_pct"] = 100.0 * pyd / opening if pyd is not None else None\n'
     '    out["data_quality_notes"] = " ".join(n for n in (\n'
     '        cm.get("data_quality_notes") or "",\n'
     '        "[OPENING RESERVES CONFIRMED BY TWO READINGS OF THE FILING: %s replaces %s, register "\n'
     '        "data/opening_reserves_confirmed.json]" % (_amount_m(opening), _amount_m(old))) if n)\n'
     '    return out\n'
     '\n'
     '\n'
     'def pyd_basis(cm, key, register, models=None):\n'),
    # counters
    ('        "confirmed_figures_applied": 0,\n        "takeon_excluded": 0,\n',
     '        "confirmed_figures_applied": 0,\n        "takeon_excluded": 0,\n'
     '        # opening reserves adopted from data/opening_reserves_confirmed.json (eighth amendment)\n'
     '        "confirmed_openings_applied": 0,\n'),
    ('    takeon_register = load_takeon_register()\n',
     '    takeon_register = load_takeon_register()\n'
     '    opening_register = load_opening_reserves_confirmed()\n'),
    ('            counters["confirmed_figures_applied"] += 1\n',
     '            counters["confirmed_figures_applied"] += 1\n'
     '        # Opening reserves two readings of the filing confirmed, for the registered records only: in the\n'
     '        # report\'s currency, so before the FX conversion, and on a copy that goes back into the models dict.\n'
     '        if basis_key in opening_register:\n'
     '            cm = apply_confirmed_opening(cm, opening_register[basis_key])\n'
     '            models[canonical_key] = cm\n'
     '            counters["confirmed_openings_applied"] += 1\n'),
    ('    log(f"  Take-on, not development: {counters[\'takeon_excluded\']}")\n',
     '    log(f"  Take-on, not development: {counters[\'takeon_excluded\']}")\n'
     '    log(f"  Confirmed opening reserves applied: {counters[\'confirmed_openings_applied\']}")\n'),
    ('        "takeon_excluded": counters["takeon_excluded"],\n',
     '        "takeon_excluded": counters["takeon_excluded"],\n'
     '        "confirmed_openings_applied": counters["confirmed_openings_applied"],\n'),
]

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "OPENING_RESERVES_CONFIRMED" in t:
    raise SystemExit("already patched")
for old, new in EDITS:
    if t.count(old) != 1:
        raise SystemExit("anchor found %d times: %r" % (t.count(old), old[:100]))
    t = t.replace(old, new)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("run_analysis.py: %d edits (confirmed opening reserves; a confirmed basis without a figure)" % len(EDITS))
