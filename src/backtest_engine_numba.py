# ============================================================================
# BACKTEST_ENGINE_NUMBA.PY - Version Numba JIT modulable
# ============================================================================
#
# Architecture "Config Vector" :
#   - Tous les parametres sont packes dans un float64 array (cfg[])
#   - Ajouter un parametre = ajouter 1 constante d'index + 1 ligne de packing
#   - Le kernel Numba lit cfg[IDX] au lieu d'arguments nommes
#   - La signature du kernel ne change JAMAIS
#
# Drop-in replacement pour backtest_engine_hybrid.run_hybrid_backtest()
#
# Usage :
#   from backtest_engine_numba import run_hybrid_backtest
#   # (meme signature, meme DataFrame en retour)
#
# Corrections v2 :
#   - Fix session_end : comparaison en minutes (pas juste heures)
#   - Fix MAX_TRADES : warning si limite atteinte
#   - Exit reasons : noms coherents avec metrics.py
#
# ============================================================================

import warnings
import numpy as np
import pandas as pd
from numba import njit

try:
    from common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
    )
except ImportError:
    from .common import (
        STATE_FLAT, STATE_LONG, STATE_SHORT,
        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
    )


# ============================================================================
# CONFIG VECTOR — Index des parametres
# ============================================================================
# Pour ajouter un nouveau parametre :
#   1. Ajouter un CFG_xxx ici (incrementer l'index)
#   2. Ajouter l'extraction dans pack_config()
#   3. Utiliser cfg[CFG_xxx] dans le kernel
#   4. Incrementer CFG_SIZE
#   5. C'est tout.

# Entry
CFG_Z_LONG              = 0
CFG_Z_SHORT             = 1
CFG_CORR_MIN            = 2
CFG_SCORE_MIN           = 3
CFG_HURST_MAX           = 4

# Exit Z-Score
CFG_ZSCORE_TP_ENABLED   = 5
CFG_ZSCORE_TP_LONG      = 6
CFG_ZSCORE_SL_LONG      = 7
CFG_ZSCORE_TP_SHORT     = 8
CFG_ZSCORE_SL_SHORT     = 9
CFG_ZSCORE_TP_MIN_PNL   = 10   # NaN = desactive

# Exit Dollar
CFG_PNL_TP              = 11
CFG_PNL_SL              = 12

# Contracts / Point Values
CFG_GC_PV               = 13
CFG_SI_PV               = 14
CFG_GC_TV               = 15   # tick value
CFG_SI_TV               = 16

# Sizing
CFG_SIZING_MODE         = 17   # 0=fixed, 1=dollar_neutral, 2=dollar_neutral_beta
CFG_SI_CONTRACTS_BASE   = 18
CFG_GC_CONTRACTS_MAX    = 19

# Costs
CFG_COMMISSION_RT       = 20
CFG_SLIP_GC_TICKS       = 21
CFG_SLIP_SI_TICKS       = 22

# Session
CFG_ENTRY_START_HOUR    = 23
CFG_ENTRY_END_HOUR      = 24

# Reentry
CFG_ZSCORE_RESET_LONG   = 25
CFG_ZSCORE_RESET_SHORT  = 26

# Regime filter
CFG_RF_HL_ENABLED       = 27
CFG_RF_CORR_ENABLED     = 28
CFG_RF_HL_THRESHOLD     = 29
CFG_RF_CORR_THRESHOLD   = 30

# ---- NOUVEAUX PARAMETRES (grid_micro_r1) ----
CFG_MAX_HOLDING_BARS    = 31   # 0 = desactive
CFG_FLAT_END_SESSION    = 32   # 1.0 = active, 0.0 = desactive
CFG_MICRO_MULT_MAX      = 33   # multiplicateur max micro (1, 2, etc.)
CFG_SESSION_END_MINUTES = 34   # minutes depuis minuit (ex: 15:25 = 925)

# ---- TOTAL (incrementer quand on ajoute) ----
CFG_SIZE                = 35


# ============================================================================
# PACKING : dict config -> numpy array
# ============================================================================

def pack_config(config: dict) -> np.ndarray:
    """
    Convertit le dict config Python en un float64 array pour Numba.

    C'est la SEULE fonction a modifier quand on ajoute un parametre.
    """
    cfg = np.zeros(CFG_SIZE, dtype=np.float64)

    ent = config['entry']
    ext = config['exit']
    con = config['contracts']
    siz = config['sizing']
    cos = config['costs']
    ses = config['session']
    ree = config['reentry']
    rf  = config.get('regime_filter', {})

    # Entry
    cfg[CFG_Z_LONG]            = float(ent['zscore_long'])
    cfg[CFG_Z_SHORT]           = float(ent['zscore_short'])
    cfg[CFG_CORR_MIN]          = float(ent['correlation_min'])
    cfg[CFG_SCORE_MIN]         = float(ent['cointegration_score_min'])
    cfg[CFG_HURST_MAX]         = float(ent.get('hurst_max', 1.0))

    # Exit Z-Score
    cfg[CFG_ZSCORE_TP_ENABLED] = 1.0 if ext.get('zscore_tp_enabled', True) else 0.0
    cfg[CFG_ZSCORE_TP_LONG]    = float(ext['zscore_tp_long'])
    cfg[CFG_ZSCORE_SL_LONG]    = float(ext['zscore_sl_long'])
    cfg[CFG_ZSCORE_TP_SHORT]   = float(ext['zscore_tp_short'])
    cfg[CFG_ZSCORE_SL_SHORT]   = float(ext['zscore_sl_short'])
    tp_min = ext.get('zscore_tp_min_pnl', None)
    cfg[CFG_ZSCORE_TP_MIN_PNL] = float(tp_min) if tp_min is not None else np.nan

    # Exit Dollar
    cfg[CFG_PNL_TP]            = float(ext['pnl_take_profit'])
    cfg[CFG_PNL_SL]            = float(ext['pnl_stop_loss'])

    # Contracts
    cfg[CFG_GC_PV]             = float(con['gc_point_value'])
    cfg[CFG_SI_PV]             = float(con['si_point_value'])
    cfg[CFG_GC_TV]             = float(con['gc_tick_value'])
    cfg[CFG_SI_TV]             = float(con['si_tick_value'])

    # Sizing
    mode_map = {'fixed': 0, 'dollar_neutral': 1, 'dollar_neutral_beta': 2}
    cfg[CFG_SIZING_MODE]       = float(mode_map.get(siz['mode'], 2))
    cfg[CFG_SI_CONTRACTS_BASE] = float(siz['si_contracts'])
    cfg[CFG_GC_CONTRACTS_MAX]  = float(siz.get('gc_contracts_max', 0))

    # Costs
    cfg[CFG_COMMISSION_RT]     = float(con.get('commission_per_contract_rt',
                                       cos['commission_per_contract']))
    cfg[CFG_SLIP_GC_TICKS]     = float(cos['slippage_gc_ticks'])
    cfg[CFG_SLIP_SI_TICKS]     = float(cos['slippage_si_ticks'])

    # Session
    cfg[CFG_ENTRY_START_HOUR]  = float(ses.get('entry_start_hour', 0))
    cfg[CFG_ENTRY_END_HOUR]    = float(ses.get('entry_end_hour', 24))

    # Reentry
    cfg[CFG_ZSCORE_RESET_LONG] = float(ree['zscore_reset_long'])
    cfg[CFG_ZSCORE_RESET_SHORT]= float(ree['zscore_reset_short'])

    # Regime filter
    rf_enabled = rf.get('enabled', False)
    cfg[CFG_RF_HL_ENABLED]     = 1.0 if (rf_enabled and rf.get('halflife_ar1', {}).get('enabled', False)) else 0.0
    cfg[CFG_RF_CORR_ENABLED]   = 1.0 if (rf_enabled and rf.get('correlation_daily', {}).get('enabled', False)) else 0.0
    cfg[CFG_RF_HL_THRESHOLD]   = float(rf.get('halflife_ar1', {}).get('threshold', 4.9))
    cfg[CFG_RF_CORR_THRESHOLD] = float(rf.get('correlation_daily', {}).get('threshold', 0.916))

    # Nouveaux parametres micro
    cfg[CFG_MAX_HOLDING_BARS]  = float(ext.get('max_holding_bars', 0))
    cfg[CFG_FLAT_END_SESSION]  = 1.0 if ext.get('flat_end_of_session', False) else 0.0
    cfg[CFG_MICRO_MULT_MAX]    = float(siz.get('micro_multiplier_max', 0))

    # Session end en minutes depuis minuit (Fix #4 : precision sub-heure)
    # Supporte "HH:MM" string OU int heure seule (retrocompatibilite)
    session_end_raw = ses.get('session_end_time', ses.get('end_time', '17:00'))
    if isinstance(session_end_raw, str) and ':' in str(session_end_raw):
        parts = str(session_end_raw).split(':')
        cfg[CFG_SESSION_END_MINUTES] = float(int(parts[0]) * 60 + int(parts[1]))
    else:
        # Fallback : heure entiere
        cfg[CFG_SESSION_END_MINUTES] = float(int(session_end_raw) * 60)

    return cfg


# ============================================================================
# CONSTANTES D'ETAT (dupliquees pour Numba)
# ============================================================================
_FLAT = 0
_LONG = 1
_SHORT = -1
_CD_LONG = 2
_CD_SHORT = -2

# Exit reasons (codes numeriques)
_TP_ZSCORE  = 0
_SL_ZSCORE  = 1
_TP_DOLLAR  = 2
_SL_DOLLAR  = 3
_STILL_OPEN = 4
_FLAT_EOD   = 5
_MAX_HOLD   = 6

_MAX_TRADES = 5000

# Mapping : code numerique -> string pour le DataFrame
# Les noms DOIVENT etre coherents avec metrics.py et report_generator.py
EXIT_REASON_MAP = {
    0: 'TP_ZSCORE',
    1: 'SL_ZSCORE',
    2: 'TP_DOLLAR',
    3: 'SL_DOLLAR',
    4: 'STILL_OPEN',
    5: 'FLAT_EOD',       # Nouveau type — metrics.py doit etre mis a jour
    6: 'MAX_HOLD',       # Nouveau type — metrics.py doit etre mis a jour
}

# Exit reasons que metrics.py connait deja (pour reference)
_LEGACY_EXIT_REASONS = {'TP_ZSCORE', 'SL_ZSCORE', 'TP_DOLLAR', 'SL_DOLLAR', 'STILL_OPEN'}
# Nouveaux types ajoutes par le kernel Numba
_NEW_EXIT_REASONS = {'FLAT_EOD', 'MAX_HOLD'}


# ============================================================================
# FONCTIONS HELPER NUMBA (inlinees automatiquement)
# ============================================================================

@njit(cache=True, inline='always')
def _check_entry(z, corr, score, state, hurst, cfg):
    """Check entry conditions."""
    quality = (corr > cfg[CFG_CORR_MIN]) and (score >= cfg[CFG_SCORE_MIN])
    if cfg[CFG_HURST_MAX] < 1.0 and not np.isnan(hurst):
        quality = quality and (hurst < cfg[CFG_HURST_MAX])
    if not quality:
        return 0
    if z <= cfg[CFG_Z_LONG] and state != _LONG and state != _SHORT and state != _CD_LONG:
        return 1
    if z >= cfg[CFG_Z_SHORT] and state != _LONG and state != _SHORT and state != _CD_SHORT:
        return -1
    return 0


@njit(cache=True, inline='always')
def _check_zscore_exit(z, state, cfg):
    """Check Z-Score exit. Returns (should_exit, reason_code)."""
    tp_on = cfg[CFG_ZSCORE_TP_ENABLED] > 0.5
    if state == _LONG:
        if z <= cfg[CFG_ZSCORE_SL_LONG]:
            return True, _SL_ZSCORE
        if tp_on and z >= cfg[CFG_ZSCORE_TP_LONG]:
            return True, _TP_ZSCORE
    elif state == _SHORT:
        if z >= cfg[CFG_ZSCORE_SL_SHORT]:
            return True, _SL_ZSCORE
        if tp_on and z <= cfg[CFG_ZSCORE_TP_SHORT]:
            return True, _TP_ZSCORE
    return False, -1


@njit(cache=True, inline='always')
def _calc_costs(gc_c, si_c, cfg):
    """Transaction costs inline."""
    comm = cfg[CFG_COMMISSION_RT] * (gc_c + si_c)
    slip = (cfg[CFG_SLIP_GC_TICKS] * cfg[CFG_GC_TV] * gc_c * 2.0
            + cfg[CFG_SLIP_SI_TICKS] * cfg[CFG_SI_TV] * si_c * 2.0)
    return comm + slip


@njit(cache=True, inline='always')
def _calc_size(gc_price, si_price, beta, cfg):
    """Position sizing inline."""
    si_c = int(cfg[CFG_SI_CONTRACTS_BASE])
    mode = int(cfg[CFG_SIZING_MODE])
    gc_max = int(cfg[CFG_GC_CONTRACTS_MAX])
    micro_max = int(cfg[CFG_MICRO_MULT_MAX])

    if mode == 2:  # dollar_neutral_beta
        not_gc = gc_price * cfg[CFG_GC_PV]
        not_si = si_price * cfg[CFG_SI_PV]
        gc_raw_1x = (not_si / not_gc) * beta * si_c

        # Multiplicateur optimal micro : teste 1x..Nx, garde le meilleur arrondi
        if micro_max > 1:
            best_mult = 1
            best_err = abs(round(gc_raw_1x) - gc_raw_1x) / max(gc_raw_1x, 1.0)
            for mult in range(2, micro_max + 1):
                gc_raw_m = gc_raw_1x * mult
                err = abs(round(gc_raw_m) - gc_raw_m) / max(gc_raw_m, 1.0)
                # 2x gagne seulement si ameliore significativement (>1% mieux)
                if err < best_err - 0.01:
                    best_err = err
                    best_mult = mult
            si_c = si_c * best_mult
            gc_c = int(round(gc_raw_1x * best_mult))
        else:
            gc_c = int(round(gc_raw_1x))

        if gc_c < 1:
            gc_c = 1
        if gc_max > 0 and gc_c > gc_max:
            gc_c = gc_max
    elif mode == 1:  # dollar_neutral
        not_gc = gc_price * cfg[CFG_GC_PV]
        not_si = si_price * cfg[CFG_SI_PV]
        raw = (not_si / not_gc) * si_c
        gc_c = int(round(raw))
        if gc_c < 1:
            gc_c = 1
    else:  # fixed
        gc_c = si_c

    return gc_c, si_c


@njit(cache=True, inline='always')
def _calc_pnl(direction, entry_gc, entry_si, cur_gc, cur_si, gc_c, si_c, cfg):
    """PnL brut inline."""
    if direction == 1:
        return ((entry_gc - cur_gc) * cfg[CFG_GC_PV] * gc_c
                + (cur_si - entry_si) * cfg[CFG_SI_PV] * si_c)
    else:
        return ((cur_gc - entry_gc) * cfg[CFG_GC_PV] * gc_c
                + (entry_si - cur_si) * cfg[CFG_SI_PV] * si_c)


@njit(cache=True, inline='always')
def _record_trade(results, idx, trade_no, direction, entry_idx, exit_idx,
                   entry_gc, entry_si, exit_gc, exit_si,
                   gc_c, si_c, pnl_gross, costs, pnl_net,
                   reason, max_pnl, min_pnl, exit_5s_ts):
    """Write one trade into the results array."""
    if idx < results.shape[0]:
        results[idx, 0] = trade_no
        results[idx, 1] = direction
        results[idx, 2] = entry_idx
        results[idx, 3] = exit_idx
        results[idx, 4] = entry_gc
        results[idx, 5] = entry_si
        results[idx, 6] = exit_gc
        results[idx, 7] = exit_si
        results[idx, 8] = gc_c
        results[idx, 9] = si_c
        results[idx, 10] = pnl_gross
        results[idx, 11] = costs
        results[idx, 12] = pnl_net
        results[idx, 13] = reason
        results[idx, 14] = max_pnl
        results[idx, 15] = min_pnl
        results[idx, 16] = exit_5s_ts


@njit(cache=True, inline='always')
def _regime_blocked(i, rf_hl_on, rf_corr_on, hl_ar1, corr_daily, cfg):
    """Check regime filter blocking."""
    if rf_hl_on and len(hl_ar1) > 0:
        v = hl_ar1[i]
        if not np.isnan(v) and v > cfg[CFG_RF_HL_THRESHOLD]:
            return True
    if rf_corr_on and len(corr_daily) > 0:
        v = corr_daily[i]
        if not np.isnan(v) and v < cfg[CFG_RF_CORR_THRESHOLD]:
            return True
    return False


# ============================================================================
# KERNEL PRINCIPAL
# ============================================================================

@njit(cache=True)
def _run_kernel(
    # Data arrays (signature fixe, ne change jamais)
    zscores, correlations, coint_scores,
    gc_prices, si_prices, betas, hursts,
    hours, minutes, timestamps_ns,
    dt_5s_ns, gc_5s, si_5s, timestamps_1min_ns,
    hl_ar1_values, corr_daily_values,
    # Config vector (un seul array, extensible a volonte)
    cfg,
):
    """
    Kernel Numba du backtest hybride.

    Resultat : array (MAX_TRADES, 17) + n_trades.
    Layout colonnes : voir _record_trade().
    """
    n = len(zscores)
    pnl_tp = cfg[CFG_PNL_TP]
    pnl_sl = cfg[CFG_PNL_SL]
    pure_zscore = (pnl_tp >= 50000.0 and pnl_sl <= -50000.0)
    max_hold = int(cfg[CFG_MAX_HOLDING_BARS])
    flat_eod = cfg[CFG_FLAT_END_SESSION] > 0.5
    session_end_min = int(cfg[CFG_SESSION_END_MINUTES])  # minutes depuis minuit
    entry_start_h = int(cfg[CFG_ENTRY_START_HOUR])
    entry_end_h = int(cfg[CFG_ENTRY_END_HOUR])
    reset_long = cfg[CFG_ZSCORE_RESET_LONG]
    reset_short = cfg[CFG_ZSCORE_RESET_SHORT]
    rf_hl_on = cfg[CFG_RF_HL_ENABLED] > 0.5
    rf_corr_on = cfg[CFG_RF_CORR_ENABLED] > 0.5

    results = np.empty((_MAX_TRADES, 17), dtype=np.float64)
    trade_no = 0
    state = _FLAT
    entry_idx = -1
    direction = 0
    gc_c = 0
    si_c = 0
    entry_gc = 0.0
    entry_si = 0.0
    max_pnl = 0.0
    min_pnl = 0.0
    bars_in_pos = 0
    idx_5s = 0

    for i in range(n):
        z = zscores[i]
        corr = correlations[i]
        score = coint_scores[i]
        gc = gc_prices[i]
        si = si_prices[i]
        beta = betas[i]

        if np.isnan(z) or np.isnan(corr) or np.isnan(score):
            continue

        # ================================================================
        # ETAPE 1 : Si en position -> verifier sorties
        # ================================================================
        if state == _LONG or state == _SHORT:
            bars_in_pos += 1

            # ---- 1a. Dollar exits via scan 5s (priorite max) ----
            if not pure_zscore:
                dollar_exit = False
                dollar_reason = -1
                dollar_exit_gc = 0.0
                dollar_exit_si = 0.0
                dollar_exit_ts = -1.0

                if i > 0:
                    t_prev = timestamps_1min_ns[i - 1]
                else:
                    t_prev = timestamps_1min_ns[i]
                t_curr = timestamps_1min_ns[i]

                while idx_5s < len(dt_5s_ns) and dt_5s_ns[idx_5s] < t_prev:
                    idx_5s += 1

                j = idx_5s
                while j < len(dt_5s_ns) and dt_5s_ns[j] <= t_curr:
                    pnl_5s = _calc_pnl(direction, entry_gc, entry_si,
                                        gc_5s[j], si_5s[j], gc_c, si_c, cfg)
                    if pnl_5s > max_pnl:
                        max_pnl = pnl_5s
                    if pnl_5s < min_pnl:
                        min_pnl = pnl_5s

                    if pnl_5s <= pnl_sl:
                        dollar_exit = True
                        dollar_reason = _SL_DOLLAR
                        dollar_exit_gc = gc_5s[j]
                        dollar_exit_si = si_5s[j]
                        dollar_exit_ts = dt_5s_ns[j]
                        break
                    if pnl_5s >= pnl_tp:
                        dollar_exit = True
                        dollar_reason = _TP_DOLLAR
                        dollar_exit_gc = gc_5s[j]
                        dollar_exit_si = si_5s[j]
                        dollar_exit_ts = dt_5s_ns[j]
                        break
                    j += 1

                if dollar_exit:
                    if dollar_reason == _SL_DOLLAR:
                        pnl_g = pnl_sl
                    else:
                        pnl_g = pnl_tp
                    costs = _calc_costs(gc_c, si_c, cfg)

                    if trade_no < _MAX_TRADES:
                        _record_trade(results, trade_no, trade_no + 1, direction,
                                      entry_idx, i, entry_gc, entry_si,
                                      dollar_exit_gc, dollar_exit_si,
                                      gc_c, si_c, pnl_g, costs, pnl_g - costs,
                                      dollar_reason, max_pnl, min_pnl, dollar_exit_ts)
                        trade_no += 1

                    if dollar_reason == _SL_DOLLAR:
                        state = _CD_LONG if direction == 1 else _CD_SHORT
                    else:
                        state = _FLAT
                    entry_idx = -1
                    direction = 0
                    bars_in_pos = 0

                    # Cooldown reset + reentree sur meme barre
                    if state == _CD_LONG and z >= reset_long:
                        state = _FLAT
                    elif state == _CD_SHORT and z <= reset_short:
                        state = _FLAT

                    bar_h = hours[i]
                    if entry_start_h <= entry_end_h:
                        in_entry_window = entry_start_h <= bar_h < entry_end_h
                    else:
                        in_entry_window = bar_h >= entry_start_h or bar_h < entry_end_h
                    if (in_entry_window
                        and (state == _FLAT or state == _CD_LONG or state == _CD_SHORT)):
                        if not _regime_blocked(i, rf_hl_on, rf_corr_on,
                                                hl_ar1_values, corr_daily_values, cfg):
                            entry_sig = _check_entry(z, corr, score, state, hursts[i], cfg)
                            if entry_sig != 0 and not np.isnan(beta):
                                gc_c, si_c = _calc_size(gc, si, beta, cfg)
                                direction = entry_sig
                                entry_idx = i
                                entry_gc = gc
                                entry_si = si
                                max_pnl = 0.0
                                min_pnl = 0.0
                                bars_in_pos = 0
                                state = _LONG if entry_sig == 1 else _SHORT
                    continue

            # ---- 1d. Z-Score exit (si toujours en position) ----
            if state == _LONG or state == _SHORT:
                cur_pnl = _calc_pnl(direction, entry_gc, entry_si, gc, si, gc_c, si_c, cfg)
                if cur_pnl > max_pnl:
                    max_pnl = cur_pnl
                if cur_pnl < min_pnl:
                    min_pnl = cur_pnl

                should_exit, reason = _check_zscore_exit(z, state, cfg)

                if should_exit and reason == _TP_ZSCORE and not np.isnan(cfg[CFG_ZSCORE_TP_MIN_PNL]):
                    cost_est = _calc_costs(gc_c, si_c, cfg)
                    if (cur_pnl - cost_est) < cfg[CFG_ZSCORE_TP_MIN_PNL]:
                        should_exit = False

                # ---- 1c. Max holding bars (priorite basse, apres Z-Score) ----
                if not should_exit and max_hold > 0 and bars_in_pos >= max_hold:
                    should_exit = True
                    reason = _MAX_HOLD

                # ---- 1d. Flat end of session (priorite la plus basse) ----
                if not should_exit and flat_eod:
                    bar_minutes = hours[i] * 60 + minutes[i]
                    if bar_minutes >= session_end_min:
                        should_exit = True
                        reason = _FLAT_EOD

                if should_exit:
                    if reason == _MAX_HOLD or reason == _FLAT_EOD:
                        # Pour ces exits, calculer le PnL au prix 1-min courant
                        cur_pnl = _calc_pnl(direction, entry_gc, entry_si, gc, si, gc_c, si_c, cfg)
                    costs = _calc_costs(gc_c, si_c, cfg)
                    if trade_no < _MAX_TRADES:
                        _record_trade(results, trade_no, trade_no + 1, direction,
                                      entry_idx, i, entry_gc, entry_si, gc, si,
                                      gc_c, si_c, cur_pnl, costs, cur_pnl - costs,
                                      reason, max_pnl, min_pnl, -1.0)
                        trade_no += 1

                    if reason == _SL_ZSCORE:
                        state = _CD_LONG if direction == 1 else _CD_SHORT
                    else:
                        state = _FLAT
                    entry_idx = -1
                    direction = 0
                    bars_in_pos = 0

        # ================================================================
        # ETAPE 2 : Cooldown reset
        # ================================================================
        if state == _CD_LONG and z >= reset_long:
            state = _FLAT
        elif state == _CD_SHORT and z <= reset_short:
            state = _FLAT

        # ================================================================
        # ETAPE 3 : Entrees
        # ================================================================
        bar_h = hours[i]
        if entry_start_h <= entry_end_h:
            in_entry_window = entry_start_h <= bar_h < entry_end_h
        else:
            in_entry_window = bar_h >= entry_start_h or bar_h < entry_end_h
        if (in_entry_window
            and (state == _FLAT or state == _CD_LONG or state == _CD_SHORT)):

            if _regime_blocked(i, rf_hl_on, rf_corr_on,
                                hl_ar1_values, corr_daily_values, cfg):
                continue

            entry_sig = _check_entry(z, corr, score, state, hursts[i], cfg)
            if entry_sig != 0 and not np.isnan(beta):
                gc_c, si_c = _calc_size(gc, si, beta, cfg)
                direction = entry_sig
                entry_idx = i
                entry_gc = gc
                entry_si = si
                max_pnl = 0.0
                min_pnl = 0.0
                bars_in_pos = 0
                state = _LONG if entry_sig == 1 else _SHORT

    # ---- Trade encore ouvert a la fin ----
    if entry_idx >= 0:
        last_i = n - 1
        gc_last = gc_prices[last_i]
        si_last = si_prices[last_i]
        pnl_g = _calc_pnl(direction, entry_gc, entry_si, gc_last, si_last, gc_c, si_c, cfg)
        costs = _calc_costs(gc_c, si_c, cfg)
        if trade_no < _MAX_TRADES:
            _record_trade(results, trade_no, trade_no + 1, direction,
                          entry_idx, last_i, entry_gc, entry_si, gc_last, si_last,
                          gc_c, si_c, pnl_g, costs, pnl_g - costs,
                          _STILL_OPEN, max_pnl, min_pnl, -1.0)
            trade_no += 1

    return results[:trade_no], trade_no


# ============================================================================
# WRAPPER PYTHON — Interface identique a run_hybrid_backtest()
# ============================================================================

def run_hybrid_backtest(
    df_1min: pd.DataFrame,
    df_5s: pd.DataFrame,
    config: dict,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Drop-in replacement pour backtest_engine_hybrid.run_hybrid_backtest().
    Meme signature, meme DataFrame en sortie.
    """
    required = ['ZScore', 'Correlation', 'Cointegration_Score',
                'Last_GC', 'Last_SI', 'Beta']
    missing = [c for c in required if c not in df_1min.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans df_1min : {missing}")

    n = len(df_1min)

    # ---- Extraire les numpy arrays ----
    zscores = df_1min['ZScore'].values.astype(np.float64)
    correlations = df_1min['Correlation'].values.astype(np.float64)
    coint_scores = df_1min['Cointegration_Score'].values.astype(np.float64)
    gc_prices = df_1min['Last_GC'].values.astype(np.float64)
    si_prices = df_1min['Last_SI'].values.astype(np.float64)
    betas = df_1min['Beta'].values.astype(np.float64)
    hursts = (df_1min['Hurst'].values.astype(np.float64)
              if 'Hurst' in df_1min.columns
              else np.full(n, np.nan, dtype=np.float64))

    ts_1min = pd.to_datetime(df_1min['DateTime'])
    hours = ts_1min.dt.hour.values.astype(np.int64)
    mins = ts_1min.dt.minute.values.astype(np.int64)
    ts_ns = ts_1min.values.astype(np.int64)

    dt_5s_ns = pd.to_datetime(df_5s['DateTime']).values.astype(np.int64)
    gc_5s = df_5s['Last_GC'].values.astype(np.float64)
    si_5s = df_5s['Last_SI'].values.astype(np.float64)

    # Regime filter arrays
    rf = config.get('regime_filter', {})
    rf_enabled = rf.get('enabled', False)
    hl_on = rf_enabled and rf.get('halflife_ar1', {}).get('enabled', False)
    corr_on = rf_enabled and rf.get('correlation_daily', {}).get('enabled', False)
    hl_ar1 = (df_1min['HalfLife_AR1'].values.astype(np.float64)
              if hl_on and 'HalfLife_AR1' in df_1min.columns
              else np.empty(0, dtype=np.float64))
    corr_daily = (df_1min['Corr_Daily_GC_SI'].values.astype(np.float64)
                  if corr_on and 'Corr_Daily_GC_SI' in df_1min.columns
                  else np.empty(0, dtype=np.float64))

    # ---- Pack config -> numpy ----
    cfg = pack_config(config)

    if verbose:
        print("\n[...] Backtest hybride NUMBA (1min/5min + 5s)...")

    # ---- Appeler le kernel ----
    raw, n_trades = _run_kernel(
        zscores, correlations, coint_scores,
        gc_prices, si_prices, betas, hursts,
        hours, mins, ts_ns,
        dt_5s_ns, gc_5s, si_5s, ts_ns,
        hl_ar1, corr_daily,
        cfg,
    )

    # ---- Fix #3 : Warning si MAX_TRADES atteint ----
    if n_trades >= _MAX_TRADES:
        warnings.warn(
            f"MAX_TRADES ({_MAX_TRADES}) atteint ! Resultats tronques. "
            f"Augmenter _MAX_TRADES dans backtest_engine_numba.py.",
            RuntimeWarning, stacklevel=2,
        )

    # ---- Convertir en DataFrame ----
    if n_trades == 0:
        cols = [
            'Trade_No', 'Direction', 'Entry_DateTime', 'Exit_DateTime',
            'Duration_Min', 'Entry_GC', 'Entry_SI', 'Exit_GC', 'Exit_SI',
            'Entry_ZScore', 'Exit_ZScore', 'Exit_Reason', 'Beta',
            'GC_Contracts', 'SI_Contracts', 'PnL_GC', 'PnL_SI',
            'PnL_Gross', 'Costs', 'PnL_Net', 'Max_PnL_Intra', 'Min_PnL_Intra',
        ]
        if verbose:
            print("   Trades total  : 0")
            print("   [OK] Backtest hybride Numba termine !")
        return pd.DataFrame(columns=cols)

    trades = []
    gc_pv = cfg[CFG_GC_PV]
    si_pv = cfg[CFG_SI_PV]

    # Detecter la resolution temporelle (pandas 2.x=ns, 3.x=us)
    _ts_reso = ts_1min.dtype  # datetime64[us] ou datetime64[ns]
    _ts_unit = 'us' if 'us' in str(_ts_reso) else 'ns'

    for t in range(n_trades):
        r = raw[t]
        e_idx = int(r[2])
        x_idx = int(r[3])
        d = int(r[1])
        reason_code = int(r[13])

        entry_dt = ts_1min.iloc[e_idx]
        if r[16] > 0:
            exit_dt = pd.Timestamp(int(r[16]), unit=_ts_unit)
        else:
            exit_dt = ts_1min.iloc[x_idx]
        dur = (exit_dt - entry_dt).total_seconds() / 60.0

        is_dollar = reason_code in (_TP_DOLLAR, _SL_DOLLAR)
        if is_dollar:
            pnl_gc_val = np.nan
            pnl_si_val = np.nan
        else:
            if d == 1:
                pnl_gc_val = round((r[4] - r[6]) * gc_pv * r[8], 2)
                pnl_si_val = round((r[7] - r[5]) * si_pv * r[9], 2)
            else:
                pnl_gc_val = round((r[6] - r[4]) * gc_pv * r[8], 2)
                pnl_si_val = round((r[5] - r[7]) * si_pv * r[9], 2)

        trades.append({
            'Trade_No': int(r[0]),
            'Direction': 'LONG' if d == 1 else 'SHORT',
            'Entry_DateTime': entry_dt,
            'Exit_DateTime': exit_dt,
            'Duration_Min': round(dur, 1),
            'Entry_GC': r[4],
            'Entry_SI': r[5],
            'Exit_GC': round(r[6], 2),
            'Exit_SI': round(r[7], 4),
            'Entry_ZScore': round(zscores[e_idx], 2),
            'Exit_ZScore': round(zscores[x_idx], 2),
            'Exit_Reason': EXIT_REASON_MAP.get(reason_code, 'UNKNOWN'),
            'Beta': round(betas[e_idx], 4),
            'GC_Contracts': int(r[8]),
            'SI_Contracts': int(r[9]),
            'PnL_GC': pnl_gc_val,
            'PnL_SI': pnl_si_val,
            'PnL_Gross': round(r[10], 2),
            'Costs': round(r[11], 2),
            'PnL_Net': round(r[12], 2),
            'Max_PnL_Intra': round(r[14], 2),
            'Min_PnL_Intra': round(r[15], 2),
        })

    df = pd.DataFrame(trades)
    if len(df) > 0:
        df['PnL_Cumul'] = df['PnL_Net'].cumsum().round(2)

    if verbose:
        n_l = (df['Direction'] == 'LONG').sum()
        n_s = (df['Direction'] == 'SHORT').sum()
        print(f"   Trades total  : {len(df)} ({n_l} LONG, {n_s} SHORT)")
        for reason in EXIT_REASON_MAP.values():
            c = (df['Exit_Reason'] == reason).sum()
            if c > 0:
                print(f"   {reason:12s} : {c}")
        print("   [OK] Backtest hybride Numba termine !")

    return df


# ============================================================================
# WARMUP — Pre-compiler le kernel (appeler 1 fois au demarrage)
# ============================================================================

def warmup_numba():
    """Pre-compile le kernel avec des donnees dummy (~3-5s)."""
    n, m = 100, 600
    d = np.zeros(n, dtype=np.float64)
    di = np.zeros(n, dtype=np.int64)
    d5 = np.zeros(m, dtype=np.float64)
    d5i = np.zeros(m, dtype=np.int64)
    e = np.empty(0, dtype=np.float64)
    cfg = np.zeros(CFG_SIZE, dtype=np.float64)
    cfg[CFG_GC_PV] = 10.0
    cfg[CFG_SI_PV] = 1000.0
    cfg[CFG_GC_TV] = 1.0
    cfg[CFG_SI_TV] = 5.0
    cfg[CFG_PNL_TP] = 99999.0
    cfg[CFG_PNL_SL] = -99999.0
    cfg[CFG_Z_LONG] = -3.5
    cfg[CFG_Z_SHORT] = 3.5
    cfg[CFG_ZSCORE_SL_LONG] = -5.0
    cfg[CFG_ZSCORE_SL_SHORT] = 5.0
    cfg[CFG_ZSCORE_TP_ENABLED] = 1.0
    cfg[CFG_ZSCORE_TP_MIN_PNL] = np.nan
    cfg[CFG_SIZING_MODE] = 2.0
    cfg[CFG_SI_CONTRACTS_BASE] = 1.0
    cfg[CFG_COMMISSION_RT] = 1.88
    cfg[CFG_SLIP_GC_TICKS] = 1.0
    cfg[CFG_SLIP_SI_TICKS] = 1.0
    cfg[CFG_ENTRY_END_HOUR] = 24.0
    cfg[CFG_ZSCORE_RESET_LONG] = -1.0
    cfg[CFG_ZSCORE_RESET_SHORT] = 1.0
    cfg[CFG_SESSION_END_MINUTES] = 1020.0  # 17:00

    _run_kernel(d, d, d, d + 2700, d + 31, d + 1.0, d,
                di, di, di, d5i, d5 + 2700, d5 + 31, di,
                e, e, cfg)
    print("[OK] Numba kernel pre-compiled (warmup done)")
