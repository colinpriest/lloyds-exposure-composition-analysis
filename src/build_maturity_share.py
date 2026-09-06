"""Build an observable reserve-maturity share for each syndicate-year.

Referee point: the severity S = M/R has a numerator restricted to MATURE underwriting
years (u <= t-2) but a denominator R that is TOTAL opening gross claims outstanding
(all underwriting years).  Writing phi = R_mature / R_total,

    S = M / R = phi * (M / R_mature),

so if phi varies systematically with reserve size, part of the fitted size gradient
could be a mechanical maturity artefact rather than risk pooling.

phi is not disclosed, but the gross claims-development triangle lets us approximate it.
Membership is read from the triangle's UNDERWRITING-YEAR LABELS, not from column
counts (round 52, review finding M03).  For a report at reporting year t:

  * the OPENING balance sheet is dated 31 December t-1, so the opening reserve is
    carried by underwriting years u <= t-1 (year t has not been written at that date);
  * the MATURE numerator is restricted to u <= t-2 (the manuscript's rule);
  * a column's age at the opening date is a = (t-1) - u.

An ordinary triangle whose latest underwriting year is t therefore contributes its
columns u <= t-1 to the opening population and u <= t-2 to the mature part; a lagged
triangle whose latest year is t-1 contributes every column to the opening population
and all but the latest to the mature part.  The previous construction set a = count-1
from non-null counts and included every column, which put year t into a proxy for
OPENING reserves and called t-1 mature; for 1084/2015 that gave 0.898 where the
stated membership gives 0.709.

Each underwriting year's latest ULTIMATE estimate U_u is weighted by an unpaid fraction
w(a) = exp(-a/delta) to convert ultimates into approximate reserves:

    phi(delta) = sum_{u <= t-2} U_u w(a_u) / sum_{u <= t-1} U_u w(a_u).

delta = inf is the pure ultimate share; smaller delta means faster run-off, which
gives the young year more reserve weight and pushes phi down.  The check reports
delta in {inf, 4, 2, 1} as a bracket.  The latest ultimate is a proxy for the
opening unpaid reserve of that year, not the reserve itself: it overstates the
weight of old, largely paid years for delta = inf, which is why the run-off weights
are reported alongside.  Two truncations remain: the triangle window omits the
oldest mature years (biasing phi DOWN), and a grouped label such as "2013 and prior"
is read as its stated year (its members are mature in any case).

Records whose latest underwriting year is neither t nor t-1, or whose columns give
fewer than two opening years, are not usable and are counted in the statistics.

Writes model/maturity_share.json keyed "{syndicate}_{year}".
Usage:  python src/build_maturity_share.py
"""
import io, json, glob, re
from pathlib import Path
import numpy as np

SD = Path(__file__).resolve().parent.parent
EXTRACT = SD / "pdf_extraction"
OUT = SD / "model" / "maturity_share.json"
DELTAS = [None, 4.0, 2.0, 1.0]          # None = infinity (pure ultimate share)
FNAME = re.compile(r"syndicate_(\d+)_(\d{4})\.json$")
YEAR_IN_LABEL = re.compile(r"(19|20)\d{2}")


def parse_year(label):
    """An underwriting-year label as an int; '2013 and prior' reads as 2013."""
    if isinstance(label, (int, float)) and np.isfinite(label):
        return int(label)
    m = YEAR_IN_LABEL.search(str(label))
    return int(m.group(0)) if m else None


def column_ultimates(tri):
    """(underwriting year, non-null count, latest non-null ultimate) per column."""
    uy = tri.get("underwriting_years") or []
    rows = tri.get("development_rows") or []
    if not uy or not rows:
        return None
    out = []
    for ci, label in enumerate(uy):
        u = parse_year(label)
        vals = [r[ci] for r in rows if isinstance(r, (list, tuple)) and ci < len(r)]
        nn = [v for v in vals if v is not None and isinstance(v, (int, float)) and np.isfinite(v)]
        if u is None or not nn:
            continue
        out.append((u, len(nn), float(nn[-1])))
    return out


def membership(cols, t):
    """Split the columns by label into the opening population (u <= t-1) and the
    mature numerator (u <= t-2), with each year's age at the opening date.

    Returns (opening, mature, latest_uw_year) where opening/mature are lists of
    (u, age, ultimate), or None when the triangle is not usable: latest year outside
    {t, t-1}, or fewer than two opening years.
    """
    if not cols:
        return None
    latest = max(u for u, _, _ in cols)
    if latest not in (t, t - 1):
        return None
    opening = [(u, (t - 1) - u, ult) for u, _, ult in cols if u <= t - 1]
    if len(opening) < 2:
        return None
    mature = [(u, a, ult) for u, a, ult in opening if u <= t - 2]
    return opening, mature, latest


def phi_from(opening, mature, delta):
    """phi = mature share of the (run-off-weighted) opening ultimates."""
    def w(a):
        return 1.0 if delta is None else float(np.exp(-a / delta))
    den = sum(abs(ult) * w(a) for _, a, ult in opening)   # ultimates are signed only on misparse
    num = sum(abs(ult) * w(a) for _, a, ult in mature)
    if den <= 0:
        return None
    return num / den


def triangular_ok(counts):
    """Accept a triangle whose non-null counts form 1,2,...,m (plus any all-null cols)."""
    pos = sorted(c for c in counts if c > 0)
    if len(pos) < 3:
        return False
    return pos == list(range(1, len(pos) + 1))


def main():
    files = sorted(glob.glob(str(EXTRACT / "syndicate_*_*.json")))
    print(f"extraction files: {len(files)}")
    out = {}
    stats = {"files": len(files), "no_triangle": 0, "malformed": 0, "ok": 0,
             "latest_uw_year_offset": {}, "unusable_membership": 0}
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
                cols = column_ultimates(tri)
                if not cols:
                    continue
                if not triangular_ok([c for _, c, _ in cols]):
                    continue
                cand = (len(cols), mk, key, cols)
                if best is None or cand[0] > best[0]:
                    best = cand
        if best is None:
            stats["no_triangle"] += 1
            continue
        _, mk, key, cols = best
        mem = membership(cols, yr)
        if mem is None:
            stats["unusable_membership"] += 1
            continue
        opening, mature, latest = mem
        off = str(latest - yr)
        stats["latest_uw_year_offset"][off] = stats["latest_uw_year_offset"].get(off, 0) + 1
        rec = {"syndicate": syn, "year": yr, "source_model": mk, "source_field": key,
               "n_uw_years": len(cols), "latest_uw_year": latest,
               "opening_uw_years": [u for u, _, _ in opening],
               "mature_uw_years": [u for u, _, _ in mature],
               "membership_rule": "opening u <= t-1; mature u <= t-2; age = (t-1) - u"}
        ok = True
        for delta in DELTAS:
            tag = "inf" if delta is None else f"{delta:g}"
            v = phi_from(opening, mature, delta)
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
                               "membership_rule": ("labels: opening population u <= t-1, "
                                                   "mature numerator u <= t-2, age (t-1)-u; "
                                                   "latest ultimates as reserve proxies"),
                               "records": out}, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    for tag in ("inf", "4", "2", "1"):
        v = np.array([r[f"phi_delta_{tag}"] for r in out.values()])
        print(f"phi(delta={tag:>3}): n={len(v)} mean={v.mean():.3f} "
              f"p10={np.quantile(v, .1):.3f} p50={np.quantile(v, .5):.3f} p90={np.quantile(v, .9):.3f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
