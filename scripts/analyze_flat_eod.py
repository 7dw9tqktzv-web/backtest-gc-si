"""Analyse des trades proches du FLAT_EOD et temps necessaire."""
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

trades = []
with open('output/backtest_hybrid.csv', 'r') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        t = {
            'entry_dt': datetime.strptime(row['Entry_DateTime'], '%Y-%m-%d %H:%M:%S'),
            'exit_dt': datetime.strptime(row['Exit_DateTime'], '%Y-%m-%d %H:%M:%S'),
            'duration': float(row['Duration_Min']),
            'pnl': float(row['PnL_Net']),
            'exit_reason': row['Exit_Reason'],
            'dir': row['Direction'],
            'entry_z': float(row['Entry_ZScore']),
        }
        trades.append(t)

FLAT_EOD_CT = 14 * 60 + 55  # 14:55 en minutes depuis minuit

print("=" * 80)
print("  ANALYSE FLAT_EOD : FAUT-IL BLOQUER LES ENTREES TARDIVES ?")
print("=" * 80)

# 1. Stats de duree globales
durations = [t['duration'] for t in trades]
print(f"\n  DUREE DES TRADES (tous)")
print(f"  Moyenne: {np.mean(durations):.0f} min | Mediane: {np.median(durations):.0f} min")
print(f"  P25: {np.percentile(durations, 25):.0f} min | P75: {np.percentile(durations, 75):.0f} min")
print(f"  P90: {np.percentile(durations, 90):.0f} min | P95: {np.percentile(durations, 95):.0f} min")

# Par exit reason (hors FLAT_EOD)
print(f"\n  DUREE PAR EXIT REASON (hors FLAT_EOD)")
for reason in ['TP_DOLLAR', 'TP_ZSCORE', 'SL_DOLLAR']:
    durs = [t['duration'] for t in trades if t['exit_reason'] == reason]
    if durs:
        print(f"  {reason:<12}: Med={np.median(durs):>5.0f} min | P75={np.percentile(durs, 75):>5.0f} min | P95={np.percentile(durs, 95):>5.0f} min")

# 2. Trades FLAT_EOD
flat_trades = [t for t in trades if t['exit_reason'] == 'FLAT_EOD']
print(f"\n  TRADES FLAT_EOD: {len(flat_trades)} / {len(trades)} ({100*len(flat_trades)/len(trades):.1f}%)")
print(f"  PnL total FLAT_EOD: ${sum(t['pnl'] for t in flat_trades):,.0f}")
print(f"  PnL moyen FLAT_EOD: ${np.mean([t['pnl'] for t in flat_trades]):,.0f}")

print(f"\n  {'Entry Time':<20} {'Duration':>8} {'PnL':>8} {'Dir':>6} {'Z-Entry':>8}")
print("  " + "-" * 55)
for t in sorted(flat_trades, key=lambda x: x['pnl']):
    entry_time = t['entry_dt'].strftime('%Y-%m-%d %H:%M')
    print(f"  {entry_time:<20} {t['duration']:>6.0f}m  ${t['pnl']:>6,.0f}  {t['dir']:>6}  {t['entry_z']:>7.2f}")

# 3. Temps restant avant FLAT_EOD pour chaque trade
print(f"\n\n  SIMULATION : IMPACT DU FILTRE ENTRY CUTOFF")
print(f"  (bloquer les entrees si temps restant < cutoff avant 14:55 CT)")
print()

# Calculer temps restant pour chaque trade
for t in trades:
    entry_minutes = t['entry_dt'].hour * 60 + t['entry_dt'].minute
    # Gerer overnight (entries avant minuit)
    if entry_minutes >= 17 * 60:  # apres 17h = session du soir
        time_to_flat = (24 * 60 - entry_minutes) + FLAT_EOD_CT
    else:
        time_to_flat = FLAT_EOD_CT - entry_minutes
    t['time_to_flat'] = time_to_flat

# Tester differents cutoffs
print(f"  {'Cutoff':<12} {'Trades':>7} {'Bloques':>8} {'PnL':>10} {'PnL Bloque':>12} {'Avg Bloque':>11} {'WR':>6}")
print("  " + "-" * 75)

for cutoff in [0, 30, 45, 60, 75, 90, 105, 120, 150, 180, 210, 240]:
    kept = [t for t in trades if t['time_to_flat'] >= cutoff]
    blocked = [t for t in trades if t['time_to_flat'] < cutoff]
    pnl_kept = sum(t['pnl'] for t in kept)
    pnl_blocked = sum(t['pnl'] for t in blocked)
    avg_blocked = np.mean([t['pnl'] for t in blocked]) if blocked else 0
    wr_kept = 100 * sum(1 for t in kept if t['pnl'] > 0) / len(kept) if kept else 0

    cutoff_str = f"{cutoff}min" if cutoff > 0 else "Aucun"
    flag = ""
    if cutoff == 0:
        flag = " (baseline)"
    elif cutoff == int(np.median(durations)):
        flag = " << mediane"
    elif cutoff == int(np.mean(durations)):
        flag = " << moyenne"

    print(f"  {cutoff_str:<12} {len(kept):>5}    {len(blocked):>5}   ${pnl_kept:>8,.0f}   ${pnl_blocked:>10,.0f}   ${avg_blocked:>9,.0f}  {wr_kept:>5.1f}%{flag}")

# 4. Detail des trades bloques pour le cutoff optimal
print(f"\n\n  DETAIL : TRADES ENTRANT DANS LES 120 DERNIÈRES MINUTES AVANT 14:55")
late_trades = [t for t in trades if t['time_to_flat'] < 120]
late_trades.sort(key=lambda x: x['time_to_flat'])

if late_trades:
    print(f"  {len(late_trades)} trades concernes")
    print(f"  PnL total: ${sum(t['pnl'] for t in late_trades):,.0f}")
    print(f"  PnL moyen: ${np.mean([t['pnl'] for t in late_trades]):,.0f}")
    print()
    print(f"  {'Entry':<20} {'MinLeft':>8} {'Dur':>6} {'PnL':>8} {'Exit':>12}")
    print("  " + "-" * 60)
    for t in late_trades:
        entry_str = t['entry_dt'].strftime('%Y-%m-%d %H:%M')
        print(f"  {entry_str:<20} {t['time_to_flat']:>6}m  {t['duration']:>4.0f}m  ${t['pnl']:>6,.0f}  {t['exit_reason']:>12}")

# 5. Heure de cutoff equivalente
print(f"\n\n  CORRESPONDANCE CUTOFF -> HEURE ENTRY MAX")
for cutoff in [60, 75, 90, 105, 120, 150, 180]:
    max_entry_min = FLAT_EOD_CT - cutoff
    h = max_entry_min // 60
    m = max_entry_min % 60
    print(f"  Cutoff {cutoff:>3}min -> derniere entree a {h:02d}:{m:02d} CT")
