# ============================================================================
# BACKTEST_ENGINE.PY - Moteur de Simulation des Trades
# ============================================================================
#
# Ce module simule les trades barre par barre en combinant :
#   - Les signaux d'entree bases sur le Z-Score (comme signals.py)
#   - Les sorties Z-Score (TP/SL Z-Score)
#   - Les sorties en dollars (TP $400 / SL -$800)
#
# Priorite des sorties (la premiere condition vraie declenche la sortie) :
#   1. SL Dollars   (protection du capital - priorite maximale)
#   2. SL Z-Score   (spread diverge trop)
#   3. TP Dollars   (objectif de profit atteint)
#   4. TP Z-Score   (spread revient a la moyenne)
#
# Gestion intra-barre (High/Low) :
#   Pour les sorties en dollars, on utilise les prix High et Low de chaque
#   barre pour detecter si le SL/TP a ete touche PENDANT la barre,
#   meme si le prix de cloture ne l'atteint pas.
#   Quand le SL/TP dollar est touche en intra-barre, le PnL de sortie
#   est fixe au seuil exact (-$800 ou +$400) car en live le stop
#   se serait declenche a ce niveau.
#
# Difference avec signals.py :
#   signals.py ne connait pas le PnL en dollars (il ne gere que le Z-Score).
#   backtest_engine.py calcule le PnL reel a chaque barre et peut couper
#   un trade AVANT que le Z-Score n'atteigne son seuil de sortie.
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import numpy as np
import pandas as pd
from typing import Tuple

from position import calculate_position_size, calculate_transaction_costs
try:
    from common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
        check_entry_conditions, check_cooldown_reset,
        calculate_current_pnl
    )
except ImportError:
    from .common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
        check_entry_conditions, check_cooldown_reset,
        calculate_current_pnl
    )


# ============================================================================
# VERIFICATION DES CONDITIONS DE SORTIE (Z-Score + Dollars)
# ============================================================================

def check_exit_conditions(
    zscore: float,
    current_pnl: float,
    state: int,
    config: dict
) -> Tuple[bool, str]:
    """
    Verifie toutes les conditions de sortie (Z-Score ET dollars).

    Priorite :
      1. SL Dollars  -> protection capitale (priorite max)
      2. SL Z-Score  -> spread diverge trop
      3. TP Dollars  -> objectif atteint
      4. TP Z-Score  -> retour a la moyenne

    Parametres:
    -----------
    zscore : float
        Z-Score actuel
    current_pnl : float
        PnL brut courant en dollars
    state : int
        Etat actuel (LONG ou SHORT)
    config : dict
        Configuration

    Retourne:
    ---------
    Tuple[bool, str] : (doit_sortir, raison)
    """
    pnl_tp = config['exit']['pnl_take_profit']    # +400
    pnl_sl = config['exit']['pnl_stop_loss']       # -800

    # 1. SL Dollars (priorite maximale)
    if current_pnl <= pnl_sl:
        return True, 'SL_DOLLAR'

    # 2. SL Z-Score
    if state == STATE_LONG:
        if zscore <= config['exit']['zscore_sl_long']:
            return True, 'SL_ZSCORE'
    elif state == STATE_SHORT:
        if zscore >= config['exit']['zscore_sl_short']:
            return True, 'SL_ZSCORE'

    # 3. TP Dollars
    if current_pnl >= pnl_tp:
        return True, 'TP_DOLLAR'

    # 4. TP Z-Score
    if state == STATE_LONG:
        if zscore >= config['exit']['zscore_tp_long']:
            return True, 'TP_ZSCORE'
    elif state == STATE_SHORT:
        if zscore <= config['exit']['zscore_tp_short']:
            return True, 'TP_ZSCORE'

    return False, ''




# ============================================================================
# MOTEUR DE BACKTEST PRINCIPAL
# ============================================================================

def run_backtest(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Fonction principale : simule tous les trades barre par barre.

    Parcourt les donnees minute par minute et :
    - Detecte les entrees (memes conditions que signals.py)
    - Calcule le PnL courant a chaque barre
    - Verifie les sorties Z-Score ET dollars
    - Enregistre chaque trade avec tous les details

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec les indicateurs calcules (sortie de indicators.py)
        Colonnes requises : ZScore, Correlation, Cointegration_Score,
                           Last_GC, Last_SI, Beta
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    pd.DataFrame : Liste des trades avec colonnes :
        Trade_No, Direction, Entry_DateTime, Exit_DateTime, Duration_Min,
        Entry_GC, Entry_SI, Exit_GC, Exit_SI, Entry_ZScore, Exit_ZScore,
        Exit_Reason, Beta, GC_Contracts, SI_Contracts,
        PnL_GC, PnL_SI, PnL_Gross, Costs, PnL_Net, PnL_Cumul,
        Max_PnL_Intra, Min_PnL_Intra
    """
    # Verification des colonnes requises
    required = ['ZScore', 'Correlation', 'Cointegration_Score',
                'Last_GC', 'Last_SI', 'Beta',
                'High_GC', 'Low_GC', 'High_SI', 'Low_SI']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes : {missing}")

    n = len(df)

    # Extraire les colonnes en numpy pour la performance
    zscores = df['ZScore'].values
    correlations = df['Correlation'].values
    coint_scores = df['Cointegration_Score'].values
    gc_prices = df['Last_GC'].values
    si_prices = df['Last_SI'].values
    gc_highs = df['High_GC'].values
    gc_lows = df['Low_GC'].values
    si_highs = df['High_SI'].values
    si_lows = df['Low_SI'].values
    betas = df['Beta'].values
    hursts = df['Hurst'].values if 'Hurst' in df.columns else np.full(n, np.nan)
    datetimes = df['DateTime'].values

    # Seuils de sortie en dollars
    pnl_tp = config['exit']['pnl_take_profit']    # +400
    pnl_sl = config['exit']['pnl_stop_loss']       # -800
    gc_pv = config['contracts']['gc_point_value']   # 100
    si_pv = config['contracts']['si_point_value']   # 5000

    # Variables d'etat
    state = STATE_FLAT
    trades = []
    trade_no = 0

    # Variables du trade en cours
    entry_idx = None
    direction = None
    gc_contracts = 0
    si_contracts = 0
    max_pnl_intra = 0.0
    min_pnl_intra = 0.0

    print("\n[...] Simulation du backtest...")

    for i in range(n):
        z = zscores[i]
        corr = correlations[i]
        score = coint_scores[i]
        gc = gc_prices[i]
        si = si_prices[i]
        beta = betas[i]

        # Ignorer les barres avec des donnees invalides
        if np.isnan(z) or np.isnan(corr) or np.isnan(score):
            continue

        # ---- ETAPE 1 : Verifier les sorties (si en position) ----
        if state in (STATE_LONG, STATE_SHORT):
            e_gc = gc_prices[entry_idx]
            e_si = si_prices[entry_idx]

            # --- 1a. Verifier les sorties DOLLAR en intra-barre (High/Low) ---
            # Calculer le pire et le meilleur PnL possible dans cette barre
            if direction == 1:
                # LONG spread : short GC (pire = GC High), long SI (pire = SI Low)
                worst_pnl = ((e_gc - gc_highs[i]) * gc_pv * gc_contracts +
                             (si_lows[i] - e_si) * si_pv * si_contracts)
                best_pnl = ((e_gc - gc_lows[i]) * gc_pv * gc_contracts +
                            (si_highs[i] - e_si) * si_pv * si_contracts)
            else:
                # SHORT spread : long GC (pire = GC Low), short SI (pire = SI High)
                worst_pnl = ((gc_lows[i] - e_gc) * gc_pv * gc_contracts +
                             (e_si - si_highs[i]) * si_pv * si_contracts)
                best_pnl = ((gc_highs[i] - e_gc) * gc_pv * gc_contracts +
                            (e_si - si_lows[i]) * si_pv * si_contracts)

            # Tracker le max/min PnL intra-trade
            if best_pnl > max_pnl_intra:
                max_pnl_intra = best_pnl
            if worst_pnl < min_pnl_intra:
                min_pnl_intra = worst_pnl

            # Verifier SL Dollar en intra-barre (PRIORITE MAX)
            # Si le pire PnL touche le SL, on sort a exactement le seuil
            if worst_pnl <= pnl_sl:
                trade_no += 1
                costs = calculate_transaction_costs(gc_contracts, si_contracts, config)
                # PnL fixe au seuil exact (en live le stop se declenche a -$800)
                pnl_gross = pnl_sl
                pnl_net = pnl_gross - costs['total_cost']

                entry_dt = pd.Timestamp(datetimes[entry_idx])
                exit_dt = pd.Timestamp(datetimes[i])
                duration = (exit_dt - entry_dt).total_seconds() / 60

                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_dt,
                    'Exit_DateTime': exit_dt,
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': e_gc,
                    'Entry_SI': e_si,
                    'Exit_GC': gc,
                    'Exit_SI': si,
                    'Entry_ZScore': round(zscores[entry_idx], 2),
                    'Exit_ZScore': round(z, 2),
                    'Exit_Reason': 'SL_DOLLAR',
                    'Beta': round(betas[entry_idx], 4),
                    'GC_Contracts': gc_contracts,
                    'SI_Contracts': si_contracts,
                    'PnL_GC': np.nan,
                    'PnL_SI': np.nan,
                    'PnL_Gross': round(pnl_gross, 2),
                    'Costs': costs['total_cost'],
                    'PnL_Net': round(pnl_net, 2),
                    'Max_PnL_Intra': round(max_pnl_intra, 2),
                    'Min_PnL_Intra': round(min_pnl_intra, 2),
                })

                if state == STATE_LONG:
                    state = STATE_COOLDOWN_LONG
                else:
                    state = STATE_COOLDOWN_SHORT
                entry_idx = None
                direction = None

                # Continuer a l'etape 2 (cooldown check)
                if state in (STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
                    if check_cooldown_reset(z, state, config):
                        state = STATE_FLAT

                # Verifier entree sur la meme barre
                if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
                    entry = check_entry_conditions(z, corr, score, state, config, hurst=hursts[i])
                    if entry != 0 and not np.isnan(beta):
                        size = calculate_position_size(gc, si, beta, config)
                        direction = entry
                        entry_idx = i
                        gc_contracts = size['gc_contracts']
                        si_contracts = size['si_contracts']
                        max_pnl_intra = 0.0
                        min_pnl_intra = 0.0
                        state = STATE_LONG if entry == 1 else STATE_SHORT
                continue

            # Verifier TP Dollar en intra-barre
            # On le verifie APRES le SL (le SL a la priorite)
            if best_pnl >= pnl_tp:
                trade_no += 1
                costs = calculate_transaction_costs(gc_contracts, si_contracts, config)
                # PnL fixe au seuil exact (en live le TP se declenche a +$400)
                pnl_gross = pnl_tp
                pnl_net = pnl_gross - costs['total_cost']

                entry_dt = pd.Timestamp(datetimes[entry_idx])
                exit_dt = pd.Timestamp(datetimes[i])
                duration = (exit_dt - entry_dt).total_seconds() / 60

                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_dt,
                    'Exit_DateTime': exit_dt,
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': e_gc,
                    'Entry_SI': e_si,
                    'Exit_GC': gc,
                    'Exit_SI': si,
                    'Entry_ZScore': round(zscores[entry_idx], 2),
                    'Exit_ZScore': round(z, 2),
                    'Exit_Reason': 'TP_DOLLAR',
                    'Beta': round(betas[entry_idx], 4),
                    'GC_Contracts': gc_contracts,
                    'SI_Contracts': si_contracts,
                    'PnL_GC': np.nan,
                    'PnL_SI': np.nan,
                    'PnL_Gross': round(pnl_gross, 2),
                    'Costs': costs['total_cost'],
                    'PnL_Net': round(pnl_net, 2),
                    'Max_PnL_Intra': round(max_pnl_intra, 2),
                    'Min_PnL_Intra': round(min_pnl_intra, 2),
                })

                state = STATE_FLAT
                entry_idx = None
                direction = None

                # Verifier entree sur la meme barre
                if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
                    entry = check_entry_conditions(z, corr, score, state, config, hurst=hursts[i])
                    if entry != 0 and not np.isnan(beta):
                        size = calculate_position_size(gc, si, beta, config)
                        direction = entry
                        entry_idx = i
                        gc_contracts = size['gc_contracts']
                        si_contracts = size['si_contracts']
                        max_pnl_intra = 0.0
                        min_pnl_intra = 0.0
                        state = STATE_LONG if entry == 1 else STATE_SHORT
                continue

            # --- 1b. Verifier les sorties Z-Score sur le prix de cloture ---
            current_pnl = calculate_current_pnl(
                direction, e_gc, e_si, gc, si,
                gc_contracts, si_contracts, config
            )

            should_exit, reason = check_exit_conditions(z, current_pnl, state, config)

            if should_exit:
                trade_no += 1
                costs = calculate_transaction_costs(gc_contracts, si_contracts, config)

                if direction == 1:
                    pnl_gc = (e_gc - gc) * gc_pv * gc_contracts
                    pnl_si = (si - e_si) * si_pv * si_contracts
                else:
                    pnl_gc = (gc - e_gc) * gc_pv * gc_contracts
                    pnl_si = (e_si - si) * si_pv * si_contracts

                pnl_gross = pnl_gc + pnl_si
                pnl_net = pnl_gross - costs['total_cost']

                entry_dt = pd.Timestamp(datetimes[entry_idx])
                exit_dt = pd.Timestamp(datetimes[i])
                duration = (exit_dt - entry_dt).total_seconds() / 60

                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_dt,
                    'Exit_DateTime': exit_dt,
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': e_gc,
                    'Entry_SI': e_si,
                    'Exit_GC': gc,
                    'Exit_SI': si,
                    'Entry_ZScore': round(zscores[entry_idx], 2),
                    'Exit_ZScore': round(z, 2),
                    'Exit_Reason': reason,
                    'Beta': round(betas[entry_idx], 4),
                    'GC_Contracts': gc_contracts,
                    'SI_Contracts': si_contracts,
                    'PnL_GC': round(pnl_gc, 2),
                    'PnL_SI': round(pnl_si, 2),
                    'PnL_Gross': round(pnl_gross, 2),
                    'Costs': costs['total_cost'],
                    'PnL_Net': round(pnl_net, 2),
                    'Max_PnL_Intra': round(max_pnl_intra, 2),
                    'Min_PnL_Intra': round(min_pnl_intra, 2),
                })

                if reason in ('SL_ZSCORE', 'SL_DOLLAR'):
                    if state == STATE_LONG:
                        state = STATE_COOLDOWN_LONG
                    else:
                        state = STATE_COOLDOWN_SHORT
                else:
                    state = STATE_FLAT

                entry_idx = None
                direction = None

        # ---- ETAPE 2 : Verifier le reset du cooldown ----
        if state in (STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            if check_cooldown_reset(z, state, config):
                state = STATE_FLAT

        # ---- ETAPE 3 : Verifier les entrees ----
        if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            entry = check_entry_conditions(z, corr, score, state, config, hurst=hursts[i])

            if entry != 0 and not np.isnan(beta):
                # Calculer le sizing
                size = calculate_position_size(gc, si, beta, config)

                direction = entry
                entry_idx = i
                gc_contracts = size['gc_contracts']
                si_contracts = size['si_contracts']
                max_pnl_intra = 0.0
                min_pnl_intra = 0.0

                if entry == 1:
                    state = STATE_LONG
                else:
                    state = STATE_SHORT

    # Si un trade est encore ouvert a la fin
    if entry_idx is not None:
        trade_no += 1
        last_i = n - 1
        gc = gc_prices[last_i]
        si = si_prices[last_i]

        costs = calculate_transaction_costs(gc_contracts, si_contracts, config)
        gc_pv = config['contracts']['gc_point_value']
        si_pv = config['contracts']['si_point_value']

        if direction == 1:
            pnl_gc = (gc_prices[entry_idx] - gc) * gc_pv * gc_contracts
            pnl_si = (si - si_prices[entry_idx]) * si_pv * si_contracts
        else:
            pnl_gc = (gc - gc_prices[entry_idx]) * gc_pv * gc_contracts
            pnl_si = (si_prices[entry_idx] - si) * si_pv * si_contracts

        pnl_gross = pnl_gc + pnl_si
        pnl_net = pnl_gross - costs['total_cost']

        entry_dt = pd.Timestamp(datetimes[entry_idx])
        exit_dt = pd.Timestamp(datetimes[last_i])
        duration = (exit_dt - entry_dt).total_seconds() / 60

        trades.append({
            'Trade_No': trade_no,
            'Direction': 'LONG' if direction == 1 else 'SHORT',
            'Entry_DateTime': entry_dt,
            'Exit_DateTime': exit_dt,
            'Duration_Min': round(duration, 1),
            'Entry_GC': gc_prices[entry_idx],
            'Entry_SI': si_prices[entry_idx],
            'Exit_GC': gc,
            'Exit_SI': si,
            'Entry_ZScore': round(zscores[entry_idx], 2),
            'Exit_ZScore': round(zscores[last_i], 2),
            'Exit_Reason': 'STILL_OPEN',
            'Beta': round(betas[entry_idx], 4),
            'GC_Contracts': gc_contracts,
            'SI_Contracts': si_contracts,
            'PnL_GC': round(pnl_gc, 2),
            'PnL_SI': round(pnl_si, 2),
            'PnL_Gross': round(pnl_gross, 2),
            'Costs': costs['total_cost'],
            'PnL_Net': round(pnl_net, 2),
            'Max_PnL_Intra': round(max_pnl_intra, 2),
            'Min_PnL_Intra': round(min_pnl_intra, 2),
        })

    # Construire le DataFrame
    trades_df = pd.DataFrame(trades)

    if len(trades_df) > 0:
        trades_df['PnL_Cumul'] = trades_df['PnL_Net'].cumsum().round(2)

    # Statistiques
    n_long = (trades_df['Direction'] == 'LONG').sum() if len(trades_df) > 0 else 0
    n_short = (trades_df['Direction'] == 'SHORT').sum() if len(trades_df) > 0 else 0

    print(f"   Trades total  : {len(trades_df)} ({n_long} LONG, {n_short} SHORT)")

    if len(trades_df) > 0:
        for reason in ['TP_ZSCORE', 'TP_DOLLAR', 'SL_ZSCORE', 'SL_DOLLAR', 'STILL_OPEN']:
            count = (trades_df['Exit_Reason'] == reason).sum()
            if count > 0:
                print(f"   {reason:12s} : {count}")

    print("   [OK] Backtest termine !")

    return trades_df


# ============================================================================
# EXPORT DES RESULTATS
# ============================================================================

def export_backtest(
    trades_df: pd.DataFrame,
    filepath: str = "output/backtest_trades.csv"
):
    """
    Exporte les resultats du backtest dans un fichier CSV.

    Parametres:
    -----------
    trades_df : pd.DataFrame
        Resultats du backtest (sortie de run_backtest)
    filepath : str
        Chemin du fichier de sortie
    """
    from pathlib import Path
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    trades_df.to_csv(filepath, index=False, sep=';')
    print(f"   [OK] {len(trades_df)} trades exportes dans : {filepath}")


# ============================================================================
# AFFICHAGE DU RESUME
# ============================================================================

def print_backtest_summary(trades_df: pd.DataFrame):
    """
    Affiche un resume complet des resultats du backtest.

    Parametres:
    -----------
    trades_df : pd.DataFrame
        Resultats du backtest (sortie de run_backtest)
    """
    if len(trades_df) == 0:
        print("   Aucun trade a afficher.")
        return

    n = len(trades_df)
    winners = trades_df[trades_df['PnL_Net'] > 0]
    losers = trades_df[trades_df['PnL_Net'] <= 0]

    print("\n" + "="*60)
    print("RESULTATS DU BACKTEST")
    print("="*60)

    # Global
    print("\n   --- GLOBAL ---")
    print(f"   Trades total     : {n}")
    print(f"   Gagnants         : {len(winners)} ({len(winners)/n*100:.1f}%)")
    print(f"   Perdants         : {len(losers)} ({len(losers)/n*100:.1f}%)")

    print(f"\n   PnL brut total   : ${trades_df['PnL_Gross'].sum():+,.2f}")
    print(f"   Couts totaux     : -${trades_df['Costs'].sum():,.2f}")
    print(f"   PnL net total    : ${trades_df['PnL_Net'].sum():+,.2f}")

    print(f"\n   PnL moyen/trade  : ${trades_df['PnL_Net'].mean():+,.2f}")
    if len(winners) > 0:
        print(f"   Gain moyen       : ${winners['PnL_Net'].mean():+,.2f}")
    if len(losers) > 0:
        print(f"   Perte moyenne    : ${losers['PnL_Net'].mean():+,.2f}")

    print(f"\n   Meilleur trade   : ${trades_df['PnL_Net'].max():+,.2f}")
    print(f"   Pire trade       : ${trades_df['PnL_Net'].min():+,.2f}")

    # Drawdown
    cumul = trades_df['PnL_Cumul']
    peak = cumul.cummax()
    drawdown = cumul - peak
    print(f"\n   PnL cumule final : ${cumul.iloc[-1]:+,.2f}")
    print(f"   Max Drawdown     : ${drawdown.min():+,.2f}")

    # Profit factor
    gross_profit = winners['PnL_Net'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['PnL_Net'].sum()) if len(losers) > 0 else 0
    if gross_loss > 0:
        print(f"   Profit Factor    : {gross_profit / gross_loss:.2f}")

    # Par direction
    print("\n   --- PAR DIRECTION ---")
    for d in ['LONG', 'SHORT']:
        sub = trades_df[trades_df['Direction'] == d]
        if len(sub) > 0:
            wins = (sub['PnL_Net'] > 0).sum()
            print(f"   {d:5s} : {len(sub)} trades | Win: {wins}/{len(sub)} "
                  f"({wins/len(sub)*100:.0f}%) | PnL: ${sub['PnL_Net'].sum():+,.2f}")

    # Par type de sortie
    print("\n   --- PAR TYPE DE SORTIE ---")
    for reason in ['TP_ZSCORE', 'TP_DOLLAR', 'SL_ZSCORE', 'SL_DOLLAR']:
        sub = trades_df[trades_df['Exit_Reason'] == reason]
        if len(sub) > 0:
            print(f"   {reason:12s} : {len(sub):2d} trades | PnL: ${sub['PnL_Net'].sum():+,.2f} "
                  f"| Moy: ${sub['PnL_Net'].mean():+,.2f}")

    # Par nombre de contrats GC
    print("\n   --- PAR SIZING (GC CONTRACTS) ---")
    for gc in sorted(trades_df['GC_Contracts'].unique()):
        sub = trades_df[trades_df['GC_Contracts'] == gc]
        wins = (sub['PnL_Net'] > 0).sum()
        print(f"   {gc} GC : {len(sub):2d} trades | Win: {wins}/{len(sub)} "
              f"| PnL: ${sub['PnL_Net'].sum():+,.2f} | Moy: ${sub['PnL_Net'].mean():+,.2f}")

    # Duree moyenne
    print(f"\n   --- DUREE ---")
    print(f"   Duree moyenne    : {trades_df['Duration_Min'].mean():.1f} min")
    print(f"   Duree mediane    : {trades_df['Duration_Min'].median():.1f} min")
    print(f"   Duree max        : {trades_df['Duration_Min'].max():.1f} min")

    print("\n" + "="*60)


# ============================================================================
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du moteur de backtest.

    Pour executer :
        python src/backtest_engine.py
    """
    from data_loader import load_and_prepare_data
    from indicators import calculate_all_indicators

    print("\n" + "="*60)
    print("BACKTEST ENGINE - SIMULATION COMPLETE")
    print("="*60)

    try:
        # 1. Charger les donnees
        df, config, stats = load_and_prepare_data(verbose=False)
        print(f"[OK] Donnees chargees : {len(df)} barres")

        # 2. Calculer les indicateurs
        df = calculate_all_indicators(df, config)
        print(f"[OK] Indicateurs calcules")

        # 3. Lancer le backtest
        trades_df = run_backtest(df, config)

        # 4. Afficher le resume
        print_backtest_summary(trades_df)

        # 5. Exporter
        export_backtest(trades_df, "output/backtest_trades.csv")

        # 6. Afficher les 10 premiers trades
        print("\n" + "="*60)
        print("LISTE DES TRADES (10 premiers)")
        print("="*60)
        for _, t in trades_df.head(10).iterrows():
            print(f"\n   Trade #{t['Trade_No']} - {t['Direction']} ({t['Exit_Reason']})")
            print(f"   {t['Entry_DateTime']} -> {t['Exit_DateTime']} ({t['Duration_Min']:.0f} min)")
            print(f"   GC: {t['Entry_GC']:.2f} -> {t['Exit_GC']:.2f} ({t['GC_Contracts']} ct)")
            print(f"   SI: {t['Entry_SI']:.3f} -> {t['Exit_SI']:.3f} ({t['SI_Contracts']} ct)")
            print(f"   Z:  {t['Entry_ZScore']:+.2f} -> {t['Exit_ZScore']:+.2f} | Beta: {t['Beta']:.4f}")
            print(f"   PnL: GC ${t['PnL_GC']:+,.0f} + SI ${t['PnL_SI']:+,.0f} "
                  f"= ${t['PnL_Gross']:+,.0f} - ${t['Costs']:.0f} = NET ${t['PnL_Net']:+,.0f} "
                  f"(cumul: ${t['PnL_Cumul']:+,.0f})")

        print("\n" + "="*60)
        print("[OK] Backtest termine avec succes !")
        print("="*60)

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
