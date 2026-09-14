r"""The ninth amendment's point 5, in the analysis repository: the take-on base register and its loader step.

  src/run_analysis.py                     TAKEON_BASE_REGISTER (hashed into the run identifier); _takeon_base_gaps and
                                          load_takeon_base; apply_takeon_base (the 2% guard on the 1 January figure);
                                          load_and_classify applies it after the confirmed opening reserves and before
                                          the FX conversion; counter takeon_base_applied in the counters, the log and
                                          the meta
  src/test_run_id_inputs.py               INPUTS names the register
  src/test_confirmed_figures_and_takeons.py  the counters test requires takeon_base_applied
  data/opening_reserves_takeon_base.json  a new register holding only its purpose

Every anchor must match exactly once; otherwise the script writes nothing. Line endings are kept as found.

    python patch_run_analysis_takeon_base.py
"""
import io
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
RA = AN / "src" / "run_analysis.py"
RUNID = AN / "src" / "test_run_id_inputs.py"
CFT = AN / "src" / "test_confirmed_figures_and_takeons.py"
REG = AN / "data" / "opening_reserves_takeon_base.json"

LOADER = [
    ('OPENING_RESERVES_CONFIRMED = SCRIPT_DIR / "data" / "opening_reserves_confirmed.json"\n',
     'OPENING_RESERVES_CONFIRMED = SCRIPT_DIR / "data" / "opening_reserves_confirmed.json"\n'
     '#: take-ons the adopted development covers, added to the opening reserves (error-rate protocol, ninth amendment)\n'
     'TAKEON_BASE_REGISTER = SCRIPT_DIR / "data" / "opening_reserves_takeon_base.json"\n'),
    ("OPENING_RESERVES_CONFIRMED, assumed_business.RITC_SCAN,",
     "OPENING_RESERVES_CONFIRMED, TAKEON_BASE_REGISTER, assumed_business.RITC_SCAN,"),
    ('def load_opening_reserves_confirmed(path=None):\n'
     '    """The opening reserves two readings of the filing confirmed (data/opening_reserves_confirmed.json).\n'
     '    ``path`` defaults to the committed register."""\n'
     '    return _load_evidenced_register(path or OPENING_RESERVES_CONFIRMED, _opening_gaps)\n',
     'def load_opening_reserves_confirmed(path=None):\n'
     '    """The opening reserves two readings of the filing confirmed (data/opening_reserves_confirmed.json).\n'
     '    ``path`` defaults to the committed register."""\n'
     '    return _load_evidenced_register(path or OPENING_RESERVES_CONFIRMED, _opening_gaps)\n'
     '\n'
     '\n'
     'def _takeon_base_gaps(entry):\n'
     '    gaps = _opening_gaps(entry)\n'
     '    if not _is_number(entry.get("takeon_m")) or entry["takeon_m"] <= 0:\n'
     '        gaps.append("a positive numeric takeon_m")\n'
     '    return gaps\n'
     '\n'
     '\n'
     'def load_takeon_base(path=None):\n'
     '    """The take-ons two readings of the filing found the adopted development to cover while the opening reserves\n'
     '    do not (data/opening_reserves_takeon_base.json; error-rate protocol, ninth amendment). ``path`` defaults to the\n'
     '    committed register."""\n'
     '    return _load_evidenced_register(path or TAKEON_BASE_REGISTER, _takeon_base_gaps)\n'),
    ('        "[OPENING RESERVES CONFIRMED BY TWO READINGS OF THE FILING: %s replaces %s, register "\n'
     '        "data/opening_reserves_confirmed.json]" % (_amount_m(opening), _amount_m(old))) if n)\n'
     '    return out\n',
     '        "[OPENING RESERVES CONFIRMED BY TWO READINGS OF THE FILING: %s replaces %s, register "\n'
     '        "data/opening_reserves_confirmed.json]" % (_amount_m(opening), _amount_m(old))) if n)\n'
     '    return out\n'
     '\n'
     '\n'
     'def apply_takeon_base(cm, entry):\n'
     '    """A copy of the model block whose opening reserves carry a take-on the adopted development covers (PLAN R213;\n'
     '    error-rate protocol, ninth amendment).\n'
     '\n'
     '    Severity is the development figure over the opening reserves. The study\'s eighth census found records whose\n'
     '    development covers business taken into the syndicate in the report year while the opening reserves, the gross\n'
     '    claims outstanding at 1 January before the transfer, do not. 1884/2021\'s triangle carries the RITCs of the 2018\n'
     '    years of Syndicates 1861 and 1955 (839.787m gross) on both diagonals of its step, so its -20.1m is development on\n'
     '    about 913m of reserves, and the loader divided it by 73.709m.\n'
     '\n'
     '    The amount is added to the block\'s opening reserves in the report\'s own currency, after any confirmed opening\n'
     '    reserves and before apply_fx_conversion rewrites the *_gbp_m fields in place; the copy is deep. The percentage is\n'
     '    recomputed on the sum. The development figure and its route are left as they are, and the notes say what was\n'
     '    added. An entry whose 1 January figure is not the block\'s within 2% describes other reserves and is refused.\n'
     '    """\n'
     '    block = safe_float(cm.get("opening_reserves_gbp_m"))\n'
     '    stated = float(entry["opening_reserves_m"])\n'
     '    if block is None or block <= 0 or abs(block - stated) > 0.02 * stated:\n'
     '        raise ValueError("take-on base: the entry\'s 1 January figure %s is not the block\'s opening reserves %s "\n'
     '                         "within 2%%, register data/opening_reserves_takeon_base.json"\n'
     '                         % (_amount_m(stated), _amount_m(block)))\n'
     '    takeon = float(entry["takeon_m"])\n'
     '    opening = block + takeon\n'
     '    out = copy.deepcopy(cm)\n'
     '    pyd = safe_float(cm.get("prior_year_development_gbp_m"))\n'
     '    out["opening_reserves_gbp_m"] = opening\n'
     '    out["prior_year_development_pct"] = 100.0 * pyd / opening if pyd is not None else None\n'
     '    out["data_quality_notes"] = " ".join(n for n in (\n'
     '        cm.get("data_quality_notes") or "",\n'
     '        "[OPENING RESERVES ADJUSTED FOR A TAKE-ON: %s, the %s at 1 January plus %s of gross claims reserves taken on "\n'
     '        "in the year, register data/opening_reserves_takeon_base.json]"\n'
     '        % (_amount_m(opening), _amount_m(block), _amount_m(takeon))) if n)\n'
     '    return out\n'),
    ('        # opening reserves adopted from data/opening_reserves_confirmed.json (eighth amendment)\n'
     '        "confirmed_openings_applied": 0,\n',
     '        # opening reserves adopted from data/opening_reserves_confirmed.json (eighth amendment)\n'
     '        "confirmed_openings_applied": 0,\n'
     '        # take-ons added to the opening reserves from data/opening_reserves_takeon_base.json (ninth amendment)\n'
     '        "takeon_base_applied": 0,\n'),
    ('    opening_register = load_opening_reserves_confirmed()\n',
     '    opening_register = load_opening_reserves_confirmed()\n'
     '    takeon_base_register = load_takeon_base()\n'),
    ('        if basis_key in opening_register:\n'
     '            cm = apply_confirmed_opening(cm, opening_register[basis_key])\n'
     '            models[canonical_key] = cm\n'
     '            counters["confirmed_openings_applied"] += 1\n',
     '        if basis_key in opening_register:\n'
     '            cm = apply_confirmed_opening(cm, opening_register[basis_key])\n'
     '            models[canonical_key] = cm\n'
     '            counters["confirmed_openings_applied"] += 1\n'
     '        # A take-on the adopted development covers, added to the opening reserves for the registered records only\n'
     '        # (ninth amendment): after the confirmed opening reserves, which its entry may name, and before the FX conversion.\n'
     '        if basis_key in takeon_base_register:\n'
     '            cm = apply_takeon_base(cm, takeon_base_register[basis_key])\n'
     '            models[canonical_key] = cm\n'
     '            counters["takeon_base_applied"] += 1\n'),
    ('    log(f"  Confirmed opening reserves applied: {counters[\'confirmed_openings_applied\']}")\n',
     '    log(f"  Confirmed opening reserves applied: {counters[\'confirmed_openings_applied\']}")\n'
     '    log(f"  Take-ons added to the opening reserves: {counters[\'takeon_base_applied\']}")\n'),
    ('        "confirmed_openings_applied": counters["confirmed_openings_applied"],\n',
     '        "confirmed_openings_applied": counters["confirmed_openings_applied"],\n'
     '        "takeon_base_applied": counters["takeon_base_applied"],\n'),
]
RUNID_SUBS = [('(ra, "OPENING_RESERVES_CONFIRMED"), (assumed_business, "RITC_SCAN"), (assumed_business, "TRANSFER_REGISTER"))',
               '(ra, "OPENING_RESERVES_CONFIRMED"), (ra, "TAKEON_BASE_REGISTER"), (assumed_business, "RITC_SCAN"),\n'
               '          (assumed_business, "TRANSFER_REGISTER"))')]
CFT_SUBS = [('{"confirmed_figures_applied", "takeon_excluded", "confirmed_openings_applied"}',
             '{"confirmed_figures_applied", "takeon_excluded", "confirmed_openings_applied", "takeon_base_applied"}')]
PURPOSE = (
    "Take-ons the adopted development covers while the opening reserves do not, for records the extraction error-rate "
    "study (PLAN R213, ninth amendment) found by two readings of the filing: a triangle that carries business taken into "
    "the syndicate in the report year on both diagonals of its step, or a provisions note whose prior-year line follows "
    "the take-on row of the same roll-forward. run_analysis.py (load_and_classify, apply_takeon_base) adds takeon_m, the "
    "gross claims reserves the filing states were transferred in the report year, to the opening reserves of these "
    "records only, after the confirmed opening reserves and before the FX conversion, recomputes the development "
    "percentage, and discloses the adjustment in the record's data_quality_notes; the development figure and its route "
    "are left as they are. opening_reserves_m is the gross claims outstanding at 1 January before the transfer, and the "
    "loader refuses an entry whose figure is not the record's within 2%. Amounts are in millions of the report's own "
    "currency. The loader refuses an entry without two readings, its pages and a quote; an entry marked _to_complete is "
    "skipped, not applied, until it carries them.")


def patched(path, subs):
    text = io.open(str(path), encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in subs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if text.count(old) != 1:
            raise SystemExit("%s: anchor found %d times, nothing written: %r" % (path.name, text.count(old), old[:90]))
        text = text.replace(old, new)
    return text


if REG.exists():
    raise SystemExit("%s exists already, nothing written" % REG.name)
out = {RA: patched(RA, LOADER), RUNID: patched(RUNID, RUNID_SUBS), CFT: patched(CFT, CFT_SUBS)}
for path, text in out.items():
    io.open(str(path), "w", encoding="utf-8", newline="").write(text)
io.open(str(REG), "w", encoding="utf-8", newline="").write('{\n "_purpose": %s\n}\n' % __import__("json").dumps(PURPOSE, ensure_ascii=False))
print("patched %s; wrote %s" % (", ".join(p.name for p in out), REG.name))
