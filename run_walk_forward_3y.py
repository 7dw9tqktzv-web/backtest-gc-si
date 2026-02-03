"""
Walk-Forward 3 ans - Top configs du grid search etendu (1 tick slippage)

Principe :
  - 3 ans de donnees (Jan 2023 - Jan 2026)
  - Fenetres roulantes : 3 mois train + 1 mois test
  - Pour chaque fenetre : teste les configs sur TRAIN, selectionne la meilleure,
    puis valide sur TEST (hors echantillon)
  - Slippage : 1 tick

Configs testees : top 10 du grid search etendu (5 par PnL + 5 par Sharpe, Sharpe >= 1)
"""
import sys
import time
import copy
import numpy as np
import pandas as pd
sys.path.insert(0, "src")

from data_loader import load_and_prepare_data, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics

# ============================================================================
# CONFIGS A TESTER (issues du grid search etendu 1 tick)
# ============================================================================

# Fixes pour toutes les configs
FIXED = {
    "costs.slippage_gc_ticks": 1,
    "costs.slippage_si_ticks": 1,
    "exit.zscore_tp_enabled": False,  # tpzOFF domine le top PnL
}

CONFIGS_TO_TEST = [
    # --- Top 5 par PnL (Sharpe >= 1.0) ---
    {"label": "PnL1_b1320_zp20_cp30_zE3.5_co50_TP500_SL1200",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -1200}},
    {"label": "PnL2_b1320_zp20_cp30_zE3.5_co50_TP1000_SL1200",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 1000, "exit.pnl_stop_loss": -1200}},
    {"label": "PnL3_b1320_zp20_cp30_zE3.5_co50_TP500_SL1400",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -1400}},
    {"label": "PnL4_b1320_zp20_cp30_zE3.5_co50_TP500_SL800",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -800}},
    {"label": "PnL5_b1320_zp20_cp30_zE3.5_co50_TP500_SL1000",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -1000}},
    # --- Top 5 par Sharpe (min 15 trades, Sharpe >= 1.0, configs differentes) ---
    {"label": "Sh1_b660_zp15_cp20_zE3.0_co60_TP300_SL800",
     "overrides": {"indicators.beta_lookback": 660, "indicators.zscore_period": 15,
                   "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "entry.cointegration_score_min": 60,
                   "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -800,
                   "exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 0}},
    {"label": "Sh2_b660_zp15_cp60_zE3.0_co60_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 660, "indicators.zscore_period": 15,
                   "indicators.correlation_period": 60, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "entry.cointegration_score_min": 60,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800,
                   "exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 0}},
    {"label": "Sh3_b660_zp15_cp20_zE3.0_co50_TP200_SL800_F200",
     "overrides": {"indicators.beta_lookback": 660, "indicators.zscore_period": 15,
                   "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.0, "entry.zscore_short": 3.0,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 200, "exit.pnl_stop_loss": -800,
                   "exit.zscore_tp_enabled": True, "exit.zscore_tp_min_pnl": 200}},
    {"label": "Sh4_b1320_zp20_cp20_zE3.5_co50_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1320, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 50,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
    {"label": "Sh5_b1980_zp20_cp20_zE3.5_co60_TP400_SL800",
     "overrides": {"indicators.beta_lookback": 1980, "indicators.zscore_period": 20,
                   "indicators.correlation_period": 20, "indicators.adf_hurst_period": 128,
                   "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
                   "entry.cointegration_score_min": 60,
                   "exit.pnl_take_profit": 400, "exit.pnl_stop_loss": -800}},
]

# Appliquer les fixes a chaque config
for cfg in CONFIGS_TO_TEST:
    for k, v in FIXED.items():
        if k not in cfg["overrides"]:
            cfg["overrides"][k] = v


# ============================================================================
# PARAMETRES WALK-FORWARD
# ============================================================================

TRAIN_DAYS = 63    # ~3 mois de trading (21 jours/mois x 3)
TEST_DAYS = 21     # ~1 mois de trading
STEP_DAYS = 21     # pas de 1 mois (fenetres non-chevauchantes sur test)
MAX_WARMUP_BARS = 4000  # securite pour beta_lookback max


# ============================================================================
# CHARGEMENT DES DONNEES
# ============================================================================

print("=" * 100)
print("WALK-FORWARD 3 ANS - TOP CONFIGS (1 TICK SLIPPAGE)")
print("=" * 100)

print(f"\nParametres : TRAIN={TRAIN_DAYS}j, TEST={TEST_DAYS}j, STEP={STEP_DAYS}j")
print(f"Configs a tester : {len(CONFIGS_TO_TEST)}")
print(f"Slippage : 1 tick GC + 1 tick SI\n")

print("[1/4] Chargement des donnees...")
t_start = time.time()

df_1min_raw, base_config, stats = load_and_prepare_data(verbose=False)
print(f"   Donnees 1-min : {len(df_1min_raw):,} barres")

df_5s = load_5s_data(base_config, verbose=False)
print(f"   Donnees 5s    : {len(df_5s):,} barres")

dt_min = df_1min_raw['DateTime'].min()
dt_max = df_1min_raw['DateTime'].max()
print(f"   Periode : {dt_min} -> {dt_max}")
print(f"   Charge en {time.time() - t_start:.1f}s")


# ============================================================================
# CONSTRUCTION DES FENETRES
# ============================================================================

print("\n[2/4] Construction des fenetres...")

trading_dates = pd.Series(df_1min_raw['DateTime'].dt.date.unique())
trading_dates = trading_dates.sort_values().reset_index(drop=True)
n_days = len(trading_dates)
print(f"   Jours de trading disponibles : {n_days}")

# Trouver le premier jour avec assez de warmup
warmup_day_idx = 0
for idx in range(n_days):
    day = trading_dates[idx]
    n_bars_before = len(df_1min_raw[df_1min_raw['DateTime'].dt.date < day])
    if n_bars_before >= MAX_WARMUP_BARS:
        warmup_day_idx = idx
        break

print(f"   Premier jour avec warmup : {trading_dates[warmup_day_idx]} (idx={warmup_day_idx})")

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
    })

    current_idx += STEP_DAYS

print(f"   Fenetres construites : {len(windows)}")
for i, w in enumerate(windows):
    print(f"   [{i+1:>2}] TRAIN: {w['train_start']} -> {w['train_end']}  |  "
          f"TEST: {w['test_start']} -> {w['test_end']}")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def slice_data(df, date_start, date_end, include_warmup=False, warmup_bars=0):
    """Decoupe le DataFrame entre deux dates (incluses)."""
    start_dt = pd.Timestamp(date_start)
    end_dt = pd.Timestamp(date_end) + pd.Timedelta(days=1)

    if include_warmup:
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


# ============================================================================
# BOUCLE WALK-FORWARD
# ============================================================================

print(f"\n[3/4] Execution walk-forward ({len(windows)} fenetres x {len(CONFIGS_TO_TEST)} configs)...")
t_wf_start = time.time()

wf_results = []

for w_idx, window in enumerate(windows):
    t_w = time.time()
    print(f"\n{'='*100}")
    print(f"FENETRE {w_idx+1}/{len(windows)} : "
          f"TRAIN {window['train_start']} -> {window['train_end']}  |  "
          f"TEST {window['test_start']} -> {window['test_end']}")
    print(f"{'='*100}")

    # Decouper les donnees
    df_train = slice_data(df_1min_raw, window['train_start'], window['train_end'],
                          include_warmup=True, warmup_bars=MAX_WARMUP_BARS)
    df_5s_train = slice_5s(df_5s, window['train_start'], window['train_end'])

    df_test = slice_data(df_1min_raw, window['test_start'], window['test_end'],
                         include_warmup=True, warmup_bars=MAX_WARMUP_BARS)
    df_5s_test = slice_5s(df_5s, window['test_start'], window['test_end'])

    print(f"   TRAIN: {len(df_train):,} barres 1-min, {len(df_5s_train):,} barres 5s")
    print(f"   TEST:  {len(df_test):,} barres 1-min, {len(df_5s_test):,} barres 5s")

    # --- Phase TRAIN ---
    print(f"\n   --- Phase TRAIN ---")
    train_metrics = []

    # Grouper par indicateurs
    indicator_groups = {}
    for cfg in CONFIGS_TO_TEST:
        ov = cfg['overrides']
        key = (ov.get('indicators.beta_lookback', 1980),
               ov.get('indicators.zscore_period', 20),
               ov.get('indicators.correlation_period', 30),
               ov.get('indicators.adf_hurst_period', 128))
        if key not in indicator_groups:
            indicator_groups[key] = []
        indicator_groups[key].append(cfg)

    for ind_key, group_configs in indicator_groups.items():
        ind_overrides = {
            "indicators.beta_lookback": ind_key[0],
            "indicators.zscore_period": ind_key[1],
            "indicators.correlation_period": ind_key[2],
            "indicators.adf_hurst_period": ind_key[3],
        }
        config_ind = apply_overrides(base_config, ind_overrides)
        df_train_ind = calculate_all_indicators(df_train, config_ind, verbose=False)

        for cfg in group_configs:
            config_full = apply_overrides(base_config, cfg['overrides'])
            trades_df = run_hybrid_backtest(df_train_ind, df_5s_train, config_full, verbose=False)
            metrics = compute_metrics(trades_df)
            metrics['label'] = cfg['label']
            train_metrics.append(metrics)

            print(f"      {cfg['label'][:45]:<47} | "
                  f"Tr: {metrics['trades']:<4} | "
                  f"PnL: ${metrics['pnl_net']:>8,.0f} | "
                  f"WR: {metrics['win_rate']:>5.1f}% | "
                  f"Sh: {metrics['sharpe']:>5.2f}")

    # Selectionner la meilleure config sur TRAIN (par PnL)
    best_train = max(train_metrics, key=lambda x: x['pnl_net'])
    best_label = best_train['label']
    print(f"\n   >>> Meilleure TRAIN: {best_label} "
          f"PnL=${best_train['pnl_net']:,.0f} WR={best_train['win_rate']}%")

    # --- Phase TEST ---
    print(f"   --- Phase TEST ---")
    best_cfg = [c for c in CONFIGS_TO_TEST if c['label'] == best_label][0]
    config_test = apply_overrides(base_config, best_cfg['overrides'])

    df_test_ind = calculate_all_indicators(df_test, config_test, verbose=False)
    trades_test = run_hybrid_backtest(df_test_ind, df_5s_test, config_test, verbose=False)
    test_metrics = compute_metrics(trades_test)

    print(f"   TEST: Trades={test_metrics['trades']} | "
          f"PnL=${test_metrics['pnl_net']:,.0f} | "
          f"WR={test_metrics['win_rate']}% | "
          f"PF={test_metrics['profit_factor']:.2f}")

    dt_w = time.time() - t_w
    print(f"   Fenetre terminee en {dt_w:.0f}s")

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
    })


# ============================================================================
# RESULTATS AGREGES
# ============================================================================

t_total = time.time() - t_start
print(f"\n\n{'='*120}")
print(f"[4/4] RESULTATS WALK-FORWARD 3 ANS ({t_total/60:.1f} min)")
print(f"{'='*120}")

print(f"\n{'#':<3} {'Periode TEST':<25} {'Config choisie':<50} "
      f"{'Tr':>4} {'PnL TEST':>10} {'WR%':>6} {'PF':>6} {'MaxDD':>9}")
print("-" * 120)

total_test_pnl = 0
total_test_trades = 0

for r in wf_results:
    print(f"{r['window']:<3} {r['test_start']} -> {r['test_end']:<10} "
          f"{r['best_config'][:49]:<50} "
          f"{r['test_trades']:>4} "
          f"${r['test_pnl']:>8,.0f} "
          f"{r['test_wr']:>5.1f}% "
          f"{r['test_pf']:>5.2f} "
          f"${r['test_maxdd']:>7,.0f}")
    total_test_pnl += r['test_pnl']
    total_test_trades += r['test_trades']

print("-" * 120)
print(f"{'TOT':<3} {'':<25} {'':<50} "
      f"{total_test_trades:>4} "
      f"${total_test_pnl:>8,.0f}")

# Comparaison TRAIN vs TEST
print(f"\n\nCOMPARAISON TRAIN vs TEST (agregee)")
print("=" * 70)

total_train_pnl = sum(r['train_pnl'] for r in wf_results)
total_train_trades = sum(r['train_trades'] for r in wf_results)
avg_train_wr = np.mean([r['train_wr'] for r in wf_results])
avg_test_wr = np.mean([r['test_wr'] for r in wf_results])

print(f"{'Metrique':<25} {'TRAIN':>12} {'TEST':>12}")
print(f"{'-'*50}")
print(f"{'PnL total':<25} ${total_train_pnl:>10,.0f} ${total_test_pnl:>10,.0f}")
print(f"{'Trades total':<25} {total_train_trades:>12} {total_test_trades:>12}")
print(f"{'Win Rate moyen':<25} {avg_train_wr:>11.1f}% {avg_test_wr:>11.1f}%")

# PnL/jour normalise
train_total_days = len(windows) * TRAIN_DAYS
test_total_days = len(windows) * TEST_DAYS
if train_total_days > 0 and test_total_days > 0:
    train_daily = total_train_pnl / train_total_days
    test_daily = total_test_pnl / test_total_days
    retention = test_daily / train_daily * 100 if train_daily != 0 else 0
    print(f"\n{'PnL/jour TRAIN':<25} ${train_daily:>10,.1f}")
    print(f"{'PnL/jour TEST':<25} ${test_daily:>10,.1f}")
    print(f"{'Retention OOS':<25} {retention:>11.1f}%")

n_positive = sum(1 for r in wf_results if r['test_pnl'] > 0)
n_negative = sum(1 for r in wf_results if r['test_pnl'] <= 0)
print(f"\nFenetres TEST positives : {n_positive}/{len(wf_results)}")
print(f"Fenetres TEST negatives : {n_negative}/{len(wf_results)}")

# Verdict
print(f"\n{'='*70}")
if n_positive >= len(wf_results) * 0.6 and total_test_pnl > 0:
    if total_train_pnl > 0:
        ret = (total_test_pnl / test_total_days) / (total_train_pnl / train_total_days) * 100
        if ret >= 50:
            print("VERDICT : Strategie ROBUSTE hors echantillon")
            print(f"   Retention {ret:.0f}%, {n_positive}/{len(wf_results)} fenetres positives")
        else:
            print("VERDICT : Strategie PARTIELLEMENT robuste")
            print(f"   Retention faible ({ret:.0f}%)")
    else:
        print("VERDICT : TRAIN negatif mais TEST positif -- anomalie")
else:
    print("VERDICT : OVERFITTING DETECTE")
    print(f"   {n_negative}/{len(wf_results)} fenetres negatives hors echantillon")
print(f"{'='*70}")

# Stabilite
print(f"\nSTABILITE DES CONFIGS SELECTIONNEES:")
from collections import Counter
config_counts = Counter(r['best_config'] for r in wf_results)
for cfg, count in config_counts.most_common():
    print(f"   {cfg} : {count}/{len(windows)} fenetres")

# Sauvegarder
df_wf = pd.DataFrame(wf_results)
output_path = "output/walk_forward_3y_results.csv"
df_wf.to_csv(output_path, sep=';', index=False)
print(f"\nResultats sauvegardes dans {output_path}")
print(f"[OK] Walk-forward termine en {t_total/60:.1f} min")
