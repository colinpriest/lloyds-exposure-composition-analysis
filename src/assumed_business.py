r"""Which syndicate-years are in the assumed-business regime, and on what evidence.

The adopted model gives a record whose gross triangle carries liabilities accepted from
another syndicate its own tail regime. Until round 56 that regime was the RITC scan's flag and
nothing else. A loss portfolio transfer accepted from another syndicate does the same thing to
a triangle -- its diagonal is not the syndicate's own development -- and on 13 September 2026
the owner decided that confirmed inward transfers are treated like RITC (PLAN R195).

"Confirmed" means the hand adjudication in
pdf_extraction/audit/portfolio_transfer_adjudication.json: verdict genuine, direction inward
or both, whether the record is one the transfer scanner flagged ("records") or one found by
hand that it missed ("found_by_hand"). It is not the scanner's raw flag, which carried false
positives in round 56 and missed 2008/2021 and 3500/2018.

Every script that assigns the regime reads it from here, so the headline fit and each
sensitivity assign it the same way. A missing register is an error, not an empty set: an
analysis that quietly fell back to the RITC scan alone would look complete.

Strength, for the scripts that separate strong from weak RITC evidence: a confirmed transfer
was read by hand from the filing, so it counts as strong. Weak is what remains of the RITC
scan's weak flags.
"""
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RITC_SCAN = ROOT / "pdf_extraction" / "ritc_scan.json"
TRANSFER_REGISTER = ROOT / "pdf_extraction" / "audit" / "portfolio_transfer_adjudication.json"
TRANSFER_DIRECTIONS = ("inward", "both")


def sources(ritc_scan=RITC_SCAN, register=TRANSFER_REGISTER):
    """{"{syndicate}_{year}": [source, ...]} for every syndicate-year in the regime.

    A source is "ritc_<confidence>" as the scan records it (strong or weak) or
    "transfer_<direction>" (inward or both)."""
    out = {}
    with io.open(str(ritc_scan), encoding="utf-8") as fh:
        scan = json.load(fh)
    for k, v in scan.items():
        if isinstance(v, dict) and v.get("ritc_occurred"):
            out.setdefault(k, []).append("ritc_%s" % (v.get("confidence") or "unstated"))
    if not Path(register).exists():
        raise FileNotFoundError(
            "%s is missing: the assumed-business regime needs the transfer register as well "
            "as the RITC scan (PLAN R195). Copy it from the extraction repository." % register)
    with io.open(str(register), encoding="utf-8") as fh:
        reg = json.load(fh)
    for r in (reg.get("records") or []) + (reg.get("found_by_hand") or []):
        if r.get("verdict") == "genuine" and r.get("direction") in TRANSFER_DIRECTIONS:
            out.setdefault(str(r["stem"]), []).append("transfer_%s" % r["direction"])
    return out


def keys(**kw):
    """The syndicate-years in the regime."""
    return set(sources(**kw))


def strong_weak(**kw):
    """(strong, weak) key sets: strong RITC flags with confirmed transfers, and the RITC
    flags of weak confidence that are neither."""
    src = sources(**kw)
    strong = {k for k, s in src.items()
              if "ritc_strong" in s or any(x.startswith("transfer_") for x in s)}
    weak = {k for k, s in src.items() if "ritc_weak" in s and k not in strong}
    return strong, weak
