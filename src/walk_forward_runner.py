# ============================================================================
# WALK_FORWARD_RUNNER.PY - Module generique pour les walk-forward tests
# ============================================================================
#
# Ce module factorise le code commun des scripts run_walk_forward_*.py :
# - Construction des fenetres train/test
# - Fonctions slice_data et slice_5s
# - Boucle walk-forward avec selection de la meilleure config
# - Affichage des resultats et statistiques
#
# Utilisation :
#   from walk_forward_runner import WalkForwardRunner
#   runner = WalkForwardRunner(configs_to_test=[...], train_days=63, test_days=21)
#   runner.run()
#
# ============================================================================

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
from collections import Counter

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def slice_data(df: pd.DataFrame, date_start, date_end,
               include_warmup: bool = False, warmup_bars: int = 0) -> pd.DataFrame:
    """
    Decoupe le DataFrame entre deux dates (incluses).

    Args:
        df: DataFrame avec colonne 'DateTime'
        date_start: Date de debut (date ou string)
        date_end: Date de fin (date ou string)
        include_warmup: Si True, ajoute warmup_bars barres AVANT date_start
        warmup_bars: Nombre de barres de warmup

    Returns:
        DataFrame decoupe
    """
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


def slice_5s(df_5s: pd.DataFrame, date_start, date_end) -> pd.DataFrame:
    """
    Decoupe les donnees 5s entre deux dates.

    Args:
        df_5s: DataFrame 5s avec colonne 'DateTime'
        date_start: Date de debut
        date_end: Date de fin

    Returns:
        DataFrame decoupe
    """
    start_dt = pd.Timestamp(date_start)
    end_dt = pd.Timestamp(date_end) + pd.Timedelta(days=1)
    mask = (df_5s['DateTime'] >= start_dt) & (df_5s['DateTime'] < end_dt)
    return df_5s[mask].copy().reset_index(drop=True)


# ============================================================================
# CLASSE PRINCIPALE
# ============================================================================

class WalkForwardRunner:
    """
    Runner generique pour les walk-forward tests.

    Factorise le code commun : construction des fenetres, boucle train/test,
    affichage des resultats et statistiques.

    Exemple:
        runner = WalkForwardRunner(
            configs_to_test=[
                {"label": "config1", "overrides": {...}},
                {"label": "config2", "overrides": {...}},
            ],
            train_days=63,
            test_days=21,
            step_days=21,
        )
        runner.run()
    """

    def __init__(
        self,
        configs_to_test: List[Dict],
        train_days: int = 63,
        test_days: int = 21,
        step_days: int = 21,
        warmup_bars: int = 4500,
        timeframe: str = "5min",
        title: str = "WALK-FORWARD TEST",
        output_path: str = "output/walk_forward_results.csv",
        selection_criterion: str = "pnl_net",
    ):
        """
        Initialise le runner.

        Args:
            configs_to_test: Liste de dicts avec 'label' et 'overrides'
            train_days: Nombre de jours de trading pour l'entrainement
            test_days: Nombre de jours de trading pour le test
            step_days: Decalage entre fenetres (chevauchement possible)
            warmup_bars: Nombre de barres de warmup pour les indicateurs
            timeframe: "1min" ou "5min" pour le resampling
            title: Titre affiche au lancement
            output_path: Chemin du fichier CSV de sortie
            selection_criterion: Critere pour selectionner la meilleure config ("pnl_net" ou "sharpe")
        """
        self.configs_to_test = configs_to_test
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.warmup_bars = warmup_bars
        self.timeframe = timeframe
        self.title = title
        self.output_path = Path(output_path)
        self.selection_criterion = selection_criterion

        # Donnees chargees pendant run()
        self.df_main = None
        self.df_5s = None
        self.base_config = None
        self.windows = []
        self.results = []

    def run(self):
        """Execute le walk-forward test complet."""
        print("=" * 100)
        print(self.title)
        print("=" * 100)

        print(f"\nParametres:")
        print(f"   Configs a tester : {len(self.configs_to_test)}")
        print(f"   Train : {self.train_days} jours")
        print(f"   Test  : {self.test_days} jours")
        print(f"   Step  : {self.step_days} jours")
        print(f"   Warmup: {self.warmup_bars} barres")
        print(f"   Timeframe : {self.timeframe}")
        print(f"   Selection : {self.selection_criterion}")

        # --- Charger les donnees ---
        print("\n[1/4] Chargement des donnees...")
        t_start = time.time()
        self._load_data()

        # --- Construire les fenetres ---
        print("\n[2/4] Construction des fenetres...")
        self._build_windows()

        # --- Boucle walk-forward ---
        print(f"\n[3/4] Execution walk-forward ({len(self.windows)} fenetres x {len(self.configs_to_test)} configs)...")
        self._run_walk_forward()

        # --- Afficher les resultats ---
        t_total = time.time() - t_start
        print(f"\n[4/4] RESULTATS ({t_total/60:.1f} min)")
        self._print_results()

        # --- Sauvegarder ---
        self._save_results()

    def _load_data(self):
        """Charge les donnees 1-min, 5-min et 5s."""
        t0 = time.time()
        df_1min, self.base_config, _ = load_and_prepare_data(verbose=False)

        if self.timeframe == "5min":
            self.df_main = resample_to_5min(df_1min, verbose=False)
            print(f"   Donnees 5-min : {len(self.df_main):,} barres")
        else:
            self.df_main = df_1min
            print(f"   Donnees 1-min : {len(self.df_main):,} barres")

        self.df_5s = load_5s_data(self.base_config, verbose=False)
        print(f"   Donnees 5s    : {len(self.df_5s):,} barres")

        dt_min = self.df_main['DateTime'].min()
        dt_max = self.df_main['DateTime'].max()
        print(f"   Periode : {dt_min} -> {dt_max}")
        print(f"   Charge en {time.time() - t0:.1f}s")

    def _build_windows(self):
        """Construit les fenetres train/test."""
        trading_dates = pd.Series(self.df_main['DateTime'].dt.date.unique())
        trading_dates = trading_dates.sort_values().reset_index(drop=True)
        n_days = len(trading_dates)
        print(f"   Jours de trading disponibles : {n_days}")

        # Trouver le premier jour avec warmup suffisant
        warmup_day_idx = 0
        for idx in range(n_days):
            day = trading_dates[idx]
            n_bars_before = len(self.df_main[self.df_main['DateTime'].dt.date < day])
            if n_bars_before >= self.warmup_bars:
                warmup_day_idx = idx
                break

        print(f"   Premier jour avec warmup suffisant : {trading_dates[warmup_day_idx]} (idx={warmup_day_idx})")

        # Construire les fenetres
        self.windows = []
        current_idx = warmup_day_idx

        while current_idx + self.train_days + self.test_days <= n_days:
            train_start_day = trading_dates[current_idx]
            train_end_day = trading_dates[current_idx + self.train_days - 1]
            test_start_day = trading_dates[current_idx + self.train_days]
            test_end_idx = min(current_idx + self.train_days + self.test_days - 1, n_days - 1)
            test_end_day = trading_dates[test_end_idx]

            self.windows.append({
                "train_start": train_start_day,
                "train_end": train_end_day,
                "test_start": test_start_day,
                "test_end": test_end_day,
            })

            current_idx += self.step_days

        print(f"   Fenetres construites : {len(self.windows)}")

    def _run_walk_forward(self):
        """Execute la boucle walk-forward."""
        self.results = []

        for w_idx, window in enumerate(self.windows):
            print(f"\n[{w_idx+1:>2}/{len(self.windows)}] "
                  f"TRAIN {window['train_start']} -> {window['train_end']} | "
                  f"TEST {window['test_start']} -> {window['test_end']}", end="")

            # Decouper les donnees
            df_train = slice_data(self.df_main, window['train_start'], window['train_end'],
                                  include_warmup=True, warmup_bars=self.warmup_bars)
            df_5s_train = slice_5s(self.df_5s, window['train_start'], window['train_end'])

            df_test = slice_data(self.df_main, window['test_start'], window['test_end'],
                                 include_warmup=True, warmup_bars=self.warmup_bars)
            df_5s_test = slice_5s(self.df_5s, window['test_start'], window['test_end'])

            # Phase TRAIN - tester toutes les configs
            train_metrics = []
            for cfg in self.configs_to_test:
                config_full = apply_overrides(self.base_config, cfg['overrides'])
                df_train_ind = calculate_all_indicators(df_train, config_full, verbose=False)
                trades_df = run_hybrid_backtest(df_train_ind, df_5s_train, config_full, verbose=False)
                metrics = compute_metrics(trades_df)
                metrics['label'] = cfg['label']
                train_metrics.append(metrics)

            # Selectionner la meilleure config sur TRAIN
            best_train = max(train_metrics, key=lambda x: x[self.selection_criterion])
            best_label = best_train['label']

            # Phase TEST
            best_cfg = [c for c in self.configs_to_test if c['label'] == best_label][0]
            config_test = apply_overrides(self.base_config, best_cfg['overrides'])
            df_test_ind = calculate_all_indicators(df_test, config_test, verbose=False)
            trades_test = run_hybrid_backtest(df_test_ind, df_5s_test, config_test, verbose=False)
            test_metrics = compute_metrics(trades_test)

            print(f" -> {best_label[:30]} | TEST: {test_metrics['trades']} trades, ${test_metrics['pnl_net']:>+,.0f}")

            # Stocker les resultats
            self.results.append({
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
                "test_trades": test_metrics['trades'],
                "test_pnl": test_metrics['pnl_net'],
                "test_wr": test_metrics['win_rate'],
                "test_pf": test_metrics['profit_factor'],
                "test_maxdd": test_metrics['max_dd'],
            })

    def _print_results(self):
        """Affiche les resultats agreges."""
        print(f"\n{'='*100}")
        print("RESULTATS WALK-FORWARD")
        print(f"{'='*100}")

        # Tableau recapitulatif
        print(f"\n{'#':<3} {'Periode TEST':<25} {'Config':<35} "
              f"{'Trades':>7} {'PnL TEST':>12} {'WR%':>6} {'PF':>6}")
        print("-" * 105)

        total_test_pnl = 0
        total_test_trades = 0

        for r in self.results:
            cfg_short = r['best_config'][:34]
            print(f"{r['window']:<3} {r['test_start']} -> {r['test_end']:<10} "
                  f"{cfg_short:<35} "
                  f"{r['test_trades']:>7} "
                  f"${r['test_pnl']:>+10,.0f} "
                  f"{r['test_wr']:>5.1f}% "
                  f"{r['test_pf']:>5.2f}")
            total_test_pnl += r['test_pnl']
            total_test_trades += r['test_trades']

        print("-" * 105)
        print(f"{'TOTAL':<3} {'':<25} {'':<35} "
              f"{total_test_trades:>7} "
              f"${total_test_pnl:>+10,.0f}")

        # Comparaison TRAIN vs TEST
        print(f"\n\nCOMPARAISON TRAIN vs TEST")
        print("=" * 60)

        total_train_pnl = sum(r['train_pnl'] for r in self.results)
        total_train_trades = sum(r['train_trades'] for r in self.results)

        train_total_days = len(self.windows) * self.train_days
        test_total_days = len(self.windows) * self.test_days
        train_daily = total_train_pnl / train_total_days if train_total_days > 0 else 0
        test_daily = total_test_pnl / test_total_days if test_total_days > 0 else 0

        print(f"{'Metrique':<25} {'TRAIN':>15} {'TEST':>15}")
        print(f"{'-'*60}")
        print(f"{'PnL total':<25} ${total_train_pnl:>+13,.0f} ${total_test_pnl:>+13,.0f}")
        print(f"{'Trades total':<25} {total_train_trades:>15} {total_test_trades:>15}")
        print(f"{'PnL/jour':<25} ${train_daily:>+13,.0f} ${test_daily:>+13,.0f}")

        if train_daily > 0 and test_daily != 0:
            retention = test_daily / train_daily * 100
            print(f"\n{'Retention hors echantillon':<25} {retention:>14.1f}%")

        # Compteur de fenetres
        n_positive = sum(1 for r in self.results if r['test_pnl'] > 0)
        n_negative = sum(1 for r in self.results if r['test_pnl'] < 0)
        n_zero = sum(1 for r in self.results if r['test_pnl'] == 0)

        print(f"\nFenetres TEST positives : {n_positive}/{len(self.results)} ({n_positive/len(self.results)*100:.0f}%)")
        print(f"Fenetres TEST negatives : {n_negative}/{len(self.results)} ({n_negative/len(self.results)*100:.0f}%)")
        if n_zero > 0:
            print(f"Fenetres TEST nulles    : {n_zero}/{len(self.results)}")

        # Stabilite des configs
        print(f"\nSTABILITE DES CONFIGS:")
        config_counts = Counter(r['best_config'] for r in self.results)
        for cfg, count in config_counts.most_common():
            cfg_short = cfg[:40]
            print(f"   {cfg_short:<40} : {count:>2}/{len(self.windows)} ({count/len(self.windows)*100:.0f}%)")

        # Analyse par annee
        print(f"\nANALYSE PAR ANNEE:")
        for year in ['2023', '2024', '2025', '2026']:
            pnl_year = sum(r['test_pnl'] for r in self.results if r['test_start'].startswith(year))
            if pnl_year != 0:
                print(f"   {year} : ${pnl_year:>+12,.0f}")

        # Verdict
        print(f"\n{'='*60}")
        if n_positive >= len(self.results) * 0.5 and total_test_pnl > 0:
            if train_daily > 0:
                retention_val = test_daily / train_daily * 100
                if retention_val >= 50:
                    print("VERDICT : Strategie ROBUSTE hors echantillon")
                else:
                    print("VERDICT : Strategie PARTIELLEMENT robuste")
            else:
                print("VERDICT : Strategie PROFITABLE hors echantillon")
        else:
            print("VERDICT : OVERFITTING DETECTE")
            print(f"   {n_negative}/{len(self.results)} fenetres negatives")
        print(f"{'='*60}")

    def _save_results(self):
        """Sauvegarde les resultats dans un CSV."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        df_wf = pd.DataFrame(self.results)
        df_wf.to_csv(self.output_path, sep=';', index=False)
        print(f"\nResultats sauvegardes dans {self.output_path}")
