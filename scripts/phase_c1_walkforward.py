# ============================================================================
# PHASE C1 -- Walk-Forward Diagnostique (PAS eliminatoire)
# 330 configs C0 x 15 fenetres egales -> heatmap + fenetres toxiques
# Architecture : Full Run + Trade Slicing (indicateurs sur TOUTE la periode)
# ============================================================================

import sys
import time
import multiprocessing as mp
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides_fast

# ============================================================================
# CONSTANTES
# ============================================================================

N_WINDOWS = 15
NUM_WORKERS = 24
INPUT_CSV = "output/phase_c0_top500.csv"
OUTPUT_DIR = Path("output")
REPORT_DIR = Path("output/reports")

# Shared data for workers
_WORKER_DATA = {}


def _init_worker(df_5min_arg, df_5s_arg):
    """Initialise les donnees partagees dans chaque worker."""
    _WORKER_DATA["df_5min"] = df_5min_arg
    _WORKER_DATA["df_5s"] = df_5s_arg


# ============================================================================
# CONVERSION CSV -> OVERRIDES
# ============================================================================

def csv_row_to_overrides(row):
    """
    Convertit une ligne du CSV C0 en dict d'overrides.

    Conventions de signe (ref: grid_search_runner.py:505-511) :
    - CSV zE=3.5  -> entry.zscore_long = -3.5, entry.zscore_short = +3.5
    - CSV zTP=-1.0 -> exit.zscore_tp_long = +1.0, exit.zscore_tp_short = -1.0
    - CSV zSL=4.5  -> exit.zscore_sl_long = -4.5, exit.zscore_sl_short = +4.5
    """
    zE = float(row["zE"])
    zTP = float(row["zTP"])
    zSL = float(row["zSL"])

    overrides = {
        # Indicateurs
        "indicators.beta_lookback": int(row["beta"]),
        "indicators.zscore_period": int(row["zp"]),
        "indicators.correlation_period": int(row["cp"]),
        "indicators.adf_hurst_period": int(row["adf"]),
        "indicators.period": "5min",
        # Entry
        "entry.zscore_long": -abs(zE),
        "entry.zscore_short": abs(zE),
        "entry.cointegration_score_min": int(row["co"]),
        # Exit zscore -- tp_long = -zTP (PAS -abs(zTP))
        "exit.zscore_tp_enabled": True,
        "exit.zscore_tp_long": -zTP,
        "exit.zscore_tp_short": zTP,
        "exit.zscore_sl_long": -abs(zSL),
        "exit.zscore_sl_short": abs(zSL),
        # Dollar exits desactives (mode zscore pur)
        "exit.pnl_take_profit": 99999,
        "exit.pnl_stop_loss": -99999,
        # Slippage 1 tick
        "costs.slippage_gc_ticks": 1,
        "costs.slippage_si_ticks": 1,
    }

    # Asserts obligatoires
    assert overrides["entry.zscore_long"] < 0, f"zscore_long doit etre negatif: {overrides['entry.zscore_long']}"
    assert overrides["entry.zscore_short"] > 0, f"zscore_short doit etre positif: {overrides['entry.zscore_short']}"
    assert overrides["exit.zscore_sl_long"] < 0, f"zscore_sl_long doit etre negatif: {overrides['exit.zscore_sl_long']}"
    assert overrides["exit.zscore_sl_short"] > 0, f"zscore_sl_short doit etre positif: {overrides['exit.zscore_sl_short']}"

    return overrides


# ============================================================================
# CONSTRUCTION DES FENETRES
# ============================================================================

def build_windows(df_5min):
    """Construit 15 fenetres de taille egale en barres."""
    total_bars = len(df_5min)
    window_size = total_bars // N_WINDOWS

    windows = []
    for i in range(N_WINDOWS):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size if i < N_WINDOWS - 1 else total_bars
        start_dt = df_5min.iloc[start_idx]["DateTime"]
        end_dt = df_5min.iloc[end_idx - 1]["DateTime"]
        windows.append({
            "id": f"W{i+1:02d}",
            "start_dt": start_dt,
            "end_dt": end_dt,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "bars": end_idx - start_idx,
        })

    return windows


# ============================================================================
# WORKER MULTIPROCESSING
# ============================================================================

def _process_indicator_group(args):
    """Worker : 1 groupe indicateurs = 1 calcul + N backtests."""
    group_idx, ind_key, rows_data, base_config, windows = args
    df_5min = _WORKER_DATA["df_5min"]
    df_5s = _WORKER_DATA["df_5s"]

    # 1. Calculer indicateurs UNE SEULE FOIS pour ce groupe
    ind_overrides = {
        "indicators.beta_lookback": ind_key[0],
        "indicators.zscore_period": ind_key[1],
        "indicators.correlation_period": ind_key[2],
        "indicators.adf_hurst_period": ind_key[3],
        "indicators.period": "5min",
    }
    cfg_ind = apply_overrides_fast(base_config, ind_overrides)
    df_with_ind = calculate_all_indicators(df_5min.copy(), cfg_ind, verbose=False)

    results = []
    for row_dict in rows_data:
        # 2. Overrides entry/exit
        overrides = csv_row_to_overrides(row_dict)
        cfg = apply_overrides_fast(base_config, overrides)

        # 3. Backtest complet (df_5s necessaire meme en pure zscore, arrays extraits avant le skip)
        trades_df = run_hybrid_backtest(df_with_ind, df_5s, cfg, verbose=False)

        label = row_dict["label"]
        c0_pnl = float(row_dict["pnl_net"])

        # 4. Slicer les trades dans les fenetres
        total_wf_pnl = 0.0
        for w in windows:
            if len(trades_df) > 0:
                mask = (
                    (trades_df["Entry_DateTime"] >= w["start_dt"])
                    & (trades_df["Entry_DateTime"] <= w["end_dt"])
                )
                w_trades = trades_df[mask]
                w_pnl = float(w_trades["PnL_Net"].sum()) if len(w_trades) > 0 else 0.0
                w_count = len(w_trades)
            else:
                w_pnl = 0.0
                w_count = 0

            total_wf_pnl += w_pnl
            results.append({
                "label": label,
                "window": w["id"],
                "pnl": round(w_pnl, 2),
                "trades": w_count,
            })

        # 5. Coherence (ecart WF vs C0)
        ecart_pct = abs(total_wf_pnl - c0_pnl) / abs(c0_pnl) * 100 if c0_pnl != 0 else 0
        results[-N_WINDOWS]["_ecart_pct"] = round(ecart_pct, 1)

    return group_idx, results


# ============================================================================
# ANALYSE ET RAPPORT
# ============================================================================

def analyze_results(results_df, pivot, windows, c0_df):
    """Analyse et affiche les resultats."""
    lines = []
    lines.append("# Phase C1 -- Walk-Forward Diagnostique\n")
    lines.append(f"## Resume\n")
    lines.append(f"- **Configs** : {pivot.shape[0]}")
    lines.append(f"- **Fenetres** : {pivot.shape[1]}")
    lines.append(f"- **Total runs** : {len(results_df)}")
    lines.append("")

    # Tableau des fenetres
    lines.append("## Fenetres\n")
    lines.append("| Fenetre | Debut | Fin | Barres | PnL Moyen | % Perte | Statut |")
    lines.append("|---------|-------|-----|--------|-----------|---------|--------|")

    toxic_windows = []
    for w in windows:
        wid = w["id"]
        if wid not in pivot.columns:
            continue
        col = pivot[wid]
        pnl_mean = col.mean()
        pct_loss = (col < 0).sum() / len(col) * 100
        status = "TOXIQUE" if pct_loss > 60 else "OK"
        if pct_loss > 60:
            toxic_windows.append(wid)
        start_str = w["start_dt"].strftime("%Y-%m-%d")
        end_str = w["end_dt"].strftime("%Y-%m-%d")
        lines.append(
            f"| {wid} | {start_str} | {end_str} | {w['bars']:,} | "
            f"${pnl_mean:,.0f} | {pct_loss:.0f}% | {status} |"
        )

    lines.append("")
    lines.append(f"**Fenetres toxiques** : {', '.join(toxic_windows) if toxic_windows else 'Aucune'}")
    lines.append("")

    # Regularite
    regularity = (pivot > 0).sum(axis=1) / pivot.shape[1] * 100
    regularity = regularity.sort_values(ascending=False)

    lines.append("## Top 20 par regularite\n")
    lines.append("| # | Label | % Positives | PnL Total |")
    lines.append("|---|-------|-------------|-----------|")
    for i, (label, pct) in enumerate(regularity.head(20).items(), 1):
        total_pnl = pivot.loc[label].sum()
        lines.append(f"| {i} | {label} | {pct:.0f}% | ${total_pnl:,.0f} |")

    lines.append("")

    # Configs fragiles
    fragile = regularity[regularity < 30]
    lines.append(f"## Configs fragiles (<30% fenetres positives) : {len(fragile)}/{len(regularity)}")
    lines.append("")

    # Correlation inter-configs
    if pivot.shape[0] > 1:
        corr_matrix = pivot.T.corr()
        triu_idx = np.triu_indices_from(corr_matrix, k=1)
        avg_corr = corr_matrix.values[triu_idx].mean()
        lines.append(f"## Correlation inter-configs : {avg_corr:.3f}")
        lines.append("")

    # Coherence
    lines.append("## Verification de coherence (5 premieres configs)\n")
    lines.append("| Label | WF PnL | C0 PnL | Ecart |")
    lines.append("|-------|--------|--------|-------|")
    for label in c0_df["label"].head(5):
        wf_pnl = results_df[results_df["label"] == label]["pnl"].sum()
        c0_pnl = c0_df[c0_df["label"] == label]["pnl_net"].values[0]
        ecart = abs(wf_pnl - c0_pnl) / abs(c0_pnl) * 100 if c0_pnl != 0 else 0
        status = "OK" if ecart < 5 else "ALERTE"
        lines.append(f"| {label[:60]} | ${wf_pnl:,.0f} | ${c0_pnl:,.0f} | {ecart:.1f}% {status} |")

    lines.append("")
    lines.append("## Conclusions pour C2\n")
    if toxic_windows:
        lines.append(f"- {len(toxic_windows)} fenetres toxiques identifiees : {', '.join(toxic_windows)}")
        lines.append("- Ces fenetres sont les cibles prioritaires pour le filtre de regime C2")
    else:
        lines.append("- Aucune fenetre toxique (>60% configs en perte) identifiee")
    lines.append(f"- Correlation inter-configs elevee -> les configs respirent ensemble")
    lines.append("- Le filtre C2 doit cibler le regime de marche, pas la config individuelle")
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    t_global = time.time()
    print("=" * 70)
    print("PHASE C1 -- Walk-Forward Diagnostique")
    print("=" * 70)

    # 1. Charger les donnees
    print("\n[1/5] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data()
    df_5min = resample_to_5min(df_1min)
    print(f"  df_5min : {len(df_5min):,} barres")
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"  df_5s : {len(df_5s):,} barres")

    # 2. Construire les fenetres
    print("\n[2/5] Construction des 15 fenetres...")
    windows = build_windows(df_5min)
    for w in windows:
        print(f"  {w['id']}: {w['start_dt'].strftime('%Y-%m-%d')} -> {w['end_dt'].strftime('%Y-%m-%d')} ({w['bars']:,} barres)")

    # 3. Charger et grouper les configs C0
    print("\n[3/5] Chargement des configs C0...")
    c0_df = pd.read_csv(INPUT_CSV, sep=";")
    print(f"  Configs : {len(c0_df)}")

    groups = defaultdict(list)
    for _, row in c0_df.iterrows():
        key = (int(row["beta"]), int(row["zp"]), int(row["cp"]), int(row["adf"]))
        groups[key].append(row.to_dict())
    print(f"  Groupes indicateurs : {len(groups)}")

    # 4. Executer les backtests en parallele
    print(f"\n[4/5] Lancement de {NUM_WORKERS} workers ({len(c0_df)} backtests)...")
    worker_args = [
        (g_idx, ind_key, rows, base_config, windows)
        for g_idx, (ind_key, rows) in enumerate(groups.items())
    ]

    all_results = []
    groups_done = 0
    t_start = time.time()

    with mp.Pool(processes=NUM_WORKERS, initializer=_init_worker, initargs=(df_5min, df_5s)) as pool:
        for group_idx, batch_results in pool.imap_unordered(_process_indicator_group, worker_args):
            groups_done += 1
            # Retirer les champs internes
            for r in batch_results:
                r.pop("_ecart_pct", None)
            all_results.extend(batch_results)

            if groups_done % 10 == 0 or groups_done == len(groups):
                elapsed = time.time() - t_start
                pct = groups_done / len(groups) * 100
                configs_done = len(all_results) // N_WINDOWS
                print(f"  [{groups_done:>3}/{len(groups)}] {pct:.0f}% -- {configs_done} configs -- {elapsed:.0f}s", flush=True)

    results_df = pd.DataFrame(all_results)
    elapsed_total = time.time() - t_start
    print(f"  Termine : {len(results_df):,} lignes en {elapsed_total:.0f}s")

    # Verification colonne
    if len(results_df) == 0:
        print("ERREUR : aucun resultat !")
        return

    # 5. Construire les livrables
    print("\n[5/5] Generation des livrables...")

    # Pivot heatmap
    pivot = results_df.pivot(index="label", columns="window", values="pnl")
    pivot.to_csv(OUTPUT_DIR / "phase_c1_heatmap.csv", sep=";")
    print(f"  Heatmap : {pivot.shape[0]} x {pivot.shape[1]} -> phase_c1_heatmap.csv")

    # Detail complet
    results_df.to_csv(OUTPUT_DIR / "phase_c1_results.csv", sep=";", index=False)
    print(f"  Detail : {len(results_df):,} lignes -> phase_c1_results.csv")

    # Regularite
    regularity = (pivot > 0).sum(axis=1) / pivot.shape[1] * 100
    reg_df = pd.DataFrame({
        "label": regularity.index,
        "pct_positive": regularity.values,
        "total_pnl": pivot.sum(axis=1).values,
    }).sort_values("pct_positive", ascending=False)
    reg_df.to_csv(OUTPUT_DIR / "phase_c1_regularity.csv", sep=";", index=False)
    print(f"  Regularite : {len(reg_df)} configs -> phase_c1_regularity.csv")

    # Rapport
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = analyze_results(results_df, pivot, windows, c0_df)
    report_path = REPORT_DIR / "PHASE_C1_RESULTS.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Rapport -> {report_path}")

    # Resume console
    print("\n" + "=" * 70)
    print("RESUME")
    print("=" * 70)
    print(f"Temps total : {(time.time() - t_global) / 60:.1f} min")
    print(f"\nPnL moyen par fenetre :")
    for col in sorted(pivot.columns):
        pnl_mean = pivot[col].mean()
        pct_loss = (pivot[col] < 0).sum() / len(pivot) * 100
        marker = " << TOXIQUE" if pct_loss > 60 else ""
        print(f"  {col}: ${pnl_mean:>8,.0f}  ({pct_loss:.0f}% en perte){marker}")

    # Coherence
    print("\nCoherence WF vs C0 (5 premieres) :")
    for label in c0_df["label"].head(5):
        wf_pnl = results_df[results_df["label"] == label]["pnl"].sum()
        c0_pnl = c0_df[c0_df["label"] == label]["pnl_net"].values[0]
        ecart = abs(wf_pnl - c0_pnl) / abs(c0_pnl) * 100 if c0_pnl != 0 else 0
        print(f"  {label[:50]}: WF=${wf_pnl:,.0f} vs C0=${c0_pnl:,.0f} ({ecart:.1f}%)")


if __name__ == "__main__":
    main()
