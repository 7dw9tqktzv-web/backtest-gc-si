"""
Phase 2 -- Grid search SANS TP_ZSCORE + Phase 3 PnL floor eleve.

Teste les top 5 groupes indicateurs du grid search 3y avec :
  - TP_ZSCORE desactive (exit.zscore_tp_enabled=false)
  - PnL floor eleve ($50, $100, $150, $200) sur TP_ZSCORE
  - TP dollar elargi ($300 a $800)
  - SL dollar elargi (-$600 a -$1500)
  - zscore_entry : -2.5, -3.0, -3.5
  - cointegration_score_min : 40, 50, 60
  - Slippage : 1 tick ET 2 ticks

Resultats sauvegardes dans output/grid_search_no_tp_zscore.csv
"""
import sys
import time
import itertools
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, "src")

from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics
from run_helpers import count_exit_reasons, check_csv_resumption, save_batch_csv, print_top_configs

# ============================================================================
# PARAMETRES
# ============================================================================

OUTPUT_CSV = Path("output/grid_search_no_tp_zscore.csv")

# Top 5 groupes indicateurs identifies dans le grid search 3 ans
INDICATOR_GROUPS = [
    {"indicators.beta_lookback": 3960, "indicators.zscore_period": 20, "indicators.correlation_period": 30, "indicators.adf_hurst_period": 64},
    {"indicators.beta_lookback": 660,  "indicators.zscore_period": 20, "indicators.correlation_period": 60, "indicators.adf_hurst_period": 128},
    {"indicators.beta_lookback": 3960, "indicators.zscore_period": 15, "indicators.correlation_period": 20, "indicators.adf_hurst_period": 256},
    {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20, "indicators.correlation_period": 30, "indicators.adf_hurst_period": 64},
    {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20, "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128},
]

# Variantes entry/exit
ZSCORE_ENTRIES = [-2.5, -3.0, -3.5]
COINT_MINS = [40, 50, 60]
TP_DOLLARS = [300, 400, 500, 600, 800]
SL_DOLLARS = [-600, -800, -1000, -1500]
SLIPPAGES = [1, 2]

# Modes de sortie TP_ZSCORE a tester
# None = TP_ZSCORE desactive, 0/50/100/150/200 = PnL floor
TP_ZSCORE_MODES = [
    {"label": "noTPz", "zscore_tp_enabled": False, "zscore_tp_min_pnl": None},
    {"label": "floor0", "zscore_tp_enabled": True, "zscore_tp_min_pnl": 0},
    {"label": "floor50", "zscore_tp_enabled": True, "zscore_tp_min_pnl": 50},
    {"label": "floor100", "zscore_tp_enabled": True, "zscore_tp_min_pnl": 100},
    {"label": "floor150", "zscore_tp_enabled": True, "zscore_tp_min_pnl": 150},
    {"label": "floor200", "zscore_tp_enabled": True, "zscore_tp_min_pnl": 200},
]


def build_label(ind_ov, zE, co, tp, sl, slip, mode_label):
    beta = ind_ov["indicators.beta_lookback"]
    zp = ind_ov["indicators.zscore_period"]
    cp = ind_ov["indicators.correlation_period"]
    adf = ind_ov["indicators.adf_hurst_period"]
    return f"b{beta}_zp{zp}_cp{cp}_adf{adf}_zE{abs(zE)}_co{co}_TP{tp}_SL{abs(sl)}_s{slip}_{mode_label}"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Calculer le nombre total de configs
    n_variants = (len(ZSCORE_ENTRIES) * len(COINT_MINS) * len(TP_DOLLARS)
                  * len(SL_DOLLARS) * len(SLIPPAGES) * len(TP_ZSCORE_MODES))
    n_total = len(INDICATOR_GROUPS) * n_variants

    print("=" * 100)
    print("PHASE 2+3 -- GRID SEARCH SANS TP_ZSCORE + PNL FLOOR")
    print("=" * 100)
    print(f"\n   Groupes indicateurs : {len(INDICATOR_GROUPS)}")
    print(f"   Variantes par groupe : {n_variants}")
    print(f"   Total configs : {n_total:,}")
    print(f"   Modes TP_ZSCORE : {[m['label'] for m in TP_ZSCORE_MODES]}")

    # Charger les donnees
    print("\nChargement des donnees...")
    t0 = time.time()
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # Verifier reprise
    completed_labels = check_csv_resumption(OUTPUT_CSV)

    # Executer
    print(f"\nExecution des backtests...")
    t_start = time.time()
    all_results = []
    g_done = 0
    configs_done = len(completed_labels)

    for ind_ov in INDICATOR_GROUPS:
        g_done += 1
        beta = ind_ov["indicators.beta_lookback"]
        zp = ind_ov["indicators.zscore_period"]
        cp = ind_ov["indicators.correlation_period"]
        adf = ind_ov["indicators.adf_hurst_period"]
        group_prefix = f"b{beta}_zp{zp}_cp{cp}_adf{adf}"

        # Calculer les indicateurs une seule fois
        config_ind = apply_overrides(base_config, ind_ov)
        t_ind = time.time()
        df_ind = calculate_all_indicators(df_1min, config_ind, verbose=False)
        dt_ind = time.time() - t_ind

        batch_results = []

        # Boucle sur toutes les variantes
        for zE in ZSCORE_ENTRIES:
            for co in COINT_MINS:
                for tp in TP_DOLLARS:
                    for sl in SL_DOLLARS:
                        for slip in SLIPPAGES:
                            for mode in TP_ZSCORE_MODES:
                                label = build_label(ind_ov, zE, co, tp, sl, slip, mode["label"])

                                if label in completed_labels:
                                    continue

                                # Construire les overrides
                                overrides = {
                                    **ind_ov,
                                    "entry.zscore_long": zE,
                                    "entry.zscore_short": -zE,
                                    "entry.cointegration_score_min": co,
                                    "exit.pnl_take_profit": tp,
                                    "exit.pnl_stop_loss": sl,
                                    "exit.zscore_tp_enabled": mode["zscore_tp_enabled"],
                                    "costs.slippage_gc_ticks": slip,
                                    "costs.slippage_si_ticks": slip,
                                }
                                # PnL floor (seulement si TP_ZSCORE actif)
                                if mode["zscore_tp_min_pnl"] is not None:
                                    overrides["exit.zscore_tp_min_pnl"] = mode["zscore_tp_min_pnl"]

                                config_test = apply_overrides(base_config, overrides)
                                trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
                                m = compute_metrics(trades)

                                exits = count_exit_reasons(trades)

                                batch_results.append({
                                    "label": label,
                                    "beta": beta, "zp": zp, "cp": cp, "adf": adf,
                                    "zE": abs(zE), "co": co, "TP": tp, "SL": abs(sl),
                                    "slippage": slip, "tp_zscore_mode": mode["label"],
                                    "trades": m["trades"], "long": m["long"], "short": m["short"],
                                    "win_rate": round(m["win_rate"], 1),
                                    "pnl_net": round(m["pnl_net"], 0),
                                    "pnl_avg": round(m["pnl_avg"], 2),
                                    "profit_factor": round(m["profit_factor"], 2),
                                    "max_dd": round(m["max_dd"], 0),
                                    "sharpe": round(m["sharpe"], 2),
                                    "tp_zscore_count": exits["tp_zscore"],
                                    "tp_dollar_count": exits["tp_dollar"],
                                    "sl_zscore_count": exits["sl_zscore"],
                                    "sl_dollar_count": exits["sl_dollar"],
                                })

        # Sauvegarder le batch
        if batch_results:
            save_batch_csv(batch_results, OUTPUT_CSV)

            configs_done += len(batch_results)
            all_results.extend(batch_results)

            best = max(batch_results, key=lambda x: x["pnl_net"])
            elapsed = time.time() - t_start
            pct = configs_done / n_total * 100
            eta = (elapsed / configs_done * (n_total - configs_done)) / 60 if configs_done > 0 else 0

            print(f"   [{g_done}/{len(INDICATOR_GROUPS)}] {group_prefix} "
                  f"ind={dt_ind:.0f}s | {len(batch_results)} configs | "
                  f"best=${best['pnl_net']:>+,.0f} ({best['tp_zscore_mode']}) | "
                  f"{pct:.0f}% ETA={eta:.0f}min", flush=True)

    # ============================================================================
    # RESULTATS
    # ============================================================================
    t_total = time.time() - t_start

    # Recharger tout (en cas de reprise)
    if OUTPUT_CSV.exists():
        df_all = pd.read_csv(OUTPUT_CSV, sep=";")
    else:
        df_all = pd.DataFrame(all_results)

    n_total_done = len(df_all)
    n_profitable = (df_all["pnl_net"] > 0).sum()

    print(f"\n\n{'='*130}")
    print(f"RESULTATS -- {n_total_done:,} configs en {t_total/60:.1f} min")
    print(f"{'='*130}")
    print(f"Configs rentables : {n_profitable} / {n_total_done} ({n_profitable/n_total_done*100:.1f}%)")

    # Comparaison par mode TP_ZSCORE
    print(f"\n{'='*100}")
    print("COMPARAISON PAR MODE TP_ZSCORE")
    print(f"{'='*100}")
    print(f"{'Mode':<12} {'Profitable':>12} {'Total':>8} {'%':>7} {'Best PnL':>12} {'Best Sharpe':>12}")
    print("-" * 100)
    for mode in TP_ZSCORE_MODES:
        sub = df_all[df_all["tp_zscore_mode"] == mode["label"]]
        n_prof = (sub["pnl_net"] > 0).sum()
        best_pnl = sub["pnl_net"].max() if len(sub) > 0 else 0
        best_sharpe = sub["sharpe"].max() if len(sub) > 0 else 0
        print(f"{mode['label']:<12} {n_prof:>12} {len(sub):>8} {n_prof/len(sub)*100:>6.1f}% "
              f"${best_pnl:>10,.0f} {best_sharpe:>11.2f}")

    # Comparaison par slippage
    print(f"\n{'='*100}")
    print("COMPARAISON PAR SLIPPAGE")
    print(f"{'='*100}")
    for slip in SLIPPAGES:
        sub = df_all[df_all["slippage"] == slip]
        n_prof = (sub["pnl_net"] > 0).sum()
        print(f"   {slip} tick(s) : {n_prof} / {len(sub)} rentables ({n_prof/len(sub)*100:.1f}%)")

    # Top 20 global par PnL
    print_top_configs(df_all, metric="pnl_net", n=20,
                      title="TOP 20 PAR PNL NET (tous modes confondus)")

    # Top 20 par Sharpe (min 10 trades)
    print_top_configs(df_all, metric="sharpe", n=20, min_trades=10,
                      title="TOP 20 PAR SHARPE (min 10 trades)")

    print(f"\n[OK] Resultats sauvegardes dans {OUTPUT_CSV}")
    print(f"[OK] Duree totale : {t_total/60:.1f} min")
