"""Draw the error-rate sample and write it out before anything is adjudicated (R163).

The protocol is `error-rate-protocol.md`, fixed before this ran. This does step 3 of it and
nothing else: it draws the sample, records the state it was drawn from, and stops. It does
not look at whether any record appears doubtful, because a sample chosen after that is not
a sample.

Two draws, kept apart:

  primary  n = 60, simple random without replacement from the working sample, seed 42.
           This is the one the rate is computed from.
  tail     the 20 largest transferred severities. Purposive, so it gets its own
           denominator and is never pooled with the primary. It is where an error moves
           the headline, which is exactly why pooling it would bias the rate upward.

The working sample is rebuilt from the records here rather than read from a fitted result,
because the fit has not been re-run yet: eligibility is the loader's own rule -- a record
with a development figure, a positive opening reserve and a gross basis.
"""
import glob
import io
import json
import os
from pathlib import Path

import numpy as np

EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
OUT = Path(r"C:/Users/colin/AppData/Local/Temp/claude/D--Latex-projects-BAJ---Lloyds-reserves-rescaling--claude-worktrees-fixed-effects-syndicate-repeats-fff692/9e91ee54-a3fb-43e4-ae67-a88d2e6ac499/scratchpad/round56")
SAMPLE = OUT / "error-rate-sample.json"

N_PRIMARY = 60
N_TAIL = 20
SEED = 42


def canonical(d):
    """The model block the loader would adopt."""
    ms = d.get("models") or {}
    if not ms:
        return None
    ks = sorted(ms)
    if (d.get("validation") or {}).get("passed") is True:
        return ms[ks[0]]
    cands = [(k, ms[k].get("prior_year_movement_confidence") or 0) for k in ks
             if ms[k].get("prior_year_development_pct") is not None]
    return ms[max(cands, key=lambda x: x[1])[0]] if cands else None


if SAMPLE.exists():
    raise SystemExit("%s already exists; the protocol says it is not redrawn" % SAMPLE.name)

rows = []
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*.json"))):
    stem = os.path.basename(p)[:-5]
    if "inception" in stem or not stem.count("_") == 2:
        continue
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        continue
    m = canonical(d)
    if m is None:
        continue
    pyd = m.get("prior_year_development_gbp_m")
    opening = m.get("opening_reserves_gbp_m")
    if not isinstance(pyd, (int, float)) or not isinstance(opening, (int, float)):
        continue
    if opening <= 0:
        continue
    rows.append({
        "stem": stem,
        "prior_year_development": float(pyd),
        "opening_reserves": float(opening),
        "severity": abs(float(pyd)) / float(opening),
        "currency": m.get("currency"),
        "prompt_version": (d.get("spec") or {}).get("driver_prompt_version"),
        "route": (m.get("_pyd_route") or {}).get("source"),
    })

rows.sort(key=lambda r: r["stem"])
n = len(rows)
if n < N_PRIMARY:
    raise SystemExit("only %d eligible record(s); the protocol asks for %d" % (n, N_PRIMARY))

rng = np.random.default_rng(SEED)
idx = rng.choice(n, size=N_PRIMARY, replace=False)
primary = [rows[int(i)]["stem"] for i in sorted(idx)]

by_sev = sorted(rows, key=lambda r: -r["severity"])[:N_TAIL]
tail = [r["stem"] for r in by_sev]

overlap = sorted(set(primary) & set(tail))
at_212 = sum(1 for r in rows if r["prompt_version"] == "2.12")

payload = {
    "protocol": "error-rate-protocol.md, fixed before this sample was drawn",
    "drawn": "2026-09-11",
    "seed": SEED,
    "population": {
        "description": ("records with a development figure and a positive opening reserve: "
                        "the loader's eligibility, rebuilt from the records because the fit "
                        "has not been re-run"),
        "n": n,
        "n_at_prompt_2_12": at_212,
    },
    "primary": {
        "kind": "simple random sample without replacement",
        "n": len(primary),
        "stems": primary,
        "note": "the rate is computed from this sample and this sample only",
    },
    "tail": {
        "kind": "purposive: the largest transferred severities",
        "n": len(tail),
        "stems": tail,
        "note": ("reported with its own denominator and never pooled with the primary "
                 "sample; pooling a purposive stratum into a random one biases the rate "
                 "upward"),
    },
    "overlap_primary_and_tail": overlap,
    "overlap_note": ("a record in both is adjudicated once and counted in both strata, "
                     "which are reported separately"),
}
json.dump(payload, io.open(SAMPLE, "w", encoding="utf-8"), indent=1)
print("population: %d eligible record(s), %d at prompt 2.12" % (n, at_212))
print("primary sample: %d stems" % len(primary))
print("tail stratum:   %d stems" % len(tail))
print("overlap:        %d" % len(overlap))
print("written to %s -- not redrawn" % SAMPLE.name)
