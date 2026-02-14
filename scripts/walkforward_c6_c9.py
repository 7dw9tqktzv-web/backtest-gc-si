"""
Walk-Forward Validation C6 vs C9 + Investigation regime 2024.

Part 1: Walk-forward validation avec fenetre ancree expansive (5 windows).
Part 2: Investigation detaillee du regime 2024 (trades mensuels, losing trades, volatilite spread, ADF).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
import pandas as pd
import numpy as np
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from optimizer import apply_overrides
from backtest_engine_numba import run_hybrid_backtest


# === Deux configs a comparer ===
CONFIGS = [
    {
        "name": "C6",
        "beta": 3960, "zp": 33, "cp": 27, "adf": 144,
        "zE": 3.25, "co": 45, "zTP": 0.0, "dTP": 250,
    },
    {
        "name": "C9",
        "beta": 4620, "zp": 30, "cp": 30, "adf": 96,
        "zE": 3.5, "co": 40, "zTP": 0.0, "dTP": 250,
    },
]

# === 5 fenetres ancrees expansives ===
WINDOWS = [
    {"train_start": "2023-01-01", "train_end": "2024-01-01", "test_start": "2024-01-01", "test_end": "2024-07-01"},
    {"train_start": "2023-01-01", "train_end": "2024-07-01", "test_start": "2024-07-01", "test_end": "2025-01-01"},
    {"train_start": "2023-01-01", "train_end": "2025-01-01", "test_start": "2025-01-01", "test_end": "2025-07-01"},
    {"train_start": "2023-01-01", "train_end": "2025-07-01", "test_start": "2025-07-01", "test_end": "2026-01-01"},
    {"train_start": "2023-01-01", "train_end": "2026-01-01", "test_start": "2026-01-01", "test_end": "2026-03-01"},
]


def build_overrides(cfg_params):
    """Construit le dictionnaire d'overrides a partir des parametres."""
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

    # Mapping zTP
    ztp_val = cfg_params["zTP"]
    overrides["exit.zscore_tp_long"] = ztp_val
    overrides["exit.zscore_tp_short"] = -ztp_val

    return overrides


def run_single_backtest(config_base, overrides, df_1min_global, df_5s_global):
    """Lance un backtest et retourne le DataFrame des trades."""
    cfg = apply_overrides(config_base, overrides)
    period = cfg["indicators"].get("period", "5min")
    if period == "5min":
        df_5min = resample_to_5min(df_1min_global)
        df_ind = calculate_all_indicators(df_5min, cfg)
    else:
        df_ind = calculate_all_indicators(df_1min_global, cfg)
    trades = run_hybrid_backtest(df_ind, df_5s_global, cfg, verbose=False)
    return trades, df_ind


def compute_pf(trades_df):
    """Calcule le Profit Factor."""
    if trades_df.empty:
        return 0
    wins = trades_df[trades_df["PnL_Net"] > 0]["PnL_Net"].sum()
    losses = abs(trades_df[trades_df["PnL_Net"] <= 0]["PnL_Net"].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0
    return wins / losses


def analyze_window_split(trades_df, window):
    """Decoupe les trades en train et test, retourne les metriques."""
    if trades_df.empty:
        return {"train": {}, "test": {}}

    trades_df = trades_df.copy()
    trades_df["entry_dt"] = pd.to_datetime(trades_df["Entry_DateTime"])

    train_start = pd.to_datetime(window["train_start"])
    train_end = pd.to_datetime(window["train_end"])
    test_start = pd.to_datetime(window["test_start"])
    test_end = pd.to_datetime(window["test_end"])

    train_trades = trades_df[(trades_df["entry_dt"] >= train_start) & (trades_df["entry_dt"] < train_end)]
    test_trades = trades_df[(trades_df["entry_dt"] >= test_start) & (trades_df["entry_dt"] < test_end)]

    def metrics(df, period_start, period_end):
        if df.empty:
            return {"trades": 0, "pnl": 0, "wr": 0, "pf": 0, "profitable": False, "days": 0}
        pnl = float(df["PnL_Net"].sum())
        wr = float((df["PnL_Net"] > 0).mean() * 100)
        pf = compute_pf(df)
        days = (period_end - period_start).days
        return {
            "trades": len(df),
            "pnl": pnl,
            "wr": wr,
            "pf": pf,
            "profitable": pnl > 0,
            "days": days,
        }

    return {
        "train": metrics(train_trades, train_start, train_end),
        "test": metrics(test_trades, test_start, test_end),
    }


def part1_walkforward(config_base, df_1min_global, df_5s_global):
    """Part 1: Walk-forward validation pour C6 et C9."""
    print("\n" + "=" * 80)
    print("PART 1: WALK-FORWARD VALIDATION (5 WINDOWS)")
    print("=" * 80)

    results = {}

    for cfg in CONFIGS:
        print(f"\n[{cfg['name']}] Running backtest...")
        overrides = build_overrides(cfg)
        trades_df, _ = run_single_backtest(config_base, overrides, df_1min_global, df_5s_global)
        print(f"  Total trades: {len(trades_df)}")

        window_results = []
        for i, window in enumerate(WINDOWS, 1):
            split = analyze_window_split(trades_df, window)
            window_results.append({
                "window_id": i,
                "window": window,
                "train": split["train"],
                "test": split["test"],
            })

            test = split["test"]
            profitable_str = "YES" if test["profitable"] else "NO"
            pf_str = "inf" if test["pf"] == float("inf") else f"{test['pf']:.2f}"
            print(f"  Window {i}: Test {test['trades']} trades, PnL ${test['pnl']:,.0f}, WR {test['wr']:.0f}%, PF {pf_str}, Profitable: {profitable_str}")

        # Calcul des agregats
        test_profitable_count = sum(1 for w in window_results if w["test"]["profitable"])
        test_profitable_pct = (test_profitable_count / len(WINDOWS)) * 100

        cumul_oos_pnl = sum(w["test"]["pnl"] for w in window_results)

        # OOS Sharpe (annualized)
        test_pnls = [w["test"]["pnl"] for w in window_results if w["test"]["trades"] > 0]
        avg_test_days = np.mean([w["test"]["days"] for w in window_results if w["test"]["trades"] > 0])
        if len(test_pnls) > 1 and np.std(test_pnls) > 0:
            oos_sharpe = (np.mean(test_pnls) / np.std(test_pnls)) * np.sqrt(252 / avg_test_days)
        else:
            oos_sharpe = 0

        # Performance degradation (first 2 vs last 2 windows)
        first_2_avg = np.mean([window_results[0]["test"]["pnl"], window_results[1]["test"]["pnl"]])
        last_2_avg = np.mean([window_results[3]["test"]["pnl"], window_results[4]["test"]["pnl"]])
        degradation_pct = ((last_2_avg - first_2_avg) / abs(first_2_avg) * 100) if first_2_avg != 0 else 0

        results[cfg["name"]] = {
            "cfg": cfg,
            "window_results": window_results,
            "test_profitable_count": test_profitable_count,
            "test_profitable_pct": test_profitable_pct,
            "cumul_oos_pnl": cumul_oos_pnl,
            "oos_sharpe": oos_sharpe,
            "first_2_avg": first_2_avg,
            "last_2_avg": last_2_avg,
            "degradation_pct": degradation_pct,
        }

    return results


def part2_investigation_2024(config_base, df_1min_global, df_5s_global):
    """Part 2: Investigation detaillee du regime 2024."""
    print("\n" + "=" * 80)
    print("PART 2: INVESTIGATION REGIME 2024")
    print("=" * 80)

    results = {}

    for cfg in CONFIGS:
        print(f"\n[{cfg['name']}] Running backtest...")
        overrides = build_overrides(cfg)
        trades_df, df_ind = run_single_backtest(config_base, overrides, df_1min_global, df_5s_global)

        trades_df = trades_df.copy()
        trades_df["entry_dt"] = pd.to_datetime(trades_df["Entry_DateTime"])
        trades_df["year"] = trades_df["entry_dt"].dt.year
        trades_df["month"] = trades_df["entry_dt"].dt.to_period("M")

        # A) Trades par mois en 2024
        trades_2024 = trades_df[trades_df["year"] == 2024]
        if not trades_2024.empty:
            monthly_2024 = trades_2024.groupby("month").agg(
                trades=("PnL_Net", "count"),
                pnl=("PnL_Net", "sum"),
            )
        else:
            monthly_2024 = pd.DataFrame()

        # B) Losing trades en 2024
        losing_2024 = trades_2024[trades_2024["PnL_Net"] <= 0]
        if not losing_2024.empty:
            avg_entry_zscore = float(losing_2024["Entry_ZScore"].abs().mean())
            avg_duration_min = float(losing_2024["Duration_Min"].mean())
            exit_breakdown = losing_2024["Exit_Reason"].value_counts().to_dict()
        else:
            avg_entry_zscore = 0
            avg_duration_min = 0
            exit_breakdown = {}

        # C) Spread volatility par annee
        df_ind_copy = df_ind.copy()
        if "DateTime" in df_ind_copy.columns:
            df_ind_copy = df_ind_copy.set_index("DateTime")
        df_ind_copy.index = pd.to_datetime(df_ind_copy.index)
        df_ind_copy["year"] = df_ind_copy.index.year

        spread_vol_by_year = {}
        for year in sorted(df_ind_copy["year"].unique()):
            df_year = df_ind_copy[df_ind_copy["year"] == year]
            # Resampler a daily, calculer std des changements daily
            daily_spread = df_year["Spread"].resample("D").last().dropna()
            if len(daily_spread) > 1:
                daily_returns = daily_spread.diff().dropna()
                spread_vol = float(daily_returns.std())
            else:
                spread_vol = 0
            spread_vol_by_year[year] = spread_vol

        # D) ADF stationarity par annee
        adf_by_year = {}
        for year in sorted(df_ind_copy["year"].unique()):
            df_year = df_ind_copy[df_ind_copy["year"] == year]
            avg_adf = float(df_year["ADF_Statistic"].mean())
            adf_by_year[year] = avg_adf

        results[cfg["name"]] = {
            "monthly_2024": monthly_2024,
            "losing_2024": {
                "count": len(losing_2024),
                "avg_entry_zscore": avg_entry_zscore,
                "avg_duration_min": avg_duration_min,
                "exit_breakdown": exit_breakdown,
            },
            "spread_vol_by_year": spread_vol_by_year,
            "adf_by_year": adf_by_year,
        }

    return results


def format_report(wf_results, inv_results, output_path):
    """Genere le rapport markdown."""
    lines = []
    lines.append("# Walk-Forward Validation C6 vs C9 + Investigation Regime 2024")
    lines.append("")
    lines.append("Date: 2026-02-14")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("**C6**: beta=3960, zp=33, cp=27, adf=144, zE=3.25, co=45, zTP=0.0, dTP=250")
    lines.append("")
    lines.append("**C9**: beta=4620, zp=30, cp=30, adf=96, zE=3.5, co=40, zTP=0.0, dTP=250")
    lines.append("")
    lines.append("Parametres fixes (identiques pour les deux):")
    lines.append("- Contract mode: micro")
    lines.append("- Micro multiplier max: 2")
    lines.append("- Slippage: 1 tick per leg")
    lines.append("- zSL: -99/+99 (disabled)")
    lines.append("- dSL: -99999 (disabled)")
    lines.append("- max_holding_bars: 0 (disabled)")
    lines.append("- flat_end_of_session: True")
    lines.append("")

    # === PART 1 ===
    lines.append("# PART 1: WALK-FORWARD VALIDATION")
    lines.append("")
    lines.append("## Schema des fenetres (anchored expanding)")
    lines.append("")
    lines.append("```")
    for i, w in enumerate(WINDOWS, 1):
        lines.append(f"Window {i}:")
        lines.append(f"  Train: {w['train_start']} to {w['train_end']}")
        lines.append(f"  Test:  {w['test_start']} to {w['test_end']}")
    lines.append("```")
    lines.append("")

    # Tableau comparatif par fenetre
    lines.append("## Resultats par fenetre")
    lines.append("")

    for cfg_name in ["C6", "C9"]:
        lines.append(f"### {cfg_name}")
        lines.append("")
        lines.append("| Window | Train PnL | Test Trades | Test PnL | Test WR | Test PF | Profitable |")
        lines.append("|--------|-----------|-------------|----------|---------|---------|------------|")

        wf = wf_results[cfg_name]
        for w in wf["window_results"]:
            train = w["train"]
            test = w["test"]
            pf_str = "inf" if test["pf"] == float("inf") else f"{test['pf']:.2f}"
            profitable_str = "YES" if test["profitable"] else "NO"
            lines.append(
                f"| {w['window_id']} | ${train['pnl']:,.0f} | {test['trades']} | ${test['pnl']:,.0f} | {test['wr']:.0f}% | {pf_str} | {profitable_str} |"
            )
        lines.append("")

    # Tableau comparatif agregats
    lines.append("## Agregats OOS (Out-of-Sample)")
    lines.append("")
    lines.append("| Config | Windows Profitable | Cumul OOS PnL | OOS Sharpe | First 2 Avg | Last 2 Avg | Degradation |")
    lines.append("|--------|--------------------|---------------|------------|-------------|------------|-------------|")

    for cfg_name in ["C6", "C9"]:
        wf = wf_results[cfg_name]
        deg_str = f"{wf['degradation_pct']:+.1f}%" if abs(wf['degradation_pct']) != float('inf') else "N/A"
        lines.append(
            f"| {cfg_name} | {wf['test_profitable_count']}/5 ({wf['test_profitable_pct']:.0f}%) | ${wf['cumul_oos_pnl']:,.0f} | {wf['oos_sharpe']:.2f} | ${wf['first_2_avg']:,.0f} | ${wf['last_2_avg']:,.0f} | {deg_str} |"
        )

    lines.append("")

    # === PART 2 ===
    lines.append("# PART 2: INVESTIGATION REGIME 2024")
    lines.append("")

    # A) Trades par mois en 2024
    lines.append("## A) Trades par mois en 2024")
    lines.append("")

    for cfg_name in ["C6", "C9"]:
        lines.append(f"### {cfg_name}")
        lines.append("")
        inv = inv_results[cfg_name]
        monthly = inv["monthly_2024"]
        if not monthly.empty:
            lines.append("| Month | Trades | PnL |")
            lines.append("|-------|--------|-----|")
            for month, row in monthly.iterrows():
                lines.append(f"| {month} | {row['trades']} | ${row['pnl']:,.0f} |")
        else:
            lines.append("Aucun trade en 2024.")
        lines.append("")

    # B) Losing trades 2024
    lines.append("## B) Losing trades en 2024")
    lines.append("")
    lines.append("| Config | Count | Avg Entry ZScore (abs) | Avg Duration (min) | Exit Type Breakdown |")
    lines.append("|--------|-------|------------------------|--------------------|--------------------|")

    for cfg_name in ["C6", "C9"]:
        inv = inv_results[cfg_name]
        losing = inv["losing_2024"]
        exit_str = ", ".join([f"{k}={v}" for k, v in losing["exit_breakdown"].items()])
        if not exit_str:
            exit_str = "N/A"
        lines.append(
            f"| {cfg_name} | {losing['count']} | {losing['avg_entry_zscore']:.2f} | {losing['avg_duration_min']:.0f} | {exit_str} |"
        )

    lines.append("")

    # C) Spread volatility par annee
    lines.append("## C) Spread volatility par annee (std daily changes)")
    lines.append("")
    lines.append("| Config | 2023 | 2024 | 2025 | 2026 |")
    lines.append("|--------|------|------|------|------|")

    for cfg_name in ["C6", "C9"]:
        inv = inv_results[cfg_name]
        vol = inv["spread_vol_by_year"]
        row = [cfg_name]
        for year in [2023, 2024, 2025, 2026]:
            v = vol.get(year, 0)
            row.append(f"{v:.2f}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # D) ADF stationarity par annee
    lines.append("## D) ADF stationarity par annee (avg ADF_Statistic)")
    lines.append("")
    lines.append("| Config | 2023 | 2024 | 2025 | 2026 |")
    lines.append("|--------|------|------|------|------|")

    for cfg_name in ["C6", "C9"]:
        inv = inv_results[cfg_name]
        adf = inv["adf_by_year"]
        row = [cfg_name]
        for year in [2023, 2024, 2025, 2026]:
            a = adf.get(year, 0)
            row.append(f"{a:.2f}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("---")
    lines.append("*Genere par walkforward_c6_c9.py*")

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("\n" + "=" * 80)
    print("RAPPORT GENERE")
    print("=" * 80)
    print(report)
    return report


# === MAIN ===
if __name__ == "__main__":
    print("=" * 80)
    print("WALK-FORWARD VALIDATION C6 vs C9 + INVESTIGATION REGIME 2024")
    print("=" * 80)

    # Charger les donnees une seule fois
    print("\nChargement des donnees...")
    config_path = "config/strategy_params.yaml"
    with open(config_path, encoding="utf-8") as f:
        config_base = yaml.safe_load(f)

    df_1min_global, config_base, _ = load_and_prepare_data(config_path)
    df_5s_global = load_5s_data(config_base)
    print(f"  {len(df_1min_global):,} barres 1-min, {len(df_5s_global):,} barres 5s")

    # Part 1: Walk-forward
    wf_results = part1_walkforward(config_base, df_1min_global, df_5s_global)

    # Part 2: Investigation 2024
    inv_results = part2_investigation_2024(config_base, df_1min_global, df_5s_global)

    # Generer le rapport
    format_report(wf_results, inv_results, "output/reports/WALKFORWARD_C6_C9.md")
    print("\n[OK] Rapport sauvegarde dans output/reports/WALKFORWARD_C6_C9.md")
