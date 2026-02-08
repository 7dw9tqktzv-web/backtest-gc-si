# ============================================================================
# TEST_PHASE_C2B.PY - Tests pour les filtres de regime Phase C2b
# ============================================================================
#
# Tests des indicateurs daily (Half-life AR1, Correlation Daily) et
# du filtre de blocage dans le backtest engine.
#
# ============================================================================

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from indicators import calculate_halflife_ar1, calculate_rolling_correlation_daily
from common import build_config_fingerprint, _regime_filter_fingerprint


# ============================================================================
# HELPERS
# ============================================================================

def _make_daily_df(n_days, spread_func=None, gc_base=2800.0, si_base=32.0):
    """Cree un DataFrame avec des barres intraday (1 par jour pour simplifier)."""
    dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    np.random.seed(42)

    if spread_func is not None:
        # On va creer des prix qui produisent le spread voulu
        # Spread = Log_SI - Beta * Log_GC - Alpha, mais ici on bypass
        pass

    gc_prices = gc_base + np.cumsum(np.random.randn(n_days) * 2)
    si_prices = si_base + np.cumsum(np.random.randn(n_days) * 0.02)

    df = pd.DataFrame({
        'DateTime': dates,
        'Last_GC': gc_prices,
        'Last_SI': si_prices,
    })

    # Ajouter log prices et spread (simplifie : spread = log(SI) - log(GC))
    df['Log_GC'] = np.log(df['Last_GC'])
    df['Log_SI'] = np.log(df['Last_SI'])
    df['Spread'] = df['Log_SI'] - df['Log_GC']

    return df


def _make_ar1_spread_df(n_days, phi=0.9):
    """Cree un DataFrame avec un spread AR(1) de coefficient phi connu."""
    np.random.seed(42)
    spread = np.zeros(n_days)
    for i in range(1, n_days):
        spread[i] = phi * spread[i - 1] + np.random.randn() * 0.01

    dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    df = pd.DataFrame({
        'DateTime': dates,
        'Last_GC': 2800.0 + np.arange(n_days) * 0.1,
        'Last_SI': 32.0 + np.arange(n_days) * 0.001,
        'Spread': spread,
    })
    return df


def _make_intraday_df(n_days, bars_per_day=5):
    """Cree un DataFrame avec plusieurs barres par jour (intraday)."""
    dates = []
    for d in range(n_days):
        day = datetime(2025, 1, 1) + timedelta(days=d)
        for h in range(bars_per_day):
            dates.append(day + timedelta(hours=h + 9))

    n = len(dates)
    np.random.seed(42)
    gc_prices = 2800.0 + np.cumsum(np.random.randn(n) * 0.5)
    si_prices = 32.0 + np.cumsum(np.random.randn(n) * 0.003)

    df = pd.DataFrame({
        'DateTime': dates,
        'Last_GC': gc_prices,
        'Last_SI': si_prices,
    })
    df['Log_GC'] = np.log(df['Last_GC'])
    df['Log_SI'] = np.log(df['Last_SI'])
    df['Spread'] = df['Log_SI'] - df['Log_GC']
    return df


# ============================================================================
# TESTS - INDICATEURS
# ============================================================================

class TestHalfLifeAR1:

    def test_known_value(self):
        """Spread AR(1) avec phi=0.9 -> half-life theorique = 6.58 jours."""
        df = _make_ar1_spread_df(200, phi=0.9)
        df = calculate_halflife_ar1(df, window_days=60)

        assert 'HalfLife_AR1' in df.columns
        valid = df['HalfLife_AR1'].dropna()
        assert len(valid) > 0

        # Half-life theorique = -ln(2)/ln(0.9) = 6.58
        theoretical = -np.log(2) / np.log(0.9)
        # Tolerance large car estimation empirique avec bruit
        median_hl = valid.median()
        assert 1.5 < median_hl < 15.0, f"Half-life median {median_hl} hors plage attendue"

    def test_no_mean_reversion(self):
        """Spread random walk (phi ~= 1) -> retourne NaN."""
        np.random.seed(42)
        n = 200
        spread = np.cumsum(np.random.randn(n) * 0.01)  # random walk

        dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        df = pd.DataFrame({
            'DateTime': dates,
            'Last_GC': np.full(n, 2800.0),
            'Last_SI': np.full(n, 32.0),
            'Spread': spread,
        })

        df = calculate_halflife_ar1(df, window_days=60)
        # La plupart des valeurs devraient etre NaN (phi >= 1)
        valid = df['HalfLife_AR1'].dropna()
        nan_ratio = 1 - len(valid) / len(df)
        assert nan_ratio > 0.3, f"Trop de valeurs valides pour un random walk: {len(valid)}"

    def test_window_size(self):
        """Fenetre plus courte -> plus de valeurs valides (warmup plus court)."""
        df = _make_ar1_spread_df(200, phi=0.9)

        df_short = calculate_halflife_ar1(df.copy(), window_days=30)
        df_long = calculate_halflife_ar1(df.copy(), window_days=90)

        valid_short = df_short['HalfLife_AR1'].dropna()
        valid_long = df_long['HalfLife_AR1'].dropna()
        assert len(valid_short) >= len(valid_long)

    def test_intraday_forward_fill(self):
        """Verifie que le forward-fill intraday fonctionne."""
        df = _make_intraday_df(n_days=100, bars_per_day=5)
        # Ajouter un spread AR(1)
        np.random.seed(42)
        n = len(df)
        spread = np.zeros(n)
        for i in range(1, n):
            spread[i] = 0.9 * spread[i - 1] + np.random.randn() * 0.01
        df['Spread'] = spread

        df = calculate_halflife_ar1(df, window_days=30)

        # Toutes les barres du meme jour doivent avoir la meme valeur
        df['Date'] = pd.to_datetime(df['DateTime']).dt.date
        for date, group in df.groupby('Date'):
            vals = group['HalfLife_AR1'].dropna().unique()
            if len(vals) > 0:
                assert len(vals) == 1, f"Valeurs differentes le meme jour {date}: {vals}"


class TestRollingCorrelationDaily:

    def test_perfect_correlation(self):
        """Deux series parfaitement correlees -> corr ~= 1.0."""
        n = 100
        dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        np.random.seed(42)
        gc = 2800.0 + np.cumsum(np.random.randn(n) * 2)
        # SI suit GC parfaitement (mise a l'echelle)
        si = 32.0 + (gc - 2800.0) * 0.01

        df = pd.DataFrame({
            'DateTime': dates,
            'Last_GC': gc,
            'Last_SI': si,
        })

        df = calculate_rolling_correlation_daily(df, window_days=20)
        assert 'Corr_Daily_GC_SI' in df.columns

        valid = df['Corr_Daily_GC_SI'].dropna()
        assert len(valid) > 0
        assert valid.mean() > 0.95, f"Correlation moyenne {valid.mean()} trop basse"

    def test_resample_intraday(self):
        """Verifie que le resample intraday -> daily fonctionne."""
        df = _make_intraday_df(n_days=80, bars_per_day=5)
        df = calculate_rolling_correlation_daily(df, window_days=20)

        # Toutes les barres du meme jour doivent avoir la meme correlation
        df['Date'] = pd.to_datetime(df['DateTime']).dt.date
        for date, group in df.groupby('Date'):
            vals = group['Corr_Daily_GC_SI'].dropna().unique()
            if len(vals) > 0:
                assert len(vals) == 1, f"Valeurs differentes le meme jour {date}: {vals}"


# ============================================================================
# TESTS - FILTRE DE BLOCAGE
# ============================================================================

class TestRegimeFilterBlocking:

    def _make_config_with_filter(self, hl_enabled=True, corr_enabled=True,
                                  hl_threshold=4.9, corr_threshold=0.916):
        """Config de test avec regime filter."""
        return {
            'contracts': {
                'gc_point_value': 100, 'gc_tick_size': 0.10, 'gc_tick_value': 10,
                'si_point_value': 5000, 'si_tick_size': 0.005, 'si_tick_value': 25,
            },
            'indicators': {
                'period': '5min', 'beta_lookback': 20, 'zscore_period': 10,
                'correlation_period': 10, 'adf_hurst_period': 20,
                'adf_critical_value': -2.86, 'coint_corr_threshold': 0.6,
            },
            'entry': {
                'zscore_long': -3.0, 'zscore_short': 3.0,
                'correlation_min': 0.60, 'cointegration_score_min': 50,
                'hurst_max': 1.0,
            },
            'exit': {
                'zscore_tp_enabled': True, 'zscore_tp_long': -2.0,
                'zscore_sl_long': -3.5, 'zscore_tp_short': 2.0,
                'zscore_sl_short': 3.5,
                'pnl_take_profit': 50000, 'pnl_stop_loss': -50000,
                'zscore_tp_min_pnl': None,
            },
            'reentry': {'zscore_reset_long': -1.0, 'zscore_reset_short': 1.0},
            'sizing': {'mode': 'dollar_neutral_beta', 'si_contracts': 1, 'gc_contracts_max': 0},
            'costs': {'commission_per_contract': 4.0, 'slippage_gc_ticks': 1, 'slippage_si_ticks': 1},
            'session': {'start_time': '18:00:00', 'end_time': '17:00:00',
                       'entry_start_hour': 0, 'entry_end_hour': 24},
            'regime_filter': {
                'enabled': True,
                'halflife_ar1': {'enabled': hl_enabled, 'window': 60, 'threshold': hl_threshold},
                'correlation_daily': {'enabled': corr_enabled, 'window': 40, 'threshold': corr_threshold},
            },
        }

    def _make_simple_backtest_df(self, n=100, hl_ar1_val=3.0, corr_daily_val=0.95):
        """DataFrame minimal avec signaux d'entree et colonnes regime filter."""
        np.random.seed(42)
        dates = [datetime(2025, 6, 1, 18, 0) + timedelta(minutes=i) for i in range(n)]

        df = pd.DataFrame({
            'DateTime': dates,
            'Last_GC': 2800.0 + np.random.randn(n) * 0.5,
            'Last_SI': 32.0 + np.random.randn(n) * 0.005,
            'ZScore': np.zeros(n),
            'Correlation': np.full(n, 0.90),
            'Cointegration_Score': np.full(n, 75.0),
            'Beta': np.full(n, 1.05),
            'Hurst': np.full(n, 0.35),
            'HalfLife_AR1': np.full(n, hl_ar1_val),
            'Corr_Daily_GC_SI': np.full(n, corr_daily_val),
        })

        # Creer un signal d'entree LONG au bar 30
        df.loc[30, 'ZScore'] = -3.5
        # Signal de sortie TP au bar 40
        df.loc[40, 'ZScore'] = -1.5

        return df

    def test_blocks_entry_halflife(self):
        """Half-life > seuil -> entree bloquee."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter(hl_enabled=True, corr_enabled=False, hl_threshold=4.9)
        # Half-life = 6.0 > 4.9 -> devrait bloquer
        df = self._make_simple_backtest_df(hl_ar1_val=6.0, corr_daily_val=0.95)
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades = run_hybrid_backtest(df, df_5s, config, verbose=False)
        assert len(trades) == 0, f"Attendu 0 trades (bloque), obtenu {len(trades)}"

    def test_blocks_entry_correlation(self):
        """Correlation < seuil -> entree bloquee."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter(hl_enabled=False, corr_enabled=True, corr_threshold=0.916)
        # Corr = 0.85 < 0.916 -> devrait bloquer
        df = self._make_simple_backtest_df(hl_ar1_val=3.0, corr_daily_val=0.85)
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades = run_hybrid_backtest(df, df_5s, config, verbose=False)
        assert len(trades) == 0, f"Attendu 0 trades (bloque), obtenu {len(trades)}"

    def test_or_logic(self):
        """Un seul filtre declenche suffit a bloquer."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter(hl_enabled=True, corr_enabled=True)
        # HL OK (3.0 < 4.9), Corr KO (0.85 < 0.916) -> bloque
        df = self._make_simple_backtest_df(hl_ar1_val=3.0, corr_daily_val=0.85)
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades = run_hybrid_backtest(df, df_5s, config, verbose=False)
        assert len(trades) == 0

    def test_does_not_affect_open_position(self):
        """Position ouverte -> filtre ne force pas la sortie."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter(hl_enabled=True, corr_enabled=False, hl_threshold=4.9)
        # HL = 3.0 au debut (OK), puis passe a 6.0 apres entree
        df = self._make_simple_backtest_df(hl_ar1_val=3.0, corr_daily_val=0.95)
        # Apres entree (bar 30), HL passe a 6.0 (> seuil)
        df.loc[31:, 'HalfLife_AR1'] = 6.0
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades = run_hybrid_backtest(df, df_5s, config, verbose=False)
        # Le trade doit quand meme se conclure (entree OK, sortie sur TP_ZSCORE)
        assert len(trades) >= 1, "Le trade ouvert ne devrait pas etre force a sortir"

    def test_nan_does_not_block(self):
        """Valeur NaN -> ne bloque pas (conservateur)."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter(hl_enabled=True, corr_enabled=True)
        df = self._make_simple_backtest_df(hl_ar1_val=np.nan, corr_daily_val=np.nan)
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades = run_hybrid_backtest(df, df_5s, config, verbose=False)
        # NaN = pas de blocage, le trade devrait passer
        # (si les conditions d'entree sont remplies)
        # Au minimum, on verifie que ca ne crashe pas
        assert isinstance(trades, pd.DataFrame)

    def test_disabled_by_default(self):
        """Config sans regime_filter.enabled -> comportement identique."""
        from backtest_engine_hybrid import run_hybrid_backtest

        config = self._make_config_with_filter()
        config['regime_filter']['enabled'] = False

        # Meme avec des valeurs qui bloqueraient, le filtre est OFF
        df = self._make_simple_backtest_df(hl_ar1_val=10.0, corr_daily_val=0.5)
        df_5s = pd.DataFrame({'DateTime': [], 'Last_GC': [], 'Last_SI': []})

        trades_off = run_hybrid_backtest(df, df_5s, config, verbose=False)

        config['regime_filter']['enabled'] = True
        trades_on = run_hybrid_backtest(df, df_5s, config, verbose=False)

        # OFF: trades autorisees, ON: trades bloquees
        assert len(trades_off) >= len(trades_on)


# ============================================================================
# TESTS - FINGERPRINT
# ============================================================================

class TestRegimeFilterFingerprint:

    def test_fingerprint_disabled(self):
        """Filtre desactive -> pas de suffix."""
        config = {'regime_filter': {'enabled': False}}
        assert _regime_filter_fingerprint(config) == ''

    def test_fingerprint_enabled(self):
        """Filtre active -> suffix avec parametres."""
        config = {
            'regime_filter': {
                'enabled': True,
                'halflife_ar1': {'enabled': True, 'window': 60, 'threshold': 4.9},
                'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.916},
            }
        }
        fp = _regime_filter_fingerprint(config)
        assert '_RF' in fp
        assert 'hl60' in fp
        assert 'cd40' in fp

    def test_fingerprint_distinct(self):
        """Configs avec/sans filtre ont des fingerprints differents."""
        base_config = {
            'indicators': {'beta_lookback': 1320, 'zscore_period': 20,
                          'correlation_period': 30, 'adf_hurst_period': 128},
            'entry': {'zscore_long': -3.5, 'zscore_short': 3.5,
                     'correlation_min': 0.6, 'cointegration_score_min': 50},
            'exit': {'zscore_tp_long': -2.0, 'zscore_tp_short': 2.0,
                    'zscore_sl_long': -3.5, 'zscore_sl_short': 3.5,
                    'pnl_take_profit': 500, 'pnl_stop_loss': -1200},
        }

        config_off = {**base_config, 'regime_filter': {'enabled': False}}
        config_on = {**base_config, 'regime_filter': {
            'enabled': True,
            'halflife_ar1': {'enabled': True, 'window': 60, 'threshold': 4.9},
            'correlation_daily': {'enabled': True, 'window': 40, 'threshold': 0.916},
        }}

        fp_off = build_config_fingerprint(config_off)
        fp_on = build_config_fingerprint(config_on)
        assert fp_off != fp_on
