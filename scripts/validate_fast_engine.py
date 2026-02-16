#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_fast_engine.py - Validation de parite entre moteur actuel et fast engine.

Compare trade par trade sur 100+ configs variees.
Critere : 100% identique (nombre de trades, bar entree/sortie, PnL, exit reason).

Usage :
    python scripts/validate_fast_engine.py
"""

import sys
import os
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest, pack_config
from optimizer import apply_overrides_fast
from fast_grid_engine import (
    scan_entries, build_paths_and_thresholds,
    precompute_cooldown_reset, replay_state_machine,
    warmup_fast_engine,
    CFG_ZSCORE_RESET_LONG, CFG_ZSCORE_RESET_SHORT,
)


def load_data():
    """Charge les donnees 1-min, 5-min et 5s."""
    print("Chargement des donnees...")
    df_1min, config, _ = load_and_prepare_data()
    df_5min = resample_to_5min(df_1min)
    df_5s = load_5s_data(config)
    print(f"  1-min: {len(df_1min):,} barres")
    print(f"  5-min: {len(df_5min):,} barres")
    print(f"  5s: {len(df_5s):,} barres")
    return df_1min, df_5min, df_5s, config


def generate_test_configs():
    """Genere 100+ configs de test couvrant tous les edge cases."""
    configs = []

    # 6 groupes indicateurs — betas extremes (1980, 5280) + intermediaires
    indicator_groups = [
        # Beta court (1980) — plus de signaux, plus de trades
        {"indicators.beta_lookback": 1980, "indicators.zscore_period": 12,
         "indicators.correlation_period": 20, "indicators.adf_hurst_period": 26},
        {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
         "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26},
        # Intermediaire
        {"indicators.beta_lookback": 2640, "indicators.zscore_period": 24,
         "indicators.correlation_period": 20, "indicators.adf_hurst_period": 48},
        {"indicators.beta_lookback": 3960, "indicators.zscore_period": 30,
         "indicators.correlation_period": 24, "indicators.adf_hurst_period": 96},
        # Beta long (5280) — moins de signaux, indicateurs plus lisses
        {"indicators.beta_lookback": 5280, "indicators.zscore_period": 36,
         "indicators.correlation_period": 30, "indicators.adf_hurst_period": 144},
        {"indicators.beta_lookback": 5280, "indicators.zscore_period": 20,
         "indicators.correlation_period": 20, "indicators.adf_hurst_period": 64},
    ]

    # 50 exit combos — focus sur les edge cases demandes
    exit_combos = [
        # === PURE ZSCORE (pas de dollar exits) ===
        {"zE": 3.0, "zTP": 0.5, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_05"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_00_low"},
        {"zE": 3.5, "zTP": 1.0, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_10"},
        {"zE": 3.0, "zTP": -1.0, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_neg10"},
        {"zE": 3.0, "zTP": -1.5, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_neg15"},
        {"zE": 2.75, "zTP": 0.25, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "pure_z_025"},

        # === zSL SERRE — beaucoup de cooldowns ===
        # zSL tres proche de zE → quasi-systematique cooldown
        {"zE": 3.0, "zTP": 0.0, "zSL": 3.5, "dTP": 0, "dSL": 0, "tag": "zsl35_ze30"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.5, "dTP": 0, "dSL": 0, "tag": "zsl35_ze25"},
        {"zE": 3.0, "zTP": 0.5, "zSL": 3.5, "dTP": 0, "dSL": 0, "tag": "zsl35_tp05"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.0, "dTP": 0, "dSL": 0, "tag": "zsl30_ze25"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 4.0, "dTP": 0, "dSL": 0, "tag": "zsl40_ze30"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 4.0, "dTP": 0, "dSL": 0, "tag": "zsl40_ze25"},
        # zSL serre + dollar exits
        {"zE": 3.0, "zTP": 0.0, "zSL": 3.5, "dTP": 300, "dSL": -500, "tag": "zsl35_dollar"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.5, "dTP": 200, "dSL": -300, "tag": "zsl35_tight_d"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 3.5, "dTP": 150, "dSL": -300, "tag": "zsl35_dtp150"},

        # === dTP TRES PETITS — sorties rapides, beaucoup de re-entrees same-bar ===
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 150, "dSL": 0, "tag": "dtp150"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 99, "dTP": 150, "dSL": 0, "tag": "dtp150_ze25"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 200, "dSL": 0, "tag": "dtp200"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 99, "dTP": 200, "dSL": 0, "tag": "dtp200_ze25"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 250, "dSL": 0, "tag": "dtp250"},
        {"zE": 3.25, "zTP": 0.0, "zSL": 99, "dTP": 250, "dSL": 0, "tag": "dtp250_c6"},
        # dTP petit + dSL
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 150, "dSL": -300, "tag": "dtp150_dsl300"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 99, "dTP": 200, "dSL": -400, "tag": "dtp200_dsl400"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 250, "dSL": -500, "tag": "dtp250_dsl500"},
        # dTP petit + zSL serre (double stress)
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.5, "dTP": 150, "dSL": 0, "tag": "dtp150_zsl35"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 3.5, "dTP": 200, "dSL": -300, "tag": "dtp200_zsl35_d"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.0, "dTP": 150, "dSL": -300, "tag": "dtp150_zsl30_d"},

        # === dSL SERRE — beaucoup de dollar SL + cooldowns ===
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 0, "dSL": -300, "tag": "dsl300"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 99, "dTP": 0, "dSL": -300, "tag": "dsl300_ze25"},
        {"zE": 3.0, "zTP": 0.5, "zSL": 99, "dTP": 0, "dSL": -400, "tag": "dsl400_tp05"},
        {"zE": 2.75, "zTP": 1.0, "zSL": 99, "dTP": 0, "dSL": -300, "tag": "dsl300_tp10"},

        # === BOTH DOLLAR (stress combinatoire) ===
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 300, "dSL": -500, "tag": "d300_500"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 400, "dSL": -600, "tag": "d400_600"},
        {"zE": 3.0, "zTP": 0.0, "zSL": 99, "dTP": 500, "dSL": -1000, "tag": "d500_1000"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.5, "dTP": 250, "dSL": -300, "tag": "all_tight"},
        {"zE": 3.25, "zTP": 0.5, "zSL": 4.0, "dTP": 400, "dSL": -600, "tag": "all_medium"},

        # === zTP NEGATIF (attend que z depasse l'autre cote) ===
        {"zE": 3.5, "zTP": -1.0, "zSL": 5.0, "dTP": 0, "dSL": 0, "tag": "neg_tp10_zsl5"},
        {"zE": 3.0, "zTP": -0.5, "zSL": 99, "dTP": 0, "dSL": 0, "tag": "neg_tp05"},
        {"zE": 3.5, "zTP": -0.5, "zSL": 4.0, "dTP": 300, "dSL": -500, "tag": "neg_tp05_full"},
        {"zE": 3.0, "zTP": -1.5, "zSL": 4.0, "dTP": 250, "dSL": -400, "tag": "neg_tp15_d"},
        {"zE": 2.75, "zTP": -0.5, "zSL": 3.5, "dTP": 200, "dSL": -300, "tag": "neg_tp05_tight"},

        # === HIGH TRADE COUNT CONFIGS (zE bas + dTP petit) ===
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.5, "dTP": 150, "dSL": -300, "tag": "max_trades_1"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 3.0, "dTP": 200, "dSL": -400, "tag": "max_trades_2"},
        {"zE": 2.5, "zTP": 0.0, "zSL": 4.0, "dTP": 250, "dSL": -300, "tag": "max_trades_3"},

        # === WIDE DOLLAR (peu d'exits dollar, la plupart zscore/EOD) ===
        {"zE": 3.0, "zTP": 0.5, "zSL": 99, "dTP": 600, "dSL": -1000, "tag": "wide_d1"},
        {"zE": 3.5, "zTP": 0.0, "zSL": 99, "dTP": 500, "dSL": -800, "tag": "wide_d2"},

        # === C6-LIKE CONFIGS ===
        {"zE": 3.25, "zTP": 0.0, "zSL": 99, "dTP": 250, "dSL": 0, "tag": "c6_exact"},
        {"zE": 3.25, "zTP": 0.0, "zSL": 99, "dTP": 300, "dSL": 0, "tag": "c6_dtp300"},
        {"zE": 3.25, "zTP": 0.25, "zSL": 99, "dTP": 250, "dSL": -500, "tag": "c6_plus_dsl"},
        {"zE": 3.5, "zTP": 0.0, "zSL": 99, "dTP": 250, "dSL": 0, "tag": "c6_ze35"},
    ]

    # Combiner groupes x exits = 6 x 50 = 300 configs
    for ig in indicator_groups:
        for ec in exit_combos:
            configs.append({**ig, **ec})

    print(f"  {len(configs)} configs de test generees")
    return configs


def run_reference_engine(df_5min, df_5s, base_config, test_config):
    """Lance le moteur actuel (reference) pour une config."""
    # Construire la config complete
    overrides = {
        "contracts.mode": "micro",
        "exit.zscore_tp_enabled": True,
        "costs.slippage_gc_ticks": 2,
        "costs.slippage_si_ticks": 2,
        "session.session_end_time": "14:55",
        "session.entry_start_hour": 18,
        "session.entry_end_hour": 14,
        "session.flat_end_of_session": True,
        # Entry
        "entry.zscore_long": -abs(test_config["zE"]),
        "entry.zscore_short": abs(test_config["zE"]),
        "entry.cointegration_score_min": 40,
        # Exits zscore
        "exit.zscore_tp_long": -test_config["zTP"],
        "exit.zscore_tp_short": test_config["zTP"],
        "exit.zscore_sl_long": -abs(test_config["zSL"]),
        "exit.zscore_sl_short": abs(test_config["zSL"]),
        # Exits dollar
        "exit.pnl_take_profit": test_config["dTP"] if test_config["dTP"] > 0 else 99999,
        "exit.pnl_stop_loss": test_config["dSL"] if test_config["dSL"] < 0 else -99999,
        "exit.max_holding_bars": 0,
        "sizing.micro_multiplier_max": 2,
        # Indicateurs
        "indicators.beta_lookback": test_config["indicators.beta_lookback"],
        "indicators.zscore_period": test_config["indicators.zscore_period"],
        "indicators.correlation_period": test_config["indicators.correlation_period"],
        "indicators.adf_hurst_period": test_config["indicators.adf_hurst_period"],
    }
    config_test = apply_overrides_fast(base_config, overrides)

    # Calculer indicateurs
    df_ind = calculate_all_indicators(df_5min.copy(), config_test, verbose=False)

    # Lancer backtest
    trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
    return trades, df_ind, config_test


def run_fast_engine(df_ind, df_5s, config_test, test_config):
    """Lance le fast engine pour une config."""
    cfg = pack_config(config_test)

    # Extraire les arrays numpy
    zscores = df_ind['ZScore'].values.astype(np.float64)
    correlations = df_ind['Correlation'].values.astype(np.float64)
    coint_scores = df_ind['Cointegration_Score'].values.astype(np.float64)
    hursts = df_ind['Hurst'].values.astype(np.float64) if 'Hurst' in df_ind.columns else np.full(len(df_ind), np.nan)
    gc_prices = df_ind['Last_GC'].values.astype(np.float64)
    si_prices = df_ind['Last_SI'].values.astype(np.float64)
    betas = df_ind['Beta'].values.astype(np.float64)
    hours = pd.to_datetime(df_ind['DateTime']).dt.hour.values.astype(np.int32)
    minutes = pd.to_datetime(df_ind['DateTime']).dt.minute.values.astype(np.int32)
    timestamps_ns = pd.to_datetime(df_ind['DateTime']).values.astype(np.int64)

    # 5s arrays
    dt_5s_ns = pd.to_datetime(df_5s['DateTime']).values.astype(np.int64)
    gc_5s = df_5s['Last_GC'].values.astype(np.float64)
    si_5s = df_5s['Last_SI'].values.astype(np.float64)

    # Regime filter (desactive)
    hl_ar1 = np.empty(0, dtype=np.float64)
    corr_daily = np.empty(0, dtype=np.float64)

    # Valeurs de seuils pour ce test (une seule valeur chaque)
    ztp_values = np.array([test_config["zTP"]], dtype=np.float64)
    zsl_values = np.array([test_config["zSL"]], dtype=np.float64)
    dtp_raw = test_config["dTP"]
    dsl_raw = test_config["dSL"]
    dtp_values = np.array([dtp_raw if dtp_raw > 0 else 99999.0], dtype=np.float64)
    dsl_values = np.array([dsl_raw if dsl_raw < 0 else -99999.0], dtype=np.float64)

    # 1. Scan entries
    entries = scan_entries(
        zscores, correlations, coint_scores, hursts,
        gc_prices, si_prices, betas,
        hours, minutes, hl_ar1, corr_daily, cfg,
    )

    if entries.shape[0] == 0:
        return pd.DataFrame()

    # 2. Build paths and thresholds
    table = build_paths_and_thresholds(
        entries, zscores, gc_prices, si_prices,
        hours, minutes, timestamps_ns,
        dt_5s_ns, gc_5s, si_5s, cfg,
        ztp_values, zsl_values, dtp_values, dsl_values,
    )

    # 3. Cooldown reset
    first_z_ge, first_z_le = precompute_cooldown_reset(
        zscores, cfg[CFG_ZSCORE_RESET_LONG], cfg[CFG_ZSCORE_RESET_SHORT]
    )

    # 4. Replay
    n_ztp = len(ztp_values)
    n_zsl = len(zsl_values)
    n_dtp = len(dtp_values)
    n_dsl = len(dsl_values)
    off_zsl = n_ztp
    off_dtp = n_ztp + n_zsl
    off_dsl = off_dtp + n_dtp
    off_eod = off_dsl + n_dsl

    has_dtp = dtp_raw > 0
    has_dsl = dsl_raw < 0

    results, n_trades = replay_state_machine(
        entries, table, zscores, gc_prices, si_prices,
        first_z_ge, first_z_le,
        0,        # ztp_idx
        off_zsl,  # zsl_idx
        off_dtp if has_dtp else -1,  # dtp_idx
        off_dsl if has_dsl else -1,  # dsl_idx
        off_eod,  # eod_idx
        has_dtp, has_dsl, True,  # has_eod
        0,  # max_hold_bars
        cfg,
    )

    if n_trades == 0:
        return pd.DataFrame()

    # Convertir en DataFrame (meme format que run_hybrid_backtest)
    reason_map = {0: 'TP_ZSCORE', 1: 'SL_ZSCORE', 2: 'TP_DOLLAR',
                  3: 'SL_DOLLAR', 4: 'STILL_OPEN', 5: 'FLAT_EOD', 6: 'MAX_HOLD'}

    trades_data = []
    for i in range(n_trades):
        r = results[i]
        trades_data.append({
            'Trade_No': int(r[0]),
            'Direction': int(r[1]),
            'Entry_Idx': int(r[2]),
            'Exit_Idx': int(r[3]),
            'Entry_GC': r[4],
            'Entry_SI': r[5],
            'Exit_GC': r[6],
            'Exit_SI': r[7],
            'GC_Contracts': int(r[8]),
            'SI_Contracts': int(r[9]),
            'PnL_Gross': r[10],
            'Costs': r[11],
            'PnL_Net': r[12],
            'Exit_Reason': reason_map.get(int(r[13]), f'UNKNOWN_{int(r[13])}'),
            'Max_PnL_Intra': r[14],
            'Min_PnL_Intra': r[15],
        })

    return pd.DataFrame(trades_data)


def compare_trades(ref_trades, fast_trades, config_tag):
    """Compare deux DataFrames de trades. Retourne (ok, message)."""
    if len(ref_trades) == 0 and len(fast_trades) == 0:
        return True, "0 trades (both)"

    if len(ref_trades) != len(fast_trades):
        return False, f"Trade count: ref={len(ref_trades)} fast={len(fast_trades)}"

    n = len(ref_trades)
    errors = []

    for i in range(n):
        r = ref_trades.iloc[i]
        f = fast_trades.iloc[i]

        # Comparer les champs critiques
        ref_dir = 1 if r['Direction'] == 'LONG' else (-1 if r['Direction'] == 'SHORT' else int(r['Direction']))
        fast_dir = int(f['Direction'])
        if ref_dir != fast_dir:
            errors.append(f"  Trade {i+1}: Direction ref={r['Direction']} fast={fast_dir}")

        # Entry bar (utiliser Entry_DateTime → convertir en index)
        # Le ref a Entry_DateTime, le fast a Entry_Idx
        # On compare Entry_Idx si disponible
        if 'Entry_Idx' in r.index and 'Entry_Idx' in f.index:
            if int(r.get('Entry_Idx', -1)) != int(f['Entry_Idx']):
                errors.append(f"  Trade {i+1}: Entry_Idx ref={r.get('Entry_Idx')} fast={f['Entry_Idx']}")

        # PnL Net (comparer directement, pas recalcule)
        pnl_diff = abs(r['PnL_Net'] - f['PnL_Net'])
        if pnl_diff > 0.01:
            errors.append(f"  Trade {i+1}: PnL_Net ref={r['PnL_Net']:.2f} fast={f['PnL_Net']:.2f} (diff={pnl_diff:.2f})")

        # Exit reason
        ref_reason = r['Exit_Reason']
        fast_reason = f['Exit_Reason']
        if ref_reason != fast_reason:
            errors.append(f"  Trade {i+1}: Exit_Reason ref={ref_reason} fast={fast_reason}")

        # Prix d'entree
        if abs(r['Entry_GC'] - f['Entry_GC']) > 0.001:
            errors.append(f"  Trade {i+1}: Entry_GC ref={r['Entry_GC']:.2f} fast={f['Entry_GC']:.2f}")
        if abs(r['Entry_SI'] - f['Entry_SI']) > 0.001:
            errors.append(f"  Trade {i+1}: Entry_SI ref={r['Entry_SI']:.4f} fast={f['Entry_SI']:.4f}")

        if len(errors) >= 10:
            errors.append("  ... (tronque a 10 erreurs)")
            break

    if errors:
        return False, f"{len(errors)} divergences sur {n} trades:\n" + "\n".join(errors)
    return True, f"{n} trades OK"


def main():
    t0 = time.time()

    # Charger les donnees
    df_1min, df_5min, df_5s, base_config = load_data()

    # Warmup Numba
    print("\nWarmup Numba (fast engine)...")
    warmup_fast_engine()

    # Generer les configs
    print("\nGeneration des configs de test...")
    test_configs = generate_test_configs()

    # Lancer les tests
    print(f"\nValidation de parite sur {len(test_configs)} configs...")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0
    failures = []
    total_trades = 0
    max_trades_config = ("", 0)

    for idx, tc in enumerate(test_configs):
        tag = tc.get("tag", "unknown")
        ig_key = (tc["indicators.beta_lookback"], tc["indicators.zscore_period"],
                  tc["indicators.correlation_period"], tc["indicators.adf_hurst_period"])

        try:
            # Reference engine
            ref_trades, df_ind, config_test = run_reference_engine(
                df_5min, df_5s, base_config, tc
            )

            # Fast engine
            fast_trades = run_fast_engine(df_ind, df_5s, config_test, tc)

            # Comparer
            ok, msg = compare_trades(ref_trades, fast_trades, tag)
            n_ref = len(ref_trades)
            total_trades += n_ref

            if n_ref > max_trades_config[1]:
                max_trades_config = (f"{tag} ig={ig_key}", n_ref)

            if ok:
                passed += 1
                status = "PASS"
            else:
                failed += 1
                status = "FAIL"
                failures.append((tag, ig_key, msg))

            # Afficher : toujours les FAIL, sinon tous les 25
            if not ok or (idx + 1) % 25 == 0:
                print(f"  [{idx+1:>3}/{len(test_configs)}] {status} {tag:<30s} "
                      f"ref={n_ref:>4} trades | {msg[:50]}")

        except Exception as ex:
            skipped += 1
            print(f"  [{idx+1:>3}/{len(test_configs)}] SKIP {tag:<30s} | ERROR: {str(ex)[:60]}")

    # Rapport final
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"RESULTATS : {passed} PASS / {failed} FAIL / {skipped} SKIP")
    print(f"Total trades valides : {total_trades:,}")
    print(f"Config max trades : {max_trades_config[0]} ({max_trades_config[1]} trades)")
    print(f"Temps total : {elapsed:.1f}s")

    if failures:
        print(f"\n{'='*70}")
        print("DETAILS DES ECHECS :")
        for tag, ig_key, msg in failures:
            print(f"\n  [{tag}] ig={ig_key}")
            print(f"  {msg}")

    if failed == 0 and skipped == 0:
        print("\n*** VALIDATION REUSSIE : 100% parite ***")
        return 0
    elif failed > 0:
        print(f"\n*** ECHEC : {failed} configs divergent ***")
        return 1
    else:
        print(f"\n*** ATTENTION : {skipped} configs en erreur ***")
        return 2


if __name__ == "__main__":
    sys.exit(main())
