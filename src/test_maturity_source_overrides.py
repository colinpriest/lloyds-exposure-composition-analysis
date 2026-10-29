import copy
import json
from pathlib import Path

import pytest
import build_maturity_share as maturity

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = json.loads((ROOT / 'data/maturity_proxy_source_overrides.json').read_text(encoding='utf-8'))['records']


def selected(ident):
    syn, year = ident.split('_')
    d = json.loads((ROOT / 'pdf_extraction' / f'syndicate_{syn}_{year}.json').read_text(encoding='utf-8'))
    o = OVERRIDES[ident]
    tri = d['models'][o['source_model']][o['source_field']]
    return tri, maturity.column_ultimates(tri), o


def corrected(ident):
    tri, cols, o = selected(ident)
    return maturity.filing_current_estimates(tri, cols, o, o['source_model'], o['source_field'])


def test_each_override_matches_selected_input_and_printed_values():
    records = json.loads((ROOT / 'model/maturity_share.json').read_text(encoding='utf-8'))['records']
    for ident in OVERRIDES:
        syn, year = ident.split('_')
        cols = corrected(ident)
        opening, mature, latest = maturity.membership(cols, int(year))
        for delta in maturity.DELTAS:
            key = 'phi_delta_inf' if delta is None else f'phi_delta_{delta:g}'
            assert records[ident][key] == pytest.approx(maturity.phi_from(opening, mature, delta))
        assert records[ident]['source_override']['source_filing_sha256'] == OVERRIDES[ident]['source_filing_sha256']


def test_382_2016_uses_reported_totals_not_increments():
    values = {u: value for u, _, value in corrected('382_2016')}
    assert [values[y] for y in (2008, 2009, 2010)] == [110403, 140783, 323780]
    assert sum(values.values()) == 1884466
    headline = json.loads((ROOT / 'model/exposure_results.json').read_text(encoding='utf-8'))
    # Confirm source-backed headline independently, without changing it.
    rows = [r for r in headline['observations'] if r['syndicate'] == 382 and r['year'] == 2016]
    assert len(rows) == 1
    assert rows[0]['pyd_gbp_m'] == pytest.approx(-14.328)
    assert rows[0]['pyd_basis_source'] == 'confirmed-figure:register'


def test_shifted_years_and_recovered_groups():
    for ident, group, youngest, current in [('1200_2018', (2012,712.3),(2017,421.6), None), ('1084_2021',(2011,1637.1),(2020,864.2),(2021,537.6)), ('2623_2023',(2013,8824.7),None,None)]:
        cols=corrected(ident); values={u:v for u,_,v in cols}
        assert values[group[0]] == pytest.approx(group[1])
        if youngest:
            assert values[youngest[0]] == pytest.approx(youngest[1])
        opening, mature, _ = maturity.membership(cols, int(ident.split('_')[1]))
        assert group[0] in [u for u,_,_ in mature]
        if current:
            assert values[current[0]] == pytest.approx(current[1])
            assert current[0] not in [u for u,_,_ in opening]
    assert {u:v for u,_,v in corrected('435_2015')}[2011] == 184880
    assert {u:v for u,_,v in corrected('1225_2022')}[2017] == pytest.approx(3893.2)
    assert {u:v for u,_,v in corrected('1225_2018')}[2013] == pytest.approx(2640.1)
    assert {u:v for u,_,v in corrected('1225_2016')}[2011] == pytest.approx(2280.9)
    assert {u:v for u,_,v in corrected('1225_2020')}[2015] == pytest.approx(2890.0)
    gross_1225 = {u:v for u,_,v in corrected('1225_2021')}
    assert [gross_1225[u] for u in range(2016,2022)] == [3216.6,319.0,309.6,342.3,354.8,207.0]
    # The previously selected 1274/2022 triangle was net; the filing gives gross.
    gross = {u:v for u,_,v in corrected('1274_2022')}
    assert [gross[u] for u in (2012, 2013, 2021, 2022)] == [946246, 179555, 235997, 180131]
    shifted = {u:v for u,_,v in corrected('2088_2019')}
    assert [shifted[u] for u in (2012, 2013, 2018, 2019)] == [35827, 33205, 146793, 45110]
    opening, _, _ = maturity.membership(corrected('2088_2019'), 2019)
    assert 2019 not in [u for u,_,_ in opening]


def test_override_fails_closed_for_changed_sources():
    tri, cols, o = selected('1084_2021')
    for kind in ('fingerprint','model','years','sum','group_overlap'):
        alt, over, model = copy.deepcopy(tri), copy.deepcopy(o), o['source_model']
        if kind == 'fingerprint': alt['underwriting_years'][0] = '1900'
        if kind == 'model': model = 'changed'
        if kind == 'years': over['expected_extracted_cohort_years'][0] = 1900
        if kind == 'sum': over['current_estimate_total'] += 1
        if kind == 'group_overlap': over['additional_grouped_cohort']['latest_underwriting_year'] = 2012
        with pytest.raises(ValueError):
            maturity.filing_current_estimates(alt, cols, over, model, o['source_field'])


def test_uniform_scale_does_not_change_share():
    cols=corrected('382_2016')
    opening,mature,_=maturity.membership(cols,2016)
    scaled=lambda xs:[(u,a,v*1000) for u,a,v in xs]
    for delta in maturity.DELTAS:
        assert maturity.phi_from(opening,mature,delta) == pytest.approx(maturity.phi_from(scaled(opening),scaled(mature),delta))
