#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ============================================================================
# PHASE C5 : SLIPPAGE STRESS TEST (1, 2, 2.5, 3 ticks)
# ============================================================================
#
# Teste 2 configs de reference avec 4 niveaux de slippage pour verifier
# que la strategie survit a un slippage superieur au nominal (2 ticks).
#
# Critere GO : PnL > 0 a 2.5 ticks ET marge de securite > 0.5 tick
#
# Usage : python scripts/phase_c5_slippage_stress.py
# ============================================================================

import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides

# -- Niveaux de slippage a tester
SLIPPAGE_LEVELS = [1.0, 2.0, 2.5, 3.0]

# -- Configs de reference
CONFIGS = {
    "b3960 (WF best)": {
        "indicators.period": "5min",
        "indicators.beta_lookback": 3960,
        "indicators.zscore_period": 24,
        "indicators.correlation_period": 12,
        "indicators.adf_hurst_period": 26,
        "entry.zscore_long": -3.5,
        "entry.zscore_short": 3.5,
        "entry.cointegration_score_min": 50,
        "exit.zscore_tp_enabled": True,
        "exit.zscore_tp_long": 1.0,
        "exit.zscore_tp_short": -1.0,
        "exit.zscore_sl_long": -4.0,
        "exit.zscore_sl_short": 4.0,
        "exit.pnl_take_profit": 99999,
        "exit.pnl_stop_loss": -99999,
    },
    "b2640 (B2 top)": {
        "indicators.period": "5min",
        "indicators.beta_lookback": 2640,
        "indicators.zscore_period": 20,
        "indicators.correlation_period": 30,
        "indicators.adf_hurst_period": 26,
        "entry.zscore_long": -3.5,
        "entry.zscore_short": 3.5,
        "entry.cointegration_score_min": 40,
        "exit.zscore_tp_enabled": True,
        "exit.zscore_tp_long": 1.0,
        "exit.zscore_tp_short": -1.0,
        "exit.zscore_sl_long": -4.0,
        "exit.zscore_sl_short": 4.0,
        "exit.pnl_take_profit": 99999,
        "exit.pnl_stop_loss": -99999,
    },
}

# -- Monte Carlo
N_SIMULATIONS = 1000
MC_SEED = 42
MC_HORIZON = 100


def run_all_backtests(df_5min_base, df_5s, base_config):
    """Lance les 8 backtests (2 configs x 4 slippages)."""
    all_results = []

    for config_name, overrides in CONFIGS.items():
        print(f"\n{'='*60}")
        print(f"  Config : {config_name}")
        print(f"{'='*60}")

        # Appliquer les overrides de base (sans slippage)
        cfg_base = apply_overrides(base_config, overrides)

        # Calculer les indicateurs une seule fois par config
        print("   Calcul des indicateurs...")
        df_5min = calculate_all_indicators(df_5min_base.copy(), cfg_base, verbose=False)

        for slip in SLIPPAGE_LEVELS:
            # Appliquer le slippage
            cfg = apply_overrides(cfg_base, {
                "costs.slippage_gc_ticks": slip,
                "costs.slippage_si_ticks": slip,
            })

            print(f"   Slippage {slip} ticks...", end=" ")
            trades_df = run_hybrid_backtest(df_5min, df_5s, cfg, verbose=False)
            trades_df = trades_df[trades_df["Exit_Reason"] != "STILL_OPEN"].copy()

            n_trades = len(trades_df)
            if n_trades == 0:
                print("0 trades")
                all_results.append({
                    "config": config_name, "slippage": slip,
                    "trades": 0, "pnl": 0, "wr": 0, "pf": 0,
                    "maxdd": 0, "sharpe": 0, "pnl_per_trade": 0,
                    "trades_df": pd.DataFrame(),
                })
                continue

            pnl = trades_df["PnL_Net"].sum()
            wins = (trades_df["PnL_Net"] > 0).sum()
            wr = 100 * wins / n_trades
            gross_wins = trades_df.loc[trades_df["PnL_Net"] > 0, "PnL_Net"].sum()
            gross_losses = abs(trades_df.loc[trades_df["PnL_Net"] <= 0, "PnL_Net"].sum())
            pf = gross_wins / gross_losses if gross_losses > 0 else float("inf")

            # MaxDD
            cumul = trades_df["PnL_Net"].cumsum()
            running_max = cumul.cummax()
            maxdd = (cumul - running_max).min()

            # Sharpe (per trade)
            mean_pnl = trades_df["PnL_Net"].mean()
            std_pnl = trades_df["PnL_Net"].std()
            sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0

            print(f"{n_trades} trades, PnL ${pnl:,.0f}, WR {wr:.0f}%, PF {pf:.2f}")

            all_results.append({
                "config": config_name, "slippage": slip,
                "trades": n_trades, "pnl": pnl, "wr": wr, "pf": pf,
                "maxdd": maxdd, "sharpe": sharpe,
                "pnl_per_trade": pnl / n_trades,
                "trades_df": trades_df,
            })

    return all_results


def print_results_table(results):
    """Affiche les tableaux de resultats par config."""
    for config_name in CONFIGS:
        cfg_results = [r for r in results if r["config"] == config_name]
        print(f"\n{'='*80}")
        print(f"  {config_name}")
        print(f"{'='*80}")
        print(f"{'Slippage':>10} | {'Trades':>6} | {'PnL':>10} | {'WR':>5} | "
              f"{'PF':>6} | {'MaxDD':>10} | {'Sharpe':>7} | {'PnL/Trade':>10}")
        print("-" * 80)
        for r in cfg_results:
            print(f"{r['slippage']:>7.1f} tk | {r['trades']:>6} | ${r['pnl']:>9,.0f} | "
                  f"{r['wr']:>4.0f}% | {r['pf']:>5.2f} | ${r['maxdd']:>9,.0f} | "
                  f"{r['sharpe']:>6.3f} | ${r['pnl_per_trade']:>9,.0f}")


def print_comparison_table(results):
    """Affiche le tableau comparatif."""
    config_names = list(CONFIGS.keys())
    print(f"\n{'='*60}")
    print(f"  COMPARAISON")
    print(f"{'='*60}")
    print(f"{'Slippage':>10} | {config_names[0]:>18} | {config_names[1]:>18}")
    print("-" * 55)
    for slip in SLIPPAGE_LEVELS:
        pnls = []
        for cn in config_names:
            r = [x for x in results if x["config"] == cn and x["slippage"] == slip][0]
            pnls.append(r["pnl"])
        print(f"{slip:>7.1f} tk | ${pnls[0]:>17,.0f} | ${pnls[1]:>17,.0f}")


def compute_degradation(results):
    """Calcule le cout marginal par tick et le breakeven slippage."""
    print(f"\n{'='*60}")
    print(f"  DEGRADATION PAR TICK")
    print(f"{'='*60}")

    degradation = {}
    for config_name in CONFIGS:
        cfg_results = [r for r in results if r["config"] == config_name]
        r1 = [r for r in cfg_results if r["slippage"] == 1.0][0]
        r2 = [r for r in cfg_results if r["slippage"] == 2.0][0]

        n_trades = r1["trades"]
        if n_trades == 0:
            continue

        # Cout marginal par tick = delta PnL / delta slippage / n_trades
        cost_per_tick = (r1["pnl"] - r2["pnl"]) / n_trades  # par trade, pour 1 tick

        # Breakeven : PnL_1tick / cost_per_tick + 1
        if cost_per_tick > 0:
            breakeven = 1.0 + r1["pnl"] / (cost_per_tick * n_trades)
        else:
            breakeven = float("inf")

        margin = breakeven - 2.0

        print(f"\n   {config_name}:")
        print(f"   Cout marginal par tick supplementaire : ${cost_per_tick:,.0f}/trade")
        print(f"   Breakeven slippage : {breakeven:.1f} ticks")
        print(f"   Marge de securite (vs 2 ticks) : {margin:.1f} ticks")

        degradation[config_name] = {
            "cost_per_tick": cost_per_tick,
            "breakeven": breakeven,
            "margin": margin,
        }

    return degradation


def run_monte_carlo_25(results):
    """Lance un mini Monte Carlo sur les trades a 2.5 ticks."""
    print(f"\n{'='*60}")
    print(f"  MONTE CARLO A 2.5 TICKS (1000 sims x 100 trades)")
    print(f"{'='*60}")

    mc_results = {}
    np.random.seed(MC_SEED)

    for config_name in CONFIGS:
        r25 = [r for r in results
               if r["config"] == config_name and r["slippage"] == 2.5][0]

        if r25["pnl"] <= 0:
            print(f"\n   {config_name} : PnL <= 0 a 2.5 ticks, MC non applicable")
            mc_results[config_name] = None
            continue

        pnls = r25["trades_df"]["PnL_Net"].values
        if len(pnls) < 10:
            print(f"\n   {config_name} : {len(pnls)} trades, insuffisant")
            mc_results[config_name] = None
            continue

        cumulative_pnls = np.empty(N_SIMULATIONS)
        for i in range(N_SIMULATIONS):
            sampled = np.random.choice(pnls, size=MC_HORIZON, replace=True)
            cumulative_pnls[i] = sampled.sum()

        p_loss = 100 * (cumulative_pnls < 0).sum() / N_SIMULATIONS
        median_pnl = np.median(cumulative_pnls)
        p5 = np.percentile(cumulative_pnls, 5)

        print(f"\n   {config_name} :")
        print(f"   P(perte 100 trades) a 2.5 ticks : {p_loss:.1f}%")
        print(f"   PnL median : ${median_pnl:,.0f}")
        print(f"   PnL P5 : ${p5:,.0f}")

        mc_results[config_name] = {
            "p_loss": p_loss, "median": median_pnl, "p5": p5,
            "cumulative_pnls": cumulative_pnls,
        }

    return mc_results


def print_verdict(results, degradation, mc_results):
    """Affiche le verdict final."""
    print(f"\n{'='*60}")
    print(f"  VERDICT FINAL C5")
    print(f"{'='*60}")

    verdicts = {}
    for config_name in CONFIGS:
        r25 = [r for r in results
               if r["config"] == config_name and r["slippage"] == 2.5][0]
        r3 = [r for r in results
              if r["config"] == config_name and r["slippage"] == 3.0][0]

        deg = degradation.get(config_name, {})
        margin = deg.get("margin", 0)
        breakeven = deg.get("breakeven", 0)

        pnl_25 = r25["pnl"]
        pnl_3 = r3["pnl"]

        if pnl_25 > 0 and margin > 0.5:
            verdict = "GO"
        elif pnl_25 > 0:
            verdict = "GO CONDITIONNEL"
        else:
            verdict = "NO-GO"

        verdicts[config_name] = verdict

        print(f"\n   {config_name} :")
        print(f"   PnL a 2.5 ticks : ${pnl_25:,.0f} ({verdict})")
        print(f"   PnL a 3 ticks   : ${pnl_3:,.0f}")
        print(f"   Breakeven slippage : {breakeven:.1f} ticks")
        print(f"   Marge de securite  : {margin:.1f} ticks")

        mc = mc_results.get(config_name)
        if mc:
            print(f"   MC P(perte 100tr) a 2.5 ticks : {mc['p_loss']:.1f}%")

    # Recommandation
    print(f"\n{'='*60}")
    print(f"  RECOMMANDATION PRODUCTION")
    print(f"{'='*60}")

    # Choisir la config avec la meilleure marge
    best_config = max(degradation, key=lambda c: degradation[c]["margin"])
    best_margin = degradation[best_config]["margin"]
    best_verdict = verdicts[best_config]

    print(f"   Config recommandee : {best_config}")
    print(f"   Marge de securite  : {best_margin:.1f} ticks")
    print(f"   Verdict : {best_verdict}")

    if best_verdict == "GO":
        print(f"\n   >>> GO <<< Strategie validee pour Phase D (Sierra Chart)")
    elif best_verdict == "GO CONDITIONNEL":
        print(f"\n   >>> GO CONDITIONNEL <<< Sizing conservateur recommande")
    else:
        print(f"\n   >>> NO-GO <<< Strategie ne supporte pas le slippage reel")

    return verdicts


def save_results(results, degradation, mc_results, verdicts):
    """Sauvegarde les resultats."""
    output_dir = Path("output")

    # -- Resultats des 8 backtests
    rows = []
    for r in results:
        rows.append({
            "config": r["config"], "slippage": r["slippage"],
            "trades": r["trades"], "pnl": round(r["pnl"], 2),
            "wr": round(r["wr"], 1), "pf": round(r["pf"], 2),
            "maxdd": round(r["maxdd"], 2), "sharpe": round(r["sharpe"], 4),
            "pnl_per_trade": round(r["pnl_per_trade"], 2),
        })
    df = pd.DataFrame(rows)
    path = output_dir / "phase_c5_slippage_results.csv"
    df.to_csv(path, index=False, sep=";")
    print(f"\n   Resultats : {path}")

    # -- Synthese
    summary_rows = []
    for config_name in CONFIGS:
        deg = degradation.get(config_name, {})
        for slip in SLIPPAGE_LEVELS:
            r = [x for x in results if x["config"] == config_name and x["slippage"] == slip][0]
            summary_rows.append({
                "config": config_name, "slippage": slip,
                "pnl": round(r["pnl"], 0), "trades": r["trades"],
                "pf": round(r["pf"], 2),
                "breakeven": round(deg.get("breakeven", 0), 1),
                "margin": round(deg.get("margin", 0), 1),
                "verdict": verdicts.get(config_name, ""),
            })
    df_summary = pd.DataFrame(summary_rows)
    path = output_dir / "phase_c5_summary.csv"
    df_summary.to_csv(path, index=False, sep=";")
    print(f"   Synthese : {path}")

    # -- MC a 2.5 ticks
    mc_rows = []
    for config_name, mc in mc_results.items():
        if mc is None:
            continue
        for i, pnl in enumerate(mc["cumulative_pnls"]):
            mc_rows.append({
                "config": config_name, "simulation": i + 1,
                "pnl_cumul_100trades": round(pnl, 2),
            })
    if mc_rows:
        df_mc = pd.DataFrame(mc_rows)
        path = output_dir / "phase_c5_monte_carlo_2.5tick.csv"
        df_mc.to_csv(path, index=False, sep=";")
        print(f"   MC 2.5 ticks : {path}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PHASE C5 : SLIPPAGE STRESS TEST")
    print("  2 configs x 4 slippages = 8 backtests")
    print("=" * 60)

    # -- Charger les donnees une seule fois
    print("\n   Chargement des donnees...")
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5min_base = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print("   Donnees chargees.")

    # -- Lancer les 8 backtests
    results = run_all_backtests(df_5min_base, df_5s, base_config)

    # -- Afficher les resultats
    print_results_table(results)
    print_comparison_table(results)

    # -- Degradation
    degradation = compute_degradation(results)

    # -- Monte Carlo a 2.5 ticks
    mc_results = run_monte_carlo_25(results)

    # -- Verdict
    verdicts = print_verdict(results, degradation, mc_results)

    # -- Sauvegarder
    print(f"\n{'='*60}")
    print(f"  SAUVEGARDE")
    print(f"{'='*60}")
    save_results(results, degradation, mc_results, verdicts)

    print("\n   Phase C5 terminee.\n")
