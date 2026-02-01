"""
Grid search 864 configs sur 8 mois de donnees.
Optimise : indicateurs calcules 1 fois par combinaison unique (16 groupes),
puis boucle sur les 54 variantes d'entree/sortie sans recalcul.

Parametres testes :
- beta_lookback: 1320, 1980, 2640, 3960
- zscore_period: 20, 30
- correlation_period: 30, 60
- cointegration_score_min: 40, 50, 60
- zscore_entry (long/short): -2.5/+2.5, -3.0/+3.0
- TP: 200, 300, 400
- SL: -400, -600, -800
"""
import sys
import copy
import time
sys.path.insert(0, "src")

from itertools import product
from collections import defaultdict

from data_loader import load_and_prepare_data
from data_loader_5s import load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest, export_backtest
from optimizer import (
    apply_overrides, build_label, compute_metrics,
    print_comparison_table, save_results_to_log,
    build_config_fingerprint
)


# ============================================================================
# GRILLE DE PARAMETRES
# ============================================================================

# Parametres qui impactent les INDICATEURS (necessitent un recalcul)
beta_values = [1320, 1980, 2640, 3960]
zp_values = [20, 30]
cp_values = [30, 60]
# adf_hurst_period fixe a 128

# Parametres qui impactent uniquement ENTREE/SORTIE (pas de recalcul)
coint_values = [40, 50, 60]
zentry_values = [(-2.5, 2.5), (-3.0, 3.0)]
tp_values = [200, 300, 400]
sl_values = [-400, -600, -800]

# Compter
n_indicator_combos = len(beta_values) * len(zp_values) * len(cp_values)
n_entry_exit_combos = len(coint_values) * len(zentry_values) * len(tp_values) * len(sl_values)
n_total = n_indicator_combos * n_entry_exit_combos

print(f"Combinaisons d'indicateurs : {n_indicator_combos}")
print(f"Variantes entree/sortie par groupe : {n_entry_exit_combos}")
print(f"Total configs : {n_total}")
print()

# ============================================================================
# CHARGEMENT DES DONNEES (1 seule fois)
# ============================================================================

print("=" * 60)
print("GRID SEARCH OPTIMISE")
print("=" * 60)

print("\n[1/3] Chargement des donnees...")
t_start = time.time()

df_1min_raw, base_config, stats = load_and_prepare_data(verbose=False)
print(f"   [OK] Donnees 1-min : {len(df_1min_raw):,} barres")

df_5s = load_5s_data(base_config, verbose=False)
print(f"   [OK] Donnees 5s : {len(df_5s):,} barres")

t_load = time.time() - t_start
print(f"   Chargement en {t_load:.1f}s")

# ============================================================================
# BOUCLE PRINCIPALE : GROUPER PAR INDICATEURS
# ============================================================================

print(f"\n[2/3] Execution des backtests ({n_total} configs)...")

all_results = []
overrides_map = {}
config_count = 0
t_backtest_start = time.time()

for beta, zp, cp in product(beta_values, zp_values, cp_values):
    # Preparer la config pour ce groupe d'indicateurs
    indicator_overrides = {
        "indicators.beta_lookback": beta,
        "indicators.zscore_period": zp,
        "indicators.correlation_period": cp,
    }
    config_ind = apply_overrides(base_config, indicator_overrides)

    # Calculer les indicateurs UNE SEULE FOIS pour ce groupe
    group_label = f"beta{beta}_zp{zp}_cp{cp}"
    print(f"\n   === Groupe {group_label} : calcul des indicateurs... ===")
    t_group = time.time()

    df_with_indicators = calculate_all_indicators(df_1min_raw, config_ind)

    t_ind = time.time() - t_group
    print(f"   Indicateurs calcules en {t_ind:.1f}s")

    # Boucle sur les variantes d'entree/sortie (pas de recalcul d'indicateurs)
    for coint, (ze_l, ze_s), tp, sl in product(coint_values, zentry_values, tp_values, sl_values):
        config_count += 1

        # Appliquer les overrides d'entree/sortie
        full_overrides = {
            **indicator_overrides,
            "entry.cointegration_score_min": coint,
            "entry.zscore_long": ze_l,
            "entry.zscore_short": ze_s,
            "exit.pnl_take_profit": tp,
            "exit.pnl_stop_loss": sl,
        }
        config_full = apply_overrides(base_config, full_overrides)
        label = build_label(full_overrides)

        # Lancer le backtest hybride (reutilise df_with_indicators)
        trades_df = run_hybrid_backtest(df_with_indicators, df_5s, config_full)

        # Calculer les metriques
        metrics = compute_metrics(trades_df)
        metrics["label"] = label
        metrics["fingerprint"] = build_config_fingerprint(config_full)
        all_results.append(metrics)
        overrides_map[label] = full_overrides

        # Progression
        elapsed = time.time() - t_backtest_start
        avg_per_config = elapsed / config_count
        remaining = avg_per_config * (n_total - config_count)

        print(f"   [{config_count}/{n_total}] {label} | "
              f"Trades: {metrics['trades']} | WR: {metrics['win_rate']}% | "
              f"PnL: ${metrics['pnl_net']:,.0f} | PF: {metrics['profit_factor']:.2f} | "
              f"ETA: {remaining/60:.0f}min")

# ============================================================================
# RESULTATS
# ============================================================================

t_total = time.time() - t_start
print(f"\n[3/3] Resultats (temps total: {t_total/60:.1f} min)")

# Top 20 par PnL
print("\n\n")
print_comparison_table(all_results, sort_by="pnl_net")

# Top 20 par Sharpe
print("\n\n")
print_comparison_table(all_results, sort_by="sharpe")

# Top 20 par Profit Factor
print("\n\n")
print_comparison_table(all_results, sort_by="profit_factor")

# Sauvegarder dans le log
save_results_to_log(all_results, overrides_map, batch_id="grid_8mois")

print(f"\n[OK] Grid search termine : {len(all_results)} configs testees en {t_total/60:.1f} min")
