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
from optimizer import apply_overrides, apply_overrides_fast, build_label, compute_metrics


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


class TestApplyOverridesFast:
    """Tests de apply_overrides_fast() -- doit produire le meme resultat que apply_overrides."""

    def test_matches_apply_overrides(self, sample_config):
        """Verifie que fast et normal produisent le meme resultat pour 10 override sets."""
        override_sets = [
            {"exit.pnl_take_profit": 500},
            {"exit.pnl_stop_loss": -800},
            {"indicators.beta_lookback": 2640},
            {"exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -600},
            {"indicators.beta_lookback": 1320, "indicators.zscore_period": 24},
            {"exit.pnl_take_profit": 1000, "indicators.beta_lookback": 3960},
            {"indicators.correlation_period": 30, "indicators.adf_hurst_period": 128},
            {"entry.zscore_entry_long": -3.0, "entry.zscore_entry_short": 3.0},
            {"exit.zscore_tp_long": -1.5, "exit.zscore_sl_long": -4.0},
            {"exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -500,
             "indicators.beta_lookback": 2640, "indicators.zscore_period": 20},
        ]
        for ov in override_sets:
            expected = apply_overrides(sample_config, ov)
            result = apply_overrides_fast(sample_config, ov)
            # Comparer tous les sous-dicts
            for section in expected:
                if isinstance(expected[section], dict):
                    assert result[section] == expected[section], f"Mismatch on {section} with {ov}"
                else:
                    assert result[section] == expected[section], f"Mismatch on {section} with {ov}"

    def test_original_config_not_mutated(self, sample_config):
        """La config originale n'est pas modifiee par apply_overrides_fast."""
        import copy
        original = copy.deepcopy(sample_config)
        apply_overrides_fast(sample_config, {"exit.pnl_take_profit": 99999})
        assert sample_config['exit']['pnl_take_profit'] == original['exit']['pnl_take_profit']


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

    def test_sharpe_per_trade(self, sample_trades_df):
        """Sharpe par trade = mean / std (non annualise, coherent metrics.py)."""
        m = compute_metrics(sample_trades_df)
        pnl = sample_trades_df['PnL_Net']
        expected = pnl.mean() / pnl.std()
        assert np.isclose(m['sharpe'], round(expected, 3))
