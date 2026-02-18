"""
Phase 2 - Monte Carlo sur 3 configs survivantes Phase 1.

1000 resamplings avec replacement sur les trades OOS concatenes.
Elimination : PnL P5 < $0 ou DD P95 < -$3,000.

Usage:
    python scripts/run_wf_phase2_mc.py
"""
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics
from walk_forward_runner import slice_data, slice_5s
from datetime import date


# ============================================================================
# 3 CONFIGS SURVIVANTES
# ============================================================================
CONFIGS = [
    {
        "label": "C03_b7920_zE3.45_dTP175_mhb18_es22",
        "overrides": {
            "indicators.beta_lookback": 7920, "indicators.zscore_period": 26,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 48,
            "entry.zscore_entry": 3.45, "entry.cointegration_min": 20,
            "exit.zscore_tp": -1.0, "exit.zscore_sl": 99,
            "exit.dollar_tp": 175, "exit.dollar_sl": -500,
            "exit.max_holding_bars": 18, "session.entry_start_hour": 22,
        },
    },
    {
        "label": "C05_b4620_zE3.6_dTP250_mhb18_es22",
        "overrides": {
            "indicators.beta_lookback": 4620, "indicators.zscore_period": 28,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 64,
            "entry.zscore_entry": 3.6, "entry.cointegration_min": 20,
            "exit.zscore_tp": -0.5, "exit.zscore_sl": 99,
            "exit.dollar_tp": 250, "exit.dollar_sl": -500,
            "exit.max_holding_bars": 18, "session.entry_start_hour": 22,
        },
    },
    {
        "label": "C09_b2640_zE3.4_dTP200_nohold_es0",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 28,
            "indicators.correlation_period": 12, "indicators.adf_hurst_period": 64,
            "entry.zscore_entry": 3.4, "entry.cointegration_min": 20,
            "exit.zscore_tp": -0.5, "exit.zscore_sl": 99,
            "exit.dollar_tp": 200, "exit.dollar_sl": -500,
            "exit.max_holding_bars": 0, "session.entry_start_hour": 0,
        },
    },
]

FIXED = {
    "contracts.mode": "micro",
    "indicators.period": "5min",
    "exit.zscore_tp_enabled": True,
    "session.flat_end_of_session": True,
    "session.entry_end_hour": 14,
    "session.session_end_time": "14:55",
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
    "sizing.micro_multiplier_max": 2,
}

WINDOW_BOUNDARIES = [
    date(2023, 1, 26),
    date(2023, 7, 26),
    date(2024, 1, 26),
    date(2024, 7, 26),
    date(2025, 1, 26),
    date(2025, 7, 26),
    date(2026, 1, 30),
]

WARMUP_BARS = 8000
N_SIMULATIONS = 1000
PERCENTILES = [5, 25, 50, 75, 95]


def compute_max_drawdown(pnls):
    """Max drawdown from a series of trade PnLs."""
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(np.min(dd)) if len(dd) > 0 else 0.0


def compute_sharpe(pnls):
    """Sharpe ratio (mean/std) from trade PnLs."""
    if len(pnls) < 2 or np.std(pnls) == 0:
        return 0.0
    return float(np.mean(pnls) / np.std(pnls))


def monte_carlo(trade_pnls, n_sim=1000, rng=None):
    """Bootstrap resample trades n_sim times. Returns arrays of PnL, DD, Sharpe."""
    if rng is None:
        rng = np.random.default_rng(42)

    n_trades = len(trade_pnls)
    pnl_totals = np.empty(n_sim)
    dd_totals = np.empty(n_sim)
    sharpe_totals = np.empty(n_sim)

    for i in range(n_sim):
        sample = rng.choice(trade_pnls, size=n_trades, replace=True)
        pnl_totals[i] = np.sum(sample)
        dd_totals[i] = compute_max_drawdown(sample)
        sharpe_totals[i] = compute_sharpe(sample)

    return pnl_totals, dd_totals, sharpe_totals


def main():
    t_start = time.time()
    print("=" * 120)
    print("PHASE 2 - MONTE CARLO (3 configs, 1000 resamplings)")
    print("Criteres : PnL P5 >= $0 ET DD P95 >= -$3,000")
    print("=" * 120)

    # --- Load data ---
    print("\n[1/3] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_5min):,} barres 5-min | {len(df_5s):,} barres 5s")

    # --- Collect OOS trades for each config ---
    print("\n[2/3] Collecte des trades OOS (5 fenetres par config)...")

    oos_windows = []
    for i in range(5):
        test_start = WINDOW_BOUNDARIES[i + 1]
        test_end = WINDOW_BOUNDARIES[i + 2]
        oos_windows.append({"test_start": test_start, "test_end": test_end})

    mc_results = {}

    for cfg_def in CONFIGS:
        label = cfg_def["label"]
        overrides = {**cfg_def["overrides"], **FIXED}
        config = apply_overrides(base_config, overrides)

        all_pnls = []
        total_trades = 0

        for w_idx, window in enumerate(oos_windows):
            df_test = slice_data(df_5min, window["test_start"], window["test_end"],
                                 include_warmup=True, warmup_bars=WARMUP_BARS)
            df_5s_test = slice_5s(df_5s, window["test_start"], window["test_end"])

            df_with_ind = calculate_all_indicators(df_test, config, verbose=False)
            trades_df = run_hybrid_backtest(df_with_ind, df_5s_test, config, verbose=False)

            if trades_df is not None and len(trades_df) > 0:
                pnls = trades_df["PnL_Net"].values
                all_pnls.extend(pnls.tolist())
                total_trades += len(trades_df)

        trade_pnls = np.array(all_pnls)
        print(f"   {label}: {total_trades} trades OOS collectes (avg ${np.mean(trade_pnls):+.1f})")

        # --- Monte Carlo ---
        rng = np.random.default_rng(42)
        pnl_sims, dd_sims, sharpe_sims = monte_carlo(trade_pnls, N_SIMULATIONS, rng)

        mc_results[label] = {
            "trades": total_trades,
            "trade_pnls": trade_pnls,
            "pnl_sims": pnl_sims,
            "dd_sims": dd_sims,
            "sharpe_sims": sharpe_sims,
        }

    # --- Results ---
    elapsed = time.time() - t_start
    print(f"\n{'='*120}")
    print(f"RESULTATS PHASE 2 - MONTE CARLO ({elapsed:.1f}s)")
    print(f"{'='*120}")

    survivors = []
    for label, r in mc_results.items():
        pnl_pcts = np.percentile(r["pnl_sims"], PERCENTILES)
        dd_pcts = np.percentile(r["dd_sims"], PERCENTILES)
        sharpe_pcts = np.percentile(r["sharpe_sims"], PERCENTILES)

        pnl_p5 = pnl_pcts[0]
        dd_p95 = dd_pcts[4]  # P95 of DD (most negative)

        pass_pnl = pnl_p5 >= 0
        pass_dd = dd_p95 >= -3000

        verdict = "PASS" if (pass_pnl and pass_dd) else "FAIL"

        print(f"\n--- {label} ({r['trades']} trades) ---")
        print(f"   PnL  : P5=${pnl_pcts[0]:>+8,.0f}  P25=${pnl_pcts[1]:>+8,.0f}  P50=${pnl_pcts[2]:>+8,.0f}  P75=${pnl_pcts[3]:>+8,.0f}  P95=${pnl_pcts[4]:>+8,.0f}")
        print(f"   DD   : P5=${dd_pcts[0]:>+8,.0f}  P25=${dd_pcts[1]:>+8,.0f}  P50=${dd_pcts[2]:>+8,.0f}  P75=${dd_pcts[3]:>+8,.0f}  P95=${dd_pcts[4]:>+8,.0f}")
        print(f"   Sharpe: P5={sharpe_pcts[0]:>+6.3f}   P25={sharpe_pcts[1]:>+6.3f}   P50={sharpe_pcts[2]:>+6.3f}   P75={sharpe_pcts[3]:>+6.3f}   P95={sharpe_pcts[4]:>+6.3f}")
        print(f"   PnL P5 {'>=':>2} $0 : {'OK' if pass_pnl else 'FAIL'}")
        print(f"   DD P95 {'>=':>2} -$3K: {'OK' if pass_dd else 'FAIL'}")
        print(f"   >>> {verdict}")

        if verdict == "PASS":
            survivors.append(label)

    print(f"\n{'='*120}")
    print(f"SURVIVANTS PHASE 2 : {len(survivors)}/3")
    for s in survivors:
        print(f"   {s}")
    if not survivors:
        print("   AUCUN - toutes les configs eliminees")
    print(f"{'='*120}")

    # Save CSV
    rows = []
    for label, r in mc_results.items():
        pnl_pcts = np.percentile(r["pnl_sims"], PERCENTILES)
        dd_pcts = np.percentile(r["dd_sims"], PERCENTILES)
        sharpe_pcts = np.percentile(r["sharpe_sims"], PERCENTILES)
        row = {"config": label, "trades_oos": r["trades"]}
        for i, p in enumerate(PERCENTILES):
            row[f"pnl_p{p}"] = pnl_pcts[i]
            row[f"dd_p{p}"] = dd_pcts[i]
            row[f"sharpe_p{p}"] = sharpe_pcts[i]
        row["verdict"] = "PASS" if label in survivors else "FAIL"
        rows.append(row)

    out_path = Path("output/reports/wf_phase2_mc_results.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, sep=";", index=False)
    print(f"\nResultats sauvegardes dans {out_path}")


if __name__ == "__main__":
    main()
