# ============================================================================
# RUN_HELPERS.PY - Fonctions utilitaires partagees par les scripts run_*.py
# ============================================================================
#
# Factorise le code duplique entre les scripts d'execution :
#   - Chargement des donnees (1min/5min + 5s)
#   - Comptage des exit reasons
#   - Reprise CSV interrompu
#   - Sauvegarde batch CSV
#   - Affichage formate des top configs
#
# ============================================================================

import time
from pathlib import Path

import pandas as pd


# ============================================================================
# CHARGEMENT DES DONNEES
# ============================================================================

def load_data_standard(timeframe="1min", verbose=False):
    """
    Charge les donnees synchronisees (1-min ou 5-min) + 5s.

    Args:
        timeframe: "1min" ou "5min"
        verbose: afficher les details de chargement

    Returns:
        tuple: (df_main, df_5s, base_config, stats)
            df_main : DataFrame 1-min ou 5-min selon le timeframe
            df_5s   : DataFrame 5-secondes
    """
    from data_loader import load_and_prepare_data, load_5s_data

    t0 = time.time()
    df_1min, base_config, stats = load_and_prepare_data(verbose=verbose)

    if timeframe == "5min":
        from data_loader import resample_to_5min
        df_main = resample_to_5min(df_1min)
        print(f"   {len(df_main):,} barres 5-min ({time.time()-t0:.1f}s)")
    else:
        df_main = df_1min
        print(f"   {len(df_main):,} barres 1-min ({time.time()-t0:.1f}s)")

    df_5s = load_5s_data(base_config, verbose=verbose)
    print(f"   {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    return df_main, df_5s, base_config, stats


# ============================================================================
# COMPTAGE EXIT REASONS
# ============================================================================

def count_exit_reasons(trades_df):
    """
    Compte les raisons de sortie (TP/SL par type).

    Args:
        trades_df: DataFrame des trades avec colonne 'Exit_Reason'

    Returns:
        dict: {tp_zscore, tp_dollar, sl_zscore, sl_dollar}
    """
    if len(trades_df) > 0:
        return {
            "tp_zscore": int((trades_df['Exit_Reason'] == 'TP_ZSCORE').sum()),
            "tp_dollar": int((trades_df['Exit_Reason'] == 'TP_DOLLAR').sum()),
            "sl_zscore": int((trades_df['Exit_Reason'] == 'SL_ZSCORE').sum()),
            "sl_dollar": int((trades_df['Exit_Reason'] == 'SL_DOLLAR').sum()),
        }
    return {"tp_zscore": 0, "tp_dollar": 0, "sl_zscore": 0, "sl_dollar": 0}


# ============================================================================
# REPRISE CSV
# ============================================================================

def check_csv_resumption(csv_path, label_col="label"):
    """
    Verifie si un CSV de resultats existe et retourne les labels deja traites.

    Args:
        csv_path: chemin du fichier CSV
        label_col: nom de la colonne contenant les labels

    Returns:
        set: labels deja completes (vide si le fichier n'existe pas)
    """
    csv_path = Path(csv_path)
    if csv_path.exists():
        existing = pd.read_csv(csv_path, sep=";")
        completed = set(existing[label_col].values)
        print(f"[RESUME] {len(completed):,} configs deja completees")
        return completed
    return set()


# ============================================================================
# SAUVEGARDE BATCH CSV
# ============================================================================

def save_batch_csv(batch_results, output_path):
    """
    Sauvegarde un batch de resultats en CSV (append si existe, create sinon).

    Args:
        batch_results: liste de dicts a sauvegarder
        output_path: chemin du fichier CSV

    Returns:
        int: nombre de lignes sauvegardees
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_batch = pd.DataFrame(batch_results)
    if output_path.exists():
        df_batch.to_csv(output_path, mode="a", header=False, index=False, sep=";")
    else:
        df_batch.to_csv(output_path, index=False, sep=";")

    return len(df_batch)


# ============================================================================
# AFFICHAGE RESULTATS
# ============================================================================

def print_top_configs(df, metric="pnl_net", n=20, min_trades=0, title=None):
    """
    Affiche un tableau formate des top N configs triees par metric.

    Args:
        df: DataFrame de resultats
        metric: colonne de tri (pnl_net, sharpe, profit_factor...)
        n: nombre de configs a afficher
        min_trades: filtre minimum de trades
        title: titre du tableau (optionnel)
    """
    if title:
        print(f"\n{'='*130}")
        print(title)
        print(f"{'='*130}")

    df_filt = df[df["trades"] >= min_trades] if min_trades > 0 else df
    if len(df_filt) == 0:
        print("   (aucune config avec assez de trades)")
        return

    top = df_filt.nlargest(n, metric)

    print(f"{'#':<3} {'Config':<55} {'Trades':>7} {'WR%':>6} "
          f"{'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
    print("-" * 130)

    for i, (_, r) in enumerate(top.iterrows()):
        label = str(r.get('label', 'unknown'))
        if len(label) > 54:
            label = label[:51] + "..."

        pnl_col = 'pnl_net' if 'pnl_net' in r.index else 'pnl_1tick'
        print(f"{i+1:<3} {label:<55} "
              f"{int(r.get('trades', 0)):>7} "
              f"{r.get('win_rate', 0):>5.1f}% "
              f"${r.get(pnl_col, 0):>9,.0f} "
              f"{r.get('profit_factor', 0):>6.2f} "
              f"${r.get('max_dd', 0):>8,.0f} "
              f"{r.get('sharpe', 0):>6.2f}")
