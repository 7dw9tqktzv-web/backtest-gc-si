"""
Phase 3 - Deep Analysis sur C01, C03, C09.
Donnees completes, pas OOS.

Usage:
    python scripts/run_phase3_deep.py
"""
import sys
import time
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wf_configs import CONFIGS, FIXED
from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides

import warnings
warnings.filterwarnings("ignore")

SELECTED = ["C01_", "C03_", "C09_"]
EXIT_REASONS = ["TP_DOLLAR", "TP_ZSCORE", "SL_DOLLAR", "SL_ZSCORE", "MAX_HOLD", "FLAT_EOD"]
GRID_REF = {"C01": 152, "C03": 200, "C09": 238}

OUT_PATH = Path("output/reports/phase3_deep_analysis.txt")


def compute_max_drawdown(pnls):
    if len(pnls) == 0:
        return 0.0
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(np.min(dd))


def compute_sharpe(pnls):
    if len(pnls) < 2 or np.std(pnls) == 0:
        return 0.0
    return float(np.mean(pnls) / np.std(pnls))


def compute_pf(pnls):
    gains = pnls[pnls > 0].sum()
    losses = abs(pnls[pnls < 0].sum())
    if losses == 0:
        return 99.99
    return gains / losses


def longest_streak(pnls, positive=True):
    """Returns (count, total_pnl) of longest consecutive streak."""
    best_count = 0
    best_pnl = 0.0
    cur_count = 0
    cur_pnl = 0.0
    for p in pnls:
        if (positive and p > 0) or (not positive and p <= 0):
            cur_count += 1
            cur_pnl += p
        else:
            if cur_count > best_count:
                best_count = cur_count
                best_pnl = cur_pnl
            cur_count = 0
            cur_pnl = 0.0
    if cur_count > best_count:
        best_count = cur_count
        best_pnl = cur_pnl
    return best_count, best_pnl


def analyze(label, trades_df, out):
    pnls = trades_df["PnL_Net"].values
    total_pnl = pnls.sum()
    n = len(trades_df)

    trades_df = trades_df.copy()
    trades_df["Entry_DT"] = pd.to_datetime(trades_df["Entry_DateTime"])
    trades_df["Year"] = trades_df["Entry_DT"].dt.year
    trades_df["Month"] = trades_df["Entry_DT"].dt.month
    trades_df["Hour"] = trades_df["Entry_DT"].dt.hour

    out.write("=" * 120 + "\n")
    out.write(f"  {label}\n")
    out.write(f"  {n} trades | PnL ${total_pnl:+,.0f} | DD ${compute_max_drawdown(pnls):+,.0f} | Sharpe {compute_sharpe(pnls):.3f}\n")
    out.write("=" * 120 + "\n")

    # --- 1. PnL par annee ---
    out.write("\n1. PNL PAR ANNEE\n")
    out.write("-" * 90 + "\n")
    out.write(f"  {'Annee':>6} {'Trades':>7} {'PnL':>10} {'WR%':>6} {'MaxDD':>9} {'Sharpe':>8} {'PF':>7}\n")
    out.write("-" * 90 + "\n")
    years = sorted(trades_df["Year"].unique())
    yearly_pnl = {}
    for year in years:
        yr = trades_df[trades_df["Year"] == year]
        yr_pnls = yr["PnL_Net"].values
        yr_n = len(yr)
        wr = (yr_pnls > 0).sum() / yr_n * 100
        dd = compute_max_drawdown(yr_pnls)
        sh = compute_sharpe(yr_pnls)
        pf = compute_pf(yr_pnls)
        yearly_pnl[year] = yr_pnls.sum()
        out.write(f"  {year:>6} {yr_n:>7} ${yr_pnls.sum():>+9,.0f} {wr:>5.1f}% ${dd:>+8,.0f} {sh:>+8.3f} {pf:>7.2f}\n")
    out.write("-" * 90 + "\n")
    out.write(f"  {'TOTAL':>6} {n:>7} ${total_pnl:>+9,.0f} {(pnls>0).sum()/n*100:>5.1f}% ${compute_max_drawdown(pnls):>+8,.0f} {compute_sharpe(pnls):>+8.3f} {compute_pf(pnls):>7.2f}\n")

    # --- 2. PnL par mois (heatmap) ---
    out.write("\n2. PNL PAR MOIS (heatmap)\n")
    out.write("-" * 90 + "\n")
    out.write(f"  {'':>6}")
    for m in range(1, 13):
        out.write(f" {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[m-1]:>7}")
    out.write(f" {'TOTAL':>9}\n")
    out.write("-" * 90 + "\n")
    for year in years:
        out.write(f"  {year:>6}")
        yr_total = 0
        for m in range(1, 13):
            mask = (trades_df["Year"] == year) & (trades_df["Month"] == m)
            mp = trades_df.loc[mask, "PnL_Net"].sum()
            yr_total += mp
            if mp == 0 and mask.sum() == 0:
                out.write(f" {'--':>7}")
            else:
                out.write(f" ${mp:>+6,.0f}")
        out.write(f" ${yr_total:>+8,.0f}\n")

    # --- 3. Breakdown exit reasons ---
    out.write("\n3. EXIT REASONS\n")
    out.write("-" * 90 + "\n")
    out.write(f"  {'Reason':<12} {'Count':>6} {'%':>6} {'AvgPnL':>9} {'TotalPnL':>10} {'AvgDur(min)':>12}\n")
    out.write("-" * 90 + "\n")
    for er in EXIT_REASONS:
        er_df = trades_df[trades_df["Exit_Reason"] == er]
        if len(er_df) == 0:
            continue
        cnt = len(er_df)
        pct = cnt / n * 100
        avg_pnl = er_df["PnL_Net"].mean()
        tot_pnl = er_df["PnL_Net"].sum()
        avg_dur = er_df["Duration_Min"].mean() if "Duration_Min" in er_df.columns else 0
        out.write(f"  {er:<12} {cnt:>6} {pct:>5.1f}% ${avg_pnl:>+8.1f} ${tot_pnl:>+9,.0f} {avg_dur:>12.1f}\n")

    # --- 4. Distribution horaire ---
    out.write("\n4. DISTRIBUTION HORAIRE (heure CT)\n")
    out.write("-" * 60 + "\n")
    out.write(f"  {'Heure':>5} {'Trades':>7} {'PnL Moy':>9} {'PnL Tot':>10} {'WR%':>6}\n")
    out.write("-" * 60 + "\n")
    for h in range(24):
        h_df = trades_df[trades_df["Hour"] == h]
        if len(h_df) == 0:
            continue
        h_pnls = h_df["PnL_Net"].values
        wr = (h_pnls > 0).sum() / len(h_df) * 100
        out.write(f"  {h:>5} {len(h_df):>7} ${h_pnls.mean():>+8.1f} ${h_pnls.sum():>+9,.0f} {wr:>5.1f}%\n")

    # --- 5. Concentration risk ---
    out.write("\n5. CONCENTRATION RISK\n")
    out.write("-" * 90 + "\n")
    sorted_trades = trades_df.sort_values("PnL_Net", ascending=False)

    out.write("  Top 10 meilleurs trades:\n")
    for i, (_, row) in enumerate(sorted_trades.head(10).iterrows()):
        pct = row["PnL_Net"] / total_pnl * 100 if total_pnl != 0 else 0
        out.write(f"    {i+1:>2}. {str(row['Entry_DateTime'])[:16]}  ${row['PnL_Net']:>+8,.0f}  ({pct:>+5.1f}% du total)  {row['Exit_Reason']}\n")

    out.write("\n  Top 10 pires trades:\n")
    for i, (_, row) in enumerate(sorted_trades.tail(10).iloc[::-1].iterrows()):
        out.write(f"    {i+1:>2}. {str(row['Entry_DateTime'])[:16]}  ${row['PnL_Net']:>+8,.0f}  {row['Exit_Reason']}\n")

    top10_pnl = sorted_trades.head(10)["PnL_Net"].sum()
    top20_pnl = sorted_trades.head(20)["PnL_Net"].sum()
    top10_pct = top10_pnl / total_pnl * 100 if total_pnl != 0 else 0
    top20_pct = top20_pnl / total_pnl * 100 if total_pnl != 0 else 0
    out.write(f"\n  Top 10 trades = ${top10_pnl:+,.0f} ({top10_pct:.1f}% du PnL total)\n")
    out.write(f"  Top 20 trades = ${top20_pnl:+,.0f} ({top20_pct:.1f}% du PnL total)\n")

    # --- 6. Distribution PnL par trade ---
    out.write("\n6. DISTRIBUTION PNL PAR TRADE\n")
    out.write("-" * 60 + "\n")
    pcts = np.percentile(pnls, [0, 5, 25, 50, 75, 95, 100])
    out.write(f"  Min=${pcts[0]:>+8,.0f}  P5=${pcts[1]:>+8,.0f}  P25=${pcts[2]:>+8,.0f}  P50=${pcts[3]:>+8,.0f}\n")
    out.write(f"  P75=${pcts[4]:>+8,.0f}  P95=${pcts[5]:>+8,.0f}  Max=${pcts[6]:>+8,.0f}\n")
    out.write(f"\n  > +$200 : {(pnls > 200).sum():>4} trades\n")
    out.write(f"  > +$100 : {(pnls > 100).sum():>4} trades\n")
    out.write(f"  -$50~+$50 : {((pnls >= -50) & (pnls <= 50)).sum():>4} trades\n")
    out.write(f"  < -$100 : {(pnls < -100).sum():>4} trades\n")
    out.write(f"  < -$200 : {(pnls < -200).sum():>4} trades\n")

    # --- 7. Duree en position ---
    out.write("\n7. DUREE EN POSITION (minutes)\n")
    out.write("-" * 60 + "\n")
    if "Duration_Min" in trades_df.columns:
        durs = trades_df["Duration_Min"].values
        out.write(f"  Moyenne: {durs.mean():.1f} min | Mediane: {np.median(durs):.1f} min | P95: {np.percentile(durs, 95):.1f} min\n")
        out.write(f"\n  {'Reason':<12} {'Moy':>8} {'Med':>8} {'P95':>8}\n")
        for er in EXIT_REASONS:
            er_df = trades_df[trades_df["Exit_Reason"] == er]
            if len(er_df) == 0:
                continue
            d = er_df["Duration_Min"].values
            out.write(f"  {er:<12} {d.mean():>7.1f}m {np.median(d):>7.1f}m {np.percentile(d, 95):>7.1f}m\n")

    # --- 8. Equity curve stats ---
    out.write("\n8. EQUITY CURVE\n")
    out.write("-" * 60 + "\n")
    equity = np.cumsum(pnls)
    out.write(f"  PnL cumule final: ${equity[-1]:+,.0f}\n")
    out.write(f"  Max equity: ${equity.max():+,.0f} (trade #{np.argmax(equity)+1})\n")
    out.write(f"  Min equity: ${equity.min():+,.0f}\n")

    ls_count, ls_pnl = longest_streak(pnls, positive=False)
    ws_count, ws_pnl = longest_streak(pnls, positive=True)
    out.write(f"  Plus longue serie de pertes: {ls_count} trades (${ls_pnl:+,.0f})\n")
    out.write(f"  Plus longue serie de gains:  {ws_count} trades (${ws_pnl:+,.0f})\n")

    out.write("\n")

    # Return summary for comparatif
    return {
        "label": label,
        "trades": n,
        "pnl": total_pnl,
        "dd": compute_max_drawdown(pnls),
        "sharpe": compute_sharpe(pnls),
        "calmar": total_pnl / abs(compute_max_drawdown(pnls)) if compute_max_drawdown(pnls) != 0 else 0,
        "pf": compute_pf(pnls),
        "wr": (pnls > 0).sum() / n * 100,
        "eod_pct": len(trades_df[trades_df["Exit_Reason"] == "FLAT_EOD"]) / n * 100,
        "tpD_pct": len(trades_df[trades_df["Exit_Reason"] == "TP_DOLLAR"]) / n * 100,
        "tpZ_pct": len(trades_df[trades_df["Exit_Reason"] == "TP_ZSCORE"]) / n * 100,
        "maxhold_pct": len(trades_df[trades_df["Exit_Reason"] == "MAX_HOLD"]) / n * 100,
        "avg_pnl_tpD": trades_df.loc[trades_df["Exit_Reason"] == "TP_DOLLAR", "PnL_Net"].mean() if len(trades_df[trades_df["Exit_Reason"] == "TP_DOLLAR"]) > 0 else 0,
        "avg_pnl_tpZ": trades_df.loc[trades_df["Exit_Reason"] == "TP_ZSCORE", "PnL_Net"].mean() if len(trades_df[trades_df["Exit_Reason"] == "TP_ZSCORE"]) > 0 else 0,
        "avg_pnl_eod": trades_df.loc[trades_df["Exit_Reason"] == "FLAT_EOD", "PnL_Net"].mean() if len(trades_df[trades_df["Exit_Reason"] == "FLAT_EOD"]) > 0 else 0,
        "top10_pct": top10_pct,
        "max_losing_streak": ls_count,
        "pnl_2023": yearly_pnl.get(2023, 0),
        "pnl_2024": yearly_pnl.get(2024, 0),
        "pnl_2025": yearly_pnl.get(2025, 0),
    }


def main():
    t_start = time.time()

    print("=" * 80)
    print("PHASE 3 - DEEP ANALYSIS (C01, C03, C09)")
    print("=" * 80)

    print("\nChargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"  {len(df_5min):,} barres 5-min | {len(df_5s):,} barres 5s")

    selected_configs = [c for c in CONFIGS if any(c["label"].startswith(s) for s in SELECTED)]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summaries = []

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        out.write("PHASE 3 - DEEP ANALYSIS\n")
        out.write(f"Configs: C01, C03, C09 | Donnees completes | {time.strftime('%Y-%m-%d %H:%M')}\n")
        out.write("=" * 120 + "\n\n")

        for cfg_def in selected_configs:
            label = cfg_def["label"]
            tag = label[:3]
            print(f"\nBacktest {label}...")

            config = apply_overrides(base_config, {**cfg_def["overrides"], **FIXED})
            df_ind = calculate_all_indicators(df_5min.copy(), config, verbose=False)
            trades_df = run_hybrid_backtest(df_ind, df_5s, config, verbose=False)

            n = len(trades_df) if trades_df is not None else 0
            expected = GRID_REF.get(tag, 0)
            status = "OK" if n == expected else f"MISMATCH (expected {expected})"
            print(f"  {n} trades [{status}]")

            if n > 0:
                summary = analyze(label, trades_df, out)
                summaries.append(summary)

        # --- 9. Comparatif final ---
        out.write("\n" + "=" * 120 + "\n")
        out.write("9. COMPARATIF FINAL\n")
        out.write("=" * 120 + "\n\n")

        headers = ["trades", "pnl", "dd", "sharpe", "calmar", "PF", "WR%",
                    "eod%", "tpD%", "tpZ%", "mhold%", "avgTpD", "avgTpZ", "avgEOD",
                    "top10%", "maxLS", "pnl23", "pnl24", "pnl25"]
        out.write(f"  {'Config':<38}")
        for h in headers:
            out.write(f" {h:>8}")
        out.write("\n")
        out.write("  " + "-" * (38 + 8 * len(headers)) + "\n")

        for s in summaries:
            out.write(f"  {s['label']:<38}")
            out.write(f" {s['trades']:>8}")
            out.write(f" ${s['pnl']:>+7,.0f}")
            out.write(f" ${s['dd']:>+7,.0f}")
            out.write(f" {s['sharpe']:>+7.3f}")
            out.write(f" {s['calmar']:>8.2f}")
            out.write(f" {s['pf']:>7.2f}")
            out.write(f" {s['wr']:>7.1f}")
            out.write(f" {s['eod_pct']:>7.1f}")
            out.write(f" {s['tpD_pct']:>7.1f}")
            out.write(f" {s['tpZ_pct']:>7.1f}")
            out.write(f" {s['maxhold_pct']:>7.1f}")
            out.write(f" ${s['avg_pnl_tpD']:>+6.0f}")
            out.write(f" ${s['avg_pnl_tpZ']:>+6.0f}")
            out.write(f" ${s['avg_pnl_eod']:>+6.0f}")
            out.write(f" {s['top10_pct']:>7.1f}")
            out.write(f" {s['max_losing_streak']:>7}")
            out.write(f" ${s['pnl_2023']:>+6,.0f}")
            out.write(f" ${s['pnl_2024']:>+6,.0f}")
            out.write(f" ${s['pnl_2025']:>+6,.0f}")
            out.write("\n")

        out.write("\n")

    elapsed = time.time() - t_start
    print(f"\nTermine en {elapsed:.1f}s")
    print(f"Resultats dans {OUT_PATH}")


if __name__ == "__main__":
    main()
