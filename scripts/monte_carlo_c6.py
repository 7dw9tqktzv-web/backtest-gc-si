"""
Monte Carlo Bootstrap - C6 Config
Simule 1000 chemins de 200 trades tires avec remplacement.
Analyse: distribution PnL/DD/Sharpe, risque prop firm, objectif $300/jour.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from optimizer import apply_overrides
from backtest_engine_numba import run_hybrid_backtest


# --- Config C6 ---
C6_CONFIG = {
    "name": "C6_b3960_zp33_cp27_adf144_dTP250",
    "beta": 3960,
    "zp": 33,
    "cp": 27,
    "adf": 144,
    "zE": 3.25,
    "co": 45,
    "zTP": 0.0,
    "dTP": 250,
}


def build_c6_overrides():
    """Construit les overrides pour C6."""
    return {
        "indicators.beta_lookback": C6_CONFIG["beta"],
        "indicators.zscore_period": C6_CONFIG["zp"],
        "indicators.correlation_period": C6_CONFIG["cp"],
        "indicators.adf_hurst_period": C6_CONFIG["adf"],
        "entry.zscore_long": -C6_CONFIG["zE"],
        "entry.zscore_short": C6_CONFIG["zE"],
        "entry.cointegration_score_min": C6_CONFIG["co"],
        "exit.zscore_tp_enabled": True,
        "exit.zscore_tp_long": C6_CONFIG["zTP"],
        "exit.zscore_tp_short": -C6_CONFIG["zTP"],
        "exit.pnl_take_profit": C6_CONFIG["dTP"],
        # Parametres fixes
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


def run_c6_backtest(config_base, df_1min, df_5s):
    """Lance le backtest C6 et retourne les trades."""
    overrides = build_c6_overrides()
    cfg = apply_overrides(config_base, overrides)
    df_5min = resample_to_5min(df_1min)
    df_ind = calculate_all_indicators(df_5min, cfg)
    trades = run_hybrid_backtest(df_ind, df_5s, cfg, verbose=False)
    return trades


def calculate_max_drawdown(pnl_cumulative):
    """Calcule le drawdown max d'une serie de PnL cumulatif."""
    running_max = np.maximum.accumulate(pnl_cumulative)
    drawdown = pnl_cumulative - running_max
    return drawdown.min()


def calculate_sharpe(pnl_array, trades_per_year=86):
    """
    Calcule le Sharpe ratio annualise.
    trades_per_year = 258 trades / 3 ans = 86 trades/an
    Sharpe = mean(PnL) / std(PnL) * sqrt(trades_per_year)
    """
    if len(pnl_array) == 0 or np.std(pnl_array) == 0:
        return 0.0
    return np.mean(pnl_array) / np.std(pnl_array) * np.sqrt(trades_per_year)


def run_monte_carlo(pnl_net_array, n_paths=1000, n_trades=200, seed=42):
    """
    Bootstrap i.i.d. Monte Carlo.
    """
    np.random.seed(seed)

    # Tirer tous les indices d'un coup (vectorise)
    indices = np.random.choice(len(pnl_net_array), size=(n_paths, n_trades), replace=True)

    # Construire les chemins de PnL
    paths_pnl_individual = pnl_net_array[indices]  # (n_paths, n_trades)
    paths_pnl_cumulative = np.cumsum(paths_pnl_individual, axis=1)  # (n_paths, n_trades)

    # Calculer DD pour chaque chemin
    paths_dd = np.array([calculate_max_drawdown(path) for path in paths_pnl_cumulative])

    # Calculer Sharpe pour chaque chemin
    paths_sharpe = np.array([calculate_sharpe(path) for path in paths_pnl_individual])

    return {
        "paths_pnl_cumulative": paths_pnl_cumulative,
        "paths_pnl_individual": paths_pnl_individual,
        "paths_dd": paths_dd,
        "paths_sharpe": paths_sharpe,
    }


def run_block_bootstrap(pnl_net_array, n_paths=1000, n_trades=200, block_size=5, seed=42):
    """
    Block bootstrap Monte Carlo — preserve l'autocorrelation temporelle.
    Tire des blocs de k trades consecutifs avec remplacement.
    """
    np.random.seed(seed)
    n_real = len(pnl_net_array)
    # Nombre de blocs necessaires par chemin (arrondi au-dessus)
    blocks_per_path = int(np.ceil(n_trades / block_size))

    paths_pnl_individual = np.zeros((n_paths, n_trades))

    for p in range(n_paths):
        # Tirer des indices de debut de bloc
        starts = np.random.randint(0, n_real - block_size + 1, size=blocks_per_path)
        # Construire le chemin en concatenant les blocs
        trades_list = []
        for s in starts:
            trades_list.extend(pnl_net_array[s:s + block_size].tolist())
        paths_pnl_individual[p] = trades_list[:n_trades]

    paths_pnl_cumulative = np.cumsum(paths_pnl_individual, axis=1)
    paths_dd = np.array([calculate_max_drawdown(path) for path in paths_pnl_cumulative])
    paths_sharpe = np.array([calculate_sharpe(path) for path in paths_pnl_individual])

    return {
        "paths_pnl_cumulative": paths_pnl_cumulative,
        "paths_pnl_individual": paths_pnl_individual,
        "paths_dd": paths_dd,
        "paths_sharpe": paths_sharpe,
    }


def analyze_distribution(mc_results, report_lines):
    """Section A: Distribution des resultats sur 200 trades."""
    pnl_final = mc_results["paths_pnl_cumulative"][:, -1]  # PnL a la fin de chaque chemin
    dd = mc_results["paths_dd"]
    sharpe = mc_results["paths_sharpe"]

    report_lines.append("## A) Distribution des resultats sur 200 trades")
    report_lines.append("")
    report_lines.append("| Metrique | Median | P5 | P25 | P75 | P95 |")
    report_lines.append("|----------|--------|----|----|----|----|")

    report_lines.append(
        f"| PnL final ($) | ${np.median(pnl_final):,.0f} | "
        f"${np.percentile(pnl_final, 5):,.0f} | "
        f"${np.percentile(pnl_final, 25):,.0f} | "
        f"${np.percentile(pnl_final, 75):,.0f} | "
        f"${np.percentile(pnl_final, 95):,.0f} |"
    )

    report_lines.append(
        f"| Max DD ($) | ${np.median(dd):,.0f} | "
        f"${np.percentile(dd, 5):,.0f} | "
        f"${np.percentile(dd, 25):,.0f} | "
        f"${np.percentile(dd, 75):,.0f} | "
        f"${np.percentile(dd, 95):,.0f} |"
    )

    report_lines.append(
        f"| Sharpe | {np.median(sharpe):.2f} | "
        f"{np.percentile(sharpe, 5):.2f} | "
        f"{np.percentile(sharpe, 25):.2f} | "
        f"{np.percentile(sharpe, 75):.2f} | "
        f"{np.percentile(sharpe, 95):.2f} |"
    )

    report_lines.append("")


def analyze_prop_firm_risk(mc_results, report_lines):
    """Section B: Risque prop firm."""
    paths_pnl_cumulative = mc_results["paths_pnl_cumulative"]
    n_paths = len(paths_pnl_cumulative)

    # Pour chaque chemin, calculer le running DD a chaque trade
    running_max = np.maximum.accumulate(paths_pnl_cumulative, axis=1)
    running_dd = paths_pnl_cumulative - running_max  # (n_paths, n_trades)

    # Compter les chemins qui atteignent -$3000 ou -$5000 a un moment donne
    hit_3k = np.any(running_dd <= -3000, axis=1).sum()
    hit_5k = np.any(running_dd <= -5000, axis=1).sum()

    # Profitabilite apres N trades
    profit_50 = (paths_pnl_cumulative[:, 49] > 0).sum()  # index 49 = 50eme trade
    profit_100 = (paths_pnl_cumulative[:, 99] > 0).sum()
    profit_200 = (paths_pnl_cumulative[:, 199] > 0).sum()

    report_lines.append("## B) Risque prop firm")
    report_lines.append("")
    report_lines.append("| Critere | % Chemins |")
    report_lines.append("|---------|-----------|")
    report_lines.append(f"| Hit -$3,000 DD | {hit_3k / n_paths * 100:.1f}% ({hit_3k}/{n_paths}) |")
    report_lines.append(f"| Hit -$5,000 DD | {hit_5k / n_paths * 100:.1f}% ({hit_5k}/{n_paths}) |")
    report_lines.append(f"| Profitable apres 50 trades | {profit_50 / n_paths * 100:.1f}% ({profit_50}/{n_paths}) |")
    report_lines.append(f"| Profitable apres 100 trades | {profit_100 / n_paths * 100:.1f}% ({profit_100}/{n_paths}) |")
    report_lines.append(f"| Profitable apres 200 trades | {profit_200 / n_paths * 100:.1f}% ({profit_200}/{n_paths}) |")
    report_lines.append("")


def analyze_daily_objective(pnl_net_array, report_lines):
    """Section C: Objectif $300/jour."""
    pnl_mean = np.mean(pnl_net_array)

    # Trades necessaires par jour pour atteindre $300
    trades_needed_per_day = 300 / pnl_mean if pnl_mean > 0 else float("inf")

    # Realite: ~8 trades/mois = 0.36 trades/jour (258 trades / 3 ans / 12 mois * 12 / 36 mois)
    # Simplifie: 258 trades / (3 * 365.25) jours
    trades_per_day_observed = 258 / (3 * 365.25)
    daily_revenue = trades_per_day_observed * pnl_mean

    report_lines.append("## C) Objectif $300/jour")
    report_lines.append("")
    report_lines.append(f"- **PnL moyen par trade**: ${pnl_mean:.2f}")
    report_lines.append(f"- **Trades necessaires par jour**: {trades_needed_per_day:.2f}")
    report_lines.append(f"- **Trades observes par jour**: {trades_per_day_observed:.2f} (~{trades_per_day_observed * 30:.1f}/mois)")
    report_lines.append(f"- **Revenue journalier estime**: ${daily_revenue:.2f}")
    report_lines.append("")

    if daily_revenue >= 300:
        report_lines.append("**Conclusion**: Objectif $300/jour ATTEINT avec la frequence actuelle.")
    else:
        shortfall = 300 - daily_revenue
        report_lines.append(f"**Conclusion**: Objectif $300/jour NON ATTEINT. Manque ${shortfall:.2f}/jour.")
        report_lines.append(f"  - Pour atteindre $300/jour, il faudrait {trades_needed_per_day:.2f} trades/jour (actuellement {trades_per_day_observed:.2f}).")
        multiplier = trades_needed_per_day / trades_per_day_observed
        report_lines.append(f"  - Soit **{multiplier:.1f}x plus de trades** que le rythme actuel.")

    report_lines.append("")


def plot_equity_curves(mc_results, output_path):
    """Section D: Equity curves (plot + table percentiles)."""
    paths_pnl_cumulative = mc_results["paths_pnl_cumulative"]
    n_trades = paths_pnl_cumulative.shape[1]

    # Calculer les percentiles a chaque trade
    p5 = np.percentile(paths_pnl_cumulative, 5, axis=0)
    p25 = np.percentile(paths_pnl_cumulative, 25, axis=0)
    p50 = np.percentile(paths_pnl_cumulative, 50, axis=0)
    p75 = np.percentile(paths_pnl_cumulative, 75, axis=0)
    p95 = np.percentile(paths_pnl_cumulative, 95, axis=0)

    # Graphique
    plt.figure(figsize=(12, 6))
    trade_idx = np.arange(1, n_trades + 1)

    plt.plot(trade_idx, p50, color="blue", linewidth=2, label="P50 (Median)")
    plt.plot(trade_idx, p25, color="orange", linewidth=1, label="P25")
    plt.plot(trade_idx, p75, color="green", linewidth=1, label="P75")
    plt.plot(trade_idx, p5, color="red", linestyle="--", linewidth=1, label="P5")
    plt.plot(trade_idx, p95, color="green", linestyle="--", linewidth=1, label="P95")
    plt.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7)

    plt.xlabel("Trade #")
    plt.ylabel("Cumulative PnL ($)")
    plt.title("Monte Carlo C6 - Equity Curve Percentiles (1000 paths)")
    plt.legend(loc="best")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()

    # Table texte tous les 10 trades
    report_lines = []
    report_lines.append("## D) Equity curves (percentiles)")
    report_lines.append("")
    report_lines.append("### Table percentiles (tous les 10 trades)")
    report_lines.append("")
    report_lines.append("| Trade # | P5 | P25 | P50 (Median) | P75 | P95 |")
    report_lines.append("|---------|----|----|--------------|-----|-----|")

    for i in range(0, n_trades, 10):
        if i == 0:
            i = 1  # Premier trade = index 0, mais on l'affiche comme "Trade 1"
        idx = i - 1
        report_lines.append(
            f"| {i} | ${p5[idx]:,.0f} | ${p25[idx]:,.0f} | ${p50[idx]:,.0f} | ${p75[idx]:,.0f} | ${p95[idx]:,.0f} |"
        )

    # Ajouter le dernier trade (200)
    report_lines.append(
        f"| 200 | ${p5[-1]:,.0f} | ${p25[-1]:,.0f} | ${p50[-1]:,.0f} | ${p75[-1]:,.0f} | ${p95[-1]:,.0f} |"
    )

    report_lines.append("")
    report_lines.append(f"**Graphique sauvegarde**: `{output_path}`")
    report_lines.append("")

    return report_lines


def analyze_comparison(mc_iid, mc_block, report_lines):
    """Section E: Comparaison i.i.d. vs Block Bootstrap."""
    report_lines.append("## E) Comparaison i.i.d. vs Block Bootstrap (k=5)")
    report_lines.append("")
    report_lines.append("| Metrique | i.i.d. | Block k=5 | Ratio |")
    report_lines.append("|----------|--------|-----------|-------|")

    pnl_iid = mc_iid["paths_pnl_cumulative"][:, -1]
    pnl_blk = mc_block["paths_pnl_cumulative"][:, -1]
    report_lines.append(
        f"| PnL median | ${np.median(pnl_iid):,.0f} | ${np.median(pnl_blk):,.0f} | "
        f"{np.median(pnl_blk)/np.median(pnl_iid):.2f}x |"
    )
    report_lines.append(
        f"| PnL P5 (worst) | ${np.percentile(pnl_iid, 5):,.0f} | ${np.percentile(pnl_blk, 5):,.0f} | "
        f"{np.percentile(pnl_blk, 5)/max(np.percentile(pnl_iid, 5), 1):.2f}x |"
    )

    dd_iid = mc_iid["paths_dd"]
    dd_blk = mc_block["paths_dd"]
    report_lines.append(
        f"| MaxDD median | ${np.median(dd_iid):,.0f} | ${np.median(dd_blk):,.0f} | "
        f"{np.median(dd_blk)/np.median(dd_iid):.2f}x |"
    )
    report_lines.append(
        f"| MaxDD P5 (worst) | ${np.percentile(dd_iid, 5):,.0f} | ${np.percentile(dd_blk, 5):,.0f} | "
        f"{np.percentile(dd_blk, 5)/np.percentile(dd_iid, 5):.2f}x |"
    )

    sh_iid = mc_iid["paths_sharpe"]
    sh_blk = mc_block["paths_sharpe"]
    report_lines.append(
        f"| Sharpe median | {np.median(sh_iid):.2f} | {np.median(sh_blk):.2f} | "
        f"{np.median(sh_blk)/np.median(sh_iid):.2f}x |"
    )

    # Risque prop firm comparison
    run_max_iid = np.maximum.accumulate(mc_iid["paths_pnl_cumulative"], axis=1)
    run_dd_iid = mc_iid["paths_pnl_cumulative"] - run_max_iid
    run_max_blk = np.maximum.accumulate(mc_block["paths_pnl_cumulative"], axis=1)
    run_dd_blk = mc_block["paths_pnl_cumulative"] - run_max_blk

    hit3k_iid = np.any(run_dd_iid <= -3000, axis=1).sum()
    hit3k_blk = np.any(run_dd_blk <= -3000, axis=1).sum()
    prof200_iid = (mc_iid["paths_pnl_cumulative"][:, -1] > 0).sum()
    prof200_blk = (mc_block["paths_pnl_cumulative"][:, -1] > 0).sum()
    n = len(pnl_iid)

    report_lines.append(
        f"| Hit -$3K DD | {hit3k_iid/n*100:.1f}% | {hit3k_blk/n*100:.1f}% | "
        f"{max(hit3k_blk, 1)/max(hit3k_iid, 1):.1f}x |"
    )
    report_lines.append(
        f"| Profitable 200 trades | {prof200_iid/n*100:.1f}% | {prof200_blk/n*100:.1f}% | - |"
    )
    report_lines.append("")


def generate_report(mc_iid, mc_block, pnl_net_array, output_path):
    """Genere le rapport markdown complet avec i.i.d. + block bootstrap."""
    report_lines = []
    report_lines.append("# Monte Carlo Bootstrap - C6 Config (i.i.d. + Block k=5)")
    report_lines.append("")
    report_lines.append("Date: 2026-02-14")
    report_lines.append("")
    report_lines.append("## Configuration")
    report_lines.append("")
    report_lines.append(f"- **Config**: {C6_CONFIG['name']}")
    report_lines.append(f"- **Parametres**: beta={C6_CONFIG['beta']}, zp={C6_CONFIG['zp']}, cp={C6_CONFIG['cp']}, adf={C6_CONFIG['adf']}")
    report_lines.append(f"- **Entree**: zE={C6_CONFIG['zE']}, co={C6_CONFIG['co']}")
    report_lines.append(f"- **Sortie**: zTP={C6_CONFIG['zTP']}, dTP=${C6_CONFIG['dTP']}")
    report_lines.append("- **Contract mode**: micro (MGC/SIL)")
    report_lines.append("- **Micro multiplier max**: 2")
    report_lines.append("- **Slippage**: 1 tick per leg")
    report_lines.append("- **Autres**: zSL=-99/+99, dSL=-99999, mhb=0, flat_end_of_session=True")
    report_lines.append("")
    report_lines.append("## Methodologie")
    report_lines.append("")
    report_lines.append(f"- **Nombre de trades reels**: {len(pnl_net_array)}")
    report_lines.append("- **Nombre de chemins**: 1,000 par methode")
    report_lines.append("- **Trades par chemin**: 200 (tires avec remplacement)")
    report_lines.append("- **Methode 1**: i.i.d. (trades independants)")
    report_lines.append("- **Methode 2**: Block bootstrap k=5 (blocs de 5 trades consecutifs)")
    report_lines.append("- **Random seed**: 42")
    report_lines.append("")

    # ---- i.i.d. ----
    report_lines.append("---")
    report_lines.append("# METHODE 1 : Bootstrap i.i.d.")
    report_lines.append("")
    analyze_distribution(mc_iid, report_lines)
    analyze_prop_firm_risk(mc_iid, report_lines)
    analyze_daily_objective(pnl_net_array, report_lines)
    plot_path_iid = "output/reports/monte_carlo_c6_equity_iid.png"
    equity_lines = plot_equity_curves(mc_iid, plot_path_iid)
    report_lines.extend(equity_lines)

    # ---- Block k=5 ----
    report_lines.append("---")
    report_lines.append("# METHODE 2 : Block Bootstrap k=5")
    report_lines.append("")
    analyze_distribution(mc_block, report_lines)
    analyze_prop_firm_risk(mc_block, report_lines)
    plot_path_block = "output/reports/monte_carlo_c6_equity_block.png"
    equity_lines_block = plot_equity_curves(mc_block, plot_path_block)
    report_lines.extend(equity_lines_block)

    # ---- Comparison ----
    report_lines.append("---")
    report_lines.append("# COMPARAISON")
    report_lines.append("")
    analyze_comparison(mc_iid, mc_block, report_lines)

    report_lines.append("---")
    report_lines.append("*Genere par monte_carlo_c6.py*")

    report_text = "\n".join(report_lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return report_text


# === MAIN ===
if __name__ == "__main__":
    print("=" * 80)
    print("MONTE CARLO BOOTSTRAP - C6 CONFIG")
    print("=" * 80)

    # Charger les donnees
    print("\nChargement des donnees...")
    config_path = "config/strategy_params.yaml"
    with open(config_path, encoding="utf-8") as f:
        config_base = yaml.safe_load(f)

    df_1min, config_base, _ = load_and_prepare_data(config_path)
    df_5s = load_5s_data(config_base)
    print(f"  {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s")

    # Backtest C6
    print("\nBacktest C6...")
    trades_df = run_c6_backtest(config_base, df_1min, df_5s)
    print(f"  {len(trades_df)} trades")

    if trades_df.empty:
        print("\n[ERREUR] Aucun trade trouve. Impossible de lancer le Monte Carlo.")
        sys.exit(1)

    # Extraire les PnL
    pnl_net_array = trades_df["PnL_Net"].values
    print(f"  PnL moyen: ${np.mean(pnl_net_array):.2f}")
    print(f"  PnL total: ${np.sum(pnl_net_array):,.0f}")

    # Monte Carlo i.i.d.
    print("\nMonte Carlo i.i.d. (1000 paths x 200 trades)...")
    mc_iid = run_monte_carlo(pnl_net_array, n_paths=1000, n_trades=200, seed=42)
    print("  [OK] i.i.d. termine")

    # Block Bootstrap k=5
    print("\nBlock Bootstrap k=5 (1000 paths x 200 trades)...")
    mc_block = run_block_bootstrap(pnl_net_array, n_paths=1000, n_trades=200, block_size=5, seed=42)
    print("  [OK] Block bootstrap termine")

    # Generer le rapport
    print("\nGeneration du rapport...")
    output_path = "output/reports/MONTE_CARLO_C6.md"
    report = generate_report(mc_iid, mc_block, pnl_net_array, output_path)

    print("\n" + "=" * 80)
    print(report)
    print("=" * 80)
    print(f"\n[OK] Rapport sauvegarde: {output_path}")
    print("[OK] Graphiques sauvegardes: output/reports/monte_carlo_c6_equity_iid.png + _block.png")
