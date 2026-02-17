#!/usr/bin/env python
"""
Analyse approfondie trade par trade de 10 configs R1 selectionnees.
Produit un rapport detaille dans output/grid_searches/r1_corrected/r1_deep_analysis.txt

Usage:
    python scripts/analyze_r1_top_configs.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest, warmup_numba
from optimizer import apply_overrides_fast, compute_metrics

OUTPUT = Path("output/grid_searches/r1_corrected/r1_deep_analysis.txt")

CONFIGS = [
    {"name": "C1_pnl_sharpe_balanced", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -500, "mhb": 0, "mm": 2},
    {"name": "C2_pnl_brut_top", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.5, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -600, "mhb": 0, "mm": 2},
    {"name": "C3_calmar_top", "beta": 2640, "zp": 30, "cp": 12, "adf": 144,
     "zE": 3.75, "co": 20, "zTP": -1.5, "dTP": 250, "dSL": 0, "mhb": 0, "mm": 2},
    {"name": "C4_sortino_mhb6", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 0.5, "dTP": 250, "dSL": 0, "mhb": 6, "mm": 2},
    {"name": "C5_zero_eod", "beta": 1980, "zp": 20, "cp": 20, "adf": 48,
     "zE": 3.25, "co": 30, "zTP": -1.5, "dTP": 250, "dSL": -500, "mhb": 0, "mm": 2},
    {"name": "C6_low_dd_cp36", "beta": 4620, "zp": 30, "cp": 36, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -500, "mhb": 0, "mm": 2},
    {"name": "C7_high_trades", "beta": 2640, "zp": 20, "cp": 12, "adf": 32,
     "zE": 3.25, "co": 30, "zTP": -1.5, "dTP": 250, "dSL": 0, "mhb": 0, "mm": 2},
    {"name": "C8_anti_fragile", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 1.0, "dTP": 250, "dSL": 0, "mhb": 0, "mm": 2},
    {"name": "C9_alt_indicators", "beta": 2640, "zp": 30, "cp": 12, "adf": 26,
     "zE": 3.5, "co": 20, "zTP": -0.5, "dTP": 250, "dSL": -1000, "mhb": 0, "mm": 2},
    {"name": "C10_alt_mhb6", "beta": 3960, "zp": 24, "cp": 30, "adf": 144,
     "zE": 3.5, "co": 30, "zTP": 1.0, "dTP": 250, "dSL": 0, "mhb": 6, "mm": 2},
]

FIXED = {
    "contracts.mode": "micro",
    "exit.zscore_tp_enabled": True,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
    "session.session_end_time": "14:55",
    "session.entry_start_hour": 18,
    "session.entry_end_hour": 14,
}

EXIT_REASONS = ["TP_ZSCORE", "TP_DOLLAR", "SL_DOLLAR", "SL_ZSCORE", "MAX_HOLD", "FLAT_EOD"]


def build_overrides(cfg):
    """Construit les overrides pour une config."""
    return {
        "indicators.beta_lookback": cfg["beta"],
        "indicators.zscore_period": cfg["zp"],
        "indicators.correlation_period": cfg["cp"],
        "indicators.adf_hurst_period": cfg["adf"],
        "entry.zscore_long": -cfg["zE"],
        "entry.zscore_short": cfg["zE"],
        "entry.cointegration_score_min": cfg["co"],
        "exit.zscore_tp_long": -cfg["zTP"],
        "exit.zscore_tp_short": cfg["zTP"],
        "exit.zscore_sl_long": -99.0,
        "exit.zscore_sl_short": 99.0,
        "exit.pnl_take_profit": cfg["dTP"],
        "exit.pnl_stop_loss": cfg["dSL"],
        "session.flat_end_of_session": True,
        "exit.max_holding_bars": cfg["mhb"],
        "contracts.micro_multiplier_max": cfg["mm"],
        **FIXED,
    }


def analyze_config(trades, cfg, lines):
    """Analyse complete d'une config."""
    name = cfg["name"]
    n = len(trades)

    lines.append("=" * 120)
    lines.append(f"CONFIG: {name}")
    lines.append(f"  beta={cfg['beta']} zp={cfg['zp']} cp={cfg['cp']} adf={cfg['adf']} "
                 f"zE={cfg['zE']} co={cfg['co']} zTP={cfg['zTP']} dTP={cfg['dTP']} "
                 f"dSL={cfg['dSL']} mhb={cfg['mhb']} mm={cfg['mm']}")
    lines.append(f"  Trades: {n}")
    lines.append("=" * 120)

    if n == 0:
        lines.append("  AUCUN TRADE")
        return {}

    # Parse entry/exit bars and datetimes
    trades["Entry_DT"] = pd.to_datetime(trades["Entry_DateTime"])
    trades["Exit_DT"] = pd.to_datetime(trades["Exit_DateTime"])
    trades["Entry_Hour"] = trades["Entry_DT"].dt.hour
    trades["Entry_Year"] = trades["Entry_DT"].dt.year
    trades["Duration"] = trades["Duration_Min"]
    trades["Win"] = trades["PnL_Net"] > 0

    # --- A) BREAKDOWN PAR EXIT REASON ---
    lines.append("")
    lines.append("  A) BREAKDOWN PAR EXIT REASON")
    lines.append("  " + "-" * 100)
    lines.append("  {:<12} {:>6} {:>10} {:>10} {:>10} {:>6} {:>10}".format(
        "Reason", "Count", "PnL Tot", "PnL Avg", "PnL Med", "WR%", "Dur Avg"))
    lines.append("  " + "-" * 100)

    eod_count = 0
    eod_pnl_avg = 0.0

    for reason in EXIT_REASONS:
        sub = trades[trades["Exit_Reason"] == reason]
        cnt = len(sub)
        if cnt == 0:
            lines.append("  {:<12} {:>6}".format(reason, 0))
            continue
        pnl_tot = sub["PnL_Net"].sum()
        pnl_avg = sub["PnL_Net"].mean()
        pnl_med = sub["PnL_Net"].median()
        wr = (sub["PnL_Net"] > 0).mean() * 100
        dur = sub["Duration"].mean()
        lines.append("  {:<12} {:>6} {:>+10,.0f} {:>+10,.1f} {:>+10,.1f} {:>5.1f}% {:>10.1f}".format(
            reason, cnt, pnl_tot, pnl_avg, pnl_med, wr, dur))
        if reason == "FLAT_EOD":
            eod_count = cnt
            eod_pnl_avg = pnl_avg

    # --- B) ANALYSE FLAT_EOD ---
    lines.append("")
    lines.append("  B) ANALYSE FLAT_EOD")
    lines.append("  " + "-" * 100)

    eod_trades = trades[trades["Exit_Reason"] == "FLAT_EOD"]
    if len(eod_trades) == 0:
        lines.append("  Aucun trade FLAT_EOD")
    else:
        # Distribution heures d'entree
        eod_hours = eod_trades.groupby("Entry_Hour").agg(
            count=("PnL_Net", "count"),
            pnl_avg=("PnL_Net", "mean"),
        ).sort_index()
        lines.append("  Distribution heures entree (FLAT_EOD) :")
        for h, row in eod_hours.iterrows():
            lines.append("    {:>2}h CT : {:>3} trades, PnL avg ${:>+,.1f}".format(
                h, int(row["count"]), row["pnl_avg"]))

        # Avant/apres 12h CT
        before_12 = eod_trades[eod_trades["Entry_Hour"] < 12]
        after_12 = eod_trades[eod_trades["Entry_Hour"] >= 12]
        b12_pnl = before_12["PnL_Net"].mean() if len(before_12) > 0 else 0
        a12_pnl = after_12["PnL_Net"].mean() if len(after_12) > 0 else 0
        lines.append(f"  Entree < 12h CT : {len(before_12)} trades, PnL avg ${b12_pnl:+,.1f}")
        lines.append(f"  Entree >= 12h CT : {len(after_12)} trades, PnL avg ${a12_pnl:+,.1f}")

        # % positifs
        eod_pos = (eod_trades["PnL_Net"] > 0).sum()
        eod_neg = (eod_trades["PnL_Net"] <= 0).sum()
        lines.append(f"  FLAT_EOD positifs : {eod_pos}/{len(eod_trades)} ({eod_pos/len(eod_trades)*100:.1f}%)")

    # --- C) ANALYSE TEMPORELLE ---
    lines.append("")
    lines.append("  C) ANALYSE TEMPORELLE")
    lines.append("  " + "-" * 100)

    hourly = trades.groupby("Entry_Hour").agg(
        count=("PnL_Net", "count"),
        pnl_total=("PnL_Net", "sum"),
        pnl_avg=("PnL_Net", "mean"),
        wr=("Win", "mean"),
    ).sort_index()

    lines.append("  PnL moyen par heure d'entree :")
    for h, row in hourly.iterrows():
        bar = "+" * max(0, int(row["pnl_avg"] / 5)) + "-" * max(0, int(-row["pnl_avg"] / 5))
        lines.append("    {:>2}h CT : {:>3} trades, PnL avg ${:>+7,.1f}, WR {:>5.1f}% {}".format(
            h, int(row["count"]), row["pnl_avg"], row["wr"] * 100, bar))

    best_hours = hourly.nlargest(3, "pnl_avg")
    worst_hours = hourly.nsmallest(3, "pnl_avg")
    best_h_str = ", ".join(f"{int(h)}h" for h in best_hours.index)
    worst_h_str = ", ".join(f"{int(h)}h" for h in worst_hours.index)
    lines.append(f"  3 meilleures heures : {best_h_str}")
    lines.append(f"  3 pires heures      : {worst_h_str}")

    # --- D) EQUITY PAR ANNEE ---
    lines.append("")
    lines.append("  D) EQUITY PAR ANNEE")
    lines.append("  " + "-" * 100)
    lines.append("  {:>6} {:>6} {:>10} {:>10} {:>10}".format(
        "Annee", "Trades", "PnL", "PnL Avg", "Max DD"))
    lines.append("  " + "-" * 60)

    yearly_pnl = {}
    for year in sorted(trades["Entry_Year"].unique()):
        yt = trades[trades["Entry_Year"] == year]
        pnl_sum = yt["PnL_Net"].sum()
        pnl_avg = yt["PnL_Net"].mean()
        cumul = yt["PnL_Net"].cumsum()
        dd = (cumul - cumul.cummax()).min()
        yearly_pnl[year] = pnl_sum
        lines.append("  {:>6} {:>6} {:>+10,.0f} {:>+10,.1f} {:>+10,.0f}".format(
            year, len(yt), pnl_sum, pnl_avg, dd))

    # --- E) DUREE DES TRADES ---
    lines.append("")
    lines.append("  E) DUREE DES TRADES (barres 5-min)")
    lines.append("  " + "-" * 100)

    winners = trades[trades["PnL_Net"] > 0]
    losers = trades[trades["PnL_Net"] <= 0]

    w_avg = winners["Duration"].mean() if len(winners) > 0 else 0
    w_med = winners["Duration"].median() if len(winners) > 0 else 0
    l_avg = losers["Duration"].mean() if len(losers) > 0 else 0
    l_med = losers["Duration"].median() if len(losers) > 0 else 0

    lines.append(f"  Gagnants  : avg={w_avg:.1f} bars ({w_avg*5:.0f} min), "
                 f"median={w_med:.0f} bars ({w_med*5:.0f} min), n={len(winners)}")
    lines.append(f"  Perdants  : avg={l_avg:.1f} bars ({l_avg*5:.0f} min), "
                 f"median={l_med:.0f} bars ({l_med*5:.0f} min), n={len(losers)}")
    lines.append("")

    # Return summary data
    m = compute_metrics(trades)
    return {
        "name": name,
        "trades": n,
        "win_rate": m["win_rate"],
        "pnl_net": m["pnl_net"],
        "max_dd": m["max_dd"],
        "calmar": m["calmar"],
        "eod_count": eod_count,
        "eod_pct": round(eod_count / n * 100, 1) if n > 0 else 0,
        "eod_pnl_avg": round(eod_pnl_avg, 1),
        "best_hours": best_h_str,
        "worst_hours": worst_h_str,
        "avg_dur_win": round(w_avg, 1),
        "avg_dur_lose": round(l_avg, 1),
    }


def main():
    print("Chargement des donnees...")
    t0 = time.time()
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"  {len(df_5min):,} barres 5-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    warmup_numba()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("=" * 120)
    lines.append("ANALYSE APPROFONDIE R1 -- 10 CONFIGS SELECTIONNEES")
    lines.append(f"Date : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 120)

    summaries = []

    for i, cfg in enumerate(CONFIGS):
        print(f"\n[{i+1}/10] {cfg['name']}...")
        overrides = build_overrides(cfg)
        config_test = apply_overrides_fast(base_config, overrides)
        df_ind = calculate_all_indicators(df_5min, config_test, verbose=False)
        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)
        print(f"  {len(trades)} trades, PnL ${m['pnl_net']:+,.0f}, PF {m['profit_factor']:.2f}, "
              f"DD ${m['max_dd']:+,.0f}")

        summary = analyze_config(trades, cfg, lines)
        if summary:
            summaries.append(summary)

    # SYNTHESE COMPARATIVE
    lines.append("")
    lines.append("=" * 120)
    lines.append("SYNTHESE COMPARATIVE")
    lines.append("=" * 120)

    hdr = "{:<25} {:>6} {:>5} {:>9} {:>8} {:>6} {:>4} {:>5} {:>8} {:>12} {:>12} {:>7} {:>7}".format(
        "Config", "Trades", "WR%", "PnL", "MaxDD", "Cal", "EOD", "EOD%", "EOD avg",
        "Best Hours", "Worst Hours", "Dur W", "Dur L")
    lines.append(hdr)
    lines.append("-" * 160)

    for s in summaries:
        line = "{:<25} {:>6} {:>4.1f}% {:>+9,.0f} {:>+8,.0f} {:>6.2f} {:>4} {:>4.1f}% {:>+8,.1f} {:>12} {:>12} {:>7.1f} {:>7.1f}".format(
            s["name"], s["trades"], s["win_rate"], s["pnl_net"], s["max_dd"],
            s["calmar"], s["eod_count"], s["eod_pct"], s["eod_pnl_avg"],
            s["best_hours"], s["worst_hours"],
            s["avg_dur_win"], s["avg_dur_lose"])
        lines.append(line)

    # Write output
    text = "\n".join(lines) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")

    t_total = time.time() - t0
    print(f"\nTermine en {t_total:.1f}s")
    print(f"Output : {OUTPUT}")


if __name__ == "__main__":
    main()
