"""
Deep Analysis R2b - Stabilite temporelle, consistency, exit types.
Lance 9 backtests individuels et analyse les trades en detail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
import numpy as np
import pandas as pd
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from optimizer import apply_overrides
from backtest_engine_numba import run_hybrid_backtest

# --- 9 configs a analyser ---
CONFIGS = [
    {
        "name": "C1_b3960_Equilibre",
        "famille": "B - Equilibre",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 48,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C2_b3960_Volume",
        "famille": "B - Volume",
        "overrides": {
            "indicators.beta_lookback": 3960, "indicators.zscore_period": 36,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
            "entry.zscore_long": -3.25, "entry.zscore_short": 3.25,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C3_b5280_cp20",
        "famille": "A - Qualite",
        "overrides": {
            "indicators.beta_lookback": 5280, "indicators.zscore_period": 15,
            "indicators.correlation_period": 20, "indicators.adf_hurst_period": 96,
            "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C4_b5280_cp12",
        "famille": "A - Qualite",
        "overrides": {
            "indicators.beta_lookback": 5280, "indicators.zscore_period": 15,
            "indicators.correlation_period": 12, "indicators.adf_hurst_period": 96,
            "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C5_b5280_cp10",
        "famille": "A - Qualite",
        "overrides": {
            "indicators.beta_lookback": 5280, "indicators.zscore_period": 15,
            "indicators.correlation_period": 10, "indicators.adf_hurst_period": 96,
            "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C6_b7920_Long",
        "famille": "Long",
        "overrides": {
            "indicators.beta_lookback": 7920, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.25, "entry.zscore_short": 3.25,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C7_b2640_Baseline",
        "famille": "Baseline R1",
        "overrides": {
            "indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 26,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 20,
            "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C8_b9900_VolumeD",
        "famille": "Volume D",
        "overrides": {
            "indicators.beta_lookback": 9900, "indicators.zscore_period": 60,
            "indicators.correlation_period": 10, "indicators.adf_hurst_period": 256,
            "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 800, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
    {
        "name": "C9_b1980_Sniper",
        "famille": "Sniper",
        "overrides": {
            "indicators.beta_lookback": 1980, "indicators.zscore_period": 24,
            "indicators.correlation_period": 30, "indicators.adf_hurst_period": 96,
            "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
            "entry.cointegration_score_min": 50,
            "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
            "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
            "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -99999,
            "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
            "session.flat_end_of_session": True,
            "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
            "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
        }
    },
]


def run_single_backtest(config_base, overrides):
    """Lance un backtest et retourne le DataFrame des trades."""
    cfg = apply_overrides(config_base, overrides)
    period = cfg["indicators"].get("period", "5min")
    if period == "5min":
        df_5min = resample_to_5min(df_1min_global)
        df_ind = calculate_all_indicators(df_5min, cfg)
    else:
        df_ind = calculate_all_indicators(df_1min_global, cfg)
    trades = run_hybrid_backtest(df_ind, df_5s_global, cfg, verbose=False)
    return trades


def analyze_stability(trades_df, name):
    """Analyse A: stabilite temporelle par annee et par periode."""
    if trades_df.empty:
        return {"name": name, "years": {}, "total_trades": 0}

    trades_df = trades_df.copy()
    trades_df["entry_time"] = pd.to_datetime(trades_df["Entry_DateTime"])
    trades_df["year"] = trades_df["entry_time"].dt.year
    trades_df["month"] = trades_df["entry_time"].dt.to_period("M")

    result = {"name": name, "total_trades": len(trades_df), "years": {}}
    for y in sorted(trades_df["year"].unique()):
        yr = trades_df[trades_df["year"] == y]
        result["years"][y] = {
            "trades": len(yr),
            "pnl": float(yr["PnL_Net"].sum()),
            "wr": float((yr["PnL_Net"] > 0).mean() * 100),
            "avg_pnl": float(yr["PnL_Net"].mean()),
        }
    return result


def analyze_consistency(trades_df, name):
    """Analyse B: consistency mensuelle."""
    if trades_df.empty:
        return {"name": name, "months_total": 0}

    trades_df = trades_df.copy()
    trades_df["entry_time"] = pd.to_datetime(trades_df["Entry_DateTime"])
    trades_df["month"] = trades_df["entry_time"].dt.to_period("M")

    monthly = trades_df.groupby("month").agg(
        pnl=("PnL_Net", "sum"),
        trades=("PnL_Net", "count"),
    )

    # Mois entre premier et dernier trade
    all_months = pd.period_range(
        trades_df["entry_time"].min().to_period("M"),
        trades_df["entry_time"].max().to_period("M"),
        freq="M",
    )
    months_with_trades = len(monthly)
    months_positive = int((monthly["pnl"] > 0).sum())

    # Streak max mois perdants consecutifs
    pnl_series = monthly["pnl"].reindex(all_months, fill_value=0)
    losing = (pnl_series <= 0).astype(int)
    max_losing_streak = 0
    current_streak = 0
    for v in losing:
        if v == 1:
            current_streak += 1
            max_losing_streak = max(max_losing_streak, current_streak)
        else:
            current_streak = 0

    return {
        "name": name,
        "months_total": len(all_months),
        "months_with_trades": months_with_trades,
        "pct_months_active": round(months_with_trades / len(all_months) * 100, 1),
        "months_positive": months_positive,
        "pct_months_positive": round(months_positive / max(months_with_trades, 1) * 100, 1),
        "max_losing_streak": max_losing_streak,
        "avg_monthly_pnl": round(float(monthly["pnl"].mean()), 1),
        "median_monthly_pnl": round(float(monthly["pnl"].median()), 1),
    }


def analyze_exits(trades_df, name):
    """Analyse C: exit types detailles."""
    if trades_df.empty:
        return {"name": name, "exits": {}}

    result = {"name": name, "exits": {}}
    for etype in trades_df["Exit_Reason"].unique():
        sub = trades_df[trades_df["Exit_Reason"] == etype]
        # Duree en minutes (colonne pre-calculee par le moteur)
        durations = sub["Duration_Min"]

        exit_info = {
            "count": len(sub),
            "pnl_avg": round(float(sub["PnL_Net"].mean()), 1),
            "pnl_total": round(float(sub["PnL_Net"].sum()), 1),
            "duration_avg_min": round(float(durations.mean()), 1),
        }

        # Z-Score entree/sortie si dispo
        if "Entry_ZScore" in sub.columns:
            exit_info["zscore_entry_avg"] = round(float(sub["Entry_ZScore"].mean()), 2)
        if "Exit_ZScore" in sub.columns:
            exit_info["zscore_exit_avg"] = round(float(sub["Exit_ZScore"].mean()), 2)

        result["exits"][etype] = exit_info

    return result


def format_report(all_results, output_path):
    """Genere le rapport markdown."""
    lines = []
    lines.append("# Deep Analysis R2b - 9 Configs Candidates")
    lines.append("")
    lines.append(f"Date: 2026-02-14")
    lines.append("")

    # === Section A : Stabilite temporelle ===
    lines.append("## A) Stabilite temporelle")
    lines.append("")
    lines.append("| Config | Famille | Total | 2023 trades | 2023 PnL | 2024 trades | 2024 PnL | 2025 trades | 2025 PnL | 2026 trades | 2026 PnL |")
    lines.append("|--------|---------|-------|-------------|----------|-------------|----------|-------------|----------|-------------|----------|")

    for r in all_results:
        stab = r["stability"]
        row = [r["cfg"]["name"], r["cfg"]["famille"], str(stab["total_trades"])]
        for y in [2023, 2024, 2025, 2026]:
            yd = stab["years"].get(y, {"trades": 0, "pnl": 0})
            row.append(str(yd["trades"]))
            row.append(f"${yd['pnl']:,.0f}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    # Detail par annee avec WR
    lines.append("### Detail par annee")
    lines.append("")
    for r in all_results:
        stab = r["stability"]
        lines.append(f"**{r['cfg']['name']}** ({r['cfg']['famille']})")
        for y in sorted(stab["years"].keys()):
            yd = stab["years"][y]
            lines.append(f"  - {y}: {yd['trades']} trades, PnL ${yd['pnl']:,.0f}, WR {yd['wr']:.1f}%, avg ${yd['avg_pnl']:,.1f}")
        lines.append("")

    # === Section B : Consistency mensuelle ===
    lines.append("## B) Consistency mensuelle")
    lines.append("")
    lines.append("| Config | Mois actifs | % actif | Mois positifs | % positif | Max losing streak | PnL moyen/mois | PnL median/mois |")
    lines.append("|--------|-------------|---------|---------------|-----------|-------------------|----------------|-----------------|")
    for r in all_results:
        c = r["consistency"]
        lines.append(f"| {r['cfg']['name']} | {c['months_with_trades']}/{c['months_total']} | {c['pct_months_active']}% | {c['months_positive']} | {c['pct_months_positive']}% | {c['max_losing_streak']} | ${c['avg_monthly_pnl']:,.0f} | ${c['median_monthly_pnl']:,.0f} |")

    lines.append("")

    # === Section C : Exit types ===
    lines.append("## C) Analyse par type de sortie")
    lines.append("")
    for r in all_results:
        ex = r["exits"]
        lines.append(f"### {r['cfg']['name']} ({r['cfg']['famille']})")
        lines.append("")
        lines.append("| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |")
        lines.append("|-----------|---|---------|-----------|-----------------|-------------|------------|")
        for etype, info in sorted(ex["exits"].items(), key=lambda x: -x[1]["count"]):
            z_entry = f"{info.get('zscore_entry_avg', '-')}"
            z_exit = f"{info.get('zscore_exit_avg', '-')}"
            lines.append(f"| {etype} | {info['count']} | ${info['pnl_avg']:,.1f} | ${info['pnl_total']:,.0f} | {info['duration_avg_min']:.0f} | {z_entry} | {z_exit} |")
        lines.append("")

    # === Section D : Tableau comparatif final ===
    lines.append("## D) Tableau comparatif final")
    lines.append("")
    lines.append("| Config | Famille | Trades | WR | PnL | PF | DD | Sharpe | Mois+ | Max lose streak | 2023 PnL | 2024 PnL | 2025 PnL | 2026 PnL | TP_Z avg$ | TP_$ avg$ | Duree moy |")
    lines.append("|--------|---------|--------|----|-----|----|----|--------|-------|-----------------|----------|----------|----------|----------|-----------|-----------|-----------|")
    for r in all_results:
        stab = r["stability"]
        cons = r["consistency"]
        ex = r["exits"]
        trades_df = r["trades_df"]

        if trades_df.empty:
            continue

        total_pnl = float(trades_df["PnL_Net"].sum())
        total_trades = len(trades_df)
        wr = float((trades_df["PnL_Net"] > 0).mean() * 100)

        # PF
        wins = trades_df[trades_df["PnL_Net"] > 0]["PnL_Net"].sum()
        losses = abs(trades_df[trades_df["PnL_Net"] <= 0]["PnL_Net"].sum())
        pf = wins / losses if losses > 0 else float("inf")

        # Max DD
        equity = trades_df["PnL_Net"].cumsum()
        running_max = equity.cummax()
        dd = (equity - running_max).min()

        # Sharpe (annualise)
        daily_pnl = trades_df.copy()
        daily_pnl["date"] = pd.to_datetime(daily_pnl["Entry_DateTime"]).dt.date
        daily_agg = daily_pnl.groupby("date")["PnL_Net"].sum()
        if daily_agg.std() > 0:
            sharpe = round(daily_agg.mean() / daily_agg.std() * (252 ** 0.5), 2)
        else:
            sharpe = 0

        # TP_ZSCORE et TP_DOLLAR avg PnL
        tp_z_info = ex["exits"].get("TP_ZSCORE", {})
        tp_d_info = ex["exits"].get("TP_DOLLAR", {})
        tp_z_avg = f"${tp_z_info.get('pnl_avg', 0):,.0f}" if tp_z_info else "-"
        tp_d_avg = f"${tp_d_info.get('pnl_avg', 0):,.0f}" if tp_d_info else "-"

        # Duree moyenne globale (colonne pre-calculee par le moteur)
        avg_dur = round(float(trades_df["Duration_Min"].mean()), 0)

        # PnL par annee
        yr_pnl = {}
        trades_df_copy = trades_df.copy()
        trades_df_copy["year"] = pd.to_datetime(trades_df_copy["Entry_DateTime"]).dt.year
        for y in [2023, 2024, 2025, 2026]:
            yp = trades_df_copy[trades_df_copy["year"] == y]["PnL_Net"].sum()
            yr_pnl[y] = f"${yp:,.0f}"

        lines.append(
            f"| {r['cfg']['name']} | {r['cfg']['famille']} | {total_trades} | {wr:.0f}% | ${total_pnl:,.0f} | {pf:.2f} | ${dd:,.0f} | {sharpe} | {cons['pct_months_positive']}% | {cons['max_losing_streak']} | {yr_pnl[2023]} | {yr_pnl[2024]} | {yr_pnl[2025]} | {yr_pnl[2026]} | {tp_z_avg} | {tp_d_avg} | {avg_dur:.0f}min |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*Genere par deep_analysis_r2b.py*")

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return report


# === MAIN ===
if __name__ == "__main__":
    print("=" * 80)
    print("DEEP ANALYSIS R2b - 9 Configs Candidates")
    print("=" * 80)

    # Charger les donnees une seule fois
    print("\nChargement des donnees...")
    config_path = "config/strategy_params.yaml"
    with open(config_path, encoding="utf-8") as f:
        config_base = yaml.safe_load(f)

    df_1min_global, config_base, _ = load_and_prepare_data(config_path)
    df_5s_global = load_5s_data(config_base)
    print(f"  {len(df_1min_global):,} barres 1-min, {len(df_5s_global):,} barres 5s")

    all_results = []

    for i, cfg in enumerate(CONFIGS):
        print(f"\n[{i+1}/9] {cfg['name']} ({cfg['famille']})...")
        trades_df = run_single_backtest(config_base, cfg["overrides"])
        print(f"  -> {len(trades_df)} trades")

        stab = analyze_stability(trades_df, cfg["name"])
        cons = analyze_consistency(trades_df, cfg["name"])
        exits = analyze_exits(trades_df, cfg["name"])

        all_results.append({
            "cfg": cfg,
            "trades_df": trades_df,
            "stability": stab,
            "consistency": cons,
            "exits": exits,
        })

    print("\n" + "=" * 80)
    print("Generation du rapport...")
    print("=" * 80)

    format_report(all_results, "output/reports/R2B_DEEP_ANALYSIS.md")
    print("\n[OK] Rapport sauvegarde dans output/reports/R2B_DEEP_ANALYSIS.md")
