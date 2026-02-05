"""
Grid Search Etendu - 1 tick slippage
Top 5 groupes indicateurs x (6 TP x 6 SL x 3 zE x 3 modes TP_ZSCORE x 2 co) = 3,240 configs

TP : 200, 300, 400, 500, 800, 1000
SL : -400, -600, -800, -1000, -1200, -1400
zE : -2.5, -3.0, -3.5
TP_ZSCORE : OFF / ON(floor=0) / ON(floor=200)
co : 50, 60
Slippage : 1 tick

Usage : python run_grid_search_extended_1tick.py
"""
import sys
import time
import itertools
import multiprocessing as mp
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from run_helpers import check_csv_resumption, save_batch_csv, print_top_configs

# ============================================================================
# PARAMETRES
# ============================================================================

# Top 5 groupes indicateurs (issus du grid search top 200 @ 1 tick)
INDICATOR_GROUPS = [
    {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
     "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128},
    {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
     "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128},
    {"indicators.beta_lookback": 660, "indicators.zscore_period": 15,
     "indicators.correlation_period": 60, "indicators.adf_hurst_period": 128},
    {"indicators.beta_lookback": 660, "indicators.zscore_period": 15,
     "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128},
    {"indicators.beta_lookback": 3960, "indicators.zscore_period": 20,
     "indicators.correlation_period": 60, "indicators.adf_hurst_period": 256},
]

TP_VALUES = [200, 300, 400, 500, 800, 1000]
SL_VALUES = [-400, -600, -800, -1000, -1200, -1400]
ZE_VALUES = [-2.5, -3.0, -3.5]
CO_VALUES = [50, 60]

# 3 modes TP_ZSCORE : OFF / ON(floor=0) / ON(floor=200)
ZSCORE_TP_MODES = [
    {"exit.zscore_tp_enabled": False, "exit.zscore_tp_min_pnl": 0},       # OFF
    {"exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 0},        # ON, floor=0
    {"exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 200},      # ON, floor=200
]

FIXED_OVERRIDES = {
    "costs.slippage_gc_ticks": 1,
    "costs.slippage_si_ticks": 1,
}

NUM_WORKERS = 12
OUTPUT_CSV = Path("output/grid_search_extended_1tick.csv")


# ============================================================================
# GENERATION DES VARIANTES ENTRY/EXIT
# ============================================================================

def generate_entry_exit_variants():
    """Genere toutes les combinaisons entry/exit (648 variantes)."""
    variants = []
    for zE, co, tp, sl, zscore_mode in itertools.product(
            ZE_VALUES, CO_VALUES, TP_VALUES, SL_VALUES, ZSCORE_TP_MODES):
        # Label du mode TP_ZSCORE
        if not zscore_mode["exit.zscore_tp_enabled"]:
            tp_zs_label = "tpzOFF"
        elif zscore_mode["exit.zscore_tp_min_pnl"] > 0:
            tp_zs_label = f"tpzF{zscore_mode['exit.zscore_tp_min_pnl']}"
        else:
            tp_zs_label = "tpzON"

        variants.append({
            "overrides": {
                "entry.zscore_long": zE,
                "entry.zscore_short": -zE,
                "entry.cointegration_score_min": co,
                "exit.pnl_take_profit": tp,
                "exit.pnl_stop_loss": sl,
                **zscore_mode,
            },
            "zE": abs(zE),
            "co": co,
            "tp": tp,
            "sl": abs(sl),
            "tp_zs_label": tp_zs_label,
        })
    return variants


def make_label(ind_group, variant):
    """Construit le label complet."""
    b = ind_group["indicators.beta_lookback"]
    zp = ind_group["indicators.zscore_period"]
    cp = ind_group["indicators.correlation_period"]
    adf = ind_group["indicators.adf_hurst_period"]
    v = variant
    return (f"b{b}_zp{zp}_cp{cp}_adf{adf}"
            f"_zE{v['zE']}_co{v['co']}_TP{v['tp']}_SL{v['sl']}_{v['tp_zs_label']}")


# ============================================================================
# WORKER
# ============================================================================

def process_group(args):
    """Worker : indicateurs 1x par groupe, puis boucle sur les variantes."""
    g_idx, ind_group, ee_variants, base_config, df_1min, df_5s, completed_labels = args

    from indicators import calculate_all_indicators
    from backtest_engine_hybrid import run_hybrid_backtest
    from optimizer import apply_overrides, compute_metrics

    # Calculer les indicateurs une fois
    config_ind = apply_overrides(base_config, ind_group)
    t0 = time.time()
    df_ind = calculate_all_indicators(df_1min, config_ind, verbose=False)
    dt_ind = time.time() - t0

    batch_results = []
    for variant in ee_variants:
        label = make_label(ind_group, variant)

        if label in completed_labels:
            continue

        # Merge overrides
        merged = {**ind_group, **variant["overrides"], **FIXED_OVERRIDES}
        config_test = apply_overrides(base_config, merged)

        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)

        from run_helpers import count_exit_reasons as _count_er
        exits = _count_er(trades)

        b = ind_group["indicators.beta_lookback"]
        zp = ind_group["indicators.zscore_period"]
        cp = ind_group["indicators.correlation_period"]
        adf = ind_group["indicators.adf_hurst_period"]

        batch_results.append({
            "label": label,
            "beta": b, "zp": zp, "cp": cp, "adf": adf,
            "zE": variant["zE"], "co": variant["co"],
            "TP": variant["tp"], "SL": variant["sl"],
            "tp_zscore_mode": variant["tp_zs_label"],
            "trades": m["trades"], "long": m["long"], "short": m["short"],
            "win_rate": round(m["win_rate"], 1),
            "pnl_net": round(m["pnl_net"], 0),
            "pnl_avg": round(m["pnl_avg"], 2),
            "profit_factor": round(m["profit_factor"], 2),
            "max_dd": round(m["max_dd"], 0),
            "sharpe": round(m["sharpe"], 2),
            **exits,
        })

    return g_idx, batch_results, dt_ind


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("GRID SEARCH ETENDU - 1 TICK SLIPPAGE")
    print("=" * 100)

    ee_variants = generate_entry_exit_variants()
    total_configs = len(INDICATOR_GROUPS) * len(ee_variants)

    print(f"\nGroupes indicateurs : {len(INDICATOR_GROUPS)}")
    print(f"Variantes entry/exit : {len(ee_variants)}")
    print(f"   TP : {TP_VALUES}")
    print(f"   SL : {[abs(s) for s in SL_VALUES]}")
    print(f"   zE : {[abs(z) for z in ZE_VALUES]}")
    print(f"   co : {CO_VALUES}")
    print(f"   TP_ZSCORE modes : OFF / ON(floor=0) / ON(floor=200)")
    print(f"Total configs : {total_configs:,}")
    print(f"Workers : {NUM_WORKERS}")
    print(f"Slippage : 1 tick GC + 1 tick SI")

    # Charger les donnees
    print("\nChargement des donnees...")
    t0 = time.time()
    from data_loader import load_and_prepare_data, load_5s_data
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    # Verifier reprise
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    completed_labels = check_csv_resumption(OUTPUT_CSV)

    remaining = total_configs - len(completed_labels)
    print(f"Configs restantes : {remaining:,}")

    # Preparer les args
    worker_args = [
        (g_idx, ind_group, ee_variants, base_config, df_1min, df_5s, completed_labels)
        for g_idx, ind_group in enumerate(INDICATOR_GROUPS)
    ]

    # Lancement
    n_workers = min(NUM_WORKERS, len(worker_args))
    print(f"\nLancement de {n_workers} workers...")
    t_start = time.time()

    groups_done = 0
    total_results = 0
    best_pnl = -999999
    best_label = ""

    with mp.Pool(processes=n_workers) as pool:
        for g_idx, batch_results, dt_ind in pool.imap_unordered(process_group, worker_args):
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

            ind = INDICATOR_GROUPS[g_idx]
            b = ind["indicators.beta_lookback"]
            zp = ind["indicators.zscore_period"]

            elapsed = time.time() - t_start
            print(f"[{groups_done}/{len(INDICATOR_GROUPS)}] b{b}_zp{zp} "
                  f"ind={dt_ind:.0f}s | {len(batch_results)} configs | "
                  f"batch best=${best_in_batch['pnl_net']:>+10,.0f} | "
                  f"global best=${best_pnl:>+10,.0f} ({elapsed:.0f}s)", flush=True)

    # ============================================================================
    # RESULTATS
    # ============================================================================
    t_total = time.time() - t_start

    if not OUTPUT_CSV.exists():
        print("[ERREUR] Aucun resultat.")
        sys.exit(1)

    df_all = pd.read_csv(OUTPUT_CSV, sep=";")
    n_total = len(df_all)
    n_profitable = len(df_all[df_all["pnl_net"] > 0])

    print("\n\n" + "=" * 140)
    print(f"RESULTATS : {n_total:,} configs en {t_total/60:.1f} min")
    print(f"Configs rentables : {n_profitable:,} / {n_total:,} ({n_profitable/n_total*100:.1f}%)")
    print(f"Best global : {best_label} PnL=${best_pnl:,.0f}")
    print("=" * 140)

    # ---- Top 30 par PnL ----
    print_top_configs(df_all, metric="pnl_net", n=30,
                      title="TOP 30 PAR PNL NET")

    # ---- Top 30 par Sharpe (min 15 trades) ----
    print_top_configs(df_all, metric="sharpe", n=30, min_trades=15,
                      title="TOP 30 PAR SHARPE (min 15 trades)")

    # ---- Comparaison par mode TP_ZSCORE ----
    print(f"\n{'='*100}")
    print("COMPARAISON PAR MODE TP_ZSCORE")
    print(f"{'='*100}")
    for mode in ["tpzOFF", "tpzON", "tpzF200"]:
        sub = df_all[df_all["tp_zscore_mode"] == mode]
        n_prof = len(sub[sub["pnl_net"] > 0])
        if len(sub) > 0:
            print(f"\n  {mode:>8} : {len(sub):>5} configs | rentables {n_prof:>4} ({n_prof/len(sub)*100:>5.1f}%) | "
                  f"PnL moy ${sub['pnl_net'].mean():>+8,.0f} | PnL med ${sub['pnl_net'].median():>+8,.0f} | "
                  f"best ${sub['pnl_net'].max():>+9,.0f} | Sharpe moy {sub['sharpe'].mean():>+5.2f}")

    # ---- Comparaison par zE ----
    print(f"\n{'='*100}")
    print("COMPARAISON PAR ZSCORE ENTRY")
    print(f"{'='*100}")
    for zE in sorted(df_all["zE"].unique()):
        sub = df_all[df_all["zE"] == zE]
        n_prof = len(sub[sub["pnl_net"] > 0])
        if len(sub) > 0:
            print(f"  zE={zE:>4} : {len(sub):>5} configs | rentables {n_prof:>4} ({n_prof/len(sub)*100:>5.1f}%) | "
                  f"PnL moy ${sub['pnl_net'].mean():>+8,.0f} | best ${sub['pnl_net'].max():>+9,.0f} | "
                  f"Sharpe moy {sub['sharpe'].mean():>+5.2f}")

    # ---- Comparaison par TP/SL ----
    print(f"\n{'='*100}")
    print("HEATMAP PNL MOYEN PAR TP / SL (toutes configs)")
    print(f"{'='*100}")
    pivot = df_all.pivot_table(values="pnl_net", index="SL", columns="TP", aggfunc="mean")
    pivot = pivot.sort_index(ascending=False)
    header = "SL\\TP"
    print(f"\n{header:>8}", end="")
    for tp in sorted(pivot.columns):
        print(f"  TP={int(tp):>5}", end="")
    print()
    print("-" * (8 + len(pivot.columns) * 10))
    for sl in pivot.index:
        print(f"SL={int(sl):>5}", end="")
        for tp in sorted(pivot.columns):
            val = pivot.loc[sl, tp]
            print(f"  ${val:>+7,.0f}", end="")
        print()

    print(f"\n[OK] Resultats sauvegardes dans {OUTPUT_CSV}")
    print(f"[OK] Duree totale : {t_total/60:.1f} min")
