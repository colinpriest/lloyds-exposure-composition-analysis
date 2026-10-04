"""Management-margin sensitivity: the adopted model without the syndicates that state a held margin (D3-2).

The measured series is the movement in each syndicate's booked UK GAAP claims provisions. Many syndicates book those
provisions with a management margin above the actuarial best estimate (the review of 2 October 2026, M-3), so margin
builds and releases may enter the movements whose dispersion the model fits. data/margin_disclosure.json records the
working-sample filings that say so, from the review's pattern scan, each hit read and classified: held (a margin is
carried), conditional ("a margin may be applied"), contradicting ("no margin ..."), or unclear.

This refits the adopted model (adopted_model.scale_block; nothing changed but which observations are included):
  * without every syndicate that states a held margin in any year (28 syndicates at the committed scan);
  * without those and the syndicates whose filings say only that a margin may be applied (32);
  * without every syndicate the scan hit (34);
and, as a control, without the same number of records as the 28-syndicate variant drawn at random, matched on the
size proxy's deciles (the opening reserves R), over N_CONTROL draws, so that the loss of sample, about 38% of the
records and 39% of the size proxy, can be told from a margin effect.

How to read it. The comparison gives an indication of whether stated margins move k, gamma, the floor or the tail
indices, separated from the loss of sample; it does not show that margins have no effect. The flag is a lower bound
(the scan read PDFs only, so the 2024 filings published as HTML are unread until the PC rescans them), so the
records kept still hold unflagged margins, and a small shift is not evidence of none.

Writes check_margin_sensitivity_results.json.
Usage:  python src/check_margin_sensitivity.py [n_control]
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytensor

pytensor.config.mode = "NUMBA"
import pymc as pm  # noqa: E402
import arviz as az  # noqa: E402

import adopted_model  # noqa: E402
from adopted_model import scale_block, SAMPLE_CORES  # noqa: E402

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_margin_sensitivity_results.json"
MARGINS = SD / "data" / "margin_disclosure.json"
SEED = 20261004
#: the sensitivity's fits are shorter than the headline's 1500/1500, as check_serial_sensitivity.py's are: they are
#: read for their shift against the control's spread, not as a published posterior
DRAWS, TUNE, CHAINS = 1000, 1000, 4
N_CONTROL = 8
N_DECILES = 10
#: the parameters the brief asks for, as the paper reads them
REPORT = ("k", "gamma", "sd_undiv", "nu_clean", "nu_ritc")
MAX_RHAT = 1.05


def margin_variants(path=MARGINS):
    """{variant: sorted syndicates left out}: held, held or conditional, any hit (data/margin_disclosure.json)."""
    with io.open(path, encoding="utf-8") as fh:
        reg = json.load(fh)
    held, cond, any_hit = set(), set(), set()
    for e in reg["entries"]:
        any_hit.add(e["syndicate"])
        if e["class"] == "held":
            held.add(e["syndicate"])
        elif e["class"] == "conditional":
            cond.add(e["syndicate"])
    return {"held_margin": sorted(held), "held_or_conditional": sorted(held | cond), "any_scan_hit": sorted(any_hit)}


def size_deciles(R, n=N_DECILES):
    edges = np.percentile(R, np.linspace(0, 100, n + 1))
    edges[-1] += 1e-9
    return np.clip(np.digitize(R, edges) - 1, 0, n - 1)


def control_masks(R, left_out, n_draws, rng, n=N_DECILES):
    """`n_draws` masks of the records KEPT, each leaving out records drawn at random from the whole sample in the
    same number per size decile as `left_out` (a boolean mask of the records the variant leaves out)."""
    dec = size_deciles(R, n)
    need = {d: int(np.sum(left_out & (dec == d))) for d in range(n)}
    out = []
    for _ in range(n_draws):
        keep = np.ones(len(R), bool)
        for d, k in need.items():
            if k:
                keep[rng.choice(np.where(dec == d)[0], k, replace=False)] = False
        out.append(keep)
    return out


def fit(mask, label):
    """The adopted model on the observations `mask` keeps, and nothing else changed."""
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    with pm.Model():
        b = scale_block(R=R[mask], H=H[mask], yr=yr[mask], ritc=ritc[mask])
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S[mask])
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    post = idata.posterior
    draws = {p: np.asarray(post[p]).ravel() for p in adopted_model.SHARED if p in post}
    rhat = float(az.rhat(idata).to_array().max())
    if rhat > MAX_RHAT:
        raise SystemExit("%s did not converge: max R-hat %.3f" % (label, rhat))
    _ok, rows = adopted_model.check_against_headline(draws)
    return {"draws": draws, "max_rhat": rhat, "divergences": int(idata.sample_stats["diverging"].sum()),
            "guard_rows": rows}


def summarise(result, mask, syn, label, spec):
    """The record of one fit: what it left out, the reported parameters and their gaps from the headline."""
    d = result["draws"]
    out = {"label": label, "spec": spec, "n": int(mask.sum()), "n_left_out": int((~mask).sum()),
           "n_syndicates": int(len(set(syn[mask].tolist()))),
           "max_rhat": result["max_rhat"], "divergences": result["divergences"],
           "must_match_headline": False,
           "why_it_need_not": "a subsample is expected to move the shared parameters; the comparison records how far",
           "headline_guard": result["guard_rows"]}
    for p in REPORT:
        if p in d:
            a = np.asarray(d[p], float)
            out[p] = {"mean": float(a.mean()), "sd": float(a.std()),
                      "interval_95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]}
    return out


def control_spread(controls):
    """Each reported parameter's mean across the control draws, and the range those draws span."""
    out = {}
    for p in REPORT:
        vals = [c[p]["mean"] for c in controls if p in c]
        if vals:
            out[p] = {"mean_of_means": float(np.mean(vals)), "min": float(np.min(vals)), "max": float(np.max(vals)),
                      "sd_of_means": float(np.std(vals, ddof=1)) if len(vals) > 1 else None}
    return out


def assemble(variants, controls, headline, syndicates, n_control, n_sample):
    """The results record from the fitted summaries (separated from the fitting so its form can be tested)."""
    spread = control_spread(controls)
    reading = {}
    for name, v in variants.items():
        reading[name] = {}
        for p in REPORT:
            if p not in v or p not in spread:
                continue
            shift = v[p]["mean"] - float(headline[p]["mean"])
            lo, hi = spread[p]["min"], spread[p]["max"]
            reading[name][p] = {"shift_from_headline": shift,
                                "variant_mean": v[p]["mean"],
                                "control_range_of_means": [lo, hi],
                                "variant_outside_control_range": bool(not lo <= v[p]["mean"] <= hi)}
    return {
        "purpose": ("the adopted model refitted without the syndicates whose filings state a management margin above "
                    "the best estimate, against a size-matched random exclusion (decision D3-2, 4 October 2026)"),
        "source": "data/margin_disclosure.json",
        "flag_is_a_lower_bound": ("the scan read the PDFs only: the 2024 filings published as HTML are unread until "
                                  "the PC rescans them, so the records kept still hold unflagged margins"),
        "n_sample": int(n_sample),
        "syndicates_left_out": syndicates,
        "control": {"n_draws": int(n_control), "matched_on": "the deciles of the opening reserves R (the size proxy)",
                    "matched_to": "held_margin", "seed": SEED},
        "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS},
        "headline": {p: {"mean": float(headline[p]["mean"]), "sd": float(headline[p]["sd"])}
                     for p in REPORT if p in headline},
        "variants": variants,
        "controls": controls,
        "control_spread": spread,
        "comparison": reading,
        "reading": ("this gives an indication of whether stated margins move the fitted parameters beyond what the "
                    "loss of sample does; it is not proof of no effect, because the flag is a lower bound and a "
                    "small shift does not show there is none"),
    }


def run(n_control=N_CONTROL, fit_fn=fit):
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    rng = np.random.default_rng(SEED)
    sets = margin_variants()
    variants = {}
    for name, synds in sets.items():
        keep = ~np.isin(syn, synds)
        variants[name] = summarise(fit_fn(keep, name), keep, syn, name,
                                   "the adopted model without the %d syndicates of %s" % (len(synds), name))
    held_out = np.isin(syn, sets["held_margin"])
    controls = []
    for i, keep in enumerate(control_masks(R, held_out, n_control, rng)):
        label = "control_%d" % (i + 1)
        controls.append(summarise(fit_fn(keep, label), keep, syn, label,
                                  "the adopted model without records drawn at random, matched on size decile"))
    return assemble(variants, controls, adopted_model.headline(), sets, n_control, len(S))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    n_control = int(argv[0]) if argv and argv[0].isdigit() else N_CONTROL
    out = run(n_control)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    for name, row in out["comparison"].items():
        print("%-20s " % name + "  ".join("%s %+.4f%s" % (p, r["shift_from_headline"],
                                                           "*" if r["variant_outside_control_range"] else "")
                                           for p, r in row.items()))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
