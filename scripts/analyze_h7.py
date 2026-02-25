"""Analyse des trades heure 7 CT - saisonnalite et sous-periodes."""
import csv
from datetime import datetime
from collections import defaultdict

trades = []
with open('output/backtest_hybrid.csv', 'r') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        trades.append(row)

h7 = [t for t in trades if datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S').hour == 7]
print(f'=== TRADES HEURE 7 CT (7:00-7:59) ===')
print(f'Total: {len(h7)} trades sur {len(trades)} ({100*len(h7)/len(trades):.0f}%)')
print()

monthly = defaultdict(int)
monthly_pnl = defaultdict(float)
for t in h7:
    dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
    monthly[dt.month] += 1
    monthly_pnl[dt.month] += float(t['PnL_Net'])

print(f'{"Mois":<6} {"Trades":>7} {"PnL":>10} {"Saison":>10}')
print('-' * 40)
for m in range(1, 13):
    if m in monthly:
        season = 'HIVER' if m in [11, 12, 1, 2, 3] else 'ETE'
        print(f'{m:>4}    {monthly[m]:>5}   ${monthly_pnl[m]:>8,.0f}   {season}')

hiver_trades = sum(monthly[m] for m in [11, 12, 1, 2, 3] if m in monthly)
ete_trades = sum(monthly[m] for m in [4, 5, 6, 7, 8, 9, 10] if m in monthly)
hiver_pnl = sum(monthly_pnl[m] for m in [11, 12, 1, 2, 3] if m in monthly)
ete_pnl = sum(monthly_pnl[m] for m in [4, 5, 6, 7, 8, 9, 10] if m in monthly)

print()
print(f'HIVER (Nov-Mar): {hiver_trades} trades, PnL ${hiver_pnl:,.0f}')
print(f'ETE   (Avr-Oct): {ete_trades} trades, PnL ${ete_pnl:,.0f}')

print()
print('=== CONTEXTE HORAIRE ===')
print('7:00 CT = 8:00 ET (toujours, CT et ET basculent DST ensemble)')
print('US Equity Open = 8:30 CT / 9:30 ET')
print('Major Data Releases (NFP, CPI) = 7:30 CT / 8:30 ET')
print()

# Sous-periodes
sub = defaultdict(lambda: {'count': 0, 'pnl': 0.0})
for t in h7:
    dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
    minute = dt.minute
    if minute < 15:
        slot = '7:00-7:14'
    elif minute < 30:
        slot = '7:15-7:29'
    elif minute < 45:
        slot = '7:30-7:44'
    else:
        slot = '7:45-7:59'
    sub[slot]['count'] += 1
    sub[slot]['pnl'] += float(t['PnL_Net'])

print('=== SOUS-PERIODES HEURE 7 CT ===')
print(f'{"Slot":<12} {"Trades":>7} {"PnL":>10} {"PnL/trade":>10}')
print('-' * 45)
for slot in ['7:00-7:14', '7:15-7:29', '7:30-7:44', '7:45-7:59']:
    d = sub[slot]
    avg = d['pnl'] / d['count'] if d['count'] > 0 else 0
    print(f'{slot:<12} {d["count"]:>5}   ${d["pnl"]:>8,.0f}   ${avg:>8,.0f}')

# Par annee
print()
print('=== PAR ANNEE ===')
yearly = defaultdict(lambda: {'count': 0, 'pnl': 0.0})
for t in h7:
    dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
    yearly[dt.year]['count'] += 1
    yearly[dt.year]['pnl'] += float(t['PnL_Net'])

for y in sorted(yearly.keys()):
    d = yearly[y]
    avg = d['pnl'] / d['count'] if d['count'] > 0 else 0
    print(f'  {y}: {d["count"]} trades, PnL ${d["pnl"]:,.0f}, avg ${avg:,.0f}')
