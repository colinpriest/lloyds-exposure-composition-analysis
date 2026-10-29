"""Run a maturity sensitivity in a fresh output directory without modifying the checkout.

The primary, recovered-groups-omitted and 457/2015-excluded cases all invoke the
same seven-fit maturity producer. The producer reads the specified candidate proxy
and writes a new result and diagnostics. These are new runs; they do not recreate
or overwrite historical provenance records. Run in an isolated checkout:

    python src/targeted_maturity_refit.py --case primary --output-dir PATH
    python src/targeted_maturity_refit.py --case no-groups --output-dir PATH
    python src/targeted_maturity_refit.py --case exclude-457 --output-dir PATH
"""
import argparse
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAGS = ('inf', '4', '2', '1')


def candidate(source, case):
    """Create the requested proxy variant without mutating the primary input."""
    result = copy.deepcopy(source)
    if case == 'exclude-457':
        if result['records'].pop('457_2015', None) is None:
            raise ValueError('457/2015 missing from the primary proxy')
    elif case not in ('primary', 'no-groups'):
        raise ValueError('unknown case: ' + str(case))
    return result


def membership(source, exposure):
    rows = [o for o in exposure['observations'] if o.get('s_raw_a') is not None
            and o.get('opening_reserves_gbp_m') and o.get('hhi') is not None]
    keys = [f"{o['syndicate']}_{o['year']}" for o in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate working-sample keys')
    included = []
    for key in keys:
        rec = source['records'].get(key)
        vals = [] if rec is None else [rec.get('phi_delta_' + tag) for tag in TAGS]
        if vals and all(v is not None and math.isfinite(float(v)) and float(v) >= .10 for v in vals):
            included.append(key)
    return {'n_working_sample': len(keys), 'n_refit': len(included), 'refit_keys': included}


def run(case, output_dir):
    import check_maturity_denominator as check
    from build_maturity_group_sensitivity import build
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    primary = json.loads((ROOT / 'model/maturity_share.json').read_text(encoding='utf-8'))
    source = primary
    if case == 'no-groups':
        overrides = json.loads((ROOT / 'data/maturity_proxy_source_overrides.json').read_text(encoding='utf-8'))['records']
        source, _ = build(primary, overrides)
    selected = candidate(source, case)
    exposure = json.loads((ROOT / 'model/exposure_results.json').read_text(encoding='utf-8'))
    baseline, changed = membership(primary, exposure), membership(selected, exposure)
    (output / 'candidate.json').write_text(json.dumps(selected, indent=2) + '\n', encoding='utf-8')
    (output / 'inputs.json').write_text(json.dumps({'case': case, 'baseline': baseline,
                                                    'candidate': changed}, indent=2) + '\n', encoding='utf-8')
    tags = ['baseline_same_subsample'] + [f'V2_delta_{x}' for x in TAGS] + [f'V1_delta_{x}' for x in ('inf', '2')]
    summaries = []
    original = check.az.summary
    def record_summary(*args, **kwargs):
        table = original(*args, **kwargs)
        if len(summaries) >= len(tags):
            raise RuntimeError('unexpected extra posterior summary')
        columns = ('mean', 'sd', 'hdi_2.5%', 'hdi_97.5%', 'ess_bulk', 'ess_tail', 'r_hat')
        metrics = {}
        for name in table.index:
            metrics[str(name)] = {}
            for col in columns:
                if col in table.columns:
                    value = float(table.loc[name, col])
                    metrics[str(name)][col] = value if math.isfinite(value) else None
        summaries.append({'fit': tags[len(summaries)], 'parameters': metrics})
        return table
    check.MAT = output / 'candidate.json'
    check.OUT = output / 'results.json'
    check.az.summary = record_summary
    try:
        check.main()
    finally:
        check.az.summary = original
    if len(summaries) != len(tags):
        raise RuntimeError('expected seven posterior summaries, got %d' % len(summaries))
    (output / 'diagnostics.json').write_text(json.dumps({'status': 'complete', 'fit_summaries': summaries}, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=('primary', 'no-groups', 'exclude-457'))
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    run(args.case, args.output_dir)


if __name__ == '__main__':
    main()
