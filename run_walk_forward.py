"""
Walk-Forward Test sur 8 mois de donnees GC/SI.

Principe :
  - Decoupe les donnees en fenetres glissantes (train + test)
  - Pour chaque fenetre : teste N configs sur TRAIN, selectionne la meilleure,
    puis valide sur TEST (hors echantillon)
  - Agregation des resultats hors echantillon pour detecter l'overfitting

Fenetres : 6 periodes de ~30j train + ~15j test (glissement ~25j)
Warm-up  : beta_lookback barres incluses avant chaque fenetre d'entrainement
Configs  : top 12 du grid search (6 par PnL + 6 par Sharpe, dedupliques)
"""
import sys
import time
import copy
import numpy as np
import pandas as pd
sys.path.insert(0, "src")

from itertools import product
from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides, build_label, compute_metrics


# ============================================================================
# CONFIGS A TESTER (top du grid search sur 8 mois)
# ============================================================================
# Top 6 par PnL + Top 6 par Sharpe (dedupliques)

CONFIGS_TO_TEST = [
    # --- Top PnL ---
    {"label": "PnL1_b1320_zp20_cp30_co40_TP400_SL600",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -600}},
    {"label": "PnL2_b1980_zp20_cp30_co40_TP400_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -600}},
    {"label": "PnL3_b1320_zp20_cp30_co40_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "PnL4_b1980_zp20_cp30_co40_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "PnL5_b1320_zp20_cp30_co40_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
    {"label": "PnL6_b1980_zp20_cp30_co40_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 40,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
    # --- Top Sharpe / risk-adjusted ---
    {"label": "Sh1_b2640_zp20_cp30_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh2_b2640_zp20_cp60_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 60, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh3_b3960_zp20_cp30_co60_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 3960, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 60,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh4_b1980_zp20_cp60_co50_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 60, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
    {"label": "Sh5_b2640_zp20_cp30_co50_zE3_TP200_SL400",
     "overrides": {"indicators.beta_lookback": 2640, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -400}},
    {"label": "Sh6_b1980_zp20_cp30_co50_TP300_SL600",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "entry.cointegration_score_min": 50,
                   "entry.zscore_long": -2.5, "entry.zscore_short": 2.5,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -600}},
]


# ============================================================================
# CHARGEMENT DES DONNEES (1 seule fois)
# ============================================================================

print("=" * 70)
print("WALK-FORWARD TEST")
print("=" * 70)

print("\n[1/4] Chargement des donnees...")
t_start = time.time()

df_1min_raw, base_config, stats = load_and_prepare_data(verbose=False)
print(f"   Donnees 1-min : {len(df_1min_raw):,} barres")

df_5s = load_5s_data(base_config, verbose=False)
print(f"   Donnees 5s    : {len(df_5s):,} barres")

# Plage de dates
dt_min = df_1min_raw['DateTime'].min()
dt_max = df_1min_raw['DateTime'].max()
print(f"   Periode : {dt_min} -> {dt_max}")

t_load = time.time() - t_start
print(f"   Charge en {t_load:.1f}s")


# ============================================================================
# CONSTRUCTION DES FENETRES WALK-FORWARD
# ============================================================================

print("\n[2/4] Construction des fenetres...")

# Parametres des fenetres
TRAIN_DAYS = 30    # jours de trading pour entrainement
TEST_DAYS = 15     # jours de trading pour test
STEP_DAYS = 25     # decalage entre fenetres (chevauchement train possible)

# Identifier les jours de trading uniques
trading_dates = pd.Series(df_1min_raw['DateTime'].dt.date.unique())
trading_dates = trading_dates.sort_values().reset_index(drop=True)
n_days = len(trading_dates)
print(f"   Jours de trading disponibles : {n_days}")

# Warm-up : on a besoin de max(beta_lookback) barres avant le debut du train
# Le plus grand beta teste est 3960 (dans nos configs)
MAX_WARMUP_BARS = 4000  # un peu plus que 3960 pour securite

# Trouver le premier jour ou on a assez de warmup
# On cherche le jour ou on a >= MAX_WARMUP_BARS barres avant lui
warmup_day_idx = 0
for idx in range(n_days):
    day = trading_dates[idx]
    n_bars_before = len(df_1min_raw[df_1min_raw['DateTime'].dt.date < day])
    if n_bars_before >= MAX_WARMUP_BARS:
        warmup_day_idx = idx
        break

print(f"   Premier jour avec warmup suffisant : {trading_dates[warmup_day_idx]} (idx={warmup_day_idx})")

# Construire les fenetres
windows = []
current_idx = warmup_day_idx

while current_idx + TRAIN_DAYS + TEST_DAYS <= n_days:
    train_start_day = trading_dates[current_idx]
    train_end_day = trading_dates[current_idx + TRAIN_DAYS - 1]
    test_start_day = trading_dates[current_idx + TRAIN_DAYS]
    test_end_idx = min(current_idx + TRAIN_DAYS + TEST_DAYS - 1, n_days - 1)
    test_end_day = trading_dates[test_end_idx]

    windows.append({
        "train_start": train_start_day,
        "train_end": train_end_day,
        "test_start": test_start_day,
        "test_end": test_end_day,
        "train_start_idx": current_idx,
    })

    current_idx += STEP_DAYS

print(f"   Fenetres construites : {len(windows)}")
for i, w in enumerate(windows):
    print(f"   [{i+1}] TRAIN: {w['train_start']} -> {w['train_end']}  |  "
          f"TEST: {w['test_start']} -> {w['test_end']}")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def slice_data(df, date_start, date_end, include_warmup=False, warmup_bars=0):
    """
    Decoupe le DataFrame entre deux dates (incluses).
    Si include_warmup=True, ajoute warmup_bars barres AVANT date_start.
    """
    import datetime as dt_module
    # Convertir les dates en datetime pour la comparaison
    start_dt = pd.Timestamp(date_start)
    end_dt = pd.Timestamp(date_end) + pd.Timedelta(days=1)  # fin de journee incluse

    if include_warmup:
        # Trouver l'index de la premiere barre du jour start
        mask_start = df['DateTime'] >= start_dt
        first_idx = mask_start.idxmax() if mask_start.any() else 0
        warmup_start_idx = max(0, first_idx - warmup_bars)
        mask_end = df['DateTime'] < end_dt
        return df.iloc[warmup_start_idx:][mask_end.iloc[warmup_start_idx:]].copy().reset_index(drop=True)
    else:
        mask = (df['DateTime'] >= start_dt) & (df['DateTime'] < end_dt)
        return df[mask].copy().reset_index(drop=True)


def slice_5s(df_5s, date_start, date_end):
    """Decoupe les donnees 5s entre deux dates."""
    start_dt = pd.Timestamp(date_start)
    end_dt = pd.Timestamp(date_end) + pd.Timedelta(days=1)
    mask = (df_5s['DateTime'] >= start_dt) & (df_5s['DateTime'] < end_dt)
    return df_5s[mask].copy().reset_index(drop=True)


def run_backtest_on_window(df_1min_slice, df_5s_slice, config, warmup_bars=0):
    """
    Calcule les indicateurs et lance le backtest sur une fenetre.
    Les indicateurs sont calcules sur la totalite du slice (warmup inclus).
    Le backtest s'execute sur la totalite aussi (les premieres barres avec
    NaN ne genereront pas de trades).
    """
    df_ind = calculate_all_indicators(df_1min_slice, config)
    trades_df = run_hybrid_backtest(df_ind, df_5s_slice, config)
    return trades_df


# ============================================================================
# BOUCLE WALK-FORWARD
# ============================================================================

print(f"\n[3/4] Execution walk-forward ({len(windows)} fenetres x {len(CONFIGS_TO_TEST)} configs)...")
t_wf_start = time.time()

wf_results = []  # Resultats par fenetre

for w_idx, window in enumerate(windows):
    print(f"\n{'='*70}")
    print(f"FENETRE {w_idx+1}/{len(windows)} : "
          f"TRAIN {window['train_start']} -> {window['train_end']}  |  "
          f"TEST {window['test_start']} -> {window['test_end']}")
    print(f"{'='*70}")

    # --- Decouper les donnees pour cette fenetre ---
    # TRAIN : avec warmup avant pour le calcul des indicateurs
    df_train = slice_data(df_1min_raw, window['train_start'], window['train_end'],
                          include_warmup=True, warmup_bars=MAX_WARMUP_BARS)
    df_5s_train = slice_5s(df_5s, window['train_start'], window['train_end'])

    # TEST : avec warmup aussi (les indicateurs doivent etre calcules)
    df_test = slice_data(df_1min_raw, window['test_start'], window['test_end'],
                         include_warmup=True, warmup_bars=MAX_WARMUP_BARS)
    df_5s_test = slice_5s(df_5s, window['test_start'], window['test_end'])

    print(f"   TRAIN: {len(df_train):,} barres 1-min (warmup inclus), {len(df_5s_train):,} barres 5s")
    print(f"   TEST:  {len(df_test):,} barres 1-min (warmup inclus), {len(df_5s_test):,} barres 5s")

    # --- Phase TRAIN : tester toutes les configs ---
    print(f"\n   --- Phase TRAIN : {len(CONFIGS_TO_TEST)} configs ---")
    train_metrics = []

    # Grouper par indicateurs pour optimiser (meme logique que grid search)
    indicator_groups = {}
    for cfg in CONFIGS_TO_TEST:
        ov = cfg['overrides']
        key = (ov.get('indicators.beta_lookback', 1980),
               ov.get('indicators.zscore_period', 20),
               ov.get('indicators.correlation_period', 30))
        if key not in indicator_groups:
            indicator_groups[key] = []
        indicator_groups[key].append(cfg)

    for (beta, zp, cp), group_configs in indicator_groups.items():
        # Calculer les indicateurs UNE fois pour ce groupe
        ind_overrides = {
            "indicators.beta_lookback": beta,
            "indicators.zscore_period": zp,
            "indicators.correlation_period": cp,
        }
        config_ind = apply_overrides(base_config, ind_overrides)
        df_train_ind = calculate_all_indicators(df_train, config_ind)

        for cfg in group_configs:
            config_full = apply_overrides(base_config, cfg['overrides'])
            trades_df = run_hybrid_backtest(df_train_ind, df_5s_train, config_full)
            metrics = compute_metrics(trades_df)
            metrics['label'] = cfg['label']
            train_metrics.append(metrics)

            print(f"      {cfg['label'][:40]:<42} | "
                  f"Trades: {metrics['trades']:<4} | "
                  f"PnL: ${metrics['pnl_net']:>8,.0f} | "
                  f"PF: {metrics['profit_factor']:.2f}")

    # --- Selectionner la meilleure config sur TRAIN ---
    # Critere : PnL net (on prend la config la plus rentable)
    best_train = max(train_metrics, key=lambda x: x['pnl_net'])
    best_label = best_train['label']
    print(f"\n   >>> Meilleure config TRAIN: {best_label}")
    print(f"       PnL: ${best_train['pnl_net']:,.0f} | "
          f"WR: {best_train['win_rate']}% | "
          f"PF: {best_train['profit_factor']:.2f} | "
          f"Trades: {best_train['trades']}")

    # --- Phase TEST : valider la config selectionnee ---
    print(f"\n   --- Phase TEST : validation hors echantillon ---")

    # Retrouver les overrides de la meilleure config
    best_cfg = [c for c in CONFIGS_TO_TEST if c['label'] == best_label][0]
    config_test = apply_overrides(base_config, best_cfg['overrides'])

    # Calculer indicateurs et backtest sur TEST
    df_test_ind = calculate_all_indicators(df_test, config_test)
    trades_test = run_hybrid_backtest(df_test_ind, df_5s_test, config_test)
    test_metrics = compute_metrics(trades_test)
    test_metrics['label'] = best_label

    print(f"   TEST: Trades: {test_metrics['trades']} | "
          f"PnL: ${test_metrics['pnl_net']:,.0f} | "
          f"WR: {test_metrics['win_rate']}% | "
          f"PF: {test_metrics['profit_factor']:.2f} | "
          f"MaxDD: ${test_metrics['max_dd']:,.0f}")

    # --- Comparer TRAIN vs TEST ---
    if best_train['pnl_net'] != 0:
        degradation = (test_metrics['pnl_net'] / best_train['pnl_net'] - 1) * 100
    else:
        degradation = 0.0

    # Normaliser par nombre de jours
    train_pnl_per_day = best_train['pnl_net'] / TRAIN_DAYS if TRAIN_DAYS > 0 else 0
    test_pnl_per_day = test_metrics['pnl_net'] / TEST_DAYS if TEST_DAYS > 0 else 0

    print(f"\n   COMPARAISON TRAIN vs TEST:")
    print(f"   {'Metrique':<20} {'TRAIN':>12} {'TEST':>12}")
    print(f"   {'-'*46}")
    deg_str = f"{degradation:+.0f}%" if best_train['pnl_net'] != 0 else "N/A"
    print(f"   {'PnL Net':<20} ${best_train['pnl_net']:>10,.0f} ${test_metrics['pnl_net']:>10,.0f}  ({deg_str})")
    print(f"   {'PnL/jour':<20} ${train_pnl_per_day:>10,.0f} ${test_pnl_per_day:>10,.0f}")
    print(f"   {'Win Rate':<20} {best_train['win_rate']:>11.1f}% {test_metrics['win_rate']:>11.1f}%")
    print(f"   {'Profit Factor':<20} {best_train['profit_factor']:>12.2f} {test_metrics['profit_factor']:>12.2f}")
    print(f"   {'Trades':<20} {best_train['trades']:>12} {test_metrics['trades']:>12}")

    # Stocker les resultats de cette fenetre
    wf_results.append({
        "window": w_idx + 1,
        "train_start": str(window['train_start']),
        "train_end": str(window['train_end']),
        "test_start": str(window['test_start']),
        "test_end": str(window['test_end']),
        "best_config": best_label,
        "train_trades": best_train['trades'],
        "train_pnl": best_train['pnl_net'],
        "train_wr": best_train['win_rate'],
        "train_pf": best_train['profit_factor'],
        "train_sharpe": best_train['sharpe'],
        "train_maxdd": best_train['max_dd'],
        "test_trades": test_metrics['trades'],
        "test_pnl": test_metrics['pnl_net'],
        "test_wr": test_metrics['win_rate'],
        "test_pf": test_metrics['profit_factor'],
        "test_sharpe": test_metrics['sharpe'],
        "test_maxdd": test_metrics['max_dd'],
        "all_train_metrics": train_metrics,
    })


# ============================================================================
# RESULTATS AGREGES
# ============================================================================

t_total = time.time() - t_start
print(f"\n\n{'='*70}")
print(f"[4/4] RESULTATS WALK-FORWARD ({t_total/60:.1f} min)")
print(f"{'='*70}")

# Tableau recapitulatif
print(f"\n{'#':<3} {'Periode TEST':<25} {'Config choisie':<35} "
      f"{'Trades':>7} {'PnL TEST':>10} {'WR%':>6} {'PF':>6} {'MaxDD':>9}")
print("-" * 105)

total_test_pnl = 0
total_test_trades = 0
all_test_pf = []

for r in wf_results:
    print(f"{r['window']:<3} {r['test_start']} -> {r['test_end']:<10} "
          f"{r['best_config'][:34]:<35} "
          f"{r['test_trades']:>7} "
          f"${r['test_pnl']:>8,.0f} "
          f"{r['test_wr']:>5.1f}% "
          f"{r['test_pf']:>5.2f} "
          f"${r['test_maxdd']:>7,.0f}")
    total_test_pnl += r['test_pnl']
    total_test_trades += r['test_trades']
    if r['test_pf'] > 0:
        all_test_pf.append(r['test_pf'])

print("-" * 105)
avg_pf = np.mean(all_test_pf) if all_test_pf else 0
print(f"{'TOTAL':<3} {'':<25} {'':<35} "
      f"{total_test_trades:>7} "
      f"${total_test_pnl:>8,.0f} "
      f"{'':>6} "
      f"{avg_pf:>5.2f} ")

# Comparaison TRAIN vs TEST agregee
print(f"\n\nCOMPARAISON TRAIN vs TEST (agregee)")
print("=" * 60)

total_train_pnl = sum(r['train_pnl'] for r in wf_results)
total_train_trades = sum(r['train_trades'] for r in wf_results)
avg_train_pf = np.mean([r['train_pf'] for r in wf_results])
avg_test_pf_all = np.mean([r['test_pf'] for r in wf_results])
avg_train_wr = np.mean([r['train_wr'] for r in wf_results])
avg_test_wr = np.mean([r['test_wr'] for r in wf_results])

print(f"{'Metrique':<25} {'TRAIN':>12} {'TEST':>12} {'Ratio':>10}")
print(f"{'-'*60}")
print(f"{'PnL total':<25} ${total_train_pnl:>10,.0f} ${total_test_pnl:>10,.0f}")
print(f"{'Trades total':<25} {total_train_trades:>12} {total_test_trades:>12}")
print(f"{'Win Rate moyen':<25} {avg_train_wr:>11.1f}% {avg_test_wr:>11.1f}%")
print(f"{'Profit Factor moyen':<25} {avg_train_pf:>12.2f} {avg_test_pf_all:>12.2f}")

# Calcul du ratio de degradation
if total_train_pnl > 0 and total_test_pnl > 0:
    # Normaliser par nombre de jours
    train_total_days = len(windows) * TRAIN_DAYS
    test_total_days = len(windows) * TEST_DAYS
    train_daily = total_train_pnl / train_total_days
    test_daily = total_test_pnl / test_total_days
    retention = test_daily / train_daily * 100
    print(f"\n{'PnL/jour TRAIN':<25} ${train_daily:>10,.0f}")
    print(f"{'PnL/jour TEST':<25} ${test_daily:>10,.0f}")
    print(f"{'Retention hors echantillon':<25} {retention:>11.1f}%")

# Compteur de fenetres positives/negatives
n_positive = sum(1 for r in wf_results if r['test_pnl'] > 0)
n_negative = sum(1 for r in wf_results if r['test_pnl'] <= 0)
print(f"\nFenetres TEST positives : {n_positive}/{len(wf_results)}")
print(f"Fenetres TEST negatives : {n_negative}/{len(wf_results)}")

# Verdict
print(f"\n{'='*60}")
if n_positive >= len(wf_results) * 0.6 and total_test_pnl > 0:
    if total_test_pnl > 0 and total_train_pnl > 0:
        retention_val = (total_test_pnl / test_total_days) / (total_train_pnl / train_total_days) * 100
        if retention_val >= 50:
            print("VERDICT : Strategie ROBUSTE hors echantillon")
            print(f"   Retention {retention_val:.0f}% du PnL/jour, "
                  f"{n_positive}/{len(wf_results)} fenetres positives")
        else:
            print("VERDICT : Strategie PARTIELLEMENT robuste")
            print(f"   Retention faible ({retention_val:.0f}%), signaux d'overfitting potentiel")
    else:
        print("VERDICT : Strategie PROFITABLE hors echantillon")
else:
    print("VERDICT : OVERFITTING DETECTE")
    print(f"   {n_negative}/{len(wf_results)} fenetres negatives hors echantillon")
    print("   Les parametres optimises ne generalisent pas")
print(f"{'='*60}")

# Stabilite des configs selectionnees
print(f"\nSTABILITE DES CONFIGS SELECTIONNEES:")
selected_configs = [r['best_config'] for r in wf_results]
from collections import Counter
config_counts = Counter(selected_configs)
for cfg, count in config_counts.most_common():
    print(f"   {cfg} : {count}/{len(windows)} fenetres")

if len(config_counts) <= 2:
    print("   -> Bonne stabilite : 1-2 configs dominent")
elif len(config_counts) <= 4:
    print("   -> Stabilite moyenne : 3-4 configs differentes")
else:
    print("   -> Faible stabilite : configs differentes a chaque fenetre")

# Sauvegarder les resultats
df_wf = pd.DataFrame([{k: v for k, v in r.items() if k != 'all_train_metrics'} for r in wf_results])
output_path = "output/walk_forward_results.csv"
df_wf.to_csv(output_path, sep=';', index=False)
print(f"\nResultats sauvegardes dans {output_path}")

print(f"\n[OK] Walk-forward termine en {t_total/60:.1f} min")
