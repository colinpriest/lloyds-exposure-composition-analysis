"""Copy the staged extraction error-rate study into the analysis repository at results/extraction_error_rate/, and check
every copied file against MANIFEST.json before anything is added to git.

Refuses if the target exists, or if the staged tree lacks the .gitattributes that marks its files -text. Without it the
repository's core.autocrlf=true would store the CRLF and mixed files with LF and give a Windows checkout CRLF for every
LF file, so a clone would not hold the hashed bytes. verify_a5_blobs.py checks the committed blobs.

    python copy_stage_to_analysis.py
"""
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "extraction_error_rate_staging"
DST = Path(r"D:\dev\IME-Lloyds-exposure-composition\results\extraction_error_rate")

if DST.exists():
    raise SystemExit("target exists: %s" % DST)
manifest = json.load(io.open(str(SRC / "MANIFEST.json"), encoding="utf-8"))
if manifest["count"] != len(manifest["files"]):
    raise SystemExit("the manifest's count disagrees with its list")
attrs = SRC / ".gitattributes"
if not attrs.exists() or b"* -text" not in attrs.read_bytes():
    raise SystemExit("the staged tree has no .gitattributes marking its files -text: re-run the staging")
shutil.copytree(str(SRC), str(DST))

bad = []
for f in manifest["files"]:
    data = (DST / f["path"]).read_bytes()
    if len(data) != f["bytes"] or hashlib.sha256(data).hexdigest() != f["sha256"]:
        bad.append(f["path"])
listed = {f["path"] for f in manifest["files"]} | {"MANIFEST.json", "README.md", ".gitattributes"}
present = {p.relative_to(DST).as_posix() for p in DST.rglob("*") if p.is_file()}
extra, missing = sorted(present - listed), sorted(listed - present)
print("copied %d files (%d in the manifest, plus MANIFEST.json, README.md and .gitattributes); hash or size "
      "mismatches %d; files not listed %d; listed but missing %d"
      % (len(present), manifest["count"], len(bad), len(extra), len(missing)))
for p in bad[:10] + extra[:10] + missing[:10]:
    print("   ", p)
sys.exit(1 if bad or extra or missing else 0)
