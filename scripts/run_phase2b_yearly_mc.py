"""
Phase 2b - Analyse par annee + Monte Carlo IN-SAMPLE complet.

3 configs (C03, C05, C09) sur donnees completes.
- PnL, trades, Sharpe, DD, WR, exit reasons par annee civile
- Monte Carlo 1000 resamplings sur tous les trades

Usage:
    python scripts/run_phase2b_yearly_mc.py
"""
import sys
import time
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics


from wf_configs import CONFIGS, FIXED

# Phase 2b only tests C03, C05, C09
CONFIGS = [c for c in CONFIGS if c["label"].startswith(("C03_", "C05_", "C09_"))]

N_SIMULATIONS = 1000
PERCENTILES = [5, 25, 50, 75, 95]
EXIT_REASONS = ["TP_DOLLAR", "TP_ZSCORE", "SL_DOLLAR", "SL_ZSCORE", "MAX_HOLD", "FLAT_EOD"]


def compute_max_drawdown(pnls):
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(np.min(dd)) if len(dd) > 0 else 0.0


def compute_sharpe(pnls):
    if len(pnls) < 2 or np.std(pnls) == 0:
        return 0.0
    return float(np.mean(pnls) / np.std(pnls))


def monte_carlo(trade_pnls, n_sim=1000):
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
    print("PHASE 2b - ANALYSE PAR ANNEE + MONTE CARLO IN-SAMPLE COMPLET")
    print("=" * 120)

    # --- Load data ---
    print("\n[1/2] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_5min):,} barres 5-min | {len(df_5s):,} barres 5s")

    # --- Backtest each config on full data ---
    print("\n[2/2] Backtests complets + analyse...")

    for cfg_def in CONFIGS:
        label = cfg_def["label"]
        overrides = {**cfg_def["overrides"], **FIXED}
        config = apply_overrides(base_config, overrides)

        df_with_ind = calculate_all_indicators(df_5min.copy(), config, verbose=False)
        trades_df = run_hybrid_backtest(df_with_ind, df_5s, config, verbose=False)

        if trades_df is None or len(trades_df) == 0:
            print(f"\n{'='*120}")
            print(f"{label}: 0 trades")
            continue

        # Add year column
        trades_df["Year"] = pd.to_datetime(trades_df["Entry_DateTime"]).dt.year
        years = sorted(trades_df["Year"].unique())

        print(f"\n{'='*120}")
        print(f"  {label}")
        print(f"  {len(trades_df)} trades total | PnL ${trades_df['PnL_Net'].sum():+,.0f}")
        print(f"{'='*120}")

        # --- Yearly breakdown ---
        print(f"\n  {'Annee':>6} {'Trades':>7} {'PnL Net':>10} {'MaxDD':>9} {'Sharpe':>8} {'WR%':>6} {'AvgPnL':>8}")
        print(f"  {'-'*65}")

        for year in years:
            yr_df = trades_df[trades_df["Year"] == year]
            pnls = yr_df["PnL_Net"].values
            n = len(yr_df)
            pnl_total = pnls.sum()
            dd = compute_max_drawdown(pnls)
            sharpe = compute_sharpe(pnls)
            wr = (pnls > 0).sum() / n * 100 if n > 0 else 0
            avg = pnls.mean()
            print(f"  {year:>6} {n:>7} ${pnl_total:>+9,.0f} ${dd:>+8,.0f} {sharpe:>+8.3f} {wr:>5.1f}% ${avg:>+7.1f}")

        # Total row
        all_pnls = trades_df["PnL_Net"].values
        print(f"  {'-'*65}")
        print(f"  {'TOTAL':>6} {len(trades_df):>7} ${all_pnls.sum():>+9,.0f} ${compute_max_drawdown(all_pnls):>+8,.0f} {compute_sharpe(all_pnls):>+8.3f} {(all_pnls > 0).sum()/len(all_pnls)*100:>5.1f}% ${all_pnls.mean():>+7.1f}")

        # --- Exit reasons by year ---
        print(f"\n  Exit Reasons par annee:")
        print(f"  {'Annee':>6}", end="")
        for er in EXIT_REASONS:
            print(f" {er:>10}", end="")
        print()
        print(f"  {'-'*75}")

        for year in years:
            yr_df = trades_df[trades_df["Year"] == year]
            counts = Counter(yr_df["Exit_Reason"].values)
            n = len(yr_df)
            print(f"  {year:>6}", end="")
            for er in EXIT_REASONS:
                c = counts.get(er, 0)
                pct = c / n * 100 if n > 0 else 0
                print(f" {c:>3}({pct:>4.0f}%)", end="")
            print()

        # Total exit reasons
        all_counts = Counter(trades_df["Exit_Reason"].values)
        n_all = len(trades_df)
        print(f"  {'TOTAL':>6}", end="")
        for er in EXIT_REASONS:
            c = all_counts.get(er, 0)
            pct = c / n_all * 100 if n_all > 0 else 0
            print(f" {c:>3}({pct:>4.0f}%)", end="")
        print()

        # --- Avg PnL by exit reason ---
        print(f"\n  Avg PnL par exit reason:")
        print(f"  {'Reason':<12} {'Count':>6} {'AvgPnL':>9} {'TotalPnL':>10}")
        print(f"  {'-'*40}")
        for er in EXIT_REASONS:
            er_df = trades_df[trades_df["Exit_Reason"] == er]
            if len(er_df) > 0:
                print(f"  {er:<12} {len(er_df):>6} ${er_df['PnL_Net'].mean():>+8.1f} ${er_df['PnL_Net'].sum():>+9,.0f}")

        # --- Monte Carlo IN-SAMPLE ---
        print(f"\n  MONTE CARLO IN-SAMPLE ({len(trades_df)} trades, {N_SIMULATIONS} sims):")
        pnl_sims, dd_sims, sharpe_sims = monte_carlo(all_pnls, N_SIMULATIONS)

        pnl_pcts = np.percentile(pnl_sims, PERCENTILES)
        dd_pcts = np.percentile(dd_sims, PERCENTILES)
        sharpe_pcts = np.percentile(sharpe_sims, PERCENTILES)

        pass_pnl = pnl_pcts[0] >= 0
        pass_dd = dd_pcts[4] >= -3000

        print(f"   PnL  : P5=${pnl_pcts[0]:>+8,.0f}  P25=${pnl_pcts[1]:>+8,.0f}  P50=${pnl_pcts[2]:>+8,.0f}  P75=${pnl_pcts[3]:>+8,.0f}  P95=${pnl_pcts[4]:>+8,.0f}")
        print(f"   DD   : P5=${dd_pcts[0]:>+8,.0f}  P25=${dd_pcts[1]:>+8,.0f}  P50=${dd_pcts[2]:>+8,.0f}  P75=${dd_pcts[3]:>+8,.0f}  P95=${dd_pcts[4]:>+8,.0f}")
        print(f"   Sharpe: P5={sharpe_pcts[0]:>+6.3f}   P25={sharpe_pcts[1]:>+6.3f}   P50={sharpe_pcts[2]:>+6.3f}   P75={sharpe_pcts[3]:>+6.3f}   P95={sharpe_pcts[4]:>+6.3f}")
        print(f"   PnL P5 >= $0 : {'OK' if pass_pnl else 'FAIL'}")
        print(f"   DD P95 >= -$3K: {'OK' if pass_dd else 'FAIL'}")
        verdict = "PASS" if (pass_pnl and pass_dd) else "FAIL"
        print(f"   >>> {verdict}")

    elapsed = time.time() - t_start
    print(f"\n{'='*120}")
    print(f"Termine en {elapsed:.1f}s")
    print(f"{'='*120}")


if __name__ == "__main__":
    main()
