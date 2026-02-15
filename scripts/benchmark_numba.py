#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benchmark de parite : backtest_engine_hybrid.py vs backtest_engine_numba.py

Compare les resultats (nombre de trades, PnL, exit reasons) et les performances.
Les nouvelles features (flat_end_of_session, max_holding_bars) sont desactivees
pour garantir la parite.

Usage :
    python scripts/benchmark_numba.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators


def main():
    print("=" * 80)
    print("BENCHMARK : backtest_engine_hybrid vs backtest_engine_numba")
    print("=" * 80)

    # ---- 1. Charger les donnees ----
    print("\n[1/6] Chargement des donnees...")
    t0 = time.perf_counter()
    df_1min, config, stats = load_and_prepare_data(verbose=False)

    indicator_period = config.get("indicators", {}).get("period", "1min")
    if indicator_period == "5min":
        df_bars = resample_to_5min(df_1min, verbose=False)
    else:
        df_bars = df_1min

    df_bars = calculate_all_indicators(df_bars, config, verbose=False)
    df_5s = load_5s_data(config, verbose=False)
    dt_load = time.perf_counter() - t0
    print(f"   {len(df_bars):,} barres {indicator_period}, {len(df_5s):,} barres 5s ({dt_load:.1f}s)")

    # ---- 2. Desactiver les nouvelles features pour parite ----
    config["exit"]["flat_end_of_session"] = False
    config["exit"]["max_holding_bars"] = 0
    config["sizing"]["micro_multiplier_max"] = 0
    # S'assurer que session.flat_end_of_session est aussi off
    config["session"]["flat_end_of_session"] = False
    print("[2/6] Nouvelles features desactivees (flat_eod=off, max_hold=0, micro_mult=0)")

    # ---- 3. Importer les deux engines ----
    from backtest_engine_hybrid import run_hybrid_backtest as run_original
    from backtest_engine_numba import run_hybrid_backtest as run_numba, warmup_numba

    # ---- 4. Warmup Numba (hors chrono) ----
    print("[3/6] Warmup Numba (pre-compilation JIT)...")
    t0 = time.perf_counter()
    warmup_numba()
    dt_warmup = time.perf_counter() - t0
    print(f"   Warmup: {dt_warmup:.1f}s")

    # ---- 5. Benchmark timing ----
    N_RUNS = 3

    print(f"\n[4/6] Benchmark timing ({N_RUNS} runs chacun)...")
    print("\n   --- ORIGINAL (Python) ---")
    times_orig = []
    trades_orig = None
    for r in range(N_RUNS):
        t0 = time.perf_counter()
        trades_orig = run_original(df_bars, df_5s, config, verbose=False)
        dt = time.perf_counter() - t0
        times_orig.append(dt)
        print(f"   Run {r+1}: {dt:.3f}s ({len(trades_orig)} trades)")

    print("\n   --- NUMBA (JIT) ---")
    times_numba = []
    trades_numba = None
    for r in range(N_RUNS):
        t0 = time.perf_counter()
        trades_numba = run_numba(df_bars, df_5s, config, verbose=False)
        dt = time.perf_counter() - t0
        times_numba.append(dt)
        print(f"   Run {r+1}: {dt:.3f}s ({len(trades_numba)} trades)")

    avg_orig = np.mean(times_orig)
    avg_numba = np.mean(times_numba)
    speedup = avg_orig / avg_numba if avg_numba > 0 else float("inf")

    print(f"\n   Moyenne Original : {avg_orig:.3f}s")
    print(f"   Moyenne Numba    : {avg_numba:.3f}s")
    print(f"   Speedup          : {speedup:.1f}x")

    # ---- 6. Comparaison de parite ----
    print(f"\n[5/6] Comparaison de parite...")

    parity_ok = True
    issues = []

    # 6a. Nombre de trades
    n_orig = len(trades_orig)
    n_numba = len(trades_numba)
    if n_orig != n_numba:
        parity_ok = False
        issues.append(f"Nombre de trades: Original={n_orig}, Numba={n_numba}")
        print(f"   [FAIL] Trades: {n_orig} vs {n_numba}")
    else:
        print(f"   [OK] Trades: {n_orig} == {n_numba}")

    # 6b. PnL total
    pnl_orig = trades_orig["PnL_Net"].sum() if n_orig > 0 else 0
    pnl_numba = trades_numba["PnL_Net"].sum() if n_numba > 0 else 0
    pnl_diff = abs(pnl_orig - pnl_numba)
    if pnl_diff > 1.0:
        parity_ok = False
        issues.append(f"PnL total diff: ${pnl_diff:.2f} (Original=${pnl_orig:.2f}, Numba=${pnl_numba:.2f})")
        print(f"   [FAIL] PnL total: ${pnl_orig:,.2f} vs ${pnl_numba:,.2f} (diff=${pnl_diff:.2f})")
    else:
        print(f"   [OK] PnL total: ${pnl_orig:,.2f} vs ${pnl_numba:,.2f} (diff=${pnl_diff:.2f})")

    # 6c. Comparaison trade par trade
    n_compare = min(n_orig, n_numba)
    first_divergence = None
    trade_diffs = 0

    for t in range(n_compare):
        orig = trades_orig.iloc[t]
        numb = trades_numba.iloc[t]

        # Direction
        if orig["Direction"] != numb["Direction"]:
            trade_diffs += 1
            if first_divergence is None:
                first_divergence = (t, "Direction", orig["Direction"], numb["Direction"])
            continue

        # Exit Reason
        if orig["Exit_Reason"] != numb["Exit_Reason"]:
            trade_diffs += 1
            if first_divergence is None:
                first_divergence = (t, "Exit_Reason", orig["Exit_Reason"], numb["Exit_Reason"])
            continue

        # PnL par trade
        pnl_diff_t = abs(orig["PnL_Net"] - numb["PnL_Net"])
        if pnl_diff_t > 0.50:
            trade_diffs += 1
            if first_divergence is None:
                first_divergence = (t, "PnL_Net", f"${orig['PnL_Net']:.2f}", f"${numb['PnL_Net']:.2f}")

    if trade_diffs > 0:
        parity_ok = False
        issues.append(f"{trade_diffs} trades divergent sur {n_compare}")
        print(f"   [FAIL] {trade_diffs}/{n_compare} trades divergent")
        if first_divergence:
            idx, field, val_o, val_n = first_divergence
            print(f"          Premier divergence: trade #{idx+1}, {field}: {val_o} vs {val_n}")
            # Afficher les details du trade divergent
            print(f"\n          --- Trade #{idx+1} ORIGINAL ---")
            for col in ["Direction", "Entry_DateTime", "Exit_DateTime", "Exit_Reason",
                        "Entry_GC", "Entry_SI", "Exit_GC", "Exit_SI",
                        "GC_Contracts", "SI_Contracts", "PnL_Gross", "Costs", "PnL_Net",
                        "Entry_ZScore", "Exit_ZScore", "Beta"]:
                if col in trades_orig.columns:
                    print(f"          {col:20s}: {trades_orig.iloc[idx][col]}")
            print(f"\n          --- Trade #{idx+1} NUMBA ---")
            for col in ["Direction", "Entry_DateTime", "Exit_DateTime", "Exit_Reason",
                        "Entry_GC", "Entry_SI", "Exit_GC", "Exit_SI",
                        "GC_Contracts", "SI_Contracts", "PnL_Gross", "Costs", "PnL_Net",
                        "Entry_ZScore", "Exit_ZScore", "Beta"]:
                if col in trades_numba.columns:
                    print(f"          {col:20s}: {trades_numba.iloc[idx][col]}")
    else:
        print(f"   [OK] {n_compare}/{n_compare} trades identiques (Direction, Exit_Reason, PnL<$0.50)")

    # ---- 7. Verdict ----
    print(f"\n[6/6] VERDICT")
    print("=" * 80)

    if parity_ok and speedup > 2.0:
        print(f"   NUMBA VALIDE -- Speedup: {speedup:.1f}x -- Integration recommandee")
        # Extrapolation grid search
        configs_252k = 252_000
        workers = 24
        time_per_config_numba = avg_numba
        time_per_config_orig = avg_orig
        wall_orig = (configs_252k * time_per_config_orig) / workers / 3600
        wall_numba = (configs_252k * time_per_config_numba) / workers / 3600
        print(f"\n   Extrapolation grid search 252K configs (24 workers):")
        print(f"   Original : {wall_orig:.1f}h")
        print(f"   Numba    : {wall_numba:.1f}h")
        print(f"   Gain     : {wall_orig - wall_numba:.1f}h economisees")
        return 0
    else:
        print(f"   NUMBA REJETE")
        if not parity_ok:
            print(f"   Raisons de non-parite:")
            for issue in issues:
                print(f"     - {issue}")
        if speedup <= 2.0:
            print(f"   Speedup insuffisant: {speedup:.1f}x (minimum 2x requis)")
        print(f"\n   NE PAS passer aux phases suivantes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
