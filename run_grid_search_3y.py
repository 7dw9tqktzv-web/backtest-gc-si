"""
Grid Search Phase 1 - Donnees 3 ans (Jan 2023 - Jan 2026)
300 groupes indicateurs x 108 entry/exit = 32,400 configs
VERSION PARALLELE (multiprocessing)

Indicateurs :
  beta_lookback: 660, 1320, 1980, 2640, 3960
  zscore_period: 15, 20, 30, 50, 60
  correlation_period: 20, 30, 50, 60
  adf_hurst_period: 64, 128, 256

Entry/Exit :
  zscore_entry: -2.0, -2.5, -3.0, -3.5
  cointegration_score_min: 40, 50, 60
  pnl_take_profit: 200, 300, 400
  pnl_stop_loss: -400, -600, -800

Fixes : zscore_tp_min_pnl=0, slippage 2 ticks, commission $4
"""
import sys
import time
import itertools
import multiprocessing as mp
from pathlib import Path
from functools import partial

import pandas as pd
import numpy as np

sys.path.insert(0, "src")

# ============================================================================
# GRILLE DE PARAMETRES
# ============================================================================

INDICATOR_PARAMS = {
    "beta_lookback": [660, 1320, 1980, 2640, 3960],
    "zscore_period": [15, 20, 30, 50, 60],
    "correlation_period": [20, 30, 50, 60],
    "adf_hurst_period": [64, 128, 256],
}

ENTRY_EXIT_PARAMS = {
    "zscore_entry": [-2.0, -2.5, -3.0, -3.5],
    "cointegration_score_min": [40, 50, 60],
    "pnl_take_profit": [200, 300, 400],
    "pnl_stop_loss": [-400, -600, -800],
}

FIXED_OVERRIDES = {
    "exit.zscore_tp_min_pnl": 0,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

NUM_WORKERS = 8  # 8 workers x ~2-3 Go RAM = ~20 Go (sur 49 Go libres)

# ============================================================================
# GENERATION DES COMBINAISONS
# ============================================================================

def generate_indicator_groups():
    keys = list(INDICATOR_PARAMS.keys())
    values = [INDICATOR_PARAMS[k] for k in keys]
    groups = []
    for combo in itertools.product(*values):
        overrides = {f"indicators.{keys[i]}": combo[i] for i in range(len(keys))}
        groups.append(overrides)
    return groups


def generate_entry_exit_variants():
    variants = []
    for zE in ENTRY_EXIT_PARAMS["zscore_entry"]:
        for co in ENTRY_EXIT_PARAMS["cointegration_score_min"]:
            for tp in ENTRY_EXIT_PARAMS["pnl_take_profit"]:
                for sl in ENTRY_EXIT_PARAMS["pnl_stop_loss"]:
                    variants.append({
                        "entry.zscore_long": zE,
                        "entry.zscore_short": -zE,
                        "entry.cointegration_score_min": co,
                        "exit.pnl_take_profit": tp,
                        "exit.pnl_stop_loss": sl,
                    })
    return variants


# ============================================================================
# WORKER : traite un groupe d'indicateurs complet
# ============================================================================

def process_indicator_group(args):
    """
    Worker function : calcule les indicateurs pour un groupe,
    puis execute les 108 backtests entry/exit.
    Retourne une liste de dicts (resultats).
    """
    g_idx, ind_ov, base_config, df_1min, df_5s, ee_variants, completed_labels = args

    # Import dans le worker (necessaire pour multiprocessing)
    from indicators import calculate_all_indicators
    from backtest_engine_hybrid import run_hybrid_backtest
    from optimizer import apply_overrides, compute_metrics

    beta = ind_ov["indicators.beta_lookback"]
    zp = ind_ov["indicators.zscore_period"]
    cp = ind_ov["indicators.correlation_period"]
    adf = ind_ov["indicators.adf_hurst_period"]
    group_prefix = f"b{beta}_zp{zp}_cp{cp}_adf{adf}"

    # Verifier si tout le groupe est deja fait
    group_done = all(
        f"{group_prefix}_zE{abs(ee['entry.zscore_long'])}_co{ee['entry.cointegration_score_min']}_TP{ee['exit.pnl_take_profit']}_SL{abs(ee['exit.pnl_stop_loss'])}"
        in completed_labels
        for ee in ee_variants
    )
    if group_done:
        return g_idx, [], 0.0

    # Calculer les indicateurs
    config_ind = apply_overrides(base_config, ind_ov)
    t_ind = time.time()
    df_ind = calculate_all_indicators(df_1min, config_ind, verbose=False)
    dt_ind = time.time() - t_ind

    # Tester toutes les variantes entry/exit
    batch_results = []
    for ee_ov in ee_variants:
        zE = abs(ee_ov["entry.zscore_long"])
        co = ee_ov["entry.cointegration_score_min"]
        tp = ee_ov["exit.pnl_take_profit"]
        sl = abs(ee_ov["exit.pnl_stop_loss"])
        label = f"{group_prefix}_zE{zE}_co{co}_TP{tp}_SL{sl}"

        if label in completed_labels:
            continue

        merged = {**ind_ov, **ee_ov, **FIXED_OVERRIDES}
        config_test = apply_overrides(base_config, merged)
        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)

        if len(trades) > 0:
            tp_zscore = (trades['Exit_Reason'] == 'TP_ZSCORE').sum()
            tp_dollar = (trades['Exit_Reason'] == 'TP_DOLLAR').sum()
            sl_zscore = (trades['Exit_Reason'] == 'SL_ZSCORE').sum()
            sl_dollar = (trades['Exit_Reason'] == 'SL_DOLLAR').sum()
        else:
            tp_zscore = tp_dollar = sl_zscore = sl_dollar = 0

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
            "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
            "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
        })

    return g_idx, batch_results, dt_ind


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("GRID SEARCH PHASE 1 - DONNEES 3 ANS (PARALLELE)")
    print("=" * 100)

    ind_groups = generate_indicator_groups()
    ee_variants = generate_entry_exit_variants()
    total_configs = len(ind_groups) * len(ee_variants)

    print(f"\nGroupes indicateurs : {len(ind_groups)}")
    print(f"Variantes entry/exit : {len(ee_variants)}")
    print(f"Total configs : {total_configs:,}")
    print(f"Workers : {NUM_WORKERS}")
    print(f"Fixes : zscore_tp_min_pnl=0, slippage=2 ticks")

    # Charger les donnees (une seule fois dans le process principal)
    print("\nChargement des donnees...")
    t0 = time.time()
    from data_loader import load_and_prepare_data
    from data_loader_5s import load_5s_data
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # Fichier de sortie
    output_path = Path("output/grid_search_3y_phase1.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Verifier reprise
    completed_labels = set()
    if output_path.exists():
        existing = pd.read_csv(output_path, sep=";")
        completed_labels = set(existing["label"].values)
        print(f"\n[RESUME] {len(completed_labels):,} configs deja completees, reprise...")

    # Preparer les arguments pour les workers
    worker_args = [
        (g_idx, ind_ov, base_config, df_1min, df_5s, ee_variants, completed_labels)
        for g_idx, ind_ov in enumerate(ind_groups)
    ]

    print(f"\nLancement de {NUM_WORKERS} workers en parallele...")
    t_start = time.time()

    groups_done = 0
    total_results = 0
    best_pnl_global = -999999
    best_label_global = ""

    # Utiliser Pool avec imap_unordered pour obtenir les resultats au fur et a mesure
    with mp.Pool(processes=NUM_WORKERS) as pool:
        for g_idx, batch_results, dt_ind in pool.imap_unordered(process_indicator_group, worker_args):
            groups_done += 1

            if not batch_results:
                continue

            # Sauvegarder le batch
            df_batch = pd.DataFrame(batch_results)
            if output_path.exists():
                df_batch.to_csv(output_path, mode="a", header=False, index=False, sep=";")
            else:
                df_batch.to_csv(output_path, index=False, sep=";")

            total_results += len(batch_results)
            best = max(batch_results, key=lambda x: x["pnl_net"])
            if best["pnl_net"] > best_pnl_global:
                best_pnl_global = best["pnl_net"]
                best_label_global = best["label"]

            elapsed = time.time() - t_start
            pct = groups_done / len(ind_groups) * 100
            eta_min = (elapsed / groups_done * (len(ind_groups) - groups_done)) / 60 if groups_done > 0 else 0

            # Retrouver les params du groupe
            ind_ov = ind_groups[g_idx]
            beta = ind_ov["indicators.beta_lookback"]
            zp = ind_ov["indicators.zscore_period"]
            cp = ind_ov["indicators.correlation_period"]

            print(f"[{groups_done:>3}/{len(ind_groups)}] b{beta}_zp{zp}_cp{cp} "
                  f"ind={dt_ind:.0f}s | {len(batch_results)} configs | "
                  f"best=${best['pnl_net']:>+10,.0f} Sh={best['sharpe']:>+6.2f} | "
                  f"{pct:.0f}% {elapsed/60:.0f}min ETA={eta_min:.0f}min", flush=True)

    # ============================================================================
    # RESULTATS FINAUX
    # ============================================================================
    t_total = time.time() - t_start

    if output_path.exists():
        df_all = pd.read_csv(output_path, sep=";")
    else:
        df_all = pd.DataFrame()

    n_total = len(df_all)
    n_profitable = len(df_all[df_all["pnl_net"] > 0]) if n_total > 0 else 0

    print("\n\n" + "=" * 120)
    print(f"GRID SEARCH TERMINE : {n_total:,} configs en {t_total/3600:.1f}h")
    print(f"Configs rentables : {n_profitable:,} / {n_total:,} ({n_profitable/n_total*100:.1f}%)" if n_total > 0 else "Aucun resultat")
    print(f"Meilleur global : {best_label_global} PnL=${best_pnl_global:,.0f}")
    print("=" * 120)

    if n_total == 0:
        print("[ERREUR] Aucun resultat. Verifier les logs.")
        sys.exit(1)

    # Top 20 par PnL
    top_pnl = df_all.nlargest(20, "pnl_net")
    print(f"\n{'='*120}")
    print("TOP 20 PAR PNL NET")
    print(f"{'='*120}")
    print(f"{'#':<3} {'Config':<55} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
    print("-" * 120)
    for i, (_, r) in enumerate(top_pnl.iterrows()):
        print(f"{i+1:<3} {r['label']:<55} {r['trades']:>7} {r['win_rate']:>5.1f}% "
              f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['sharpe']:>6.2f}")

    # Top 20 par Sharpe (min 20 trades)
    df_filtered = df_all[df_all["trades"] >= 20]
    if len(df_filtered) > 0:
        top_sharpe = df_filtered.nlargest(20, "sharpe")
        print(f"\n{'='*120}")
        print("TOP 20 PAR SHARPE (min 20 trades)")
        print(f"{'='*120}")
        print(f"{'#':<3} {'Config':<55} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
        print("-" * 120)
        for i, (_, r) in enumerate(top_sharpe.iterrows()):
            print(f"{i+1:<3} {r['label']:<55} {r['trades']:>7} {r['win_rate']:>5.1f}% "
                  f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['sharpe']:>6.2f}")

    # Top 20 par PnL/MaxDD ratio (min 20 trades)
    df_filtered2 = df_filtered.copy()
    df_filtered2["pnl_dd_ratio"] = df_filtered2.apply(
        lambda r: r["pnl_net"] / abs(r["max_dd"]) if r["max_dd"] != 0 else 0, axis=1)
    top_ratio = df_filtered2.nlargest(20, "pnl_dd_ratio")
    print(f"\n{'='*120}")
    print("TOP 20 PAR PNL/MAXDD RATIO (min 20 trades)")
    print(f"{'='*120}")
    print(f"{'#':<3} {'Config':<55} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Ratio':>7}")
    print("-" * 120)
    for i, (_, r) in enumerate(top_ratio.iterrows()):
        print(f"{i+1:<3} {r['label']:<55} {r['trades']:>7} {r['win_rate']:>5.1f}% "
              f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['pnl_dd_ratio']:>6.2f}")

    print(f"\n[OK] Resultats sauvegardes dans {output_path}")
    print(f"[OK] Duree totale : {t_total/3600:.1f}h ({t_total/60:.0f} min)")
