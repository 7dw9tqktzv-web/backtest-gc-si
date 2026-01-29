# ============================================================================
# BACKTEST_ENGINE_HYBRID.PY - Approche A : Hybride 1min + 5s
# ============================================================================
#
# Principe :
#   - Les signaux d'entree/sortie Z-Score sont calcules sur barres 1-minute
#     (meme pipeline que backtest_engine.py)
#   - Quand on est en position, on surveille le PnL sur barres 5 secondes
#     pour detecter les sorties TP Dollar (+$400) et SL Dollar (-$800)
#   - Si aucun trigger dollar sur les barres 5s, on verifie les sorties
#     Z-Score sur la barre 1-minute suivante
#
# Avantage : precision des exits en dollars sans recalculer les indicateurs
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import numpy as np
import pandas as pd
from typing import Tuple
from pathlib import Path

from data_loader import load_and_prepare_data, load_config
from data_loader_5s import load_5s_data
from indicators import calculate_all_indicators
from position import calculate_position_size, calculate_transaction_costs


# ============================================================================
# CONSTANTES D'ETATS (identiques a signals.py / backtest_engine.py)
# ============================================================================

STATE_FLAT = 0
STATE_LONG = 1
STATE_SHORT = -1
STATE_COOLDOWN_LONG = 2
STATE_COOLDOWN_SHORT = -2


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def calculate_current_pnl(
    direction: int,
    entry_gc: float,
    entry_si: float,
    current_gc: float,
    current_si: float,
    gc_contracts: int,
    si_contracts: int,
    config: dict
) -> float:
    """
    Calcule le PnL brut courant d'une position ouverte.
    Identique a backtest_engine.py.
    """
    gc_pv = config['contracts']['gc_point_value']   # 100
    si_pv = config['contracts']['si_point_value']   # 5000

    if direction == 1:
        # LONG spread : long SI, short GC
        pnl_si = (current_si - entry_si) * si_pv * si_contracts
        pnl_gc = (entry_gc - current_gc) * gc_pv * gc_contracts
    else:
        # SHORT spread : short SI, long GC
        pnl_si = (entry_si - current_si) * si_pv * si_contracts
        pnl_gc = (current_gc - entry_gc) * gc_pv * gc_contracts

    return pnl_gc + pnl_si


def check_entry_conditions(
    zscore: float,
    correlation: float,
    cointegration_score: float,
    state: int,
    config: dict
) -> int:
    """
    Verifie les conditions d'entree (identique a backtest_engine.py).
    Retourne 1 (LONG), -1 (SHORT), ou 0 (pas d'entree).
    """
    z_long = config['entry']['zscore_long']
    z_short = config['entry']['zscore_short']
    corr_min = config['entry']['correlation_min']
    score_min = config['entry']['cointegration_score_min']

    quality_ok = (correlation > corr_min) and (cointegration_score >= score_min)
    if not quality_ok:
        return 0

    if zscore <= z_long and state not in (STATE_LONG, STATE_SHORT, STATE_COOLDOWN_LONG):
        return 1

    if zscore >= z_short and state not in (STATE_LONG, STATE_SHORT, STATE_COOLDOWN_SHORT):
        return -1

    return 0


def check_zscore_exit(zscore: float, state: int, config: dict) -> Tuple[bool, str]:
    """
    Verifie uniquement les sorties Z-Score (pas les dollars).
    Les sorties dollars sont gerees via les barres 5s.
    """
    if state == STATE_LONG:
        if zscore <= config['exit']['zscore_sl_long']:
            return True, 'SL_ZSCORE'
        if zscore >= config['exit']['zscore_tp_long']:
            return True, 'TP_ZSCORE'
    elif state == STATE_SHORT:
        if zscore >= config['exit']['zscore_sl_short']:
            return True, 'SL_ZSCORE'
        if zscore <= config['exit']['zscore_tp_short']:
            return True, 'TP_ZSCORE'
    return False, ''


def check_cooldown_reset(zscore: float, state: int, config: dict) -> bool:
    """Verifie si le cooldown est termine."""
    if state == STATE_COOLDOWN_LONG:
        return zscore >= config['reentry']['zscore_reset_long']
    elif state == STATE_COOLDOWN_SHORT:
        return zscore <= config['reentry']['zscore_reset_short']
    return False


# ============================================================================
# MOTEUR DE BACKTEST HYBRIDE
# ============================================================================

def run_hybrid_backtest(
    df_1min: pd.DataFrame,
    df_5s: pd.DataFrame,
    config: dict
) -> pd.DataFrame:
    """
    Backtest hybride : signaux 1-min + suivi PnL sur barres 5s.

    Logique :
    - On itere barre par barre sur le df_1min
    - Les entrees et sorties Z-Score sont evaluees sur les barres 1-min
    - Quand on est en position, on recupere les barres 5s dans l'intervalle
      [barre_1min_precedente, barre_1min_courante] pour surveiller le PnL
    - Si le PnL touche SL (-$800) ou TP (+$400) sur une barre 5s, on sort
      au seuil exact
    - Si aucun trigger 5s, on verifie les sorties Z-Score sur la barre 1-min

    Parametres:
    -----------
    df_1min : pd.DataFrame
        Donnees 1-minute avec indicateurs calcules
    df_5s : pd.DataFrame
        Donnees 5-secondes synchronisees (colonnes: DateTime, Last_GC, Last_SI)
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    pd.DataFrame : Liste des trades
    """
    # Verification des colonnes requises
    required_1min = ['ZScore', 'Correlation', 'Cointegration_Score',
                     'Last_GC', 'Last_SI', 'Beta']
    missing = [col for col in required_1min if col not in df_1min.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans df_1min : {missing}")

    n = len(df_1min)

    # Extraire les colonnes 1-min en numpy
    zscores = df_1min['ZScore'].values
    correlations = df_1min['Correlation'].values
    coint_scores = df_1min['Cointegration_Score'].values
    gc_prices = df_1min['Last_GC'].values
    si_prices = df_1min['Last_SI'].values
    betas = df_1min['Beta'].values
    datetimes_1min = df_1min['DateTime'].values

    # Preparer les donnees 5s pour acces rapide
    # On cree un index pour retrouver les barres 5s entre deux barres 1-min
    dt_5s = df_5s['DateTime'].values
    gc_5s = df_5s['Last_GC'].values
    si_5s = df_5s['Last_SI'].values

    # Seuils de sortie en dollars
    pnl_tp = config['exit']['pnl_take_profit']    # +400
    pnl_sl = config['exit']['pnl_stop_loss']       # -800

    # Variables d'etat
    state = STATE_FLAT
    trades = []
    trade_no = 0

    # Variables du trade en cours
    entry_1min_idx = None
    direction = None
    gc_contracts = 0
    si_contracts = 0
    entry_gc = 0.0
    entry_si = 0.0
    max_pnl_intra = 0.0
    min_pnl_intra = 0.0

    # Index courant dans les barres 5s (pour eviter de re-scanner depuis le debut)
    idx_5s_start = 0

    print("\n[...] Simulation du backtest hybride (1min + 5s)...")

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

        # ---- ETAPE 1 : Si en position, verifier les sorties ----
        if state in (STATE_LONG, STATE_SHORT):

            # --- 1a. Verifier les sorties DOLLAR sur barres 5s ---
            # Trouver les barres 5s entre la barre 1-min precedente et la courante
            if i > 0:
                t_prev = datetimes_1min[i - 1]
            else:
                t_prev = datetimes_1min[i]
            t_curr = datetimes_1min[i]

            # Avancer idx_5s_start pour ne pas re-scanner les anciennes barres
            while idx_5s_start < len(dt_5s) and dt_5s[idx_5s_start] < t_prev:
                idx_5s_start += 1

            # Scanner les barres 5s dans l'intervalle (t_prev, t_curr]
            dollar_exit = False
            dollar_reason = ''
            dollar_exit_dt = None
            dollar_exit_gc = 0.0
            dollar_exit_si = 0.0

            j = idx_5s_start
            while j < len(dt_5s) and dt_5s[j] <= t_curr:
                pnl_5s = calculate_current_pnl(
                    direction, entry_gc, entry_si,
                    gc_5s[j], si_5s[j],
                    gc_contracts, si_contracts, config
                )

                # Tracker max/min PnL intra-trade
                if pnl_5s > max_pnl_intra:
                    max_pnl_intra = pnl_5s
                if pnl_5s < min_pnl_intra:
                    min_pnl_intra = pnl_5s

                # Verifier SL Dollar (priorite max)
                if pnl_5s <= pnl_sl:
                    dollar_exit = True
                    dollar_reason = 'SL_DOLLAR'
                    dollar_exit_dt = dt_5s[j]
                    dollar_exit_gc = gc_5s[j]
                    dollar_exit_si = si_5s[j]
                    break

                # Verifier TP Dollar
                if pnl_5s >= pnl_tp:
                    dollar_exit = True
                    dollar_reason = 'TP_DOLLAR'
                    dollar_exit_dt = dt_5s[j]
                    dollar_exit_gc = gc_5s[j]
                    dollar_exit_si = si_5s[j]
                    break

                j += 1

            if dollar_exit:
                # Enregistrer le trade avec sortie dollar
                trade_no += 1
                costs = calculate_transaction_costs(gc_contracts, si_contracts, config)

                # PnL fixe au seuil exact
                if dollar_reason == 'SL_DOLLAR':
                    pnl_gross = pnl_sl
                else:
                    pnl_gross = pnl_tp
                pnl_net = pnl_gross - costs['total_cost']

                entry_dt = pd.Timestamp(datetimes_1min[entry_1min_idx])
                exit_dt = pd.Timestamp(dollar_exit_dt)
                duration = (exit_dt - entry_dt).total_seconds() / 60

                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_dt,
                    'Exit_DateTime': exit_dt,
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': entry_gc,
                    'Entry_SI': entry_si,
                    'Exit_GC': round(dollar_exit_gc, 2),
                    'Exit_SI': round(dollar_exit_si, 4),
                    'Entry_ZScore': round(zscores[entry_1min_idx], 2),
                    'Exit_ZScore': round(z, 2),
                    'Exit_Reason': dollar_reason,
                    'Beta': round(betas[entry_1min_idx], 4),
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

                # Transition d'etat
                if dollar_reason == 'SL_DOLLAR':
                    state = STATE_COOLDOWN_LONG if direction == 1 else STATE_COOLDOWN_SHORT
                else:
                    state = STATE_FLAT

                entry_1min_idx = None
                direction = None

                # Verifier cooldown reset + reentree sur la meme barre 1-min
                if state in (STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
                    if check_cooldown_reset(z, state, config):
                        state = STATE_FLAT

                if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
                    entry = check_entry_conditions(z, corr, score, state, config)
                    if entry != 0 and not np.isnan(beta):
                        size = calculate_position_size(gc, si, beta, config)
                        direction = entry
                        entry_1min_idx = i
                        entry_gc = gc
                        entry_si = si
                        gc_contracts = size['gc_contracts']
                        si_contracts = size['si_contracts']
                        max_pnl_intra = 0.0
                        min_pnl_intra = 0.0
                        state = STATE_LONG if entry == 1 else STATE_SHORT
                continue

            # --- 1b. Pas de trigger 5s -> verifier sorties Z-Score sur barre 1-min ---
            # Aussi tracker le PnL sur le prix de cloture 1-min
            current_pnl = calculate_current_pnl(
                direction, entry_gc, entry_si, gc, si,
                gc_contracts, si_contracts, config
            )
            if current_pnl > max_pnl_intra:
                max_pnl_intra = current_pnl
            if current_pnl < min_pnl_intra:
                min_pnl_intra = current_pnl

            should_exit, reason = check_zscore_exit(z, state, config)

            if should_exit:
                trade_no += 1
                costs = calculate_transaction_costs(gc_contracts, si_contracts, config)

                gc_pv = config['contracts']['gc_point_value']
                si_pv = config['contracts']['si_point_value']

                if direction == 1:
                    pnl_gc = (entry_gc - gc) * gc_pv * gc_contracts
                    pnl_si = (si - entry_si) * si_pv * si_contracts
                else:
                    pnl_gc = (gc - entry_gc) * gc_pv * gc_contracts
                    pnl_si = (entry_si - si) * si_pv * si_contracts

                pnl_gross = pnl_gc + pnl_si
                pnl_net = pnl_gross - costs['total_cost']

                entry_dt = pd.Timestamp(datetimes_1min[entry_1min_idx])
                exit_dt = pd.Timestamp(datetimes_1min[i])
                duration = (exit_dt - entry_dt).total_seconds() / 60

                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_dt,
                    'Exit_DateTime': exit_dt,
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': entry_gc,
                    'Entry_SI': entry_si,
                    'Exit_GC': gc,
                    'Exit_SI': si,
                    'Entry_ZScore': round(zscores[entry_1min_idx], 2),
                    'Exit_ZScore': round(z, 2),
                    'Exit_Reason': reason,
                    'Beta': round(betas[entry_1min_idx], 4),
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

                if reason in ('SL_ZSCORE',):
                    state = STATE_COOLDOWN_LONG if direction == 1 else STATE_COOLDOWN_SHORT
                else:
                    state = STATE_FLAT

                entry_1min_idx = None
                direction = None

        # ---- ETAPE 2 : Verifier le reset du cooldown ----
        if state in (STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            if check_cooldown_reset(z, state, config):
                state = STATE_FLAT

        # ---- ETAPE 3 : Verifier les entrees ----
        if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            entry = check_entry_conditions(z, corr, score, state, config)

            if entry != 0 and not np.isnan(beta):
                size = calculate_position_size(gc, si, beta, config)
                direction = entry
                entry_1min_idx = i
                entry_gc = gc
                entry_si = si
                gc_contracts = size['gc_contracts']
                si_contracts = size['si_contracts']
                max_pnl_intra = 0.0
                min_pnl_intra = 0.0
                state = STATE_LONG if entry == 1 else STATE_SHORT

    # Si un trade est encore ouvert a la fin
    if entry_1min_idx is not None:
        trade_no += 1
        last_i = n - 1
        gc = gc_prices[last_i]
        si = si_prices[last_i]

        costs = calculate_transaction_costs(gc_contracts, si_contracts, config)
        gc_pv = config['contracts']['gc_point_value']
        si_pv = config['contracts']['si_point_value']

        if direction == 1:
            pnl_gc = (entry_gc - gc) * gc_pv * gc_contracts
            pnl_si = (si - entry_si) * si_pv * si_contracts
        else:
            pnl_gc = (gc - entry_gc) * gc_pv * gc_contracts
            pnl_si = (entry_si - si) * si_pv * si_contracts

        pnl_gross = pnl_gc + pnl_si
        pnl_net = pnl_gross - costs['total_cost']

        entry_dt = pd.Timestamp(datetimes_1min[entry_1min_idx])
        exit_dt = pd.Timestamp(datetimes_1min[last_i])
        duration = (exit_dt - entry_dt).total_seconds() / 60

        trades.append({
            'Trade_No': trade_no,
            'Direction': 'LONG' if direction == 1 else 'SHORT',
            'Entry_DateTime': entry_dt,
            'Exit_DateTime': exit_dt,
            'Duration_Min': round(duration, 1),
            'Entry_GC': entry_gc,
            'Entry_SI': entry_si,
            'Exit_GC': gc,
            'Exit_SI': si,
            'Entry_ZScore': round(zscores[entry_1min_idx], 2),
            'Exit_ZScore': round(zscores[last_i], 2),
            'Exit_Reason': 'STILL_OPEN',
            'Beta': round(betas[entry_1min_idx], 4),
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

    print("   [OK] Backtest hybride termine !")

    return trades_df


# ============================================================================
# EXPORT ET AFFICHAGE
# ============================================================================

def export_backtest(trades_df: pd.DataFrame, filepath: str = "output/backtest_hybrid.csv"):
    """Exporte les resultats du backtest hybride dans un fichier CSV."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(filepath, index=False, sep=';')
    print(f"   [OK] {len(trades_df)} trades exportes dans : {filepath}")


def print_backtest_summary(trades_df: pd.DataFrame, title: str = "BACKTEST HYBRIDE"):
    """Affiche un resume des resultats."""
    if len(trades_df) == 0:
        print("   Aucun trade a afficher.")
        return

    n = len(trades_df)
    winners = trades_df[trades_df['PnL_Net'] > 0]
    losers = trades_df[trades_df['PnL_Net'] <= 0]

    print("\n" + "="*60)
    print(f"RESULTATS - {title}")
    print("="*60)

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

    # Par sizing
    print("\n   --- PAR SIZING (GC CONTRACTS) ---")
    for gc in sorted(trades_df['GC_Contracts'].unique()):
        sub = trades_df[trades_df['GC_Contracts'] == gc]
        wins = (sub['PnL_Net'] > 0).sum()
        print(f"   {gc} GC : {len(sub):2d} trades | Win: {wins}/{len(sub)} "
              f"| PnL: ${sub['PnL_Net'].sum():+,.2f} | Moy: ${sub['PnL_Net'].mean():+,.2f}")

    # Duree
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
    Backtest hybride : signaux 1-min + suivi PnL 5s.

    Pour executer :
        python src/backtest_engine_hybrid.py
    """
    print("\n" + "="*60)
    print("BACKTEST HYBRIDE - APPROCHE A (1min + 5s)")
    print("="*60)

    try:
        # 1. Charger les donnees 1-minute et la config
        df_1min, config, stats = load_and_prepare_data(verbose=False)
        print(f"[OK] Donnees 1-min chargees : {len(df_1min)} barres")

        # 2. Calculer les indicateurs sur 1-minute
        df_1min = calculate_all_indicators(df_1min, config)
        print(f"[OK] Indicateurs 1-min calcules")

        # 3. Charger les donnees 5-secondes
        df_5s = load_5s_data(config, verbose=True)

        # 4. Lancer le backtest hybride
        trades_df = run_hybrid_backtest(df_1min, df_5s, config)

        # 5. Afficher le resume
        print_backtest_summary(trades_df, "BACKTEST HYBRIDE (1min + 5s)")

        # 6. Exporter
        export_backtest(trades_df, "output/backtest_hybrid.csv")

        print("\n[OK] Backtest hybride termine avec succes !")

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
