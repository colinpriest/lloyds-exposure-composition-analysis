"""Build an observable reserve-maturity share for each syndicate-year.

Referee point: the severity S = M/R has a numerator restricted to MATURE underwriting
years (u <= t-2) but a denominator R that is TOTAL opening gross claims outstanding
(all underwriting years).  Writing phi = R_mature / R_total,

    S = M / R = phi * (M / R_mature),

so if phi varies systematically with reserve size, part of the fitted size gradient
could be a mechanical maturity artefact rather than risk pooling.

phi is not disclosed, but the gross claims-development triangle lets us approximate it.
For a report at reporting year t, each underwriting-year column carries n development
observations, and n is exactly its age at that report's valuation date.  The OPENING
balance sheet for year t is one year earlier, so a column with n observations has
opening age a = n - 1.  Mature (u <= t-2) is a >= 1; the young part of the opening
reserve is exactly the single most recent underwriting year, a = 0.

Weighting each underwriting year's latest ultimate estimate U_u by an unpaid fraction
w(a) = exp(-a/delta) converts ultimates into approximate reserves:

    phi(delta) = sum_{a>=1} U_a w(a) / sum_{a>=0} U_a w(a).

delta = inf reproduces the pure ultimate share (no run-off weighting); smaller delta
means faster run-off, which gives the young year more reserve weight and so pushes phi
down.  We report delta in {inf, 4, 2, 1} as a bracket rather than claiming one pattern.

Two truncations both bias phi DOWNWARD (i.e. overstate the young share, and so overstate
the potential confound): the triangle window omits the oldest mature years, and a
malformed column pair can double-count the young year.  The check is therefore
conservative.

Writes model/maturity_share.json keyed "{syndicate}_{year}".
Usage:  python build_maturity_share.py
"""
import io, json, glob, re
from pathlib import Path
import numpy as np

SD = Path(__file__).resolve().parent.parent
EXTRACT = SD / "pdf_extraction"
OUT = SD / "model" / "maturity_share.json"
DELTAS = [None, 4.0, 2.0, 1.0]          # None = infinity (pure ultimate share)
FNAME = re.compile(r"syndicate_(\d+)_(\d{4})\.json$")


def column_counts(tri):
    """Non-null count per underwriting-year column, layout-agnostic."""
    uy = tri.get("underwriting_years") or []
    rows = tri.get("development_rows") or []
    if not uy or not rows:
        return None, None
    cols, lasts = [], []
    for ci in range(len(uy)):
        vals = [r[ci] for r in rows if isinstance(r, (list, tuple)) and ci < len(r)]
        nn = [v for v in vals if v is not None and isinstance(v, (int, float))
              and np.isfinite(v)]
        cols.append(len(nn))
        lasts.append(float(nn[-1]) if nn else None)
    return cols, lasts


def triangular_ok(counts):
    """Accept a triangle whose non-null counts form 1,2,...,m (plus any all-null cols)."""
    pos = sorted(c for c in counts if c > 0)
    if len(pos) < 3:
        return False
    return pos == list(range(1, len(pos) + 1))


def phi_from(counts, lasts, delta):
    """phi = mature reserve share, with opening age a = count - 1."""
    num = den = 0.0
    for c, u in zip(counts, lasts):
        if c <= 0 or u is None:
            continue
        a = c - 1                                  # age at the OPENING balance date
        mag = abs(u)                               # ultimates are signed only on misparse
        w = 1.0 if delta is None else float(np.exp(-a / delta))
        den += mag * w
        if a >= 1:
            num += mag * w
    if den <= 0:
        return None
    return num / den


def main():
    files = sorted(glob.glob(str(EXTRACT / "syndicate_*_*.json")))
    print(f"extraction files: {len(files)}")
    out, stats = {}, {"files": len(files), "no_triangle": 0, "malformed": 0, "ok": 0}
    for fn in files:
        m = FNAME.search(fn.replace("\\", "/"))
        if not m:
            continue
        syn, yr = int(m.group(1)), int(m.group(2))
        try:
            d = json.load(io.open(fn, encoding="utf-8"))
        except Exception:
            continue
        best = None
        for mk, mv in (d.get("models") or {}).items():
            if not isinstance(mv, dict):
                continue
            for key in ("_claims_triangle", "_rag_triangle"):
                tri = mv.get(key)
                if not isinstance(tri, dict):
                    continue
                counts, lasts = column_counts(tri)
                if counts is None:
                    continue
                if not triangular_ok(counts):
                    continue
                cand = (sum(1 for c in counts if c > 0), mk, key, counts, lasts)
                if best is None or cand[0] > best[0]:
                    best = cand
        if best is None:
            stats["no_triangle"] += 1
            continue
        _, mk, key, counts, lasts = best
        rec = {"syndicate": syn, "year": yr, "source_model": mk, "source_field": key,
               "n_uw_years": sum(1 for c in counts if c > 0)}
        ok = True
        for delta in DELTAS:
            tag = "inf" if delta is None else f"{delta:g}"
            v = phi_from(counts, lasts, delta)
            if v is None:
                ok = False
                break
            rec[f"phi_delta_{tag}"] = v
        if not ok:
            stats["malformed"] += 1
            continue
        stats["ok"] += 1
        out[f"{syn}_{yr}"] = rec

    OUT.write_text(json.dumps({"stats": stats, "deltas": ["inf", "4", "2", "1"],
                               "records": out}, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    for tag in ("inf", "4", "2", "1"):
        v = np.array([r[f"phi_delta_{tag}"] for r in out.values()])
        print(f"phi(delta={tag:>3}): mean {v.mean():.3f}  median {np.median(v):.3f}  "
              f"p5 {np.percentile(v,5):.3f}  p95 {np.percentile(v,95):.3f}  min {v.min():.3f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
