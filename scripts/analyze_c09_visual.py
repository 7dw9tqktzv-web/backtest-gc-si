"""
analyze_c09_visual.py - Analyse visuelle complete de la config C09
===================================================================
Genere un rapport HTML avec equity curve, heatmaps, distributions horaires,
analyse par jour de la semaine, et metriques detaillees.

Usage:
    python scripts/analyze_c09_visual.py
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "output" / "backtest_hybrid.csv"
OUT_DIR = BASE_DIR / "output" / "reports" / "c09_visual"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trades():
    trades = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            t = {
                'no': int(row['Trade_No']),
                'dir': row['Direction'],
                'entry_dt': datetime.strptime(row['Entry_DateTime'], '%Y-%m-%d %H:%M:%S'),
                'exit_dt': datetime.strptime(row['Exit_DateTime'], '%Y-%m-%d %H:%M:%S'),
                'duration': float(row['Duration_Min']),
                'entry_z': float(row['Entry_ZScore']),
                'exit_z': float(row['Exit_ZScore']),
                'exit_reason': row['Exit_Reason'],
                'beta': float(row['Beta']),
                'gc_contracts': int(row['GC_Contracts']),
                'si_contracts': int(row['SI_Contracts']),
                'pnl_gross': float(row['PnL_Gross']),
                'costs': float(row['Costs']),
                'pnl_net': float(row['PnL_Net']),
                'pnl_cumul': float(row['PnL_Cumul']),
                'max_pnl': float(row['Max_PnL_Intra']),
                'min_pnl': float(row['Min_PnL_Intra']),
                'entry_gc': float(row['Entry_GC']),
                'entry_si': float(row['Entry_SI']),
            }
            trades.append(t)
    return trades


def plot_equity_curve(trades):
    """Equity curve + drawdown overlay."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]},
                                     sharex=True)
    fig.suptitle('C09 - Equity Curve & Drawdown', fontsize=14, fontweight='bold')

    dates = [t['exit_dt'] for t in trades]
    cumul = [t['pnl_cumul'] for t in trades]

    # Equity curve
    ax1.fill_between(dates, 0, cumul, alpha=0.3, color='steelblue')
    ax1.plot(dates, cumul, color='steelblue', linewidth=1.5)
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_ylabel('PnL Cumule ($)')
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
    ax1.grid(True, alpha=0.3)

    # Marquer les annees
    for year in [2023, 2024, 2025, 2026]:
        dt = datetime(year, 1, 1)
        if dates[0] < dt < dates[-1]:
            ax1.axvline(x=dt, color='red', linestyle=':', alpha=0.4)
            ax1.text(dt, max(cumul) * 0.95, str(year), fontsize=9, color='red', alpha=0.6)

    # Drawdown
    peak = 0
    dd = []
    for c in cumul:
        peak = max(peak, c)
        dd.append(c - peak)

    ax2.fill_between(dates, dd, 0, color='red', alpha=0.4)
    ax2.plot(dates, dd, color='red', linewidth=1)
    ax2.set_ylabel('Drawdown ($)')
    ax2.set_xlabel('Date')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '01_equity_curve.png', dpi=150)
    plt.close()
    print("  [OK] 01_equity_curve.png")


def plot_monthly_heatmap(trades):
    """PnL heatmap par mois."""
    monthly = defaultdict(float)
    for t in trades:
        key = (t['entry_dt'].year, t['entry_dt'].month)
        monthly[key] += t['pnl_net']

    years = sorted(set(k[0] for k in monthly.keys()))
    months = list(range(1, 13))
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    data = np.full((len(years), 12), np.nan)
    for (y, m), pnl in monthly.items():
        yi = years.index(y)
        data[yi, m - 1] = pnl

    fig, ax = plt.subplots(figsize=(14, 4))
    fig.suptitle('C09 - PnL Mensuel (Heatmap)', fontsize=14, fontweight='bold')

    # Colormap vert/rouge
    cmap = plt.cm.RdYlGn
    vmax = max(abs(np.nanmin(data)), abs(np.nanmax(data)))
    im = ax.imshow(data, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')

    ax.set_xticks(range(12))
    ax.set_xticklabels(month_names)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years)

    # Annoter les cellules
    for i in range(len(years)):
        for j in range(12):
            val = data[i, j]
            if not np.isnan(val):
                color = 'white' if abs(val) > vmax * 0.6 else 'black'
                ax.text(j, i, f'${val:,.0f}', ha='center', va='center',
                        fontsize=8, color=color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='PnL ($)', shrink=0.8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '02_monthly_heatmap.png', dpi=150)
    plt.close()
    print("  [OK] 02_monthly_heatmap.png")


def plot_hourly_analysis(trades):
    """Analyse par heure CT."""
    hourly_pnl = defaultdict(list)
    for t in trades:
        h = t['entry_dt'].hour
        hourly_pnl[h].append(t['pnl_net'])

    hours = sorted(hourly_pnl.keys())
    avg_pnl = [np.mean(hourly_pnl[h]) for h in hours]
    total_pnl = [np.sum(hourly_pnl[h]) for h in hours]
    counts = [len(hourly_pnl[h]) for h in hours]
    win_rates = [100 * sum(1 for p in hourly_pnl[h] if p > 0) / len(hourly_pnl[h]) for h in hours]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('C09 - Analyse par Heure (CT)', fontsize=14, fontweight='bold')

    # Total PnL par heure
    colors = ['green' if p >= 0 else 'red' for p in total_pnl]
    axes[0, 0].bar(hours, total_pnl, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0, 0].set_title('PnL Total par Heure')
    axes[0, 0].set_xlabel('Heure (CT)')
    axes[0, 0].set_ylabel('PnL ($)')
    axes[0, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[0, 0].grid(True, alpha=0.3)

    # Nombre de trades par heure
    axes[0, 1].bar(hours, counts, color='steelblue', alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0, 1].set_title('Nombre de Trades par Heure')
    axes[0, 1].set_xlabel('Heure (CT)')
    axes[0, 1].set_ylabel('Trades')
    axes[0, 1].grid(True, alpha=0.3)

    # PnL moyen par heure
    colors_avg = ['green' if p >= 0 else 'red' for p in avg_pnl]
    axes[1, 0].bar(hours, avg_pnl, color=colors_avg, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[1, 0].set_title('PnL Moyen par Heure')
    axes[1, 0].set_xlabel('Heure (CT)')
    axes[1, 0].set_ylabel('PnL Moyen ($)')
    axes[1, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[1, 0].grid(True, alpha=0.3)

    # Win rate par heure
    axes[1, 1].bar(hours, win_rates, color='orange', alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[1, 1].axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50%')
    axes[1, 1].set_title('Win Rate par Heure')
    axes[1, 1].set_xlabel('Heure (CT)')
    axes[1, 1].set_ylabel('Win Rate (%)')
    axes[1, 1].set_ylim(0, 100)
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '03_hourly_analysis.png', dpi=150)
    plt.close()
    print("  [OK] 03_hourly_analysis.png")


def plot_day_of_week(trades):
    """Analyse par jour de la semaine."""
    dow_pnl = defaultdict(list)
    dow_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    for t in trades:
        d = t['entry_dt'].weekday()
        dow_pnl[d].append(t['pnl_net'])

    days = sorted(dow_pnl.keys())
    names = [dow_names[d] for d in days]
    total_pnl = [np.sum(dow_pnl[d]) for d in days]
    avg_pnl = [np.mean(dow_pnl[d]) for d in days]
    counts = [len(dow_pnl[d]) for d in days]
    win_rates = [100 * sum(1 for p in dow_pnl[d] if p > 0) / len(dow_pnl[d]) for d in days]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('C09 - Analyse par Jour de la Semaine', fontsize=14, fontweight='bold')

    colors = ['green' if p >= 0 else 'red' for p in total_pnl]
    axes[0, 0].bar(names, total_pnl, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0, 0].set_title('PnL Total par Jour')
    axes[0, 0].set_ylabel('PnL ($)')
    axes[0, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].tick_params(axis='x', rotation=45)

    axes[0, 1].bar(names, counts, color='steelblue', alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0, 1].set_title('Nombre de Trades par Jour')
    axes[0, 1].set_ylabel('Trades')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].tick_params(axis='x', rotation=45)

    colors_avg = ['green' if p >= 0 else 'red' for p in avg_pnl]
    axes[1, 0].bar(names, avg_pnl, color=colors_avg, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[1, 0].set_title('PnL Moyen par Jour')
    axes[1, 0].set_ylabel('PnL Moyen ($)')
    axes[1, 0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].tick_params(axis='x', rotation=45)

    axes[1, 1].bar(names, win_rates, color='orange', alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[1, 1].axhline(y=50, color='red', linestyle='--', alpha=0.5)
    axes[1, 1].set_title('Win Rate par Jour')
    axes[1, 1].set_ylabel('Win Rate (%)')
    axes[1, 1].set_ylim(0, 100)
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '04_day_of_week.png', dpi=150)
    plt.close()
    print("  [OK] 04_day_of_week.png")


def plot_exit_reasons(trades):
    """Distribution des raisons de sortie."""
    reasons = defaultdict(lambda: {'count': 0, 'pnl': 0, 'pnls': []})
    for t in trades:
        r = t['exit_reason']
        reasons[r]['count'] += 1
        reasons[r]['pnl'] += t['pnl_net']
        reasons[r]['pnls'].append(t['pnl_net'])

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('C09 - Analyse des Sorties', fontsize=14, fontweight='bold')

    labels = list(reasons.keys())
    counts = [reasons[r]['count'] for r in labels]
    pnls = [reasons[r]['pnl'] for r in labels]
    avg_pnls = [np.mean(reasons[r]['pnls']) for r in labels]

    # Pie chart des counts
    colors_pie = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6']
    axes[0].pie(counts, labels=labels, autopct='%1.1f%%', colors=colors_pie[:len(labels)],
                startangle=90)
    axes[0].set_title('Distribution des Sorties')

    # PnL total par raison
    colors_bar = ['green' if p >= 0 else 'red' for p in pnls]
    axes[1].barh(labels, pnls, color=colors_bar, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[1].set_title('PnL Total par Raison')
    axes[1].set_xlabel('PnL ($)')
    axes[1].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    axes[1].grid(True, alpha=0.3)

    # PnL moyen par raison
    colors_avg = ['green' if p >= 0 else 'red' for p in avg_pnls]
    axes[2].barh(labels, avg_pnls, color=colors_avg, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[2].set_title('PnL Moyen par Raison')
    axes[2].set_xlabel('PnL Moyen ($)')
    axes[2].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '05_exit_reasons.png', dpi=150)
    plt.close()
    print("  [OK] 05_exit_reasons.png")


def plot_pnl_distribution(trades):
    """Distribution des PnL par trade."""
    pnls = [t['pnl_net'] for t in trades]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('C09 - Distribution des PnL', fontsize=14, fontweight='bold')

    # Histogramme
    bins = np.arange(min(pnls) - 25, max(pnls) + 50, 50)
    n, bins_out, patches = axes[0].hist(pnls, bins=bins, edgecolor='black', linewidth=0.5, alpha=0.7)
    for patch, left_edge in zip(patches, bins_out[:-1]):
        if left_edge < 0:
            patch.set_facecolor('red')
        else:
            patch.set_facecolor('green')
    axes[0].axvline(x=0, color='black', linestyle='--', alpha=0.5)
    axes[0].axvline(x=np.mean(pnls), color='blue', linestyle='--', alpha=0.7,
                     label=f'Moy=${np.mean(pnls):.0f}')
    axes[0].axvline(x=np.median(pnls), color='orange', linestyle='--', alpha=0.7,
                     label=f'Med=${np.median(pnls):.0f}')
    axes[0].set_title('Histogramme PnL par Trade')
    axes[0].set_xlabel('PnL ($)')
    axes[0].set_ylabel('Nombre de trades')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Box plot par annee
    yearly = defaultdict(list)
    for t in trades:
        yearly[t['entry_dt'].year].append(t['pnl_net'])
    years = sorted(yearly.keys())
    data_bp = [yearly[y] for y in years]
    bp = axes[1].boxplot(data_bp, labels=[str(y) for y in years], patch_artist=True)
    for patch in bp['boxes']:
        patch.set_facecolor('steelblue')
        patch.set_alpha(0.5)
    axes[1].axhline(y=0, color='red', linestyle='--', alpha=0.5)
    axes[1].set_title('Distribution PnL par Annee')
    axes[1].set_ylabel('PnL ($)')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '06_pnl_distribution.png', dpi=150)
    plt.close()
    print("  [OK] 06_pnl_distribution.png")


def plot_duration_analysis(trades):
    """Analyse de la duree des trades."""
    durations_by_reason = defaultdict(list)
    durations_by_dir = defaultdict(list)
    for t in trades:
        durations_by_reason[t['exit_reason']].append(t['duration'])
        durations_by_dir[t['dir']].append(t['duration'])

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('C09 - Duree des Trades', fontsize=14, fontweight='bold')

    # Histogramme global
    all_dur = [t['duration'] for t in trades]
    axes[0].hist(all_dur, bins=30, color='steelblue', alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0].axvline(x=np.mean(all_dur), color='red', linestyle='--',
                     label=f'Moy={np.mean(all_dur):.0f}min')
    axes[0].axvline(x=np.median(all_dur), color='orange', linestyle='--',
                     label=f'Med={np.median(all_dur):.0f}min')
    axes[0].set_title('Distribution des Durees')
    axes[0].set_xlabel('Duree (min)')
    axes[0].set_ylabel('Trades')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Box plot par exit reason
    reasons = sorted(durations_by_reason.keys())
    data_r = [durations_by_reason[r] for r in reasons]
    bp = axes[1].boxplot(data_r, labels=reasons, patch_artist=True)
    for patch in bp['boxes']:
        patch.set_facecolor('lightcoral')
        patch.set_alpha(0.5)
    axes[1].set_title('Duree par Exit Reason')
    axes[1].set_ylabel('Duree (min)')
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(True, alpha=0.3)

    # Scatter PnL vs Duration
    pnls = [t['pnl_net'] for t in trades]
    colors = ['green' if p >= 0 else 'red' for p in pnls]
    axes[2].scatter(all_dur, pnls, c=colors, alpha=0.4, s=20, edgecolors='black', linewidth=0.3)
    axes[2].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[2].set_title('PnL vs Duree')
    axes[2].set_xlabel('Duree (min)')
    axes[2].set_ylabel('PnL ($)')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '07_duration_analysis.png', dpi=150)
    plt.close()
    print("  [OK] 07_duration_analysis.png")


def plot_yearly_equity(trades):
    """Equity curve par annee (overlay)."""
    yearly_trades = defaultdict(list)
    for t in trades:
        yearly_trades[t['entry_dt'].year].append(t)

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle('C09 - Equity Curve par Annee', fontsize=14, fontweight='bold')

    colors_y = {'2022': 'gray', '2023': '#e74c3c', '2024': '#f39c12',
                '2025': '#2ecc71', '2026': '#3498db'}

    for year in sorted(yearly_trades.keys()):
        trades_y = yearly_trades[year]
        cumul = np.cumsum([t['pnl_net'] for t in trades_y])
        trade_nums = range(1, len(cumul) + 1)
        color = colors_y.get(str(year), 'black')
        ax.plot(trade_nums, cumul, label=f'{year} ({len(trades_y)} trades, ${cumul[-1]:,.0f})',
                linewidth=2, color=color)

    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Trade #')
    ax.set_ylabel('PnL Cumule ($)')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '08_yearly_equity.png', dpi=150)
    plt.close()
    print("  [OK] 08_yearly_equity.png")


def plot_mae_mfe(trades):
    """Maximum Adverse/Favorable Excursion."""
    pnls = [t['pnl_net'] for t in trades]
    maes = [t['min_pnl'] for t in trades]  # worst intra-trade PnL
    mfes = [t['max_pnl'] for t in trades]  # best intra-trade PnL

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('C09 - MAE / MFE (Excursions Intra-Trade)', fontsize=14, fontweight='bold')

    # MAE vs PnL
    colors = ['green' if p >= 0 else 'red' for p in pnls]
    axes[0].scatter(maes, pnls, c=colors, alpha=0.4, s=25, edgecolors='black', linewidth=0.3)
    axes[0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    axes[0].set_title('MAE (Max Adverse Excursion) vs PnL Final')
    axes[0].set_xlabel('MAE - Pire PnL Intra-Trade ($)')
    axes[0].set_ylabel('PnL Net Final ($)')
    axes[0].grid(True, alpha=0.3)

    # MFE vs PnL
    axes[1].scatter(mfes, pnls, c=colors, alpha=0.4, s=25, edgecolors='black', linewidth=0.3)
    axes[1].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[1].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    # Ligne diagonale (MFE = PnL = parfait)
    max_val = max(max(mfes), max(pnls))
    axes[1].plot([0, max_val], [0, max_val], 'b--', alpha=0.3, label='MFE = PnL (sortie parfaite)')
    axes[1].set_title('MFE (Max Favorable Excursion) vs PnL Final')
    axes[1].set_xlabel('MFE - Meilleur PnL Intra-Trade ($)')
    axes[1].set_ylabel('PnL Net Final ($)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '09_mae_mfe.png', dpi=150)
    plt.close()
    print("  [OK] 09_mae_mfe.png")


def plot_long_vs_short(trades):
    """Comparaison LONG vs SHORT."""
    dir_data = defaultdict(lambda: {'pnls': [], 'count': 0})
    for t in trades:
        d = t['dir']
        dir_data[d]['pnls'].append(t['pnl_net'])
        dir_data[d]['count'] += 1

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('C09 - LONG vs SHORT', fontsize=14, fontweight='bold')

    dirs = ['LONG', 'SHORT']
    colors_d = ['#2ecc71', '#e74c3c']

    # PnL total
    totals = [np.sum(dir_data[d]['pnls']) for d in dirs]
    axes[0].bar(dirs, totals, color=colors_d, alpha=0.7, edgecolor='black', linewidth=0.5)
    axes[0].set_title('PnL Total')
    axes[0].set_ylabel('PnL ($)')
    axes[0].grid(True, alpha=0.3)
    for i, v in enumerate(totals):
        axes[0].text(i, v + 50, f'${v:,.0f}', ha='center', fontweight='bold')

    # Nombre de trades + win rate
    counts = [dir_data[d]['count'] for d in dirs]
    win_rates = [100 * sum(1 for p in dir_data[d]['pnls'] if p > 0) / len(dir_data[d]['pnls'])
                 for d in dirs]
    x = np.arange(len(dirs))
    width = 0.35
    bars1 = axes[1].bar(x - width/2, counts, width, label='Trades', color='steelblue', alpha=0.7)
    ax2 = axes[1].twinx()
    bars2 = ax2.bar(x + width/2, win_rates, width, label='Win Rate', color='orange', alpha=0.7)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(dirs)
    axes[1].set_ylabel('Nombre de Trades')
    ax2.set_ylabel('Win Rate (%)')
    ax2.set_ylim(0, 100)
    axes[1].set_title('Trades & Win Rate')
    axes[1].legend(loc='upper left')
    ax2.legend(loc='upper right')
    axes[1].grid(True, alpha=0.3)

    # Box plot distribution
    data_bp = [dir_data[d]['pnls'] for d in dirs]
    bp = axes[2].boxplot(data_bp, labels=dirs, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors_d):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    axes[2].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    axes[2].set_title('Distribution PnL')
    axes[2].set_ylabel('PnL ($)')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / '10_long_vs_short.png', dpi=150)
    plt.close()
    print("  [OK] 10_long_vs_short.png")


def generate_summary_text(trades):
    """Genere un resume texte des metriques cles."""
    pnls = [t['pnl_net'] for t in trades]
    n = len(pnls)
    total_pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    wr = 100 * len(wins) / n if n > 0 else 0

    # Drawdown
    cumul = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumul)
    dd = cumul - peak
    max_dd = dd.min()

    # Sharpe (annualise)
    avg_pnl = np.mean(pnls)
    std_pnl = np.std(pnls, ddof=1) if n > 1 else 1
    trades_per_year = n / 3  # ~3 ans
    sharpe = (avg_pnl / std_pnl) * np.sqrt(trades_per_year) if std_pnl > 0 else 0

    # Profit Factor
    gross_wins = sum(wins) if wins else 0
    gross_losses = abs(sum(losses)) if losses else 1
    pf = gross_wins / gross_losses if gross_losses > 0 else 99.99

    # Expectancy
    expectancy = avg_pnl

    # Payoff ratio
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 1
    payoff = avg_win / avg_loss if avg_loss > 0 else 99.99

    summary = f"""
================================================================================
  CONFIG C09 - RESUME COMPLET
  b2640_zp28_cp12_adf64_zE3.4_co20_zTP-0.5_dTP200_dSL-500_nohold_mm2_es0
================================================================================

  METRIQUES GLOBALES
  ------------------
  Trades:           {n}
  PnL Net:          ${total_pnl:,.0f}
  Win Rate:         {wr:.1f}%
  Profit Factor:    {pf:.2f}
  Sharpe:           {sharpe:.3f}
  Max Drawdown:     ${max_dd:,.0f}
  Calmar:           {total_pnl / abs(max_dd):.2f}
  Expectancy:       ${expectancy:,.1f}/trade
  Payoff Ratio:     {payoff:.2f}

  Avg Win:          ${avg_win:,.1f}
  Avg Loss:         ${-abs(np.mean(losses)) if losses else 0:,.1f}
  Best Trade:       ${max(pnls):,.0f}
  Worst Trade:      ${min(pnls):,.0f}

  Duree Moyenne:    {np.mean([t['duration'] for t in trades]):.0f} min
  Duree Mediane:    {np.median([t['duration'] for t in trades]):.0f} min

  PERIODE
  -------
  Debut:            {trades[0]['entry_dt'].strftime('%Y-%m-%d')}
  Fin:              {trades[-1]['exit_dt'].strftime('%Y-%m-%d')}
  Jours:            {(trades[-1]['exit_dt'] - trades[0]['entry_dt']).days}

  Graphiques generes dans: output/reports/c09_visual/
================================================================================
"""
    with open(OUT_DIR / 'summary.txt', 'w', encoding='utf-8') as f:
        f.write(summary)
    print(summary)


def main():
    print("=" * 60)
    print("  ANALYSE VISUELLE C09")
    print("=" * 60)

    if not CSV_PATH.exists():
        print(f"ERREUR: {CSV_PATH} introuvable")
        print("Lancez d'abord: python src/backtest_engine_numba.py")
        sys.exit(1)

    trades = load_trades()
    print(f"  {len(trades)} trades charges\n")
    print("  Generation des graphiques...")

    plot_equity_curve(trades)
    plot_monthly_heatmap(trades)
    plot_hourly_analysis(trades)
    plot_day_of_week(trades)
    plot_exit_reasons(trades)
    plot_pnl_distribution(trades)
    plot_duration_analysis(trades)
    plot_yearly_equity(trades)
    plot_mae_mfe(trades)
    plot_long_vs_short(trades)

    print("\n  Generation du resume...")
    generate_summary_text(trades)

    print(f"\n  Tous les fichiers dans: {OUT_DIR}")


if __name__ == '__main__':
    main()
