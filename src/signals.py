# ============================================================================
# SIGNALS.PY - Generation des Signaux d'Entree/Sortie (Z-Score)
# ============================================================================
#
# Ce module genere les signaux de trading bases sur le Z-Score.
# Il gere un automate d'etats (state machine) avec 5 etats possibles :
#
#   FLAT (0)            -> Pas de position ouverte
#   LONG (1)            -> Position LONG spread ouverte
#   SHORT (-1)          -> Position SHORT spread ouverte
#   COOLDOWN_LONG (2)   -> Attente reset Z-Score apres SL LONG
#   COOLDOWN_SHORT (-2) -> Attente reset Z-Score apres SL SHORT
#
# Architecture :
#   Ce module gere uniquement les signaux bases sur le Z-Score.
#   Les sorties en dollars (TP/SL $) sont gerees dans backtest_engine.py
#   car elles necessitent le PnL reel de la position.
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import pandas as pd
import numpy as np

try:
    from common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
        check_entry_conditions, check_zscore_exit, check_cooldown_reset
    )
except ImportError:
    from .common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
        check_entry_conditions, check_zscore_exit, check_cooldown_reset
    )

# Colonnes requises pour generate_signals()
REQUIRED_COLUMNS = ['ZScore', 'Correlation', 'Cointegration_Score']


# ============================================================================
# FONCTION PRINCIPALE DE GENERATION DES SIGNAUX
# ============================================================================

def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Fonction principale : parcourt les donnees barre par barre et genere
    tous les signaux d'entree/sortie bases sur le Z-Score.

    C'est un automate d'etats (state machine) qui simule le comportement
    de l'indicateur Sierra Chart v1.4 :

        FLAT -> (conditions entree) -> LONG ou SHORT
        LONG -> (TP Z-Score)        -> FLAT (reentree immediate possible)
        LONG -> (SL Z-Score)        -> COOLDOWN_LONG (attente reset)
        SHORT -> (TP Z-Score)       -> FLAT
        SHORT -> (SL Z-Score)       -> COOLDOWN_SHORT
        COOLDOWN_LONG -> (reset)    -> FLAT
        COOLDOWN_SHORT -> (reset)   -> FLAT

    Le reversal est possible : LONG -> TP -> SHORT sur la meme barre.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec les indicateurs calcules (sortie de indicators.py)
        Colonnes requises : ZScore, Correlation, Cointegration_Score
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec les colonnes de signaux ajoutees :
        - Signal : 1 (entree LONG), -1 (entree SHORT), 0 (rien)
        - Exit_Signal : 1 (sortie), 0 (pas de sortie)
        - Exit_Reason : 'TP_ZSCORE', 'SL_ZSCORE', ou NaN
        - State : Etat de la machine a etats (pour debug)
    """
    # Verification des colonnes requises
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans le DataFrame : {missing}. "
            f"Avez-vous appele calculate_all_indicators() avant generate_signals() ?"
        )

    df = df.copy()

    n = len(df)

    # Initialiser les colonnes de sortie avec des tableaux numpy (performance)
    signals = np.zeros(n, dtype=int)
    exit_signals = np.zeros(n, dtype=int)
    exit_reasons = np.full(n, '', dtype=object)
    states = np.zeros(n, dtype=int)

    # Recuperer les colonnes en numpy pour la performance
    zscores = df['ZScore'].values
    correlations = df['Correlation'].values
    coint_scores = df['Cointegration_Score'].values
    hursts = df['Hurst'].values if 'Hurst' in df.columns else np.full(n, np.nan)

    # Etat initial
    state = STATE_FLAT

    print("\n[...] Generation des signaux...")

    for i in range(n):
        z = zscores[i]
        corr = correlations[i]
        score = coint_scores[i]
        h = hursts[i]

        # Ignorer les barres avec des donnees invalides (NaN)
        if np.isnan(z) or np.isnan(corr) or np.isnan(score):
            states[i] = state
            continue

        # ---- ETAPE 1 : Verifier les sorties (si en position) ----
        if state in (STATE_LONG, STATE_SHORT):
            should_exit, reason = check_zscore_exit(z, state, config)

            if should_exit:
                exit_signals[i] = 1
                exit_reasons[i] = reason

                # Determiner le nouvel etat apres la sortie
                if reason == 'SL_ZSCORE':
                    # Stop Loss -> Cooldown dans la meme direction
                    if state == STATE_LONG:
                        state = STATE_COOLDOWN_LONG
                    else:
                        state = STATE_COOLDOWN_SHORT
                else:
                    # Take Profit -> Retour a FLAT (reentree immediate possible)
                    state = STATE_FLAT

        # ---- ETAPE 2 : Verifier le reset du cooldown ----
        if state in (STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            if check_cooldown_reset(z, state, config):
                state = STATE_FLAT

        # ---- ETAPE 3 : Verifier les entrees (si FLAT ou cooldown oppose) ----
        if state in (STATE_FLAT, STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT):
            entry = check_entry_conditions(z, corr, score, state, config, hurst=h)

            if entry != 0:
                signals[i] = entry

                if entry == 1:
                    state = STATE_LONG
                else:
                    state = STATE_SHORT

                # Si on vient d'entrer via un cooldown oppose, le cooldown est consomme
                # (l'entree dans l'autre direction annule le cooldown)

        # Sauvegarder l'etat de la barre
        states[i] = state

    # Ajouter les colonnes au DataFrame
    df['Signal'] = signals
    df['Exit_Signal'] = exit_signals
    df['Exit_Reason'] = exit_reasons
    df['State'] = states

    # Remplacer les chaines vides par NaN pour Exit_Reason
    df['Exit_Reason'] = df['Exit_Reason'].replace('', np.nan)

    # Statistiques
    n_long = (signals == 1).sum()
    n_short = (signals == -1).sum()
    n_exits = (exit_signals == 1).sum()
    n_tp = (exit_reasons == 'TP_ZSCORE').sum()
    n_sl = (exit_reasons == 'SL_ZSCORE').sum()

    print(f"   Entrees LONG  : {n_long}")
    print(f"   Entrees SHORT : {n_short}")
    print(f"   Sorties total : {n_exits} (TP: {n_tp}, SL: {n_sl})")
    print("   [OK] Signaux generes !")

    return df


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def get_signal_summary(df: pd.DataFrame) -> dict:
    """
    Resume statistique des signaux generes.

    Utile pour valider rapidement que la strategie genere
    un nombre raisonnable de signaux.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec les signaux generes (sortie de generate_signals)

    Retourne:
    ---------
    dict : Dictionnaire avec les statistiques des signaux
    """
    summary = {
        'total_bars': len(df),
        'entries_long': (df['Signal'] == 1).sum(),
        'entries_short': (df['Signal'] == -1).sum(),
        'exits_total': (df['Exit_Signal'] == 1).sum(),
        'exits_tp_zscore': (df['Exit_Reason'] == 'TP_ZSCORE').sum(),
        'exits_sl_zscore': (df['Exit_Reason'] == 'SL_ZSCORE').sum(),
    }

    summary['total_entries'] = summary['entries_long'] + summary['entries_short']

    # Ratio TP/SL
    if summary['exits_sl_zscore'] > 0:
        summary['tp_sl_ratio'] = summary['exits_tp_zscore'] / summary['exits_sl_zscore']
    else:
        summary['tp_sl_ratio'] = float('inf') if summary['exits_tp_zscore'] > 0 else 0

    # Pourcentage du temps en position
    bars_in_position = (df['State'].isin([STATE_LONG, STATE_SHORT])).sum()
    summary['time_in_market_pct'] = bars_in_position / len(df) * 100

    return summary


def build_trade_list(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construit la liste des trades a partir des signaux generes.

    Chaque trade contient : entree, sortie, direction, prix, Z-Score, duree.
    On ne parcourt que les barres avec un signal ou une sortie (optimise).

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec les signaux generes (sortie de generate_signals)

    Retourne:
    ---------
    pd.DataFrame : Un DataFrame avec une ligne par trade :
        - Trade_No       : Numero du trade
        - Direction       : LONG ou SHORT
        - Entry_DateTime  : Date/heure d'entree
        - Exit_DateTime   : Date/heure de sortie
        - Duration_Min    : Duree du trade en minutes
        - Entry_GC        : Prix GC a l'entree
        - Entry_SI        : Prix SI a l'entree
        - Exit_GC         : Prix GC a la sortie
        - Exit_SI         : Prix SI a la sortie
        - Entry_ZScore    : Z-Score a l'entree
        - Exit_ZScore     : Z-Score a la sortie
        - Exit_Reason     : Raison de la sortie (TP_ZSCORE, SL_ZSCORE)
    """
    trades = []
    trade_no = 0

    # Filtrer uniquement les barres avec un evenement (entree ou sortie)
    # au lieu de parcourir les 44000 barres
    event_mask = (df['Signal'] != 0) | (df['Exit_Signal'] == 1)
    event_rows = df[event_mask]

    # Variables pour tracker le trade en cours
    entry_row = None
    direction = None

    for _, row in event_rows.iterrows():

        # Nouvelle entree
        if row['Signal'] != 0:
            # Si on est deja en trade, c'est un reversal :
            # la sortie du trade precedent est sur la meme barre
            if entry_row is not None:
                trade_no += 1
                duration = (row['DateTime'] - entry_row['DateTime']).total_seconds() / 60
                trades.append({
                    'Trade_No': trade_no,
                    'Direction': 'LONG' if direction == 1 else 'SHORT',
                    'Entry_DateTime': entry_row['DateTime'],
                    'Exit_DateTime': row['DateTime'],
                    'Duration_Min': round(duration, 1),
                    'Entry_GC': entry_row['Last_GC'],
                    'Entry_SI': entry_row['Last_SI'],
                    'Exit_GC': row['Last_GC'],
                    'Exit_SI': row['Last_SI'],
                    'Entry_ZScore': round(entry_row['ZScore'], 2),
                    'Exit_ZScore': round(row['ZScore'], 2),
                    'Exit_Reason': row['Exit_Reason'] if row['Exit_Signal'] == 1 else 'REVERSAL',
                })

            # Enregistrer la nouvelle entree
            entry_row = row
            direction = row['Signal']

        # Sortie sans nouvelle entree
        elif row['Exit_Signal'] == 1 and entry_row is not None:
            trade_no += 1
            duration = (row['DateTime'] - entry_row['DateTime']).total_seconds() / 60
            trades.append({
                'Trade_No': trade_no,
                'Direction': 'LONG' if direction == 1 else 'SHORT',
                'Entry_DateTime': entry_row['DateTime'],
                'Exit_DateTime': row['DateTime'],
                'Duration_Min': round(duration, 1),
                'Entry_GC': entry_row['Last_GC'],
                'Entry_SI': entry_row['Last_SI'],
                'Exit_GC': row['Last_GC'],
                'Exit_SI': row['Last_SI'],
                'Entry_ZScore': round(entry_row['ZScore'], 2),
                'Exit_ZScore': round(row['ZScore'], 2),
                'Exit_Reason': row['Exit_Reason'],
            })
            entry_row = None
            direction = None

    # Si un trade est encore ouvert a la fin des donnees
    if entry_row is not None:
        last_row = df.iloc[-1]
        trade_no += 1
        duration = (last_row['DateTime'] - entry_row['DateTime']).total_seconds() / 60
        trades.append({
            'Trade_No': trade_no,
            'Direction': 'LONG' if direction == 1 else 'SHORT',
            'Entry_DateTime': entry_row['DateTime'],
            'Exit_DateTime': last_row['DateTime'],
            'Duration_Min': round(duration, 1),
            'Entry_GC': entry_row['Last_GC'],
            'Entry_SI': entry_row['Last_SI'],
            'Exit_GC': last_row['Last_GC'],
            'Exit_SI': last_row['Last_SI'],
            'Entry_ZScore': round(entry_row['ZScore'], 2),
            'Exit_ZScore': round(last_row['ZScore'], 2),
            'Exit_Reason': 'STILL_OPEN',
        })

    return pd.DataFrame(trades)


def export_trade_list(trades_df: pd.DataFrame, filepath: str = "output/trade_list.csv"):
    """
    Exporte la liste des trades dans un fichier CSV.

    Parametres:
    -----------
    trades_df : pd.DataFrame
        DataFrame des trades (sortie de build_trade_list)
    filepath : str
        Chemin du fichier de sortie (defaut: output/trade_list.csv)
    """
    from pathlib import Path

    # Creer le dossier output s'il n'existe pas
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    trades_df.to_csv(filepath, index=False, sep=';')
    print(f"   [OK] {len(trades_df)} trades exportes dans : {filepath}")


def get_signals_at_datetime(
    df: pd.DataFrame,
    target_datetime: str
) -> dict:
    """
    Recupere l'etat des signaux a une date/heure specifique.

    Utile pour comparer avec Sierra Chart a un instant donne.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec les signaux generes
    target_datetime : str
        Date/heure cible (format: "2026-01-23 10:30:00")

    Retourne:
    ---------
    dict ou None : Etat des signaux a cette date
    """
    target = pd.to_datetime(target_datetime)

    # Chercher la correspondance exacte
    mask = df['DateTime'] == target

    if mask.sum() == 0:
        # Chercher la plus proche
        time_diff = abs(df['DateTime'] - target)
        closest_idx = time_diff.idxmin()

        if time_diff[closest_idx] > pd.Timedelta(minutes=5):
            return None

        row = df.loc[closest_idx]
    else:
        row = df[mask].iloc[0]

    return {
        'datetime': row['DateTime'],
        'zscore': row.get('ZScore', np.nan),
        'correlation': row.get('Correlation', np.nan),
        'cointegration_score': row.get('Cointegration_Score', np.nan),
        'signal': row.get('Signal', 0),
        'exit_signal': row.get('Exit_Signal', 0),
        'exit_reason': row.get('Exit_Reason', np.nan),
        'state': row.get('State', 0),
    }


# ============================================================================
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module signals.

    Pour executer ce test :
        python src/signals.py
    """
    from data_loader import load_and_prepare_data
    from indicators import calculate_all_indicators

    print("\n" + "="*60)
    print("TEST DU MODULE SIGNALS")
    print("="*60)

    try:
        # 1. Charger les donnees
        df, config, stats = load_and_prepare_data(verbose=False)
        print(f"[OK] Donnees chargees : {len(df)} barres")

        # 2. Calculer les indicateurs
        df = calculate_all_indicators(df, config)
        print(f"[OK] Indicateurs calcules")

        # 3. Generer les signaux
        df = generate_signals(df, config)

        # 4. Afficher le resume
        summary = get_signal_summary(df)

        print("\n" + "="*60)
        print("RESUME DES SIGNAUX")
        print("="*60)
        print(f"\n   Barres totales      : {summary['total_bars']:,}")
        print(f"   Entrees LONG        : {summary['entries_long']}")
        print(f"   Entrees SHORT       : {summary['entries_short']}")
        print(f"   Total entrees       : {summary['total_entries']}")
        print(f"   Sorties TP Z-Score  : {summary['exits_tp_zscore']}")
        print(f"   Sorties SL Z-Score  : {summary['exits_sl_zscore']}")
        print(f"   Ratio TP/SL         : {summary['tp_sl_ratio']:.2f}")
        print(f"   Temps en position   : {summary['time_in_market_pct']:.1f}%")

        # 5. Afficher les premiers signaux d'entree
        entries = df[df['Signal'] != 0].head(5)
        if len(entries) > 0:
            print("\n" + "="*60)
            print("PREMIERS SIGNAUX D'ENTREE")
            print("="*60)
            for _, row in entries.iterrows():
                direction = "LONG" if row['Signal'] == 1 else "SHORT"
                print(f"\n   Date         : {row['DateTime']}")
                print(f"   Direction    : {direction}")
                print(f"   Z-Score      : {row['ZScore']:.2f}")
                print(f"   Correlation  : {row['Correlation']:.3f}")
                print(f"   Coint. Score : {row['Cointegration_Score']:.1f}")

        # 6. Afficher les premieres sorties
        exits = df[df['Exit_Signal'] == 1].head(5)
        if len(exits) > 0:
            print("\n" + "="*60)
            print("PREMIERES SORTIES")
            print("="*60)
            for _, row in exits.iterrows():
                print(f"\n   Date         : {row['DateTime']}")
                print(f"   Raison       : {row['Exit_Reason']}")
                print(f"   Z-Score      : {row['ZScore']:.2f}")

        # 7. Construire et exporter la liste des trades
        print("\n" + "="*60)
        print("EXPORT DES TRADES")
        print("="*60)
        trades_df = build_trade_list(df)
        export_trade_list(trades_df, "output/trade_list.csv")

        # Afficher les 10 premiers trades
        print("\n" + "="*60)
        print("LISTE DES TRADES (10 premiers)")
        print("="*60)
        for _, t in trades_df.head(10).iterrows():
            print(f"\n   Trade #{t['Trade_No']} - {t['Direction']}")
            print(f"   Entree : {t['Entry_DateTime']}  |  Z={t['Entry_ZScore']:+.2f}")
            print(f"   Sortie : {t['Exit_DateTime']}  |  Z={t['Exit_ZScore']:+.2f}")
            print(f"   Duree  : {t['Duration_Min']:.0f} min  |  Raison: {t['Exit_Reason']}")
            print(f"   Prix   : GC {t['Entry_GC']:.2f} -> {t['Exit_GC']:.2f}")
            print(f"            SI {t['Entry_SI']:.3f} -> {t['Exit_SI']:.3f}")

        print("\n" + "="*60)
        print("[OK] Test du module signals REUSSI !")
        print("="*60)

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
