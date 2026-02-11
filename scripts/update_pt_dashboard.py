#!/usr/bin/env python
# ============================================================================
# UPDATE_PT_DASHBOARD.PY - Dashboard cumulatif paper trading
# ============================================================================
#
# Met a jour le dashboard Markdown avec les resultats de la derniere
# comparaison SC vs Python. Chaque execution ajoute une ligne au tableau.
#
# Usage:
#   python scripts/update_pt_dashboard.py
#   python scripts/update_pt_dashboard.py --sc sc_trades.csv --py pt_reference_trades.csv
#   python scripts/update_pt_dashboard.py --note "Premier export apres roll GCM26"
#
# Sortie:
#   output/production/PAPER_TRADING_DASHBOARD.md  (cree ou mis a jour)
# ============================================================================

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
import numpy as np

PRODUCTION_DIR = Path("output/production")
DASHBOARD_PATH = PRODUCTION_DIR / "PAPER_TRADING_DASHBOARD.md"
HISTORY_PATH = PRODUCTION_DIR / "pt_history.json"


def load_trades(filepath):
    """Charge un CSV de trades (sep=;). Retourne None si le fichier n'existe pas."""
    path = Path(filepath)
    if not path.exists():
        return None
    df = pd.read_csv(path, sep=';')
    return df if len(df) > 0 else None


def compute_snapshot(df_sc, df_py, tolerance_min=5):
    """Calcule les metriques d'un snapshot (une comparaison)."""
    from compare_sc_python import match_trades

    matched, sc_orphans, py_orphans = match_trades(df_sc, df_py, tolerance_min)
    total = len(matched) + len(sc_orphans) + len(py_orphans)

    # PnL
    sc_pnl = df_sc['PnL_Net'].sum() if len(df_sc) > 0 else 0
    py_pnl = df_py['PnL_Net'].sum() if len(df_py) > 0 else 0

    # Win rates
    sc_wr = (df_sc['PnL_Net'] > 0).sum() / len(df_sc) * 100 if len(df_sc) > 0 else 0
    py_wr = (df_py['PnL_Net'] > 0).sum() / len(df_py) * 100 if len(df_py) > 0 else 0

    # Exit reason match
    exit_match = 0
    pnl_deltas = []
    for m in matched:
        py = df_py.iloc[m['py_idx']]
        sc = df_sc.iloc[m['sc_idx']]
        if py.get('Exit_Reason', '') == sc.get('Exit_Reason', ''):
            exit_match += 1
        pnl_deltas.append(abs(sc['PnL_Net'] - py['PnL_Net']))

    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'trades_sc': len(df_sc),
        'trades_py': len(df_py),
        'matched': len(matched),
        'sc_orphans': len(sc_orphans),
        'py_orphans': len(py_orphans),
        'concordance': len(matched) / total * 100 if total > 0 else 0,
        'exit_match_pct': exit_match / len(matched) * 100 if matched else 0,
        'pnl_sc': sc_pnl,
        'pnl_py': py_pnl,
        'pnl_delta_median': float(np.median(pnl_deltas)) if pnl_deltas else 0,
        'wr_sc': sc_wr,
        'wr_py': py_wr,
    }


def load_history():
    """Charge l'historique des snapshots."""
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_history(history):
    """Sauvegarde l'historique."""
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def generate_dashboard(history, note=None):
    """Genere le Markdown du dashboard."""
    lines = []
    lines.append("# Paper Trading Dashboard")
    lines.append("")
    lines.append(f"*Derniere mise a jour: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    if not history:
        lines.append("Aucun snapshot enregistre. Lancer `python scripts/update_pt_dashboard.py`.")
        return "\n".join(lines)

    # Resume courant (dernier snapshot)
    last = history[-1]
    lines.append("## Status actuel")
    lines.append("")
    lines.append(f"| Metrique | Valeur |")
    lines.append(f"|----------|--------|")
    lines.append(f"| Trades SC | {last['trades_sc']} |")
    lines.append(f"| Trades Python | {last['trades_py']} |")
    lines.append(f"| Concordance | {last['concordance']:.0f}% ({last['matched']} matches) |")
    lines.append(f"| Exit reason match | {last['exit_match_pct']:.0f}% |")
    lines.append(f"| PnL SC | ${last['pnl_sc']:+,.0f} |")
    lines.append(f"| PnL Python | ${last['pnl_py']:+,.0f} |")
    lines.append(f"| Delta PnL median | ${last['pnl_delta_median']:,.0f} |")
    lines.append(f"| Win Rate SC / PY | {last['wr_sc']:.0f}% / {last['wr_py']:.0f}% |")
    lines.append("")

    # Criteres GO/NO-GO
    lines.append("## Criteres de validation (objectif 30+ trades)")
    lines.append("")
    trades_ok = last['trades_sc'] >= 30
    conc_ok = last['concordance'] >= 90
    exit_ok = last['exit_match_pct'] >= 85
    delta_ok = last['pnl_delta_median'] < 200

    def check(ok):
        return "PASS" if ok else "..."

    lines.append(f"| Critere | Objectif | Actuel | Status |")
    lines.append(f"|---------|----------|--------|--------|")
    lines.append(f"| Trades minimum | >= 30 | {last['trades_sc']} | {check(trades_ok)} |")
    lines.append(f"| Concordance | >= 90% | {last['concordance']:.0f}% | {check(conc_ok)} |")
    lines.append(f"| Exit reason match | >= 85% | {last['exit_match_pct']:.0f}% | {check(exit_ok)} |")
    lines.append(f"| Delta PnL median | < $200 | ${last['pnl_delta_median']:,.0f} | {check(delta_ok)} |")
    lines.append("")

    if all([trades_ok, conc_ok, exit_ok, delta_ok]):
        lines.append("**VERDICT: GO pour production**")
    elif last['trades_sc'] >= 30:
        lines.append("**VERDICT: NO-GO -criteres non atteints**")
    else:
        lines.append(f"**VERDICT: EN COURS -{last['trades_sc']}/30 trades**")
    lines.append("")

    # Historique
    lines.append("## Historique des snapshots")
    lines.append("")
    lines.append(f"| Date | SC | PY | Match | Conc. | Exit% | PnL SC | PnL PY | dPnL med | Note |")
    lines.append(f"|------|----|----|-------|-------|-------|--------|--------|----------|------|")
    for h in history:
        note_txt = h.get('note', '')
        lines.append(
            f"| {h['date']} "
            f"| {h['trades_sc']} "
            f"| {h['trades_py']} "
            f"| {h['matched']} "
            f"| {h['concordance']:.0f}% "
            f"| {h['exit_match_pct']:.0f}% "
            f"| ${h['pnl_sc']:+,.0f} "
            f"| ${h['pnl_py']:+,.0f} "
            f"| ${h['pnl_delta_median']:,.0f} "
            f"| {note_txt} |"
        )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Update paper trading dashboard")
    parser.add_argument("--sc", default=str(PRODUCTION_DIR / "sc_trades.csv"),
                        help="CSV trades SC")
    parser.add_argument("--py", default=str(PRODUCTION_DIR / "pt_reference_trades.csv"),
                        help="CSV trades Python")
    parser.add_argument("--tolerance", type=int, default=5,
                        help="Tolerance de match en minutes")
    parser.add_argument("--note", default="",
                        help="Note pour ce snapshot (ex: 'Semaine 1', 'Post-roll')")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("PAPER TRADING DASHBOARD - Mise a jour")
    print(f"{'='*60}\n")

    # Charger les trades
    df_sc = load_trades(args.sc)
    df_py = load_trades(args.py)

    if df_sc is None:
        print(f"[ERREUR] Pas de trades SC: {args.sc}")
        print("  Lancer d'abord: python scripts/parse_sc_trades.py <message_log.txt>")
        sys.exit(1)
    if df_py is None:
        print(f"[ERREUR] Pas de trades Python: {args.py}")
        print("  Lancer d'abord: python scripts/run_paper_trading_ref.py")
        sys.exit(1)

    print(f"[OK] SC: {len(df_sc)} trades")
    print(f"[OK] Python: {len(df_py)} trades")

    # Calculer le snapshot
    snapshot = compute_snapshot(df_sc, df_py, args.tolerance)
    snapshot['note'] = args.note
    print(f"[OK] Concordance: {snapshot['concordance']:.0f}% "
          f"({snapshot['matched']} matches)")

    # Ajouter a l'historique
    history = load_history()
    history.append(snapshot)
    save_history(history)
    print(f"[OK] Historique: {len(history)} snapshots")

    # Generer le dashboard
    dashboard = generate_dashboard(history)
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(dashboard)
    print(f"[OK] Dashboard -> {DASHBOARD_PATH}")

    # Afficher
    print(f"\n{dashboard}")


if __name__ == "__main__":
    main()
