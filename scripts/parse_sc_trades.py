#!/usr/bin/env python
# ============================================================================
# PARSE_SC_TRADES.PY - Import des trades depuis le Message Log Sierra Chart
# ============================================================================
#
# Parse les lignes ENTRY/EXIT du study "Spead GC/SI" dans le Message Log SC
# et produit un CSV compatible avec le format du backtest Python.
#
# Usage:
#   python scripts/parse_sc_trades.py <message_log.txt>
#   python scripts/parse_sc_trades.py <message_log.txt> --output trades_sc.csv
#   python scripts/parse_sc_trades.py <message_log.txt> --start 2026-02-01
#
# Format ENTRY attendu:
#   2026-02-10  13:17:50.506 | ... | ENTRY LONG: 3 GC(rc=3) @ 4637.20,
#     1 SI(rc=1) @ 84.6600, Z=-3.51 Beta=2.7498 NotGC=$463720 NotSI=$423300
#     Raw=2.51->3 sym=SIH26_FUT_CME
#
# Format EXIT attendu:
#   2026-02-10  13:17:53.509 | ... | EXIT TP_ZSCORE LONG: NetPnL=$3234
#     (gross=$3250 comm=$16) Z=1.01 GC=3(rc=3) SI=1(rc=1) bars=10
#
# Note: En replay, les timestamps sont le temps mur (accelere).
#       En paper trading live, les timestamps sont les vrais horaires.
# ============================================================================

import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pandas as pd


# Regex pour les lignes ENTRY du study
ENTRY_RE = re.compile(
    r"(?P<datetime>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\.\d+\s*\|.*"
    r"ENTRY\s+(?P<direction>LONG|SHORT):\s+"
    r"(?P<gc_qty>\d+)\s+GC\(rc=\d+\)\s+@\s+(?P<gc_price>[\d.]+),\s+"
    r"(?P<si_qty>\d+)\s+SI\(rc=\d+\)\s+@\s+(?P<si_price>[\d.]+),\s+"
    r"Z=(?P<zscore>[-\d.]+)\s+"
    r"Beta=(?P<beta>[\d.]+)"
)

# Regex pour les lignes EXIT du study
EXIT_RE = re.compile(
    r"(?P<datetime>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\.\d+\s*\|.*"
    r"EXIT\s+(?P<exit_reason>\S+)\s+(?P<direction>LONG|SHORT):\s+"
    r"NetPnL=\$(?P<pnl_net>[-\d]+)\s+"
    r"\(gross=\$(?P<pnl_gross>[-\d]+)\s+comm=\$(?P<commission>\d+)\)\s+"
    r"Z=(?P<zscore>[-\d.]+)\s+"
    r"GC=(?P<gc_qty>\d+)\(rc=\d+\)\s+"
    r"SI=(?P<si_qty>\d+)\(rc=\d+\)\s+"
    r"bars=(?P<bars>\d+)"
)


def parse_message_log(filepath):
    """Parse le Message Log SC et extrait les trades ENTRY/EXIT."""
    entries = []  # pile des entrees non fermees
    trades = []
    trade_no = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            # Chercher une ENTRY
            m = ENTRY_RE.search(line)
            if m:
                entries.append({
                    'datetime': m.group('datetime'),
                    'direction': m.group('direction'),
                    'gc_contracts': int(m.group('gc_qty')),
                    'si_contracts': int(m.group('si_qty')),
                    'gc_price': float(m.group('gc_price')),
                    'si_price': float(m.group('si_price')),
                    'zscore': float(m.group('zscore')),
                    'beta': float(m.group('beta')),
                })
                continue

            # Chercher un EXIT
            m = EXIT_RE.search(line)
            if m:
                exit_dir = m.group('direction')

                # Matcher avec la derniere ENTRY de meme direction
                entry = None
                for i in range(len(entries) - 1, -1, -1):
                    if entries[i]['direction'] == exit_dir:
                        entry = entries.pop(i)
                        break

                if entry is None:
                    print(f"[WARN] EXIT sans ENTRY correspondante: {line.strip()[:80]}")
                    continue

                trade_no += 1
                trades.append({
                    'Trade_No': trade_no,
                    'Direction': entry['direction'],
                    'Entry_DateTime': entry['datetime'],
                    'Exit_DateTime': m.group('datetime'),
                    'Entry_GC': entry['gc_price'],
                    'Entry_SI': entry['si_price'],
                    'Entry_ZScore': entry['zscore'],
                    'Exit_ZScore': float(m.group('zscore')),
                    'Exit_Reason': m.group('exit_reason'),
                    'Beta': entry['beta'],
                    'GC_Contracts': entry['gc_contracts'],
                    'SI_Contracts': entry['si_contracts'],
                    'PnL_Gross': float(m.group('pnl_gross')),
                    'Commission': float(m.group('commission')),
                    'PnL_Net': float(m.group('pnl_net')),
                    'Bars_Held': int(m.group('bars')),
                })

    if entries:
        print(f"[INFO] {len(entries)} position(s) encore ouverte(s) a la fin du log")

    return trades


def main():
    parser = argparse.ArgumentParser(description="Parse SC Message Log trades")
    parser.add_argument("logfile", help="Chemin vers le Message Log SC (.txt)")
    parser.add_argument("--output", default=None,
                        help="Fichier CSV de sortie (defaut: output/production/sc_trades.csv)")
    parser.add_argument("--start", default=None,
                        help="Filtrer les trades apres cette date (YYYY-MM-DD)")
    args = parser.parse_args()

    logpath = Path(args.logfile)
    if not logpath.exists():
        print(f"[ERREUR] Fichier introuvable: {logpath}")
        sys.exit(1)

    print(f"\n[...] Parsing {logpath.name}...")
    trades = parse_message_log(logpath)
    print(f"[OK] {len(trades)} trades extraits")

    if not trades:
        print("[INFO] Aucun trade trouve dans le log.")
        return

    df = pd.DataFrame(trades)

    # Filtre date
    if args.start:
        df['Entry_DateTime'] = pd.to_datetime(df['Entry_DateTime'])
        df = df[df['Entry_DateTime'] >= pd.Timestamp(args.start)]
        print(f"[OK] {len(df)} trades apres {args.start}")

    if len(df) > 0:
        df['PnL_Cumul'] = df['PnL_Net'].cumsum().round(2)

    # Sauvegarder
    outpath = Path(args.output) if args.output else Path("output/production/sc_trades.csv")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outpath, index=False, sep=';')
    print(f"[OK] {len(df)} trades -> {outpath}")

    # Afficher le resume
    print(f"\n{'='*70}")
    print(f"TRADES SIERRA CHART - {logpath.name}")
    print(f"{'='*70}")
    if len(df) > 0:
        print(f"Trades       : {len(df)}")
        winners = (df['PnL_Net'] > 0).sum()
        print(f"Win rate     : {winners}/{len(df)} ({winners/len(df)*100:.1f}%)")
        print(f"PnL net      : ${df['PnL_Net'].sum():+,.0f}")
        print(f"PnL brut     : ${df['PnL_Gross'].sum():+,.0f}")
        print(f"Commissions  : ${df['Commission'].sum():,.0f}")
        print()
        print(f"{'#':>3} {'Dir':>5} {'Entree':>16} {'Sortie':>16} "
              f"{'Exit':>10} {'GC':>3} {'PnL Net':>10} {'Cumul':>10}")
        print("-" * 85)
        for _, t in df.iterrows():
            entry_dt = str(t['Entry_DateTime'])[:16]
            exit_dt = str(t['Exit_DateTime'])[:16]
            print(f"{int(t['Trade_No']):3d} {t['Direction']:>5} {entry_dt:>16} "
                  f"{exit_dt:>16} {t['Exit_Reason']:>10} {int(t['GC_Contracts']):3d} "
                  f"${t['PnL_Net']:+9,.0f} ${t['PnL_Cumul']:+9,.0f}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
