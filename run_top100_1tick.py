"""
Phase 1 -- Relancer les top 100 configs (3 ans) avec 1 tick slippage.

Lit output/grid_search_3y_phase1.csv, prend les 100 meilleures par PnL,
les regroupe par indicateurs (calcul 1 fois par groupe), et relance
chaque variante entry/exit avec slippage=1 tick.

Sauvegarde dans output/grid_search_3y_1tick_top100.csv
"""
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, "src")

from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics

# ============================================================================
# PARAMETRES
# ============================================================================

INPUT_CSV = Path("output/grid_search_3y_phase1.csv")
OUTPUT_CSV = Path("output/grid_search_3y_1tick_top100.csv")
TOP_N = 100

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("PHASE 1 -- TOP 100 CONFIGS AVEC 1 TICK SLIPPAGE")
    print("=" * 100)

    # 1. Charger le CSV du grid search 3 ans
    if not INPUT_CSV.exists():
        print(f"[ERREUR] Fichier introuvable : {INPUT_CSV}")
        sys.exit(1)

    df_grid = pd.read_csv(INPUT_CSV, sep=";")
    print(f"\n   {len(df_grid):,} configs chargees depuis {INPUT_CSV}")

    # 2. Prendre les top 100 par PnL
    top100 = df_grid.nlargest(TOP_N, "pnl_net").copy()
    print(f"   Top {len(top100)} selectionnees (PnL de ${top100['pnl_net'].iloc[0]:,.0f} a ${top100['pnl_net'].iloc[-1]:,.0f})")

    # 3. Regrouper par indicateurs
    ind_cols = ["beta", "zp", "cp", "adf"]
    groups = top100.groupby(ind_cols)
    print(f"   {len(groups)} groupes indicateurs distincts")

    # 4. Charger les donnees
    print("\nChargement des donnees...")
    t0 = time.time()
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # 5. Executer les backtests groupes
    print(f"\nExecution des backtests (slippage = 1 tick)...")
    t_start = time.time()
    all_results = []
    g_done = 0

    for (beta, zp, cp, adf), group_df in groups:
        g_done += 1
        group_prefix = f"b{beta}_zp{zp}_cp{cp}_adf{adf}"

        # Calculer les indicateurs une seule fois pour ce groupe
        ind_overrides = {
            "indicators.beta_lookback": int(beta),
            "indicators.zscore_period": int(zp),
            "indicators.correlation_period": int(cp),
            "indicators.adf_hurst_period": int(adf),
        }
        config_ind = apply_overrides(base_config, ind_overrides)
        t_ind = time.time()
        df_ind = calculate_all_indicators(df_1min, config_ind, verbose=False)
        dt_ind = time.time() - t_ind

        # Tester chaque variante entry/exit du groupe
        for _, row in group_df.iterrows():
            zE = row["zE"]
            co = int(row["co"])
            tp = int(row["TP"])
            sl = int(row["SL"])
            label = f"{group_prefix}_zE{zE}_co{co}_TP{tp}_SL{sl}"

            # Overrides complets avec slippage 1 tick
            merged = {
                **ind_overrides,
                "entry.zscore_long": -zE,
                "entry.zscore_short": zE,
                "entry.cointegration_score_min": co,
                "exit.pnl_take_profit": tp,
                "exit.pnl_stop_loss": -sl,
                "exit.zscore_tp_min_pnl": 0,
                "costs.slippage_gc_ticks": 1,
                "costs.slippage_si_ticks": 1,
            }
            config_test = apply_overrides(base_config, merged)
            trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
            m = compute_metrics(trades)

            # Compter les exit reasons
            if len(trades) > 0:
                tp_zscore = (trades['Exit_Reason'] == 'TP_ZSCORE').sum()
                tp_dollar = (trades['Exit_Reason'] == 'TP_DOLLAR').sum()
                sl_zscore = (trades['Exit_Reason'] == 'SL_ZSCORE').sum()
                sl_dollar = (trades['Exit_Reason'] == 'SL_DOLLAR').sum()
            else:
                tp_zscore = tp_dollar = sl_zscore = sl_dollar = 0

            # PnL 2-tick original pour comparaison
            pnl_2tick = row["pnl_net"]

            all_results.append({
                "label": label,
                "beta": int(beta), "zp": int(zp), "cp": int(cp), "adf": int(adf),
                "zE": zE, "co": co, "TP": tp, "SL": sl,
                "trades": m["trades"], "long": m["long"], "short": m["short"],
                "win_rate": round(m["win_rate"], 1),
                "pnl_1tick": round(m["pnl_net"], 0),
                "pnl_2tick": round(pnl_2tick, 0),
                "delta": round(m["pnl_net"] - pnl_2tick, 0),
                "pnl_avg": round(m["pnl_avg"], 2),
                "profit_factor": round(m["profit_factor"], 2),
                "max_dd": round(m["max_dd"], 0),
                "sharpe": round(m["sharpe"], 2),
                "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
                "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
            })

        elapsed = time.time() - t_start
        print(f"   [{g_done}/{len(groups)}] {group_prefix} "
              f"ind={dt_ind:.0f}s | {len(group_df)} configs | "
              f"{elapsed/60:.1f}min", flush=True)

    # 6. Sauvegarder
    df_results = pd.DataFrame(all_results)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(OUTPUT_CSV, sep=";", index=False)

    # 7. Afficher les resultats
    t_total = time.time() - t_start
    n_profitable = (df_results["pnl_1tick"] > 0).sum()

    print(f"\n\n{'='*120}")
    print(f"RESULTATS PHASE 1 -- TOP {len(df_results)} CONFIGS EN 1 TICK")
    print(f"{'='*120}")
    print(f"Configs rentables (1 tick) : {n_profitable} / {len(df_results)} ({n_profitable/len(df_results)*100:.1f}%)")
    print(f"Configs rentables (2 tick) : {(df_results['pnl_2tick'] > 0).sum()} / {len(df_results)}")
    print(f"Delta moyen 1tick vs 2tick : ${df_results['delta'].mean():,.0f}")
    print(f"Duree : {t_total/60:.1f} min")

    # Top 20 par PnL 1-tick
    top_pnl = df_results.nlargest(20, "pnl_1tick")
    print(f"\n{'='*130}")
    print("TOP 20 PAR PNL NET (1 TICK)")
    print(f"{'='*130}")
    print(f"{'#':<3} {'Config':<50} {'Trades':>7} {'WR%':>6} {'PnL 1tick':>11} {'PnL 2tick':>11} {'Delta':>8} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
    print("-" * 130)
    for i, (_, r) in enumerate(top_pnl.iterrows()):
        print(f"{i+1:<3} {r['label']:<50} {r['trades']:>7} {r['win_rate']:>5.1f}% "
              f"${r['pnl_1tick']:>9,.0f} ${r['pnl_2tick']:>9,.0f} ${r['delta']:>+7,.0f} "
              f"{r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['sharpe']:>6.2f}")

    # Top 20 par Sharpe (min 10 trades)
    df_min10 = df_results[df_results["trades"] >= 10]
    if len(df_min10) > 0:
        top_sharpe = df_min10.nlargest(20, "sharpe")
        print(f"\n{'='*130}")
        print("TOP 20 PAR SHARPE (min 10 trades, 1 tick)")
        print(f"{'='*130}")
        print(f"{'#':<3} {'Config':<50} {'Trades':>7} {'WR%':>6} {'PnL 1tick':>11} {'PnL 2tick':>11} {'Delta':>8} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
        print("-" * 130)
        for i, (_, r) in enumerate(top_sharpe.iterrows()):
            print(f"{i+1:<3} {r['label']:<50} {r['trades']:>7} {r['win_rate']:>5.1f}% "
                  f"${r['pnl_1tick']:>9,.0f} ${r['pnl_2tick']:>9,.0f} ${r['delta']:>+7,.0f} "
                  f"{r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['sharpe']:>6.2f}")

    # Distribution des exit reasons
    print(f"\n{'='*80}")
    print("DISTRIBUTION DES EXIT REASONS (moyennes)")
    print(f"{'='*80}")
    for col in ["tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar"]:
        avg = df_results[col].mean()
        total = df_results[["tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar"]].sum(axis=1).mean()
        pct = avg / total * 100 if total > 0 else 0
        print(f"   {col:<12} : {avg:>6.1f} ({pct:>5.1f}%)")

    print(f"\n[OK] Resultats sauvegardes dans {OUTPUT_CSV}")
