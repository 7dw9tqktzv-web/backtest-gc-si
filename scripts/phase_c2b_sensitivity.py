# ============================================================================
# PHASE C2b - ANALYSE DE SENSIBILITE DU SEUIL DE CORRELATION
# ============================================================================
#
# Teste une gamme de seuils de correlation daily pour identifier le sweet spot
# entre qualite des trades et quantite suffisante pour validation statistique.
#
# Usage:
#   python scripts/phase_c2b_sensitivity.py
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
            'PnL': 0, 'Trades': 0, 'Blocked': 0, 'Win_Rate': 0,
            'PF': 0, 'Max_DD': 0, 'Sharpe': 0, 'Avg_PnL': 0,
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
    print("=" * 90)
    print("PHASE C2b - ANALYSE DE SENSIBILITE DU SEUIL DE CORRELATION DAILY")
    print("=" * 90)

    # Charger les donnees
    print("\n[1/4] Chargement des donnees...")
    df_raw, config, stats = load_and_prepare_data(verbose=False)
    print(f"   Barres 1-min: {len(df_raw)}")

    # Config meilleure 5-min B2
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
    config['exit']['pnl_take_profit'] = 999999
    config['exit']['pnl_stop_loss'] = -999999
    config['exit']['zscore_tp_min_pnl'] = None
    config['costs']['slippage_gc_ticks'] = 1
    config['costs']['slippage_si_ticks'] = 1

    # Resample 5-min
    print("[2/4] Resample en 5-min...")
    df_5min = resample_to_5min(df_raw)
    print(f"   Barres 5-min: {len(df_5min)}")

    # Donnees 5s
    print("[3/4] Chargement des donnees 5s...")
    df_5s = load_5s_data(config, verbose=False)
    print(f"   Barres 5s: {len(df_5s)}")

    # Seuils a tester
    thresholds = [0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.98, 1.00]

    # Pre-calculer les indicateurs avec correlation daily pour tous les seuils
    # (les indicateurs sont les memes, seul le seuil de blocage change)
    # On calcule une seule fois avec le filtre active
    print("\n[4/4] Lancement des backtests (14 seuils)...")

    cfg_base = copy.deepcopy(config)
    cfg_base['regime_filter'] = {
        'enabled': True,
        'halflife_ar1': {'enabled': False, 'window': 60, 'threshold': 4.9},
        'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.80},
    }

    # Calculer les indicateurs une seule fois (avec le filtre active)
    df_with_indicators = calculate_all_indicators(df_5min.copy(), cfg_base, verbose=False)

    # Baseline (sans filtre)
    cfg_baseline = copy.deepcopy(config)
    cfg_baseline['regime_filter'] = {'enabled': False}
    df_baseline = calculate_all_indicators(df_5min.copy(), cfg_baseline, verbose=False)
    trades_baseline = run_hybrid_backtest(df_baseline, df_5s, cfg_baseline, verbose=False)
    baseline_trades = len(trades_baseline)

    results = []

    for threshold in thresholds:
        cfg = copy.deepcopy(config)
        cfg['regime_filter'] = {
            'enabled': True,
            'halflife_ar1': {'enabled': False, 'window': 60, 'threshold': 4.9},
            'correlation_daily': {'enabled': True, 'window': 40, 'threshold': threshold},
        }

        # Reutiliser le df avec indicateurs deja calcules
        trades = run_hybrid_backtest(df_with_indicators.copy(), df_5s, cfg, verbose=False)
        m = compute_metrics(trades)
        m['Threshold'] = threshold
        m['Blocked'] = baseline_trades - m['Trades']
        results.append(m)

        print(f"   Seuil {threshold:.2f} : {m['Trades']:3d} trades | "
              f"PnL ${m['PnL']:+9,.0f} | PF {m['PF']:6.2f} | "
              f"WR {m['Win_Rate']:5.1f}% | Sharpe {m['Sharpe']:.3f}")

    # Tableau comparatif
    print("\n" + "=" * 110)
    print("TABLEAU DE SENSIBILITE")
    print("=" * 110)

    header = (f"{'Seuil':>6} {'Trades':>7} {'Bloques':>8} {'WR%':>6} "
              f"{'PnL':>11} {'PF':>7} {'MaxDD':>11} {'Sharpe':>7} {'PnL/Trade':>10}")
    print(header)
    print("-" * 110)

    for m in results:
        pnl_per_trade = m['PnL'] / m['Trades'] if m['Trades'] > 0 else 0
        pf_str = f"{m['PF']:.2f}" if m['PF'] < 100 else "inf"
        print(f"{m['Threshold']:>6.2f} {m['Trades']:>7} {m['Blocked']:>8} {m['Win_Rate']:>5.1f}% "
              f"${m['PnL']:>+10,.0f} {pf_str:>7} ${m['Max_DD']:>+10,.0f} {m['Sharpe']:>7.3f} "
              f"${pnl_per_trade:>+9,.0f}")

    # Identification des seuils optimaux
    print("\n" + "=" * 110)
    print("SEUILS OPTIMAUX")
    print("=" * 110)

    df_results = pd.DataFrame(results)
    df_results['PnL_per_Trade'] = df_results.apply(
        lambda r: r['PnL'] / r['Trades'] if r['Trades'] > 0 else 0, axis=1
    )

    # 1. Max PnL
    has_trades = df_results[df_results['Trades'] > 0]
    if len(has_trades) > 0:
        best_pnl = has_trades.loc[has_trades['PnL'].idxmax()]
        print(f"\n   Max PnL     : seuil={best_pnl['Threshold']:.2f} | "
              f"PnL=${best_pnl['PnL']:+,.0f} | {int(best_pnl['Trades'])} trades")

    # 2. Max Sharpe
    if len(has_trades) > 0:
        best_sharpe = has_trades.loc[has_trades['Sharpe'].idxmax()]
        print(f"   Max Sharpe  : seuil={best_sharpe['Threshold']:.2f} | "
              f"Sharpe={best_sharpe['Sharpe']:.3f} | {int(best_sharpe['Trades'])} trades")

    # 3. Sweet spot (best Sharpe avec >= 50 trades)
    enough_trades = df_results[df_results['Trades'] >= 50]
    if len(enough_trades) > 0:
        sweet = enough_trades.loc[enough_trades['Sharpe'].idxmax()]
        print(f"   Sweet spot  : seuil={sweet['Threshold']:.2f} | "
              f"Sharpe={sweet['Sharpe']:.3f} | {int(sweet['Trades'])} trades | "
              f"PnL=${sweet['PnL']:+,.0f}")
    else:
        print("   Sweet spot  : AUCUN seuil avec >= 50 trades")

    # 4. Safe (best PF avec >= 70 trades)
    safe_trades = df_results[df_results['Trades'] >= 70]
    if len(safe_trades) > 0:
        safe = safe_trades.loc[safe_trades['PF'].idxmax()]
        print(f"   Safe        : seuil={safe['Threshold']:.2f} | "
              f"PF={safe['PF']:.2f} | {int(safe['Trades'])} trades | "
              f"PnL=${safe['PnL']:+,.0f}")
    else:
        print("   Safe        : AUCUN seuil avec >= 70 trades")

    # Diagnostic de robustesse
    print("\n" + "=" * 110)
    print("DIAGNOSTIC DE ROBUSTESSE")
    print("=" * 110)

    # Verifier si le filtre est progressif
    pnl_values = df_results[df_results['Trades'] > 0]['PnL'].values
    if len(pnl_values) >= 3:
        # Calculer la variance normalisee du PnL entre seuils adjacents
        diffs = np.abs(np.diff(pnl_values))
        mean_diff = np.mean(diffs)
        max_diff = np.max(diffs)
        range_pnl = np.max(pnl_values) - np.min(pnl_values)

        print(f"\n   Variation moyenne entre seuils adjacents : ${mean_diff:,.0f}")
        print(f"   Variation max entre seuils adjacents     : ${max_diff:,.0f}")
        print(f"   Range PnL total                          : ${range_pnl:,.0f}")

        if max_diff > range_pnl * 0.5:
            print("   --> ATTENTION : effet de seuil brutal detecte (curve-fitting probable)")
        elif mean_diff < range_pnl * 0.15:
            print("   --> Filtre progressif (degradation lineaire) -- signal ROBUSTE")
        else:
            print("   --> Filtre moderement stable")

    # Sauvegarder
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "phase_c2b_sensitivity.csv"
    df_results.to_csv(csv_path, index=False)
    print(f"\n[OK] Resultats sauvegardes dans : {csv_path}")
    print("=" * 110)


if __name__ == '__main__':
    main()
