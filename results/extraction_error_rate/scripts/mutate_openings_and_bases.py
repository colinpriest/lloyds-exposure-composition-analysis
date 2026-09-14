r"""Mutation check: the tests of the confirmed opening reserves and the figure-less basis fail when the code is wrong.

Each mutation edits src/run_analysis.py in the analysis repository, runs the two test files, and expects a failure.
The file is restored byte for byte after every mutation, whatever happens, and its hash is checked at the end.

    python mutate_openings_and_bases.py
"""
import hashlib
import io
import re
import subprocess
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
P = AN / "src" / "run_analysis.py"
TESTS = ["src/test_confirmed_openings_and_bases.py", "src/test_run_id_inputs.py"]
MUTATIONS = [
    ("the opening reserves are never applied",
     "            cm = apply_confirmed_opening(cm, opening_register[basis_key])\n", "            pass\n"),
    ("the percentage is not recomputed on the confirmed opening",
     "    out[\"prior_year_development_pct\"] = 100.0 * pyd / opening if pyd is not None else None\n", "    pass\n"),
    ("a gross basis without a figure is accepted",
     "        if entry.get(\"basis\") not in (\"net\", \"unknown\"):\n", "        if False:\n"),
    ("an entry without a figure takes a gross basis",
     "\"basis\": entry[\"basis\"], \"register\": \"data/pyd_confirmed_figures.json\"}",
     "\"basis\": \"gross\", \"register\": \"data/pyd_confirmed_figures.json\"}"),
    ("the run identifier ignores the opening register",
     "                                   OPENING_RESERVES_CONFIRMED, assumed_business.RITC_SCAN,\n",
     "                                   assumed_business.RITC_SCAN,\n"),
]

original = P.read_bytes()
digest = hashlib.sha256(original).hexdigest()
text = original.decode("utf-8")
crlf = "\r\n" in text
norm = text.replace("\r\n", "\n")
caught = 0
try:
    for name, old, new in MUTATIONS:
        if norm.count(old) != 1:
            raise SystemExit("mutation %r: anchor found %d times" % (name, norm.count(old)))
        mutated = norm.replace(old, new)
        P.write_bytes((mutated.replace("\n", "\r\n") if crlf else mutated).encode("utf-8"))
        try:
            out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + TESTS, cwd=str(AN),
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            P.write_bytes(original)
        failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", out.stdout, re.M)
        ok = out.returncode != 0 and failed
        caught += bool(ok)
        print("%-58s %s (%d failing: %s)" % (name, "CAUGHT" if ok else "NOT CAUGHT", len(failed),
                                              ", ".join(f.split("::")[-1] for f in failed[:3])))
finally:
    P.write_bytes(original)
if hashlib.sha256(P.read_bytes()).hexdigest() != digest:
    raise SystemExit("run_analysis.py was not restored")
print("mutations caught: %d of %d; run_analysis.py restored (sha256 %s)" % (caught, len(MUTATIONS), digest[:12]))
if caught != len(MUTATIONS):
    sys.exit(1)
