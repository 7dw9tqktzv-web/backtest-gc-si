#!/usr/bin/env python
"""
Analyse des resultats filtres du grid search R1 : 12 profils de scoring.
Genere top 20 CSV par profil + summary avec chevauchement.

Usage:
    python scripts/score_r1_profiles.py
"""

import sys
import time
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

INPUT = Path("output/grid_searches/r1_corrected/r1_survivors.csv")
OUT_DIR = Path("output/grid_searches/r1_corrected/r1_profiles")

DISPLAY_COLS = [
    "label", "beta", "zp", "cp", "adf", "zE", "co", "zTP", "zSL",
    "dTP", "dSL", "mhb", "mm", "trades", "long", "short", "win_rate",
    "pnl_net", "pnl_avg", "profit_factor", "max_dd", "sharpe", "sortino",
    "calmar", "tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar",
    "max_hold", "end_session",
]


def profile_01_pnl(df):
    """PROFIL 1 -- PnL Brut"""
    return "PnL Brut", df.nlargest(20, "pnl_net"), len(df)


def profile_02_calmar(df):
    """PROFIL 2 -- Calmar"""
    sub = df[df["max_dd"] < 0].copy()
    sub["calmar"] = sub["pnl_net"] / sub["max_dd"].abs()
    return "Calmar", sub.nlargest(20, "calmar"), len(sub)


def profile_03_sharpe(df):
    """PROFIL 3 -- Sharpe"""
    return "Sharpe", df.nlargest(20, "sharpe"), len(df)


def profile_04_sortino(df):
    """PROFIL 4 -- Sortino"""
    return "Sortino", df.nlargest(20, "sortino"), len(df)


def profile_05_consistency(df):
    """PROFIL 5 -- Consistency"""
    sub = df.copy()
    sub["consistency"] = sub["win_rate"] * sub["profit_factor"]
    return "Consistency", sub.nlargest(20, "consistency"), len(sub)


def profile_06_fast_mean_reversion(df):
    """PROFIL 6 -- Fast Mean Reversion"""
    sub = df[(df["mhb"] > 0) & (df["mhb"] <= 12) & (df["dTP"] > 0)].copy()
    sub["ratio_tp_dollar"] = sub["tp_dollar"] / sub["trades"]
    sub = sub[sub["ratio_tp_dollar"] >= 0.3]
    return "Fast Mean Reversion", sub.nlargest(20, "pnl_net"), len(sub)


def profile_07_dollar_exit_dominant(df):
    """PROFIL 7 -- Dollar Exit Dominant"""
    sub = df.copy()
    sub["ratio_dollar"] = (sub["tp_dollar"] + sub["sl_dollar"]) / sub["trades"]
    sub = sub[sub["ratio_dollar"] >= 0.7]
    sub["calmar"] = np.where(
        sub["max_dd"] < 0,
        sub["pnl_net"] / sub["max_dd"].abs(),
        0.0,
    )
    return "Dollar Exit Dominant", sub.nlargest(20, "calmar"), len(sub)


def profile_08_pure_zscore(df):
    """PROFIL 8 -- Pure Zscore"""
    sub = df[(df["dTP"] == 0) & (df["dSL"] == 0)].copy()
    sub["calmar"] = np.where(
        sub["max_dd"] < 0,
        sub["pnl_net"] / sub["max_dd"].abs(),
        0.0,
    )
    return "Pure Zscore", sub.nlargest(20, "calmar"), len(sub)


def profile_09_low_drawdown(df):
    """PROFIL 9 -- Low Drawdown"""
    sub = df[df["max_dd"] >= -1500]
    return "Low Drawdown", sub.nlargest(20, "pnl_net"), len(sub)


def profile_10_balanced(df):
    """PROFIL 10 -- Balanced (rang moyen)"""
    sub = df.copy()
    sub["calmar_tmp"] = np.where(
        sub["max_dd"] < 0,
        sub["pnl_net"] / sub["max_dd"].abs(),
        0.0,
    )
    sub["consistency_tmp"] = sub["win_rate"] * sub["profit_factor"]
    sub["rank_pnl"] = sub["pnl_net"].rank(pct=True)
    sub["rank_calmar"] = sub["calmar_tmp"].rank(pct=True)
    sub["rank_sharpe"] = sub["sharpe"].rank(pct=True)
    sub["rank_consistency"] = sub["consistency_tmp"].rank(pct=True)
    sub["balanced"] = (
        sub["rank_pnl"] + sub["rank_calmar"]
        + sub["rank_sharpe"] + sub["rank_consistency"]
    ) / 4
    return "Balanced", sub.nlargest(20, "balanced"), len(sub)


def profile_11_profit_efficiency(df):
    """PROFIL 11 -- Profit Efficiency"""
    return "Profit Efficiency", df.nlargest(20, "pnl_avg"), len(df)


def profile_12_anti_fragile(df):
    """PROFIL 12 -- Anti-Fragile"""
    sub = df[
        (df["pnl_net"] > 0)
        & (df["win_rate"] >= 45)
        & (df["win_rate"] <= 55)
    ]
    return "Anti-Fragile", sub.nlargest(20, "profit_factor"), len(sub)


ALL_PROFILES = [
    (1, profile_01_pnl),
    (2, profile_02_calmar),
    (3, profile_03_sharpe),
    (4, profile_04_sortino),
    (5, profile_05_consistency),
    (6, profile_06_fast_mean_reversion),
    (7, profile_07_dollar_exit_dominant),
    (8, profile_08_pure_zscore),
    (9, profile_09_low_drawdown),
    (10, profile_10_balanced),
    (11, profile_11_profit_efficiency),
    (12, profile_12_anti_fragile),
]

PROFILE_NAMES = {
    1: "pnl_brut",
    2: "calmar",
    3: "sharpe",
    4: "sortino",
    5: "consistency",
    6: "fast_mean_reversion",
    7: "dollar_exit_dominant",
    8: "pure_zscore",
    9: "low_drawdown",
    10: "balanced",
    11: "profit_efficiency",
    12: "anti_fragile",
}


def format_top3_line(row):
    """Formate une ligne de config pour le summary."""
    cols = [c for c in DISPLAY_COLS if c in row.index]
    parts = []
    for c in cols:
        v = row[c]
        if isinstance(v, float):
            if c in ("pnl_net", "pnl_avg", "max_dd"):
                parts.append(f"{c}=${v:,.0f}")
            elif c in ("win_rate",):
                parts.append(f"{c}={v:.1f}%")
            elif c in ("sharpe", "sortino", "calmar", "profit_factor"):
                parts.append(f"{c}={v:.3f}")
            else:
                parts.append(f"{c}={v}")
        else:
            parts.append(f"{c}={v}")
    return "  " + " | ".join(parts)


def main():
    if not INPUT.exists():
        print(f"[ERREUR] Fichier introuvable : {INPUT}")
        sys.exit(1)

    print(f"Chargement : {INPUT}")
    t0 = time.time()
    df = pd.read_csv(INPUT, sep=";")
    print(f"  {len(df):,} survivants charges ({time.time()-t0:.1f}s)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Recalculer calmar si absent ou 0
    if "calmar" not in df.columns:
        df["calmar"] = np.where(
            df["max_dd"] < 0,
            df["pnl_net"] / df["max_dd"].abs(),
            0.0,
        )

    results = {}  # num -> (name, top20_df, n_eligible)
    all_top20_labels = {}  # num -> set of labels

    summary_lines = []
    summary_lines.append("=" * 120)
    summary_lines.append(f"GRID SEARCH R1 CORRIGE -- ANALYSE 12 PROFILS")
    summary_lines.append(f"Survivants charges : {len(df):,}")
    summary_lines.append("=" * 120)

    for num, func in ALL_PROFILES:
        name, top20, n_eligible = func(df)
        fname = PROFILE_NAMES[num]

        # Sauvegarder CSV
        out_cols = [c for c in DISPLAY_COLS if c in top20.columns]
        # Ajouter les colonnes calculees si presentes
        extra = [c for c in top20.columns if c not in DISPLAY_COLS]
        top20_out = top20[out_cols + extra]
        csv_path = OUT_DIR / f"profile_{num:02d}_{fname}.csv"
        top20_out.to_csv(csv_path, index=False, sep=";")

        results[num] = (name, top20, n_eligible)
        labels = set(top20["label"].values) if len(top20) > 0 else set()
        all_top20_labels[num] = labels

        # Summary
        summary_lines.append("")
        summary_lines.append(f"PROFIL {num:>2} -- {name}")
        summary_lines.append(f"  Configs eligibles : {n_eligible:,}")
        summary_lines.append(f"  Top 3 :")

        for rank, (_, row) in enumerate(top20.head(3).iterrows()):
            summary_lines.append(f"  #{rank+1}")
            summary_lines.append(format_top3_line(row))

        print(f"  Profil {num:>2} {name:<25} : {n_eligible:>10,} eligibles, "
              f"{len(top20):>2} top configs -> {csv_path.name}")

    # Matrice de chevauchement
    summary_lines.append("")
    summary_lines.append("=" * 120)
    summary_lines.append("MATRICE DE CHEVAUCHEMENT")
    summary_lines.append("=" * 120)

    # Compter dans combien de profils chaque config apparait
    label_counts = Counter()
    for num, labels in all_top20_labels.items():
        for lbl in labels:
            label_counts[lbl] += 1

    # Distribution
    dist = Counter(label_counts.values())
    for n_profiles in sorted(dist.keys()):
        summary_lines.append(
            f"  Configs dans {n_profiles} profil(s) : {dist[n_profiles]}"
        )

    # Configs dans 4+ profils
    robust = {lbl: cnt for lbl, cnt in label_counts.items() if cnt >= 4}
    summary_lines.append("")
    summary_lines.append(f"CONFIGS ROBUSTES (4+ profils) : {len(robust)}")
    summary_lines.append("-" * 120)

    if robust:
        for lbl, cnt in sorted(robust.items(), key=lambda x: -x[1]):
            row = df[df["label"] == lbl].iloc[0]
            profiles_in = [
                f"P{num}" for num, labels in all_top20_labels.items()
                if lbl in labels
            ]
            summary_lines.append(
                f"  [{cnt} profils: {', '.join(profiles_in)}]"
            )
            summary_lines.append(format_top3_line(row))
            summary_lines.append("")
    else:
        summary_lines.append("  Aucune config dans 4+ profils.")

    # Ecrire le summary
    summary_path = OUT_DIR / "summary.txt"
    summary_text = "\n".join(summary_lines) + "\n"
    summary_path.write_text(summary_text, encoding="utf-8")

    t_total = time.time() - t0
    print(f"\nTermine en {t_total:.1f}s")
    print(f"Summary : {summary_path}")
    print(f"CSVs    : {OUT_DIR}/profile_*.csv")

    # Afficher le summary
    print()
    print(summary_text)


if __name__ == "__main__":
    main()
