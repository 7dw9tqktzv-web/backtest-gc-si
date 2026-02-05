# ============================================================================
# TEST_METRICS.PY - Tests des fonctions d'analyse de metrics.py
# ============================================================================
#
# Tests de compute_global_metrics(), compute_advanced_metrics(),
# compute_exit_analysis(), compute_pnl_distribution().
#
# IMPORTANT : metrics.py attend des list[dict] avec STRING values
# (format csv.DictReader), pas des DataFrames. La fixture
# sample_trades_list dans conftest.py fournit ce format.
#
# DOCUMENTATION BUG SHARPE :
# --------------------------
# optimizer.py : Sharpe = (mean/std) * sqrt(252)       -> annualisation fixe
# metrics.py   : Sharpe = mean/std puis * sqrt(T/an)   -> annualisation variable
# Avec ~68 trades/an : ratio ~1.94x. Voir test_sharpe_discrepancy_documented().
#
# ============================================================================

import sys
import math
import statistics
from pathlib import Path

import numpy as np
import pytest

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from metrics import (
    compute_global_metrics,
    compute_advanced_metrics,
    compute_exit_analysis,
    compute_pnl_distribution,
)


# ============================================================================
# TESTS compute_global_metrics()
# ============================================================================

class TestComputeGlobalMetrics:
    """Tests de compute_global_metrics()."""

    def test_basic_3_trades(self, sample_trades_list):
        """Metriques globales avec 3 trades connus."""
        gm = compute_global_metrics(sample_trades_list)
        assert gm['n'] == 3
        assert gm['n_long'] == 2
        assert gm['n_short'] == 1
        assert gm['winners'] == 2
        assert gm['losers'] == 1
        # PnL net = 372 + 472 - 828 = 16
        assert np.isclose(gm['pnl_net'], 16.0)
        assert gm['win_rate'] == 66.7

    def test_single_trade(self):
        """Metriques avec un seul trade."""
        trades = [{
            'Trade_No': '1', 'Direction': 'LONG',
            'Entry_DateTime': '2026-01-01 10:00:00',
            'Exit_DateTime': '2026-01-01 11:00:00',
            'Duration_Min': '60.0',
            'PnL_Gross': '200.0', 'Costs': '78.0', 'PnL_Net': '122.0',
            'PnL_Cumul': '122.0',
        }]
        gm = compute_global_metrics(trades)
        assert gm['n'] == 1
        assert gm['win_rate'] == 100.0
        assert gm['profit_factor'] == float('inf')

    def test_all_winners(self):
        """Tous gagnants -> PF=inf."""
        trades = [
            {'Direction': 'LONG', 'Entry_DateTime': '2026-01-01 10:00:00',
             'Exit_DateTime': '2026-01-01 11:00:00', 'Duration_Min': '60.0',
             'PnL_Gross': '200.0', 'Costs': '78.0', 'PnL_Net': '100.0',
             'PnL_Cumul': '100.0'},
            {'Direction': 'SHORT', 'Entry_DateTime': '2026-01-01 14:00:00',
             'Exit_DateTime': '2026-01-01 15:00:00', 'Duration_Min': '60.0',
             'PnL_Gross': '300.0', 'Costs': '78.0', 'PnL_Net': '200.0',
             'PnL_Cumul': '300.0'},
        ]
        gm = compute_global_metrics(trades)
        assert gm['profit_factor'] == float('inf')
        assert gm['win_rate'] == 100.0

    def test_all_losers(self):
        """Tous perdants -> PF=0."""
        trades = [
            {'Direction': 'LONG', 'Entry_DateTime': '2026-01-01 10:00:00',
             'Exit_DateTime': '2026-01-01 11:00:00', 'Duration_Min': '60.0',
             'PnL_Gross': '-200.0', 'Costs': '78.0', 'PnL_Net': '-278.0',
             'PnL_Cumul': '-278.0'},
            {'Direction': 'SHORT', 'Entry_DateTime': '2026-01-01 14:00:00',
             'Exit_DateTime': '2026-01-01 15:00:00', 'Duration_Min': '60.0',
             'PnL_Gross': '-300.0', 'Costs': '78.0', 'PnL_Net': '-378.0',
             'PnL_Cumul': '-656.0'},
        ]
        gm = compute_global_metrics(trades)
        assert gm['profit_factor'] == 0
        assert gm['win_rate'] == 0.0

    def test_max_drawdown(self, sample_trades_list):
        """Verifie le calcul du max drawdown."""
        gm = compute_global_metrics(sample_trades_list)
        # Cumul: [372, 844, 16] -> peak=844, trough=16, DD = 16 - 844 = -828
        assert gm['max_dd'] == 16.0 - 844.0  # = -828.0


# ============================================================================
# TESTS compute_advanced_metrics()
# ============================================================================

class TestComputeAdvancedMetrics:
    """Tests de compute_advanced_metrics()."""

    def test_sharpe_per_trade(self, sample_trades_list):
        """Sharpe par trade = mean / stdev(PnL_Net)."""
        gm = compute_global_metrics(sample_trades_list)
        am = compute_advanced_metrics(gm)
        expected = round(gm['pnl_avg'] / statistics.stdev(gm['pnl_list']), 3)
        assert am['sharpe'] == expected

    def test_sharpe_annualized(self, sample_trades_list):
        """Sharpe annualise = sharpe * sqrt(trades_per_year)."""
        gm = compute_global_metrics(sample_trades_list)
        am = compute_advanced_metrics(gm)
        trades_per_year = am['trades_per_day'] * 252
        expected = round(am['sharpe'] * math.sqrt(trades_per_year), 3)
        assert am['sharpe_annualise'] == expected

    def test_calmar(self, sample_trades_list):
        """Calmar = PnL_net / |Max_DD|."""
        gm = compute_global_metrics(sample_trades_list)
        am = compute_advanced_metrics(gm)
        expected = round(gm['pnl_net'] / abs(gm['max_dd']), 2)
        assert am['calmar'] == expected

    def test_sharpe_coherence_optimizer_metrics(self, sample_trades_list):
        """
        Coherence Sharpe : optimizer.py et metrics.py utilisent la meme formule.
        Les deux calculent Sharpe par trade = mean / stdev (non annualise).
        """
        gm = compute_global_metrics(sample_trades_list)
        am = compute_advanced_metrics(gm)

        # Sharpe par trade (formule optimizer.py apres fix)
        pnl_list = gm['pnl_list']
        optimizer_sharpe = statistics.mean(pnl_list) / statistics.stdev(pnl_list)

        # Sharpe par trade (metrics.py)
        metrics_sharpe = am['sharpe']

        assert np.isclose(optimizer_sharpe, metrics_sharpe, atol=0.001)


# ============================================================================
# TESTS compute_exit_analysis()
# ============================================================================

class TestComputeExitAnalysis:
    """Tests de compute_exit_analysis()."""

    def test_count_by_reason(self, sample_trades_list):
        """Compte les trades par raison de sortie."""
        exits = compute_exit_analysis(sample_trades_list)
        assert exits['TP_ZSCORE']['trades'] == 2
        assert exits['SL_ZSCORE']['trades'] == 1
        assert exits['TP_DOLLAR']['trades'] == 0
        assert exits['SL_DOLLAR']['trades'] == 0


# ============================================================================
# TESTS compute_pnl_distribution()
# ============================================================================

class TestComputePnlDistribution:
    """Tests de compute_pnl_distribution()."""

    def test_distribution_keys(self, sample_trades_list):
        """Verifie les 6 cles de la distribution."""
        gm = compute_global_metrics(sample_trades_list)
        dist = compute_pnl_distribution(gm)
        for key in ['min', 'q1', 'median', 'q3', 'max', 'std']:
            assert key in dist, f"Cle manquante : {key}"

    def test_min_max_correct(self, sample_trades_list):
        """Min et max correspondent aux PnL extremes."""
        gm = compute_global_metrics(sample_trades_list)
        dist = compute_pnl_distribution(gm)
        assert dist['min'] == min(gm['pnl_list'])
        assert dist['max'] == max(gm['pnl_list'])
