"""
Walk-Forward Test 5-min - Top 5 Beta Longs
Test des 5 meilleures configs du grid search beta long (3960 = 15 jours)
"""
import sys
sys.path.insert(0, "src")

from walk_forward_runner import WalkForwardRunner

# ============================================================================
# TOP 5 CONFIGS DU GRID SEARCH BETA LONG
# ============================================================================

CONFIGS_TO_TEST = [
    {
        "label": "b3960_zp24_cp12_adf26_zE3.5_co40_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 12,
            "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5,
            "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0,
            "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0,
            "exit.zscore_sl_short": 4.0,
            "exit.zscore_tp_min_pnl": None,
            "exit.pnl_take_profit": 99999,
            "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2,
            "costs.slippage_si_ticks": 2,
        }
    },
    {
        "label": "b3960_zp24_cp12_adf26_zE3.5_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 12,
            "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5,
            "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0,
            "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0,
            "exit.zscore_sl_short": 4.0,
            "exit.zscore_tp_min_pnl": None,
            "exit.pnl_take_profit": 99999,
            "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2,
            "costs.slippage_si_ticks": 2,
        }
    },
    {
        "label": "b3960_zp24_cp60_adf26_zE3.5_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 60,
            "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5,
            "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0,
            "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0,
            "exit.zscore_sl_short": 4.0,
            "exit.zscore_tp_min_pnl": None,
            "exit.pnl_take_profit": 99999,
            "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2,
            "costs.slippage_si_ticks": 2,
        }
    },
    {
        "label": "b3960_zp24_cp24_adf26_zE3.5_co40_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 24,
            "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5,
            "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0,
            "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0,
            "exit.zscore_sl_short": 4.0,
            "exit.zscore_tp_min_pnl": None,
            "exit.pnl_take_profit": 99999,
            "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2,
            "costs.slippage_si_ticks": 2,
        }
    },
    {
        "label": "b3960_zp24_cp48_adf26_zE3.5_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 48,
            "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5,
            "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0,
            "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0,
            "exit.zscore_sl_short": 4.0,
            "exit.zscore_tp_min_pnl": None,
            "exit.pnl_take_profit": 99999,
            "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2,
            "costs.slippage_si_ticks": 2,
        }
    },
]

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    runner = WalkForwardRunner(
        configs_to_test=CONFIGS_TO_TEST,
        train_days=63,
        test_days=21,
        step_days=21,
        warmup_bars=4500,  # beta=3960 barres 5-min + marge
        timeframe="5min",
        title="WALK-FORWARD TEST 5-MIN - TOP 5 BETA LONGS (b3960 = 15 jours)",
        output_path="output/walk_forward_beta_long_results.csv",
        selection_criterion="pnl_net",
    )

    runner.run()
