"""
Grid Search Phase 1 - Donnees 3 ans (Jan 2023 - Jan 2026)
300 groupes indicateurs x 108 entry/exit = 32,400 configs
VERSION PARALLELE (multiprocessing)

Indicateurs :
  beta_lookback: 660, 1320, 1980, 2640, 3960
  zscore_period: 15, 20, 30, 50, 60
  correlation_period: 20, 30, 50, 60
  adf_hurst_period: 64, 128, 256

Entry/Exit :
  zscore_entry: -2.0, -2.5, -3.0, -3.5
  cointegration_score_min: 40, 50, 60
  pnl_take_profit: 200, 300, 400
  pnl_stop_loss: -400, -600, -800

Fixes : zscore_tp_min_pnl=0, slippage 2 ticks, commission $4
"""
import sys
sys.path.insert(0, "src")

from grid_search_runner import (
    GridSearchRunner,
    create_standard_entry_exit_generator,
    create_standard_label_builder,
    create_standard_result_builder,
)

# ============================================================================
# CONFIGURATION DU GRID SEARCH
# ============================================================================

INDICATOR_PARAMS = {
    "beta_lookback": [660, 1320, 1980, 2640, 3960],
    "zscore_period": [15, 20, 30, 50, 60],
    "correlation_period": [20, 30, 50, 60],
    "adf_hurst_period": [64, 128, 256],
}

ENTRY_EXIT_PARAMS = {
    "zscore_entry": [2.0, 2.5, 3.0, 3.5],
    "cointegration_min": [40, 50, 60],
    "pnl_take_profit": [200, 300, 400],
    "pnl_stop_loss": [-400, -600, -800],
}

FIXED_OVERRIDES = {
    "exit.zscore_tp_min_pnl": 0,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

NUM_WORKERS = 24  # 24 threads (hyperthreading)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    runner = GridSearchRunner(
        indicator_params=INDICATOR_PARAMS,
        entry_exit_generator=create_standard_entry_exit_generator(
            zscore_entry=ENTRY_EXIT_PARAMS["zscore_entry"],
            cointegration_min=ENTRY_EXIT_PARAMS["cointegration_min"],
            pnl_take_profit=ENTRY_EXIT_PARAMS["pnl_take_profit"],
            pnl_stop_loss=ENTRY_EXIT_PARAMS["pnl_stop_loss"],
        ),
        label_builder=create_standard_label_builder(),
        result_builder=create_standard_result_builder(),
        fixed_overrides=FIXED_OVERRIDES,
        timeframe="1min",
        title="GRID SEARCH PHASE 1 - DONNEES 3 ANS (PARALLELE)",
    )

    runner.run(
        num_workers=NUM_WORKERS,
        output_path="output/grid_search_3y_phase1.csv",
        min_trades_for_sharpe=20,
    )
