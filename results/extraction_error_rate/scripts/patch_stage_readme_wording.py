r"""stage_extraction_error_rate.py: two README defects found on the first staging after refit 3.

  * The protocol's amendment count took every heading containing "amendment", so implementation note 4 ("...on the
    sixth amendment's question") counted as a tenth amendment. An amendment heading is one that opens "<Ordinal>
    amendment," or "Amendment,".
  * The take-on base census's records left as they are were listed with the scorer's raw reasons, Python values
    included ("(None, True)"). They are listed in plain words.

Each replacement must match exactly once, or nothing is written.

    python patch_stage_readme_wording.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
TARGET = SCR / "stage_extraction_error_rate.py"
REPLACEMENTS = [
    ('amendment_heads = re.findall(r"^## (.*[Aa]mendment.*)$", protocol_text, re.M)',
     'amendment_heads = re.findall(r"^## ((?:[A-Z][a-z]+ )?[Aa]mendment, .*)$", protocol_text, re.M)'),
    ('other9 = ["%s (%s)" % (key(r["stem"]), r["reason"]) for r in census9["table"] if r["outcome"] != "adjusted"',
     '# Both readings of 1110/2022 and 609/2014 find a covered transfer and no amount stated in the filing; the\n'
     '# first reading of 1084/2014 does not decide coverage. A reason with no plain wording stops the staging.\n'
     'PLAIN9 = {"a reading gives no transferred amount": "the filing states no amount for the covered transfer",\n'
     '          "the readings do not both find a covered transfer": "the two readings do not both find a covered transfer"}\n'
     '\n'
     '\n'
     'def plain9(reason):\n'
     '    bare = re.sub(r" \\((?:None|True|False|[-+0-9.e]+), (?:None|True|False|[-+0-9.e]+)\\)$", "", reason)\n'
     '    if bare not in PLAIN9:\n'
     '        raise SystemExit("no plain wording for the ninth census reason %r" % reason)\n'
     '    return PLAIN9[bare]\n'
     '\n'
     '\n'
     'other9 = ["%s (%s)" % (key(r["stem"]), plain9(r["reason"])) for r in census9["table"] if r["outcome"] != "adjusted"'),
]

raw = io.open(str(TARGET), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if "PLAIN9" in text:
    raise SystemExit("the staging script already has the plain reasons")
for old, new in REPLACEMENTS:
    n = text.count(old)
    if n != 1:
        raise SystemExit("expected once, found %d: %r" % (n, old[:90]))
    text = text.replace(old, new)
compile(text, TARGET.name, "exec")
io.open(str(TARGET), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print("patched %d sites in %s" % (len(REPLACEMENTS), TARGET.name))
