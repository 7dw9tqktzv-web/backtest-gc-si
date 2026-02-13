"""
Grid Search TOP 100 - Retest avec 1 tick de slippage
Lit les resultats du grid search 3 ans (2 ticks), prend les top 100 par PnL,
et les relance avec 1 tick de slippage pour mesurer le delta.

Usage : python run_grid_search_top100_1tick.py [--top N] [--sort pnl_net|sharpe]
"""
import sys
import time
import argparse
import multiprocessing as mp
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from run_helpers import count_exit_reasons, check_csv_resumption, save_batch_csv, print_top_configs

# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_CSV = Path("output/grid_search_3y_phase1.csv")
OUTPUT_CSV = Path("output/grid_search_top100_1tick.csv")
NUM_WORKERS = 12  # 12 cores Ryzen 9 7900X

FIXED_OVERRIDES = {
    "exit.zscore_tp_min_pnl": 0,
    "costs.slippage_gc_ticks": 1,   # <-- 1 tick au lieu de 2
    "costs.slippage_si_ticks": 1,   # <-- 1 tick au lieu de 2
}


# ============================================================================
# RECONSTRUCTION DES OVERRIDES DEPUIS LE CSV
# ============================================================================

def row_to_overrides(row):
    """Reconstruit le dict d'overrides depuis une ligne du CSV de resultats."""
    return {
        # Indicateurs
        "indicators.beta_lookback": int(row["beta"]),
        "indicators.zscore_period": int(row["zp"]),
        "indicators.correlation_period": int(row["cp"]),
        "indicators.adf_hurst_period": int(row["adf"]),
        # Entry
        "entry.zscore_long": -float(row["zE"]),       # zE est stocke en positif
        "entry.zscore_short": float(row["zE"]),
        "entry.cointegration_score_min": int(row["co"]),
        # Exit
        "exit.pnl_take_profit": int(row["TP"]),
        "exit.pnl_stop_loss": -int(row["SL"]),         # SL stocke en positif
    }


def make_label(row):
    """Reconstruit le label depuis une ligne du CSV."""
    return (f"b{int(row['beta'])}_zp{int(row['zp'])}_cp{int(row['cp'])}_adf{int(row['adf'])}"
            f"_zE{row['zE']}_co{int(row['co'])}_TP{int(row['TP'])}_SL{int(row['SL'])}")


# ============================================================================
# WORKER : groupe par indicateurs pour eviter recalcul
# ============================================================================

def process_group(args):
    """
    Worker : calcule les indicateurs une fois pour le groupe,
    puis execute les backtests pour chaque config entry/exit du groupe.
    """
    group_key, configs, base_config, df_1min, df_5s, completed_labels = args

    from indicators import calculate_all_indicators
    from backtest_engine_numba import run_hybrid_backtest
    from optimizer import apply_overrides, compute_metrics

    # Indicateurs communs au groupe
    first = configs[0]
    ind_ov = {
        "indicators.beta_lookback": first["indicators.beta_lookback"],
        "indicators.zscore_period": first["indicators.zscore_period"],
        "indicators.correlation_period": first["indicators.correlation_period"],
        "indicators.adf_hurst_period": first["indicators.adf_hurst_period"],
    }

    config_ind = apply_overrides(base_config, ind_ov)
    t0 = time.time()
    df_ind = calculate_all_indicators(df_1min, config_ind, verbose=False)
    dt_ind = time.time() - t0

    batch_results = []
    for cfg_overrides in configs:
        merged = {**cfg_overrides, **FIXED_OVERRIDES}
        label = merged.pop("_label", "unknown")

        if label in completed_labels:
            continue

        config_test = apply_overrides(base_config, merged)
        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)

        from run_helpers import count_exit_reasons as _count_er
        exits = _count_er(trades)

        beta = cfg_overrides["indicators.beta_lookback"]
        zp = cfg_overrides["indicators.zscore_period"]
        cp = cfg_overrides["indicators.correlation_period"]
        adf = cfg_overrides["indicators.adf_hurst_period"]
        zE = abs(cfg_overrides["entry.zscore_long"])
        co = cfg_overrides["entry.cointegration_score_min"]
        tp = cfg_overrides["exit.pnl_take_profit"]
        sl = abs(cfg_overrides["exit.pnl_stop_loss"])

        batch_results.append({
            "label": label,
            "beta": beta, "zp": zp, "cp": cp, "adf": adf,
            "zE": zE, "co": co, "TP": tp, "SL": sl,
            "trades": m["trades"], "long": m["long"], "short": m["short"],
            "win_rate": round(m["win_rate"], 1),
            "pnl_net": round(m["pnl_net"], 0),
            "pnl_avg": round(m["pnl_avg"], 2),
            "profit_factor": round(m["profit_factor"], 2),
            "max_dd": round(m["max_dd"], 0),
            "sharpe": round(m["sharpe"], 2),
            **exits,
        })

    return group_key, batch_results, dt_ind


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retest top N configs avec 1 tick slippage")
    parser.add_argument("--top", type=int, default=100, help="Nombre de configs a retester (default: 100)")
    parser.add_argument("--sort", type=str, default="pnl_net", help="Critere de tri (pnl_net, sharpe)")
    args = parser.parse_args()

    TOP_N = args.top
    SORT_BY = args.sort

    print("=" * 100)
    print(f"GRID SEARCH TOP {TOP_N} - RETEST AVEC 1 TICK DE SLIPPAGE")
    print("=" * 100)

    # ---- Charger les resultats 2 ticks ----
    if not SOURCE_CSV.exists():
        print(f"[ERREUR] Fichier source introuvable : {SOURCE_CSV}")
        sys.exit(1)

    df_source = pd.read_csv(SOURCE_CSV, sep=";")
    print(f"\nSource : {SOURCE_CSV} ({len(df_source):,} configs)")

    # ---- Extraire le top N ----
    ascending = False if SORT_BY in ("pnl_net", "sharpe", "profit_factor") else True
    df_top = df_source.nlargest(TOP_N, SORT_BY)
    print(f"Top {TOP_N} par {SORT_BY} : PnL range [{df_top['pnl_net'].min():+,.0f} ; {df_top['pnl_net'].max():+,.0f}]")

    # ---- Construire les overrides ----
    all_configs = []
    for _, row in df_top.iterrows():
        ov = row_to_overrides(row)
        ov["_label"] = make_label(row)
        all_configs.append(ov)

    # ---- Grouper par indicateurs (eviter recalcul) ----
    groups = {}
    for cfg in all_configs:
        key = (cfg["indicators.beta_lookback"], cfg["indicators.zscore_period"],
               cfg["indicators.correlation_period"], cfg["indicators.adf_hurst_period"])
        if key not in groups:
            groups[key] = []
        groups[key].append(cfg)

    print(f"Configs a tester : {len(all_configs)}")
    print(f"Groupes indicateurs uniques : {len(groups)} (1 calcul d'indicateurs par groupe)")
    print(f"Workers : {NUM_WORKERS}")
    print(f"Slippage : 1 tick GC + 1 tick SI")

    # ---- Charger les donnees ----
    print("\nChargement des donnees...")
    t0 = time.time()
    from data_loader import load_and_prepare_data, load_5s_data
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # ---- Verifier reprise ----
    completed_labels = check_csv_resumption(OUTPUT_CSV)

    # ---- Preparer les args workers ----
    worker_args = [
        (group_key, configs, base_config, df_1min, df_5s, completed_labels)
        for group_key, configs in groups.items()
    ]

    # ---- Lancement ----
    print(f"\nLancement de {min(NUM_WORKERS, len(worker_args))} workers...")
    t_start = time.time()

    groups_done = 0
    total_results = 0
    best_pnl = -999999
    best_label = ""

    with mp.Pool(processes=min(NUM_WORKERS, len(worker_args))) as pool:
        for group_key, batch_results, dt_ind in pool.imap_unordered(process_group, worker_args):
            groups_done += 1

            if not batch_results:
                continue

            # Sauvegarder
            save_batch_csv(batch_results, OUTPUT_CSV)

            total_results += len(batch_results)
            best_in_batch = max(batch_results, key=lambda x: x["pnl_net"])
            if best_in_batch["pnl_net"] > best_pnl:
                best_pnl = best_in_batch["pnl_net"]
                best_label = best_in_batch["label"]

            b, zp, cp, adf = group_key
            elapsed = time.time() - t_start
            print(f"[{groups_done:>3}/{len(groups)}] b{b}_zp{zp}_cp{cp}_adf{adf} "
                  f"ind={dt_ind:.0f}s | {len(batch_results)} configs | "
                  f"best=${best_in_batch['pnl_net']:>+10,.0f} | "
                  f"global best=${best_pnl:>+10,.0f} ({elapsed:.0f}s)", flush=True)

    # ============================================================================
    # RESULTATS + COMPARAISON
    # ============================================================================
    t_total = time.time() - t_start

    if not OUTPUT_CSV.exists():
        print("[ERREUR] Aucun resultat produit.")
        sys.exit(1)

    df_1tick = pd.read_csv(OUTPUT_CSV, sep=";")
    n_total = len(df_1tick)
    n_profitable = len(df_1tick[df_1tick["pnl_net"] > 0])

    print("\n\n" + "=" * 120)
    print(f"RESULTATS : {n_total} configs retestees en {t_total:.0f}s ({t_total/60:.1f} min)")
    print(f"Configs rentables : {n_profitable} / {n_total} ({n_profitable/n_total*100:.1f}%)" if n_total > 0 else "")
    print("=" * 120)

    # ---- Top 20 par PnL (1 tick) ----
    print_top_configs(df_1tick, metric="pnl_net", n=20,
                      title="TOP 20 PAR PNL NET (1 TICK SLIPPAGE)")

    # ---- Comparaison 2 ticks vs 1 tick ----
    print(f"\n{'='*130}")
    print("COMPARAISON 2 TICKS vs 1 TICK (memes configs)")
    print(f"{'='*130}")
    print(f"{'#':<3} {'Config':<50} {'PnL 2tick':>11} {'PnL 1tick':>11} {'Delta':>10} {'Trades':>7}")
    print("-" * 130)

    # Merge sur le label pour comparer
    df_compare = df_1tick.merge(
        df_source[["label", "pnl_net"]].rename(columns={"pnl_net": "pnl_2tick"}),
        on="label", how="left"
    )
    df_compare["delta"] = df_compare["pnl_net"] - df_compare["pnl_2tick"]
    df_compare = df_compare.sort_values("pnl_net", ascending=False)

    for i, (_, r) in enumerate(df_compare.head(20).iterrows()):
        pnl_2t = r.get("pnl_2tick", 0)
        print(f"{i+1:<3} {r['label']:<50} ${pnl_2t:>9,.0f} ${r['pnl_net']:>9,.0f} "
              f"${r['delta']:>+8,.0f} {r['trades']:>7}")

    # ---- Stats globales ----
    print(f"\n--- Statistiques globales ---")
    print(f"Delta moyen (1tick - 2tick) : ${df_compare['delta'].mean():>+,.0f}")
    print(f"Delta median                : ${df_compare['delta'].median():>+,.0f}")
    print(f"Delta min/max               : ${df_compare['delta'].min():>+,.0f} / ${df_compare['delta'].max():>+,.0f}")
    print(f"Rentables 2 ticks           : {len(df_compare[df_compare['pnl_2tick'] > 0])} / {n_total}")
    print(f"Rentables 1 tick            : {n_profitable} / {n_total}")

    print(f"\n[OK] Resultats sauvegardes dans {OUTPUT_CSV}")
    print(f"[OK] Duree totale : {t_total:.0f}s ({t_total/60:.1f} min)")
