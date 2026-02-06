# ============================================================================
# OPTIMIZER.PY - Backtest Multi-Config
# ============================================================================
#
# Ce module charge les donnees UNE fois, puis execute N backtests avec des
# configurations differentes en boucle. Un tableau comparatif est affiche
# a la fin.
#
# Utilise par :
#   - Le skill /optimize (grid search)
#   - Execution directe : python src/optimizer.py
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import copy
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest, export_backtest
try:
    from common import build_config_fingerprint
except ImportError:
    from .common import build_config_fingerprint


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def apply_overrides(config, overrides):
    """
    Apply parameter overrides to a deep copy of the configuration.

    Keys use dot notation to access nested keys.
    Example: "exit.pnl_take_profit" -> config['exit']['pnl_take_profit']

    Parameters
    ----------
    config : dict
        Base configuration loaded from YAML.
    overrides : dict
        Parameters to modify. Keys are dot-separated paths,
        values are the new values.

    Returns
    -------
    dict
        Deep copy of config with overrides applied.
    """
    cfg = copy.deepcopy(config)
    for dotted_key, value in overrides.items():
        keys = dotted_key.split('.')
        target = cfg
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return cfg


def apply_overrides_fast(config, overrides):
    """
    Version rapide sans deepcopy pour les hot paths (grid search).

    Fait une copie superficielle du dict racine et des sous-dicts touches.
    Ne PAS muter le resultat apres retour (usage unique par backtest).
    """
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in config.items()}
    for dotted_key, value in overrides.items():
        keys = dotted_key.split('.')
        if len(keys) == 2:
            section, param = keys
            if section not in cfg or not isinstance(cfg[section], dict):
                cfg[section] = dict(config.get(section, {}))
            cfg[section][param] = value
        else:
            target = cfg
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                else:
                    target[k] = dict(target[k])
                target = target[k]
            target[keys[-1]] = value
    return cfg


def build_label(overrides):
    """
    Build a short label from overrides using parameter shortcuts.

    Example: {"exit.pnl_take_profit": 500, "indicators.beta_lookback": 1320}
        -> "TP500_beta1320"

    Returns "baseline" if overrides is empty.
    """
    if not overrides:
        return "baseline"

    # Raccourcis pour les noms de parametres courants
    shortcuts = {
        "indicators.beta_lookback": "beta",
        "indicators.zscore_period": "zp",
        "indicators.correlation_period": "corr",
        "indicators.adf_hurst_period": "adf",
        "entry.zscore_long": "zEL",
        "entry.zscore_short": "zES",
        "entry.correlation_min": "corrMin",
        "entry.cointegration_score_min": "coint",
        "entry.hurst_max": "hMax",
        "exit.zscore_tp_long": "zTPL",
        "exit.zscore_tp_short": "zTPS",
        "exit.zscore_sl_long": "zSLL",
        "exit.zscore_sl_short": "zSLS",
        "exit.pnl_take_profit": "TP",
        "exit.pnl_stop_loss": "SL",
    }

    parts = []
    for key, val in overrides.items():
        short = shortcuts.get(key, key.split('.')[-1])
        # Formater la valeur (enlever le signe negatif pour les seuils)
        if isinstance(val, float):
            val_str = f"{val:g}"
        else:
            val_str = str(val)
        parts.append(f"{short}{val_str}")

    return "_".join(parts)


def compute_metrics(trades_df):
    """
    Compute key performance metrics from a trades DataFrame.

    Sharpe ratio is computed per trade (not annualized), consistent
    with metrics.py: Sharpe = mean(PnL) / std(PnL).

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade list with 'PnL_Net' and 'Direction' columns.

    Returns
    -------
    dict
        Performance metrics: trades, long, short, winners, win_rate,
        pnl_net, pnl_avg, best, worst, max_dd, profit_factor, sharpe.
        All values are 0 if trades_df is empty.
    """
    n = len(trades_df)
    if n == 0:
        return {
            "trades": 0, "long": 0, "short": 0,
            "winners": 0, "win_rate": 0.0,
            "pnl_net": 0.0, "pnl_avg": 0.0,
            "best": 0.0, "worst": 0.0,
            "max_dd": 0.0, "profit_factor": 0.0, "sharpe": 0.0
        }

    pnl = trades_df['PnL_Net']
    n_long = len(trades_df[trades_df['Direction'] == 'LONG'])
    n_short = len(trades_df[trades_df['Direction'] == 'SHORT'])
    winners = (pnl > 0).sum()
    win_rate = winners / n * 100

    pnl_net = pnl.sum()
    pnl_avg = pnl.mean()
    best = pnl.max()
    worst = pnl.min()

    # Max drawdown
    cumul = pnl.cumsum()
    max_dd = (cumul - cumul.cummax()).min()

    # Profit factor
    gains = pnl[pnl > 0].sum()
    losses = abs(pnl[pnl <= 0].sum())
    profit_factor = gains / losses if losses > 0 else float('inf')

    # Sharpe (par trade, non annualise -- coherent avec metrics.py)
    if pnl.std() > 0:
        sharpe = pnl.mean() / pnl.std()
    else:
        sharpe = 0.0

    return {
        "trades": n,
        "long": n_long,
        "short": n_short,
        "winners": winners,
        "win_rate": round(win_rate, 1),
        "pnl_net": round(pnl_net, 2),
        "pnl_avg": round(pnl_avg, 2),
        "best": round(best, 2),
        "worst": round(worst, 2),
        "max_dd": round(max_dd, 2),
        "profit_factor": round(profit_factor, 2),
        "sharpe": round(sharpe, 3)
    }


# ============================================================================
# SAUVEGARDE DES RESULTATS DANS LE LOG
# ============================================================================

LOG_PATH = Path("output/optimization_log.csv")
LOG_COLUMNS = [
    "DateTime", "Batch_ID", "Label", "Overrides",
    "Trades", "LONG", "SHORT", "Winners", "Win_Rate",
    "PnL_Net", "PnL_Avg", "Best", "Worst", "Max_Drawdown",
    "Profit_Factor", "Sharpe", "Fingerprint"
]


def save_results_to_log(results, overrides_map, batch_id=None):
    """
    Save optimization results to the CSV log file.

    Parameters
    ----------
    results : list of dict
        Metrics for each config (returned by run_optimization).
    overrides_map : dict
        Mapping of label -> overrides dict (to record tested parameters).
    batch_id : str, optional
        Batch identifier (default: timestamp YYYYmmdd_HHMMSS).
    """
    if batch_id is None:
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for r in results:
        label = r.get("label", "")
        overrides = overrides_map.get(label, {})
        # Formater les overrides en texte lisible : "key=val|key=val"
        ov_str = "|".join(f"{k}={v}" for k, v in overrides.items()) if overrides else "baseline"

        rows.append({
            "DateTime": now,
            "Batch_ID": batch_id,
            "Label": label,
            "Overrides": ov_str,
            "Trades": r.get("trades", 0),
            "LONG": r.get("long", 0),
            "SHORT": r.get("short", 0),
            "Winners": r.get("winners", 0),
            "Win_Rate": r.get("win_rate", 0.0),
            "PnL_Net": r.get("pnl_net", 0.0),
            "PnL_Avg": r.get("pnl_avg", 0.0),
            "Best": r.get("best", 0.0),
            "Worst": r.get("worst", 0.0),
            "Max_Drawdown": r.get("max_dd", 0.0),
            "Profit_Factor": r.get("profit_factor", 0.0),
            "Sharpe": r.get("sharpe", 0.0),
            "Fingerprint": r.get("fingerprint", ""),
        })

    df_new = pd.DataFrame(rows, columns=LOG_COLUMNS)

    # Append au fichier existant (ou creer si absent)
    if LOG_PATH.exists():
        df_new.to_csv(LOG_PATH, sep=';', index=False, mode='a', header=False)
    else:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_new.to_csv(LOG_PATH, sep=';', index=False)

    print(f"\n   [LOG] {len(rows)} resultats sauvegardes dans {LOG_PATH}")
    print(f"         Batch ID: {batch_id}")


def load_log():
    """
    Load the full optimization log from CSV.

    Returns
    -------
    pd.DataFrame
        All log rows, or empty DataFrame if file does not exist.
    """
    if not LOG_PATH.exists():
        print("   Aucun log d'optimisation trouve.")
        return pd.DataFrame(columns=LOG_COLUMNS)

    df = pd.read_csv(LOG_PATH, sep=';')
    print(f"   [LOG] {len(df)} resultats charges depuis {LOG_PATH}")
    return df


def print_log_summary(df=None, top_n=20, sort_by="PnL_Net"):
    """
    Print a formatted summary of the optimization log.

    Parameters
    ----------
    df : pd.DataFrame, optional
        Log to display. If None, loads from file.
    top_n : int
        Number of results to display.
    sort_by : str
        Sort column (PnL_Net, Profit_Factor, Win_Rate, Sharpe, Max_Drawdown).
    """
    if df is None:
        df = load_log()

    if df.empty:
        return

    # Trier
    ascending = sort_by == "Max_Drawdown"
    df_sorted = df.sort_values(sort_by, ascending=ascending).head(top_n)

    print(f"\n{'=' * 110}")
    print(f"TOP {min(top_n, len(df_sorted))} RESULTATS (trie par {sort_by}) -- {len(df)} total dans le log")
    print(f"{'=' * 110}")
    print(f"{'#':<3} {'Batch':<16} {'Label':<25} {'Trades':<7} {'WR%':<7} "
          f"{'PnL':<11} {'PF':<6} {'MaxDD':<10} {'Sharpe':<8}")
    print(f"{'-' * 110}")

    for i, (_, r) in enumerate(df_sorted.iterrows()):
        print(f"{i+1:<3} {str(r.get('Batch_ID', '')):<16} "
              f"{str(r.get('Label', '')):<25} "
              f"{int(r.get('Trades', 0)):<7} "
              f"{r.get('Win_Rate', 0):<7.1f} "
              f"${r.get('PnL_Net', 0):>9,.0f} "
              f"{r.get('Profit_Factor', 0):<6.2f} "
              f"${r.get('Max_Drawdown', 0):>8,.0f} "
              f"{r.get('Sharpe', 0):<8.3f}")

    print(f"{'=' * 110}")

    # Nombre de batches distincts
    n_batches = df['Batch_ID'].nunique()
    print(f"\n   {len(df)} configs au total dans {n_batches} batch(es)")


def delete_batch(batch_id):
    """
    Delete an entire batch from the optimization log.

    Parameters
    ----------
    batch_id : str
        Batch identifier to remove.
    """
    if not LOG_PATH.exists():
        print("   Aucun log trouve.")
        return

    df = pd.read_csv(LOG_PATH, sep=';')
    before = len(df)
    df = df[df['Batch_ID'] != batch_id]
    after = len(df)

    if before == after:
        print(f"   Batch '{batch_id}' non trouve dans le log.")
        return

    df.to_csv(LOG_PATH, sep=';', index=False)
    print(f"   [LOG] Batch '{batch_id}' supprime : {before - after} lignes retirees ({after} restantes)")


def keep_top_n(n=50, sort_by="PnL_Net"):
    """
    Keep only the top N results in the optimization log, removing the rest.

    Parameters
    ----------
    n : int
        Number of results to keep.
    sort_by : str
        Sort criterion to determine "best" results.
    """
    if not LOG_PATH.exists():
        print("   Aucun log trouve.")
        return

    df = pd.read_csv(LOG_PATH, sep=';')
    before = len(df)

    if before <= n:
        print(f"   Le log contient {before} lignes (<= {n}), rien a supprimer.")
        return

    ascending = sort_by == "Max_Drawdown"
    df = df.sort_values(sort_by, ascending=ascending).head(n)
    df.to_csv(LOG_PATH, sep=';', index=False)
    print(f"   [LOG] Log nettoye : {before} -> {n} lignes (top {n} par {sort_by})")


# ============================================================================
# EXECUTION D'UN BACKTEST POUR UNE CONFIG
# ============================================================================

def run_single_config(df_1min, df_5s, config, label="", verbose=True):
    """
    Run a complete hybrid backtest for a single configuration.

    Computes indicators, runs the backtest, exports results, and
    returns performance metrics.

    Parameters
    ----------
    df_1min : pd.DataFrame
        Synchronized 1-minute data (raw, without indicators).
    df_5s : pd.DataFrame
        Synchronized 5-second data.
    config : dict
        Complete strategy configuration.
    label : str
        Label to identify this config in results.
    verbose : bool
        Print progress messages (default: True).

    Returns
    -------
    dict
        Performance metrics with additional 'label' and 'fingerprint' keys.
    """
    if verbose:
        print(f"\n--- Config: {label} ---")

    # 1. Calculer les indicateurs (fait un .copy() en interne)
    df_ind = calculate_all_indicators(df_1min, config)

    # 2. Lancer le backtest hybride
    trades_df = run_hybrid_backtest(df_ind, df_5s, config)

    # 3. Exporter (ecrase le precedent)
    export_backtest(trades_df, config, "output/backtest_hybrid.csv")

    # 4. Calculer les metriques
    metrics = compute_metrics(trades_df)
    metrics["label"] = label
    metrics["fingerprint"] = build_config_fingerprint(config)

    if verbose:
        print(f"   -> {metrics['trades']} trades | "
              f"WR {metrics['win_rate']}% | "
              f"PnL ${metrics['pnl_net']:,.0f} | "
              f"PF {metrics['profit_factor']:.2f}")

    return metrics


# ============================================================================
# ORCHESTRATEUR MULTI-CONFIG
# ============================================================================

def run_optimization(configs_list, verbose=True):
    """
    Run N backtests with different configurations.

    Loads data ONCE, then loops over each config. Results are displayed
    in a comparison table and saved to the optimization log.

    Parameters
    ----------
    configs_list : list of dict
        List of config specifications, each with:
        - "label" (str, optional): config name (auto-generated if missing)
        - "overrides" (dict): parameters to modify (dot notation)
        Example: [
            {"label": "baseline", "overrides": {}},
            {"label": "TP500", "overrides": {"exit.pnl_take_profit": 500}},
        ]
    verbose : bool
        Print progress messages (default: True).

    Returns
    -------
    list of dict
        Performance metrics for each configuration.
    """
    print("\n" + "=" * 60)
    print("OPTIMISATION MULTI-CONFIG")
    print("=" * 60)
    print(f"   Configurations a tester : {len(configs_list)}")

    # 1. Charger les donnees (1 seule fois)
    print("\n[1/3] Chargement des donnees...")
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    print(f"   [OK] Donnees 1-min : {len(df_1min):,} barres")

    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   [OK] Donnees 5s : {len(df_5s):,} barres")

    # 2. Boucle sur chaque config
    print(f"\n[2/3] Execution des backtests...")
    results = []

    for i, cfg_spec in enumerate(configs_list):
        overrides = cfg_spec.get("overrides", {})
        label = cfg_spec.get("label", build_label(overrides))

        print(f"\n   [{i+1}/{len(configs_list)}] {label}")

        # Appliquer les overrides sur la config de base
        config_i = apply_overrides(base_config, overrides)

        # Executer le backtest
        metrics = run_single_config(df_1min, df_5s, config_i, label, verbose=False)
        results.append(metrics)

        # Afficher un resume rapide
        print(f"      Trades: {metrics['trades']} | "
              f"WR: {metrics['win_rate']}% | "
              f"PnL: ${metrics['pnl_net']:,.0f} | "
              f"PF: {metrics['profit_factor']:.2f} | "
              f"MaxDD: ${metrics['max_dd']:,.0f}")

    # 3. Afficher le tableau comparatif
    print(f"\n[3/3] Resultats")
    print_comparison_table(results)

    # 4. Sauvegarder dans le log
    overrides_map = {}
    for cfg_spec in configs_list:
        overrides = cfg_spec.get("overrides", {})
        label = cfg_spec.get("label", build_label(overrides))
        overrides_map[label] = overrides

    save_results_to_log(results, overrides_map)

    return results


# ============================================================================
# AFFICHAGE DU TABLEAU COMPARATIF
# ============================================================================

def print_comparison_table(results, sort_by="pnl_net"):
    """
    Print a formatted comparison table of results, sorted by chosen criterion.

    Parameters
    ----------
    results : list of dict
        Metrics for each config (from run_optimization).
    sort_by : str
        Sort criterion (pnl_net, profit_factor, win_rate, sharpe, max_dd).
    """
    if not results:
        print("   Aucun resultat a afficher.")
        return

    # Trier par le critere choisi (descending sauf max_dd)
    reverse = sort_by != "max_dd"
    sorted_results = sorted(results, key=lambda x: x.get(sort_by, 0), reverse=reverse)

    # En-tete
    print("\n" + "=" * 95)
    print(f"COMPARAISON DES CONFIGURATIONS (trie par {sort_by})")
    print("=" * 95)
    print(f"{'#':<3} {'Label':<20} {'Trades':<8} {'WR%':<7} {'PnL':<12} "
          f"{'PF':<6} {'MaxDD':<10} {'Sharpe':<8} {'Best':<9} {'Worst':<9}")
    print("-" * 95)

    for i, r in enumerate(sorted_results):
        print(f"{i+1:<3} {r['label']:<20} {r['trades']:<8} "
              f"{r['win_rate']:<7} "
              f"${r['pnl_net']:>9,.0f}  "
              f"{r['profit_factor']:<6.2f} "
              f"${r['max_dd']:>8,.0f} "
              f"{r['sharpe']:<8.3f} "
              f"${r['best']:>7,.0f} "
              f"${r['worst']:>7,.0f}")

    print("=" * 95)


# ============================================================================
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module optimizer.

    Execute 3 configs de test pour valider le fonctionnement :
    1. Baseline (config actuelle)
    2. TP a 500
    3. Beta lookback a 1320

    Pour executer :
        python src/optimizer.py
    """
    configs = [
        {
            "label": "baseline",
            "overrides": {}
        },
        {
            "label": "TP500",
            "overrides": {"exit.pnl_take_profit": 500}
        },
        {
            "label": "beta1320",
            "overrides": {"indicators.beta_lookback": 1320}
        },
    ]

    results = run_optimization(configs)
    print(f"\n[OK] Optimisation terminee : {len(results)} configs testees")
