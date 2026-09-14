r"""Mutation check of the take-on base loader step (ninth amendment, point 5): each mutant must make its test fail.

A green test proves nothing on its own. Each mutation below breaks one promise of apply_takeon_base or its call in
load_and_classify; the named test module must then fail. The script restores src/run_analysis.py byte for byte after
every mutant, and refuses to start unless each anchor matches exactly once.

  guard      the 2% check on the entry's 1 January figure is removed
  order      the take-on is added before the confirmed opening reserves
  percent    the percentage is not recomputed on the adjusted reserves
  counter    takeon_base_applied is not counted
  fx         the take-on is added after the FX conversion
  run-id     the register is not hashed into the run identifier

    python mutate_takeon_base.py
"""
import io
import subprocess
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
RA = AN / "src" / "run_analysis.py"
ORIGINAL = RA.read_bytes()
TEXT = ORIGINAL.decode("utf-8")
NL = "\r\n" if "\r\n" in TEXT else "\n"

BASE_BLOCK = ('        # A take-on the adopted development covers, added to the opening reserves for the registered records only\n'
              '        # (ninth amendment): after the confirmed opening reserves, which its entry may name, and before the FX conversion.\n'
              '        if basis_key in takeon_base_register:\n'
              '            cm = apply_takeon_base(cm, takeon_base_register[basis_key])\n'
              '            models[canonical_key] = cm\n'
              '            counters["takeon_base_applied"] += 1\n')
OPEN_BLOCK = ('        if basis_key in opening_register:\n'
              '            cm = apply_confirmed_opening(cm, opening_register[basis_key])\n'
              '            models[canonical_key] = cm\n'
              '            counters["confirmed_openings_applied"] += 1\n')
FX_LINE = '        fx_info = apply_fx_conversion(data, cm, fname)\n'
MUTANTS = {
    "guard": ("src/test_takeon_base.py",
              [('    if block is None or block <= 0 or abs(block - stated) > 0.02 * stated:\n',
                '    if block is None:\n')]),
    "order": ("src/test_takeon_base.py", [(OPEN_BLOCK + BASE_BLOCK, BASE_BLOCK + OPEN_BLOCK)]),
    "percent": ("src/test_takeon_base.py",
                [('    out["prior_year_development_pct"] = 100.0 * pyd / opening if pyd is not None else None\n'
                  '    out["data_quality_notes"] = " ".join(n for n in (\n'
                  '        cm.get("data_quality_notes") or "",\n'
                  '        "[OPENING RESERVES ADJUSTED FOR A TAKE-ON',
                  '    out["data_quality_notes"] = " ".join(n for n in (\n'
                  '        cm.get("data_quality_notes") or "",\n'
                  '        "[OPENING RESERVES ADJUSTED FOR A TAKE-ON')]),
    "counter": ("src/test_takeon_base.py",
                [('            counters["takeon_base_applied"] += 1\n', '            pass\n')]),
    "fx": ("src/test_takeon_base.py", [(BASE_BLOCK, ""), (FX_LINE, FX_LINE + BASE_BLOCK)]),
    "run-id": ("src/test_run_id_inputs.py",
               [("OPENING_RESERVES_CONFIRMED, TAKEON_BASE_REGISTER, assumed_business.RITC_SCAN,",
                 "OPENING_RESERVES_CONFIRMED, assumed_business.RITC_SCAN,")]),
}

for name, (_test, subs) in MUTANTS.items():
    for old, _new in subs:
        n = TEXT.count(old.replace("\n", NL))
        if n != 1:
            raise SystemExit("mutant %s: anchor found %d times: %r" % (name, n, old[:80]))

caught = 0
try:
    for name, (test, subs) in MUTANTS.items():
        text = TEXT
        for old, new in subs:
            text = text.replace(old.replace("\n", NL), new.replace("\n", NL))
        RA.write_bytes(text.encode("utf-8"))
        run = subprocess.run([sys.executable, "-m", "pytest", test, "-q", "-x", "-p", "no:cacheprovider"], cwd=str(AN),
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [line for line in (run.stdout + run.stderr).strip().splitlines() if line.strip()][-1:]
        failed = run.returncode != 0
        caught += failed
        print("%-8s %s  (%s)" % (name, "caught" if failed else "SURVIVED", tail[0] if tail else "no output"))
        RA.write_bytes(ORIGINAL)
finally:
    RA.write_bytes(ORIGINAL)
if RA.read_bytes() != ORIGINAL:
    raise SystemExit("src/run_analysis.py was not restored")
print("mutants caught %d of %d; run_analysis.py restored" % (caught, len(MUTANTS)))
sys.exit(0 if caught == len(MUTANTS) else 1)
