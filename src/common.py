# ============================================================================
# COMMON.PY - Constantes et Fonctions Partagees
# ============================================================================
#
# Ce module centralise les constantes d'etats et les fonctions utilitaires
# partagees entre signals.py, backtest_engine.py et backtest_engine_hybrid.py.
#
# Principe : une seule source de verite pour eviter les divergences
# entre les differents modules (ex: filtre Hurst).
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import numpy as np
from typing import Tuple


# ============================================================================
# CONSTANTES D'ETATS DE LA MACHINE A ETATS
# ============================================================================
# Utilises par signals.py, backtest_engine.py, backtest_engine_hybrid.py.

STATE_FLAT = 0
STATE_LONG = 1
STATE_SHORT = -1
STATE_COOLDOWN_LONG = 2
STATE_COOLDOWN_SHORT = -2


# ============================================================================
# FONCTIONS DE VERIFICATION DES CONDITIONS
# ============================================================================

def check_entry_conditions(
    zscore: float,
    correlation: float,
    cointegration_score: float,
    state: int,
    config: dict,
    hurst: float = 0.0
) -> int:
    """
    Verifie si les conditions d'entree sont remplies.

    Logique :
    - On ne peut entrer que si on est FLAT
      (ou COOLDOWN dans la direction opposee)
    - Il faut que les conditions soient vraies simultanement :
      Z-Score au-dela du seuil, correlation suffisante, score suffisant,
      et Hurst en dessous du seuil max (si active)

    Parametres:
    -----------
    zscore : float
        Valeur actuelle du Z-Score
    correlation : float
        Valeur actuelle de la correlation Pearson
    cointegration_score : float
        Score de cointegration actuel (0-100)
    state : int
        Etat actuel de la machine a etats
    config : dict
        Configuration chargee depuis YAML
    hurst : float
        Valeur actuelle de l'exposant de Hurst (< 0.5 = mean reversion)

    Retourne:
    ---------
    int : 1 (LONG), -1 (SHORT), ou 0 (pas d'entree)
    """
    # Recuperer les seuils depuis la config
    z_long = config['entry']['zscore_long']            # -3.0
    z_short = config['entry']['zscore_short']           # +3.0
    corr_min = config['entry']['correlation_min']       # 0.70
    score_min = config['entry']['cointegration_score_min']  # 50
    hurst_max = config['entry'].get('hurst_max', 1.0)  # 1.0 = desactive

    # Conditions de qualite communes aux deux directions
    quality_ok = (correlation > corr_min) and (cointegration_score >= score_min)

    # Filtre Hurst independant (si active)
    if hurst_max < 1.0 and not np.isnan(hurst):
        quality_ok = quality_ok and (hurst < hurst_max)

    if not quality_ok:
        return 0

    # Verifier entree LONG
    # Autorise si FLAT ou COOLDOWN_SHORT (le cooldown LONG bloque le LONG)
    if zscore <= z_long and state not in (STATE_LONG, STATE_SHORT, STATE_COOLDOWN_LONG):
        return 1

    # Verifier entree SHORT
    # Autorise si FLAT ou COOLDOWN_LONG (le cooldown SHORT bloque le SHORT)
    if zscore >= z_short and state not in (STATE_LONG, STATE_SHORT, STATE_COOLDOWN_SHORT):
        return -1

    return 0


def check_zscore_exit(
    zscore: float,
    state: int,
    config: dict
) -> Tuple[bool, str]:
    """
    Verifie les conditions de sortie basees sur le Z-Score.

    Logique :
    - Priorite 1 : Stop Loss (protection du capital)
    - Priorite 2 : Take Profit (prise de benefice)

    Parametres:
    -----------
    zscore : float
        Valeur actuelle du Z-Score
    state : int
        Etat actuel (doit etre LONG ou SHORT)
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    Tuple[bool, str] : (doit_sortir, raison)
        - doit_sortir : True si on doit cloturer la position
        - raison : 'SL_ZSCORE', 'TP_ZSCORE', ou '' si pas de sortie
    """
    if state == STATE_LONG:
        # SL LONG : Z-Score continue de baisser -> danger
        if zscore <= config['exit']['zscore_sl_long']:     # <= -3.5
            return True, 'SL_ZSCORE'
        # TP LONG : Z-Score remonte vers la moyenne -> profit
        if zscore >= config['exit']['zscore_tp_long']:     # >= -2.0
            return True, 'TP_ZSCORE'

    elif state == STATE_SHORT:
        # SL SHORT : Z-Score continue de monter -> danger
        if zscore >= config['exit']['zscore_sl_short']:    # >= +3.5
            return True, 'SL_ZSCORE'
        # TP SHORT : Z-Score redescend vers la moyenne -> profit
        if zscore <= config['exit']['zscore_tp_short']:    # <= +2.0
            return True, 'TP_ZSCORE'

    return False, ''


def check_cooldown_reset(
    zscore: float,
    state: int,
    config: dict
) -> bool:
    """
    Verifie si le cooldown est termine (Z-Score revenu a la zone neutre).

    Apres un Stop Loss, on attend que le Z-Score revienne vers zero
    avant d'autoriser une nouvelle entree dans la meme direction.
    Cela evite de "re-rentrer trop vite" dans un mouvement adverse.

    Parametres:
    -----------
    zscore : float
        Valeur actuelle du Z-Score
    state : int
        Etat actuel (doit etre COOLDOWN_LONG ou COOLDOWN_SHORT)
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    bool : True si le cooldown est termine -> retour a FLAT
    """
    if state == STATE_COOLDOWN_LONG:
        # Z-Score doit remonter a -1.0 pour autoriser un nouveau LONG
        return zscore >= config['reentry']['zscore_reset_long']   # >= -1.0

    elif state == STATE_COOLDOWN_SHORT:
        # Z-Score doit redescendre a +1.0 pour autoriser un nouveau SHORT
        return zscore <= config['reentry']['zscore_reset_short']  # <= +1.0

    return False


# ============================================================================
# CALCUL DU PNL COURANT
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

    Utilise par backtest_engine.py et backtest_engine_hybrid.py pour
    surveiller le PnL intra-trade (exits en dollars).

    Parametres:
    -----------
    direction : int
        1 = LONG spread (long SI, short GC)
       -1 = SHORT spread (short SI, long GC)
    entry_gc, entry_si : float
        Prix d'entree GC et SI
    current_gc, current_si : float
        Prix courant GC et SI
    gc_contracts, si_contracts : int
        Nombre de contrats
    config : dict
        Configuration (pour point values)

    Retourne:
    ---------
    float : PnL brut en dollars (sans couts de transaction)
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


# ============================================================================
# EMPREINTE DE CONFIGURATION
# ============================================================================

def build_config_fingerprint(config):
    """
    Construit une empreinte des parametres cles de la config.
    Permet de verifier que le CSV a ete genere avec la config actuelle.

    Utilise par backtest_engine_hybrid.py (export) et metrics.py (validation).
    """
    ind = config['indicators']
    ext = config['exit']
    ent = config['entry']
    return (f"beta{ind['beta_lookback']}_zp{ind['zscore_period']}"
            f"_corr{ind['correlation_period']}_adf{ind['adf_hurst_period']}"
            f"_zE{ent['zscore_long']}_{ent['zscore_short']}"
            f"_zTP{ext['zscore_tp_long']}_{ext['zscore_tp_short']}"
            f"_zSL{ext['zscore_sl_long']}_{ext['zscore_sl_short']}"
            f"_TP{ext['pnl_take_profit']}_SL{ext['pnl_stop_loss']}"
            f"_corr{ent['correlation_min']}_coint{ent['cointegration_score_min']}")
