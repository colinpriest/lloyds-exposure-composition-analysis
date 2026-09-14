r"""stage_extraction_error_rate.py: the staged tree carries a .gitattributes marking every file -text.

The analysis repository runs with core.autocrlf=true, which rewrites line endings on checkin and checkout. Of the 805
files staged, 195 hold CRLF and 10 mixed endings (git ls-files --eol): git would store those with LF, and a Windows
checkout would give every LF file CRLF, so a clone would not hold the bytes MANIFEST.json hashes. With the attribute
git converts nothing: every checkout holds the staged bytes. The README's file list says so. (A first count of 802 CRLF
files came from Git Bash's grep, which does not see a line-end CR; git's count is the one above.)

Each replacement must match exactly once, or nothing is written.

    python patch_stage_gitattributes.py
"""
import io
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "stage_extraction_error_rate.py"
REPLACEMENTS = [
    ('- `MANIFEST.json`: every file with its SHA-256.\n"""',
     '- `MANIFEST.json`: every file with its SHA-256.\n'
     '- `.gitattributes`: marks every file here `-text`, so git converts no line endings and a checkout on any platform\n'
     '  holds the bytes MANIFEST.json hashes.\n"""'),
    ('io.open(str(OUT / "MANIFEST.json"), "w", encoding="utf-8", newline="\\n").write(\n'
     '    json.dumps({"files": manifest, "count": len(manifest)}, indent=1) + "\\n")\n',
     'io.open(str(OUT / "MANIFEST.json"), "w", encoding="utf-8", newline="\\n").write(\n'
     '    json.dumps({"files": manifest, "count": len(manifest)}, indent=1) + "\\n")\n'
     'io.open(str(OUT / ".gitattributes"), "w", encoding="utf-8", newline="\\n").write(\n'
     '    "# kept byte for byte: MANIFEST.json hashes these files as staged, line endings included\\n* -text\\n")\n'),
]

raw = io.open(str(TARGET), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if '".gitattributes"' in text:
    raise SystemExit("the staging script already writes .gitattributes")
for old, new in REPLACEMENTS:
    n = text.count(old)
    if n != 1:
        raise SystemExit("expected once, found %d: %r" % (n, old[:90]))
    text = text.replace(old, new)
compile(text, TARGET.name, "exec")
io.open(str(TARGET), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print("patched %d sites in %s" % (len(REPLACEMENTS), TARGET.name))
