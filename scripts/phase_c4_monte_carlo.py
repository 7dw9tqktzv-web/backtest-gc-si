#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ============================================================================
# PHASE C4 : MONTE CARLO BOOTSTRAP (1000 simulations)
# ============================================================================
#
# Reechantillonne les trades reels (avec remise) pour estimer la distribution
# de performance et quantifier le risque.
#
# Source des trades : backtest complet 3 ans avec la config la plus frequemment
# selectionnee en walk-forward (zTP-1.0_b2640_zp20_cp30_adf26_co40_zSL4.0,
# 13/34 fenetres WF).
#
# Usage : python scripts/phase_c4_monte_carlo.py
# ============================================================================

import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

# -- Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides

# -- Config de la simulation
N_SIMULATIONS = 1000
SEED = 42
HORIZONS = [50, 100, 150, 200]

# Config la plus frequente en WF 5min zTP (13/34 fenetres)
WF_CONFIG_LABEL = "zTP-1.0_b2640_zp20_cp30_adf26_co40_zSL4.0"
WF_CONFIG_OVERRIDES = {
    "indicators.period": "5min",
    "indicators.beta_lookback": 2640,
    "indicators.zscore_period": 20,
    "indicators.correlation_period": 30,
    "indicators.adf_hurst_period": 26,
    "entry.zscore_long": -3.5,
    "entry.zscore_short": 3.5,
    "entry.cointegration_score_min": 40,
    "exit.zscore_tp_enabled": True,
    "exit.zscore_tp_long": 1.0,      # zTP -1.0 = overshoot (long sort a z=+1.0)
    "exit.zscore_tp_short": -1.0,    # (short sort a z=-1.0)
    "exit.zscore_sl_long": -4.0,
    "exit.zscore_sl_short": 4.0,
    "exit.pnl_take_profit": 99999,
    "exit.pnl_stop_loss": -99999,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}


def load_trades():
    """Charge les donnees et lance le backtest pour obtenir les trades individuels."""
    print("=" * 60)
    print("  PHASE C4 : CHARGEMENT DES DONNEES")
    print("=" * 60)

    # Charger les donnees 1-min
    df_1min, config, stats = load_and_prepare_data(verbose=True)

    # Resampler en 5-min
    df_5min = resample_to_5min(df_1min, verbose=True)

    # Charger les donnees 5s
    df_5s = load_5s_data(config, verbose=True)

    # Appliquer les overrides de la config WF
    cfg = apply_overrides(config, WF_CONFIG_OVERRIDES)

    print(f"\n   Config : {WF_CONFIG_LABEL}")
    print(f"   Timeframe : 5min")
    print(f"   Slippage : 2 ticks")

    # Calculer les indicateurs sur 5-min
    df_5min = calculate_all_indicators(df_5min, cfg, verbose=True)

    # Lancer le backtest
    print("\n   Lancement du backtest hybride...")
    trades_df = run_hybrid_backtest(df_5min, df_5s, cfg, verbose=True)

    return trades_df


def print_trade_stats(pnls, directions=None, source_label="backtest complet 3 ans"):
    """Affiche les statistiques de base des trades."""
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    print(f"\n   Source : {source_label}")
    print(f"   Nombre de trades : {len(pnls)}")
    print(f"   PnL moyen  : ${pnls.mean():,.0f}")
    print(f"   PnL median : ${np.median(pnls):,.0f}")
    print(f"   PnL std    : ${pnls.std():,.0f}")
    print(f"   Win Rate   : {100 * len(wins) / len(pnls):.1f}%")
    print(f"   Plus gros gain  : ${pnls.max():,.0f}")
    print(f"   Plus grosse perte : ${pnls.min():,.0f}")

    if directions is not None:
        n_long = (directions == "LONG").sum()
        n_short = (directions == "SHORT").sum()
        print(f"   Directions : {n_long} LONG, {n_short} SHORT")


def monte_carlo_bootstrap(trade_pnls, n_simulations=1000, horizons=None):
    """
    Monte Carlo bootstrap : tire n_trades PnL au hasard avec remise,
    calcule le PnL cumule et le max drawdown de chaque simulation.
    """
    if horizons is None:
        horizons = HORIZONS

    np.random.seed(SEED)
    results = {}

    for n_trades in horizons:
        cumulative_pnls = np.empty(n_simulations)
        max_drawdowns = np.empty(n_simulations)

        for i in range(n_simulations):
            sampled = np.random.choice(trade_pnls, size=n_trades, replace=True)
            cumulative = np.cumsum(sampled)
            cumulative_pnls[i] = cumulative[-1]
            # Max drawdown
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = cumulative - running_max
            max_drawdowns[i] = drawdowns.min()

        results[n_trades] = {
            "cumulative_pnls": cumulative_pnls,
            "max_drawdowns": max_drawdowns,
        }

    return results


def print_results(results, trade_pnls, source_label):
    """Affiche les tableaux de resultats Monte Carlo."""
    print("\n" + "=" * 80)
    print(f"  MONTE CARLO BOOTSTRAP - {N_SIMULATIONS} simulations")
    print(f"  Source : {source_label}")
    print(f"  Trades source : {len(trade_pnls)} trades, "
          f"PnL moyen ${trade_pnls.mean():,.0f}, "
          f"WR {100 * (trade_pnls > 0).sum() / len(trade_pnls):.0f}%")
    print("=" * 80)

    # -- Tableau PnL
    print(f"\n{'Horizon':>12} | {'P(perte)':>8} | {'PnL P5':>10} | {'PnL P25':>10} | "
          f"{'PnL Median':>10} | {'PnL P75':>10} | {'PnL P95':>10}")
    print("-" * 80)

    for h in HORIZONS:
        pnls = results[h]["cumulative_pnls"]
        p_loss = 100 * (pnls < 0).sum() / len(pnls)
        p5 = np.percentile(pnls, 5)
        p25 = np.percentile(pnls, 25)
        p50 = np.percentile(pnls, 50)
        p75 = np.percentile(pnls, 75)
        p95 = np.percentile(pnls, 95)
        print(f"{h:>9} tr | {p_loss:>7.1f}% | ${p5:>9,.0f} | ${p25:>9,.0f} | "
              f"${p50:>9,.0f} | ${p75:>9,.0f} | ${p95:>9,.0f}")

    # -- Tableau MaxDD
    print(f"\n{'Horizon':>12} | {'MaxDD P5':>12} | {'MaxDD Median':>12} | {'MaxDD P95':>12}")
    print("-" * 58)

    for h in HORIZONS:
        dds = results[h]["max_drawdowns"]
        dd_p5 = np.percentile(dds, 5)
        dd_p50 = np.percentile(dds, 50)
        dd_p95 = np.percentile(dds, 95)
        print(f"{h:>9} tr | ${dd_p5:>11,.0f} | ${dd_p50:>11,.0f} | ${dd_p95:>11,.0f}")

    # -- Verdict GO/NO-GO
    pnls_100 = results[100]["cumulative_pnls"]
    dds_100 = results[100]["max_drawdowns"]
    p_loss_100 = 100 * (pnls_100 < 0).sum() / len(pnls_100)
    maxdd_p5_100 = np.percentile(dds_100, 5)

    print("\n" + "=" * 80)
    print("  VERDICT GO/NO-GO (horizon 100 trades)")
    print("=" * 80)
    print(f"   P(perte a 100 trades)    : {p_loss_100:.1f}%  (seuil GO < 30%)")
    print(f"   MaxDD P5 a 100 trades    : ${maxdd_p5_100:,.0f}  (seuil GO > -$25,000)")

    if p_loss_100 < 30 and maxdd_p5_100 > -25000:
        verdict = "GO"
        print(f"\n   >>> {verdict} <<< Strategie validee pour C5 (slippage stress test)")
    elif p_loss_100 < 40 and maxdd_p5_100 > -35000:
        verdict = "GO CONDITIONNEL"
        print(f"\n   >>> {verdict} <<< Viable mais sizing conservateur recommande")
    else:
        verdict = "NO-GO"
        print(f"\n   >>> {verdict} <<< Strategie trop risquee pour production")

    return verdict, p_loss_100, maxdd_p5_100


def sensitivity_by_direction(trades_df):
    """Analyse Monte Carlo separee par direction LONG/SHORT."""
    print("\n" + "=" * 80)
    print("  ANALYSE PAR DIRECTION")
    print("=" * 80)

    for direction in ["LONG", "SHORT"]:
        mask = trades_df["Direction"] == direction
        pnls = trades_df.loc[mask, "PnL_Net"].values

        if len(pnls) < 10:
            print(f"\n   {direction} : {len(pnls)} trades (insuffisant)")
            continue

        print(f"\n   --- {direction} ({len(pnls)} trades) ---")
        print_trade_stats(pnls, source_label=f"{direction} only")

        results = monte_carlo_bootstrap(pnls, n_simulations=N_SIMULATIONS,
                                         horizons=[50, 100])
        for h in [50, 100]:
            p = results[h]["cumulative_pnls"]
            p_loss = 100 * (p < 0).sum() / len(p)
            print(f"   {h} trades : P(perte)={p_loss:.1f}%, "
                  f"median=${np.median(p):,.0f}, "
                  f"P5=${np.percentile(p, 5):,.0f}")


def sensitivity_by_year(trades_df):
    """Analyse Monte Carlo separee par annee."""
    print("\n" + "=" * 80)
    print("  ANALYSE PAR ANNEE")
    print("=" * 80)

    trades_df = trades_df.copy()
    trades_df["Year"] = pd.to_datetime(trades_df["Entry_DateTime"]).dt.year

    for year in sorted(trades_df["Year"].unique()):
        mask = trades_df["Year"] == year
        pnls = trades_df.loc[mask, "PnL_Net"].values

        if len(pnls) < 5:
            print(f"\n   {year} : {len(pnls)} trades (insuffisant)")
            continue

        wins = (pnls > 0).sum()
        print(f"\n   {year} : {len(pnls)} trades, PnL ${pnls.sum():,.0f}, "
              f"WR {100 * wins / len(pnls):.0f}%, "
              f"mean ${pnls.mean():,.0f}")


def generate_histogram(results, output_path="output/phase_c4_monte_carlo_100trades.png"):
    """Genere l'histogramme du PnL cumule a 100 trades."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("   matplotlib non disponible, histogramme non genere")
        return

    pnls = results[100]["cumulative_pnls"]
    p_loss = 100 * (pnls < 0).sum() / len(pnls)
    median_pnl = np.median(pnls)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Histogramme avec couleurs
    bins = np.linspace(pnls.min(), pnls.max(), 50)
    n, bins_out, patches = ax.hist(pnls, bins=bins, edgecolor="black", alpha=0.7)

    # Colorier vert/rouge
    for patch, left_edge in zip(patches, bins_out[:-1]):
        if left_edge < 0:
            patch.set_facecolor("#d32f2f")
        else:
            patch.set_facecolor("#388e3c")

    # Ligne verticale PnL = 0
    ax.axvline(x=0, color="red", linewidth=2, linestyle="--", label="PnL = 0")

    # Annotations
    ax.annotate(f"P(perte) = {p_loss:.1f}%",
                xy=(0.05, 0.92), xycoords="axes fraction",
                fontsize=12, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow"))
    ax.annotate(f"PnL median = ${median_pnl:,.0f}",
                xy=(0.05, 0.83), xycoords="axes fraction",
                fontsize=11,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow"))

    ax.set_xlabel("PnL cumule ($)", fontsize=12)
    ax.set_ylabel("Nombre de simulations", fontsize=12)
    ax.set_title(f"Monte Carlo Bootstrap - {N_SIMULATIONS} simulations x 100 trades\n"
                 f"Config: {WF_CONFIG_LABEL} (5min, 2 ticks)", fontsize=13)
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"   Histogramme sauvegarde : {output_path}")
    plt.close()


def save_results(results, trade_pnls, verdict, p_loss_100, maxdd_p5_100):
    """Sauvegarde les resultats en CSV."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # -- Resultats detailles (1000 lignes par horizon)
    rows = []
    for h in HORIZONS:
        for i in range(N_SIMULATIONS):
            rows.append({
                "horizon": h,
                "simulation": i + 1,
                "pnl_cumul": round(results[h]["cumulative_pnls"][i], 2),
                "max_drawdown": round(results[h]["max_drawdowns"][i], 2),
            })
    df_detail = pd.DataFrame(rows)
    detail_path = output_dir / "phase_c4_monte_carlo_results.csv"
    df_detail.to_csv(detail_path, index=False, sep=";")
    print(f"   Resultats detailles : {detail_path}")

    # -- Synthese
    summary_rows = []
    for h in HORIZONS:
        pnls = results[h]["cumulative_pnls"]
        dds = results[h]["max_drawdowns"]
        summary_rows.append({
            "horizon": h,
            "p_loss_pct": round(100 * (pnls < 0).sum() / len(pnls), 1),
            "pnl_p5": round(np.percentile(pnls, 5), 0),
            "pnl_p25": round(np.percentile(pnls, 25), 0),
            "pnl_median": round(np.median(pnls), 0),
            "pnl_p75": round(np.percentile(pnls, 75), 0),
            "pnl_p95": round(np.percentile(pnls, 95), 0),
            "pnl_mean": round(pnls.mean(), 0),
            "maxdd_p5": round(np.percentile(dds, 5), 0),
            "maxdd_median": round(np.median(dds), 0),
            "maxdd_p95": round(np.percentile(dds, 95), 0),
            "n_trades_source": len(trade_pnls),
            "source": "backtest_complet_3ans",
            "config": WF_CONFIG_LABEL,
            "verdict": verdict,
        })
    df_summary = pd.DataFrame(summary_rows)
    summary_path = output_dir / "phase_c4_summary.csv"
    df_summary.to_csv(summary_path, index=False, sep=";")
    print(f"   Synthese : {summary_path}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PHASE C4 : MONTE CARLO BOOTSTRAP")
    print("  1000 simulations x 4 horizons")
    print("=" * 60)

    # -- Etape 1 : Charger les trades
    trades_df = load_trades()

    if len(trades_df) == 0:
        print("\n   ERREUR : aucun trade genere. Verifier la config.")
        sys.exit(1)

    # Exclure les trades encore ouverts
    trades_df = trades_df[trades_df["Exit_Reason"] != "STILL_OPEN"].copy()

    trade_pnls = trades_df["PnL_Net"].values
    source_label = f"backtest complet 3 ans, config {WF_CONFIG_LABEL}"

    print("\n" + "=" * 60)
    print("  STATISTIQUES DES TRADES SOURCE")
    print("=" * 60)
    print_trade_stats(trade_pnls, trades_df["Direction"].values, source_label)

    # -- Etape 2 : Monte Carlo
    print("\n   Lancement de {0} simulations x {1} horizons...".format(
        N_SIMULATIONS, len(HORIZONS)))
    results = monte_carlo_bootstrap(trade_pnls, N_SIMULATIONS, HORIZONS)
    print("   Termine.")

    # -- Etape 3 : Afficher les resultats
    verdict, p_loss_100, maxdd_p5_100 = print_results(
        results, trade_pnls, source_label)

    # -- Etape 4 : Sensibilite par direction et par annee
    if len(trades_df) >= 80:
        sensitivity_by_direction(trades_df)
        sensitivity_by_year(trades_df)
    else:
        print(f"\n   {len(trades_df)} trades < 80 : analyse de sensibilite ignoree")

    # -- Histogramme
    generate_histogram(results)

    # -- Etape 5 : Sauvegarder
    print("\n" + "=" * 60)
    print("  SAUVEGARDE DES RESULTATS")
    print("=" * 60)
    save_results(results, trade_pnls, verdict, p_loss_100, maxdd_p5_100)

    print("\n   Phase C4 terminee.\n")
