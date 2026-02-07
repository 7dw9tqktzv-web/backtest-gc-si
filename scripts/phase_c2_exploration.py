# ============================================================================
# PHASE C2 EXPLORATION -- Rolling Hurst du Spread vs Fenetres Toxiques C1
# Exploratoire : graphiques + correlations, aucune modification du backtest
# ============================================================================

import sys
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import load_and_prepare_data, resample_to_5min
from indicators import calculate_all_indicators
from optimizer import apply_overrides_fast

OUTPUT_DIR = Path("output")
REPORT_DIR = Path("output/reports")

# Lookbacks en jours pour le Rolling Hurst
HURST_LOOKBACKS = [20, 40, 60]

# Fenetres toxiques C1
TOXIC_WINDOWS = {"W02", "W04", "W05", "W08"}


# ============================================================================
# ROLLING HURST (R/S method, multi-scale)
# ============================================================================

def rolling_hurst_daily(spread_daily, lookback):
    """
    Calcule le Rolling Hurst Exponent sur des donnees daily.
    Methode R/S avec sous-periodes [8, 16, 32, ...] <= lookback.
    """
    values = spread_daily.values.astype(np.float64)
    n = len(values)
    result = np.full(n, np.nan)

    sub_periods = np.array([p for p in [8, 16, 32, 64, 128] if p <= lookback])
    if len(sub_periods) < 2:
        return pd.Series(result, index=spread_daily.index)

    log_n = np.log(sub_periods)

    for i in range(lookback, n):
        window = values[i - lookback:i]
        log_rs_vals = []
        log_n_vals = []

        for sp in sub_periods:
            if sp > lookback:
                continue
            # R/S pour cette sous-periode (sur la fin de la fenetre)
            seg = window[-sp:]
            mean_seg = np.mean(seg)
            std_seg = np.std(seg, ddof=0)
            if std_seg < 1e-10:
                continue
            deviations = seg - mean_seg
            cum_dev = np.cumsum(deviations)
            R = np.max(cum_dev) - np.min(cum_dev)
            if R < 1e-10:
                continue
            rs = R / std_seg
            log_rs_vals.append(np.log(rs))
            log_n_vals.append(np.log(sp))

        if len(log_rs_vals) >= 2:
            slope, _, _, _, _ = stats.linregress(log_n_vals, log_rs_vals)
            result[i] = np.clip(slope, 0.01, 0.99)

    return pd.Series(result, index=spread_daily.index)


# ============================================================================
# CONSTRUCTION DES FENETRES C1 (meme logique que phase_c1_walkforward.py)
# ============================================================================

def build_windows_from_5min(df_5min, n_windows=15):
    """Construit les fenetres C1 et retourne les dates."""
    total_bars = len(df_5min)
    window_size = total_bars // n_windows
    windows = []
    for i in range(n_windows):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size if i < n_windows - 1 else total_bars
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
    print("PHASE C2 EXPLORATION -- Rolling Hurst vs Fenetres Toxiques")
    print("=" * 70)

    # 1. Charger les donnees
    print("\n[1/6] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data()
    df_5min = resample_to_5min(df_1min)
    print(f"  df_5min : {len(df_5min):,} barres")

    # 2. Calculer le spread pour beta=2640 et beta=5280
    print("\n[2/6] Calcul du spread pour beta=2640 et beta=5280...")
    spreads_daily = {}
    for beta in [2640, 5280]:
        overrides = {
            "indicators.beta_lookback": beta,
            "indicators.zscore_period": 24,
            "indicators.correlation_period": 24,
            "indicators.adf_hurst_period": 26,
            "indicators.period": "5min",
        }
        cfg = apply_overrides_fast(base_config, overrides)
        df_ind = calculate_all_indicators(df_5min.copy(), cfg, verbose=False)

        # Resampler le spread en daily (dernier close de chaque jour)
        spread_5min = df_ind.set_index("DateTime")["Spread"]
        spread_daily = spread_5min.resample("D").last().dropna()
        spreads_daily[beta] = spread_daily
        print(f"  beta={beta}: {len(spread_daily)} jours de spread")

    # On utilise beta=2640 comme reference principale
    spread_ref = spreads_daily[2640]

    # 3. Rolling Hurst pour 3 lookbacks
    print("\n[3/6] Calcul Rolling Hurst (3 lookbacks)...")
    hurst_series = {}
    for lb in HURST_LOOKBACKS:
        h = rolling_hurst_daily(spread_ref, lb)
        hurst_series[lb] = h
        valid = h.dropna()
        print(f"  Lookback {lb}j: {len(valid)} valeurs, mean={valid.mean():.3f}, std={valid.std():.3f}")

    # Aussi pour beta=5280
    hurst_5280 = {}
    for lb in HURST_LOOKBACKS:
        hurst_5280[lb] = rolling_hurst_daily(spreads_daily[5280], lb)

    # 4. Construire fenetres C1 et aligner
    print("\n[4/6] Alignement avec fenetres C1...")
    windows = build_windows_from_5min(df_5min)

    # Charger PnL moyen par fenetre depuis le heatmap
    heatmap = pd.read_csv(OUTPUT_DIR / "phase_c1_heatmap.csv", sep=";", index_col=0)
    pnl_means = heatmap.mean(axis=0)

    # Calculer Hurst moyen et % trending par fenetre
    window_stats = []
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

        for lb in HURST_LOOKBACKS:
            h = hurst_series[lb]
            mask = (h.index >= start) & (h.index <= end)
            h_window = h[mask].dropna()
            if len(h_window) > 0:
                row[f"hurst_mean_{lb}"] = round(h_window.mean(), 4)
                row[f"hurst_pct_trending_{lb}"] = round((h_window > 0.5).mean() * 100, 1)
            else:
                row[f"hurst_mean_{lb}"] = np.nan
                row[f"hurst_pct_trending_{lb}"] = np.nan

        window_stats.append(row)

    stats_df = pd.DataFrame(window_stats)
    stats_df.to_csv(OUTPUT_DIR / "phase_c2_hurst_vs_windows.csv", sep=";", index=False)
    print(f"  Exporte: phase_c2_hurst_vs_windows.csv")

    # Afficher le tableau
    print(f"\n  {'Window':<6} {'PnL':>8} {'Toxic':>6}", end="")
    for lb in HURST_LOOKBACKS:
        print(f"  {'H_'+str(lb):>6} {'%T_'+str(lb):>6}", end="")
    print()
    print("  " + "-" * 70)
    for _, r in stats_df.iterrows():
        toxic_str = "YES" if r["is_toxic"] else ""
        print(f"  {r['window']:<6} {r['pnl_mean']:>8,.0f} {toxic_str:>6}", end="")
        for lb in HURST_LOOKBACKS:
            hm = r.get(f"hurst_mean_{lb}", np.nan)
            pt = r.get(f"hurst_pct_trending_{lb}", np.nan)
            print(f"  {hm:>6.3f} {pt:>5.1f}%", end="")
        print()

    # 5. Correlations
    print("\n[5/6] Correlations Hurst vs PnL...")
    print(f"\n  {'Lookback':>10} {'Pearson r':>10} {'p-value':>10} {'Spearman r':>10} {'p-value':>10}")
    print("  " + "-" * 55)

    best_lb = None
    best_spearman = 0

    for lb in HURST_LOOKBACKS:
        col = f"hurst_mean_{lb}"
        valid = stats_df[[col, "pnl_mean"]].dropna()
        if len(valid) < 5:
            continue
        pr, pp = stats.pearsonr(valid[col], valid["pnl_mean"])
        sr, sp = stats.spearmanr(valid[col], valid["pnl_mean"])
        print(f"  {lb:>8}j {pr:>10.3f} {pp:>10.4f} {sr:>10.3f} {sp:>10.4f}")
        if abs(sr) > abs(best_spearman):
            best_spearman = sr
            best_lb = lb

    print(f"\n  Meilleur lookback: {best_lb}j (Spearman r={best_spearman:.3f})")

    # Toxique vs Sain
    toxic_rows = stats_df[stats_df["is_toxic"] == 1]
    sain_rows = stats_df[stats_df["is_toxic"] == 0]
    # Fenetres tres saines (W14, W15)
    best_rows = stats_df[stats_df["window"].isin(["W14", "W15"])]

    print(f"\n  Hurst moyen par categorie (lookback {best_lb}j) :")
    col = f"hurst_mean_{best_lb}"
    col_pct = f"hurst_pct_trending_{best_lb}"
    print(f"    Toxiques (W02/W04/W05/W08): H={toxic_rows[col].mean():.3f}, %trending={toxic_rows[col_pct].mean():.1f}%")
    print(f"    Saines (reste):              H={sain_rows[col].mean():.3f}, %trending={sain_rows[col_pct].mean():.1f}%")
    print(f"    Meilleures (W14/W15):        H={best_rows[col].mean():.3f}, %trending={best_rows[col_pct].mean():.1f}%")

    # 6. Graphiques
    print("\n[6/6] Generation des graphiques...")

    # --- Graphique 1 : 3 subplots empiles ---
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True,
                              gridspec_kw={"height_ratios": [1, 1.2, 0.8]})

    # Zones toxiques
    for ax in axes:
        for w in windows:
            if w["id"] in TOXIC_WINDOWS:
                ax.axvspan(w["start_dt"], w["end_dt"], alpha=0.15, color="red", zorder=0)

    # Subplot 1: Spread daily
    ax1 = axes[0]
    ax1.plot(spread_ref.index, spread_ref.values, color="steelblue", linewidth=0.7)
    ax1.set_ylabel("Spread GC/SI (beta=2640)")
    ax1.set_title("Phase C2 -- Rolling Hurst vs Fenetres Toxiques C1")
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Rolling Hurst
    ax2 = axes[1]
    colors = ["#2196F3", "#FF9800", "#4CAF50"]
    for lb, color in zip(HURST_LOOKBACKS, colors):
        h = hurst_series[lb].dropna()
        ax2.plot(h.index, h.values, color=color, linewidth=0.8, label=f"Hurst {lb}j", alpha=0.8)
    ax2.axhline(y=0.5, color="red", linestyle="--", linewidth=1.5, alpha=0.7, label="H=0.5")
    ax2.set_ylabel("Hurst Exponent")
    ax2.set_ylim(0.2, 0.85)
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # Subplot 3: PnL moyen par fenetre
    ax3 = axes[2]
    for w in windows:
        wid = w["id"]
        pnl = float(pnl_means.get(wid, 0))
        mid_date = w["start_dt"] + (w["end_dt"] - w["start_dt"]) / 2
        color = "red" if pnl < 0 else "green"
        ax3.bar(mid_date, pnl, width=50, color=color, alpha=0.7, edgecolor="black", linewidth=0.5)
        ax3.text(mid_date, pnl + (500 if pnl >= 0 else -500), wid, ha="center", va="bottom" if pnl >= 0 else "top", fontsize=7)
    ax3.axhline(y=0, color="black", linewidth=0.5)
    ax3.set_ylabel("PnL moyen ($)")
    ax3.set_xlabel("Date")
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "phase_c2_hurst_analysis.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> phase_c2_hurst_analysis.png")

    # --- Graphique 2 : Scatter Hurst vs PnL ---
    fig2, ax_s = plt.subplots(figsize=(10, 7))
    col = f"hurst_mean_{best_lb}"

    for _, r in stats_df.iterrows():
        hm = r[col]
        pnl = r["pnl_mean"]
        if pd.isna(hm):
            continue
        if r["is_toxic"]:
            color = "red"
        elif r["window"] in ("W14", "W15"):
            color = "green"
        else:
            color = "gray"
        ax_s.scatter(hm, pnl, c=color, s=80, edgecolors="black", linewidth=0.5, zorder=5)
        ax_s.annotate(r["window"], (hm, pnl), textcoords="offset points",
                      xytext=(8, 5), fontsize=9)

    ax_s.axvline(x=0.5, color="red", linestyle="--", linewidth=1.5, alpha=0.5, label="H=0.5")
    ax_s.axhline(y=0, color="black", linestyle="-", linewidth=0.5, alpha=0.5)
    ax_s.set_xlabel(f"Hurst Exponent moyen (lookback {best_lb}j)")
    ax_s.set_ylabel("PnL moyen par fenetre ($)")
    ax_s.set_title(f"Phase C2 -- Scatter Hurst vs PnL (Spearman r={best_spearman:.3f})")
    ax_s.legend(loc="upper left")
    ax_s.grid(True, alpha=0.3)

    # Legende custom
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='Toxique'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, label='Saine (W14/W15)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=10, label='Neutre'),
    ]
    ax_s.legend(handles=legend_elements, loc="upper left")

    fig2.savefig(OUTPUT_DIR / "phase_c2_hurst_scatter.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  -> phase_c2_hurst_scatter.png")

    # 7. Rapport
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = generate_report(stats_df, hurst_series, best_lb, best_spearman,
                              toxic_rows, sain_rows, best_rows, HURST_LOOKBACKS)
    report_path = REPORT_DIR / "PHASE_C2_EXPLORATION_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  -> {report_path}")

    elapsed = time.time() - t0
    print(f"\nTermine en {elapsed:.0f}s")


def generate_report(stats_df, hurst_series, best_lb, best_spearman,
                     toxic_rows, sain_rows, best_rows, lookbacks):
    """Genere le rapport Markdown."""
    lines = []
    lines.append("# Phase C2 -- Exploration Rolling Hurst vs Fenetres Toxiques\n")

    lines.append("## 1. Resume\n")
    lines.append("- **Objectif** : Tester si le Rolling Hurst du spread GC/SI predit les fenetres toxiques C1")
    lines.append("- **Methode** : R/S (Rescaled Range) sur spread daily, sous-periodes [8, 16, 32, 64]")
    lines.append("- **Lookbacks testes** : 20j, 40j, 60j (donnees daily)")
    lines.append("- **Reference** : beta=2640 (champion B2)")
    lines.append("")

    lines.append("## 2. Statistiques Hurst globales\n")
    lines.append("| Lookback | Jours valides | Mean | Std | % < 0.5 | % > 0.5 |")
    lines.append("|----------|---------------|------|-----|---------|---------|")
    for lb in lookbacks:
        h = hurst_series[lb].dropna()
        pct_mr = (h < 0.5).mean() * 100
        pct_tr = (h > 0.5).mean() * 100
        lines.append(f"| {lb}j | {len(h)} | {h.mean():.3f} | {h.std():.3f} | {pct_mr:.1f}% | {pct_tr:.1f}% |")
    lines.append("")

    lines.append("## 3. Correlation Hurst vs PnL par fenetre\n")
    lines.append("| Lookback | Pearson r | p-value | Spearman r | p-value |")
    lines.append("|----------|-----------|---------|------------|---------|")
    for lb in lookbacks:
        col = f"hurst_mean_{lb}"
        valid = stats_df[[col, "pnl_mean"]].dropna()
        if len(valid) >= 5:
            pr, pp = stats.pearsonr(valid[col], valid["pnl_mean"])
            sr, sp = stats.spearmanr(valid[col], valid["pnl_mean"])
            lines.append(f"| {lb}j | {pr:.3f} | {pp:.4f} | {sr:.3f} | {sp:.4f} |")
    lines.append(f"\n**Meilleur lookback** : {best_lb}j (Spearman r={best_spearman:.3f})")
    lines.append("")

    lines.append("## 4. Toxique vs Sain\n")
    col = f"hurst_mean_{best_lb}"
    col_pct = f"hurst_pct_trending_{best_lb}"
    lines.append(f"| Categorie | N | Hurst moyen | % trending | PnL moyen |")
    lines.append(f"|-----------|---|-------------|------------|-----------|")
    lines.append(f"| Toxiques (W02/W04/W05/W08) | {len(toxic_rows)} | {toxic_rows[col].mean():.3f} | {toxic_rows[col_pct].mean():.1f}% | ${toxic_rows['pnl_mean'].mean():,.0f} |")
    lines.append(f"| Saines (reste) | {len(sain_rows)} | {sain_rows[col].mean():.3f} | {sain_rows[col_pct].mean():.1f}% | ${sain_rows['pnl_mean'].mean():,.0f} |")
    lines.append(f"| Meilleures (W14/W15) | {len(best_rows)} | {best_rows[col].mean():.3f} | {best_rows[col_pct].mean():.1f}% | ${best_rows['pnl_mean'].mean():,.0f} |")
    lines.append("")

    lines.append("## 5. Tableau complet\n")
    header = "| Fenetre | Dates | PnL | Toxic |"
    for lb in lookbacks:
        header += f" H_{lb} | %T_{lb} |"
    lines.append(header)
    sep = "|---------|-------|-----|-------|"
    for lb in lookbacks:
        sep += "------|-------|"
    lines.append(sep)

    for _, r in stats_df.iterrows():
        toxic_str = "YES" if r["is_toxic"] else ""
        line = f"| {r['window']} | {r['start']} - {r['end']} | ${r['pnl_mean']:,.0f} | {toxic_str} |"
        for lb in lookbacks:
            hm = r.get(f"hurst_mean_{lb}", np.nan)
            pt = r.get(f"hurst_pct_trending_{lb}", np.nan)
            line += f" {hm:.3f} | {pt:.1f}% |"
        lines.append(line)
    lines.append("")

    lines.append("## 6. Verdict\n")
    delta_h = toxic_rows[col].mean() - sain_rows[col].mean()
    if abs(best_spearman) >= 0.5:
        lines.append(f"- **Discriminant** : Spearman r={best_spearman:.3f} (significatif)")
    elif abs(best_spearman) >= 0.3:
        lines.append(f"- **Moderement discriminant** : Spearman r={best_spearman:.3f}")
    else:
        lines.append(f"- **Faiblement discriminant** : Spearman r={best_spearman:.3f}")
    lines.append(f"- Delta Hurst toxique-sain : {delta_h:+.3f}")
    lines.append(f"- Meilleur lookback : {best_lb}j")
    lines.append("")

    lines.append("## 7. Prochaines etapes\n")
    lines.append("- Si discriminant : integrer comme filtre dans le backtest engine (C2b)")
    lines.append("- Si insuffisant : tester Realized Vol du spread et/ou GVZ/VXSLV ratio")
    lines.append("- Le filtre doit etre calculable en daily pour Sierra Chart (check quotidien)")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
