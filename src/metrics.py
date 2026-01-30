"""
metrics.py - Analyse de performance et archivage des backtests
==============================================================
Module qui lit backtest_hybrid.csv, calcule toutes les metriques de performance,
genere un rapport texte + graphique equity curve, et archive le tout dans une
structure de dossiers organisee.

Usage standalone :
    python src/metrics.py

Sections d'analyse :
    1. Metriques globales (PnL, Win Rate, Profit Factor, Max DD, Durees)
    2. Metriques avancees (Sharpe, Sortino, Calmar, Expectancy, Payoff Ratio)
    3. Analyse par session (Asia, Europe, US)
    4. Analyse par direction (LONG, SHORT)
    5. Courbe d'equity (CSV + PNG)
    6. Analyse de risque (drawdown duration, consecutive losses/wins)
    7. Analyse par sizing (GC contracts)
    8. Analyse par type de sortie (TP/SL)
    9. Distribution des PnL (quartiles)
   10. Analyse par jour de la semaine
"""

import csv
import os
import shutil
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path

import yaml
import matplotlib
matplotlib.use('Agg')  # Backend sans affichage (pas de fenetre)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


# ============================================================================
# CHEMINS
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "strategy_params.yaml"
BACKTEST_CSV = BASE_DIR / "output" / "backtest_hybrid.csv"
ARCHIVE_DIR = BASE_DIR / "output" / "archive"
INDEX_CSV = ARCHIVE_DIR / "index.csv"


# ============================================================================
# CHARGEMENT DES DONNEES
# ============================================================================
def load_config():
    """Charge la configuration depuis strategy_params.yaml."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def load_trades(filepath=None):
    """Charge les trades depuis le CSV du backtest (separateur point-virgule)."""
    if filepath is None:
        filepath = BACKTEST_CSV
    if not os.path.exists(filepath):
        print(f"[ERREUR] Fichier introuvable : {filepath}")
        print("         Lance d'abord le backtest : python src/backtest_engine_hybrid.py")
        raise SystemExit(1)
    trades = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            trades.append(row)
    return trades


# ============================================================================
# SECTION 1 : METRIQUES GLOBALES
# ============================================================================
def compute_global_metrics(trades):
    """Calcule les metriques globales de performance."""
    n = len(trades)
    pnl_list = [float(t['PnL_Net']) for t in trades]
    pnl_gross_list = [float(t['PnL_Gross']) for t in trades]
    costs_list = [float(t['Costs']) for t in trades]
    durations = [float(t['Duration_Min']) for t in trades]

    n_long = sum(1 for t in trades if t['Direction'] == 'LONG')
    n_short = sum(1 for t in trades if t['Direction'] == 'SHORT')
    winners = sum(1 for p in pnl_list if p > 0)
    losers = sum(1 for p in pnl_list if p <= 0)

    pnl_net = sum(pnl_list)
    pnl_gross = sum(pnl_gross_list)
    costs_total = sum(costs_list)

    win_rate = round(100 * winners / n, 1) if n else 0
    pnl_avg = round(pnl_net / n, 2) if n else 0

    gains = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    gain_avg = round(statistics.mean(gains), 2) if gains else 0
    loss_avg = round(statistics.mean(losses), 2) if losses else 0

    best = max(pnl_list) if pnl_list else 0
    worst = min(pnl_list) if pnl_list else 0

    sum_gains = sum(gains)
    sum_losses = abs(sum(losses))
    profit_factor = round(sum_gains / sum_losses, 2) if sum_losses else float('inf')

    # Max drawdown depuis PnL_Cumul
    cumul = [float(t['PnL_Cumul']) for t in trades]
    peak = cumul[0]
    max_dd = 0
    for c in cumul:
        if c > peak:
            peak = c
        dd = c - peak
        if dd < max_dd:
            max_dd = dd

    # Durees
    dur_avg = round(statistics.mean(durations), 1) if durations else 0
    dur_median = round(statistics.median(durations), 1) if durations else 0
    dur_max = max(durations) if durations else 0

    # Temps total en position (somme des durees en minutes)
    total_in_market = sum(durations)

    # Nombre de jours de trading (du premier au dernier trade)
    first_dt = datetime.strptime(trades[0]['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
    last_dt = datetime.strptime(trades[-1]['Exit_DateTime'], '%Y-%m-%d %H:%M:%S')
    days_loaded = (last_dt - first_dt).days + 1

    return {
        'n': n, 'n_long': n_long, 'n_short': n_short,
        'winners': winners, 'losers': losers, 'win_rate': win_rate,
        'pnl_net': pnl_net, 'pnl_gross': pnl_gross, 'costs_total': costs_total,
        'pnl_avg': pnl_avg, 'gain_avg': gain_avg, 'loss_avg': loss_avg,
        'best': best, 'worst': worst,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'dur_avg': dur_avg, 'dur_median': dur_median, 'dur_max': dur_max,
        'total_in_market_min': total_in_market,
        'days_loaded': days_loaded,
        'pnl_list': pnl_list,
        'cumul': cumul,
    }


# ============================================================================
# SECTION 2 : METRIQUES AVANCEES
# ============================================================================
def compute_advanced_metrics(gm):
    """Calcule Sharpe, Sortino, Calmar, Expectancy, Payoff Ratio."""
    pnl_list = gm['pnl_list']
    n = gm['n']

    # Sharpe Ratio (par trade, annualise avec racine du nombre de trades/an)
    if n > 1:
        pnl_std = statistics.stdev(pnl_list)
        sharpe = round(gm['pnl_avg'] / pnl_std, 3) if pnl_std else 0
    else:
        sharpe = 0
        pnl_std = 0

    # Sortino Ratio (seule la volatilite negative)
    neg_returns = [p for p in pnl_list if p < 0]
    if len(neg_returns) > 1:
        downside_std = statistics.stdev(neg_returns)
        sortino = round(gm['pnl_avg'] / downside_std, 3) if downside_std else 0
    else:
        sortino = 0

    # Calmar Ratio (PnL net / |Max DD|)
    calmar = round(gm['pnl_net'] / abs(gm['max_dd']), 2) if gm['max_dd'] != 0 else 0

    # Expectancy = (Win% x Gain moyen) - (Loss% x |Perte moyenne|)
    win_pct = gm['winners'] / n if n else 0
    loss_pct = gm['losers'] / n if n else 0
    expectancy = round(win_pct * gm['gain_avg'] - loss_pct * abs(gm['loss_avg']), 2)

    # Payoff Ratio = Gain moyen / |Perte moyenne|
    payoff = round(gm['gain_avg'] / abs(gm['loss_avg']), 2) if gm['loss_avg'] != 0 else 0

    # Annualise (estimation: trades par jour * 252 jours)
    trades_per_day = n / gm['days_loaded'] if gm['days_loaded'] > 0 else 0
    trades_per_year = trades_per_day * 252
    pnl_annualise = round(gm['pnl_avg'] * trades_per_year, 0) if trades_per_year else 0
    sharpe_annualise = round(sharpe * math.sqrt(trades_per_year), 3) if trades_per_year > 0 else 0

    return {
        'sharpe': sharpe,
        'sortino': sortino,
        'calmar': calmar,
        'expectancy': expectancy,
        'payoff_ratio': payoff,
        'pnl_annualise': pnl_annualise,
        'sharpe_annualise': sharpe_annualise,
        'trades_per_day': round(trades_per_day, 1),
    }


# ============================================================================
# SECTION 3 : ANALYSE PAR SESSION (Asia, Europe, US)
# ============================================================================
def compute_session_analysis(trades):
    """Analyse par session de trading (heures Chicago Time).
    Asia  : 17:30 - 02:00 CT
    Europe: 02:00 - 08:30 CT
    US    : 08:30 - 15:00 CT
    """
    sessions = {
        'Asia': {'trades': 0, 'wins': 0, 'pnl': 0},
        'Europe': {'trades': 0, 'wins': 0, 'pnl': 0},
        'US': {'trades': 0, 'wins': 0, 'pnl': 0},
    }

    for t in trades:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        hour = dt.hour
        minute = dt.minute
        time_val = hour * 60 + minute  # en minutes depuis minuit

        # Asia: 17:30 (1050) -> 02:00 (120) -- traverse minuit
        # Europe: 02:00 (120) -> 08:30 (510)
        # US: 08:30 (510) -> 15:00 (900)
        if time_val >= 1050 or time_val < 120:
            session = 'Asia'
        elif 120 <= time_val < 510:
            session = 'Europe'
        else:
            session = 'US'

        pnl = float(t['PnL_Net'])
        sessions[session]['trades'] += 1
        sessions[session]['pnl'] += pnl
        if pnl > 0:
            sessions[session]['wins'] += 1

    # Calculer win rate par session
    for s in sessions.values():
        s['win_rate'] = round(100 * s['wins'] / s['trades'], 1) if s['trades'] else 0
        s['pnl'] = round(s['pnl'], 2)
        s['pnl_avg'] = round(s['pnl'] / s['trades'], 2) if s['trades'] else 0

    return sessions


# ============================================================================
# SECTION 4 : ANALYSE PAR DIRECTION
# ============================================================================
def compute_direction_analysis(trades):
    """Analyse par direction (LONG vs SHORT)."""
    dirs = {
        'LONG': {'trades': 0, 'wins': 0, 'pnl': 0, 'gains': 0, 'losses': 0},
        'SHORT': {'trades': 0, 'wins': 0, 'pnl': 0, 'gains': 0, 'losses': 0},
    }

    for t in trades:
        d = t['Direction']
        pnl = float(t['PnL_Net'])
        dirs[d]['trades'] += 1
        dirs[d]['pnl'] += pnl
        if pnl > 0:
            dirs[d]['wins'] += 1
            dirs[d]['gains'] += pnl
        else:
            dirs[d]['losses'] += pnl

    for d in dirs.values():
        d['win_rate'] = round(100 * d['wins'] / d['trades'], 1) if d['trades'] else 0
        d['pnl'] = round(d['pnl'], 2)
        d['pnl_avg'] = round(d['pnl'] / d['trades'], 2) if d['trades'] else 0
        abs_losses = abs(d['losses'])
        d['profit_factor'] = round(d['gains'] / abs_losses, 2) if abs_losses else float('inf')

    return dirs


# ============================================================================
# SECTION 5 : COURBE D'EQUITY (donnees pour graphique)
# ============================================================================
def compute_equity_data(trades):
    """Prepare les donnees pour la courbe d'equity et underwater."""
    dates = []
    cumul = []
    underwater = []

    peak = 0
    for t in trades:
        dt = datetime.strptime(t['Exit_DateTime'], '%Y-%m-%d %H:%M:%S')
        c = float(t['PnL_Cumul'])
        dates.append(dt)
        cumul.append(c)
        if c > peak:
            peak = c
        underwater.append(c - peak)

    return {'dates': dates, 'cumul': cumul, 'underwater': underwater}


# ============================================================================
# SECTION 6 : ANALYSE DE RISQUE
# ============================================================================
def compute_risk_analysis(trades, gm):
    """Drawdown duration, consecutive losses/wins."""
    pnl_list = gm['pnl_list']
    cumul = gm['cumul']

    # --- Drawdown duration (en nombre de trades) ---
    peak = cumul[0]
    peak_idx = 0
    max_dd_duration = 0
    current_dd_start = 0
    in_dd = False

    for i, c in enumerate(cumul):
        if c >= peak:
            if in_dd:
                dd_duration = i - current_dd_start
                if dd_duration > max_dd_duration:
                    max_dd_duration = dd_duration
                in_dd = False
            peak = c
            peak_idx = i
        else:
            if not in_dd:
                current_dd_start = peak_idx
                in_dd = True

    # Si on finit en drawdown
    if in_dd:
        dd_duration = len(cumul) - 1 - current_dd_start
        if dd_duration > max_dd_duration:
            max_dd_duration = dd_duration

    # --- Consecutive losses ---
    max_consec_losses = 0
    max_consec_losses_pnl = 0
    current_streak = 0
    current_streak_pnl = 0

    for p in pnl_list:
        if p <= 0:
            current_streak += 1
            current_streak_pnl += p
        else:
            if current_streak > max_consec_losses:
                max_consec_losses = current_streak
                max_consec_losses_pnl = current_streak_pnl
            current_streak = 0
            current_streak_pnl = 0
    # Verifier la derniere serie
    if current_streak > max_consec_losses:
        max_consec_losses = current_streak
        max_consec_losses_pnl = current_streak_pnl

    # --- Consecutive wins ---
    max_consec_wins = 0
    max_consec_wins_pnl = 0
    current_streak = 0
    current_streak_pnl = 0

    for p in pnl_list:
        if p > 0:
            current_streak += 1
            current_streak_pnl += p
        else:
            if current_streak > max_consec_wins:
                max_consec_wins = current_streak
                max_consec_wins_pnl = current_streak_pnl
            current_streak = 0
            current_streak_pnl = 0
    if current_streak > max_consec_wins:
        max_consec_wins = current_streak
        max_consec_wins_pnl = current_streak_pnl

    return {
        'max_dd_duration_trades': max_dd_duration,
        'max_consec_losses': max_consec_losses,
        'max_consec_losses_pnl': round(max_consec_losses_pnl, 2),
        'max_consec_wins': max_consec_wins,
        'max_consec_wins_pnl': round(max_consec_wins_pnl, 2),
    }


# ============================================================================
# SECTION 7 : ANALYSE PAR SIZING (GC CONTRACTS)
# ============================================================================
def compute_sizing_analysis(trades):
    """Analyse par nombre de contrats GC."""
    sizing = {}
    for t in trades:
        gc = int(t['GC_Contracts'])
        if gc not in sizing:
            sizing[gc] = {'trades': 0, 'wins': 0, 'pnl': 0}
        pnl = float(t['PnL_Net'])
        sizing[gc]['trades'] += 1
        sizing[gc]['pnl'] += pnl
        if pnl > 0:
            sizing[gc]['wins'] += 1

    for s in sizing.values():
        s['win_rate'] = round(100 * s['wins'] / s['trades'], 1) if s['trades'] else 0
        s['pnl'] = round(s['pnl'], 2)
        s['pnl_avg'] = round(s['pnl'] / s['trades'], 2) if s['trades'] else 0

    return dict(sorted(sizing.items()))


# ============================================================================
# SECTION 8 : ANALYSE PAR TYPE DE SORTIE
# ============================================================================
def compute_exit_analysis(trades):
    """Analyse par type de sortie (TP_DOLLAR, TP_ZSCORE, SL_DOLLAR, SL_ZSCORE)."""
    exits = {}
    for t in trades:
        reason = t['Exit_Reason']
        if reason not in exits:
            exits[reason] = {'trades': 0, 'wins': 0, 'pnl': 0, 'durations': []}
        pnl = float(t['PnL_Net'])
        dur = float(t['Duration_Min'])
        exits[reason]['trades'] += 1
        exits[reason]['pnl'] += pnl
        exits[reason]['durations'].append(dur)
        if pnl > 0:
            exits[reason]['wins'] += 1

    for e in exits.values():
        e['win_rate'] = round(100 * e['wins'] / e['trades'], 1) if e['trades'] else 0
        e['pnl'] = round(e['pnl'], 2)
        e['pnl_avg'] = round(e['pnl'] / e['trades'], 2) if e['trades'] else 0
        e['dur_avg'] = round(statistics.mean(e['durations']), 1) if e['durations'] else 0

    # Ordre fixe pour affichage
    order = ['TP_DOLLAR', 'TP_ZSCORE', 'SL_DOLLAR', 'SL_ZSCORE']
    return {k: exits.get(k, {'trades': 0, 'wins': 0, 'pnl': 0, 'win_rate': 0, 'pnl_avg': 0, 'dur_avg': 0}) for k in order}


# ============================================================================
# SECTION 9 : DISTRIBUTION DES PNL
# ============================================================================
def compute_pnl_distribution(gm):
    """Quartiles et statistiques de distribution."""
    pnl_list = gm['pnl_list']
    n = len(pnl_list)

    # statistics.quantiles() repartit en 4 quartiles avec interpolation (Python 3.8+)
    if n >= 2:
        q1, median, q3 = statistics.quantiles(pnl_list, n=4)
    else:
        q1 = median = q3 = pnl_list[0] if pnl_list else 0

    return {
        'min': min(pnl_list) if pnl_list else 0,
        'q1': round(q1, 2),
        'median': round(median, 2),
        'q3': round(q3, 2),
        'max': max(pnl_list) if pnl_list else 0,
        'std': round(statistics.stdev(pnl_list), 2) if n > 1 else 0,
    }


# ============================================================================
# SECTION 10 : ANALYSE PAR JOUR DE LA SEMAINE
# ============================================================================
def compute_weekday_analysis(trades):
    """Analyse par jour de la semaine (Lundi-Vendredi)."""
    days = {
        0: {'name': 'Lundi', 'trades': 0, 'wins': 0, 'pnl': 0},
        1: {'name': 'Mardi', 'trades': 0, 'wins': 0, 'pnl': 0},
        2: {'name': 'Mercredi', 'trades': 0, 'wins': 0, 'pnl': 0},
        3: {'name': 'Jeudi', 'trades': 0, 'wins': 0, 'pnl': 0},
        4: {'name': 'Vendredi', 'trades': 0, 'wins': 0, 'pnl': 0},
        5: {'name': 'Samedi', 'trades': 0, 'wins': 0, 'pnl': 0},
        6: {'name': 'Dimanche', 'trades': 0, 'wins': 0, 'pnl': 0},
    }

    for t in trades:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        wd = dt.weekday()
        pnl = float(t['PnL_Net'])
        days[wd]['trades'] += 1
        days[wd]['pnl'] += pnl
        if pnl > 0:
            days[wd]['wins'] += 1

    result = {}
    for wd in sorted(days.keys()):
        d = days[wd]
        if d['trades'] > 0:
            d['win_rate'] = round(100 * d['wins'] / d['trades'], 1)
            d['pnl'] = round(d['pnl'], 2)
            d['pnl_avg'] = round(d['pnl'] / d['trades'], 2)
            result[wd] = d

    return result


# ============================================================================
# GENERATION DU RAPPORT TEXTE
# ============================================================================
def generate_report(gm, am, sessions, dirs, risk, sizing, exits, dist, weekdays, config):
    """Genere le rapport texte complet."""
    lines = []
    lines.append("=" * 70)
    lines.append("RAPPORT DE PERFORMANCE - BACKTEST HYBRIDE (1min + 5s)")
    lines.append("=" * 70)
    lines.append(f"Date du rapport : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Periode         : {config['indicators'].get('period', '1min')}")
    lines.append(f"Jours de donnees: {gm['days_loaded']}")
    lines.append("")

    # --- Parametres utilises ---
    lines.append("-" * 70)
    lines.append("PARAMETRES UTILISES")
    lines.append("-" * 70)
    ind = config['indicators']
    ent = config['entry']
    ext = config['exit']
    lines.append(f"  Indicateurs : beta_lookback={ind['beta_lookback']}, zscore_period={ind['zscore_period']}, "
                 f"correlation_period={ind['correlation_period']}, adf_hurst_period={ind['adf_hurst_period']}")
    lines.append(f"  Entree      : Z-Score LONG<={ent['zscore_long']}, SHORT>={ent['zscore_short']}, "
                 f"Corr>={ent['correlation_min']}, Coint>={ent['cointegration_score_min']}")
    lines.append(f"  Sortie Z    : TP LONG>={ext['zscore_tp_long']}, SL LONG<={ext['zscore_sl_long']}, "
                 f"TP SHORT<={ext['zscore_tp_short']}, SL SHORT>={ext['zscore_sl_short']}")
    lines.append(f"  Sortie $    : TP=${ext['pnl_take_profit']}, SL=${ext['pnl_stop_loss']}")
    lines.append("")

    # --- Section 1 : Metriques globales ---
    lines.append("-" * 70)
    lines.append("1. METRIQUES GLOBALES")
    lines.append("-" * 70)
    lines.append(f"  Trades total     : {gm['n']} ({gm['n_long']} LONG, {gm['n_short']} SHORT)")
    lines.append(f"  Gagnants         : {gm['winners']} ({gm['win_rate']}%)")
    lines.append(f"  Perdants         : {gm['losers']} ({round(100 - gm['win_rate'], 1)}%)")
    lines.append(f"  PnL brut         : ${gm['pnl_gross']:+,.2f}")
    lines.append(f"  Couts totaux     : -${gm['costs_total']:,.2f}")
    lines.append(f"  PnL net          : ${gm['pnl_net']:+,.2f}")
    lines.append(f"  PnL moyen/trade  : ${gm['pnl_avg']:+,.2f}")
    lines.append(f"  Gain moyen       : ${gm['gain_avg']:+,.2f}")
    lines.append(f"  Perte moyenne    : ${gm['loss_avg']:+,.2f}")
    lines.append(f"  Meilleur trade   : ${gm['best']:+,.2f}")
    lines.append(f"  Pire trade       : ${gm['worst']:+,.2f}")
    lines.append(f"  Profit Factor    : {gm['profit_factor']}")
    lines.append(f"  Max Drawdown     : ${gm['max_dd']:+,.2f}")
    lines.append(f"  Duree moy/trade  : {gm['dur_avg']} min")
    lines.append(f"  Duree mediane    : {gm['dur_median']} min")
    lines.append(f"  Duree max        : {gm['dur_max']} min")
    lines.append(f"  Temps en position: {gm['total_in_market_min']:.0f} min")
    lines.append("")

    # --- Section 2 : Metriques avancees ---
    lines.append("-" * 70)
    lines.append("2. METRIQUES AVANCEES")
    lines.append("-" * 70)
    lines.append(f"  Sharpe Ratio       : {am['sharpe']} (par trade)")
    lines.append(f"  Sharpe Annualise   : {am['sharpe_annualise']}")
    lines.append(f"  Sortino Ratio      : {am['sortino']} (par trade)")
    lines.append(f"  Calmar Ratio       : {am['calmar']} (PnL net / |Max DD|)")
    lines.append(f"  Expectancy         : ${am['expectancy']:+,.2f} /trade")
    lines.append(f"  Payoff Ratio       : {am['payoff_ratio']} (Gain moy / |Perte moy|)")
    lines.append(f"  PnL Annualise      : ${am['pnl_annualise']:+,.0f}")
    lines.append(f"  Trades/jour        : {am['trades_per_day']}")
    lines.append("")

    # --- Section 3 : Analyse par session ---
    lines.append("-" * 70)
    lines.append("3. ANALYSE PAR SESSION")
    lines.append("-" * 70)
    lines.append(f"  {'Session':<10} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'PnL Net':>12} {'PnL Moy':>10}")
    lines.append(f"  {'-'*10} {'-'*7} {'-'*6} {'-'*7} {'-'*12} {'-'*10}")
    for name, s in sessions.items():
        lines.append(f"  {name:<10} {s['trades']:>7} {s['wins']:>6} {s['win_rate']:>6.1f}% ${s['pnl']:>+10,.2f} ${s['pnl_avg']:>+8,.2f}")
    lines.append("")

    # --- Section 4 : Analyse par direction ---
    lines.append("-" * 70)
    lines.append("4. ANALYSE PAR DIRECTION")
    lines.append("-" * 70)
    lines.append(f"  {'Dir':<7} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'PnL Net':>12} {'PnL Moy':>10} {'PF':>6}")
    lines.append(f"  {'-'*7} {'-'*7} {'-'*6} {'-'*7} {'-'*12} {'-'*10} {'-'*6}")
    for name, d in dirs.items():
        pf_str = f"{d['profit_factor']}" if d['profit_factor'] != float('inf') else "inf"
        lines.append(f"  {name:<7} {d['trades']:>7} {d['wins']:>6} {d['win_rate']:>6.1f}% ${d['pnl']:>+10,.2f} ${d['pnl_avg']:>+8,.2f} {pf_str:>6}")
    lines.append("")

    # --- Section 5 : Courbe d'equity (reference au PNG) ---
    lines.append("-" * 70)
    lines.append("5. COURBE D'EQUITY")
    lines.append("-" * 70)
    lines.append("  Voir fichier : equity_curve.png")
    lines.append("")

    # --- Section 6 : Analyse de risque ---
    lines.append("-" * 70)
    lines.append("6. ANALYSE DE RISQUE")
    lines.append("-" * 70)
    lines.append(f"  Max Drawdown           : ${gm['max_dd']:+,.2f}")
    lines.append(f"  DD duration max        : {risk['max_dd_duration_trades']} trades")
    lines.append(f"  Pertes consecutives max: {risk['max_consec_losses']} trades (${risk['max_consec_losses_pnl']:+,.2f})")
    lines.append(f"  Gains consecutifs max  : {risk['max_consec_wins']} trades (${risk['max_consec_wins_pnl']:+,.2f})")
    lines.append("")

    # --- Section 7 : Analyse par sizing ---
    lines.append("-" * 70)
    lines.append("7. ANALYSE PAR SIZING (GC CONTRACTS)")
    lines.append("-" * 70)
    lines.append(f"  {'GC':<5} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'PnL Net':>12} {'PnL Moy':>10}")
    lines.append(f"  {'-'*5} {'-'*7} {'-'*6} {'-'*7} {'-'*12} {'-'*10}")
    for gc, s in sizing.items():
        lines.append(f"  {gc:<5} {s['trades']:>7} {s['wins']:>6} {s['win_rate']:>6.1f}% ${s['pnl']:>+10,.2f} ${s['pnl_avg']:>+8,.2f}")
    lines.append("")

    # --- Section 8 : Analyse par type de sortie ---
    lines.append("-" * 70)
    lines.append("8. ANALYSE PAR TYPE DE SORTIE")
    lines.append("-" * 70)
    lines.append(f"  {'Type':<12} {'Trades':>7} {'Win%':>7} {'PnL Net':>12} {'PnL Moy':>10} {'Duree Moy':>10}")
    lines.append(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*12} {'-'*10} {'-'*10}")
    for name, e in exits.items():
        lines.append(f"  {name:<12} {e['trades']:>7} {e['win_rate']:>6.1f}% ${e['pnl']:>+10,.2f} ${e['pnl_avg']:>+8,.2f} {e['dur_avg']:>8.1f} min")
    lines.append("")

    # --- Section 9 : Distribution des PnL ---
    lines.append("-" * 70)
    lines.append("9. DISTRIBUTION DES PNL")
    lines.append("-" * 70)
    lines.append(f"  Min     : ${dist['min']:+,.2f}")
    lines.append(f"  Q1 (25%): ${dist['q1']:+,.2f}")
    lines.append(f"  Mediane : ${dist['median']:+,.2f}")
    lines.append(f"  Q3 (75%): ${dist['q3']:+,.2f}")
    lines.append(f"  Max     : ${dist['max']:+,.2f}")
    lines.append(f"  Ecart-type: ${dist['std']:,.2f}")
    lines.append("")

    # --- Section 10 : Analyse par jour de la semaine ---
    lines.append("-" * 70)
    lines.append("10. ANALYSE PAR JOUR DE LA SEMAINE")
    lines.append("-" * 70)
    lines.append(f"  {'Jour':<10} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'PnL Net':>12} {'PnL Moy':>10}")
    lines.append(f"  {'-'*10} {'-'*7} {'-'*6} {'-'*7} {'-'*12} {'-'*10}")
    for wd, d in weekdays.items():
        lines.append(f"  {d['name']:<10} {d['trades']:>7} {d['wins']:>6} {d['win_rate']:>6.1f}% ${d['pnl']:>+10,.2f} ${d['pnl_avg']:>+8,.2f}")
    lines.append("")

    lines.append("=" * 70)
    lines.append("FIN DU RAPPORT")
    lines.append("=" * 70)

    return '\n'.join(lines)


# ============================================================================
# GENERATION DU GRAPHIQUE EQUITY CURVE
# ============================================================================
def generate_equity_chart(equity_data, output_path):
    """Genere le graphique PNG avec equity curve et underwater."""
    dates = equity_data['dates']
    cumul = equity_data['cumul']
    underwater = equity_data['underwater']

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                    gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.05})

    # --- Equity Curve ---
    ax1.plot(dates, cumul, color='#2196F3', linewidth=1.5, label='PnL Cumule')
    ax1.fill_between(dates, 0, cumul, alpha=0.1, color='#2196F3')
    ax1.axhline(y=0, color='gray', linewidth=0.5, linestyle='--')
    ax1.set_ylabel('PnL Cumule ($)')
    ax1.set_title('Courbe d\'Equity - Backtest Hybride GC/SI')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # --- Underwater (Drawdown) ---
    ax2.fill_between(dates, 0, underwater, color='#F44336', alpha=0.4, label='Drawdown')
    ax2.plot(dates, underwater, color='#F44336', linewidth=0.8)
    ax2.axhline(y=0, color='gray', linewidth=0.5)
    ax2.set_ylabel('Drawdown ($)')
    ax2.set_xlabel('Date')
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Rotation des dates
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    fig.subplots_adjust(left=0.08, right=0.95, top=0.93, bottom=0.12)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


# ============================================================================
# ARCHIVAGE
# ============================================================================
def build_archive_path(config):
    """Construit le chemin d'archive selon la structure definie.
    output/archive/{period}/{indicateurs}/{entry_exit}/
    """
    ind = config['indicators']
    ent = config['entry']
    ext = config['exit']

    # Niveau 1 : Periode
    period = ind.get('period', '1min')

    # Niveau 2 : Parametres indicateurs
    level2 = (f"beta{ind['beta_lookback']}_zp{ind['zscore_period']}"
              f"_corr{ind['correlation_period']}_adf{ind['adf_hurst_period']}")

    # Niveau 3 : Parametres entry/exit (tout inclure)
    ze_long = str(ent['zscore_long']).replace('-', 'n')  # -2.5 -> n2.5
    ze_short = str(ent['zscore_short'])
    ztp_long = str(ext['zscore_tp_long']).replace('-', 'n')
    zsl_long = str(ext['zscore_sl_long']).replace('-', 'n')
    ztp_short = str(ext['zscore_tp_short'])
    zsl_short = str(ext['zscore_sl_short'])
    tp = str(ext['pnl_take_profit'])
    sl = str(abs(ext['pnl_stop_loss']))
    corr_min = str(ent['correlation_min'])
    coint_min = str(ent['cointegration_score_min'])

    level3 = (f"zE{ze_long}_{ze_short}_zTP{ztp_long}_{ztp_short}"
              f"_zSL{zsl_long}_{zsl_short}_TP{tp}_SL{sl}"
              f"_corr{corr_min}_coint{coint_min}")

    return ARCHIVE_DIR / period / level2 / level3


def archive_results(archive_path, report_text, config):
    """Archive les resultats dans le dossier structure."""
    # Creer les dossiers
    archive_path.mkdir(parents=True, exist_ok=True)

    # 1. Copier backtest_hybrid.csv
    shutil.copy2(BACKTEST_CSV, archive_path / "backtest_hybrid.csv")

    # 2. Sauvegarder le rapport
    report_path = archive_path / "metrics_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)

    # 3. Generer la courbe d'equity (fait dans main)

    # 4. Sauvegarder la config
    config_path = archive_path / "params_snapshot.yaml"
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    return archive_path


def update_index(config, gm, am, archive_path, trades):
    """Met a jour le fichier index.csv avec les metriques du run.

    Args:
        trades: liste de trades deja chargee (evite de relire le CSV).
    """
    ind = config['indicators']
    ent = config['entry']
    ext = config['exit']

    # Chemin relatif depuis archive/ (forward slashes pour compatibilite CSV)
    try:
        rel_path = archive_path.relative_to(ARCHIVE_DIR).as_posix()
    except ValueError:
        rel_path = str(archive_path).replace('\\', '/')

    headers = (
        "DateTime;Folder_Path;Period;Beta;ZP;Corr;ADF;"
        "ZE_Long;ZE_Short;ZTP_Long;ZTP_Short;ZSL_Long;ZSL_Short;"
        "TP;SL;Corr_Min;Coint_Min;"
        "Trades;LONG;SHORT;Winners;Win_Rate;PnL_Net;PnL_Avg;"
        "Best;Worst;Max_DD;Profit_Factor;Sharpe;Calmar;"
        "Days_Loaded;TP_DOLLAR;TP_ZSCORE;SL_DOLLAR;SL_ZSCORE"
    )

    # Compter les exits
    exits = {}
    for t in trades:
        r = t['Exit_Reason']
        exits[r] = exits.get(r, 0) + 1

    row = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')};"
        f"{rel_path};"
        f"{ind.get('period', '1min')};"
        f"{ind['beta_lookback']};{ind['zscore_period']};{ind['correlation_period']};{ind['adf_hurst_period']};"
        f"{ent['zscore_long']};{ent['zscore_short']};{ext['zscore_tp_long']};{ext['zscore_tp_short']};{ext['zscore_sl_long']};{ext['zscore_sl_short']};"
        f"{ext['pnl_take_profit']};{ext['pnl_stop_loss']};{ent['correlation_min']};{ent['cointegration_score_min']};"
        f"{gm['n']};{gm['n_long']};{gm['n_short']};{gm['winners']};{gm['win_rate']};"
        f"{gm['pnl_net']};{gm['pnl_avg']};{gm['best']};{gm['worst']};{gm['max_dd']};"
        f"{gm['profit_factor']};{am['sharpe']};{am['calmar']};"
        f"{gm['days_loaded']};"
        f"{exits.get('TP_DOLLAR', 0)};{exits.get('TP_ZSCORE', 0)};"
        f"{exits.get('SL_DOLLAR', 0)};{exits.get('SL_ZSCORE', 0)}"
    )

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Lire l'index existant pour detecter les doublons
    # Un doublon = meme Folder_Path ET meme Days_Loaded
    # Si meme Folder_Path mais Days_Loaded different -> run distinct, on garde les deux
    existing_lines = []
    file_exists = INDEX_CSV.exists()
    if file_exists:
        with open(INDEX_CSV, 'r', encoding='utf-8') as f:
            existing_lines = f.readlines()

    rel_path_str = rel_path if isinstance(rel_path, str) else str(rel_path)
    days_str = str(gm['days_loaded'])

    if file_exists and len(existing_lines) > 1:
        # Filtrer les doublons (meme folder + meme days_loaded) -> on les ecrase
        filtered = [existing_lines[0]]  # garder le header
        for line in existing_lines[1:]:
            parts = line.strip().split(';')
            if len(parts) >= 31:
                # Normaliser les chemins (forward slashes) pour comparaison
                line_path = parts[1].replace('\\', '/')
                line_days = parts[30]  # Days_Loaded est en position 30 (0-indexed)
                # Garder la ligne si ce n'est PAS un doublon
                if not (line_path == rel_path_str and line_days == days_str):
                    filtered.append(line if line.endswith('\n') else line + '\n')
            else:
                filtered.append(line if line.endswith('\n') else line + '\n')

        # Reecrire l'index filtre + nouvelle ligne
        with open(INDEX_CSV, 'w', encoding='utf-8', newline='') as f:
            for line in filtered:
                f.write(line)
            f.write(row + '\n')
    else:
        with open(INDEX_CSV, 'w', encoding='utf-8', newline='') as f:
            f.write(headers + '\n')
            f.write(row + '\n')


# ============================================================================
# MAIN
# ============================================================================
def run_metrics():
    """Point d'entree principal : analyse + archivage."""
    print("=" * 60)
    print("METRICS - Analyse de performance et archivage")
    print("=" * 60)

    # Charger
    print("[...] Chargement de la configuration...")
    config = load_config()

    print("[...] Chargement des trades...")
    trades = load_trades()
    print(f"[OK] {len(trades)} trades charges")

    # Calculer toutes les metriques
    print("[...] Calcul des metriques...")
    gm = compute_global_metrics(trades)
    am = compute_advanced_metrics(gm)
    sessions = compute_session_analysis(trades)
    dirs = compute_direction_analysis(trades)
    equity = compute_equity_data(trades)
    risk = compute_risk_analysis(trades, gm)
    sizing = compute_sizing_analysis(trades)
    exits = compute_exit_analysis(trades)
    dist = compute_pnl_distribution(gm)
    weekdays = compute_weekday_analysis(trades)
    print("[OK] Metriques calculees")

    # Generer le rapport texte
    print("[...] Generation du rapport...")
    report = generate_report(gm, am, sessions, dirs, risk, sizing, exits, dist, weekdays, config)

    # Afficher le rapport dans la console
    print()
    print(report)
    print()

    # Archiver
    print("[...] Archivage des resultats...")
    archive_path = build_archive_path(config)
    archive_results(archive_path, report, config)

    # Generer la courbe d'equity
    print("[...] Generation de la courbe d'equity...")
    chart_path = archive_path / "equity_curve.png"
    generate_equity_chart(equity, chart_path)
    print(f"[OK] Graphique sauvegarde : {chart_path}")

    # Mettre a jour l'index
    print("[...] Mise a jour de l'index...")
    update_index(config, gm, am, archive_path, trades)
    print(f"[OK] Index mis a jour : {INDEX_CSV}")

    print()
    print(f"[OK] Archive complete dans : {archive_path}")
    print("=" * 60)

    return gm, am


if __name__ == '__main__':
    run_metrics()
