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

from data_loader import load_and_prepare_data
from data_loader_5s import load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import (run_hybrid_backtest, export_backtest,
                                    build_config_fingerprint)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def apply_overrides(config, overrides):
    """
    Applique des overrides sur une copie de la config.

    Les cles utilisent la notation a points pour acceder aux cles imbriquees.
    Ex: "indicators.beta_lookback" -> config['indicators']['beta_lookback']

    Parametres:
    -----------
    config : dict
        Configuration de base chargee depuis le YAML
    overrides : dict
        Dict de parametres a modifier (cle: "section.param", valeur: nouvelle valeur)

    Retourne:
    ---------
    dict : Copie de la config avec les overrides appliques
    """
    cfg = copy.deepcopy(config)
    for dotted_key, value in overrides.items():
        keys = dotted_key.split('.')
        target = cfg
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return cfg


def build_label(overrides):
    """
    Construit un label court a partir des overrides.

    Ex: {"exit.pnl_take_profit": 500, "indicators.beta_lookback": 1320}
        -> "TP500_beta1320"
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
    Calcule les metriques cles a partir d'un DataFrame de trades.

    Retourne:
    ---------
    dict : Metriques cles (trades, long, short, winners, win_rate, pnl_net,
           pnl_avg, best, worst, max_dd, profit_factor, sharpe)
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

    # Sharpe (annualise sur ~252 jours)
    if pnl.std() > 0:
        sharpe = (pnl.mean() / pnl.std()) * np.sqrt(252)
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
# EXECUTION D'UN BACKTEST POUR UNE CONFIG
# ============================================================================

def run_single_config(df_1min, df_5s, config, label="", verbose=True):
    """
    Execute un backtest hybride complet pour une config donnee.

    Parametres:
    -----------
    df_1min : pd.DataFrame
        Donnees synchronisees 1-minute (brutes, sans indicateurs)
    df_5s : pd.DataFrame
        Donnees synchronisees 5-secondes
    config : dict
        Configuration complete avec parametres de la strategie
    label : str
        Label pour identifier cette config dans les resultats
    verbose : bool
        Si True, affiche la progression

    Retourne:
    ---------
    dict : Metriques cles + label + fingerprint
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
    Execute N backtests avec des configs differentes.

    Charge les donnees UNE seule fois, puis boucle sur chaque config.

    Parametres:
    -----------
    configs_list : list of dict
        Liste de dicts avec :
        - "label" (str, optionnel) : nom de la config
        - "overrides" (dict) : parametres a modifier (notation a points)
        Ex: [
            {"label": "baseline", "overrides": {}},
            {"label": "TP500", "overrides": {"exit.pnl_take_profit": 500}},
        ]
    verbose : bool
        Si True, affiche la progression

    Retourne:
    ---------
    list of dict : Metriques de chaque config
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

    return results


# ============================================================================
# AFFICHAGE DU TABLEAU COMPARATIF
# ============================================================================

def print_comparison_table(results, sort_by="pnl_net"):
    """
    Affiche un tableau comparatif des resultats, trie par le critere choisi.

    Parametres:
    -----------
    results : list of dict
        Liste des metriques de chaque config
    sort_by : str
        Critere de tri (pnl_net, profit_factor, win_rate, sharpe, max_dd)
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
