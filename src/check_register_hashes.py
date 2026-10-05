"""PC check: every source_file a register names hashes to the source_sha256 it records.

data/composition_page_readings.json and data/eligibility_from_filing.json each record, per entry, the filing the pages
were read in (source_file, relative to the filings folder) and that file's SHA-256. No test compares them with the files,
because the filings are not in this repository (a test that skipped without them would be no test), so this script
does it on the PC, where they are. It is not in the manifest: run it by hand after editing either register, or before
a recorded pass.

It exits 0 if every file is found and its hash matches, and 1 on any mismatch or missing file, naming each. The filings
folder is the first argument, else the LLOYDS_FILINGS_DIR environment variable, else
D:/dev/lloyds_reserve_stress_testing.

Run:  python src/check_register_hashes.py [filings_folder]
"""
import hashlib
import json
import os
import sys
from pathlib import Path

SD = Path(__file__).resolve().parent.parent
REGISTERS = (SD / "data" / "composition_page_readings.json", SD / "data" / "eligibility_from_filing.json")
DEFAULT_FILINGS = "D:/dev/lloyds_reserve_stress_testing"


def entries(path):
    """{key: entry} of a register's entries that name a source file (keys starting "_" are notes)."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict) and "source_file" in v}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(filings, registers=None):
    """[(register name, key, status, detail)] for every entry; status is "ok", "mismatch" or "missing"."""
    out = []
    for reg in (REGISTERS if registers is None else registers):
        for key, e in sorted(entries(reg).items()):
            f = Path(filings) / e["source_file"]
            if not f.is_file():
                out.append((Path(reg).name, key, "missing", str(f)))
                continue
            got, want = sha256_of(f), e.get("source_sha256")
            out.append((Path(reg).name, key, "ok" if got == want else "mismatch",
                        "%s: file %s, register %s" % (e["source_file"], got, want)))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    filings = argv[0] if argv else os.environ.get("LLOYDS_FILINGS_DIR", DEFAULT_FILINGS)
    rows = check(filings)
    bad = [r for r in rows if r[2] != "ok"]
    for name, key, status, detail in bad:
        print("%s %s: %s (%s)" % (name, key, status.upper(), detail))
    print("%d source files checked in %s: %d ok, %d mismatched or missing"
          % (len(rows), filings, len(rows) - len(bad), len(bad)))
    return 1 if bad or not rows else 0


if __name__ == "__main__":
    sys.exit(main())
