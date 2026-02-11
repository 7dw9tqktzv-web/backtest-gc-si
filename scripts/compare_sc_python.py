#!/usr/bin/env python
# ============================================================================
# COMPARE_SC_PYTHON.PY - Comparateur trades Sierra Chart vs Python
# ============================================================================
#
# Matche les trades SC (Message Log) avec les trades Python (backtest)
# et produit un rapport de concordance detaille.
#
# Usage:
#   python scripts/compare_sc_python.py
#   python scripts/compare_sc_python.py --sc trades_sc.csv --py pt_reference_trades.csv
#   python scripts/compare_sc_python.py --tolerance 10
#
# Criteres de match : meme direction + entry datetime +/- tolerance minutes.
# ============================================================================

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pandas as pd
import numpy as np

PRODUCTION_DIR = Path("output/production")


def load_trades(filepath, source_name):
    """Charge un CSV de trades (sep=;)."""
    path = Path(filepath)
    if not path.exists():
        print(f"[ERREUR] {source_name}: fichier introuvable: {path}")
        sys.exit(1)
    df = pd.read_csv(path, sep=';')
    print(f"[OK] {source_name}: {len(df)} trades charges depuis {path.name}")
    return df


def match_trades(df_sc, df_py, tolerance_min=5):
    """Matche les trades SC vs Python par direction + datetime proximite.

    Retourne une liste de dicts avec les paires matchees et les orphelins.
    """
    sc_dt = pd.to_datetime(df_sc['Entry_DateTime'])
    py_dt = pd.to_datetime(df_py['Entry_DateTime'])

    matched = []
    sc_used = set()
    py_used = set()

    # Pour chaque trade Python, chercher le meilleur match SC
    for py_idx in range(len(df_py)):
        py_dir = df_py.iloc[py_idx]['Direction']
        py_time = py_dt.iloc[py_idx]
        best_sc_idx = None
        best_delta = pd.Timedelta(minutes=tolerance_min + 1)

        for sc_idx in range(len(df_sc)):
            if sc_idx in sc_used:
                continue
            if df_sc.iloc[sc_idx]['Direction'] != py_dir:
                continue
            delta = abs(sc_dt.iloc[sc_idx] - py_time)
            if delta <= pd.Timedelta(minutes=tolerance_min) and delta < best_delta:
                best_delta = delta
                best_sc_idx = sc_idx

        if best_sc_idx is not None:
            matched.append({
                'py_idx': py_idx,
                'sc_idx': best_sc_idx,
                'delta_min': best_delta.total_seconds() / 60,
            })
            sc_used.add(best_sc_idx)
            py_used.add(py_idx)

    # Orphelins
    sc_orphans = [i for i in range(len(df_sc)) if i not in sc_used]
    py_orphans = [i for i in range(len(df_py)) if i not in py_used]

    return matched, sc_orphans, py_orphans


def generate_comparison_report(df_sc, df_py, matched, sc_orphans, py_orphans, tolerance_min):
    """Genere le rapport de comparaison."""
    lines = []
    sep = "=" * 80
    lines.append(sep)
    lines.append("COMPARAISON SC vs PYTHON - Paper Trading")
    lines.append(sep)
    lines.append(f"Date generation  : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Tolerance match  : +/- {tolerance_min} min")
    lines.append(f"Trades SC        : {len(df_sc)}")
    lines.append(f"Trades Python    : {len(df_py)}")
    lines.append(f"Matches          : {len(matched)}")
    lines.append(f"SC orphelins     : {len(sc_orphans)} (SC only, pas de match Python)")
    lines.append(f"Python orphelins : {len(py_orphans)} (Python only, pas de match SC)")
    lines.append("")

    # Score de concordance
    total = len(matched) + len(sc_orphans) + len(py_orphans)
    if total > 0:
        score = len(matched) / total * 100
        lines.append(f"SCORE CONCORDANCE: {score:.0f}% ({len(matched)}/{total})")
    lines.append("")

    # Detail des matches
    if matched:
        lines.append(sep)
        lines.append("TRADES MATCHES")
        lines.append(sep)
        lines.append(f"{'#':>3} {'Dir':>5} {'Entry PY':>16} {'Entry SC':>16} "
                     f"{'Dt':>5} {'Z PY':>6} {'Z SC':>6} {'dZ':>6} "
                     f"{'PnL PY':>9} {'PnL SC':>9} {'dPnL':>9} {'Exit PY':>10} {'Exit SC':>10}")
        lines.append("-" * 120)

        pnl_deltas = []
        z_deltas = []
        exit_match_count = 0

        for i, m in enumerate(matched):
            py = df_py.iloc[m['py_idx']]
            sc = df_sc.iloc[m['sc_idx']]

            py_entry = str(py['Entry_DateTime'])[:16]
            sc_entry = str(sc['Entry_DateTime'])[:16]

            # Z-Score delta
            py_z = py.get('Entry_ZScore', np.nan)
            sc_z = sc.get('Entry_ZScore', np.nan)
            dz = sc_z - py_z if not (pd.isna(py_z) or pd.isna(sc_z)) else np.nan
            if not pd.isna(dz):
                z_deltas.append(abs(dz))

            # PnL delta
            py_pnl = py['PnL_Net']
            sc_pnl = sc['PnL_Net']
            dpnl = sc_pnl - py_pnl
            pnl_deltas.append(abs(dpnl))

            # Exit reason match
            py_exit = py.get('Exit_Reason', '?')
            sc_exit = sc.get('Exit_Reason', '?')
            if py_exit == sc_exit:
                exit_match_count += 1

            lines.append(
                f"{i+1:3d} {py['Direction']:>5} {py_entry:>16} {sc_entry:>16} "
                f"{m['delta_min']:4.1f}m "
                f"{py_z:6.2f} {sc_z:6.2f} {dz:+5.2f} "
                f"${py_pnl:+8,.0f} ${sc_pnl:+8,.0f} ${dpnl:+8,.0f} "
                f"{py_exit:>10} {sc_exit:>10}"
            )

        # Statistiques des matches
        lines.append("")
        lines.append("--- STATISTIQUES MATCHES ---")
        lines.append(f"Exit reason identique : {exit_match_count}/{len(matched)} "
                     f"({exit_match_count/len(matched)*100:.0f}%)")
        if z_deltas:
            lines.append(f"Delta Z-Score entry   : median {np.median(z_deltas):.3f}, "
                         f"max {np.max(z_deltas):.3f}")
        if pnl_deltas:
            lines.append(f"Delta PnL net         : median ${np.median(pnl_deltas):,.0f}, "
                         f"max ${np.max(pnl_deltas):,.0f}")
            lines.append(f"PnL total Python      : ${df_py.iloc[[m['py_idx'] for m in matched]]['PnL_Net'].sum():+,.0f}")
            lines.append(f"PnL total SC          : ${df_sc.iloc[[m['sc_idx'] for m in matched]]['PnL_Net'].sum():+,.0f}")

    # Orphelins SC
    if sc_orphans:
        lines.append("")
        lines.append(sep)
        lines.append(f"SC ORPHELINS ({len(sc_orphans)} trades) - presents dans SC, absents dans Python")
        lines.append(sep)
        for idx in sc_orphans:
            sc = df_sc.iloc[idx]
            entry_dt = str(sc['Entry_DateTime'])[:16]
            lines.append(f"  {sc['Direction']:>5} {entry_dt} | "
                         f"Z={sc.get('Entry_ZScore', '?')} | "
                         f"PnL=${sc['PnL_Net']:+,.0f} | {sc.get('Exit_Reason', '?')}")

    # Orphelins Python
    if py_orphans:
        lines.append("")
        lines.append(sep)
        lines.append(f"PYTHON ORPHELINS ({len(py_orphans)} trades) - presents dans Python, absents dans SC")
        lines.append(sep)
        for idx in py_orphans:
            py = df_py.iloc[idx]
            entry_dt = str(py['Entry_DateTime'])[:16]
            lines.append(f"  {py['Direction']:>5} {entry_dt} | "
                         f"Z={py.get('Entry_ZScore', '?')} | "
                         f"PnL=${py['PnL_Net']:+,.0f} | {py.get('Exit_Reason', '?')}")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare trades SC vs Python")
    parser.add_argument("--sc", default=str(PRODUCTION_DIR / "sc_trades.csv"),
                        help="CSV trades SC (defaut: output/production/sc_trades.csv)")
    parser.add_argument("--py", default=str(PRODUCTION_DIR / "pt_reference_trades.csv"),
                        help="CSV trades Python (defaut: output/production/pt_reference_trades.csv)")
    parser.add_argument("--tolerance", type=int, default=5,
                        help="Tolerance de match en minutes (defaut: 5)")
    parser.add_argument("--output", default=str(PRODUCTION_DIR / "pt_comparison_report.txt"),
                        help="Fichier rapport de sortie")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("COMPARAISON SC vs PYTHON")
    print(f"{'='*60}\n")

    df_sc = load_trades(args.sc, "SC")
    df_py = load_trades(args.py, "Python")

    # Matcher
    matched, sc_orphans, py_orphans = match_trades(df_sc, df_py, args.tolerance)

    print(f"\n[OK] {len(matched)} matches, {len(sc_orphans)} SC orphelins, "
          f"{len(py_orphans)} Python orphelins")

    # Rapport
    report = generate_comparison_report(df_sc, df_py, matched, sc_orphans, py_orphans, args.tolerance)

    outpath = Path(args.output)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"[OK] Rapport -> {outpath}")

    # Afficher
    print("\n" + report)


if __name__ == "__main__":
    main()
