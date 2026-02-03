"""
Grid Search 5-min - Donnees 3 ans (Jan 2023 - Jan 2026)
1,080 groupes indicateurs x 144 entry/exit = 155,520 configs
VERSION PARALLELE (multiprocessing Pool(24))

Indicateurs :
  beta_lookback: 132, 264, 396, 528, 792, 1320, 2640, 3690, 5280
  zscore_period: 10, 15, 20, 30, 50, 60, 80, 100
  correlation_period: 15, 30, 50, 60, 80
  adf_hurst_period: 26, 64, 128

Entry/Exit :
  zscore_entry: 2.0, 2.5, 3.0, 3.5
  cointegration_min: 40, 50
  zscore_tp: 1.0, 1.5, 2.0
  zscore_sl: 3.5, 4.0, 5.0
  dollar_mode: pure_zscore, safety (-$2000 SL)

Fixes : zscore_tp_enabled=True, zscore_tp_min_pnl=None, slippage 2 ticks
"""
import sys
sys.path.insert(0, "src")

from grid_search_runner import (
    GridSearchRunner,
    create_zscore_entry_exit_generator,
    create_zscore_label_builder,
    create_zscore_result_builder,
)

# ============================================================================
# CONFIGURATION DU GRID SEARCH
# ============================================================================

INDICATOR_PARAMS = {
    "beta_lookback": [132, 264, 396, 528, 792, 1320, 2640, 3690, 5280],
    "zscore_period": [10, 15, 20, 30, 50, 60, 80, 100],
    "correlation_period": [15, 30, 50, 60, 80],
    "adf_hurst_period": [26, 64, 128],
}

ZSCORE_ENTRY = [2.0, 2.5, 3.0, 3.5]
COINTEGRATION_MIN = [40, 50]
ZSCORE_TP = [1.0, 1.5, 2.0]
ZSCORE_SL = [3.5, 4.0, 5.0]
DOLLAR_MODES = ["pure_zscore", "safety"]

FIXED_OVERRIDES = {
    "exit.zscore_tp_enabled": True,
    "exit.zscore_tp_min_pnl": None,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

NUM_WORKERS = 24

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    runner = GridSearchRunner(
        indicator_params=INDICATOR_PARAMS,
        entry_exit_generator=create_zscore_entry_exit_generator(
            zscore_entry=ZSCORE_ENTRY,
            cointegration_min=COINTEGRATION_MIN,
            zscore_tp=ZSCORE_TP,
            zscore_sl=ZSCORE_SL,
            dollar_modes=DOLLAR_MODES,
        ),
        label_builder=create_zscore_label_builder(),
        result_builder=create_zscore_result_builder(),
        fixed_overrides=FIXED_OVERRIDES,
        timeframe="5min",
        title="GRID SEARCH 5-MIN - DONNEES 3 ANS (PARALLELE)",
    )

    runner.run(
        num_workers=NUM_WORKERS,
        output_path="output/grid_search_5min_phase1.csv",
        min_trades_for_sharpe=10,
    )
