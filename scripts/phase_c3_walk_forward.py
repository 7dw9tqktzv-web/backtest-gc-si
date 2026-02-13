# ============================================================================
# PHASE C3 - WALK-FORWARD FINAL AVEC FILTRE CORRELATION DAILY
# ============================================================================
#
# Compare le walk-forward avec et sans filtre correlation daily.
# Seuil FIXE (pas optimise par fenetre) pour eviter l'overfitting.
#
# Teste aussi 2 seuils supplementaires (0.84, 0.88) pour la robustesse.
#
# Usage:
#   python scripts/phase_c3_walk_forward.py
#
# ============================================================================

import sys
import time
import copy
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics
from walk_forward_runner import slice_data, slice_5s


# ============================================================================
# CONFIGS CANDIDATES (meme pool que WF precedents)
# ============================================================================

# Top 4 configs zTP (wf_5min_ztp.yaml)
CONFIGS_ZTP = [
    {
        "label": "zTP-1.0_b2640_zp20_cp30_adf26_co40",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "zTP-0.5_b2640_zp20_cp30_adf26_co40",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 0.5, "exit.zscore_tp_short": -0.5,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "zTP0.0_b2640_zp20_cp30_adf26_co40",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "zTP1.0_b2640_zp20_cp30_adf26_co40",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": -1.0, "exit.zscore_tp_short": 1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
]

# Top 5 configs beta long (wf_beta_long.yaml)
CONFIGS_BETA_LONG = [
    {
        "label": "b3960_zp24_cp12_adf26_co40_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 24,
            "indicators.correlation_period": 12, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "b3960_zp24_cp12_adf26_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 24,
            "indicators.correlation_period": 12, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "b3960_zp24_cp60_adf26_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 24,
            "indicators.correlation_period": 60, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "b3960_zp24_cp24_adf26_co40_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 24,
            "indicators.correlation_period": 24, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 40,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
    {
        "label": "b3960_zp24_cp48_adf26_co50_zTP-1.0",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 24,
            "indicators.correlation_period": 48, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_enabled": True,
            "exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
            "exit.zscore_sl_long": -4.0, "exit.zscore_sl_short": 4.0,
            "exit.pnl_take_profit": 99999, "exit.pnl_stop_loss": -99999,
            "costs.slippage_gc_ticks": 2, "costs.slippage_si_ticks": 2,
        },
    },
]

ALL_CONFIGS = CONFIGS_ZTP + CONFIGS_BETA_LONG


# ============================================================================
# WALK-FORWARD ENGINE
# ============================================================================

def run_single_wf(df_main, df_5s, base_config, configs_to_test,
                  regime_filter_config, train_days=63, test_days=21,
                  step_days=21, warmup_bars=4500, verbose=True):
    """
    Lance un walk-forward complet et retourne les resultats par fenetre.

    Args:
        regime_filter_config: dict pour config['regime_filter'] (None = sans filtre)

    Returns:
        list of dicts avec resultats par fenetre
    """
    # Construire les fenetres
    trading_dates = pd.Series(df_main['DateTime'].dt.date.unique()).sort_values().reset_index(drop=True)
    n_days = len(trading_dates)

    # Trouver le premier jour avec warmup suffisant
    warmup_day_idx = 0
    for idx in range(n_days):
        day = trading_dates[idx]
        n_bars_before = len(df_main[df_main['DateTime'].dt.date < day])
        if n_bars_before >= warmup_bars:
            warmup_day_idx = idx
            break

    windows = []
    current_idx = warmup_day_idx
    while current_idx + train_days + test_days <= n_days:
        windows.append({
            "train_start": trading_dates[current_idx],
            "train_end": trading_dates[current_idx + train_days - 1],
            "test_start": trading_dates[current_idx + train_days],
            "test_end": trading_dates[min(current_idx + train_days + test_days - 1, n_days - 1)],
        })
        current_idx += step_days

    results = []

    for w_idx, window in enumerate(windows):
        # Decouper les donnees
        df_train = slice_data(df_main, window['train_start'], window['train_end'],
                              include_warmup=True, warmup_bars=warmup_bars)
        df_5s_train = slice_5s(df_5s, window['train_start'], window['train_end'])
        df_test = slice_data(df_main, window['test_start'], window['test_end'],
                             include_warmup=True, warmup_bars=warmup_bars)
        df_5s_test = slice_5s(df_5s, window['test_start'], window['test_end'])

        # Phase TRAIN - tester toutes les configs
        train_metrics = []
        for cfg in configs_to_test:
            config_full = apply_overrides(base_config, cfg['overrides'])
            if regime_filter_config:
                config_full['regime_filter'] = copy.deepcopy(regime_filter_config)
            df_train_ind = calculate_all_indicators(df_train, config_full, verbose=False)
            trades_df = run_hybrid_backtest(df_train_ind, df_5s_train, config_full, verbose=False)
            metrics = compute_metrics(trades_df)
            metrics['label'] = cfg['label']
            train_metrics.append(metrics)

        # Selectionner la meilleure config sur TRAIN (par PnL)
        best_train = max(train_metrics, key=lambda x: x['pnl_net'])
        best_label = best_train['label']

        # Phase TEST
        best_cfg = [c for c in configs_to_test if c['label'] == best_label][0]
        config_test = apply_overrides(base_config, best_cfg['overrides'])
        if regime_filter_config:
            config_test['regime_filter'] = copy.deepcopy(regime_filter_config)
        df_test_ind = calculate_all_indicators(df_test, config_test, verbose=False)
        trades_test = run_hybrid_backtest(df_test_ind, df_5s_test, config_test, verbose=False)
        test_metrics = compute_metrics(trades_test)

        if verbose:
            print(f"   W{w_idx+1:02d} TEST {window['test_start']} -> {window['test_end']} | "
                  f"{best_label[:30]:30s} | {test_metrics['trades']:>3} trades ${test_metrics['pnl_net']:>+8,.0f}")

        results.append({
            "window": w_idx + 1,
            "test_start": str(window['test_start']),
            "test_end": str(window['test_end']),
            "best_config": best_label,
            "train_trades": best_train['trades'],
            "train_pnl": best_train['pnl_net'],
            "test_trades": test_metrics['trades'],
            "test_pnl": test_metrics['pnl_net'],
            "test_wr": test_metrics['win_rate'],
            "test_pf": test_metrics['profit_factor'],
            "test_maxdd": test_metrics['max_dd'],
        })

    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 110)
    print("PHASE C3 - WALK-FORWARD FINAL AVEC FILTRE CORRELATION DAILY")
    print("=" * 110)

    t_global = time.time()

    # --- Charger les donnees ---
    print("\n[1/5] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   5-min: {len(df_5min):,} barres | 5s: {len(df_5s):,} barres")
    print(f"   Configs candidates: {len(ALL_CONFIGS)} (4 zTP + 5 beta long)")

    # --- WF SANS FILTRE (baseline) ---
    print(f"\n[2/5] Walk-forward SANS filtre (baseline)...")
    print(f"   34 fenetres x {len(ALL_CONFIGS)} configs...")
    results_no_filter = run_single_wf(
        df_5min, df_5s, base_config, ALL_CONFIGS,
        regime_filter_config=None,
        warmup_bars=4500,
    )

    # --- WF AVEC FILTRE seuil=0.86 ---
    print(f"\n[3/5] Walk-forward AVEC filtre correlation (seuil=0.86)...")
    rf_086 = {
        'enabled': True,
        'halflife_ar1': {'enabled': False, 'window': 60, 'threshold': 4.9},
        'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.86},
    }
    results_filter_086 = run_single_wf(
        df_5min, df_5s, base_config, ALL_CONFIGS,
        regime_filter_config=rf_086,
        warmup_bars=4500,
    )

    # --- WF seuils supplementaires (0.84 et 0.88) ---
    print(f"\n[4/5] Walk-forward seuils supplementaires (0.84, 0.88)...")

    rf_084 = copy.deepcopy(rf_086)
    rf_084['correlation_daily']['threshold'] = 0.84
    print(f"   Seuil 0.84:")
    results_filter_084 = run_single_wf(
        df_5min, df_5s, base_config, ALL_CONFIGS,
        regime_filter_config=rf_084,
        warmup_bars=4500,
    )

    rf_088 = copy.deepcopy(rf_086)
    rf_088['correlation_daily']['threshold'] = 0.88
    print(f"   Seuil 0.88:")
    results_filter_088 = run_single_wf(
        df_5min, df_5s, base_config, ALL_CONFIGS,
        regime_filter_config=rf_088,
        warmup_bars=4500,
    )

    t_total = time.time() - t_global

    # ================================================================
    # RESULTATS
    # ================================================================
    print(f"\n\n{'='*110}")
    print(f"[5/5] RESULTATS (temps total: {t_total/60:.1f} min)")
    print(f"{'='*110}")

    # --- Tableau global ---
    def summarize(results):
        pnl = sum(r['test_pnl'] for r in results)
        trades = sum(r['test_trades'] for r in results)
        n_pos = sum(1 for r in results if r['test_pnl'] > 0)
        n_inactive = sum(1 for r in results if r['test_trades'] == 0)
        pnl_per_trade = pnl / trades if trades > 0 else 0

        # Win rate et PF agreges
        all_pnls = [r['test_pnl'] for r in results if r['test_trades'] > 0]
        wins_pnl = sum(p for p in all_pnls if p > 0)
        loss_pnl = abs(sum(p for p in all_pnls if p < 0))
        pf = wins_pnl / loss_pnl if loss_pnl > 0 else float('inf')

        # Max drawdown sur les fenetres (equity curve des PnL par fenetre)
        cumul = np.cumsum([r['test_pnl'] for r in results])
        peak = np.maximum.accumulate(cumul)
        maxdd = np.min(cumul - peak) if len(cumul) > 0 else 0

        return {
            'pnl': pnl, 'trades': trades, 'n_pos': n_pos,
            'n_inactive': n_inactive, 'pnl_per_trade': pnl_per_trade,
            'pf': pf, 'maxdd': maxdd, 'n_windows': len(results),
        }

    s_no = summarize(results_no_filter)
    s_086 = summarize(results_filter_086)

    print(f"\nTABLEAU GLOBAL")
    print(f"{'='*90}")
    header = f"{'Metrique':<30} {'Sans Filtre':>18} {'Avec Filtre (0.86)':>18} {'Delta':>15}"
    print(header)
    print("-" * 90)

    def fmt_delta(v_no, v_with, fmt_str="${:+,.0f}", is_pct=False):
        d = v_with - v_no
        if is_pct:
            return f"{d:+.1f}%"
        return fmt_str.format(d)

    print(f"{'PnL total TEST':<30} ${s_no['pnl']:>+16,.0f} ${s_086['pnl']:>+16,.0f} {fmt_delta(s_no['pnl'], s_086['pnl']):>15}")
    print(f"{'Trades TEST':<30} {s_no['trades']:>18} {s_086['trades']:>18} {s_086['trades'] - s_no['trades']:>+15}")
    pf_no_str = f"{s_no['pf']:.2f}" if s_no['pf'] < 100 else "inf"
    pf_086_str = f"{s_086['pf']:.2f}" if s_086['pf'] < 100 else "inf"
    print(f"{'Profit Factor':<30} {pf_no_str:>18} {pf_086_str:>18}")
    print(f"{'Max Drawdown (fenetres)':<30} ${s_no['maxdd']:>+16,.0f} ${s_086['maxdd']:>+16,.0f} {fmt_delta(s_no['maxdd'], s_086['maxdd']):>15}")
    print(f"{'Fenetres positives':<30} {s_no['n_pos']:>13}/{s_no['n_windows']} {s_086['n_pos']:>13}/{s_086['n_windows']} {s_086['n_pos'] - s_no['n_pos']:>+15}")
    print(f"{'Fenetres inactives (0 trades)':<30} {s_no['n_inactive']:>13}/{s_no['n_windows']} {s_086['n_inactive']:>13}/{s_086['n_windows']} {s_086['n_inactive'] - s_no['n_inactive']:>+15}")
    ppt_no = s_no['pnl_per_trade']
    ppt_086 = s_086['pnl_per_trade']
    print(f"{'PnL/Trade moyen':<30} ${ppt_no:>+16,.0f} ${ppt_086:>+16,.0f} {fmt_delta(ppt_no, ppt_086):>15}")

    # --- Tableau par fenetre ---
    print(f"\n\nTABLEAU PAR FENETRE")
    print(f"{'='*130}")
    header2 = (f"{'W':>3} {'Periode TEST':<25} {'Tr(sans)':>8} {'PnL(sans)':>11} "
               f"{'Tr(avec)':>8} {'PnL(avec)':>11} {'Delta PnL':>11}")
    print(header2)
    print("-" * 130)

    for rn, rf in zip(results_no_filter, results_filter_086):
        delta = rf['test_pnl'] - rn['test_pnl']
        print(f"{rn['window']:>3} {rn['test_start']} -> {rn['test_end']:<10} "
              f"{rn['test_trades']:>8} ${rn['test_pnl']:>+10,.0f} "
              f"{rf['test_trades']:>8} ${rf['test_pnl']:>+10,.0f} "
              f"${delta:>+10,.0f}")

    # --- Fenetres toxiques C1 ---
    # C1 identifie W02, W04, W05, W08 comme toxiques
    # Mais les index C1 etaient sur 15 fenetres (C0 scoring)
    # Ici on a 34 fenetres avec decalage 21j. On identifie les toxiques
    # comme les fenetres avec les pires PnL sans filtre
    print(f"\n\nFENETRES TOXIQUES (pires PnL sans filtre)")
    print(f"{'='*100}")

    # Trouver les 6 pires fenetres sans filtre
    sorted_by_pnl = sorted(enumerate(results_no_filter), key=lambda x: x[1]['test_pnl'])
    toxic_indices = [i for i, r in sorted_by_pnl[:6]]

    header3 = f"{'W':>3} {'Periode TEST':<25} {'PnL sans':>11} {'PnL avec':>11} {'Delta':>11} {'Neutralisee?':>14}"
    print(header3)
    print("-" * 100)

    n_neutralized = 0
    for idx in sorted(toxic_indices):
        rn = results_no_filter[idx]
        rf = results_filter_086[idx]
        delta = rf['test_pnl'] - rn['test_pnl']
        neutralized = rf['test_pnl'] >= 0 or rf['test_pnl'] > rn['test_pnl']
        if neutralized:
            n_neutralized += 1
        status = "OUI" if neutralized else "NON"
        print(f"{rn['window']:>3} {rn['test_start']} -> {rn['test_end']:<10} "
              f"${rn['test_pnl']:>+10,.0f} ${rf['test_pnl']:>+10,.0f} "
              f"${delta:>+10,.0f} {status:>14}")

    print(f"\nNeutralisees: {n_neutralized}/{len(toxic_indices)}")

    # --- Analyse par periode ---
    print(f"\n\nANALYSE PAR PERIODE")
    print(f"{'='*80}")
    header4 = f"{'Periode':<15} {'Fenetres':<10} {'PnL sans':>12} {'PnL avec':>12} {'Delta':>12}"
    print(header4)
    print("-" * 80)

    for year_label, year_prefixes in [("2023", ["2023"]), ("2024", ["2024"]), ("2025-2026", ["2025", "2026"])]:
        pnl_no = sum(r['test_pnl'] for r in results_no_filter
                     if any(r['test_start'].startswith(y) for y in year_prefixes))
        pnl_with = sum(r['test_pnl'] for r in results_filter_086
                       if any(r['test_start'].startswith(y) for y in year_prefixes))
        n_win = sum(1 for r in results_no_filter
                    if any(r['test_start'].startswith(y) for y in year_prefixes))
        delta = pnl_with - pnl_no
        print(f"{year_label:<15} {n_win:<10} ${pnl_no:>+11,.0f} ${pnl_with:>+11,.0f} ${delta:>+11,.0f}")

    # --- Test de sensibilite ---
    print(f"\n\nTEST DE SENSIBILITE DU SEUIL")
    print(f"{'='*80}")

    s_084 = summarize(results_filter_084)
    s_088 = summarize(results_filter_088)

    header5 = f"{'Seuil':<15} {'PnL WF':>12} {'Trades':>8} {'Fen. +':>8} {'PF':>8} {'PnL/Trade':>12}"
    print(header5)
    print("-" * 80)

    for label, s in [("Sans filtre", s_no), ("0.84", s_084), ("0.86", s_086), ("0.88", s_088)]:
        pf_s = f"{s['pf']:.2f}" if s['pf'] < 100 else "inf"
        ppt = f"${s['pnl_per_trade']:+,.0f}" if s['trades'] > 0 else "N/A"
        print(f"{label:<15} ${s['pnl']:>+11,.0f} {s['trades']:>8} "
              f"{s['n_pos']:>3}/{s['n_windows']} {pf_s:>8} {ppt:>12}")

    # --- VERDICT ---
    print(f"\n\n{'='*110}")
    print("VERDICT PHASE C3")
    print(f"{'='*110}")

    pnl_gain = s_086['pnl'] >= s_no['pnl']
    pnl_80pct = s_086['pnl'] >= 0.8 * s_no['pnl']
    more_positive = s_086['n_pos'] > s_no['n_pos']
    half_positive = s_086['n_pos'] >= s_086['n_windows'] * 0.5
    toxic_ok = n_neutralized >= 4  # au moins 4/6 toxiques ameliorees

    # Stabilite seuils : les 3 seuils donnent des resultats coherents ?
    seuil_stable = (
        abs(s_084['pnl'] - s_086['pnl']) < 0.3 * max(abs(s_086['pnl']), 1) and
        abs(s_088['pnl'] - s_086['pnl']) < 0.3 * max(abs(s_086['pnl']), 1)
    )

    print(f"\n   PnL avec filtre >= sans filtre     : {'OUI' if pnl_gain else 'NON'} (${s_086['pnl']:+,.0f} vs ${s_no['pnl']:+,.0f})")
    print(f"   Fenetres positives >= 50%           : {'OUI' if half_positive else 'NON'} ({s_086['n_pos']}/{s_086['n_windows']})")
    print(f"   Fenetres toxiques neutralisees >= 4/6: {'OUI' if toxic_ok else 'NON'} ({n_neutralized}/6)")
    print(f"   Fenetres positives > sans filtre    : {'OUI' if more_positive else 'NON'} ({s_086['n_pos']} vs {s_no['n_pos']})")
    print(f"   Seuil stable (0.84/0.86/0.88)       : {'OUI' if seuil_stable else 'NON'}")

    if pnl_gain and half_positive and toxic_ok:
        print(f"\n   >>> VERDICT : **GO** -- Filtre valide en walk-forward hors echantillon")
    elif pnl_80pct and more_positive and n_neutralized >= 3:
        print(f"\n   >>> VERDICT : **GO CONDITIONNEL** -- Filtre ameliore la consistance")
    else:
        print(f"\n   >>> VERDICT : **NO-GO** -- Filtre non valide en walk-forward")

    print(f"{'='*110}")

    # --- Sauvegarder ---
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Resultats detailles
    rows = []
    for rn, rf in zip(results_no_filter, results_filter_086):
        rows.append({
            'window': rn['window'],
            'test_start': rn['test_start'],
            'test_end': rn['test_end'],
            'best_config_no_filter': rn['best_config'],
            'trades_no_filter': rn['test_trades'],
            'pnl_no_filter': rn['test_pnl'],
            'best_config_filter': rf['best_config'],
            'trades_filter': rf['test_trades'],
            'pnl_filter': rf['test_pnl'],
            'delta_pnl': rf['test_pnl'] - rn['test_pnl'],
        })

    df_detail = pd.DataFrame(rows)
    csv_detail = output_dir / "phase_c3_walk_forward_results.csv"
    df_detail.to_csv(csv_detail, sep=';', index=False)
    print(f"\nResultats detailles : {csv_detail}")

    # Comparaison globale
    comparison = {
        'metric': ['PnL_total', 'Trades', 'Fenetres_positives', 'PnL_per_trade', 'PF', 'MaxDD'],
        'sans_filtre': [s_no['pnl'], s_no['trades'], s_no['n_pos'], s_no['pnl_per_trade'], s_no['pf'], s_no['maxdd']],
        'avec_filtre_086': [s_086['pnl'], s_086['trades'], s_086['n_pos'], s_086['pnl_per_trade'], s_086['pf'], s_086['maxdd']],
    }
    df_comp = pd.DataFrame(comparison)
    csv_comp = output_dir / "phase_c3_comparison.csv"
    df_comp.to_csv(csv_comp, index=False)
    print(f"Comparaison globale : {csv_comp}")


if __name__ == '__main__':
    main()
