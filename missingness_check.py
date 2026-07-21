"""#5 missingness test: are extraction failures systematically size-biased?

Reserves are unavailable for a failed extraction, so we cannot observe the failed filing's size
directly. But most failure-prone syndicates ALSO have successful years, so we can probe size via
those. If syndicates that suffer extraction failures are NOT systematically smaller than those
that never fail, the missingness is (with respect to size) not informative — a null result that
closes the size-bias concern.

Tests (opening reserves = size proxy; a filing is 'failed' if neither LLM returned reserves):
  A. Per syndicate: median size of syndicates with >=1 failed year vs syndicates with 0 failures.
  B. Per filing: syndicate median size of FAILED filings vs SUCCESSFUL filings (paired to the
     same-syndicate successful-year size, so each failed filing is scored by its own syndicate).
  C. Year distribution of failures (failures are expected to cluster in early scanned years, i.e.
     confounded with vintage, not size).

Run: python missingness_check.py
"""
import io, json, glob
from pathlib import Path
import numpy as np
from scipy import stats
from collections import defaultdict, Counter

SD = Path(__file__).resolve().parent


def scan():
    """Return list of (syndicate, year, reserves_or_None).
    Reserves are converted to GBP at the reporting-date H.10 spot rate for
    USD-presented reports (docs/fx-conversion.md), so sizes are comparable."""
    cs = json.load(io.open(SD / "pdf_extraction" / "currency_scan.json", encoding="utf-8"))
    fx = json.load(io.open(SD / "model" / "fx_rates_h10.json", encoding="utf-8"))
    cur = {k: v["currency"] for k, v in cs["reports"].items()}
    rates = {int(y): r["usd_per_gbp"] for y, r in fx["year_end_rates"].items()}
    rows = []
    for f in glob.glob(str(SD / "pdf_extraction" / "syndicate_*_*.json")):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
            md = d.get("models", {})
            res = None
            for mk in ("gemini-2.5-flash", "gpt-5-mini"):
                v = md.get(mk, {}).get("opening_reserves_gbp_m")
                if v is not None and v > 0:
                    res = float(v); break
            base = f.split("syndicate_")[1].replace(".json", "")
            s, y = base.rsplit("_", 1)
            if res is not None and cur.get(base) == "USD":
                res = res / rates[int(y)]
            rows.append((int(s), int(y), res))
        except Exception:
            pass
    return rows


def main():
    rows = scan()
    n = len(rows)
    failed = [r for r in rows if r[2] is None]
    ok = [r for r in rows if r[2] is not None]
    print(f"extraction files: {n}  |  successful (reserves): {len(ok)}  |  failed/empty: {len(failed)}")

    # syndicate median size from successful years
    by_syn = defaultdict(list)
    for s, y, res in ok:
        by_syn[s].append(res)
    syn_size = {s: float(np.median(v)) for s, v in by_syn.items()}

    fail_syn = {r[0] for r in failed}
    ok_syn = set(by_syn)
    # syndicates observed at all (have >=1 successful year)
    has_fail = [syn_size[s] for s in ok_syn if s in fail_syn]     # syndicates with >=1 failure AND a successful year
    no_fail = [syn_size[s] for s in ok_syn if s not in fail_syn]   # syndicates that never failed
    print(f"\nA. Per-syndicate size (median opening reserves, from successful years):")
    print(f"   syndicates with >=1 failed year (n={len(has_fail)}): median size £{np.median(has_fail):.0f}m")
    print(f"   syndicates with 0 failed years  (n={len(no_fail)}): median size £{np.median(no_fail):.0f}m")
    uA = stats.mannwhitneyu(has_fail, no_fail, alternative="two-sided")
    print(f"   Mann-Whitney U p={uA.pvalue:.3f}  ({'no size difference' if uA.pvalue>0.05 else 'DIFFERENT'})")

    # B. per FAILED filing, scored by its own syndicate's successful-year size (only failures whose
    #    syndicate has a successful year elsewhere), vs successful filings' own reserves
    fail_sizes = [syn_size[s] for s, y, _ in failed if s in syn_size]
    ok_sizes = [res for s, y, res in ok]
    n_orphan = sum(1 for s, y, _ in failed if s not in syn_size)
    print(f"\nB. Per-filing size proxy:")
    print(f"   failed filings scored by same-syndicate size (n={len(fail_sizes)}; {n_orphan} orphan failures with no successful year): median £{np.median(fail_sizes):.0f}m")
    print(f"   successful filings' own reserves (n={len(ok_sizes)}): median £{np.median(ok_sizes):.0f}m")
    uB = stats.mannwhitneyu(fail_sizes, ok_sizes, alternative="two-sided")
    print(f"   Mann-Whitney U p={uB.pvalue:.3f}  ({'no size difference' if uB.pvalue>0.05 else 'DIFFERENT'})")

    # C. year distribution of failures (vintage confound)
    fy = Counter(y for _, y, _ in failed); ty = Counter(y for _, y, _ in rows)
    print(f"\nC. Failure rate by year (failures cluster in older scanned vintages, not by size):")
    for y in sorted(ty):
        print(f"   {y}: {fy.get(y,0):>3} / {ty[y]:>3}  ({100*fy.get(y,0)/ty[y]:>4.0f}%)")

    # D. The test that actually matters for a CONDITIONAL model: does failure-proneness predict
    #    SEVERITY given size? (size-biased missingness is harmless if, conditional on size, the
    #    severity of failure-prone syndicates matches everyone else's -> MAR wrt the outcome.)
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    Sarr = np.array([o["s_raw_a"] for o in recs]); Rarr = np.array([o["opening_reserves_gbp_m"] for o in recs])
    fp = np.array([o["syndicate"] in fail_syn for o in recs], float)   # failure-prone syndicate?
    X = np.column_stack([np.ones(len(Sarr)), np.log(Rarr / 500.0), fp])
    def ols(X, y):
        b, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ b
        s2 = (r @ r) / (len(y) - X.shape[1]); se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
        return b, se
    for yy, lbl in [(Sarr, "signed S"), (np.abs(Sarr), "|S| (dispersion)")]:
        b, se = ols(X, yy); t = b[2] / se[2]; p = 2 * (1 - stats.norm.cdf(abs(t)))
        print(f"\nD. {lbl} ~ 1 + logR + failure_prone:  failure_prone coef={b[2]:+.4f} (SE {se[2]:.4f}) "
              f"p={p:.3f}  ({'no outcome bias given size' if p>0.05 else 'OUTCOME DIFFERS'})")
    b, se = ols(X, np.abs(Sarr)); p_disp = 2 * (1 - stats.norm.cdf(abs(b[2] / se[2])))

    out = {"n_files": n, "n_success": len(ok), "n_failed": len(failed),
           "A_per_syndicate": {"median_size_has_failure": float(np.median(has_fail)),
                               "median_size_no_failure": float(np.median(no_fail)),
                               "n_has_failure": len(has_fail), "n_no_failure": len(no_fail), "p": float(uA.pvalue)},
           "B_per_filing": {"median_failed_synd_size": float(np.median(fail_sizes)),
                            "median_success_size": float(np.median(ok_sizes)),
                            "n_failed_scored": len(fail_sizes), "n_orphan": n_orphan, "p": float(uB.pvalue)},
           "C_failure_by_year": {int(y): [fy.get(y, 0), ty[y]] for y in sorted(ty)},
           "D_outcome_given_size": {"abs_S_failure_prone_coef": float(b[2]), "abs_S_p": float(p_disp)}}
    (SD / "results" / "missingness_check_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWrote missingness_check_results.json")


if __name__ == "__main__":
    main()
