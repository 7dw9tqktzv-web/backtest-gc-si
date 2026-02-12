# ============================================================================
# GRID_SEARCH_RUNNER.PY - Module generique pour les grid searches
# ============================================================================
#
# Ce module factorise le code commun des scripts run_grid_search_*.py :
# - Generation des combinaisons de parametres
# - Worker multiprocessing pour le calcul parallele
# - Gestion du resume (reprise apres interruption)
# - Affichage des resultats Top 20
#
# Utilisation :
#   from grid_search_runner import GridSearchRunner
#   runner = GridSearchRunner(indicator_params={...}, entry_exit_params={...})
#   runner.run(num_workers=24, output_path="output/results.csv")
#
# ============================================================================

import sys
import time
import itertools
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_hybrid import run_hybrid_backtest
from optimizer import apply_overrides, apply_overrides_fast, compute_metrics


# ============================================================================
# WORKER FUNCTION (niveau module pour multiprocessing)
# ============================================================================

_WORKER_DATA = {}

def _init_worker(df_main_arg, path_5s):
    """Initialise les donnees partagees dans chaque worker (1 fois par worker).
    df_main (5-min, petit) passe par pickle. df_5s (4.6M lignes) est lu depuis parquet."""
    _WORKER_DATA['df_main'] = df_main_arg
    _WORKER_DATA['df_5s'] = pd.read_parquet(path_5s)


def _process_indicator_group(args):
    """
    Worker function : calcule les indicateurs pour un groupe (1 fois),
    puis execute tous les backtests entry/exit pour ce groupe.

    Args:
        args: tuple (g_idx, ind_overrides, base_config,
                     ee_variants, completed_labels, fixed_overrides,
                     label_builder, result_builder, timeframe)

    Returns:
        tuple (g_idx, batch_results, dt_ind)
    """
    (g_idx, ind_ov, base_config, ee_variants,
     completed_labels, fixed_overrides, label_builder, result_builder, timeframe) = args

    df_main = _WORKER_DATA['df_main']
    df_5s = _WORKER_DATA['df_5s']

    # Import dans le worker (necessaire pour multiprocessing sur Windows)
    from indicators import calculate_all_indicators
    from backtest_engine_hybrid import run_hybrid_backtest
    from optimizer import apply_overrides, apply_overrides_fast, compute_metrics

    # Construire le prefixe du groupe d'indicateurs
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)
    group_prefix = f"b{beta}_zp{zp}_cp{cp}_adf{adf}"

    # Verifier si tout le groupe est deja fait (skip si resume)
    group_done = all(
        label_builder(group_prefix, ee) in completed_labels
        for ee in ee_variants
    )
    if group_done:
        return g_idx, [], 0.0

    # Calculer les indicateurs (1 fois par groupe)
    config_ind = apply_overrides_fast(base_config, {**ind_ov, **fixed_overrides})
    t_ind = time.time()
    df_ind = calculate_all_indicators(df_main, config_ind, verbose=False)
    dt_ind = time.time() - t_ind

    # Tester toutes les variantes entry/exit
    batch_results = []
    for ee in ee_variants:
        label = label_builder(group_prefix, ee)

        if label in completed_labels:
            continue

        # Fusionner tous les overrides
        if isinstance(ee, dict) and "overrides" in ee:
            merged = {**ind_ov, **ee["overrides"], **fixed_overrides}
        else:
            merged = {**ind_ov, **ee, **fixed_overrides}

        config_test = apply_overrides_fast(base_config, merged)
        trades = run_hybrid_backtest(df_ind, df_5s, config_test, verbose=False)
        m = compute_metrics(trades)

        # Compter les types de sorties
        if len(trades) > 0:
            tp_zscore = (trades['Exit_Reason'] == 'TP_ZSCORE').sum()
            tp_dollar = (trades['Exit_Reason'] == 'TP_DOLLAR').sum()
            sl_zscore = (trades['Exit_Reason'] == 'SL_ZSCORE').sum()
            sl_dollar = (trades['Exit_Reason'] == 'SL_DOLLAR').sum()
            max_hold = (trades['Exit_Reason'] == 'MAX_HOLD').sum()
            end_session = (trades['Exit_Reason'] == 'END_SESSION').sum()
        else:
            tp_zscore = tp_dollar = sl_zscore = sl_dollar = max_hold = end_session = 0

        # Construire le resultat via le callback
        result = result_builder(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar, max_hold, end_session)
        batch_results.append(result)

    return g_idx, batch_results, dt_ind


# ============================================================================
# CLASSE PRINCIPALE
# ============================================================================

class GridSearchRunner:
    """
    Runner generique pour les grid searches.

    Factorise le code commun : generation des combinaisons, worker multiprocessing,
    gestion du resume, affichage des resultats.

    Exemple:
        runner = GridSearchRunner(
            indicator_params={"beta_lookback": [660, 1320], "zscore_period": [15, 20]},
            entry_exit_generator=my_generator_func,
            label_builder=my_label_func,
            result_builder=my_result_func,
        )
        runner.run(num_workers=24, output_path="output/results.csv")
    """

    def __init__(
        self,
        indicator_params: Dict[str, List[Any]],
        entry_exit_generator: Callable[[], List[Dict]],
        label_builder: Callable[[str, Dict], str],
        result_builder: Callable[[str, Dict, Dict, Dict, int, int, int, int], Dict],
        fixed_overrides: Optional[Dict[str, Any]] = None,
        timeframe: str = "1min",
        title: str = "GRID SEARCH",
    ):
        """
        Initialise le runner.

        Args:
            indicator_params: Dict des parametres indicateurs avec leurs valeurs a tester
                Ex: {"beta_lookback": [660, 1320], "zscore_period": [15, 20]}
            entry_exit_generator: Fonction qui retourne la liste des variantes entry/exit
            label_builder: Fonction(group_prefix, ee_variant) -> label string
            result_builder: Fonction(label, ind_ov, ee, metrics, tp_z, tp_d, sl_z, sl_d) -> dict
            fixed_overrides: Overrides fixes appliques a toutes les configs
            timeframe: "1min" ou "5min" pour le resampling
            title: Titre affiche au lancement
        """
        self.indicator_params = indicator_params
        self.entry_exit_generator = entry_exit_generator
        self.label_builder = label_builder
        self.result_builder = result_builder
        self.fixed_overrides = fixed_overrides or {}
        self.timeframe = timeframe
        self.title = title

        # Generer les combinaisons
        self.indicator_groups = self._generate_indicator_groups()
        self.entry_exit_variants = entry_exit_generator()
        self.total_configs = len(self.indicator_groups) * len(self.entry_exit_variants)

    def _generate_indicator_groups(self) -> List[Dict]:
        """Genere toutes les combinaisons de parametres indicateurs."""
        keys = list(self.indicator_params.keys())
        values = [self.indicator_params[k] for k in keys]
        groups = []
        for combo in itertools.product(*values):
            overrides = {f"indicators.{keys[i]}": combo[i] for i in range(len(keys))}
            groups.append(overrides)
        return groups

    def run(
        self,
        num_workers: int = 24,
        output_path: str = "output/grid_search_results.csv",
        min_trades_for_sharpe: int = 20,
    ):
        """
        Execute le grid search en parallele.

        Args:
            num_workers: Nombre de workers multiprocessing
            output_path: Chemin du fichier CSV de sortie
            min_trades_for_sharpe: Minimum de trades pour le classement Sharpe
        """
        print("=" * 100)
        print(self.title)
        print("=" * 100)

        print(f"\nGroupes indicateurs : {len(self.indicator_groups)}")
        print(f"Variantes entry/exit : {len(self.entry_exit_variants)}")
        print(f"Total configs : {self.total_configs:,}")
        print(f"Workers : {num_workers}")
        print(f"Timeframe : {self.timeframe}")
        if self.fixed_overrides:
            fixes_str = ", ".join(f"{k}={v}" for k, v in self.fixed_overrides.items())
            print(f"Fixes : {fixes_str}")

        # --- Charger les donnees ---
        print("\nChargement des donnees...")
        t0 = time.time()

        df_1min, base_config, stats = load_and_prepare_data(verbose=False)
        print(f"   {len(df_1min):,} barres 1-min chargees ({time.time()-t0:.1f}s)")

        if self.timeframe == "5min":
            df_main = resample_to_5min(df_1min, verbose=True)
            print(f"   {len(df_main):,} barres 5-min")
        else:
            df_main = df_1min

        df_5s = load_5s_data(base_config, verbose=False)
        print(f"   {len(df_5s):,} barres 5s")

        # --- Gestion du resume ---
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        completed_labels = set()
        if output_path.exists():
            existing = pd.read_csv(output_path, sep=";")
            completed_labels = set(existing["label"].values)
            print(f"\n[RESUME] {len(completed_labels):,} configs deja completees, reprise...")

        # --- Preparer les arguments pour les workers ---
        # Si peu de groupes indicateurs vs workers, chunker les variants
        # pour paralleliser sur les entry/exit au lieu des indicateurs
        n_groups = len(self.indicator_groups)
        if n_groups < num_workers and len(self.entry_exit_variants) > 1000:
            # Splitter les variants en petits chunks (~1000 configs) pour
            # avoir des resultats intermediaires reguliers (~1h entre chaque)
            all_variants = self.entry_exit_variants
            target_chunk_size = 1000
            chunk_size = max(1, min(target_chunk_size, len(all_variants) // num_workers))
            variant_chunks = [
                all_variants[i:i + chunk_size]
                for i in range(0, len(all_variants), chunk_size)
            ]
            worker_args = []
            for g_idx, ind_ov in enumerate(self.indicator_groups):
                for chunk in variant_chunks:
                    worker_args.append(
                        (g_idx, ind_ov, base_config, chunk,
                         completed_labels, self.fixed_overrides, self.label_builder,
                         self.result_builder, self.timeframe)
                    )
            # Mettre a jour le nombre de groupes pour l'affichage de progression
            self._total_tasks = len(worker_args)
            print(f"\n[CHUNK] {n_groups} groupe(s) x {len(variant_chunks)} chunks = {len(worker_args)} taches paralleles")
        else:
            worker_args = [
                (g_idx, ind_ov, base_config, self.entry_exit_variants,
                 completed_labels, self.fixed_overrides, self.label_builder,
                 self.result_builder, self.timeframe)
                for g_idx, ind_ov in enumerate(self.indicator_groups)
            ]
            self._total_tasks = len(worker_args)

        # --- Lancer le pool multiprocessing ---
        print(f"\nLancement de {num_workers} workers en parallele...")
        t_start = time.time()

        groups_done = 0
        total_results = 0
        best_pnl_global = -999999
        best_label_global = ""

        # Ecrire df_5s en parquet temporaire pour eviter le pickle (4.6M lignes)
        import tempfile
        tmp_5s = Path(tempfile.mktemp(suffix='_5s.parquet'))
        df_5s.to_parquet(tmp_5s)
        del df_5s  # Liberer la memoire du processus parent
        print(f"   [OK] df_5s ecrit en parquet temporaire ({tmp_5s})")

        with mp.Pool(processes=num_workers,
                     initializer=_init_worker,
                     initargs=(df_main, tmp_5s)) as pool:
            for g_idx, batch_results, dt_ind in pool.imap_unordered(_process_indicator_group, worker_args):
                groups_done += 1

                if not batch_results:
                    # Groupe deja complet ou aucun resultat
                    if groups_done % 50 == 0:
                        elapsed = time.time() - t_start
                        pct = groups_done / self._total_tasks * 100
                        print(f"[{groups_done:>4}/{self._total_tasks}] (skip) "
                              f"{pct:.0f}% {elapsed/60:.0f}min", flush=True)
                    continue

                # Sauvegarder le batch dans le CSV
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
                pct = groups_done / self._total_tasks * 100
                eta_min = (elapsed / groups_done * (self._total_tasks - groups_done)) / 60 if groups_done > 0 else 0

                # Retrouver les params du groupe pour l'affichage
                ind_ov = self.indicator_groups[g_idx]
                beta = ind_ov.get("indicators.beta_lookback", 0)
                zp = ind_ov.get("indicators.zscore_period", 0)

                print(f"[{groups_done:>4}/{self._total_tasks}] b{beta}_zp{zp} "
                      f"ind={dt_ind:.1f}s | {len(batch_results)} configs | "
                      f"best=${best['pnl_net']:>+10,.0f} Sh={best.get('sharpe', 0):>+6.2f} | "
                      f"{pct:.0f}% {elapsed/60:.0f}min ETA={eta_min:.0f}min", flush=True)

        # Cleanup parquet temporaire
        if tmp_5s.exists():
            tmp_5s.unlink()

        # --- Afficher les resultats ---
        t_total = time.time() - t_start
        self._print_results(output_path, t_total, best_label_global, best_pnl_global, min_trades_for_sharpe)

    def _print_results(
        self,
        output_path: Path,
        t_total: float,
        best_label: str,
        best_pnl: float,
        min_trades: int
    ):
        """Affiche les resultats finaux (Top 20 par PnL, Sharpe, Ratio)."""
        if not output_path.exists():
            print("[ERREUR] Aucun resultat. Verifier les logs.")
            return

        df_all = pd.read_csv(output_path, sep=";")
        n_total = len(df_all)
        n_profitable = len(df_all[df_all["pnl_net"] > 0]) if n_total > 0 else 0
        n_trades_pos = len(df_all[df_all["trades"] > 0]) if n_total > 0 else 0

        print("\n\n" + "=" * 130)
        print(f"GRID SEARCH TERMINE : {n_total:,} configs en {t_total/3600:.1f}h")
        print(f"Configs avec trades : {n_trades_pos:,} / {n_total:,}")
        if n_total > 0:
            print(f"Configs rentables : {n_profitable:,} / {n_total:,} ({n_profitable/n_total*100:.1f}%)")
        print(f"Meilleur global : {best_label} PnL=${best_pnl:,.0f}")
        print("=" * 130)

        if n_total == 0:
            return

        # Top 20 par PnL
        top_pnl = df_all.nlargest(20, "pnl_net")
        print(f"\n{'='*130}")
        print("TOP 20 PAR PNL NET")
        print(f"{'='*130}")
        print(f"{'#':<3} {'Config':<65} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
        print("-" * 130)
        for i, (_, r) in enumerate(top_pnl.iterrows()):
            sharpe = r.get('sharpe', 0)
            print(f"{i+1:<3} {r['label']:<65} {int(r['trades']):>7} {r['win_rate']:>5.1f}% "
                  f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {sharpe:>6.2f}")

        # Top 20 par Sharpe (min trades)
        if "sharpe" in df_all.columns:
            df_filtered = df_all[df_all["trades"] >= min_trades]
            if len(df_filtered) > 0:
                top_sharpe = df_filtered.nlargest(20, "sharpe")
                print(f"\n{'='*130}")
                print(f"TOP 20 PAR SHARPE (min {min_trades} trades)")
                print(f"{'='*130}")
                print(f"{'#':<3} {'Config':<65} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Sharpe':>7}")
                print("-" * 130)
                for i, (_, r) in enumerate(top_sharpe.iterrows()):
                    print(f"{i+1:<3} {r['label']:<65} {int(r['trades']):>7} {r['win_rate']:>5.1f}% "
                          f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['sharpe']:>6.2f}")

        # Top 20 par PnL/MaxDD ratio
        if "max_dd" in df_all.columns:
            df_filtered2 = df_all[df_all["trades"] >= min_trades].copy()
            if len(df_filtered2) > 0:
                df_filtered2["pnl_dd_ratio"] = df_filtered2.apply(
                    lambda r: r["pnl_net"] / abs(r["max_dd"]) if r["max_dd"] != 0 else 0, axis=1)
                top_ratio = df_filtered2.nlargest(20, "pnl_dd_ratio")
                print(f"\n{'='*130}")
                print(f"TOP 20 PAR PNL/MAXDD RATIO (min {min_trades} trades)")
                print(f"{'='*130}")
                print(f"{'#':<3} {'Config':<65} {'Trades':>7} {'WR%':>6} {'PnL':>11} {'PF':>7} {'MaxDD':>10} {'Ratio':>7}")
                print("-" * 130)
                for i, (_, r) in enumerate(top_ratio.iterrows()):
                    print(f"{i+1:<3} {r['label']:<65} {int(r['trades']):>7} {r['win_rate']:>5.1f}% "
                          f"${r['pnl_net']:>9,.0f} {r['profit_factor']:>6.2f} ${r['max_dd']:>8,.0f} {r['pnl_dd_ratio']:>6.2f}")

        print(f"\n[OK] Resultats sauvegardes dans {output_path}")
        print(f"[OK] Duree totale : {t_total/3600:.1f}h ({t_total/60:.0f} min)")


# ============================================================================
# HELPERS POUR CREER DES GENERATEURS STANDARD
# ============================================================================

def create_standard_entry_exit_generator(
    zscore_entry: List[float],
    cointegration_min: List[int],
    pnl_take_profit: List[int],
    pnl_stop_loss: List[int],
) -> Callable[[], List[Dict]]:
    """
    Cree un generateur standard pour les variantes entry/exit (mode dollar).

    Args:
        zscore_entry: Liste des seuils Z-Score entry (valeurs positives)
        cointegration_min: Liste des seuils cointegration minimum
        pnl_take_profit: Liste des TP en dollars
        pnl_stop_loss: Liste des SL en dollars (valeurs negatives)

    Returns:
        Fonction qui genere la liste des variantes
    """
    def generator():
        variants = []
        for zE in zscore_entry:
            for co in cointegration_min:
                for tp in pnl_take_profit:
                    for sl in pnl_stop_loss:
                        variants.append({
                            "entry.zscore_long": -abs(zE),
                            "entry.zscore_short": abs(zE),
                            "entry.cointegration_score_min": co,
                            "exit.pnl_take_profit": tp,
                            "exit.pnl_stop_loss": sl if sl < 0 else -sl,
                        })
        return variants
    return generator


def _standard_label_builder(group_prefix: str, ee: Dict) -> str:
    """Label builder standard pour le mode dollar (module-level, picklable)."""
    zE = abs(ee.get("entry.zscore_long", 0))
    co = ee.get("entry.cointegration_score_min", 0)
    tp = ee.get("exit.pnl_take_profit", 0)
    sl = abs(ee.get("exit.pnl_stop_loss", 0))
    return f"{group_prefix}_zE{zE}_co{co}_TP{tp}_SL{sl}"


def _standard_result_builder(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar, max_hold=0, end_session=0):
    """Result builder standard (module-level, picklable)."""
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)

    zE = abs(ee.get("entry.zscore_long", 0))
    co = ee.get("entry.cointegration_score_min", 0)
    tp = ee.get("exit.pnl_take_profit", 0)
    sl = abs(ee.get("exit.pnl_stop_loss", 0))

    return {
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
        "calmar": round(m["pnl_net"] / abs(m["max_dd"]), 2) if m["max_dd"] != 0 else 0,
        "sortino": round(m.get("sortino", 0), 3),
        "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
        "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
    }


def create_standard_label_builder() -> Callable[[str, Dict], str]:
    """Retourne le label builder standard pour le mode dollar."""
    return _standard_label_builder


def create_standard_result_builder() -> Callable:
    """Retourne le result builder standard."""
    return _standard_result_builder


# ============================================================================
# HELPERS POUR LE MODE 5-MIN PURE Z-SCORE
# ============================================================================

def create_zscore_entry_exit_generator(
    zscore_entry: List[float],
    cointegration_min: List[int],
    zscore_tp: List[float],
    zscore_sl: List[float],
    dollar_modes: List[str] = ["pure_zscore"],
) -> Callable[[], List[Dict]]:
    """
    Cree un generateur pour les variantes entry/exit en mode Z-Score pur.

    Args:
        zscore_entry: Liste des seuils Z-Score entry
        cointegration_min: Liste des seuils cointegration
        zscore_tp: Liste des seuils Z-Score TP
        zscore_sl: Liste des seuils Z-Score SL
        dollar_modes: Liste des modes dollar ("pure_zscore" ou "safety")

    Returns:
        Fonction qui genere la liste des variantes
    """
    def generator():
        variants = []
        for zE in zscore_entry:
            for co in cointegration_min:
                for zTP in zscore_tp:
                    for zSL in zscore_sl:
                        for mode in dollar_modes:
                            ov = {
                                "entry.zscore_long": -abs(zE),
                                "entry.zscore_short": abs(zE),
                                "entry.cointegration_score_min": co,
                                "exit.zscore_tp_long": -zTP,
                                "exit.zscore_tp_short": zTP,
                                "exit.zscore_sl_long": -abs(zSL),
                                "exit.zscore_sl_short": abs(zSL),
                            }

                            if mode == "pure_zscore":
                                ov["exit.pnl_take_profit"] = 99999
                                ov["exit.pnl_stop_loss"] = -99999
                            else:  # safety
                                ov["exit.pnl_take_profit"] = 99999
                                ov["exit.pnl_stop_loss"] = -2000

                            variants.append({
                                "overrides": ov,
                                "zE": zE, "co": co, "zTP": zTP, "zSL": zSL,
                                "mode": mode,
                            })
        return variants
    return generator


def _zscore_label_builder(group_prefix: str, ee: Dict) -> str:
    """Label builder pour le mode Z-Score pur (module-level, picklable)."""
    mode_tag = "pure" if ee.get("mode") == "pure_zscore" else "safe"
    return (f"{group_prefix}_zE{ee['zE']}_co{ee['co']}"
            f"_zTP{ee['zTP']}_zSL{ee['zSL']}_{mode_tag}")


def _zscore_result_builder(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar, max_hold=0, end_session=0):
    """Result builder pour le mode Z-Score pur (module-level, picklable)."""
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)

    return {
        "label": label,
        "beta": beta, "zp": zp, "cp": cp, "adf": adf,
        "zE": ee["zE"], "co": ee["co"],
        "zTP": ee["zTP"], "zSL": ee["zSL"],
        "mode": ee["mode"],
        "trades": m["trades"], "long": m["long"], "short": m["short"],
        "win_rate": round(m["win_rate"], 1),
        "pnl_net": round(m["pnl_net"], 0),
        "pnl_avg": round(m["pnl_avg"], 2),
        "profit_factor": round(m["profit_factor"], 2),
        "max_dd": round(m["max_dd"], 0),
        "sharpe": round(m["sharpe"], 2),
        "calmar": round(m["pnl_net"] / abs(m["max_dd"]), 2) if m["max_dd"] != 0 else 0,
        "sortino": round(m.get("sortino", 0), 3),
        "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
        "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
    }


def create_zscore_label_builder() -> Callable[[str, Dict], str]:
    """Retourne le label builder pour le mode Z-Score pur."""
    return _zscore_label_builder


def create_zscore_result_builder() -> Callable:
    """Retourne le result builder pour le mode Z-Score pur."""
    return _zscore_result_builder


# ============================================================================
# HELPERS POUR LE MODE HYBRIDE (Z-Score TP + Dollar SL)
# ============================================================================

def create_hybrid_entry_exit_generator(
    zscore_entry: List[float],
    cointegration_min: List[int],
    zscore_tp: List[float],
    pnl_stop_loss: List[int],
    pnl_take_profit_cap: List[int] = [99999],
) -> Callable[[], List[Dict]]:
    """
    Cree un generateur pour le mode hybride : Z-Score TP + Dollar SL.

    Args:
        zscore_entry: Liste des seuils Z-Score entry (valeurs positives)
        cointegration_min: Liste des seuils cointegration minimum
        zscore_tp: Liste des seuils Z-Score TP
        pnl_stop_loss: Liste des SL en dollars (valeurs negatives)
        pnl_take_profit_cap: Cap dollar TP optionnel (99999 = desactive)

    Returns:
        Fonction qui genere la liste des variantes
    """
    def generator():
        variants = []
        for zE in zscore_entry:
            for co in cointegration_min:
                for zTP in zscore_tp:
                    for sl in pnl_stop_loss:
                        for tp_cap in pnl_take_profit_cap:
                            ov = {
                                "entry.zscore_long": -abs(zE),
                                "entry.zscore_short": abs(zE),
                                "entry.cointegration_score_min": co,
                                "exit.zscore_tp_long": -zTP,
                                "exit.zscore_tp_short": zTP,
                                "exit.zscore_sl_long": -99999,
                                "exit.zscore_sl_short": 99999,
                                "exit.pnl_take_profit": tp_cap,
                                "exit.pnl_stop_loss": sl if sl < 0 else -sl,
                            }
                            variants.append({
                                "overrides": ov,
                                "zE": zE, "co": co, "zTP": zTP,
                                "SL": abs(sl), "TP_cap": tp_cap,
                            })
        return variants
    return generator


def _hybrid_label_builder(group_prefix: str, ee: Dict) -> str:
    """Label builder pour le mode hybride (module-level, picklable)."""
    tp_cap = ee.get("TP_cap", 99999)
    tp_tag = f"_TPcap{tp_cap}" if tp_cap != 99999 else ""
    return (f"{group_prefix}_zE{ee['zE']}_co{ee['co']}"
            f"_zTP{ee['zTP']}_SL{ee['SL']}{tp_tag}")


def _hybrid_result_builder(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar, max_hold=0, end_session=0):
    """Result builder pour le mode hybride (module-level, picklable)."""
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)

    return {
        "label": label,
        "beta": beta, "zp": zp, "cp": cp, "adf": adf,
        "zE": ee["zE"], "co": ee["co"],
        "zTP": ee["zTP"], "SL": ee["SL"], "TP_cap": ee["TP_cap"],
        "trades": m["trades"], "long": m["long"], "short": m["short"],
        "win_rate": round(m["win_rate"], 1),
        "pnl_net": round(m["pnl_net"], 0),
        "pnl_avg": round(m["pnl_avg"], 2),
        "profit_factor": round(m["profit_factor"], 2),
        "max_dd": round(m["max_dd"], 0),
        "sharpe": round(m["sharpe"], 2),
        "calmar": round(m["pnl_net"] / abs(m["max_dd"]), 2) if m["max_dd"] != 0 else 0,
        "sortino": round(m.get("sortino", 0), 3),
        "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
        "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
    }


def create_hybrid_label_builder() -> Callable[[str, Dict], str]:
    """Retourne le label builder pour le mode hybride."""
    return _hybrid_label_builder


def create_hybrid_result_builder() -> Callable:
    """Retourne le result builder pour le mode hybride."""
    return _hybrid_result_builder


# ============================================================================
# HELPERS POUR LE MODE MICRO_FULL (tous parametres explores)
# ============================================================================

def create_micro_full_entry_exit_generator(
    zscore_entry: List[float],
    cointegration_min: List[int],
    zscore_tp: List[float],
    zscore_sl: List[float],
    dollar_tp: List[int],
    dollar_sl: List[int],
    flat_end_of_session: List[bool],
    max_holding_bars: List[int],
    micro_multiplier_max: List[int],
) -> Callable[[], List[Dict]]:
    """
    Generateur pour le mode micro_full : exploration complete de tous les
    parametres entry/exit/session/sizing pour le sizing micro prop firm.
    """
    def generator():
        variants = []
        for zE in zscore_entry:
            for co in cointegration_min:
                for zTP in zscore_tp:
                    for zSL in zscore_sl:
                        # Skip si zSL <= zE (SL declenche immediatement)
                        if zSL != 99 and zSL <= zE:
                            continue
                        for dTP in dollar_tp:
                            for dSL in dollar_sl:
                                for feos in flat_end_of_session:
                                    for mhb in max_holding_bars:
                                        for mm in micro_multiplier_max:
                                            ov = {
                                                "entry.zscore_long": -abs(zE),
                                                "entry.zscore_short": abs(zE),
                                                "entry.cointegration_score_min": co,
                                                "exit.zscore_tp_long": -zTP,
                                                "exit.zscore_tp_short": zTP,
                                                "exit.zscore_sl_long": -abs(zSL),
                                                "exit.zscore_sl_short": abs(zSL),
                                                "exit.pnl_take_profit": dTP if dTP > 0 else 99999,
                                                "exit.pnl_stop_loss": dSL if dSL < 0 else -99999,
                                                "exit.max_holding_bars": mhb,
                                                "session.flat_end_of_session": feos,
                                                "sizing.micro_multiplier_max": mm,
                                            }
                                            variants.append({
                                                "overrides": ov,
                                                "zE": zE, "co": co,
                                                "zTP": zTP, "zSL": zSL,
                                                "dTP": dTP, "dSL": dSL,
                                                "feos": feos, "mhb": mhb,
                                                "mm": mm,
                                            })
        return variants
    return generator


def _micro_full_label_builder(group_prefix: str, ee: Dict) -> str:
    """Label builder pour le mode micro_full (module-level, picklable)."""
    feos_tag = "feos" if ee["feos"] else "nofeos"
    mhb_tag = f"mhb{ee['mhb']}" if ee["mhb"] > 0 else "nohold"
    dtp_tag = f"dTP{ee['dTP']}" if ee["dTP"] > 0 else "nodTP"
    dsl_tag = f"dSL{abs(ee['dSL'])}" if ee["dSL"] < 0 else "nodSL"
    return (f"{group_prefix}_zE{ee['zE']}_co{ee['co']}"
            f"_zTP{ee['zTP']}_zSL{ee['zSL']}"
            f"_{dtp_tag}_{dsl_tag}_{feos_tag}_{mhb_tag}_mm{ee['mm']}")


def _micro_full_result_builder(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar, max_hold=0, end_session=0):
    """Result builder pour le mode micro_full (module-level, picklable)."""
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)

    return {
        "label": label,
        "beta": beta, "zp": zp, "cp": cp, "adf": adf,
        "zE": ee["zE"], "co": ee["co"],
        "zTP": ee["zTP"], "zSL": ee["zSL"],
        "dTP": ee["dTP"], "dSL": ee["dSL"],
        "feos": ee["feos"], "mhb": ee["mhb"], "mm": ee["mm"],
        "trades": m["trades"], "long": m["long"], "short": m["short"],
        "win_rate": round(m["win_rate"], 1),
        "pnl_net": round(m["pnl_net"], 0),
        "pnl_avg": round(m["pnl_avg"], 2),
        "profit_factor": round(m["profit_factor"], 2),
        "max_dd": round(m["max_dd"], 0),
        "sharpe": round(m["sharpe"], 2),
        "calmar": round(m["pnl_net"] / abs(m["max_dd"]), 2) if m["max_dd"] != 0 else 0,
        "sortino": round(m.get("sortino", 0), 3),
        "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
        "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
        "max_hold": max_hold, "end_session": end_session,
    }


def create_micro_full_label_builder() -> Callable[[str, Dict], str]:
    """Retourne le label builder pour le mode micro_full."""
    return _micro_full_label_builder


def create_micro_full_result_builder() -> Callable:
    """Retourne le result builder pour le mode micro_full."""
    return _micro_full_result_builder
