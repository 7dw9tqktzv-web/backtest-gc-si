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
    Check whether entry conditions are met for a new trade.

    All conditions must be satisfied simultaneously:
    - Z-Score beyond entry threshold (negative for LONG, positive for SHORT)
    - Pearson correlation above minimum
    - Cointegration score above minimum
    - Hurst exponent below maximum (if enabled, i.e. hurst_max < 1.0)

    State constraints:
    - Can only enter from FLAT or opposite-direction COOLDOWN
    - COOLDOWN_LONG blocks LONG entries (but allows SHORT)
    - COOLDOWN_SHORT blocks SHORT entries (but allows LONG)

    Parameters
    ----------
    zscore : float
        Current Z-Score value.
    correlation : float
        Current Pearson correlation between log(GC) and log(SI).
    cointegration_score : float
        Current composite cointegration score (0-100).
    state : int
        Current state machine state (STATE_FLAT, STATE_LONG, etc.).
    config : dict
        Strategy configuration loaded from YAML.
    hurst : float
        Current Hurst exponent (H < 0.5 = mean-reverting, H > 0.5 = trending).

    Returns
    -------
    int
        1 (LONG entry), -1 (SHORT entry), or 0 (no entry).
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
    Check Z-Score-based exit conditions for an open position.

    Exit priority (checked in order):
    1. Stop Loss (SL_ZSCORE) -- capital protection, highest priority
    2. Take Profit (TP_ZSCORE) -- profit taking, can be disabled via config

    For LONG positions:
    - SL triggers when Z-Score drops further (Z <= zscore_sl_long)
    - TP triggers when Z-Score reverts toward mean (Z >= zscore_tp_long)

    For SHORT positions:
    - SL triggers when Z-Score rises further (Z >= zscore_sl_short)
    - TP triggers when Z-Score reverts toward mean (Z <= zscore_tp_short)

    Parameters
    ----------
    zscore : float
        Current Z-Score value.
    state : int
        Current state (must be STATE_LONG or STATE_SHORT).
    config : dict
        Strategy configuration loaded from YAML.

    Returns
    -------
    tuple[bool, str]
        (should_exit, reason) where reason is 'SL_ZSCORE', 'TP_ZSCORE',
        or '' if no exit triggered.
    """
    # Parametre optionnel : desactiver les sorties TP_ZSCORE (defaut: True = actif)
    tp_enabled = config['exit'].get('zscore_tp_enabled', True)

    if state == STATE_LONG:
        # SL LONG : Z-Score continue de baisser -> danger
        if zscore <= config['exit']['zscore_sl_long']:     # <= -3.5
            return True, 'SL_ZSCORE'
        # TP LONG : Z-Score remonte vers la moyenne -> profit
        if tp_enabled and zscore >= config['exit']['zscore_tp_long']:     # >= -2.0
            return True, 'TP_ZSCORE'

    elif state == STATE_SHORT:
        # SL SHORT : Z-Score continue de monter -> danger
        if zscore >= config['exit']['zscore_sl_short']:    # >= +3.5
            return True, 'SL_ZSCORE'
        # TP SHORT : Z-Score redescend vers la moyenne -> profit
        if tp_enabled and zscore <= config['exit']['zscore_tp_short']:    # <= +2.0
            return True, 'TP_ZSCORE'

    return False, ''


def check_cooldown_reset(
    zscore: float,
    state: int,
    config: dict
) -> bool:
    """
    Check whether the cooldown period has ended (Z-Score returned to neutral zone).

    After a stop loss exit, the strategy waits for the Z-Score to revert
    toward zero before allowing re-entry in the same direction. This prevents
    re-entering too quickly into an adverse move.

    Cooldown reset thresholds:
    - COOLDOWN_LONG: Z-Score must rise back to zscore_reset_long (e.g. -1.0)
    - COOLDOWN_SHORT: Z-Score must fall back to zscore_reset_short (e.g. +1.0)

    Parameters
    ----------
    zscore : float
        Current Z-Score value.
    state : int
        Current state (must be STATE_COOLDOWN_LONG or STATE_COOLDOWN_SHORT).
    config : dict
        Strategy configuration loaded from YAML.

    Returns
    -------
    bool
        True if cooldown is over and state should transition back to FLAT.
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
    Calculate the current gross PnL of an open position.

    Used by backtest engines to monitor intra-trade PnL for dollar-based
    exit detection (TP_DOLLAR and SL_DOLLAR).

    Formula:
        LONG spread (long SI, short GC):
            PnL = (current_SI - entry_SI) * SI_pv * SI_qty
                + (entry_GC - current_GC) * GC_pv * GC_qty

        SHORT spread (short SI, long GC):
            PnL = (entry_SI - current_SI) * SI_pv * SI_qty
                + (current_GC - entry_GC) * GC_pv * GC_qty

        where GC_pv = $100/point, SI_pv = $5,000/point.

    Parameters
    ----------
    direction : int
        1 = LONG spread (long SI, short GC),
       -1 = SHORT spread (short SI, long GC).
    entry_gc, entry_si : float
        Entry prices for GC and SI.
    current_gc, current_si : float
        Current prices for GC and SI.
    gc_contracts, si_contracts : int
        Number of contracts for each leg.
    config : dict
        Strategy configuration (for point values).

    Returns
    -------
    float
        Gross PnL in USD (before transaction costs).
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
    Build a fingerprint string from key configuration parameters.

    Used to verify that a backtest CSV was generated with the current
    configuration. Compared by backtest_engine_hybrid.py (export) and
    metrics.py (validation).

    Returns
    -------
    str
        Fingerprint like 'beta1320_zp24_corr24_adf96_zE-3.5_3.5_zTP-2.0_2.0_...'
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
