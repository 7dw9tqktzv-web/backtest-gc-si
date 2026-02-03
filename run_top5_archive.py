"""
Archive des top 5 configs issues du walk-forward 3 ans (post-correction bugs 1, 4, 5).
Lance un backtest complet 3 ans pour chaque config, puis metrics + archivage.

Top 5 par frequence de selection dans le walk-forward :
  1. PnL2  : 16/34 fenetres (config dominante)
  2. Sh3   : 7/34 fenetres
  3. PnL1  : 4/34 fenetres
  4. Sh5   : 3/34 fenetres
  5. Sh4   : 2/34 fenetres
"""
import sys
import copy
import time
import yaml
from pathlib import Path

sys.path.insert(0, "src")

from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest, export_backtest
from metrics import run_metrics
from optimizer import apply_overrides

# ============================================================================
# CONFIG
# ============================================================================
CONFIG_PATH = Path("config/strategy_params.yaml")

# Fixes communes : 1 tick slippage
FIXED = {
    "costs.slippage_gc_ticks": 1,
    "costs.slippage_si_ticks": 1,
}

# Top 5 configs du walk-forward
TOP5_CONFIGS = [
    {
        "label": "PnL2_b1320_zp20_cp30_zE3.5_co50_TP1000_SL1200",
        "overrides": {
            "indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.pnl_take_profit": 1000, "exit.pnl_stop_loss": -1200,
            "exit.zscore_tp_enabled": False,
            "exit.zscore_tp_min_pnl": None,
        },
    },
    {
        "label": "Sh3_b660_zp15_cp20_zE3.0_co50_TP200_SL800_F200",
        "overrides": {
            "indicators.beta_lookback": 660, "indicators.zscore_period": 15,
            "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
            "entry.cointegration_score_min": 50,
            "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -800,
            "exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 200,
        },
    },
    {
        "label": "PnL1_b1320_zp20_cp30_zE3.5_co50_TP500_SL1200",
        "overrides": {
            "indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -1200,
            "exit.zscore_tp_enabled": False,
            "exit.zscore_tp_min_pnl": None,
        },
    },
    {
        "label": "Sh5_b1980_zp20_cp20_zE3.5_co60_TP400_SL800",
        "overrides": {
            "indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
            "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 60,
            "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800,
            "exit.zscore_tp_enabled": False,
            "exit.zscore_tp_min_pnl": None,
        },
    },
    {
        "label": "Sh4_b1320_zp20_cp20_zE3.5_co50_TP400_SL800",
        "overrides": {
            "indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
            "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800,
            "exit.zscore_tp_enabled": False,
            "exit.zscore_tp_min_pnl": None,
        },
    },
]


def save_config_yaml(config, path):
    """Sauvegarde la config dans le fichier YAML."""
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def main():
    t0 = time.time()

    # Sauvegarder le YAML original
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        original_yaml_content = f.read()

    print("=" * 80)
    print("ARCHIVAGE TOP 5 CONFIGS - Walk-Forward 3 ans (bugs 1/4/5 corriges)")
    print("=" * 80)

    # Charger les donnees une seule fois
    print("\n[1/2] Chargement des donnees...")
    df_1min, base_config, stats = load_and_prepare_data(verbose=True)
    df_5s = load_5s_data(base_config, verbose=True)
    print("[OK] Donnees chargees\n")

    results = []

    try:
        for i, cfg_def in enumerate(TOP5_CONFIGS, 1):
            label = cfg_def["label"]
            overrides = {**FIXED, **cfg_def["overrides"]}

            print("=" * 80)
            print(f"CONFIG {i}/5 : {label}")
            print("=" * 80)

            # Appliquer les overrides
            config = apply_overrides(base_config, overrides)

            # Calculer les indicateurs
            print(f"  [1/4] Calcul des indicateurs...")
            df_ind = calculate_all_indicators(df_1min, config)

            # Lancer le backtest hybride
            print(f"  [2/4] Backtest hybride 3 ans...")
            t1 = time.time()
            trades_df = run_hybrid_backtest(df_ind, df_5s, config)
            dt = time.time() - t1
            n_trades = len(trades_df)
            pnl = trades_df['PnL_Net'].sum() if n_trades > 0 else 0
            print(f"  [OK] {n_trades} trades, PnL=${pnl:,.0f} ({dt:.1f}s)")

            # Exporter le CSV (necessaire pour metrics.py)
            print(f"  [3/4] Export CSV...")
            export_backtest(trades_df, config, "output/backtest_hybrid.csv")

            # Sauvegarder la config dans le YAML (necessaire pour metrics.py)
            save_config_yaml(config, CONFIG_PATH)

            # Lancer metrics + archivage
            print(f"  [4/4] Metrics + archivage...")
            gm, am = run_metrics()

            results.append({
                "rank": i,
                "label": label,
                "trades": n_trades,
                "pnl": pnl,
            })

            print(f"\n  >>> Config {i}/5 archivee avec succes\n")

    finally:
        # Restaurer le YAML original quoi qu'il arrive
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(original_yaml_content)
        print("[OK] YAML original restaure")

    # Resume final
    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print(f"RESUME TOP 5 CONFIGS (total : {elapsed:.1f}s)")
    print("=" * 80)
    print(f"{'#':<4} {'Label':<55} {'Trades':>7} {'PnL':>12}")
    print("-" * 80)
    for r in results:
        print(f"{r['rank']:<4} {r['label']:<55} {r['trades']:>7} ${r['pnl']:>10,.0f}")
    print("-" * 80)
    print("[OK] Toutes les configs archivees dans output/archive/")
    print("     Consultez output/archive/index.csv pour la comparaison complete")


if __name__ == "__main__":
    main()
