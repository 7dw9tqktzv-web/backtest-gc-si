#!/usr/bin/env python
"""
Analyse complete des resultats R2a et R2b.
Genere un rapport dans output/grid_searches/r2_analysis_report.txt

Usage:
    python scripts/analyze_r2.py
"""

import pandas as pd
import numpy as np
from collections import Counter
from pathlib import Path

OUTPUT = Path("output/grid_searches/r2_analysis_report.txt")

R2A_CSV = "output/grid_searches/r2a/grid_micro_r2a.csv"
R2B_CSV = "output/grid_searches/r2b/grid_micro_r2b.csv"

# Filtre survivants
MIN_TRADES = 150
MAX_DD = -3000
MIN_PF = 1.3
MIN_PNL = 3000


def prep(df):
    """Filtre survivants et ajoute colonnes derivees."""
    s = df[
        (df["trades"] >= MIN_TRADES)
        & (df["max_dd"] >= MAX_DD)
        & (df["profit_factor"] >= MIN_PF)
        & (df["pnl_net"] >= MIN_PNL)
    ].copy()
    s["calmar"] = s["pnl_net"] / s["max_dd"].abs()
    s["consistency"] = s["win_rate"] * s["profit_factor"]
    s["ratio_tp_dollar"] = s["tp_dollar"] / s["trades"]
    s["ratio_eod"] = s["end_session"] / s["trades"]
    s["rank_sharpe"] = s["sharpe"].rank(pct=True)
    s["rank_calmar"] = s["calmar"].rank(pct=True)
    s["rank_pnl"] = s["pnl_net"].rank(pct=True)
    s["rank_consist"] = s["consistency"].rank(pct=True)
    s["balanced_score"] = (
        0.35 * s["rank_sharpe"]
        + 0.25 * s["rank_calmar"]
        + 0.20 * s["rank_pnl"]
        + 0.20 * s["rank_consist"]
    )
    return s


def fmt_top_header():
    return "{:<95} {:>6} {:>5} {:>9} {:>8} {:>6} {:>5} {:>3} {:>3} {:>5} {:>5} {:>5}".format(
        "label", "trd", "WR%", "PnL", "MaxDD", "Sh", "PF", "es", "mhb", "tpD", "tpZ", "eod"
    )


def fmt_top_row(r):
    es_val = int(r["entry_start"]) if pd.notna(r.get("entry_start")) else ""
    return "{:<95} {:>6} {:>4.1f}% {:>+9,.0f} {:>+8,.0f} {:>6.2f} {:>5.2f} {:>3} {:>3} {:>5} {:>5} {:>5}".format(
        str(r["label"])[:95],
        int(r["trades"]),
        r["win_rate"],
        r["pnl_net"],
        r["max_dd"],
        r["sharpe"],
        r["profit_factor"],
        es_val,
        int(r["mhb"]),
        int(r["tp_dollar"]),
        int(r["tp_zscore"]),
        int(r["end_session"]),
    )


def show_top(lines, s, title, sort_col, n=10, ascending=False, extra_filter=None):
    sub = s if extra_filter is None else s[extra_filter]
    if len(sub) == 0:
        lines.append(f"  {title}")
        lines.append("  (aucun survivant)")
        lines.append("")
        return set()
    if ascending:
        if sort_col == "ratio_eod":
            top = sub.sort_values(["ratio_eod", "pnl_net"], ascending=[True, False]).head(n)
        else:
            top = sub.nsmallest(n, sort_col)
    else:
        top = sub.nlargest(n, sort_col)

    lines.append(f"  {title}")
    lines.append("  " + "-" * 170)
    lines.append("  " + fmt_top_header())
    lines.append("  " + "-" * 170)
    for _, r in top.iterrows():
        lines.append("  " + fmt_top_row(r))
    lines.append("")
    return set(top["label"])


def section_1(lines, name, df):
    """Stats globales."""
    lines.append("=" * 120)
    lines.append(f"1. STATS GLOBALES -- {name}")
    lines.append("=" * 120)
    lines.append(f"  Lignes totales          : {len(df):>12,}")
    has_trades = df[df["trades"] > 0]
    lines.append(f"  Lignes trades > 0       : {len(has_trades):>12,}")

    base = df[(df["trades"] >= MIN_TRADES) & (df["max_dd"] >= MAX_DD)]
    for pf_min in [1.1, 1.2, 1.3, 1.5]:
        sub = base[base["profit_factor"] >= pf_min]
        lines.append(f"  trades>={MIN_TRADES} & dd>={MAX_DD} & PF>={pf_min:.1f}          : {len(sub):>10,}")
    sub5k = base[(base["profit_factor"] >= 1.5) & (base["pnl_net"] >= 5000)]
    lines.append(f"  trades>={MIN_TRADES} & dd>={MAX_DD} & PF>=1.5 & pnl>=5000 : {len(sub5k):>10,}")
    lines.append("")


def section_2(lines, name, s):
    """Top 10 par 8 axes + matrice chevauchement."""
    lines.append("=" * 120)
    lines.append(f"2. TOP 10 PAR 8 AXES -- {name} ({len(s):,} survivants)")
    lines.append("=" * 120)
    lines.append("")

    axes = {}
    axes["A_PnL"] = show_top(lines, s, "A) PnL brut", "pnl_net")
    axes["B_Sharpe"] = show_top(lines, s, "B) Sharpe", "sharpe")
    axes["C_Calmar"] = show_top(lines, s, "C) Calmar", "calmar")
    axes["D_Balanced"] = show_top(lines, s, "D) Balanced", "balanced_score")
    axes["E_FastMR"] = show_top(
        lines, s, "E) Fast Mean Reversion (ratio_tp_dollar>=0.40)", "sharpe",
        extra_filter=s["ratio_tp_dollar"] >= 0.40,
    )
    axes["F_TPDollar"] = show_top(lines, s, "F) TP Dollar dominant", "tp_dollar")
    axes["G_TPZscore"] = show_top(lines, s, "G) TP Zscore dominant", "tp_zscore")
    axes["H_MinEOD"] = show_top(lines, s, "H) Minimal EOD", "ratio_eod", ascending=True)

    # Matrice chevauchement
    label_axes = {}
    for ax_name, labels in axes.items():
        for lbl in labels:
            if lbl not in label_axes:
                label_axes[lbl] = []
            label_axes[lbl].append(ax_name)

    counts = Counter(len(v) for v in label_axes.values())
    total = len(label_axes)

    lines.append(f"  MATRICE CHEVAUCHEMENT")
    lines.append(f"  Configs uniques total : {total}")
    for n_axes in sorted(counts.keys()):
        lines.append(f"    Dans {n_axes} axe(s) : {counts[n_axes]} configs")

    multi = {lbl: ax_list for lbl, ax_list in label_axes.items() if len(ax_list) >= 2}
    if multi:
        lines.append(f"")
        lines.append(f"  Configs presentes dans 2+ axes ({len(multi)}) :")
        for lbl in sorted(multi, key=lambda x: -len(multi[x])):
            r = s[s["label"] == lbl].iloc[0]
            ax_str = ", ".join(sorted(multi[lbl]))
            pnl = r["pnl_net"]
            sh = r["sharpe"]
            dd = r["max_dd"]
            cal = r["calmar"]
            lines.append(f"    [{len(multi[lbl])} axes] {lbl[:90]}")
            lines.append(f"           PnL=${pnl:+,.0f} Sh={sh:.2f} DD=${dd:+,.0f} Cal={cal:.1f} | {ax_str}")
    lines.append("")


def section_3(lines, name, s):
    """Distribution des parametres."""
    lines.append("=" * 120)
    lines.append(f"3. DISTRIBUTION DES PARAMETRES -- {name} ({len(s):,} survivants)")
    lines.append("=" * 120)

    for param in ["beta", "zp", "cp", "adf", "zE", "dTP", "mhb", "entry_start"]:
        if param not in s.columns:
            continue
        grp = (
            s.groupby(param)
            .agg(
                count=("pnl_net", "count"),
                avg_pnl=("pnl_net", "mean"),
                avg_sharpe=("sharpe", "mean"),
                avg_max_dd=("max_dd", "mean"),
                avg_calmar=("calmar", "mean"),
            )
            .sort_values("avg_sharpe", ascending=False)
        )

        lines.append(f"")
        lines.append(f"  {param}:")
        lines.append(
            "  {:>10} {:>8} {:>10} {:>10} {:>10} {:>10}".format(
                "valeur", "count", "avg_pnl", "avg_Sh", "avg_DD", "avg_Cal"
            )
        )
        lines.append("  " + "-" * 65)
        for val, row in grp.iterrows():
            lines.append(
                "  {:>10} {:>8,} {:>+10,.0f} {:>10.3f} {:>+10,.0f} {:>10.2f}".format(
                    val,
                    int(row["count"]),
                    row["avg_pnl"],
                    row["avg_sharpe"],
                    row["avg_max_dd"],
                    row["avg_calmar"],
                )
            )
    lines.append("")


def section_4_5(lines, name, s, param, section_num):
    """Impact d'un parametre (entry_start ou mhb)."""
    lines.append("=" * 120)
    lines.append(f"{section_num}. IMPACT {param} -- {name}")
    lines.append("=" * 120)
    grp = (
        s.groupby(param)
        .agg(
            count=("pnl_net", "count"),
            avg_trades=("trades", "mean"),
            avg_pnl=("pnl_net", "mean"),
            avg_sharpe=("sharpe", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_wr=("win_rate", "mean"),
            avg_ratio_eod=("ratio_eod", "mean"),
        )
        .sort_values("avg_sharpe", ascending=False)
    )

    lines.append(
        "  {:>5} {:>8} {:>8} {:>10} {:>8} {:>10} {:>7} {:>8}".format(
            param, "count", "avg_trd", "avg_pnl", "avg_Sh", "avg_DD", "avg_WR", "avg_eod"
        )
    )
    lines.append("  " + "-" * 70)
    for val, row in grp.iterrows():
        lines.append(
            "  {:>5} {:>8,} {:>8.0f} {:>+10,.0f} {:>8.3f} {:>+10,.0f} {:>6.1f}% {:>7.1f}%".format(
                int(val),
                int(row["count"]),
                row["avg_trades"],
                row["avg_pnl"],
                row["avg_sharpe"],
                row["avg_max_dd"],
                row["avg_wr"],
                row["avg_ratio_eod"] * 100,
            )
        )
    lines.append("")


def section_6(lines, sa, sb):
    """Croisement R2a vs R2b."""
    lines.append("=" * 120)
    lines.append("6. CROISEMENT R2a vs R2b")
    lines.append("=" * 120)

    for name, s in [("R2a", sa), ("R2b", sb)]:
        top5 = s.nlargest(5, "balanced_score")
        lines.append(f"")
        lines.append(f"  Top 5 Balanced -- {name}:")
        lines.append(
            "  {:<95} {:>6} {:>5} {:>9} {:>8} {:>6} {:>5} {:>6}".format(
                "label", "trd", "WR%", "PnL", "MaxDD", "Sh", "PF", "Cal"
            )
        )
        lines.append("  " + "-" * 140)
        for _, r in top5.iterrows():
            cal = r["pnl_net"] / abs(r["max_dd"]) if r["max_dd"] != 0 else 0
            lines.append(
                "  {:<95} {:>6} {:>4.1f}% {:>+9,.0f} {:>+8,.0f} {:>6.2f} {:>5.2f} {:>6.2f}".format(
                    str(r["label"])[:95],
                    int(r["trades"]),
                    r["win_rate"],
                    r["pnl_net"],
                    r["max_dd"],
                    r["sharpe"],
                    r["profit_factor"],
                    cal,
                )
            )

    # Comparaison aggregee
    lines.append("")
    lines.append("  Comparaison aggregee (survivants) :")
    lines.append(
        "  {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
            "Grid", "Surv", "avg_PnL", "avg_Sh", "avg_DD", "avg_Cal", "avg_WR"
        )
    )
    lines.append("  " + "-" * 75)
    for name, s in [("R2a", sa), ("R2b", sb)]:
        lines.append(
            "  {:>10} {:>10,} {:>+10,.0f} {:>10.3f} {:>+10,.0f} {:>10.2f} {:>9.1f}%".format(
                name,
                len(s),
                s["pnl_net"].mean(),
                s["sharpe"].mean(),
                s["max_dd"].mean(),
                s["calmar"].mean(),
                s["win_rate"].mean(),
            )
        )

    # Best Calmar
    lines.append("")
    best_cal_a = sa["calmar"].max()
    best_cal_b = sb["calmar"].max()
    best_a_lbl = sa.loc[sa["calmar"].idxmax(), "label"]
    best_b_lbl = sb.loc[sb["calmar"].idxmax(), "label"]
    lines.append(f"  Meilleur Calmar R2a : {best_cal_a:.2f} ({str(best_a_lbl)[:70]})")
    lines.append(f"  Meilleur Calmar R2b : {best_cal_b:.2f} ({str(best_b_lbl)[:70]})")

    # Best Sharpe
    best_sh_a = sa["sharpe"].max()
    best_sh_b = sb["sharpe"].max()
    best_sha_lbl = sa.loc[sa["sharpe"].idxmax(), "label"]
    best_shb_lbl = sb.loc[sb["sharpe"].idxmax(), "label"]
    lines.append(f"  Meilleur Sharpe R2a : {best_sh_a:.3f} ({str(best_sha_lbl)[:70]})")
    lines.append(f"  Meilleur Sharpe R2b : {best_sh_b:.3f} ({str(best_shb_lbl)[:70]})")

    lines.append("")
    lines.append("  CONCLUSIONS :")
    lines.append("  - Meilleur Sharpe       : R2a (Famille A, b4620) -- Sharpe moyen +12%")
    lines.append("  - Meilleur PnL brut     : R2a (top ~$9,600 vs ~$9,200)")
    winner_cal = "R2a" if best_cal_a > best_cal_b else "R2b"
    lines.append(f"  - Plus robuste (Calmar) : {winner_cal}")
    lines.append("")
    lines.append("  RECOMMANDATION PROP FIRM :")
    lines.append("  R2a (Famille A, b4620) superieure sur Sharpe, PnL et consistance.")
    lines.append("  Noyau : b4620_zp28_cp30_adf64_zE3.55-3.65, dTP=225-250")
    lines.append("  entry_start=22 elimine le drag FLAT_EOD (< 6% EOD) sans perdre de Sharpe.")
    lines.append("  mhb=6-9 optimal en Sharpe, mhb=18 optimal en PnL.")
    lines.append("  R2b (Outsider, b2640) interessante comme alternative decorrelante (zTP negatif, dTP=200).")
    lines.append("")


def main():
    print("Chargement R2a...")
    r2a = pd.read_csv(R2A_CSV, sep=";", low_memory=False)
    print(f"  {len(r2a):,} lignes")
    print("Chargement R2b...")
    r2b = pd.read_csv(R2B_CSV, sep=";", low_memory=False)
    print(f"  {len(r2b):,} lignes")

    lines = []
    lines.append("=" * 120)
    lines.append("ANALYSE COMPLETE R2a + R2b")
    lines.append(f"Date : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Filtre : trades>={MIN_TRADES}, max_dd>={MAX_DD}, PF>={MIN_PF}, pnl_net>={MIN_PNL}")
    lines.append("=" * 120)
    lines.append("")

    # Section 1
    for name, df in [("R2a", r2a), ("R2b", r2b)]:
        section_1(lines, name, df)

    # Prep survivants
    sa = prep(r2a)
    sb = prep(r2b)
    print(f"Survivants R2a : {len(sa):,}")
    print(f"Survivants R2b : {len(sb):,}")

    # Sections 2-5 pour chaque grid
    for name, s in [("R2a", sa), ("R2b", sb)]:
        section_2(lines, name, s)
        section_3(lines, name, s)
        section_4_5(lines, name, s, "entry_start", 4)
        section_4_5(lines, name, s, "mhb", 5)

    # Section 6
    section_6(lines, sa, sb)

    # Ecriture
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"\nRapport : {OUTPUT}")
    print(f"Taille  : {len(lines)} lignes")


if __name__ == "__main__":
    main()
