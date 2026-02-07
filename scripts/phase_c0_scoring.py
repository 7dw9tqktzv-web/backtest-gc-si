"""
Phase C0 — Scoring & Pre-selection Prop Firm

Charge le CSV B2 (champion Phase B), applique des filtres qualite
orientes prop firm, score les survivantes, et produit un pool de
top 500 configs pour la Phase C1 (Walk-Forward diagnostique).

Usage:
    python scripts/phase_c0_scoring.py
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

# ============================================================================
# CONFIGURATION
# ============================================================================

CSV_PATH = Path("output/grid_search_B2_5min_zscore_1tick.csv")
OUTPUT_SCORED = Path("output/phase_c0_scored_configs.csv")
OUTPUT_TOP500 = Path("output/phase_c0_top500.csv")
OUTPUT_REPORT = Path("output/reports/PHASE_C0_SCORING_REPORT.md")

# Filtres qualite adaptes aux donnees B2 (3 ans, drawdowns structurels 2023)
# Note: MaxDD median = -$9.5K, Sharpe median = 0.08 sur 3 ans de backtest.
# Les seuils prop firm ($3K MaxDD, 0.5 Sharpe) s'appliquent au live mensuel,
# pas au backtest complet. On filtre ici sur la qualite relative.
FILTERS = [
    ("trades", ">=", 150),      # Significativite (~1 trade/5 jours sur 3 ans)
    ("pnl_net", ">", 0),        # Rentable
    ("profit_factor", ">", 1.3), # Qualite
    ("max_dd", ">", -15000),     # Exclut les pires drawdowns (> 1.5x median)
    ("pnl_avg", ">", 80),       # Viable apres slippage (median ~$116)
]

# Filtres relaxes (si < 50 survivantes)
RELAXED_FILTERS = [
    ("trades", ">=", 100),
    ("pnl_net", ">", 0),
    ("profit_factor", ">", 1.2),
    ("max_dd", ">", -18000),
    ("pnl_avg", ">", 50),
]

# Poids du scoring
SCORING_WEIGHTS = {
    "pnl_net": 0.10,
    "sortino": 0.25,
    "profit_factor": 0.25,
    "pnl_avg": 0.20,
    "calmar": 0.20,
}

N_SELECT = 500


# ============================================================================
# FONCTIONS
# ============================================================================

def apply_filters(df, filters):
    """Applique les filtres sequentiellement et retourne (df_filtered, funnel)."""
    funnel = [("Depart", len(df), 0)]
    current = df.copy()

    for col, op, val in filters:
        before = len(current)
        if op == ">=":
            current = current[current[col] >= val]
        elif op == ">":
            current = current[current[col] > val]
        elif op == "<=":
            current = current[current[col] <= val]
        elif op == "<":
            current = current[current[col] < val]
        eliminated = before - len(current)
        label = f"{col} {op} {val}"
        funnel.append((label, len(current), eliminated))

    return current, funnel


def print_funnel(funnel):
    """Affiche l'entonnoir de filtrage."""
    print(f"\n{'='*60}")
    print(f"ENTONNOIR DE FILTRAGE")
    print(f"{'='*60}")
    for label, count, elim in funnel:
        if elim == 0:
            print(f"  {label:30s} : {count:>6,}")
        else:
            print(f"  Apres {label:24s} : {count:>6,}  (-{elim:,})")
    print(f"{'='*60}")
    print(f"  Survivantes : {funnel[-1][1]:,} configs")
    print(f"{'='*60}")


def score_configs(df):
    """Score les configs avec normalisation min-max et poids."""
    scored = df.copy()

    # Traiter NaN/inf : clipper aux percentiles 1%-99%
    for col in SCORING_WEIGHTS:
        vals = scored[col].replace([np.inf, -np.inf], np.nan)
        p01 = vals.quantile(0.01)
        p99 = vals.quantile(0.99)
        median_val = vals.median()
        vals = vals.fillna(median_val)
        vals = vals.clip(p01, p99)
        scored[col] = vals

    # Normalisation min-max (0-1)
    for col in SCORING_WEIGHTS:
        vmin = scored[col].min()
        vmax = scored[col].max()
        if vmax > vmin:
            scored[f"{col}_norm"] = (scored[col] - vmin) / (vmax - vmin)
        else:
            scored[f"{col}_norm"] = 0.5

    # Score composite
    scored["score"] = sum(
        SCORING_WEIGHTS[col] * scored[f"{col}_norm"]
        for col in SCORING_WEIGHTS
    )

    # Trier par score decroissant
    scored = scored.sort_values("score", ascending=False).reset_index(drop=True)
    scored.index = scored.index + 1  # rank commence a 1
    scored.index.name = "rank"

    return scored


def print_top_n(df, n, title):
    """Affiche le top N configs."""
    print(f"\n{'='*120}")
    print(f"{title}")
    print(f"{'='*120}")
    cols = ["label", "trades", "pnl_net", "profit_factor", "sharpe",
            "sortino", "calmar", "pnl_avg", "max_dd", "win_rate", "score"]
    header = f"{'#':>4}  {'label':60s}  {'tr':>4}  {'PnL':>8}  {'PF':>5}  {'Sh':>5}  {'So':>6}  {'Ca':>5}  {'$/tr':>6}  {'MaxDD':>7}  {'WR%':>5}  {'Score':>5}"
    print(header)
    print("-" * 120)
    for rank, row in df.head(n).iterrows():
        print(f"{rank:>4}  {row['label']:60s}  {row['trades']:>4.0f}  {row['pnl_net']:>8,.0f}  {row['profit_factor']:>5.2f}  {row['sharpe']:>5.2f}  {row['sortino']:>6.3f}  {row['calmar']:>5.2f}  {row['pnl_avg']:>6.1f}  {row['max_dd']:>7,.0f}  {row['win_rate']:>5.1f}  {row['score']:>5.3f}")


def print_diversity(df, n, title):
    """Affiche la distribution des parametres dans le top N."""
    top = df.head(n)
    print(f"\n{'='*80}")
    print(f"DIVERSITE DES PARAMETRES — {title}")
    print(f"{'='*80}")
    params = ["beta", "zp", "cp", "adf", "zE", "co", "zTP", "zSL"]
    for p in params:
        if p in top.columns:
            counts = top[p].value_counts().sort_index()
            dist = "  ".join(f"{v}={c}" for v, c in counts.items())
            print(f"  {p:6s}: {dist}")


def print_clusters(df, n, title):
    """Analyse le clustering dans le top N."""
    top = df.head(n)
    clusters = top.groupby(["beta", "zp", "adf"]).size().sort_values(ascending=False)
    total = len(top)

    print(f"\n{'='*80}")
    print(f"CLUSTERS (beta, zp, adf) — {title}")
    print(f"{'='*80}")
    for i, ((beta, zp, adf), count) in enumerate(clusters.head(10).items()):
        pct = count / total * 100
        print(f"  {i+1:>2}. b{beta}_zp{zp}_adf{adf} : {count} configs ({pct:.1f}%)")

    if len(clusters) == 0:
        print("  (aucun cluster)")
        return

    # Alerte si > 50% dans le meme cluster
    top_cluster_pct = clusters.iloc[0] / total * 100
    if top_cluster_pct > 50:
        print(f"\n  *** ALERTE : {top_cluster_pct:.0f}% du pool dans un seul cluster ! Diversification forcee recommandee.")
    elif top_cluster_pct > 30:
        print(f"\n  ** ATTENTION : {top_cluster_pct:.0f}% du pool dans le top cluster. Surveiller.")
    else:
        print(f"\n  OK : cluster dominant = {top_cluster_pct:.1f}% — bonne diversite.")


def print_score_distribution(df):
    """Affiche la distribution des scores."""
    scores = df["score"]
    print(f"\n{'='*60}")
    print(f"DISTRIBUTION DES SCORES")
    print(f"{'='*60}")
    print(f"  Min    : {scores.min():.3f}")
    print(f"  Q25    : {scores.quantile(0.25):.3f}")
    print(f"  Median : {scores.median():.3f}")
    print(f"  Q75    : {scores.quantile(0.75):.3f}")
    print(f"  Max    : {scores.max():.3f}")
    if len(df) >= 50:
        print(f"  Ecart top1-top50  : {scores.iloc[0] - scores.iloc[49]:.3f}")
    if len(df) >= 500:
        print(f"  Ecart top1-top500 : {scores.iloc[0] - scores.iloc[499]:.3f}")


def generate_report(df_all, funnel, scored, filters_used, relaxed):
    """Genere le rapport Markdown."""
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    n_select = min(N_SELECT, len(scored))

    lines = []
    lines.append("# Phase C0 -- Scoring & Pre-selection Prop Firm")
    lines.append("")
    lines.append("## Resume")
    lines.append("")
    lines.append(f"- **Source** : B2 (5min zscore 1tick, champion Phase B)")
    lines.append(f"- **Depart** : {len(df_all):,} configs")
    lines.append(f"- **Survivantes** : {len(scored):,} configs apres filtrage")
    lines.append(f"- **Top selectionnees** : {n_select} pour Phase C1 Walk-Forward")
    if relaxed:
        lines.append(f"- **Filtres relaxes** : OUI (< 50 survivantes avec filtres stricts)")
    lines.append("")

    # Entonnoir
    lines.append("## Entonnoir de filtrage")
    lines.append("")
    lines.append("| Filtre | Restantes | Eliminees |")
    lines.append("|--------|-----------|-----------|")
    for label, count, elim in funnel:
        if elim == 0:
            lines.append(f"| {label} | {count:,} | - |")
        else:
            lines.append(f"| {label} | {count:,} | -{elim:,} |")
    lines.append("")

    # Scoring
    lines.append("## Formule de scoring")
    lines.append("")
    lines.append("Normalisation min-max (0-1) sur les survivantes, puis somme ponderee :")
    lines.append("")
    lines.append("| Metrique | Poids | Justification |")
    lines.append("|----------|-------|---------------|")
    lines.append("| Sortino | 0.25 | Penalise uniquement le downside risk |")
    lines.append("| Profit Factor | 0.25 | Qualite des trades |")
    lines.append("| $/trade | 0.20 | Robustesse au slippage reel |")
    lines.append("| Calmar | 0.20 | PnL/MaxDD -- protection du capital |")
    lines.append("| PnL Net | 0.10 | PnL absolu (reduit -- consistance > max PnL) |")
    lines.append("")
    lines.append("Sortino+Calmar = 45% : consistance et protection du capital priment.")
    lines.append("")

    # Top 20
    lines.append("## Top 20 configs")
    lines.append("")
    lines.append("| Rank | Label | Trades | PnL | PF | Sharpe | Sortino | Calmar | $/trade | MaxDD | WR% | Score |")
    lines.append("|------|-------|--------|-----|-----|--------|---------|--------|---------|-------|-----|-------|")
    for rank, row in scored.head(20).iterrows():
        lines.append(
            f"| {rank} | {row['label']} | {row['trades']:.0f} | ${row['pnl_net']:,.0f} | "
            f"{row['profit_factor']:.2f} | {row['sharpe']:.2f} | {row['sortino']:.3f} | "
            f"{row['calmar']:.2f} | ${row['pnl_avg']:.1f} | ${row['max_dd']:,.0f} | "
            f"{row['win_rate']:.1f}% | {row['score']:.3f} |"
        )
    lines.append("")

    # Diversite top 50
    lines.append("## Diversite des parametres (top 50)")
    lines.append("")
    top50 = scored.head(50)
    for p in ["beta", "zp", "cp", "adf", "zE", "co", "zTP", "zSL"]:
        if p in top50.columns:
            counts = top50[p].value_counts().sort_index()
            dist = ", ".join(f"{v}={c}" for v, c in counts.items())
            lines.append(f"- **{p}** : {dist}")
    lines.append("")

    # Clusters top 500
    lines.append(f"## Clusters (beta, zp, adf) -- top {n_select}")
    lines.append("")
    top_n = scored.head(n_select)
    clusters = top_n.groupby(["beta", "zp", "adf"]).size().sort_values(ascending=False)
    lines.append("| Cluster | Configs | % du pool |")
    lines.append("|---------|---------|-----------|")
    for (beta, zp, adf), count in clusters.head(10).items():
        pct = count / n_select * 100
        lines.append(f"| b{beta}_zp{zp}_adf{adf} | {count} | {pct:.1f}% |")
    lines.append("")

    top_pct = clusters.iloc[0] / n_select * 100
    if top_pct > 50:
        lines.append(f"**ALERTE** : {top_pct:.0f}% du pool dans un seul cluster. Diversification forcee recommandee.")
    elif top_pct > 30:
        lines.append(f"**ATTENTION** : {top_pct:.0f}% du pool dans le top cluster. A surveiller.")
    else:
        lines.append(f"Bonne diversite : cluster dominant = {top_pct:.1f}%.")
    lines.append("")

    # Score distribution
    lines.append("## Distribution des scores")
    lines.append("")
    scores = scored["score"]
    lines.append(f"- Min : {scores.min():.3f}")
    lines.append(f"- Q25 : {scores.quantile(0.25):.3f}")
    lines.append(f"- Median : {scores.median():.3f}")
    lines.append(f"- Q75 : {scores.quantile(0.75):.3f}")
    lines.append(f"- Max : {scores.max():.3f}")
    if len(scored) >= 50:
        lines.append(f"- Ecart top1-top50 : {scores.iloc[0] - scores.iloc[49]:.3f}")
    if len(scored) >= 500:
        lines.append(f"- Ecart top1-top500 : {scores.iloc[0] - scores.iloc[499]:.3f}")
    lines.append("")

    # Recommandation
    lines.append("## Recommandation")
    lines.append("")
    lines.append(f"Pool de {n_select} configs selectionne pour Phase C1 Walk-Forward diagnostique.")
    lines.append(f"Fichier : `output/phase_c0_top500.csv`")
    lines.append("")

    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] Rapport genere : {OUTPUT_REPORT}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    # Charger B2
    print(f"Chargement de {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, sep=";")
    print(f"B2 charge : {len(df):,} configs")

    # Filtres stricts
    filtered, funnel = apply_filters(df, FILTERS)
    print_funnel(funnel)

    relaxed = False
    if len(filtered) < 50:
        print(f"\n*** ALERTE : {len(filtered)} survivantes < 50 seuil minimum")
        print("*** Application des filtres relaxes...")
        filtered, funnel = apply_filters(df, RELAXED_FILTERS)
        print_funnel(funnel)
        relaxed = True

        if len(filtered) < 50:
            print(f"\n*** CRITIQUE : {len(filtered)} survivantes meme avec filtres relaxes")

    # Scoring
    scored = score_configs(filtered)

    # Affichage
    print_top_n(scored, 20, "TOP 20 PAR SCORE COMPOSITE")
    print_diversity(scored, 50, "TOP 50")
    print_diversity(scored, min(N_SELECT, len(scored)), f"TOP {min(N_SELECT, len(scored))}")
    print_clusters(scored, min(N_SELECT, len(scored)), f"TOP {min(N_SELECT, len(scored))}")
    print_score_distribution(scored)

    # Export
    scored.to_csv(OUTPUT_SCORED, sep=";", index=True, index_label="rank")
    print(f"\n[OK] Toutes survivantes : {OUTPUT_SCORED} ({len(scored):,} configs)")

    n_select = min(N_SELECT, len(scored))
    scored.head(n_select).to_csv(OUTPUT_TOP500, sep=";", index=True, index_label="rank")
    print(f"[OK] Top {n_select} : {OUTPUT_TOP500}")

    # Rapport
    generate_report(df, funnel, scored, FILTERS if not relaxed else RELAXED_FILTERS, relaxed)

    print(f"\n{'='*60}")
    print(f"PHASE C0 TERMINEE")
    print(f"  Source     : B2 (34,560 configs)")
    print(f"  Survivantes: {len(scored):,}")
    print(f"  Top select.: {n_select}")
    print(f"  Filtres    : {'RELAXES' if relaxed else 'STRICTS'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
