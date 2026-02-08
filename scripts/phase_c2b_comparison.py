# ============================================================================
# PHASE C2b - COMPARAISON DES FILTRES DE REGIME
# ============================================================================
#
# Lance 4 backtests avec la meilleure config 5-min et compare :
#   A) Baseline (sans filtre)
#   B) Half-life AR(1) seul
#   C) Correlation Daily seule
#   D) Les deux combines
#
# Usage:
#   python scripts/phase_c2b_comparison.py
#
# ============================================================================

import sys
import os
import copy
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest


def compute_metrics(trades_df):
    """Calcule les metriques cles d'un backtest."""
    if len(trades_df) == 0:
        return {
            'PnL': 0, 'Trades': 0, 'Win_Rate': 0, 'PF': 0,
            'Max_DD': 0, 'Sharpe': 0, 'Avg_PnL': 0,
        }

    pnl_net = trades_df['PnL_Net']
    winners = pnl_net[pnl_net > 0]
    losers = pnl_net[pnl_net <= 0]

    gross_profit = winners.sum() if len(winners) > 0 else 0
    gross_loss = abs(losers.sum()) if len(losers) > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    cumul = pnl_net.cumsum()
    peak = cumul.cummax()
    max_dd = (cumul - peak).min()

    sharpe = pnl_net.mean() / pnl_net.std() if pnl_net.std() > 0 else 0

    return {
        'PnL': round(pnl_net.sum(), 2),
        'Trades': len(trades_df),
        'Win_Rate': round(len(winners) / len(trades_df) * 100, 1),
        'PF': round(pf, 2),
        'Max_DD': round(max_dd, 2),
        'Sharpe': round(sharpe, 3),
        'Avg_PnL': round(pnl_net.mean(), 2),
    }


def main():
    print("=" * 70)
    print("PHASE C2b - COMPARAISON DES FILTRES DE REGIME")
    print("=" * 70)

    # Charger les donnees
    print("\n[1/5] Chargement des donnees...")
    df_raw, config, stats = load_and_prepare_data(verbose=False)
    print(f"   Barres 1-min: {len(df_raw)}")

    # Utiliser la meilleure config 5-min B2
    # b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0
    config['indicators']['period'] = '5min'
    config['indicators']['beta_lookback'] = 2640
    config['indicators']['zscore_period'] = 20
    config['indicators']['correlation_period'] = 30
    config['indicators']['adf_hurst_period'] = 26
    config['entry']['zscore_long'] = -3.5
    config['entry']['zscore_short'] = 3.5
    config['entry']['cointegration_score_min'] = 40
    config['exit']['zscore_tp_enabled'] = True
    config['exit']['zscore_tp_long'] = -1.0
    config['exit']['zscore_tp_short'] = 1.0
    config['exit']['zscore_sl_long'] = -3.5
    config['exit']['zscore_sl_short'] = 3.5
    # Mode pure zscore (pas de dollar exits)
    config['exit']['pnl_take_profit'] = 999999
    config['exit']['pnl_stop_loss'] = -999999
    config['exit']['zscore_tp_min_pnl'] = None
    config['costs']['slippage_gc_ticks'] = 1
    config['costs']['slippage_si_ticks'] = 1

    # Resample en 5-min
    print("[2/5] Resample en 5-min...")
    df_5min = resample_to_5min(df_raw)
    print(f"   Barres 5-min: {len(df_5min)}")

    # Charger les donnees 5s (pour le backtest hybride)
    print("[3/5] Chargement des donnees 5s...")
    df_5s = load_5s_data(config, verbose=False)
    print(f"   Barres 5s: {len(df_5s)}")

    # Definir les 4 modes
    modes = {
        'A: Baseline (OFF/OFF)': {'enabled': False},
        'B: Half-life seul (ON/OFF)': {
            'enabled': True,
            'halflife_ar1': {'enabled': True, 'window': 60, 'threshold': 4.9},
            'correlation_daily': {'enabled': False, 'window': 40, 'threshold': 0.916},
        },
        'C: Correlation seule (OFF/ON)': {
            'enabled': True,
            'halflife_ar1': {'enabled': False, 'window': 60, 'threshold': 4.9},
            'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.916},
        },
        'D: Combines (ON/ON)': {
            'enabled': True,
            'halflife_ar1': {'enabled': True, 'window': 60, 'threshold': 4.9},
            'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.916},
        },
    }

    results = {}

    print("\n[4/5] Lancement des 4 backtests...")
    for mode_name, rf_config in modes.items():
        print(f"\n   --- {mode_name} ---")
        cfg = copy.deepcopy(config)
        cfg['regime_filter'] = rf_config

        # Calculer les indicateurs (avec ou sans regime filter)
        df = calculate_all_indicators(df_5min.copy(), cfg, verbose=False)

        # Lancer le backtest
        trades = run_hybrid_backtest(df, df_5s, cfg, verbose=False)

        metrics = compute_metrics(trades)
        results[mode_name] = metrics

        print(f"   PnL: ${metrics['PnL']:+,.0f} | Trades: {metrics['Trades']} | "
              f"WR: {metrics['Win_Rate']}% | PF: {metrics['PF']:.2f} | "
              f"MaxDD: ${metrics['Max_DD']:+,.0f}")

    # Tableau comparatif
    print("\n" + "=" * 70)
    print("[5/5] TABLEAU COMPARATIF")
    print("=" * 70)

    baseline_pnl = results['A: Baseline (OFF/OFF)']['PnL']

    header = f"{'Mode':<30} {'PnL':>10} {'Delta':>10} {'Trades':>7} {'WR%':>6} {'PF':>6} {'MaxDD':>10} {'Sharpe':>7}"
    print(header)
    print("-" * len(header))

    for mode_name, m in results.items():
        delta = m['PnL'] - baseline_pnl
        delta_str = f"${delta:+,.0f}" if mode_name != 'A: Baseline (OFF/OFF)' else '-'
        print(f"{mode_name:<30} ${m['PnL']:>+9,.0f} {delta_str:>10} {m['Trades']:>7} "
              f"{m['Win_Rate']:>5.1f}% {m['PF']:>5.2f} ${m['Max_DD']:>+9,.0f} {m['Sharpe']:>6.3f}")

    # Sauvegarder en CSV
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "phase_c2b_comparison.csv"

    rows = []
    for mode_name, m in results.items():
        row = {'Mode': mode_name, **m}
        row['Delta_vs_Baseline'] = m['PnL'] - baseline_pnl
        rows.append(row)

    df_results = pd.DataFrame(rows)
    df_results.to_csv(csv_path, index=False)
    print(f"\n[OK] Resultats sauvegardes dans : {csv_path}")
    print("=" * 70)


if __name__ == '__main__':
    main()
