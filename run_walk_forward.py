"""
Walk-Forward Test sur 8 mois de donnees GC/SI.

Principe :
  - Decoupe les donnees en fenetres glissantes (train + test)
  - Pour chaque fenetre : teste N configs sur TRAIN, selectionne la meilleure,
    puis valide sur TEST (hors echantillon)
  - Agregation des resultats hors echantillon pour detecter l'overfitting

Fenetres : 6 periodes de ~30j train + ~15j test (glissement ~25j)
Warm-up  : beta_lookback barres incluses avant chaque fenetre d'entrainement
Configs  : top 12 du grid search (6 par PnL + 6 par Sharpe, dedupliques)
"""
import sys
sys.path.insert(0, "src")

from walk_forward_runner import WalkForwardRunner

# ============================================================================
# CONFIGS A TESTER (top du grid search sur 8 mois)
# ============================================================================
# Top 6 par PnL + Top 6 par Sharpe (dedupliques)

CONFIGS_TO_TEST = [
    # --- Top PnL ---
    {"label": "PnL1_b1320_zp20_cp30_co40_TP400_SL600",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -600}},
    {"label": "PnL2_b1980_zp20_cp30_co40_TP400_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -600}},
    {"label": "PnL3_b1320_zp20_cp30_co40_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "PnL4_b1980_zp20_cp30_co40_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "PnL5_b1320_zp20_cp30_co40_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
    {"label": "PnL6_b1980_zp20_cp30_co40_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
    # --- Top Sharpe / risk-adjusted ---
    {"label": "Sh1_b2640_zp20_cp30_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh2_b2640_zp20_cp60_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 60, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh3_b3960_zp20_cp30_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 3960, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh4_b1980_zp20_cp60_co50_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 60, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "Sh5_b2640_zp20_cp30_co50_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh6_b1980_zp20_cp30_co50_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
]

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    runner = WalkForwardRunner(
        configs_to_test=CONFIGS_TO_TEST,
        train_days=30,
        test_days=15,
        step_days=25,
        warmup_bars=4000,  # max beta 3960 + marge
        timeframe="1min",
        title="WALK-FORWARD TEST (1-min, 8 mois)",
        output_path="output/walk_forward_results.csv",
        selection_criterion="pnl_net",
    )

    runner.run()
