"""
Walk-Forward Test 5-min avec zTP=-1.0 sur 3 ans de donnees.

Objectif: Valider la robustesse de la config optimale zTP=-1.0 hors echantillon.

Config testee: b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL4.0
  - PnL sur 3 ans: $45,224
  - 100 trades, 53% WR, PF=2.41, Sharpe=3.02

Fenetres: 34 periodes de 63j train + 21j test (comme walk-forward 1-min 3y)
"""
import sys
sys.path.insert(0, "src")

from walk_forward_runner import WalkForwardRunner

# ============================================================================
# CONFIGS A TESTER (variantes de zTP)
# ============================================================================

# Config de base (meilleure du grid search zTP etendu)
BASE_OVERRIDES = {
    "indicators.beta_lookback": 2640,
    "indicators.zscore_period": 20,
    "indicators.correlation_period": 30,
    "indicators.adf_hurst_period": 26,
    "entry.zscore_long": -3.5,
    "entry.zscore_short": 3.5,
    "entry.cointegration_score_min": 40,
    "exit.zscore_tp_enabled": True,
    "exit.zscore_sl_long": -4.0,
    "exit.zscore_sl_short": 4.0,
    "exit.zscore_tp_min_pnl": None,
    "exit.pnl_take_profit": 99999,
    "exit.pnl_stop_loss": -99999,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

CONFIGS_TO_TEST = [
    {
        "label": "zTP-1.0_b2640_zp20_cp30_adf26_co40_zSL4.0",
        "overrides": {
            **BASE_OVERRIDES,
            "exit.zscore_tp_long": 1.0,  # zTP=-1.0 -> TP LONG >= 1.0
            "exit.zscore_tp_short": -1.0,
        }
    },
    {
        "label": "zTP-0.5_b2640_zp20_cp30_adf26_co40_zSL4.0",
        "overrides": {
            **BASE_OVERRIDES,
            "exit.zscore_tp_long": 0.5,
            "exit.zscore_tp_short": -0.5,
        }
    },
    {
        "label": "zTP0.0_b2640_zp20_cp30_adf26_co40_zSL4.0",
        "overrides": {
            **BASE_OVERRIDES,
            "exit.zscore_tp_long": 0.0,
            "exit.zscore_tp_short": 0.0,
        }
    },
    {
        "label": "zTP1.0_b2640_zp20_cp30_adf26_co40_zSL4.0",
        "overrides": {
            **BASE_OVERRIDES,
            "exit.zscore_tp_long": -1.0,  # zTP=1.0 -> TP LONG >= -1.0
            "exit.zscore_tp_short": 1.0,
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
        warmup_bars=3000,  # beta=2640 barres 5-min + marge
        timeframe="5min",
        title="WALK-FORWARD TEST 5-MIN - CONFIG zTP=-1.0",
        output_path="output/walk_forward_5min_ztp_results.csv",
        selection_criterion="pnl_net",
    )

    runner.run()
