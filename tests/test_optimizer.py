# ============================================================================
# TEST_OPTIMIZER.PY - Tests des fonctions pures de optimizer.py
# ============================================================================
#
# Tests de apply_overrides(), build_label(), compute_metrics().
# Documente la divergence de calcul du Sharpe entre optimizer.py et metrics.py.
#
# ============================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from optimizer import apply_overrides, build_label, compute_metrics


# ============================================================================
# TESTS apply_overrides()
# ============================================================================

class TestApplyOverrides:
    """Tests de la fonction apply_overrides()."""

    def test_apply_single_override(self, sample_config):
        """Override simple d'une cle imbriquee."""
        result = apply_overrides(sample_config, {"exit.pnl_take_profit": 500})
        assert result['exit']['pnl_take_profit'] == 500

    def test_apply_nested_override(self, sample_config):
        """Override de cle imbriquee avec notation a points."""
        result = apply_overrides(sample_config, {"indicators.beta_lookback": 2640})
        assert result['indicators']['beta_lookback'] == 2640

    def test_deep_copy_unchanged(self, sample_config):
        """La config originale n'est pas modifiee."""
        original_tp = sample_config['exit']['pnl_take_profit']
        result = apply_overrides(sample_config, {"exit.pnl_take_profit": 999})
        assert sample_config['exit']['pnl_take_profit'] == original_tp
        assert result['exit']['pnl_take_profit'] == 999

    def test_multiple_overrides(self, sample_config):
        """Plusieurs overrides appliques simultanement."""
        overrides = {
            "exit.pnl_take_profit": 500,
            "exit.pnl_stop_loss": -800,
            "indicators.beta_lookback": 2640,
        }
        result = apply_overrides(sample_config, overrides)
        assert result['exit']['pnl_take_profit'] == 500
        assert result['exit']['pnl_stop_loss'] == -800
        assert result['indicators']['beta_lookback'] == 2640


# ============================================================================
# TESTS build_label()
# ============================================================================

class TestBuildLabel:
    """Tests de la fonction build_label()."""

    def test_empty_returns_baseline(self):
        """Overrides vides -> 'baseline'."""
        assert build_label({}) == "baseline"

    def test_known_shortcuts(self):
        """Verifie les raccourcis connus (TP, SL, beta)."""
        label = build_label({"exit.pnl_take_profit": 500})
        assert "TP" in label and "500" in label

        label = build_label({"indicators.beta_lookback": 1320})
        assert "beta" in label and "1320" in label


# ============================================================================
# TESTS compute_metrics()
# ============================================================================

class TestComputeMetrics:
    """Tests de compute_metrics() de optimizer.py."""

    def test_basic_metrics(self, sample_trades_df):
        """Metriques basiques avec 3 trades connus."""
        m = compute_metrics(sample_trades_df)
        assert m['trades'] == 3
        assert m['long'] == 2
        assert m['short'] == 1
        assert m['winners'] == 2  # PnL_Net > 0 pour trades 1 et 2

    def test_empty_trades(self):
        """DataFrame vide retourne des metriques a zero."""
        empty_df = pd.DataFrame(columns=['Direction', 'PnL_Net'])
        m = compute_metrics(empty_df)
        assert m['trades'] == 0
        assert m['pnl_net'] == 0.0
        assert m['sharpe'] == 0.0

    def test_sharpe_uses_sqrt_252(self, sample_trades_df):
        """
        DOCUMENTATION BUG SHARPE
        -------------------------
        optimizer.py : Sharpe = (mean/std) * sqrt(252)
        metrics.py   : Sharpe = mean/std puis * sqrt(trades_per_year)

        Avec ~68 trades/an : sqrt(68)=8.2 vs sqrt(252)=15.9 -> ratio ~1.94x.
        Ce test verifie que optimizer.py utilise bien sqrt(252).
        """
        m = compute_metrics(sample_trades_df)
        pnl = sample_trades_df['PnL_Net']
        expected = (pnl.mean() / pnl.std()) * np.sqrt(252)
        assert np.isclose(m['sharpe'], round(expected, 3))
