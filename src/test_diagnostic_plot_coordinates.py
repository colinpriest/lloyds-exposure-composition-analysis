"""The diagnostic plots must use the stored fitted data, not fabricated zeroes."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
import run_analysis as ra


@pytest.fixture
def results():
    return json.loads((Path(__file__).resolve().parent.parent / 'model/exposure_results.json').read_text(encoding='utf8'))


def capture(monkeypatch, function, results):
    figures = []
    monkeypatch.setattr(ra, '_save_fig', lambda fig, name: figures.append((fig, name)))
    function(results)
    assert len(figures) == 1
    return figures[0][0]


def test_size_plot_uses_raw_squared_severities(results, monkeypatch):
    fig = capture(monkeypatch, ra._gen_fig_power_law_size, results)
    points = results['joint_composition']['scatter_points']
    offsets = fig.axes[0].collections[0].get_offsets()
    np.testing.assert_allclose(offsets[:, 0], [p['reserves'] for p in points])
    np.testing.assert_allclose(offsets[:, 1], [p['y_raw_sq'] for p in points])
    assert len(offsets) == 313 and np.all(offsets[:, 1] > 0)
    assert fig.axes[0].get_yscale() == "symlog"
    plt.close(fig)


def test_hhi_plot_uses_actual_fitted_squared_severity_bins(results, monkeypatch):
    fig = capture(monkeypatch, ra._gen_fig_power_law_hhi, results)
    bins = results['exposure_composition']['dispersion_models']['single_h']['bin_points']
    offsets = fig.axes[0].collections[0].get_offsets()
    np.testing.assert_allclose(offsets[:, 0], [p['x'] for p in bins])
    np.testing.assert_allclose(offsets[:, 1], [p['y'] for p in bins])
    assert len(offsets) == len(bins) and np.all(offsets[:, 1] > 0)
    plt.close(fig)


def test_adjusted_plot_uses_adjusted_severities_and_concentration_curve(results, monkeypatch):
    fig = capture(monkeypatch, ra._gen_fig_size_adjusted_hhi, results)
    ax = fig.axes[0]
    pts = results['joint_composition']['scatter_points']
    offsets = ax.collections[0].get_offsets()
    np.testing.assert_allclose(offsets[:, 0], [p['x'] for p in pts])
    np.testing.assert_allclose(offsets[:, 1], [p['y_adj_sq'] for p in pts])
    assert len(offsets) == 313 and np.all(offsets[:, 1] > 0)
    assert fig.axes[0].get_yscale() == "symlog"
    fit = results['joint_composition']['disp_h_adjusted']
    x, y = ax.lines[0].get_data()
    np.testing.assert_allclose(y, fit['A'] + fit['B'] * (1 - x) ** fit['C'])
    assert y[0] > y[-1]
    plt.close(fig)


def test_zero_severities_remain_plotted(results, monkeypatch):
    first = results['joint_composition']['scatter_points'][0]
    first['y_raw_sq'] = first['y_adj_sq'] = 0.0
    for function in (ra._gen_fig_power_law_size, ra._gen_fig_size_adjusted_hhi):
        fig = capture(monkeypatch, function, results)
        assert fig.axes[0].collections[0].get_offsets()[0, 1] == 0
        assert fig.axes[0].get_yscale() == "symlog"
        assert np.isfinite(fig.axes[0].transData.transform((0, 0))).all()
        plt.close(fig)


def test_capital_outputs_identify_concentration_only_and_size_only_operator(monkeypatch):
    # Deliberately distinct synthetic values expose field swaps that gamma=0 masks.
    results = {'capital_impact': {'portfolios': [{'name': 'Example',
        'naive': {'var_995': 0.1}, 'concentration_only': {'var_995': 0.2},
        'full': {'var_995': 0.5}}]}}
    written = []
    monkeypatch.setattr(ra, '_write_tex', lambda name, content: written.append((name, content)))
    ra._gen_table4(results)
    name, table = written[0]
    assert name == 'table4_var_decomposition.tex'
    assert 'Conc.-adj.' in table and 'Conc. effect' in table
    assert 'Mix-adj.' not in table and 'Mix effect' not in table
    assert 'Example & 0.1000 & 0.2000 & 0.5000 & 0.1000 & 0.3000' in table
    assert r'\gamma=0' in table
    fig = capture(monkeypatch, ra._gen_fig_capital_decomposition, results)
    ax = fig.axes[0]
    assert [bar.get_height() for bar in ax.patches] == pytest.approx([0.1, 0.2, 0.5])
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ['Naive', 'Concentration-only', 'Fully adjusted']
    assert r'\gamma=0' in ax.get_title()
    plt.close(fig)
