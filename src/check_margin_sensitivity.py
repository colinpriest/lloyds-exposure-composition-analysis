"""Management-margin sensitivity: the adopted model without the syndicates that state a held margin (D3-2).

The measured series is the movement in each syndicate's booked UK GAAP claims provisions. Many syndicates book those
provisions with a management margin above the actuarial best estimate (the review of 2 October 2026, M-3), so margin
builds and releases may enter the movements whose dispersion the model fits. data/margin_disclosure.json records the
working-sample filings that say so, from the review's pattern scan, each hit read and classified: held (a margin is
carried), conditional ("a margin may be applied"), contradicting ("no margin ..."), or unclear.

This refits the adopted model (adopted_model.scale_block; nothing changed but which observations are included):
  * without every syndicate that states a held margin in any year (31 syndicates at the PC rescan of 5 October 2026);
  * without those and the syndicates whose filings say only that a margin may be applied (35);
  * without every syndicate the scan hit (37);
and, for EACH variant, two controls over N_CONTROL draws each, so that the loss of sample, 36% to 40% of the records
and 39% to 41% of the size proxy, can be told from a margin effect:
  * a record-level control: the same number of records drawn at random, matched on the size proxy's deciles (the
    opening reserves R). It leaves out the variant's number of records but keeps 106 to 117 of the 118 syndicates
    (200 draws, measured), where the variant keeps 81 to 87, and 14 to 32 of the 38 RITC records (mean 22 to 24),
    where the variant keeps 26 to 31;
  * a whole-syndicate control: random whole syndicates left out, drawn from the syndicates the variant keeps, matched
    on the syndicates' size (their total R, in quartiles) and, by rejection, on the records left out and their share
    of the size proxy (each within MATCH_TOLERANCE of the variant's). This is the like-for-like comparator: it removes
    syndicates, not scattered records, so the year effects and the RITC regime are confounded as the variant's are
    (the stage-3 review, finding 3). It keeps the variant's number of syndicates exactly, and, by rejection, the
    variant's RITC count to within RITC_TOLERANCE records (on the register of 5 October 2026 and the
    regenerated working sample: a tolerance of 1 accepts a draw at 254, 365 and 29 tries for the 31-, 35- and
    37-syndicate variants on one seed of 100 draws, and at 239 to 290, 345 to 390 and 27 to 30 over the verifier's five
    seeds of 200 draws, so the rejection costs seconds, and the controls keep 30 to 32 RITC records
    against the variant's 31, and 25 to 27 against 26). The variants leave out 241, 255 and 268 of the 674 records on
    the regenerated sample (the committed sample before the regeneration gives 242, 256 and 269): read the counts
    from the regenerated results, not from this text. Each fit records n_ritc_kept.

How to read it. The comparison gives an indication of whether stated margins move k, gamma, the floor or the tail
indices, separated from the loss of sample; it does not show that margins have no effect. The flag is a lower bound
(the scan read PDFs only, so the 2024 filings published as HTML are unread until the PC rescans them), so the
records kept still hold unflagged margins, and a small shift is not evidence of none. A variant's mean outside the
minimum to maximum of n control means happens with probability 2/(n+1) with no effect at all (2 in 9, 22%, at n = 8),
so each row also carries the standardised distance from the control mean in units of the control's own sd.

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
#: the whole-syndicate control matches on quartiles of the syndicates' total R (the flagged syndicates are mostly
#: large: with quintiles the 34-syndicate variant needs 13 syndicates from a stratum holding 10 unflagged ones), and
#: by rejection on the records left out and their share of R, each within MATCH_TOLERANCE of the variant's
N_SYNDICATE_STRATA = 4
MATCH_TOLERANCE = 0.10
#: and on the RITC records left out, within this many of the variant's. Measured over 100 draws (tries per accepted
#: draw) on the register of 5 October 2026 (31-, 35- and 37-syndicate variants) and the regenerated working sample, one
#: seed of 100 draws: a tolerance of 3 took 100, 112 and 10, 1 took 254, 365 and 29 (239 to 290, 345 to 390 and 27 to 30
#: over five seeds of 200 draws), and 0 took 709, 1,103 and 69, so 1 is feasible with margin and keeps the RITC count
#: within 1 of the variant's (the 8-draw runs take 3,417, 3,526 and 192 tries)
RITC_TOLERANCE = 1
MAX_TRIES = 200000
CONTROL_KINDS = ("record", "syndicate")
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


def syndicate_control_masks(R, syn, left_syndicates, n_draws, rng, n=N_SYNDICATE_STRATA, tol=MATCH_TOLERANCE,
                            max_tries=MAX_TRIES, ritc=None, ritc_tol=None):
    """(masks of the records KEPT, tries): `n_draws` distinct sets of whole syndicates left out, each drawn from the
    syndicates the variant keeps, in the same number per stratum of total R as `left_syndicates`, and accepted only
    if the records left out and their share of R are within `tol` of the variant's. The draws are cheap (no fit), so
    the rejection costs nothing; it is needed because the flagged syndicates hold more records than syndicates of
    their size do (a stratified draw alone leaves out about 17% fewer records). With `ritc` (the RITC flags) and
    `ritc_tol`, a draw must also leave out within `ritc_tol` RITC records of the variant's, so that the controls keep
    about the variant's RITC count (nu_RITC is fitted on those records)."""
    synds = np.array(sorted(set(syn.tolist())))
    total = np.array([R[syn == s].sum() for s in synds])
    edges = np.percentile(total, np.linspace(0, 100, n + 1))
    edges[-1] += 1e-9
    stratum = np.clip(np.digitize(total, edges) - 1, 0, n - 1)
    flagged = np.isin(synds, list(left_syndicates))
    need = [int((flagged & (stratum == d)).sum()) for d in range(n)]
    pool = [np.where(~flagged & (stratum == d))[0] for d in range(n)]
    if any(k > len(p) for k, p in zip(need, pool)):
        raise ValueError("a size stratum holds fewer unflagged syndicates (%s) than the variant leaves out (%s)"
                         % ([len(p) for p in pool], need))
    left = np.isin(syn, list(left_syndicates))
    target_n, target_r = int(left.sum()), float(R[left].sum())
    target_ritc = None if ritc is None else int(np.sum(ritc[left]))
    masks, seen, tries = [], set(), 0
    while len(masks) < n_draws:
        tries += 1
        if tries > max_tries:
            raise RuntimeError("no %d whole-syndicate draws within %.0f%% of the variant's records and size in %d "
                               "tries" % (n_draws, 100 * tol, max_tries))
        pick = np.concatenate([rng.choice(p, k, replace=False) for p, k in zip(pool, need) if k])
        key = tuple(sorted(pick.tolist()))
        if key in seen:
            continue
        out = np.isin(syn, synds[pick])
        if abs(out.sum() - target_n) <= tol * target_n and abs(R[out].sum() - target_r) <= tol * target_r and (
                ritc is None or abs(int(np.sum(ritc[out])) - target_ritc) <= ritc_tol):
            seen.add(key)
            masks.append(~out)
    return masks, tries


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


def summarise(result, mask, syn, label, spec, R=None, ritc=None):
    """The record of one fit: what it left out, the reported parameters and their gaps from the headline."""
    d = result["draws"]
    out = {"label": label, "spec": spec, "n": int(mask.sum()), "n_left_out": int((~mask).sum()),
           "n_syndicates": int(len(set(syn[mask].tolist()))),
           "n_ritc_kept": None if ritc is None else int(np.sum(ritc[mask])),
           "share_of_R_left_out": None if R is None else float(R[~mask].sum() / R.sum()),
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
    """Each reported parameter's mean across the control draws, the range those draws span and their sd."""
    out = {}
    for p in REPORT:
        vals = [c[p]["mean"] for c in controls if p in c]
        if vals:
            out[p] = {"n_draws": len(vals), "mean_of_means": float(np.mean(vals)), "min": float(np.min(vals)),
                      "max": float(np.max(vals)),
                      "sd_of_means": float(np.std(vals, ddof=1)) if len(vals) > 1 else None}
    return out


def versus_control(value, spread):
    """One variant mean against one control's spread: the min-max flag and the standardised distance (the distance
    from the control mean in units of the control's own sd; None if the sd is unknown or zero)."""
    lo, hi, sd = spread["min"], spread["max"], spread["sd_of_means"]
    diff = value - spread["mean_of_means"]
    n = spread["n_draws"]
    return {"control_mean_of_means": spread["mean_of_means"], "control_sd_of_means": sd, "n_draws": n,
            "control_range_of_means": [lo, hi], "variant_minus_control_mean": diff,
            "standardised_distance": (diff / sd) if sd else None,
            "variant_outside_control_range": bool(not lo <= value <= hi),
            "chance_outside_range_with_no_effect": 2.0 / (n + 1)}


def assemble(variants, controls, headline, syndicates, n_control, n_sample, matching=None):
    """The results record from the fitted summaries (separated from the fitting so its form can be tested).
    `controls` is {kind: {variant: [control summaries]}} for the kinds in CONTROL_KINDS; `matching` is the whole-
    syndicate control's rejection record, {variant: {...}}."""
    spread = {kind: {name: control_spread(cs) for name, cs in per.items()} for kind, per in controls.items()}
    reading = {}
    for name, v in variants.items():
        reading[name] = {}
        for p in REPORT:
            if p not in v:
                continue
            row = {"shift_from_headline": v[p]["mean"] - float(headline[p]["mean"]), "variant_mean": v[p]["mean"],
                   "versus_control": {}}
            for kind in CONTROL_KINDS:
                sp = spread.get(kind, {}).get(name, {})
                if p in sp:
                    row["versus_control"][kind] = versus_control(v[p]["mean"], sp[p])
            reading[name][p] = row
    return {
        "purpose": ("the adopted model refitted without the syndicates whose filings state a management margin above "
                    "the best estimate, against size-matched random exclusions: records at random and whole "
                    "syndicates at random, for each variant (decision D3-2, 4 October 2026; the stage-3 review, "
                    "finding 3)"),
        "source": "data/margin_disclosure.json",
        "flag_is_a_lower_bound": ("the scan read the PDFs only: the 2024 filings published as HTML are unread until "
                                  "the PC rescans them, so the records kept still hold unflagged margins"),
        "n_sample": int(n_sample),
        "syndicates_left_out": syndicates,
        "controls_design": {
            "n_draws_each": int(n_control), "seed": SEED,
            "record": {"matched_on": "the deciles of the opening reserves R (the size proxy), per variant",
                       "caveat": ("it leaves out records drawn at random, the variant whole syndicates: it keeps "
                                  "106 to 117 of the 118 syndicates, the variant 81 to 87, and on average 22 to 24 "
                                  "RITC records to the variant's 27 to 32 (measured over 200 draws), so it "
                                  "understates the spread a syndicate-level exclusion of the same size would show")},
            "syndicate": {"matched_on": ("quartiles of the syndicates' total R, then by rejection on the records left "
                                         "out and their share of R, each within %.0f%% of the variant's, and on the "
                                         "RITC records left out, within %d of the variant's"
                                         % (100 * MATCH_TOLERANCE, RITC_TOLERANCE)),
                          "drawn_from": "the syndicates the variant keeps",
                          "n_strata": N_SYNDICATE_STRATA, "tolerance": MATCH_TOLERANCE,
                          "per_variant": matching or {},
                          "caveat": ("it removes whole syndicates as the variant does and keeps the same number of "
                                     "them, and the RITC records it keeps are within %d of the variant's (each fit "
                                     "records n_ritc_kept), but it leaves out 3 to 10%% fewer records than the "
                                     "variant (about 8%% on average) and a slightly smaller share of the size proxy "
                                     "(measured over 200 draws; the per-draw figures are in per_variant), and its draws are from syndicates whose margin "
                                     "disclosure is unflagged, not known to be none (the flag is a lower bound)"
                                     % RITC_TOLERANCE)},
            "min_max_flag_caveat": ("a variant mean outside the minimum to maximum of n control means happens with "
                                    "probability 2/(n+1) with no effect (2 in 9, 22%, at n = 8): read the "
                                    "standardised distance beside it")},
        "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS},
        "headline": {p: {"mean": float(headline[p]["mean"]), "sd": float(headline[p]["sd"])}
                     for p in REPORT if p in headline},
        "variants": variants,
        "controls": controls,
        "control_spread": spread,
        "comparison": reading,
        "reading": ("each variant against its two matched controls gives an indication of whether stated margins "
                    "move the fitted parameters beyond what the loss of sample does; it is not proof of no effect, "
                    "because the flag is a lower bound, and a small shift does not show there is none. The "
                    "whole-syndicate control is the like-for-like comparator; the record-level control keeps more "
                    "syndicates and more RITC records than the variant, so it understates the spread"),
    }


def run(n_control=N_CONTROL, fit_fn=fit):
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    rng = np.random.default_rng(SEED)
    sets = margin_variants()
    variants = {}
    for name, synds in sets.items():
        keep = ~np.isin(syn, synds)
        variants[name] = summarise(fit_fn(keep, name), keep, syn, name,
                                   "the adopted model without the %d syndicates of %s" % (len(synds), name),
                                   R, ritc)
    controls = {kind: {} for kind in CONTROL_KINDS}
    matching = {}
    for name, synds in sets.items():
        out = np.isin(syn, synds)
        masks = {"record": control_masks(R, out, n_control, rng)}
        masks["syndicate"], tries = syndicate_control_masks(R, syn, synds, n_control, rng, ritc=ritc,
                                                            ritc_tol=RITC_TOLERANCE)
        matching[name] = {"tries": int(tries), "accepted": int(n_control),
                          "variant_records_left_out": int(out.sum()),
                          "variant_share_of_R_left_out": float(R[out].sum() / R.sum()),
                          "variant_ritc_left_out": int(ritc[out].sum()), "ritc_tolerance": RITC_TOLERANCE,
                          "draws_ritc_left_out": [int(ritc[~m].sum()) for m in masks["syndicate"]],
                          "draws_records_left_out": [int((~m).sum()) for m in masks["syndicate"]],
                          "draws_share_of_R_left_out": [float(R[~m].sum() / R.sum()) for m in masks["syndicate"]]}
        for kind in CONTROL_KINDS:
            controls[kind][name] = []
            for i, keep in enumerate(masks[kind]):
                label = "%s_%s_control_%d" % (name, kind, i + 1)
                spec = ("the adopted model without %s matched to %s" %
                        ("records drawn at random, on size decile" if kind == "record"
                         else "whole syndicates drawn at random, on size, records and share of R", name))
                controls[kind][name].append(summarise(fit_fn(keep, label), keep, syn, label, spec, R, ritc))
    return assemble(variants, controls, adopted_model.headline(), sets, n_control, len(S), matching)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    n_control = int(argv[0]) if argv and argv[0].isdigit() else N_CONTROL
    out = run(n_control)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    # for each variant and parameter: the shift from the headline, then the standardised distance from each control's
    # mean (and its sd); "*" marks a mean outside that control's min-max range, which happens 22% of the time with
    # no effect at n = 8, so the distance is the figure to read
    for name, row in out["comparison"].items():
        print(name)
        for p, r in row.items():
            parts = []
            for kind, vc in r["versus_control"].items():
                z = vc["standardised_distance"]
                parts.append("%s distance %s (control sd %s)%s" % (
                    kind, "n/a" if z is None else "%+.2f" % z,
                    "n/a" if vc["control_sd_of_means"] is None else "%.4f" % vc["control_sd_of_means"],
                    "*" if vc["variant_outside_control_range"] else ""))
            print("  %-9s shift %+.4f  %s" % (p, r["shift_from_headline"], "; ".join(parts)))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
