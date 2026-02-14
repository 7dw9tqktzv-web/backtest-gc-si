"""
Deep Analysis R2c - Stabilite temporelle, consistency, exit types.
Lance 10 backtests individuels et analyse les trades en detail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
import pandas as pd
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from optimizer import apply_overrides
from backtest_engine_numba import run_hybrid_backtest

# --- 10 configs a analyser (top 10 R2c par Sharpe, trades>=80) ---
CONFIGS = [
    {
        "name": "C1_b4620_zp30_cp27_adf160_dTP300",
        "famille": "B4620 Ultra Court",
        "beta": 4620, "zp": 30, "cp": 27, "adf": 160,
        "zE": 3.5, "co": 45, "zTP": 0.0, "dTP": 300,
    },
    {
        "name": "C2_b4620_zp30_cp27_adf160_dTP250",
        "famille": "B4620 Ultra Court",
        "beta": 4620, "zp": 30, "cp": 27, "adf": 160,
        "zE": 3.5, "co": 45, "zTP": 0.0, "dTP": 250,
    },
    {
        "name": "C3_b4290_zp33_cp30_adf128_dTP300",
        "famille": "B4290 Court",
        "beta": 4290, "zp": 33, "cp": 30, "adf": 128,
        "zE": 3.5, "co": 50, "zTP": 0.0, "dTP": 300,
    },
    {
        "name": "C4_b4290_zp33_cp33_adf112_dTP400",
        "famille": "B4290 Court",
        "beta": 4290, "zp": 33, "cp": 33, "adf": 112,
        "zE": 3.25, "co": 55, "zTP": 0.0, "dTP": 400,
    },
    {
        "name": "C5_b4290_zp30_cp24_adf160_dTP300",
        "famille": "B4290 Court",
        "beta": 4290, "zp": 30, "cp": 24, "adf": 160,
        "zE": 3.5, "co": 45, "zTP": 0.0, "dTP": 300,
    },
    {
        "name": "C6_b3960_zp33_cp27_adf144_dTP250",
        "famille": "B3960 Equilibre",
        "beta": 3960, "zp": 33, "cp": 27, "adf": 144,
        "zE": 3.25, "co": 45, "zTP": 0.0, "dTP": 250,
    },
    {
        "name": "C7_b4290_zp30_cp24_adf96_dTP300",
        "famille": "B4290 Court",
        "beta": 4290, "zp": 30, "cp": 24, "adf": 96,
        "zE": 3.5, "co": 45, "zTP": 0.0, "dTP": 300,
    },
    {
        "name": "C8_b4290_zp33_cp33_adf112_dTP350",
        "famille": "B4290 Court",
        "beta": 4290, "zp": 33, "cp": 33, "adf": 112,
        "zE": 3.25, "co": 55, "zTP": 0.0, "dTP": 350,
    },
    {
        "name": "C9_b4620_zp30_cp30_adf96_dTP250",
        "famille": "B4620 Ultra Court",
        "beta": 4620, "zp": 30, "cp": 30, "adf": 96,
        "zE": 3.5, "co": 40, "zTP": 0.0, "dTP": 250,
    },
    {
        "name": "C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250",
        "famille": "B4620 Ultra Court",
        "beta": 4620, "zp": 33, "cp": 36, "adf": 160,
        "zE": 3.375, "co": 55, "zTP": 0.5, "dTP": 250,
    },
]


def build_overrides(cfg_params):
    """Construit le dictionnaire d'overrides a partir des parametres."""
    # Parametres fixes pour tous les configs R2c
    overrides = {
        "indicators.beta_lookback": cfg_params["beta"],
        "indicators.zscore_period": cfg_params["zp"],
        "indicators.correlation_period": cfg_params["cp"],
        "indicators.adf_hurst_period": cfg_params["adf"],
        "entry.zscore_long": -cfg_params["zE"],
        "entry.zscore_short": cfg_params["zE"],
        "entry.cointegration_score_min": cfg_params["co"],
        "exit.zscore_tp_enabled": True,
        "exit.pnl_take_profit": cfg_params["dTP"],
        # Parametres verrouilles
        "exit.zscore_sl_long": -99,
        "exit.zscore_sl_short": 99,
        "exit.pnl_stop_loss": -99999,
        "exit.max_holding_bars": 0,
        "session.flat_end_of_session": True,
        "contracts.mode": "micro",
        "sizing.micro_multiplier_max": 2,
        "costs.slippage_gc_ticks": 1,
        "costs.slippage_si_ticks": 1,
    }

    # Mapping zTP -> exit.zscore_tp_long/short
    # zTP=0.0 -> long=0.0, short=0.0
    # zTP=0.5 -> long=0.5, short=-0.5
    ztp_val = cfg_params["zTP"]
    overrides["exit.zscore_tp_long"] = ztp_val
    overrides["exit.zscore_tp_short"] = -ztp_val

    return overrides


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
        return {"name": name, "years": {}, "total_trades": 0, "years_positive": 0}

    trades_df = trades_df.copy()
    trades_df["entry_time"] = pd.to_datetime(trades_df["Entry_DateTime"])
    trades_df["year"] = trades_df["entry_time"].dt.year
    trades_df["month"] = trades_df["entry_time"].dt.to_period("M")

    result = {"name": name, "total_trades": len(trades_df), "years": {}}
    years_positive = 0
    for y in sorted(trades_df["year"].unique()):
        yr = trades_df[trades_df["year"] == y]
        yr_pnl = float(yr["PnL_Net"].sum())
        if yr_pnl > 0:
            years_positive += 1
        result["years"][y] = {
            "trades": len(yr),
            "pnl": yr_pnl,
            "wr": float((yr["PnL_Net"] > 0).mean() * 100),
            "avg_pnl": float(yr["PnL_Net"].mean()),
        }
    result["years_positive"] = years_positive
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
    lines.append("# Deep Analysis R2c - 10 Top Configs (Sharpe, trades>=80)")
    lines.append("")
    lines.append(f"Date: 2026-02-14")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("Parametres fixes :")
    lines.append("- Contract mode: micro")
    lines.append("- Micro multiplier max: 2")
    lines.append("- Slippage: 1 tick per leg")
    lines.append("- zSL: -99/+99 (disabled)")
    lines.append("- dSL: -99999 (disabled)")
    lines.append("- max_holding_bars: 0 (disabled)")
    lines.append("- flat_end_of_session: True")
    lines.append("")

    # === Section A : Stabilite temporelle ===
    lines.append("## A) Stabilite temporelle")
    lines.append("")
    lines.append("| Config | Famille | Total | 2023 trades | 2023 PnL | 2024 trades | 2024 PnL | 2025 trades | 2025 PnL | 2026 trades | 2026 PnL | Annees+ |")
    lines.append("|--------|---------|-------|-------------|----------|-------------|----------|-------------|----------|-------------|----------|---------|")

    for r in all_results:
        stab = r["stability"]
        row = [r["cfg"]["name"], r["cfg"]["famille"], str(stab["total_trades"])]
        for y in [2023, 2024, 2025, 2026]:
            yd = stab["years"].get(y, {"trades": 0, "pnl": 0})
            row.append(str(yd["trades"]))
            row.append(f"${yd['pnl']:,.0f}")
        row.append(f"{stab['years_positive']}/4")
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
    lines.append("| Config | Famille | Trades | WR | PnL | PF | DD | Sharpe | Calmar | Annees+ | Mois+ | Max lose streak | TP_Z avg$ | TP_$ avg$ | Duree moy |")
    lines.append("|--------|---------|--------|----|-----|----|----|--------|--------|---------|-------|-----------------|-----------|-----------|-----------|")
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

        # Calmar
        days_total = (pd.to_datetime(trades_df["Entry_DateTime"]).max() -
                      pd.to_datetime(trades_df["Entry_DateTime"]).min()).days
        years = days_total / 365.25
        annual_return = total_pnl / years if years > 0 else 0
        calmar = abs(annual_return / dd) if dd < 0 else float("inf")
        calmar_str = f"{calmar:.2f}" if calmar != float("inf") else "inf"

        # TP_ZSCORE et TP_DOLLAR avg PnL
        tp_z_info = ex["exits"].get("TP_ZSCORE", {})
        tp_d_info = ex["exits"].get("TP_DOLLAR", {})
        tp_z_avg = f"${tp_z_info.get('pnl_avg', 0):,.0f}" if tp_z_info else "-"
        tp_d_avg = f"${tp_d_info.get('pnl_avg', 0):,.0f}" if tp_d_info else "-"

        # Duree moyenne globale (colonne pre-calculee par le moteur)
        avg_dur = round(float(trades_df["Duration_Min"].mean()), 0)

        lines.append(
            f"| {r['cfg']['name']} | {r['cfg']['famille']} | {total_trades} | {wr:.0f}% | ${total_pnl:,.0f} | {pf:.2f} | ${dd:,.0f} | {sharpe} | {calmar_str} | {stab['years_positive']}/4 | {cons['pct_months_positive']}% | {cons['max_losing_streak']} | {tp_z_avg} | {tp_d_avg} | {avg_dur:.0f}min |"
        )

    lines.append("")

    # === Section E : Classement par stabilite ===
    lines.append("## E) Classement par stabilite (annees positives)")
    lines.append("")
    lines.append("Stability Score = nombre d'annees avec PnL positif (max 4)")
    lines.append("")

    # Trier par years_positive puis par PnL total
    sorted_by_stability = sorted(
        all_results,
        key=lambda x: (x["stability"]["years_positive"],
                      sum(y["pnl"] for y in x["stability"]["years"].values())),
        reverse=True
    )

    lines.append("| Rang | Config | Famille | Annees+ | 2023 | 2024 | 2025 | 2026 | PnL Total | Sharpe |")
    lines.append("|------|--------|---------|---------|------|------|------|------|-----------|--------|")

    for rank, r in enumerate(sorted_by_stability, 1):
        stab = r["stability"]
        trades_df = r["trades_df"]

        # Recalcul Sharpe
        if not trades_df.empty:
            daily_pnl = trades_df.copy()
            daily_pnl["date"] = pd.to_datetime(daily_pnl["Entry_DateTime"]).dt.date
            daily_agg = daily_pnl.groupby("date")["PnL_Net"].sum()
            if daily_agg.std() > 0:
                sharpe = round(daily_agg.mean() / daily_agg.std() * (252 ** 0.5), 2)
            else:
                sharpe = 0
            total_pnl = float(trades_df["PnL_Net"].sum())
        else:
            sharpe = 0
            total_pnl = 0

        # Status par annee (+ ou -)
        y2023 = "+" if stab["years"].get(2023, {}).get("pnl", 0) > 0 else "-"
        y2024 = "+" if stab["years"].get(2024, {}).get("pnl", 0) > 0 else "-"
        y2025 = "+" if stab["years"].get(2025, {}).get("pnl", 0) > 0 else "-"
        y2026 = "+" if stab["years"].get(2026, {}).get("pnl", 0) > 0 else "-"

        lines.append(
            f"| {rank} | {r['cfg']['name']} | {r['cfg']['famille']} | {stab['years_positive']}/4 | {y2023} | {y2024} | {y2025} | {y2026} | ${total_pnl:,.0f} | {sharpe} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*Genere par deep_analysis_r2c.py*")

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return report


# === MAIN ===
if __name__ == "__main__":
    print("=" * 80)
    print("DEEP ANALYSIS R2c - 10 Top Configs (Sharpe, trades>=80)")
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
        print(f"\n[{i+1}/10] {cfg['name']} ({cfg['famille']})...")
        overrides = build_overrides(cfg)
        trades_df = run_single_backtest(config_base, overrides)
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

    format_report(all_results, "output/reports/R2C_DEEP_ANALYSIS.md")
    print("\n[OK] Rapport sauvegarde dans output/reports/R2C_DEEP_ANALYSIS.md")
