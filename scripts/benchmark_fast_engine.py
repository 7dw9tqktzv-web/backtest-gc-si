#!/usr/bin/env python
"""
Benchmark : Fast Grid Engine vs Reference Engine (moteur standard).

Compare le temps d'execution sur 1 groupe indicateur avec N variantes entry/exit.
Les deux moteurs doivent produire des resultats identiques (valide par validate_fast_engine.py).

Usage:
    python scripts/benchmark_fast_engine.py [--n-variants 500]
"""

import sys
import time
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import (
    run_hybrid_backtest, pack_config, warmup_numba,
    CFG_ZSCORE_RESET_LONG, CFG_ZSCORE_RESET_SHORT,
)
from optimizer import apply_overrides_fast, compute_metrics
from fast_grid_engine import (
    scan_entries, build_paths_and_thresholds,
    precompute_cooldown_reset, replay_state_machine,
    warmup_fast_engine, ES_BAR_IDX,
)
from grid_search_runner import (
    create_micro_full_entry_exit_generator,
    create_micro_full_label_builder,
    create_micro_full_result_builder,
)


def benchmark(n_variants: int = 500):
    """Lance le benchmark sur 1 groupe indicateur."""

    # --- Donnees ---
    print("Chargement des donnees...")
    t0 = time.time()
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_5min):,} barres 5-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # --- Warmup Numba ---
    print("Warmup Numba...")
    warmup_numba()
    warmup_fast_engine()

    # --- Indicateurs (1 groupe) ---
    ind_ov = {
        "indicators.beta_lookback": 3960,
        "indicators.zscore_period": 20,
        "indicators.correlation_period": 30,
        "indicators.adf_hurst_period": 26,
    }
    fixed_overrides = {
        "contracts.mode": "micro",
        "exit.zscore_tp_enabled": True,
        "costs.slippage_gc_ticks": 2,
        "costs.slippage_si_ticks": 2,
        "session.session_end_time": "14:55",
        "session.entry_start_hour": 18,
        "session.entry_end_hour": 14,
    }

    config_ind = apply_overrides_fast(base_config, {**ind_ov, **fixed_overrides})
    print("Calcul indicateurs...")
    df_ind = calculate_all_indicators(df_5min, config_ind, verbose=False)

    # --- Generer les variantes entry/exit ---
    ee_gen = create_micro_full_entry_exit_generator(
        zscore_entry=[2.5, 2.75, 3.0, 3.25, 3.5, 3.75],
        cointegration_min=[20, 30, 40, 50, 60],
        zscore_tp=[-1.5, -1.0, -0.5, 0.0, 0.25, 0.5, 0.75, 1.0],
        zscore_sl=[3.5, 4.0, 5.0, 99],
        dollar_tp=[0, 250, 300, 350, 400, 450, 500, 600],
        dollar_sl=[0, -300, -400, -500, -600, -800, -1000],
        flat_end_of_session=[True],
        max_holding_bars=[0],
        micro_multiplier_max=[2],
    )
    all_variants = ee_gen()
    # Limiter au nombre demande
    variants = all_variants[:n_variants]
    print(f"Variantes : {len(variants)} (sur {len(all_variants)} total)")

    label_builder = create_micro_full_label_builder()
    result_builder = create_micro_full_result_builder()
    group_prefix = "b3960_zp20_cp30_adf26"

    # ====================================================================
    # BENCHMARK REFERENCE ENGINE
    # ====================================================================
    print(f"\n{'='*80}")
    print(f"REFERENCE ENGINE : {len(variants)} configs...")
    print(f"{'='*80}")

    t_ref_start = time.time()
    ref_results = []
    for i, ee in enumerate(variants):
        merged = {**ind_ov, **ee["overrides"], **fixed_overrides}
        config_test = apply_overrides_fast(base_config, merged)
        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)
        ref_results.append({"pnl_net": m["pnl_net"], "trades": m["trades"]})
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t_ref_start
            rate = (i + 1) / elapsed
            print(f"   [{i+1:>4}/{len(variants)}] {elapsed:.1f}s ({rate:.1f} configs/s)")

    t_ref = time.time() - t_ref_start
    print(f"   REFERENCE : {t_ref:.2f}s ({len(variants)/t_ref:.1f} configs/s)")

    # ====================================================================
    # BENCHMARK FAST ENGINE
    # ====================================================================
    print(f"\n{'='*80}")
    print(f"FAST ENGINE : {len(variants)} configs...")
    print(f"{'='*80}")

    # Preparer les arrays numpy
    zscores = df_ind['ZScore'].values.astype(np.float64)
    correlations = df_ind['Correlation'].values.astype(np.float64)
    coint_scores = df_ind['Cointegration_Score'].values.astype(np.float64)
    hursts = (df_ind['Hurst'].values.astype(np.float64)
              if 'Hurst' in df_ind.columns else np.full(len(df_ind), np.nan))
    gc_prices = df_ind['Last_GC'].values.astype(np.float64)
    si_prices = df_ind['Last_SI'].values.astype(np.float64)
    betas = df_ind['Beta'].values.astype(np.float64)
    ts_dt = pd.to_datetime(df_ind['DateTime'])
    hours = ts_dt.dt.hour.values.astype(np.int32)
    minutes = ts_dt.dt.minute.values.astype(np.int32)
    timestamps_ns = ts_dt.values.astype(np.int64)
    dt_5s_ns = pd.to_datetime(df_5s['DateTime']).values.astype(np.int64)
    gc_5s = df_5s['Last_GC'].values.astype(np.float64)
    si_5s = df_5s['Last_SI'].values.astype(np.float64)

    hl_ar1 = np.empty(0, dtype=np.float64)
    corr_daily = np.empty(0, dtype=np.float64)

    # Collecter les seuils uniques
    all_ztp = sorted(set(ee["zTP"] for ee in variants))
    all_zsl = sorted(set(ee["zSL"] for ee in variants))
    all_dtp_raw = sorted(set(ee["dTP"] for ee in variants))
    all_dsl_raw = sorted(set(ee["dSL"] for ee in variants))
    all_dtp = [d if d > 0 else 99999 for d in all_dtp_raw]
    all_dsl = [d if d < 0 else -99999 for d in all_dsl_raw]

    ztp_values = np.array(all_ztp, dtype=np.float64)
    zsl_values = np.array(all_zsl, dtype=np.float64)
    dtp_values = np.array(all_dtp, dtype=np.float64)
    dsl_values = np.array(all_dsl, dtype=np.float64)

    n_ztp = len(ztp_values)
    n_zsl = len(zsl_values)
    n_dtp = len(dtp_values)
    off_zsl = n_ztp
    off_dtp = off_zsl + n_zsl
    off_dsl = off_dtp + n_dtp
    off_eod = off_dsl + len(dsl_values)

    ztp_idx_map = {v: i for i, v in enumerate(all_ztp)}
    zsl_idx_map = {v: i for i, v in enumerate(all_zsl)}
    dtp_idx_map = {v: i + off_dtp for i, v in enumerate(all_dtp)}
    dsl_idx_map = {v: i + off_dsl for i, v in enumerate(all_dsl)}

    # Grouper par (zE, co, mm)
    from collections import defaultdict
    groups = defaultdict(list)
    for ee in variants:
        key = (ee["zE"], ee["co"], ee["mm"])
        groups[key].append(ee)

    t_fast_start = time.time()
    fast_results = []
    n_scans = 0

    for (zE, co, mm), group_variants in groups.items():
        first_ee = group_variants[0]
        merged = {**ind_ov, **first_ee["overrides"], **fixed_overrides}
        config_test = apply_overrides_fast(base_config, merged)
        cfg = pack_config(config_test)

        # 1. Scan entries (1 fois par groupe)
        entries = scan_entries(
            zscores, correlations, coint_scores, hursts,
            gc_prices, si_prices, betas,
            hours, minutes, hl_ar1, corr_daily, cfg,
        )
        n_scans += 1

        if entries.shape[0] == 0:
            for ee in group_variants:
                fast_results.append({"pnl_net": 0.0, "trades": 0})
            continue

        # 2. Build thresholds (1 fois par groupe)
        table = build_paths_and_thresholds(
            entries, zscores, gc_prices, si_prices,
            hours, minutes, timestamps_ns,
            dt_5s_ns, gc_5s, si_5s, cfg,
            ztp_values, zsl_values, dtp_values, dsl_values,
        )

        # 3. Precompute cooldown
        first_z_ge, first_z_le = precompute_cooldown_reset(
            zscores, cfg[CFG_ZSCORE_RESET_LONG], cfg[CFG_ZSCORE_RESET_SHORT])

        # 4. Replay pour chaque variant
        for ee in group_variants:
            ztp_idx = ztp_idx_map[ee["zTP"]]
            zsl_idx = off_zsl + zsl_idx_map[ee["zSL"]]
            dtp_raw = ee["dTP"]
            dsl_raw = ee["dSL"]
            has_dtp = dtp_raw > 0
            has_dsl = dsl_raw < 0
            dtp_mapped = dtp_raw if dtp_raw > 0 else 99999
            dsl_mapped = dsl_raw if dsl_raw < 0 else -99999
            dtp_idx = dtp_idx_map[dtp_mapped] if has_dtp else -1
            dsl_idx = dsl_idx_map[dsl_mapped] if has_dsl else -1
            has_eod = ee["feos"]
            max_hold = ee["mhb"]

            results, n_trades = replay_state_machine(
                entries, table, zscores, gc_prices, si_prices,
                first_z_ge, first_z_le,
                ztp_idx, zsl_idx, dtp_idx, dsl_idx, off_eod,
                has_dtp, has_dsl, has_eod, max_hold, cfg,
            )

            if n_trades > 0:
                pnl_sum = float(sum(results[i, 12] for i in range(n_trades)))
            else:
                pnl_sum = 0.0
            fast_results.append({"pnl_net": pnl_sum, "trades": n_trades})

    t_fast = time.time() - t_fast_start

    print(f"   FAST : {t_fast:.2f}s ({len(variants)/t_fast:.1f} configs/s)")
    print(f"   Scans 5s : {n_scans} (au lieu de {len(variants)})")

    # ====================================================================
    # COMPARAISON
    # ====================================================================
    print(f"\n{'='*80}")
    print("RESULTATS")
    print(f"{'='*80}")

    # Verifier la parite
    mismatches = 0
    for i in range(len(variants)):
        if abs(ref_results[i]["pnl_net"] - fast_results[i]["pnl_net"]) > 0.01:
            mismatches += 1
        if ref_results[i]["trades"] != fast_results[i]["trades"]:
            mismatches += 1

    speedup = t_ref / t_fast if t_fast > 0 else float('inf')

    print(f"Reference : {t_ref:.2f}s ({len(variants)/t_ref:.1f} configs/s)")
    print(f"Fast      : {t_fast:.2f}s ({len(variants)/t_fast:.1f} configs/s)")
    print(f"Speedup   : {speedup:.1f}x")
    print(f"Parite    : {'OK' if mismatches == 0 else f'FAIL ({mismatches} mismatches)'}")
    print(f"Configs   : {len(variants)}")
    print(f"Scans 5s  : {n_scans} vs {len(variants)} (facteur {len(variants)/n_scans:.0f}x)")

    # Estimation pour le grid search complet
    n_total_configs = 20_160_000
    n_total_groups = 450
    # Temps par config
    t_per_config_ref = t_ref / len(variants)
    t_per_config_fast = t_fast / len(variants)
    # Estimation naive (monothread)
    est_ref_h = n_total_configs * t_per_config_ref / 3600
    est_fast_h = n_total_configs * t_per_config_fast / 3600
    # Avec 24 workers
    est_ref_h_24 = est_ref_h / 24
    est_fast_h_24 = est_fast_h / 24

    print(f"\nEstimation pour R1 corrected ({n_total_configs/1e6:.0f}M configs) :")
    print(f"   Reference : ~{est_ref_h_24:.0f}h (24 workers)")
    print(f"   Fast      : ~{est_fast_h_24:.0f}h (24 workers)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Fast Grid Engine")
    parser.add_argument("--n-variants", type=int, default=500,
                        help="Nombre de variantes entry/exit a tester")
    args = parser.parse_args()
    benchmark(args.n_variants)
