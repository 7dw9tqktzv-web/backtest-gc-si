# scripts/pnl_decay_analysis.py
# PnL Decay Analysis - Etape A (1-min) + Etape B (5s)
# Analyse intra-trade pour calibrer mhb, dTP, dSL, zTP pour R2
#
# Usage: python scripts/pnl_decay_analysis.py
#
import sys, time, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides_fast, compute_metrics

# =============================================================================
# CONFIGURATION
# =============================================================================

FAMILIES = [
    {"id": 1, "zE": 3.5,  "co": 20, "zTP": 1.5,  "label": "F1_zE3.5_co20_zTP1.5"},
    {"id": 2, "zE": 3.5,  "co": 20, "zTP": 2.0,  "label": "F2_zE3.5_co20_zTP2.0"},
    {"id": 3, "zE": 3.5,  "co": 20, "zTP": 1.0,  "label": "F3_zE3.5_co20_zTP1.0"},
    {"id": 4, "zE": 3.5,  "co": 20, "zTP": 0.0,  "label": "F4_zE3.5_co20_zTP0.0"},
    {"id": 5, "zE": 3.5,  "co": 20, "zTP": 0.5,  "label": "F5_zE3.5_co20_zTP0.5"},
    {"id": 6, "zE": 3.25, "co": 40, "zTP": 0.5,  "label": "F6_zE3.25_co40_zTP0.5"},
    {"id": 7, "zE": 3.5,  "co": 20, "zTP": 0.75, "label": "F7_zE3.5_co20_zTP0.75"},
    {"id": 8, "zE": 3.5,  "co": 30, "zTP": 1.5,  "label": "F8_zE3.5_co30_zTP1.5"},
]

# Top 3 pour analyse 5s (meilleur score, plus diversifie)
TOP3_IDS = [1, 4, 6]

FIXED_OV = {
    "contracts.mode": "micro",
    "exit.zscore_tp_enabled": True,
    "costs.slippage_gc_ticks": 1,
    "costs.slippage_si_ticks": 1,
    "indicators.period": "5min",
}

IND_OV = {
    "indicators.beta_lookback": 2640,
    "indicators.zscore_period": 20,
    "indicators.correlation_period": 30,
    "indicators.adf_hurst_period": 26,
}

PLOTS_DIR = Path("output/reports/pnl_decay_plots")
REPORT_PATH = Path("output/reports/PNL_DECAY_ANALYSIS.md")

Z_THRESHOLDS = [1.5, 1.0, 0.5, 0.0]


# =============================================================================
# HELPERS
# =============================================================================

def build_config(base_config, family):
    """Construire la config pour une famille."""
    ee_ov = {
        "entry.zscore_long": -abs(family["zE"]),
        "entry.zscore_short": abs(family["zE"]),
        "entry.cointegration_score_min": family["co"],
        "exit.zscore_tp_long": -family["zTP"],
        "exit.zscore_tp_short": family["zTP"],
        "exit.zscore_sl_long": -99,
        "exit.zscore_sl_short": 99,
        "exit.pnl_take_profit": 300,
        "exit.pnl_stop_loss": -99999,
        "exit.max_holding_bars": 0,
        "session.flat_end_of_session": True,
        "sizing.micro_multiplier_max": 2,
    }
    merged = {**IND_OV, **ee_ov, **FIXED_OV}
    return apply_overrides_fast(base_config, merged)


def compute_pnl_at_bar(direction, entry_gc, entry_si, gc_price, si_price,
                        gc_contracts, si_contracts, gc_pv, si_pv):
    """Calculer le PnL brut a une barre donnee."""
    if direction == 1:  # LONG spread: short GC, long SI
        return (entry_gc - gc_price) * gc_pv * gc_contracts + \
               (si_price - entry_si) * si_pv * si_contracts
    else:  # SHORT spread: long GC, short SI
        return (gc_price - entry_gc) * gc_pv * gc_contracts + \
               (entry_si - si_price) * si_pv * si_contracts


# =============================================================================
# ETAPE A : ANALYSE 1-MIN
# =============================================================================

def analyze_trade_1min(trade, df_ind, gc_pv, si_pv):
    """Analyser un trade bar-par-bar sur les barres 1-min.

    Retourne un dict avec toutes les metriques intra-trade.
    """
    direction = 1 if trade['Direction'] == 'LONG' else -1
    entry_gc = trade['Entry_GC']
    entry_si = trade['Entry_SI']
    gc_contracts = trade['GC_Contracts']
    si_contracts = trade['SI_Contracts']
    entry_zscore = trade['Entry_ZScore']

    # Trouver les index dans df_ind (1-min avec ZScore)
    entry_dt = trade['Entry_DateTime']
    exit_dt = trade['Exit_DateTime']

    dt_vals = df_ind['DateTime'].values
    entry_dt64 = np.datetime64(entry_dt)
    exit_dt64 = np.datetime64(exit_dt)

    # Entry: match exact (entries sont sur barres 5-min alignees)
    entry_locs = np.where(dt_vals == entry_dt64)[0]
    if len(entry_locs) == 0:
        return None
    entry_idx = entry_locs[0]

    # Exit: nearest match (TP_DOLLAR exits sur timestamps 5s, pas alignes 1-min)
    exit_locs = np.where(dt_vals == exit_dt64)[0]
    if len(exit_locs) > 0:
        exit_idx = exit_locs[0]
    else:
        # Chercher la barre 1-min la plus proche <= exit_dt
        candidates = np.where(dt_vals[entry_idx:] <= exit_dt64)[0]
        if len(candidates) == 0:
            return None
        exit_idx = entry_idx + candidates[-1]

    # Extraire les arrays entre entry et exit
    gc_prices = df_ind['Last_GC'].values[entry_idx:exit_idx + 1]
    si_prices = df_ind['Last_SI'].values[entry_idx:exit_idx + 1]
    zscores = df_ind['ZScore'].values[entry_idx:exit_idx + 1]
    n_bars = len(gc_prices)

    if n_bars < 1:
        return None

    if n_bars == 1:
        # Trade ouvre et ferme dans la meme barre (typique TP_DOLLAR rapide)
        # On utilise le PnL connu du trade
        pnl_final = float(trade['PnL_Gross'])
        mfe = float(trade.get('Max_PnL_Intra', pnl_final))
        mae = float(trade.get('Min_PnL_Intra', 0))
        return {
            'trade_no': trade['Trade_No'],
            'direction': trade['Direction'],
            'exit_reason': trade['Exit_Reason'],
            'n_bars': 1,
            'pnl_final': pnl_final,
            'pnl_net': float(trade['PnL_Net']),
            'mfe': mfe,
            'mae': mae,
            'mfe_bar': 0,
            'mae_bar': 0,
            'decay_ratio': pnl_final / mfe if mfe > 10 else 0,
            'capture_eff': pnl_final / mfe if mfe > 10 else 0,
            'time_50pct': 0,
            'time_75pct': 0,
            'time_90pct': 0,
            'pnl_at_z1.5': np.nan,
            'pnl_at_z1.0': np.nan,
            'pnl_at_z0.5': np.nan,
            'pnl_at_z0.0': np.nan,
            'pnl_path': np.array([pnl_final]),
            'entry_zscore': float(entry_zscore),
        }

    # PnL bar par bar
    pnl_path = np.array([
        compute_pnl_at_bar(direction, entry_gc, entry_si,
                           gc_prices[i], si_prices[i],
                           gc_contracts, si_contracts, gc_pv, si_pv)
        for i in range(n_bars)
    ])

    # MFE / MAE
    mfe = pnl_path.max()
    mae = pnl_path.min()
    mfe_bar = int(pnl_path.argmax())
    mae_bar = int(pnl_path.argmin())
    pnl_final = pnl_path[-1]

    # Decay ratio et capture efficiency (guard: MFE > $10 pour eviter division quasi-zero)
    decay_ratio = pnl_final / mfe if mfe > 10 else 0
    capture_eff = pnl_final / mfe if mfe > 10 else 0

    # Temps pour capturer 50%, 75%, 90% du MFE
    time_to_pct = {}
    if mfe > 0:
        for pct in [0.5, 0.75, 0.9]:
            target = mfe * pct
            hits = np.where(pnl_path >= target)[0]
            time_to_pct[pct] = int(hits[0]) if len(hits) > 0 else n_bars
    else:
        time_to_pct = {0.5: n_bars, 0.75: n_bars, 0.9: n_bars}

    # PnL aux seuils Z-Score
    # Pour LONG: entry Z < 0, reversion vers 0 puis positif
    # Pour SHORT: entry Z > 0, reversion vers 0 puis negatif
    pnl_at_z = {}
    for z_thresh in Z_THRESHOLDS:
        if direction == 1:
            # LONG: Z remonte de negatif vers positif, on cherche Z >= z_thresh
            # z_thresh de reference = overshoot (ex: z_thresh=1.5 = Z atteint +1.5)
            target_z = z_thresh
            hits = np.where(zscores[1:] >= target_z)[0]  # skip bar 0 (entry)
        else:
            # SHORT: Z descend de positif vers negatif
            target_z = -z_thresh
            hits = np.where(zscores[1:] <= target_z)[0]
        if len(hits) > 0:
            first_hit = hits[0] + 1  # +1 car on a skip bar 0
            pnl_at_z[z_thresh] = float(pnl_path[first_hit])
        else:
            pnl_at_z[z_thresh] = np.nan

    return {
        'trade_no': trade['Trade_No'],
        'direction': trade['Direction'],
        'exit_reason': trade['Exit_Reason'],
        'n_bars': n_bars,
        'pnl_final': float(pnl_final),
        'pnl_net': float(trade['PnL_Net']),
        'mfe': float(mfe),
        'mae': float(mae),
        'mfe_bar': mfe_bar,
        'mae_bar': mae_bar,
        'decay_ratio': float(decay_ratio),
        'capture_eff': float(capture_eff),
        'time_50pct': time_to_pct[0.5],
        'time_75pct': time_to_pct[0.75],
        'time_90pct': time_to_pct[0.9],
        'pnl_at_z1.5': pnl_at_z.get(1.5, np.nan),
        'pnl_at_z1.0': pnl_at_z.get(1.0, np.nan),
        'pnl_at_z0.5': pnl_at_z.get(0.5, np.nan),
        'pnl_at_z0.0': pnl_at_z.get(0.0, np.nan),
        'pnl_path': pnl_path,
        'entry_zscore': float(entry_zscore),
    }


def run_etape_a(df_ind_5min, df_1min_analysis, df_5s, base_config, families):
    """Executer l'etape A pour toutes les familles.

    df_ind_5min: indicateurs 5-min (pour le backtest engine)
    df_1min_analysis: barres 1-min avec ZScore forward-fill (pour analyse bar-par-bar)
    """
    results = {}

    for fam in families:
        label = fam['label']
        print(f"\n--- {label} ---")
        config = build_config(base_config, fam)

        gc_pv = config['contracts']['gc_point_value']
        si_pv = config['contracts']['si_point_value']

        t0 = time.time()
        trades = run_hybrid_backtest(df_ind_5min, df_5s, config, verbose=False)
        dt = time.time() - t0
        print(f"  {len(trades)} trades ({dt:.1f}s)")

        # Analyser chaque trade sur barres 1-min (pas 5-min)
        trade_analyses = []
        for _, trade in trades.iterrows():
            result = analyze_trade_1min(trade, df_1min_analysis, gc_pv, si_pv)
            if result is not None:
                trade_analyses.append(result)

        print(f"  {len(trade_analyses)} trades analyses")

        # Agreger par exit_type
        df_ta = pd.DataFrame([{k: v for k, v in ta.items() if k != 'pnl_path'}
                              for ta in trade_analyses])
        if len(df_ta) > 0:
            for exit_type in df_ta['exit_reason'].unique():
                mask = df_ta['exit_reason'] == exit_type
                n = mask.sum()
                avg_pnl = df_ta.loc[mask, 'pnl_net'].mean()
                avg_mfe = df_ta.loc[mask, 'mfe'].mean()
                avg_mae = df_ta.loc[mask, 'mae'].mean()
                avg_decay = df_ta.loc[mask, 'decay_ratio'].mean()
                avg_mfe_bar = df_ta.loc[mask, 'mfe_bar'].mean()
                print(f"  {exit_type:>14s}: n={n:>3d} PnL_avg=${avg_pnl:>+7.0f} "
                      f"MFE=${avg_mfe:>+7.0f} MAE=${avg_mae:>+7.0f} "
                      f"Decay={avg_decay:.2f} Peak@bar={avg_mfe_bar:.0f}")

        results[label] = {
            'family': fam,
            'trades': trades,
            'analyses': trade_analyses,
            'df_analyses': df_ta,
        }

    return results


# =============================================================================
# ETAPE B : ANALYSE 5S (top 3 familles)
# =============================================================================

def analyze_trade_5s(trade, df_5s_arr, gc_pv, si_pv):
    """Analyser un trade sur les barres 5s."""
    direction = 1 if trade['Direction'] == 'LONG' else -1
    entry_gc = trade['Entry_GC']
    entry_si = trade['Entry_SI']
    gc_contracts = trade['GC_Contracts']
    si_contracts = trade['SI_Contracts']

    entry_dt = np.datetime64(trade['Entry_DateTime'])
    exit_dt = np.datetime64(trade['Exit_DateTime'])

    dt_5s = df_5s_arr['dt']
    gc_5s = df_5s_arr['gc']
    si_5s = df_5s_arr['si']

    # Trouver les barres 5s dans l'intervalle [entry, exit]
    # searchsorted pour gerer les cas ou entry_dt/exit_dt ne matchent pas exactement
    idx_start = np.searchsorted(dt_5s, entry_dt, side='left')
    # Elargir l'exit de 5s pour capturer la barre de sortie
    exit_dt_plus = exit_dt + np.timedelta64(5, 's')
    idx_end = np.searchsorted(dt_5s, exit_dt_plus, side='left')
    indices = np.arange(idx_start, min(idx_end, len(dt_5s)))

    if len(indices) < 1:
        return None

    # PnL 5s bar par bar
    pnl_5s = np.array([
        compute_pnl_at_bar(direction, entry_gc, entry_si,
                           gc_5s[i], si_5s[i],
                           gc_contracts, si_contracts, gc_pv, si_pv)
        for i in indices
    ])

    mfe_5s = float(pnl_5s.max())
    mae_5s = float(pnl_5s.min())
    mfe_5s_idx = int(pnl_5s.argmax())
    pnl_final_5s = float(pnl_5s[-1])

    # Pour TP_DOLLAR: dynamique autour du trigger $300
    tp_dollar_info = None
    if trade['Exit_Reason'] == 'TP_DOLLAR':
        trigger_idx = np.where(pnl_5s >= 300)[0]
        if len(trigger_idx) > 0:
            t_idx = trigger_idx[0]
            # PnL 30s avant (6 barres 5s) et 30s apres
            pre_start = max(0, t_idx - 6)
            post_end = min(len(pnl_5s), t_idx + 7)
            pnl_pre = pnl_5s[pre_start:t_idx]
            pnl_post = pnl_5s[t_idx:post_end]
            # Vitesse d'approche ($/seconde)
            if t_idx > 0:
                speed = (pnl_5s[t_idx] - pnl_5s[max(0, t_idx-6)]) / (min(t_idx, 6) * 5)
            else:
                speed = 0
            tp_dollar_info = {
                'trigger_bar': t_idx,
                'mfe_after_trigger': float(pnl_5s[t_idx:].max()) if t_idx < len(pnl_5s) else 300,
                'pnl_30s_before': float(pnl_pre.mean()) if len(pnl_pre) > 0 else np.nan,
                'pnl_30s_after': float(pnl_post.mean()) if len(pnl_post) > 0 else np.nan,
                'approach_speed': float(speed),
            }

    # Pour END_SESSION: trouver le point mort
    point_mort_info = None
    if trade['Exit_Reason'] == 'END_SESSION' and len(pnl_5s) > 20:
        # Point mort = barre apres laquelle std(fenetre 20 barres) < seuil
        window = 20  # 100 secondes
        stds = pd.Series(pnl_5s).rolling(window).std().values
        # Chercher la premiere barre ou std < $15 (micro sizing = petits montants)
        stable_bars = np.where(stds[window:] < 15)[0]
        if len(stable_bars) > 0:
            point_mort_bar = int(stable_bars[0] + window)
            point_mort_min = point_mort_bar * 5 / 60  # en minutes
        else:
            point_mort_bar = len(pnl_5s)
            point_mort_min = point_mort_bar * 5 / 60
        point_mort_info = {
            'point_mort_bar': point_mort_bar,
            'point_mort_min': float(point_mort_min),
            'pnl_at_point_mort': float(pnl_5s[min(point_mort_bar, len(pnl_5s)-1)]),
        }

    return {
        'trade_no': trade['Trade_No'],
        'direction': trade['Direction'],
        'exit_reason': trade['Exit_Reason'],
        'n_bars_5s': len(indices),
        'mfe_5s': mfe_5s,
        'mae_5s': mae_5s,
        'mfe_5s_bar': mfe_5s_idx,
        'pnl_final_5s': pnl_final_5s,
        'tp_dollar_info': tp_dollar_info,
        'point_mort_info': point_mort_info,
        'pnl_5s_path': pnl_5s,
    }


def run_etape_b(results_a, df_5s, base_config):
    """Executer l'etape B pour les top 3 familles."""
    # Pre-extraire les arrays 5s pour la performance
    df_5s_arr = {
        'dt': df_5s['DateTime'].values,
        'gc': df_5s['Last_GC'].values,
        'si': df_5s['Last_SI'].values,
    }

    results_b = {}

    for fam_id in TOP3_IDS:
        fam = [f for f in FAMILIES if f['id'] == fam_id][0]
        label = fam['label']
        print(f"\n--- 5s Analysis: {label} ---")

        config = build_config(base_config, fam)
        gc_pv = config['contracts']['gc_point_value']
        si_pv = config['contracts']['si_point_value']

        trades = results_a[label]['trades']
        analyses_5s = []

        t0 = time.time()
        for _, trade in trades.iterrows():
            result = analyze_trade_5s(trade, df_5s_arr, gc_pv, si_pv)
            if result is not None:
                analyses_5s.append(result)
        dt = time.time() - t0
        print(f"  {len(analyses_5s)} trades analyses en 5s ({dt:.1f}s)")

        # Stats TP_DOLLAR
        tp_dollar_trades = [a for a in analyses_5s
                           if a['exit_reason'] == 'TP_DOLLAR' and a['tp_dollar_info'] is not None]
        if tp_dollar_trades:
            mfe_after = [t['tp_dollar_info']['mfe_after_trigger'] for t in tp_dollar_trades]
            speeds = [t['tp_dollar_info']['approach_speed'] for t in tp_dollar_trades]
            print(f"  TP_DOLLAR ({len(tp_dollar_trades)} trades):")
            print(f"    MFE apres trigger $300: avg=${np.mean(mfe_after):.0f} "
                  f"med=${np.median(mfe_after):.0f} max=${np.max(mfe_after):.0f}")
            print(f"    Vitesse approche: avg=${np.mean(speeds):.1f}/s")

        # Stats END_SESSION
        end_session_trades = [a for a in analyses_5s
                             if a['exit_reason'] == 'END_SESSION' and a['point_mort_info'] is not None]
        if end_session_trades:
            pm_mins = [t['point_mort_info']['point_mort_min'] for t in end_session_trades]
            pm_pnls = [t['point_mort_info']['pnl_at_point_mort'] for t in end_session_trades]
            print(f"  END_SESSION ({len(end_session_trades)} trades):")
            print(f"    Point mort: avg={np.mean(pm_mins):.0f}min "
                  f"med={np.median(pm_mins):.0f}min")
            print(f"    PnL au point mort: avg=${np.mean(pm_pnls):.0f}")

        # MAE distribution 5s
        all_mae = [a['mae_5s'] for a in analyses_5s]
        if all_mae:
            p95 = np.percentile(all_mae, 5)  # 5th percentile (most negative)
            print(f"  MAE 5s: avg=${np.mean(all_mae):.0f} P5=${p95:.0f} "
                  f"min=${np.min(all_mae):.0f}")
            print(f"  -> SL recommande: ${p95:.0f} + marge = ${p95 * 1.2:.0f}")

        results_b[label] = {
            'analyses_5s': analyses_5s,
            'tp_dollar_trades': tp_dollar_trades,
            'end_session_trades': end_session_trades,
        }

    return results_b


# =============================================================================
# GRAPHIQUES
# =============================================================================

def generate_plots(results_a, results_b):
    """Generer les 8 graphiques."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Collecter toutes les analyses de la famille #1 (best score)
    best_label = FAMILIES[0]['label']
    df_ta = results_a[best_label]['df_analyses']
    analyses = results_a[best_label]['analyses']

    # --- Plot 1: PnL moyen normalise par barre (par exit type) ---
    fig, ax = plt.subplots(figsize=(12, 6))
    for exit_type in ['TP_ZSCORE', 'TP_DOLLAR', 'END_SESSION']:
        paths = [a['pnl_path'] for a in analyses if a['exit_reason'] == exit_type]
        if not paths:
            continue
        max_len = max(len(p) for p in paths)
        # Normaliser par MFE
        normalized = []
        for p in paths:
            mfe = p.max()
            if mfe > 0:
                norm_p = p / mfe
                # Pad to max_len
                padded = np.full(max_len, np.nan)
                padded[:len(norm_p)] = norm_p
                normalized.append(padded)
        if normalized:
            arr = np.array(normalized)
            mean_path = np.nanmean(arr, axis=0)
            ax.plot(mean_path, label=f'{exit_type} (n={len(paths)})', linewidth=2)
    ax.set_xlabel('Barre 1-min depuis entree')
    ax.set_ylabel('PnL / MFE (normalise)')
    ax.set_title(f'PnL normalise moyen par barre - {best_label}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '01_pnl_normalized_by_bar.png', dpi=150)
    plt.close()

    # --- Plot 2: Distribution decay ratio par exit type ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for idx, exit_type in enumerate(['TP_ZSCORE', 'TP_DOLLAR', 'END_SESSION']):
        mask = df_ta['exit_reason'] == exit_type
        if mask.sum() == 0:
            continue
        data = df_ta.loc[mask, 'decay_ratio'].clip(-2, 2)
        axes[idx].hist(data, bins=30, edgecolor='black', alpha=0.7)
        axes[idx].set_title(f'{exit_type} (n={mask.sum()})')
        axes[idx].set_xlabel('Decay Ratio (PnL_final / MFE)')
        axes[idx].axvline(x=data.mean(), color='red', linestyle='--',
                         label=f'avg={data.mean():.2f}')
        axes[idx].legend()
    plt.suptitle(f'Distribution Decay Ratio - {best_label}')
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '02_decay_ratio_distribution.png', dpi=150)
    plt.close()

    # --- Plot 3: Scatter MAE vs PnL final ---
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = {'TP_ZSCORE': 'green', 'TP_DOLLAR': 'blue',
              'END_SESSION': 'orange', 'SL_DOLLAR': 'red',
              'SL_ZSCORE': 'darkred', 'MAX_HOLD': 'purple'}
    for exit_type in df_ta['exit_reason'].unique():
        mask = df_ta['exit_reason'] == exit_type
        ax.scatter(df_ta.loc[mask, 'mae'], df_ta.loc[mask, 'pnl_net'],
                  c=colors.get(exit_type, 'gray'), label=exit_type,
                  alpha=0.6, s=40)
    ax.set_xlabel('MAE (Max Adverse Excursion)')
    ax.set_ylabel('PnL Net Final')
    ax.set_title(f'MAE vs PnL Final - {best_label}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.axvline(x=0, color='black', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '03_mae_vs_pnl.png', dpi=150)
    plt.close()

    # --- Plot 4: Histogramme barre du MFE peak par exit type ---
    fig, ax = plt.subplots(figsize=(10, 6))
    for exit_type in ['TP_ZSCORE', 'TP_DOLLAR', 'END_SESSION']:
        mask = df_ta['exit_reason'] == exit_type
        if mask.sum() == 0:
            continue
        data = df_ta.loc[mask, 'mfe_bar']
        ax.hist(data, bins=30, alpha=0.5, label=f'{exit_type} (avg={data.mean():.0f})')
    ax.set_xlabel('Barre du MFE peak (1-min)')
    ax.set_ylabel('Nombre de trades')
    ax.set_title(f'Barre du Peak MFE par exit type - {best_label}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '04_mfe_peak_bar.png', dpi=150)
    plt.close()

    # --- Plot 5: PnL moyen aux seuils Z ---
    fig, ax = plt.subplots(figsize=(10, 6))
    # Comparer les 8 familles sur les seuils Z
    for fam in FAMILIES:
        label = fam['label']
        df_fam = results_a[label]['df_analyses']
        if len(df_fam) == 0:
            continue
        z_cols = ['pnl_at_z1.5', 'pnl_at_z1.0', 'pnl_at_z0.5', 'pnl_at_z0.0']
        means = [df_fam[col].mean() for col in z_cols]
        means.append(df_fam['pnl_net'].mean())
        x_labels = ['Z=1.5', 'Z=1.0', 'Z=0.5', 'Z=0.0', 'Exit reel']
        ax.plot(x_labels, means, marker='o', label=f"zTP={fam['zTP']}", linewidth=2)
    ax.set_xlabel('Seuil Z-Score')
    ax.set_ylabel('PnL moyen ($)')
    ax.set_title('PnL moyen aux seuils Z-Score (8 familles)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '05_pnl_at_z_thresholds.png', dpi=150)
    plt.close()

    # --- Plot 6: END_SESSION PnL trajectory moyen ---
    fig, ax = plt.subplots(figsize=(12, 6))
    for fam_id in TOP3_IDS:
        fam = [f for f in FAMILIES if f['id'] == fam_id][0]
        label = fam['label']
        end_trades = [a for a in results_a[label]['analyses']
                     if a['exit_reason'] == 'END_SESSION']
        if not end_trades:
            continue
        paths = [a['pnl_path'] for a in end_trades]
        max_len = min(500, max(len(p) for p in paths))  # cap a 500 barres
        padded = []
        for p in paths:
            pad = np.full(max_len, np.nan)
            pad[:min(len(p), max_len)] = p[:max_len]
            padded.append(pad)
        arr = np.array(padded)
        mean_path = np.nanmean(arr, axis=0)
        ax.plot(mean_path, label=f"{label} (n={len(end_trades)})", linewidth=2)
    ax.set_xlabel('Barre 1-min depuis entree')
    ax.set_ylabel('PnL moyen ($)')
    ax.set_title('END_SESSION : Trajectoire PnL moyenne')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / '06_end_session_trajectory.png', dpi=150)
    plt.close()

    # --- Plot 7: TP_DOLLAR MFE post-trigger (5s) ---
    if results_b:
        fig, axes = plt.subplots(1, len(TOP3_IDS), figsize=(5 * len(TOP3_IDS), 5))
        if len(TOP3_IDS) == 1:
            axes = [axes]
        for idx, fam_id in enumerate(TOP3_IDS):
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label not in results_b:
                continue
            tp_trades = results_b[label]['tp_dollar_trades']
            if not tp_trades:
                continue
            mfe_after = [t['tp_dollar_info']['mfe_after_trigger'] for t in tp_trades]
            axes[idx].hist(mfe_after, bins=20, edgecolor='black', alpha=0.7)
            axes[idx].axvline(x=300, color='red', linestyle='--', label='Trigger $300')
            axes[idx].axvline(x=np.mean(mfe_after), color='blue', linestyle='--',
                            label=f'MFE avg=${np.mean(mfe_after):.0f}')
            axes[idx].set_title(f'{label}\nn={len(tp_trades)}')
            axes[idx].set_xlabel('MFE apres trigger ($)')
            axes[idx].legend(fontsize=8)
        plt.suptitle('TP_DOLLAR: MFE reel apres trigger $300 (5s)')
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / '07_tp_dollar_mfe_post_trigger.png', dpi=150)
        plt.close()

    # --- Plot 8: MAE distribution 5s avec P95 ---
    if results_b:
        fig, axes = plt.subplots(1, len(TOP3_IDS), figsize=(5 * len(TOP3_IDS), 5))
        if len(TOP3_IDS) == 1:
            axes = [axes]
        for idx, fam_id in enumerate(TOP3_IDS):
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label not in results_b:
                continue
            all_mae = [a['mae_5s'] for a in results_b[label]['analyses_5s']]
            if not all_mae:
                continue
            p95 = np.percentile(all_mae, 5)  # 5th pct = most negative
            axes[idx].hist(all_mae, bins=30, edgecolor='black', alpha=0.7)
            axes[idx].axvline(x=p95, color='red', linestyle='--',
                            label=f'P5=${p95:.0f}')
            axes[idx].axvline(x=np.mean(all_mae), color='blue', linestyle='--',
                            label=f'avg=${np.mean(all_mae):.0f}')
            axes[idx].set_title(f'{label}\nn={len(all_mae)}')
            axes[idx].set_xlabel('MAE ($)')
            axes[idx].legend(fontsize=8)
        plt.suptitle('MAE distribution 5s (P5 = SL recommande)')
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / '08_mae_distribution_5s.png', dpi=150)
        plt.close()

    print(f"\n[OK] {len(list(PLOTS_DIR.glob('*.png')))} graphiques sauvegardes dans {PLOTS_DIR}")


# =============================================================================
# RAPPORT
# =============================================================================

def generate_report(results_a, results_b):
    """Generer le rapport Markdown."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# PnL Decay Analysis - Grid Micro R1")
    lines.append("")
    lines.append("## Familles analysees")
    lines.append("")
    lines.append("| # | Config | Trades | PnL | WR | PF | DD | Sharpe |")
    lines.append("|---|--------|--------|-----|----|----|-----|--------|")

    for fam in FAMILIES:
        label = fam['label']
        trades = results_a[label]['trades']
        if len(trades) == 0:
            continue
        m = compute_metrics(trades)
        lines.append(f"| {fam['id']} | zE{fam['zE']}_co{fam['co']}_zTP{fam['zTP']} | "
                     f"{m['trades']} | ${m['pnl_net']:.0f} | {m['win_rate']:.1f}% | "
                     f"{m['profit_factor']:.2f} | ${m['max_dd']:.0f} | {m['sharpe']:.2f} |")

    # Etape A : Aggregation par exit type (famille #1)
    lines.append("")
    lines.append("## Etape A : Analyse 1-min")
    lines.append("")

    best_label = FAMILIES[0]['label']
    df_ta = results_a[best_label]['df_analyses']

    lines.append(f"### {best_label}")
    lines.append("")
    lines.append("| Exit Type | N | PnL avg | MFE avg | MAE avg | Decay | Peak bar |")
    lines.append("|-----------|---|---------|---------|---------|-------|----------|")

    for exit_type in ['TP_ZSCORE', 'TP_DOLLAR', 'END_SESSION', 'SL_DOLLAR', 'MAX_HOLD']:
        mask = df_ta['exit_reason'] == exit_type
        if mask.sum() == 0:
            continue
        sub = df_ta[mask]
        lines.append(f"| {exit_type} | {mask.sum()} | "
                     f"${sub['pnl_net'].mean():.0f} | ${sub['mfe'].mean():.0f} | "
                     f"${sub['mae'].mean():.0f} | {sub['decay_ratio'].mean():.2f} | "
                     f"{sub['mfe_bar'].mean():.0f} |")

    # PnL contribution par exit type
    lines.append("")
    lines.append("### Contribution PnL par exit type")
    lines.append("")
    total_pnl = df_ta['pnl_net'].sum()
    for exit_type in df_ta['exit_reason'].unique():
        mask = df_ta['exit_reason'] == exit_type
        pnl_type = df_ta.loc[mask, 'pnl_net'].sum()
        pct = pnl_type / total_pnl * 100 if total_pnl != 0 else 0
        lines.append(f"- **{exit_type}**: ${pnl_type:.0f} ({pct:.0f}%)")

    # Benchmarks Z-Score
    lines.append("")
    lines.append("### Benchmarks Z-Score (PnL moyen aux seuils)")
    lines.append("")
    lines.append("| Famille | Z=1.5 | Z=1.0 | Z=0.5 | Z=0.0 | Exit reel |")
    lines.append("|---------|-------|-------|-------|-------|-----------|")
    for fam in FAMILIES:
        label = fam['label']
        df_fam = results_a[label]['df_analyses']
        if len(df_fam) == 0:
            continue
        z15 = df_fam['pnl_at_z1.5'].mean()
        z10 = df_fam['pnl_at_z1.0'].mean()
        z05 = df_fam['pnl_at_z0.5'].mean()
        z00 = df_fam['pnl_at_z0.0'].mean()
        real = df_fam['pnl_net'].mean()
        lines.append(f"| zTP={fam['zTP']} | ${z15:.0f} | ${z10:.0f} | "
                     f"${z05:.0f} | ${z00:.0f} | ${real:.0f} |")

    # Etape B : Resultats 5s
    if results_b:
        lines.append("")
        lines.append("## Etape B : Analyse 5s (Top 3)")
        lines.append("")

        for fam_id in TOP3_IDS:
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label not in results_b:
                continue

            lines.append(f"### {label}")
            lines.append("")

            # TP_DOLLAR
            tp_trades = results_b[label]['tp_dollar_trades']
            if tp_trades:
                mfe_after = [t['tp_dollar_info']['mfe_after_trigger'] for t in tp_trades]
                lines.append(f"**TP_DOLLAR** ({len(tp_trades)} trades):")
                lines.append(f"- MFE apres trigger $300: avg=${np.mean(mfe_after):.0f}, "
                             f"med=${np.median(mfe_after):.0f}, max=${np.max(mfe_after):.0f}")
                if np.mean(mfe_after) > 350:
                    lines.append(f"- -> dTP trop agressif, le trade continuait. Tester $400-500")
                else:
                    lines.append(f"- -> dTP $300 optimal, MFE proche du trigger")
                lines.append("")

            # END_SESSION
            es_trades = results_b[label]['end_session_trades']
            if es_trades:
                pm_mins = [t['point_mort_info']['point_mort_min'] for t in es_trades]
                pm_pnls = [t['point_mort_info']['pnl_at_point_mort'] for t in es_trades]
                lines.append(f"**END_SESSION** ({len(es_trades)} trades):")
                lines.append(f"- Point mort moyen: {np.mean(pm_mins):.0f} min")
                lines.append(f"- PnL au point mort: avg=${np.mean(pm_pnls):.0f}")
                mhb_rec = int(np.median(pm_mins) + 30)  # + 30 min marge
                lines.append(f"- -> MHB recommande: {mhb_rec} min (median + 30 min marge)")
                lines.append("")

            # MAE
            all_mae = [a['mae_5s'] for a in results_b[label]['analyses_5s']]
            if all_mae:
                p95 = np.percentile(all_mae, 5)
                lines.append(f"**MAE 5s** ({len(all_mae)} trades):")
                lines.append(f"- Avg: ${np.mean(all_mae):.0f}, P5: ${p95:.0f}, "
                             f"Min: ${np.min(all_mae):.0f}")
                sl_rec = int(p95 * 1.2)
                lines.append(f"- -> SL recommande: ${sl_rec} (P5 x 1.2)")
                lines.append("")

    # Recommandations R2
    lines.append("")
    lines.append("## Recommandations R2")
    lines.append("")
    lines.append("Basees sur l'analyse PnL decay :")
    lines.append("")

    # mhb
    if results_b:
        all_pm = []
        for fam_id in TOP3_IDS:
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label in results_b:
                es = results_b[label]['end_session_trades']
                if es:
                    all_pm.extend([t['point_mort_info']['point_mort_min'] for t in es])
        if all_pm:
            lines.append(f"- **mhb**: {int(np.median(all_pm) + 30)} min "
                         f"(median point mort {np.median(all_pm):.0f} + 30 min marge)")

        # dTP
        all_mfe_after = []
        for fam_id in TOP3_IDS:
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label in results_b:
                tp = results_b[label]['tp_dollar_trades']
                if tp:
                    all_mfe_after.extend([t['tp_dollar_info']['mfe_after_trigger'] for t in tp])
        if all_mfe_after:
            avg_mfe = np.mean(all_mfe_after)
            if avg_mfe > 350:
                lines.append(f"- **dTP**: tester $400-500 (MFE post-trigger avg=${avg_mfe:.0f})")
            else:
                lines.append(f"- **dTP**: $300 confirme (MFE post-trigger avg=${avg_mfe:.0f})")

        # dSL
        all_mae_5s = []
        for fam_id in TOP3_IDS:
            fam = [f for f in FAMILIES if f['id'] == fam_id][0]
            label = fam['label']
            if label in results_b:
                all_mae_5s.extend([a['mae_5s'] for a in results_b[label]['analyses_5s']])
        if all_mae_5s:
            p95 = np.percentile(all_mae_5s, 5)
            lines.append(f"- **dSL**: ${int(p95 * 1.2)} (P5 MAE ${p95:.0f} x 1.2)")

    # zTP
    lines.append("")
    lines.append("### Z-Score TP optimal")
    best_z = None
    best_ratio = -1
    for fam in FAMILIES:
        if fam['zE'] != 3.5 or fam['co'] != 20:
            continue
        label = fam['label']
        df_fam = results_a[label]['df_analyses']
        if len(df_fam) == 0:
            continue
        m = compute_metrics(results_a[label]['trades'])
        # Ratio = PnL / DD (Calmar)
        calmar = m['pnl_net'] / abs(m['max_dd']) if m['max_dd'] != 0 else 0
        if calmar > best_ratio:
            best_ratio = calmar
            best_z = fam['zTP']
    if best_z is not None:
        lines.append(f"- **zTP optimal**: {best_z} (meilleur Calmar dans la zone zE=3.5/co=20)")

    lines.append("")
    lines.append("---")
    lines.append("*Genere par pnl_decay_analysis.py*")

    report_text = "\n".join(lines)
    REPORT_PATH.write_text(report_text, encoding='utf-8')
    print(f"\n[OK] Rapport sauvegarde: {REPORT_PATH}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("PNL DECAY ANALYSIS - Grid Micro R1")
    print("=" * 70)

    # 1. Charger les donnees
    print("\n=== CHARGEMENT DONNEES ===")
    t0 = time.time()
    df_1min, base_config, stats = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"OK: {len(df_5min)} barres 5min, {len(df_5s)} barres 5s ({time.time()-t0:.1f}s)")

    # 2. Calculer indicateurs (1 seule fois, memes params pour les 8 familles)
    print("\n=== CALCUL INDICATEURS ===")
    config_ind = apply_overrides_fast(base_config, {**IND_OV, **FIXED_OV})
    t1 = time.time()
    df_ind = calculate_all_indicators(df_5min, config_ind, verbose=False)
    print(f"OK: {len(df_ind)} lignes ({time.time()-t1:.1f}s)")

    # IMPORTANT: df_ind est en 5-min, mais le backtest engine utilise df_1min
    # en interne. Pour l'analyse bar-par-bar on a besoin des barres 1-min
    # avec les indicateurs. Le backtest engine recoit df_ind (5-min) et df_5s.
    # Pour reconstruire le PnL 1-min, on utilise df_1min (prix) + df_ind (ZScore).
    # Mais les ZScores sont sur 5-min...
    # On va analyser sur les barres 5-min (df_ind) pour les seuils Z,
    # et sur les barres 1-min pour le PnL bar-par-bar.

    # Pour le PnL 1-min, on utilise df_1min directement (prix disponibles)
    # Pour les Z-Scores, on forward-fill depuis df_ind vers df_1min
    print("\n=== MERGE Z-SCORE 5min -> 1min ===")
    df_1min_analysis = df_1min.copy()
    # Forward-fill ZScore from 5-min to 1-min
    zscore_5min = df_ind[['DateTime', 'ZScore']].rename(columns={'ZScore': 'ZScore_5min'})
    df_1min_analysis = pd.merge_asof(
        df_1min_analysis.sort_values('DateTime'),
        zscore_5min.sort_values('DateTime'),
        on='DateTime',
        direction='backward'
    )
    # Rename for consistency
    df_1min_analysis['ZScore'] = df_1min_analysis['ZScore_5min']
    print(f"OK: {len(df_1min_analysis)} barres 1-min avec ZScore")

    # 3. Etape A : Analyse 1-min (8 familles)
    print("\n" + "=" * 70)
    print("ETAPE A : ANALYSE 1-MIN (8 familles)")
    print("=" * 70)
    results_a = run_etape_a(df_ind, df_1min_analysis, df_5s, base_config, FAMILIES)

    # 4. Etape B : Analyse 5s (top 3)
    print("\n" + "=" * 70)
    print("ETAPE B : ANALYSE 5S (Top 3 familles)")
    print("=" * 70)
    results_b = run_etape_b(results_a, df_5s, base_config)

    # 5. Graphiques
    print("\n" + "=" * 70)
    print("GRAPHIQUES")
    print("=" * 70)
    generate_plots(results_a, results_b)

    # 6. Rapport
    print("\n" + "=" * 70)
    print("RAPPORT")
    print("=" * 70)
    generate_report(results_a, results_b)

    print("\n" + "=" * 70)
    print("ANALYSE TERMINEE")
    print("=" * 70)


if __name__ == '__main__':
    main()
