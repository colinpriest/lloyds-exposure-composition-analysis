"""Conditional inclusion of 1254/2022: adopted-model refit and rebuilt donor pool.

The account's gross whole-account incurred and inwards RITC balance are used as a
mature-cohort scenario, not an established replacement for the excluded observation.
The source transcriptions and assumptions are in data/conditional_1254_2022.json.
The existing headline fit, data, donor definitions and documents are not overwritten.
Run from an isolated analysis checkout:
  python src/check_1254_2022_inclusion.py --output-dir NEW_DIRECTORY
Full posterior and sampler arrays are saved only in the supplied new directory.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault('LLOYDS_EXTRACTION_OFFLINE', '1')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')
ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'data/conditional_1254_2022.json'
KEY = '1254_2022'
INPUTS = ('model/exposure_results.json', 'model/dispersion_calibration_ritc.json',
          'model/dispersion_posterior_draws_ritc.npz', 'results/check_gamma0_vignette_results.json',
          'src/adopted_model.py', 'src/check_cohort_scope.py', 'src/refit_vignettes.py',
          'src/run_analysis.py', 'src/assumed_business.py', 'src/donor_pool.py', 'src/pool_quantile.py',
          'src/check_gamma0_vignette.py', 'src/vignette_uncertainty.py', 'src/transfer_operator.py',
          'pdf_extraction/ritc_scan.json', 'pdf_extraction/audit/portfolio_transfer_adjudication.json',
          'data/opening_reserves_takeon_base.json', 'vignettes/vignette-1/target_profile.json',
          'vignettes/vignette-2/target_transition.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario_from_fixture(f, vector_builder):
    """Validate source transcription and compute the conditional severity and HHI."""
    import numpy as np
    if f['scenario'] != '1254_2022_conditional_roll_forward' or f['report_currency'] != 'GBP':
        raise ValueError('unexpected scenario identity or currency')
    base = f['gross_opening_reserves_gbp_m'] + f['gross_ritc_reserves_taken_on_gbp_m']
    if base <= 0:
        raise ValueError('non-positive conditional reserve base')
    movement = f['gross_claims_paid_gbp_m'] + f['gross_change_in_claims_provision_gbp_m']
    close = base + f['gross_change_in_claims_provision_gbp_m'] + f['gross_foreign_exchange_change_gbp_m']
    if not np.isclose(close, f['gross_closing_claims_provision_gbp_m'], rtol=0, atol=1e-9):
        raise ValueError('gross claims provision bridge does not reconcile')
    if f['ritc_years_of_account'] != [2017, 2018, 2019]:
        raise ValueError('unexpected inherited cohort scope')
    weights, kind = vector_builder(f['gross_premium_mix'], f['gross_written_premiums_gbp_m'])
    if kind != 'premium_mix' or not np.isclose(sum(weights), 1.0, rtol=0, atol=1e-12):
        raise ValueError('premium mix is unavailable or fails to sum to one')
    return {'reserve_base_gbp_m': float(base), 'gross_movement_gbp_m': float(movement),
            'severity': float(movement / base), 'hhi': float(np.dot(weights, weights)),
            'weights': np.asarray(weights, float).tolist(), 'weight_source': kind,
            'closing_triangle_difference_gbp_m': float(f['gross_closing_claims_provision_gbp_m'] -
                                                       f['gross_closing_triangle_gbp_m'])}


def run(output):
    import numpy as np
    import arviz as az
    import adopted_model as am
    import assumed_business
    import run_analysis as ra
    import refit_vignettes as rv
    import transfer_operator as op
    from check_cohort_scope import fit
    from pool_quantile import var_q
    from vignette_uncertainty import load_targets, transfer

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    git = lambda *cmd: subprocess.check_output(['git', '-C', str(ROOT), *cmd], text=True).strip()
    head = git('rev-parse', 'HEAD')
    status = git('status', '--porcelain', '--untracked-files=all')
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    scenario = scenario_from_fixture(fixture, ra.build_weight_vector)
    if KEY not in assumed_business.keys():
        raise SystemExit('1254/2022 is not flagged as assumed business in the committed source')
    sample = tuple(np.asarray(x) for x in am.load_sample())
    S, R, H, yr, synd, ritc = sample
    keys = ['%s_%s' % (s, y) for s, y in zip(synd, yr)]
    if len(S) != 632 or KEY in keys or len(set(keys)) != len(keys):
        raise SystemExit('headline sample changed; reconsider the conditional scenario')
    pool, pool_ritc, pool_keys = rv.pool_for()
    rv.check_pool_is_the_fit_sample(pool, pool_keys, keys, S, R)
    published, head_draws, cfg = rv.headline_block(rv.headline_record())
    baseline = rv.centre_only(head_draws, pool, pool_ritc, cfg)
    if baseline != published['centre']:
        raise SystemExit('headline centre did not reproduce')
    newS = np.append(S, scenario['severity'])
    newR = np.append(R, scenario['reserve_base_gbp_m'])
    newH = np.append(H, scenario['hhi'])
    newyr = np.append(yr, 2022)
    newsyn = np.append(synd, 1254)
    newritc = np.append(ritc, 1.0)
    print('START 633-record conditional 1254/2022 refit:', scenario, flush=True)
    params, idata = fit(newS, newR, newH, newyr, newritc)
    summary = az.summary(idata, hdi_prob=.95, round_to='none')
    diag = {'divergences': int(idata.sample_stats.diverging.sum()),
            'max_rhat': float(summary.r_hat.max()),
            'min_ess_bulk': float(summary.ess_bulk.min()),
            'min_ess_tail': float(summary.ess_tail.min())}
    if diag['divergences'] or diag['max_rhat'] > 1.01:
        raise SystemExit('nonconverged conditional fit: %s' % diag)
    saved = output / 'posterior.npz'
    np.savez_compressed(saved, **{str(k): v.values for k, v in idata.posterior.data_vars.items()},
                        **{'sample_stats__' + str(k): v.values for k, v in idata.sample_stats.data_vars.items()})
    d = rv.operator_draws(idata)
    newpool = (np.append(pool[0], round(scenario['severity'], 8)),
               np.append(pool[1], round(scenario['reserve_base_gbp_m'], 2)),
               np.append(pool[2], round(scenario['hhi'], 6)),
               np.append(pool[3], 1254), np.append(pool[4], 2022))
    new_pool_ritc = np.append(pool_ritc, True)
    newkeys = list(pool_keys) + [KEY]
    rv.check_pool_is_the_fit_sample(newpool, newkeys, keys + [KEY], newS, newR)
    pool_only = rv.centre_only(head_draws, newpool, new_pool_ritc, cfg)
    fit_only = rv.centre_only(d, pool, pool_ritc, cfg)
    combined = rv.centre_only(d, newpool, new_pool_ritc, cfg)
    th = op.params(d, op.HEADLINE)
    means = {k: float(np.mean(v)) for k, v in th.items()}
    mapped = transfer(newpool[0], newpool[1], newpool[2], load_targets()[0], means, cfg, new_pool_ritc)
    thresholds = {}
    for alpha in (.99, .995):
        q = var_q(mapped, alpha)
        thresholds[str(alpha)] = {'value': float(q),
                                  'donors_at_threshold': [str(newkeys[i]) for i in np.flatnonzero(mapped == q)],
                                  'rank_from_top': rv.rank_from_top(len(mapped), alpha)}
    result = {
        'question': 'Conditional inclusion of 1254/2022 with whole-account gross incurred as mature-cohort proxy',
        'interpretation': ('A source-based what-if, not an established or exact mature-cohort outcome. '
                           'Vignette values are empirical inverse-CDF points at posterior-mean parameters; '
                           'cross-validation and vignette uncertainty intervals are not refitted.'),
        'code_commit': head, 'working_tree_dirty': bool(status), 'working_tree_status': status.splitlines(),
        'producer_sha256': sha(__file__), 'fixture_sha256': sha(FIXTURE),
        'input_sha256': {name: sha(ROOT / name) for name in INPUTS},
        'source_report_sha256': fixture['source_sha256'],
        'sampler': {'chains': 4, 'tune': 1500, 'draws': 1500, 'target_accept': .98, 'seed': 42},
        'scenario': scenario, 'scenario_source': fixture, 'ritc_assumed_business': True,
        'baseline_n': len(S), 'conditional_n': len(newS),
        'baseline_n_syndicates': len(set(synd)), 'conditional_n_syndicates': len(set(newsyn)),
        'baseline_centre': baseline, 'baseline_exactly_reproduces_published_centre': True,
        'fit': params, 'diagnostics': diag, 'posterior_sha256': sha(saved),
        'pool_only': pool_only, 'fit_only': fit_only, 'refit_and_rebuilt_pool': combined,
        'relative_to_baseline': rv.relative(combined, baseline), 'V1_thresholds': thresholds,
        'scenario_donor_transferred_v1': float(mapped[-1]),
    }
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('DONE k=', params['k']['mean'], 'diagnostics=', diag, 'centre=', combined, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, help='new directory for results and full posterior draws')
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == '__main__':
    main()
