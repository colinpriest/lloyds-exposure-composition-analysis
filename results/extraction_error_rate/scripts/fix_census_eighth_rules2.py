r"""make_census_eighth.py: two refinements after the second dry run (census-eighth-dryrun2.log), before the amendment
is written or any record read.

  net_table        a page that introduces "both gross and net of reinsurance" tables, or prints "Gross and Net claims
                   liabilities" (a syndicate with no outward reinsurance), has a gross table: "gross and net" counts as a
                   gross heading (1225/2021, 1225/2024, 1945/2023, 2488/2017, 6103/2015, 6103/2023 were flagged without).
  takeon_triangle  "transferred to" matched transfers out of the syndicate ("Reserves transferred to Syndicate ...",
                   1200/2023 and 2024; 4000/2023; 1969/2021). A transfer or closure counts as inward only into this
                   syndicate: into "the syndicate", or into a syndicate named by this syndicate's own number.

Each anchor must match once.

    python fix_census_eighth_rules2.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "make_census_eighth.py"
EDITS = [
    ('and has no gross heading ("gross of reinsurance",',
     'and has no gross heading ("gross and net", "gross of reinsurance",'),
    ('syndicate, take-on, transferred to, from Syndicate N)',
     'syndicate, take-on, a transfer or closure into this syndicate, from Syndicate N)'),
    ('GROSS_HEAD = re.compile(r"gross of reinsurance|',
     'GROSS_HEAD = re.compile(r"gross and net|gross of reinsurance|'),
    ('INWARD = re.compile(r"accept|into (?:the|this) syndicate|take-on|taken on|transferred (?:in)?to|"\n'
     '                    r"\\bfrom (?:syndicate\\s*|s)\\d{3,4}", re.I)\n',
     'ACCEPTS = re.compile(r"\\baccept|into (?:the|this) syndicate\\b|take-on|taken on", re.I)\n'
     'TO_SYNDICATE = re.compile(r"(?:transferred|reinsured to close|closed)\\s+(?:in)?to\\s+(?:the\\s+|this\\s+)?"\n'
     '                          r"syndicate\\s*(\\d{3,4})?", re.I)\n'
     'FROM_SYNDICATE = re.compile(r"\\bfrom\\s+(?:syndicate\\s*|s)(\\d{3,4})\\b", re.I)\n'
     '\n'
     '\n'
     'def inward(w, syn):\n'
     '    """Whether a passage describes business coming into this syndicate: an acceptance, a take-on, a transfer or\n'
     '    closure into the syndicate or into this syndicate\'s own number, or business from another syndicate."""\n'
     '    if ACCEPTS.search(w):\n'
     '        return True\n'
     '    if any(m.group(1) is None or int(m.group(1)) == int(syn) for m in TO_SYNDICATE.finditer(w)):\n'
     '        return True\n'
     '    return any(int(m.group(1)) != int(syn) for m in FROM_SYNDICATE.finditer(w))\n'
     '\n'
     '\n'),
    ('        if (INWARD.search(w) and re.search(', '        if (inward(w, syn) and re.search('),
]

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "def inward(" in t:
    raise SystemExit("already refined")
for old, new in EDITS:
    if t.count(old) != 1:
        raise SystemExit("anchor found %d times: %r" % (t.count(old), old[:90]))
    t = t.replace(old, new)
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("make_census_eighth.py: 'gross and net' is a gross heading; a transfer is inward only into this syndicate")
