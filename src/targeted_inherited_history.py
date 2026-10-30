"""Re-run selected inherited-history and fixed quantile-allocation sensitivities.

Writes only to a new output directory. These are conditional synthetic-outcome
scenarios, not eligibility estimates or bounds. Run from a clean checkout:
    python src/targeted_inherited_history.py --output-dir PATH
The original selected-case result remains in check_missingness_sensitivity_results.json.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import arviz
import numpy as np
import pymc
from scipy import stats

import check_missingness_sensitivity as original
from missingness_check import add_size_proxies, classify_filings

ROOT = Path(__file__).resolve().parent.parent
PERMUTATION_SEED = 20261031
FIT_SEED = original.SEED
SOURCE_PAGES = {
    '1729_2015': 28, '2014_2015': 33, '6117_2015': 22,
    '6125_2017': 27, '6130_2017': 12, '1980_2018': 29,
    '3902_2018': 25, '1947_2019': 33, '6133_2019': 38,
    '6134_2019': 36, '1996_2024': None,
}


def select_positive_screened(dispositions, audit, m01, rates):
    """Choose 41 audited positive openings and 11 source-checked M01 proxies.

    A positive whole-account amount does not prove original-year eligibility or
    compatibility with the unavailable mature outcome. For 1980/2018 the amount
    is a January transfer, not a pre-transfer opening. The current regime flag
    is retained because the transferor is not proven under the registry rule.
    """
    selected = []
    for entry in dispositions:
        if entry['category'] != 'structural_no_eligible_outcome':
            continue
        name = entry['file']
        row = dict(entry)
        source = audit.get(name)
        if source and isinstance(source.get('opening_gross_reserve_gbp_m'), (float, int)) and source['opening_gross_reserve_gbp_m'] > 0:
            raw = float(source['opening_gross_reserve_gbp_m'])
            currency = source['opening_gross_reserve_currency']
            if currency not in ('GBP', 'USD'):
                raise ValueError('unsupported currency for ' + name)
            rate = float(rates[entry['year']]) if currency == 'USD' else None
            row['size_proxy'] = raw / rate if rate else raw
            row['size_proxy_source'] = 'audited_source_opening'
            details = {'raw_amount_m': raw, 'source_currency': currency,
                       'usd_per_gbp': rate, 'source_page': source.get('opening_gross_reserve_page'),
                       'source_sha256': source['source_sha256']}
        elif name in m01:
            if not entry.get('size_proxy') or entry['size_proxy'] <= 0:
                raise ValueError('M01 record has no positive proxy: ' + name)
            row['size_proxy_source'] = 'source_checked_model_proxy'
            details = {'source_currency': 'model proxy converted to GBP where applicable',
                       'source_page': SOURCE_PAGES[Path(name).stem.removeprefix('syndicate_')],
                       'source_sha256': m01[name]['source_sha256']}
            if name == 'syndicate_3902_2018.json':
                row['size_proxy'] = 30.259  # exact source amount; first model rounded to 30.3
                row['size_proxy_source'] = 'exact_source_opening_replaces_rounded_model'
            if name == 'syndicate_1980_2018.json':
                row['size_proxy_source'] = 'transferred_base_assumed_compatible'
        else:
            continue
        row['sensitivity_source'] = details
        selected.append(row)
    return selected


def assigned_quantiles(n, allocation):
    """Return one reproducible placement; changing placement is a sensitivity."""
    quantiles = (np.arange(n) + 0.5) / n
    if allocation == 'permuted':
        quantiles = quantiles[np.random.default_rng(PERMUTATION_SEED).permutation(n)]
    elif allocation != 'original':
        raise ValueError('unknown allocation')
    return quantiles


def pseudo_inputs(dispositions, unavailable, unresolved, selected, R, H, calibration, allocation):
    records = unavailable + unresolved + selected
    size, hhi, year, imputation = original._pseudo_inputs(records, dispositions, R, H)
    q = assigned_quantiles(len(records), allocation)
    unit_t = stats.t.ppf(q, df=calibration['nu_clean'])
    effective_size = (size / original.REF) * (1 / hhi) ** calibration['gamma']
    sigma = np.sqrt(calibration['sd_undiv'] ** 2 + calibration['sd_div'] ** 2
                    * effective_size ** (2 * (calibration['k'] - 1)))
    flags = original.ritc_flag([r['file'] for r in records]).astype(float)
    return records, size, hhi, year, q, unit_t, sigma, flags, imputation


def calculate(dispositions, unavailable, unresolved, selected, S, R, H, year, keys,
              calibration, allocation, tag, outdir):
    records, rm, hm, ym, qs, unit_t, sigma, flags, imputation = pseudo_inputs(
        dispositions, unavailable, unresolved, selected, R, H, calibration, allocation)
    n = len(records)
    categories = sorted({v['category'] for v in records})
    group = {}
    for cat in categories:
        ix = [i for i, v in enumerate(records) if v['category'] == cat]
        group[cat] = {'n': len(ix), 'mean_abs_t': float(np.mean(abs(unit_t[ix])))}
    pseudo = []
    for i, v in enumerate(records):
        row = {'file': v['file'], 'category': v['category'], 'year': int(ym[i]),
               'size_gbp_m': float(rm[i]), 'hhi': float(hm[i]),
               'size_proxy_source': v['size_proxy_source'], 'ritc_flag': bool(flags[i]),
               'quantile': float(qs[i]), 'unit_t': float(unit_t[i]), 'sigma': float(sigma[i])}
        if v.get('sensitivity_source'):
            row['source_evidence'] = v['sensitivity_source']
        pseudo.append(row)
    result = {'allocation': allocation, 'permutation_seed': PERMUTATION_SEED if allocation == 'permuted' else None,
              'n_pseudo': n, 'n_fit': len(S) + n, 'n_target_assumed': 666 + len(unresolved) + len(selected),
              'n_target_observed_outcome_missing_composition_not_added': 24,
              'weights': 'one per observed and pseudo row; no inverse-propensity weights',
              'group_abs_t': group, 'rho_abs_t_size': float(stats.spearmanr(abs(unit_t), rm).statistic),
              'rho_abs_t_year': float(stats.spearmanr(abs(unit_t), ym).statistic),
              'pseudo_inputs': pseudo, 'imputation': imputation, 'by_c': {}}
    for c in (1.0, 5.0):
        sy = np.concatenate([S, c * sigma * unit_t])
        rs = np.concatenate([R, rm]); hs = np.concatenate([H, hm]); yy = np.concatenate([year, ym])
        ritc = np.concatenate([original.ritc_flag(keys).astype(float), flags])
        years = np.sort(np.unique(yy)); yidx = np.searchsorted(years, yy)
        keep = {}
        fit = original.fit(sy, rs, hs, yidx, len(years), ritc,
                           f'{tag} c={c:g}', keep=keep, keep_as='fit')
        # Historical output key retained for reproducibility: these diagnostics
        # cover only the named parameters in convergence['parameters'], not the
        # latent reporting-year effects. Divergences cover the sampler transitions.
        fit['_diag_full'] = keep['fit']['convergence']
        result['by_c'][str(c)] = fit
        np.savez_compressed(outdir / f'{tag}-c{c:g}-draws.npz', **keep['fit']['draws'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    S, R, H, year, keys, _ = original.load_sample()
    dispositions = add_size_proxies(classify_filings())
    target = [x for x in dispositions if x['category'] in ('working_sample', 'eligible_outcome_unavailable',
                                                             'eligible_observed_composition_unavailable')]
    unavailable = [x for x in dispositions if x['category'] == 'eligible_outcome_unavailable']
    unresolved = [x for x in dispositions if x['category'] == 'eligibility_unresolved']
    screened = [x for x in dispositions if x['category'] == 'structural_no_eligible_outcome']
    if (len(S), len(target), len(unavailable), len(unresolved), len(screened)) != (632, 666, 10, 24, 102):
        raise ValueError('population changed; revalidate the scenario before refitting')
    audit_rows = json.loads((ROOT / 'pdf_extraction/audit/structural_eligibility_audit.json').read_text(encoding='utf8'))['records']
    audit = {v['file']: v for v in audit_rows}
    m = json.loads((ROOT / 'data/no_mature_cohort_records.json').read_text(encoding='utf8'))
    m01 = {'syndicate_' + k + '.json': v for k, v in m.items() if not k.startswith('_')}
    raw_rates = json.loads((ROOT / 'model/fx_rates_h10.json').read_text(encoding='utf8'))['year_end_rates']
    rates = {int(y): v['usd_per_gbp'] for y, v in raw_rates.items()}
    selected = select_positive_screened(dispositions, audit, m01, rates)
    if len(selected) != 52 or len({v['file'] for v in selected}) != 52:
        raise ValueError('the 52 source-positive candidates changed; re-audit selection')
    calibration = json.loads((ROOT / 'model/dispersion_calibration_ritc.json').read_text(encoding='utf8'))
    old = json.loads((ROOT / 'results/check_missingness_sensitivity_results.json').read_text(encoding='utf8'))
    old_stress = old['eligibility_unresolved_stress']
    if [v['file'] for v in unavailable + unresolved] != old_stress['records']:
        raise ValueError('historical selected-case order changed; revalidate comparison')
    historical = {c: old_stress['by_c'][c]['k'] for c in ('1.0', '5.0')}
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    result = {'run': {'source_commit': commit, 'python': sys.version, 'platform': platform.platform(),
                      'numpy': np.__version__, 'pymc': pymc.__version__, 'arviz': arviz.__version__,
                      'fit_seed': FIT_SEED, 'chains': 4, 'tune_per_chain': 1500, 'draws_per_chain': 1500,
                      'target_accept': 0.98},
              'interpretation': ['scenario assumes the 24 selected unresolved and the 52 additional positive-base cases meet mature gross eligibility',
                                 'size proxies may not be the applicable mature-cohort base; 1980/2018 uses the transferred base under that assumption',
                                 'the missing outcomes are fixed synthetic quantiles, not observed data or a probability bound',
                                 'one predetermined permutation is not an exhaustive allocation analysis',
                                 'these fits exclude 24 target observations with unavailable composition, as in the historical scenario'],
              'historical_690_original_order_k': historical, 'scenarios': {}}
    specs = [('690_permuted', [], 'permuted'), ('742_original', selected, 'original'),
             ('742_permuted', selected, 'permuted')]
    for name, extra, allocation in specs:
        print('Running', name, flush=True)
        result['scenarios'][name] = calculate(dispositions, unavailable, unresolved, extra, S, R, H, year, keys,
                                              calibration, allocation, name, args.output_dir)
        (args.output_dir / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(args.output_dir.glob('*-draws.npz'))}
    result['posterior_draw_hashes'] = hashes
    (args.output_dir / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print('Wrote', args.output_dir, flush=True)


if __name__ == '__main__':
    main()
