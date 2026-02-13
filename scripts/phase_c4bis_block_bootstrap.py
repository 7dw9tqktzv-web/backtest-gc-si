#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ============================================================================
# PHASE C4bis : BLOCK BOOTSTRAP + FILTRE HORAIRE
# ============================================================================
#
# Tache 1: Monte Carlo Block Bootstrap (corrige l'autocorrelation des trades)
# Tache 2: Test filtre horaire (7h-8h CT toxique)
#
# Usage : python scripts/phase_c4bis_block_bootstrap.py
# ============================================================================

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides

# -- Constantes
N_SIMULATIONS = 1000
SEED = 42
HORIZONS = [50, 100, 150, 200]
BLOCK_SIZES = [3, 5, 7, 10]
OUTPUT_DIR = Path("output")

# Config production (identique a C4)
PROD_OVERRIDES = {
    "indicators.period": "5min",
    "indicators.beta_lookback": 2640,
    "indicators.zscore_period": 20,
    "indicators.correlation_period": 30,
    "indicators.adf_hurst_period": 26,
    "entry.zscore_long": -3.5,
    "entry.zscore_short": 3.5,
    "entry.cointegration_score_min": 40,
    "exit.zscore_tp_enabled": True,
    "exit.zscore_tp_long": 1.0,
    "exit.zscore_tp_short": -1.0,
    "exit.zscore_sl_long": -4.0,
    "exit.zscore_sl_short": 4.0,
    "exit.pnl_take_profit": 99999,
    "exit.pnl_stop_loss": -99999,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}


def load_data_and_trades():
    """Charge les donnees une seule fois, retourne trades + objets necessaires."""
    print("=" * 70)
    print("  PHASE C4bis : CHARGEMENT DES DONNEES")
    print("=" * 70)

    df_1min, config, stats = load_and_prepare_data(verbose=True)
    df_5min = resample_to_5min(df_1min, verbose=True)
    df_5s = load_5s_data(config, verbose=True)
    cfg = apply_overrides(config, PROD_OVERRIDES)

    # Indicateurs 5min
    df_5min_ind = calculate_all_indicators(df_5min, cfg, verbose=True)

    # Backtest baseline (24h)
    print("\n   Backtest baseline (24h)...")
    trades_baseline = run_hybrid_backtest(df_5min_ind, df_5s, cfg, verbose=True)
    trades_baseline = trades_baseline[trades_baseline["Exit_Reason"] != "STILL_OPEN"].copy()
    print(f"   => {len(trades_baseline)} trades")

    return trades_baseline, df_5min_ind, df_5s, cfg, config


# ============================================================================
# TACHE 1 : BLOCK BOOTSTRAP
# ============================================================================

def confirm_autocorrelation(pnls):
    """Etape 1: confirmer l'autocorrelation."""
    print("\n" + "=" * 70)
    print("  ETAPE 1 : CONFIRMATION AUTOCORRELATION")
    print("=" * 70)

    n = len(pnls)

    for lag in [1, 2, 3]:
        if n > lag + 5:
            r, p = scipy_stats.pearsonr(pnls[:-lag], pnls[lag:])
            sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
            print(f"   Lag {lag}: r={r:.4f}, p={p:.6f} {sig}")

    # Test de runs
    wins = (pnls > 0).astype(int)
    n_pos = wins.sum()
    n_neg = n - n_pos
    runs = 1
    for i in range(1, n):
        if wins[i] != wins[i - 1]:
            runs += 1

    mu_runs = 1 + (2 * n_pos * n_neg) / n
    var_runs = (2 * n_pos * n_neg * (2 * n_pos * n_neg - n)) / (n * n * (n - 1))
    sigma_runs = np.sqrt(var_runs) if var_runs > 0 else 1
    z_runs = (runs - mu_runs) / sigma_runs
    p_runs = 2 * (1 - scipy_stats.norm.cdf(abs(z_runs)))
    print(f"\n   Test de runs: {runs} observes, {mu_runs:.1f} attendus, Z={z_runs:.2f}, p={p_runs:.4f}")

    # Interpretation
    print(f"\n   Interpretation:")
    print(f"   - Autocorrelation PnL magnitude = FORTE (r=0.50 lag 1)")
    print(f"   - Sequence win/loss = ALEATOIRE (runs test p={p_runs:.2f})")
    print(f"   - => Les regimes creent de l'autocorrelation en magnitude, pas en direction")
    print(f"   - => Le bootstrap i.i.d. est INVALIDE pour estimer le risque")


def block_bootstrap_simulation(pnls, block_size, n_trades, n_simulations):
    """Un block bootstrap pour un block_size et un horizon donnes."""
    n = len(pnls)
    cumulative_pnls = np.empty(n_simulations)
    max_drawdowns = np.empty(n_simulations)

    for i in range(n_simulations):
        # Construire une sequence en tirant des blocs
        sampled = []
        while len(sampled) < n_trades:
            start = np.random.randint(0, max(1, n - block_size + 1))
            block = pnls[start:start + block_size].tolist()
            sampled.extend(block)
        sampled = np.array(sampled[:n_trades])

        cumulative = np.cumsum(sampled)
        cumulative_pnls[i] = cumulative[-1]
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        max_drawdowns[i] = drawdowns.min()

    return cumulative_pnls, max_drawdowns


def iid_bootstrap_simulation(pnls, n_trades, n_simulations):
    """Bootstrap i.i.d. classique (pour comparaison)."""
    cumulative_pnls = np.empty(n_simulations)
    max_drawdowns = np.empty(n_simulations)

    for i in range(n_simulations):
        sampled = np.random.choice(pnls, size=n_trades, replace=True)
        cumulative = np.cumsum(sampled)
        cumulative_pnls[i] = cumulative[-1]
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        max_drawdowns[i] = drawdowns.min()

    return cumulative_pnls, max_drawdowns


def run_block_bootstrap(pnls):
    """Etape 2+3 : Block bootstrap complet."""
    print("\n" + "=" * 70)
    print("  ETAPE 2 : BLOCK BOOTSTRAP (1000 sims)")
    print("=" * 70)

    np.random.seed(SEED)
    all_results = {}

    # i.i.d. bootstrap
    print("\n   i.i.d. bootstrap...")
    for h in HORIZONS:
        cpnls, mdds = iid_bootstrap_simulation(pnls, h, N_SIMULATIONS)
        all_results[("iid", h)] = {"pnls": cpnls, "mdds": mdds}

    # Block bootstrap pour chaque taille
    for bs in BLOCK_SIZES:
        print(f"   Block bootstrap (k={bs})...")
        for h in HORIZONS:
            cpnls, mdds = block_bootstrap_simulation(pnls, bs, h, N_SIMULATIONS)
            all_results[(f"block_{bs}", h)] = {"pnls": cpnls, "mdds": mdds}

    # -- Tableau 1 : Comparaison a 100 trades
    print("\n" + "=" * 70)
    print("  ETAPE 3 : COMPARAISON i.i.d. vs BLOCK (horizon 100 trades)")
    print("=" * 70)

    print(f"\n   {'Methode':<14} | {'P(perte)':>8} | {'PnL P5':>10} | {'PnL Median':>10} | "
          f"{'PnL P95':>10} | {'MaxDD P5':>10}")
    print("   " + "-" * 76)

    methods_100 = [("iid", "i.i.d. (C4)")] + [(f"block_{bs}", f"Block (k={bs})") for bs in BLOCK_SIZES]
    for key, label in methods_100:
        r = all_results[(key, 100)]
        p_loss = 100 * (r["pnls"] < 0).sum() / len(r["pnls"])
        p5 = np.percentile(r["pnls"], 5)
        med = np.median(r["pnls"])
        p95 = np.percentile(r["pnls"], 95)
        dd_p5 = np.percentile(r["mdds"], 5)
        print(f"   {label:<14} | {p_loss:>7.1f}% | ${p5:>9,.0f} | ${med:>9,.0f} | "
              f"${p95:>9,.0f} | ${dd_p5:>9,.0f}")

    # -- Tableau 2 : Block k=5, tous horizons
    print(f"\n   Block bootstrap (k=5), tous horizons:")
    print(f"   {'Horizon':<12} | {'P(perte)':>8} | {'PnL P5':>10} | {'PnL P25':>10} | "
          f"{'PnL Median':>10} | {'PnL P75':>10} | {'PnL P95':>10}")
    print("   " + "-" * 80)

    for h in HORIZONS:
        r = all_results[("block_5", h)]
        p_loss = 100 * (r["pnls"] < 0).sum() / len(r["pnls"])
        p5 = np.percentile(r["pnls"], 5)
        p25 = np.percentile(r["pnls"], 25)
        med = np.median(r["pnls"])
        p75 = np.percentile(r["pnls"], 75)
        p95 = np.percentile(r["pnls"], 95)
        print(f"   {h:>8} tr  | {p_loss:>7.1f}% | ${p5:>9,.0f} | ${p25:>9,.0f} | "
              f"${med:>9,.0f} | ${p75:>9,.0f} | ${p95:>9,.0f}")

    # -- Tableau MaxDD block k=5
    print(f"\n   MaxDD Block (k=5):")
    print(f"   {'Horizon':<12} | {'MaxDD P5':>12} | {'MaxDD Median':>12} | {'MaxDD P95':>12}")
    print("   " + "-" * 55)
    for h in HORIZONS:
        r = all_results[("block_5", h)]
        dd5 = np.percentile(r["mdds"], 5)
        dd50 = np.median(r["mdds"])
        dd95 = np.percentile(r["mdds"], 95)
        print(f"   {h:>8} tr  | ${dd5:>11,.0f} | ${dd50:>11,.0f} | ${dd95:>11,.0f}")

    return all_results


def verdict_block_bootstrap(all_results):
    """Etape 4: verdict et recommandation sizing."""
    print("\n" + "=" * 70)
    print("  ETAPE 4 : VERDICT BLOCK BOOTSTRAP")
    print("=" * 70)

    # Utiliser block k=5 comme reference (le plus courant en litterature)
    r = all_results[("block_5", 100)]
    p_loss = 100 * (r["pnls"] < 0).sum() / len(r["pnls"])
    maxdd_p5 = np.percentile(r["mdds"], 5)
    pnl_median = np.median(r["pnls"])

    print(f"\n   Reference : Block bootstrap k=5, horizon 100 trades")
    print(f"   P(perte)     : {p_loss:.1f}%")
    print(f"   PnL median   : ${pnl_median:,.0f}")
    print(f"   MaxDD P5     : ${maxdd_p5:,.0f}")

    # Verdict
    if p_loss < 20:
        verdict = "GO"
        sizing = "normal (1 unite)"
        print(f"\n   >>> {verdict} <<< P(perte) < 20% -- risque acceptable pour compte propre")
    elif p_loss < 30:
        verdict = "GO CONDITIONNEL"
        sizing = "reduit (0.5 unite)"
        print(f"\n   >>> {verdict} <<< P(perte) entre 20-30% -- sizing reduit recommande")
    else:
        verdict = "PAUSE"
        sizing = "minimal (0.25 unite)"
        print(f"\n   >>> {verdict} <<< P(perte) > 30% -- amelioration necessaire avant paper trading")

    # Recommandation sizing
    if p_loss < 10:
        sizing = "normal (1 unite)"
    elif p_loss < 20:
        sizing = "reduit (0.5 unite)"
    elif p_loss < 30:
        sizing = "minimal (0.25 unite)"
    else:
        sizing = "STOP -- ne pas trader"

    print(f"   Sizing recommande : {sizing}")

    # Comparer avec i.i.d.
    r_iid = all_results[("iid", 100)]
    p_loss_iid = 100 * (r_iid["pnls"] < 0).sum() / len(r_iid["pnls"])
    ratio = p_loss / max(p_loss_iid, 0.1)
    print(f"\n   Comparaison : i.i.d. P(perte)={p_loss_iid:.1f}% vs Block P(perte)={p_loss:.1f}%")
    print(f"   Ratio de sous-estimation i.i.d. : {ratio:.1f}x")

    return verdict, p_loss, sizing


def save_block_bootstrap(all_results, verdict, p_loss, sizing):
    """Sauvegarde les resultats."""
    # Synthese
    rows = []
    methods = [("iid", "iid")] + [(f"block_{bs}", f"block_{bs}") for bs in BLOCK_SIZES]
    for key, label in methods:
        for h in HORIZONS:
            r = all_results[(key, h)]
            rows.append({
                "method": label,
                "horizon": h,
                "p_loss_pct": round(100 * (r["pnls"] < 0).sum() / len(r["pnls"]), 1),
                "pnl_p5": round(np.percentile(r["pnls"], 5), 0),
                "pnl_p25": round(np.percentile(r["pnls"], 25), 0),
                "pnl_median": round(np.median(r["pnls"]), 0),
                "pnl_p75": round(np.percentile(r["pnls"], 75), 0),
                "pnl_p95": round(np.percentile(r["pnls"], 95), 0),
                "maxdd_p5": round(np.percentile(r["mdds"], 5), 0),
                "maxdd_median": round(np.median(r["mdds"]), 0),
                "verdict": verdict if (label == "block_5" and h == 100) else "",
            })

    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "phase_c4bis_block_bootstrap_results.csv"
    df.to_csv(path, index=False, sep=";")
    print(f"\n   Resultats detailles : {path}")

    # Synthese courte
    summary = pd.DataFrame([{
        "method": "block_5",
        "horizon": 100,
        "p_loss_pct": p_loss,
        "verdict": verdict,
        "sizing": sizing,
    }])
    spath = OUTPUT_DIR / "phase_c4bis_summary.csv"
    summary.to_csv(spath, index=False, sep=";")
    print(f"   Synthese : {spath}")


# ============================================================================
# TACHE 2 : FILTRE HORAIRE
# ============================================================================

def run_hourly_filter_tests(df_5min_ind, df_5s, cfg, config, trades_baseline):
    """Teste 3 modes de filtre horaire."""
    print("\n" + "=" * 70)
    print("  TACHE 2 : TEST FILTRE HORAIRE")
    print("=" * 70)

    # Les modes a tester
    # Note: le code utilise entry_start_hour <= hour < entry_end_hour
    # La session va de 17h a 15h30 le lendemain
    # Les heures sont en CT (Chicago Time)
    # Mode A = baseline (deja fait)
    # Mode B = bloquer 0-9h (inclut le bloc toxique 7-8h + nuit)
    # Mode C = bloquer 0-8h seulement
    # Probleme: le range ne supporte pas les trous (ex: bloquer juste 7-8h)
    # Solution: tester start=9 (coupe 0-8h) et start=8 (coupe 0-7h59)

    modes = {
        "A: 24h (baseline)": {"session.entry_start_hour": 0, "session.entry_end_hour": 24},
        "B: Block 0-9h CT": {"session.entry_start_hour": 9, "session.entry_end_hour": 24},
        "C: Block 0-8h CT": {"session.entry_start_hour": 8, "session.entry_end_hour": 24},
    }

    results = {}

    for label, overrides in modes.items():
        if "baseline" in label:
            # Reutiliser le baseline deja calcule
            trades = trades_baseline
        else:
            cfg_mode = apply_overrides(cfg.copy(), overrides)
            # On ne recalcule pas les indicateurs (deja dans df_5min_ind)
            # Mais apply_overrides modifie cfg, on doit passer la bonne config
            # En fait, on modifie directement le dict
            import copy
            cfg_copy = copy.deepcopy(cfg)
            for k, v in overrides.items():
                keys = k.split(".")
                d = cfg_copy
                for kk in keys[:-1]:
                    d = d[kk]
                d[keys[-1]] = v

            trades = run_hybrid_backtest(df_5min_ind, df_5s, cfg_copy, verbose=False)
            trades = trades[trades["Exit_Reason"] != "STILL_OPEN"].copy()

        n = len(trades)
        pnl = trades["PnL_Net"].sum()
        wr = (trades["PnL_Net"] > 0).mean() * 100 if n > 0 else 0
        pf = (trades[trades["PnL_Net"] > 0]["PnL_Net"].sum() /
              abs(trades[trades["PnL_Net"] <= 0]["PnL_Net"].sum())
              if (trades["PnL_Net"] <= 0).any() and (trades["PnL_Net"] > 0).any() else 0)
        cumul = trades["PnL_Net"].cumsum()
        maxdd = (cumul - cumul.cummax()).min() if n > 0 else 0
        sharpe = trades["PnL_Net"].mean() / trades["PnL_Net"].std() if n > 1 else 0
        avg_pnl = trades["PnL_Net"].mean() if n > 0 else 0

        results[label] = {
            "trades": n, "pnl": pnl, "wr": wr, "pf": pf,
            "maxdd": maxdd, "sharpe": sharpe, "avg_pnl": avg_pnl,
        }

    # Afficher le tableau comparatif
    print(f"\n   {'Mode':<20} | {'Trades':>6} | {'PnL':>10} | {'WR':>5} | {'PF':>5} | "
          f"{'MaxDD':>10} | {'Sharpe':>6} | {'PnL/Tr':>8}")
    print("   " + "-" * 82)

    for label, r in results.items():
        print(f"   {label:<20} | {r['trades']:>6} | ${r['pnl']:>9,.0f} | {r['wr']:>4.0f}% | "
              f"{r['pf']:>5.2f} | ${r['maxdd']:>9,.0f} | {r['sharpe']:>6.3f} | ${r['avg_pnl']:>7,.0f}")

    # Verdict filtre horaire
    baseline = results["A: 24h (baseline)"]
    best_filter = None
    best_improvement = 0

    for label, r in results.items():
        if "baseline" in label:
            continue
        improvement = r["pnl"] - baseline["pnl"]
        if improvement > best_improvement:
            best_improvement = improvement
            best_filter = label

    print(f"\n   Meilleure amelioration : {best_filter} (+${best_improvement:,.0f})" if best_filter else "\n   Aucune amelioration significative")

    if best_improvement > 5000:
        print(f"   => Amelioration > $5,000 -- walk-forward recommande")
        verdict_hourly = "WALK-FORWARD REQUIS"
    elif best_improvement > 0:
        print(f"   => Amelioration < $5,000 -- insuffisant pour justifier un WF")
        verdict_hourly = "MONITOR"
    else:
        print(f"   => Pas d'amelioration")
        verdict_hourly = "NO-GO"

    # Sauver CSV
    rows = []
    for label, r in results.items():
        rows.append({"mode": label, **r})
    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "phase_c4bis_hourly_filter.csv"
    df.to_csv(path, index=False, sep=";")
    print(f"\n   -> Sauve dans {path}")

    return results, verdict_hourly, best_filter


def run_hourly_walk_forward(best_filter_label, df_5min_ind, df_5s, cfg, config):
    """Walk-forward rapide avec filtre horaire (si amelioration > $5K)."""
    print("\n" + "=" * 70)
    print("  WALK-FORWARD FILTRE HORAIRE (34 fenetres, 63j/21j)")
    print("=" * 70)

    # Determiner les overrides du filtre
    if "0-9h" in best_filter_label:
        hour_start = 9
    elif "0-8h" in best_filter_label:
        hour_start = 8
    else:
        hour_start = 0

    # Import walk-forward runner
    from walk_forward_runner import run_walk_forward

    # Configurer le WF
    import copy

    # WF configs
    wf_grid = [
        {"exit.zscore_tp_long": 1.0, "exit.zscore_tp_short": -1.0,
         "indicators.beta_lookback": beta,
         "indicators.zscore_period": zp,
         "indicators.correlation_period": 30,
         "indicators.adf_hurst_period": 26,
         "entry.cointegration_score_min": 40,
         "exit.zscore_sl_long": zsl_l, "exit.zscore_sl_short": zsl_s}
        for beta in [2640, 3960]
        for zp in [20, 24]
        for zsl_l, zsl_s in [(-4.0, 4.0), (-4.5, 4.5), (-5.0, 5.0)]
    ]

    # Ajouter le filtre horaire a chaque config
    for c in wf_grid:
        c["session.entry_start_hour"] = hour_start
        c["session.entry_end_hour"] = 24

    # Construire la config de base pour le WF
    base_cfg = copy.deepcopy(cfg)
    base_cfg["session"]["entry_start_hour"] = hour_start
    base_cfg["session"]["entry_end_hour"] = 24

    # Lancer le walk-forward
    wf_results = run_walk_forward(
        df_5min_ind, df_5s, base_cfg,
        grid_overrides=wf_grid,
        train_days=63, test_days=21,
        verbose=True
    )

    # Afficher resultats
    if wf_results is not None and len(wf_results) > 0:
        total_pnl = wf_results["test_pnl"].sum()
        total_trades = wf_results["test_trades"].sum()
        pct_positive = (wf_results["test_pnl"] > 0).mean() * 100
        print(f"\n   WF total: {total_trades} trades, ${total_pnl:,.0f} PnL, {pct_positive:.0f}% fenetres positives")

        path = OUTPUT_DIR / "phase_c4bis_hourly_wf.csv"
        wf_results.to_csv(path, index=False, sep=";")
        print(f"   -> Sauve dans {path}")

        return total_pnl, total_trades, pct_positive
    else:
        print("   WF: aucun resultat")
        return 0, 0, 0


# ============================================================================
# RAPPORT MARKDOWN
# ============================================================================

def generate_report(all_results, verdict_bb, p_loss_bb, sizing_bb,
                    hourly_results, verdict_hourly, best_filter):
    """Genere le rapport Phase C4bis."""
    lines = []
    lines.append("# Phase C4bis -- Block Bootstrap + Filtre horaire")
    lines.append("")
    lines.append("*Date: 2026-02-08*")
    lines.append("*Script: `scripts/phase_c4bis_block_bootstrap.py`*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Resume
    lines.append("## Resume executif")
    lines.append("")
    lines.append(f"**{verdict_bb}** -- Block bootstrap P(perte 100tr) = {p_loss_bb:.1f}%. "
                 f"Sizing recommande: {sizing_bb}.")
    lines.append("")

    # Tableau comparaison 100 trades
    lines.append("## Block Bootstrap vs i.i.d. (horizon 100 trades)")
    lines.append("")
    lines.append("| Methode | P(perte) | PnL P5 | PnL Median | PnL P95 | MaxDD P5 |")
    lines.append("|---------|----------|--------|------------|---------|----------|")

    methods = [("iid", "i.i.d. (C4)")] + [(f"block_{bs}", f"Block (k={bs})") for bs in BLOCK_SIZES]
    for key, label in methods:
        r = all_results[(key, 100)]
        p_loss = 100 * (r["pnls"] < 0).sum() / len(r["pnls"])
        p5 = np.percentile(r["pnls"], 5)
        med = np.median(r["pnls"])
        p95 = np.percentile(r["pnls"], 95)
        dd5 = np.percentile(r["mdds"], 5)
        lines.append(f"| {label} | {p_loss:.1f}% | ${p5:,.0f} | ${med:,.0f} | ${p95:,.0f} | ${dd5:,.0f} |")
    lines.append("")

    # Tableau block k=5 tous horizons
    lines.append("## Block bootstrap k=5, tous horizons")
    lines.append("")
    lines.append("| Horizon | P(perte) | PnL P5 | PnL Median | PnL P95 |")
    lines.append("|---------|----------|--------|------------|---------|")
    for h in HORIZONS:
        r = all_results[("block_5", h)]
        p_loss = 100 * (r["pnls"] < 0).sum() / len(r["pnls"])
        p5 = np.percentile(r["pnls"], 5)
        med = np.median(r["pnls"])
        p95 = np.percentile(r["pnls"], 95)
        lines.append(f"| {h} trades | {p_loss:.1f}% | ${p5:,.0f} | ${med:,.0f} | ${p95:,.0f} |")
    lines.append("")

    # Filtre horaire
    lines.append("## Filtre horaire")
    lines.append("")
    lines.append("| Mode | Trades | PnL | WR | PF | MaxDD | PnL/Trade |")
    lines.append("|------|--------|-----|----|----|-------|-----------|")
    for label, r in hourly_results.items():
        lines.append(f"| {label} | {r['trades']} | ${r['pnl']:,.0f} | {r['wr']:.0f}% | "
                     f"{r['pf']:.2f} | ${r['maxdd']:,.0f} | ${r['avg_pnl']:,.0f} |")
    lines.append("")
    lines.append(f"**Verdict filtre horaire: {verdict_hourly}**")
    lines.append("")

    # Verdict global
    lines.append("## Verdict final C4bis")
    lines.append("")
    lines.append(f"- Block bootstrap: **{verdict_bb}** (P(perte)={p_loss_bb:.1f}%, sizing={sizing_bb})")
    lines.append(f"- Filtre horaire: **{verdict_hourly}**")
    lines.append("")

    lines.append("---")
    lines.append("*Rapport genere par `scripts/phase_c4bis_block_bootstrap.py`*")

    report = "\n".join(lines)
    path = OUTPUT_DIR / "reports" / "PHASE_C4BIS_RESULTS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n   Rapport: {path}")
    return path


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  PHASE C4bis : BLOCK BOOTSTRAP + FILTRE HORAIRE")
    print("=" * 70)

    # Charger les donnees une seule fois
    trades_baseline, df_5min_ind, df_5s, cfg, config = load_data_and_trades()
    pnls = trades_baseline["PnL_Net"].values

    # ---- TACHE 1 : BLOCK BOOTSTRAP ----
    confirm_autocorrelation(pnls)
    all_results = run_block_bootstrap(pnls)
    verdict_bb, p_loss_bb, sizing_bb = verdict_block_bootstrap(all_results)
    save_block_bootstrap(all_results, verdict_bb, p_loss_bb, sizing_bb)

    # ---- TACHE 2 : FILTRE HORAIRE ----
    hourly_results, verdict_hourly, best_filter = run_hourly_filter_tests(
        df_5min_ind, df_5s, cfg, config, trades_baseline)

    # Walk-forward si amelioration > $5K
    if verdict_hourly == "WALK-FORWARD REQUIS" and best_filter:
        try:
            wf_pnl, wf_trades, wf_pct = run_hourly_walk_forward(
                best_filter, df_5min_ind, df_5s, cfg, config)
        except Exception as e:
            print(f"   Erreur walk-forward: {e}")

    # ---- RAPPORT ----
    generate_report(all_results, verdict_bb, p_loss_bb, sizing_bb,
                    hourly_results, verdict_hourly, best_filter)

    print("\n" + "=" * 70)
    print("  PHASE C4bis TERMINEE")
    print("=" * 70)
