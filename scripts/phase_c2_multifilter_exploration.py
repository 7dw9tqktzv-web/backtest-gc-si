# ============================================================================
# PHASE C2 MULTI-FILTRE -- 5 filtres de regime vs fenetres toxiques C1
# Exploratoire : tableaux console + correlations, aucune modification du backtest
# ============================================================================

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats as sp_stats
from statsmodels.tsa.stattools import adfuller

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import load_and_prepare_data, resample_to_5min
from indicators import calculate_all_indicators
from optimizer import apply_overrides_fast

OUTPUT_DIR = Path("output")
REPORT_DIR = Path("output/reports")

LOOKBACKS = [20, 40, 60]
TOXIC_WINDOWS = {"W02", "W04", "W05", "W08"}
N_WINDOWS = 15


# ============================================================================
# FILTRES
# ============================================================================

def realized_vol(spread, lookback):
    """Ecart-type rolling du spread."""
    return spread.rolling(lookback).std()


def rolling_adf(spread, lookback):
    """ADF statistic rolling. Plus negatif = plus stationnaire."""
    values = spread.values
    n = len(values)
    result = np.full(n, np.nan)
    for i in range(lookback, n):
        window = values[i - lookback:i]
        try:
            result[i] = adfuller(window, maxlag=1, regression="c", autolag=None)[0]
        except Exception:
            pass
    return pd.Series(result, index=spread.index)


def rolling_halflife(spread, lookback):
    """Half-life de mean-reversion via AR(1). Faible = retour rapide."""
    values = spread.values
    n = len(values)
    result = np.full(n, np.nan)
    for i in range(lookback, n):
        window = values[i - lookback:i]
        y = window[1:]
        x = window[:-1]
        var_x = np.var(x)
        if var_x < 1e-15:
            continue
        b = np.cov(x, y)[0, 1] / var_x
        if b <= 0 or b >= 1:
            continue
        result[i] = -np.log(2) / np.log(b)
    return pd.Series(result, index=spread.index)


def rolling_correlation(log_gc, log_si, lookback):
    """Correlation rolling entre log(GC) et log(SI)."""
    return log_gc.rolling(lookback).corr(log_si)


def rolling_slope(spread, lookback):
    """Pente de regression lineaire (drift du spread). |slope| eleve = trending."""
    values = spread.values
    n = len(values)
    result = np.full(n, np.nan)
    x = np.arange(lookback, dtype=np.float64)
    x_mean = x.mean()
    x_var = np.sum((x - x_mean) ** 2)
    for i in range(lookback, n):
        window = values[i - lookback:i]
        y_mean = np.mean(window)
        result[i] = np.sum((x - x_mean) * (window - y_mean)) / x_var
    return pd.Series(result, index=spread.index)


# ============================================================================
# CONSTRUCTION FENETRES C1
# ============================================================================

def build_windows_from_5min(df_5min):
    """Reconstruit les 15 fenetres C1 (meme logique que phase_c1_walkforward.py)."""
    total_bars = len(df_5min)
    window_size = total_bars // N_WINDOWS
    windows = []
    for i in range(N_WINDOWS):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size if i < N_WINDOWS - 1 else total_bars
        windows.append({
            "id": f"W{i+1:02d}",
            "start_dt": df_5min.iloc[start_idx]["DateTime"],
            "end_dt": df_5min.iloc[end_idx - 1]["DateTime"],
        })
    return windows


# ============================================================================
# MAIN
# ============================================================================

def main():
    t0 = time.time()
    print("=" * 70)
    print("PHASE C2 MULTI-FILTRE -- 5 filtres x 3 lookbacks vs fenetres toxiques")
    print("=" * 70)

    # 1. Charger donnees et spread daily
    print("\n[1/5] Chargement des donnees + spread daily (beta=2640)...")
    df_1min, base_config, _ = load_and_prepare_data()
    df_5min = resample_to_5min(df_1min)

    overrides = {
        "indicators.beta_lookback": 2640,
        "indicators.zscore_period": 24,
        "indicators.correlation_period": 24,
        "indicators.adf_hurst_period": 26,
        "indicators.period": "5min",
    }
    cfg = apply_overrides_fast(base_config, overrides)
    df_ind = calculate_all_indicators(df_5min.copy(), cfg, verbose=False)

    # Resampler en daily
    df_ind["_date"] = df_ind["DateTime"].dt.date
    df_daily = df_ind.groupby("_date").agg({
        "Spread": "last",
        "Log_GC": "last",
        "Log_SI": "last",
    })
    df_daily.index = pd.to_datetime(df_daily.index)
    print(f"  {len(df_daily)} jours de spread daily")

    # 2. Calculer les 5 filtres
    print("\n[2/5] Calcul des 5 filtres (3 lookbacks chacun)...")
    filters = {}  # {(name, lb): Series}

    for lb in LOOKBACKS:
        print(f"  Lookback {lb}j...", end=" ", flush=True)
        filters[("vol", lb)] = realized_vol(df_daily["Spread"], lb)
        filters[("adf", lb)] = rolling_adf(df_daily["Spread"], lb)
        filters[("halflife", lb)] = rolling_halflife(df_daily["Spread"], lb)
        filters[("corr", lb)] = rolling_correlation(df_daily["Log_GC"], df_daily["Log_SI"], lb)
        filters[("slope", lb)] = rolling_slope(df_daily["Spread"], lb)
        print("OK")

    # 3. Construire fenetres et PnL moyen
    print("\n[3/5] Alignement avec fenetres C1...")
    windows = build_windows_from_5min(df_5min)
    heatmap = pd.read_csv(OUTPUT_DIR / "phase_c1_heatmap.csv", sep=";", index_col=0)
    pnl_means = heatmap.mean(axis=0)

    filter_names = ["vol", "adf", "halflife", "corr", "slope"]
    filter_labels = {
        "vol": "Realized Vol",
        "adf": "Rolling ADF",
        "halflife": "Half-life",
        "corr": "Correlation GC/SI",
        "slope": "Spread Slope (|abs|)",
    }

    # Construire le grand tableau
    rows = []
    for w in windows:
        wid = w["id"]
        start = w["start_dt"]
        end = w["end_dt"]
        is_toxic = wid in TOXIC_WINDOWS
        row = {
            "window": wid,
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "pnl_mean": round(float(pnl_means.get(wid, 0)), 0),
            "is_toxic": int(is_toxic),
        }
        for fname in filter_names:
            for lb in LOOKBACKS:
                s = filters[(fname, lb)]
                mask = (s.index >= start) & (s.index <= end)
                vals = s[mask].dropna()
                if fname == "slope":
                    vals = vals.abs()  # |slope|
                if len(vals) > 0:
                    row[f"{fname}_{lb}"] = round(vals.mean(), 6)
                else:
                    row[f"{fname}_{lb}"] = np.nan
        rows.append(row)

    stats_df = pd.DataFrame(rows)
    stats_df.to_csv(OUTPUT_DIR / "phase_c2_multifilter_exploration.csv", sep=";", index=False)

    # 4. Affichage et correlations
    print("\n[4/5] Analyse par filtre...")

    spearman_results = []

    for fname in filter_names:
        label = filter_labels[fname]
        print(f"\n{'='*60}")
        print(f"  FILTRE : {label}")
        print(f"{'='*60}")

        # Tableau par fenetre
        print(f"  {'Fenetre':<6} {'Periode':<27} {'Type':<8}", end="")
        for lb in LOOKBACKS:
            print(f" {'lb='+str(lb):>10}", end="")
        print(f" {'PnL':>8}")
        print("  " + "-" * 80)

        for _, r in stats_df.iterrows():
            toxic_str = "TOXIQUE" if r["is_toxic"] else ""
            period = f"{r['start']} - {r['end'][:5]}"
            print(f"  {r['window']:<6} {period:<27} {toxic_str:<8}", end="")
            for lb in LOOKBACKS:
                v = r.get(f"{fname}_{lb}", np.nan)
                if pd.isna(v):
                    print(f" {'nan':>10}", end="")
                else:
                    print(f" {v:>10.4f}", end="")
            print(f" {r['pnl_mean']:>8,.0f}")

        # Moyennes toxiques vs saines
        toxic = stats_df[stats_df["is_toxic"] == 1]
        sain = stats_df[stats_df["is_toxic"] == 0]
        print(f"\n  {'Moyenne':>40}", end="")
        for lb in LOOKBACKS:
            col = f"{fname}_{lb}"
            t_mean = toxic[col].mean()
            s_mean = sain[col].mean()
            delta = t_mean - s_mean
            print(f"\n    TOXIQUES : lb={lb} -> {t_mean:.4f}")
            print(f"    SAINES   : lb={lb} -> {s_mean:.4f}")
            print(f"    DELTA    : lb={lb} -> {delta:+.4f}")

        # Spearman
        print(f"\n  Correlations Spearman (filtre vs PnL moyen) :")
        for lb in LOOKBACKS:
            col = f"{fname}_{lb}"
            valid = stats_df[[col, "pnl_mean"]].dropna()
            if len(valid) >= 5:
                sr, sp = sp_stats.spearmanr(valid[col], valid["pnl_mean"])
                sig = "*" if sp < 0.10 else ""
                print(f"    lb={lb}: r={sr:+.3f} (p={sp:.4f}){sig}")
                spearman_results.append({
                    "filter": label,
                    "lookback": lb,
                    "spearman_r": round(sr, 3),
                    "p_value": round(sp, 4),
                })

    # 5. Tableau recapitulatif
    print(f"\n{'='*70}")
    print("  RESUME : CORRELATIONS SPEARMAN (filtre vs PnL moyen par fenetre)")
    print(f"{'='*70}")
    print(f"  {'Filtre':<25}", end="")
    for lb in LOOKBACKS:
        print(f" {'lb='+str(lb):>12}", end="")
    print(f" {'Meilleur':>12} {'Verdict':>15}")
    print("  " + "-" * 85)

    spearman_df = pd.DataFrame(spearman_results)
    spearman_df.to_csv(OUTPUT_DIR / "phase_c2_spearman_correlations.csv", sep=";", index=False)

    best_filter = None
    best_abs_r = 0
    best_lb_global = None

    for fname in filter_names:
        label = filter_labels[fname]
        print(f"  {label:<25}", end="")
        best_r_this = 0
        best_lb_this = None
        for lb in LOOKBACKS:
            match = spearman_df[(spearman_df["filter"] == label) & (spearman_df["lookback"] == lb)]
            if len(match) > 0:
                r = match.iloc[0]["spearman_r"]
                p = match.iloc[0]["p_value"]
                sig = "*" if p < 0.10 else " "
                print(f" {r:>+10.3f}{sig}", end="")
                if abs(r) > abs(best_r_this):
                    best_r_this = r
                    best_lb_this = lb
            else:
                print(f" {'n/a':>12}", end="")

        # Verdict
        abs_r = abs(best_r_this)
        if abs_r >= 0.50:
            verdict = "PROMETTEUR"
        elif abs_r >= 0.30:
            verdict = "AMBIGU"
        else:
            verdict = "NON-DISCR."
        print(f" {'lb='+str(best_lb_this):>12} {verdict:>15}")

        if abs_r > best_abs_r:
            best_abs_r = abs_r
            best_filter = fname
            best_lb_global = best_lb_this

    print(f"\n  Meilleur filtre global : {filter_labels.get(best_filter, '?')} (lb={best_lb_global}, |r|={best_abs_r:.3f})")

    # --- POST-FILTER si au moins un filtre est prometteur ---
    if best_abs_r >= 0.40:
        print(f"\n{'='*70}")
        print(f"  POST-FILTER : {filter_labels[best_filter]} (lb={best_lb_global})")
        print(f"{'='*70}")
        run_post_filter(stats_df, best_filter, best_lb_global, heatmap, windows)
    else:
        print(f"\n  Aucun filtre suffisamment discriminant (|r| max = {best_abs_r:.3f}).")
        print("  Verdict global : NO-GO pour le filtrage de regime par indicateur unique.")

    # 6. Rapport
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = generate_report(stats_df, spearman_df, filter_names, filter_labels,
                              best_filter, best_lb_global, best_abs_r)
    report_path = REPORT_DIR / "PHASE_C2_RESULTS.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Rapport -> {report_path}")

    elapsed = time.time() - t0
    print(f"\nTermine en {elapsed:.0f}s")


# ============================================================================
# POST-FILTER
# ============================================================================

def run_post_filter(stats_df, best_filter, best_lb, heatmap, windows):
    """Applique le post-filter sur les trades C1."""
    col = f"{best_filter}_{best_lb}"

    # Determiner le seuil naturel
    toxic = stats_df[stats_df["is_toxic"] == 1][col]
    sain = stats_df[stats_df["is_toxic"] == 0][col]
    t_mean = toxic.mean()
    s_mean = sain.mean()
    midpoint = (t_mean + s_mean) / 2

    # 3 seuils autour du midpoint
    if best_filter == "adf":
        # ADF : plus negatif = meilleur. Bloquer si ADF > seuil (moins stationnaire)
        seuils = [round(midpoint + 0.3, 1), round(midpoint, 1), round(midpoint - 0.3, 1)]
        block_fn = lambda val, seuil: val > seuil
        direction = "Bloquer si ADF >"
    elif best_filter == "corr":
        # Correlation : plus haute = meilleur. Bloquer si corr < seuil
        seuils = [round(midpoint - 0.05, 2), round(midpoint, 2), round(midpoint + 0.05, 2)]
        block_fn = lambda val, seuil: val < seuil
        direction = "Bloquer si corr <"
    elif best_filter == "vol":
        # Vol : trop haute = danger. Bloquer si vol > seuil
        seuils = [round(midpoint * 0.8, 4), round(midpoint, 4), round(midpoint * 1.2, 4)]
        block_fn = lambda val, seuil: val > seuil
        direction = "Bloquer si vol >"
    elif best_filter == "halflife":
        # Half-life : trop long = danger. Bloquer si HL > seuil
        seuils = [round(midpoint * 0.8, 1), round(midpoint, 1), round(midpoint * 1.2, 1)]
        block_fn = lambda val, seuil: val > seuil
        direction = "Bloquer si HL >"
    else:  # slope
        # |Slope| : eleve = danger. Bloquer si |slope| > seuil
        seuils = [round(midpoint * 0.8, 5), round(midpoint, 5), round(midpoint * 1.2, 5)]
        block_fn = lambda val, seuil: val > seuil
        direction = "Bloquer si |slope| >"

    print(f"  Direction : {direction}")
    print(f"  Seuils testes : {seuils}")
    print(f"  Toxiques mean : {t_mean:.4f}")
    print(f"  Saines mean   : {s_mean:.4f}")

    # Pour chaque seuil, calculer l'impact
    print(f"\n  {'Seuil':>12} {'PnL avant':>12} {'PnL apres':>12} {'Delta%':>8} "
          f"{'FP bloq.':>10} {'Toxiq bloq.':>12}")
    print("  " + "-" * 70)

    best_results = None
    best_ratio = -999

    for seuil in seuils:
        # Determiner quelles fenetres sont bloquees
        blocked = set()
        for _, r in stats_df.iterrows():
            val = r[col]
            if pd.notna(val) and block_fn(val, seuil):
                blocked.add(r["window"])

        toxic_blocked = blocked & TOXIC_WINDOWS
        sain_blocked = blocked - TOXIC_WINDOWS

        # Recalculer PnL avec fenetres bloquees
        pnl_before = heatmap.sum(axis=1).mean()
        pnl_after_cols = [c for c in heatmap.columns if c not in blocked]
        pnl_after = heatmap[pnl_after_cols].sum(axis=1).mean() if pnl_after_cols else 0

        # Trades bloques (approximation via resultats C1)
        results_df = pd.read_csv(OUTPUT_DIR / "phase_c1_results.csv", sep=";")
        trades_before = results_df.groupby("label")["trades"].sum().mean()
        blocked_trades = results_df[results_df["window"].isin(blocked)].groupby("label")["trades"].sum().mean()
        trades_after = trades_before - blocked_trades

        delta_pct = (pnl_after - pnl_before) / abs(pnl_before) * 100 if pnl_before != 0 else 0

        # Ratio benefice/cout
        toxic_pnl_saved = heatmap[list(toxic_blocked)].sum(axis=1).mean() if toxic_blocked else 0
        sain_pnl_lost = heatmap[list(sain_blocked)].sum(axis=1).mean() if sain_blocked else 0
        ratio = abs(toxic_pnl_saved / sain_pnl_lost) if sain_pnl_lost != 0 else float("inf")

        print(f"  {seuil:>12.4f} {pnl_before:>12,.0f} {pnl_after:>12,.0f} {delta_pct:>+7.1f}% "
              f"{len(sain_blocked):>10} {len(toxic_blocked):>12}/{len(TOXIC_WINDOWS)}")

        if ratio > best_ratio:
            best_ratio = ratio
            best_results = {
                "seuil": seuil,
                "blocked": blocked,
                "toxic_blocked": toxic_blocked,
                "sain_blocked": sain_blocked,
                "pnl_before": pnl_before,
                "pnl_after": pnl_after,
                "ratio": ratio,
            }

    if best_results:
        print(f"\n  Meilleur seuil : {best_results['seuil']}")
        print(f"  Ratio benefice/cout : {best_results['ratio']:.2f}")

        # Exporter les resultats filtres
        blocked = best_results["blocked"]
        filtered_cols = [c for c in heatmap.columns if c not in blocked]
        filtered_pnl = heatmap[filtered_cols].sum(axis=1)
        filtered_df = pd.DataFrame({
            "label": filtered_pnl.index,
            "pnl_filtered": filtered_pnl.values,
            "pnl_original": heatmap.sum(axis=1).values,
            "windows_active": len(filtered_cols),
            "windows_blocked": len(blocked),
        })
        filtered_df.to_csv(OUTPUT_DIR / "phase_c2_filtered_results.csv", sep=";", index=False)
        print(f"  Exporte: phase_c2_filtered_results.csv")


# ============================================================================
# RAPPORT
# ============================================================================

def generate_report(stats_df, spearman_df, filter_names, filter_labels,
                     best_filter, best_lb, best_abs_r):
    """Genere le rapport Markdown."""
    lines = []
    lines.append("# Phase C2 -- Exploration Multi-Filtres de Regime\n")

    lines.append("## 1. Contexte\n")
    lines.append("- Rolling Hurst R/S = NO-GO (H toujours > 0.5, spread structurellement persistent)")
    lines.append("- Test de 5 filtres alternatifs sur spread daily, 3 lookbacks (20/40/60j)")
    lines.append("- Comparaison avec 15 fenetres C1 (4 toxiques, 11 saines)")
    lines.append("")

    lines.append("## 2. Correlations Spearman (filtre vs PnL moyen par fenetre)\n")
    lines.append("| Filtre | lb=20 | lb=40 | lb=60 | Verdict |")
    lines.append("|--------|-------|-------|-------|---------|")
    for fname in filter_names:
        label = filter_labels[fname]
        row_str = f"| {label} |"
        best_r = 0
        for lb in [20, 40, 60]:
            match = spearman_df[(spearman_df["filter"] == label) & (spearman_df["lookback"] == lb)]
            if len(match) > 0:
                r = match.iloc[0]["spearman_r"]
                p = match.iloc[0]["p_value"]
                sig = "*" if p < 0.10 else ""
                row_str += f" {r:+.3f}{sig} |"
                if abs(r) > abs(best_r):
                    best_r = r
            else:
                row_str += " n/a |"
        abs_r = abs(best_r)
        if abs_r >= 0.50:
            verdict = "PROMETTEUR"
        elif abs_r >= 0.30:
            verdict = "AMBIGU"
        else:
            verdict = "NON-DISCR."
        row_str += f" {verdict} |"
        lines.append(row_str)
    lines.append("")

    lines.append("## 3. Separation Toxiques vs Saines (moyennes par fenetre)\n")
    toxic = stats_df[stats_df["is_toxic"] == 1]
    sain = stats_df[stats_df["is_toxic"] == 0]
    lines.append("| Filtre | Lookback | Toxiques | Saines | Delta |")
    lines.append("|--------|----------|----------|--------|-------|")
    for fname in filter_names:
        label = filter_labels[fname]
        for lb in [20, 40, 60]:
            col = f"{fname}_{lb}"
            t = toxic[col].mean()
            s = sain[col].mean()
            d = t - s
            lines.append(f"| {label} | {lb}j | {t:.4f} | {s:.4f} | {d:+.4f} |")
    lines.append("")

    lines.append("## 4. Verdict\n")
    if best_abs_r >= 0.40:
        lines.append(f"- **Meilleur filtre** : {filter_labels.get(best_filter, '?')} (lb={best_lb}, |r|={best_abs_r:.3f})")
        lines.append("- Post-filter applique -- voir section 5")
    else:
        lines.append(f"- **Aucun filtre suffisamment discriminant** (meilleur |r| = {best_abs_r:.3f})")
        lines.append("- Le regime de marche dans les fenetres toxiques n'est pas capture par un seul indicateur")
        lines.append("- Options : combinaison multi-filtres, analyse des trades perdants, ou accepter le risque temporel")
    lines.append("")

    lines.append("## 5. Recommandations pour C3\n")
    if best_abs_r >= 0.40:
        lines.append(f"- Integrer {filter_labels.get(best_filter, '?')} comme filtre dans le backtest engine")
        lines.append("- Re-lancer C3 Walk-Forward eliminatoire avec le filtre")
    else:
        lines.append("- Pas de filtre single viable pour C3")
        lines.append("- Options : (1) combiner 2-3 filtres, (2) filtre horaire C+2, (3) accepter la cyclicite")
        lines.append("- La strategie reste profitable sur 3 ans malgre les fenetres toxiques")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
