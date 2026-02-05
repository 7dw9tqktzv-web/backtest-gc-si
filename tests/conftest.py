# ============================================================================
# CONFTEST.PY - Fixtures partagees pour les tests
# ============================================================================
#
# Ce fichier contient les fixtures pytest utilisees par tous les tests.
# Les fixtures fournissent des donnees de test synthetiques pour eviter
# de dependre des fichiers CSV reels (tests rapides et reproductibles).
#
# ============================================================================

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_config():
    """
    Configuration de test minimale.
    Reproduit la structure de config/strategy_params.yaml.
    """
    return {
        'data': {
            'gc_file': 'data/raw/GC_test.txt',
            'si_file': 'data/raw/SI_test.txt',
        },
        'contracts': {
            'gc_point_value': 100,
            'gc_tick_size': 0.10,
            'gc_tick_value': 10,
            'si_point_value': 5000,
            'si_tick_size': 0.005,
            'si_tick_value': 25,
        },
        'indicators': {
            'period': '1min',
            'beta_lookback': 20,  # Reduit pour les tests
            'zscore_period': 10,
            'correlation_period': 10,
            'adf_hurst_period': 20,
            'adf_critical_value': -2.86,
            'coint_corr_threshold': 0.6,
        },
        'entry': {
            'zscore_long': -3.0,
            'zscore_short': 3.0,
            'correlation_min': 0.60,
            'cointegration_score_min': 50,
            'hurst_max': 1.0,
        },
        'exit': {
            'zscore_tp_enabled': True,
            'zscore_tp_long': -2.0,
            'zscore_sl_long': -3.5,
            'zscore_tp_short': 2.0,
            'zscore_sl_short': 3.5,
            'pnl_take_profit': 300,
            'pnl_stop_loss': -600,
            'zscore_tp_min_pnl': None,
        },
        'reentry': {
            'zscore_reset_long': -1.0,
            'zscore_reset_short': 1.0,
        },
        'sizing': {
            'mode': 'dollar_neutral_beta',
            'si_contracts': 1,
            'gc_contracts_max': 0,
        },
        'costs': {
            'commission_per_contract': 4.00,
            'slippage_gc_ticks': 1,
            'slippage_si_ticks': 1,
        },
        'session': {
            'start_time': '18:00:00',
            'end_time': '17:00:00',
            'entry_start_hour': 0,
            'entry_end_hour': 24,
        },
    }


@pytest.fixture
def sample_prices_df():
    """
    DataFrame de test avec prix GC et SI synthetiques.
    Genere 100 barres avec des prix realistes et correlatifs.
    """
    np.random.seed(42)  # Reproductibilite
    n = 100

    # Prix de base
    gc_base = 2800.0
    si_base = 32.0

    # Generer des mouvements correles
    common_factor = np.cumsum(np.random.randn(n) * 0.5)
    gc_noise = np.cumsum(np.random.randn(n) * 0.3)
    si_noise = np.cumsum(np.random.randn(n) * 0.002)

    gc_prices = gc_base + common_factor * 2 + gc_noise
    si_prices = si_base + common_factor * 0.02 + si_noise

    # Creer le DataFrame
    start_date = datetime(2026, 1, 1, 18, 0, 0)
    dates = [start_date + timedelta(minutes=i) for i in range(n)]

    df = pd.DataFrame({
        'DateTime': dates,
        'Last_GC': gc_prices,
        'Last_SI': si_prices,
        'High_GC': gc_prices + np.random.rand(n) * 0.5,
        'Low_GC': gc_prices - np.random.rand(n) * 0.5,
        'High_SI': si_prices + np.random.rand(n) * 0.01,
        'Low_SI': si_prices - np.random.rand(n) * 0.01,
        'Volume_GC': np.random.randint(100, 1000, n),
        'Volume_SI': np.random.randint(50, 500, n),
    })

    return df


@pytest.fixture
def sample_df_with_indicators(sample_prices_df, sample_config):
    """
    DataFrame avec tous les indicateurs calcules.
    Utilise des valeurs synthetiques pour les tests rapides.
    """
    df = sample_prices_df.copy()
    n = len(df)

    # Log prices
    df['Log_GC'] = np.log(df['Last_GC'])
    df['Log_SI'] = np.log(df['Last_SI'])

    # Beta et Alpha (valeurs synthetiques realistes)
    df['Beta'] = 1.0 + np.random.randn(n) * 0.1
    df['Alpha'] = np.random.randn(n) * 0.01

    # Spread
    df['Spread'] = df['Log_SI'] - df['Beta'] * df['Log_GC'] - df['Alpha']

    # Z-Score avec oscillation pour generer des signaux
    zscore_base = np.sin(np.linspace(0, 4*np.pi, n)) * 4
    df['ZScore'] = zscore_base + np.random.randn(n) * 0.3
    df['Spread_Mean'] = df['Spread'].rolling(10).mean()
    df['Spread_Std'] = df['Spread'].rolling(10).std()

    # Correlation elevee (strategie requiert > 0.6)
    df['Correlation'] = 0.85 + np.random.randn(n) * 0.05
    df['Correlation'] = df['Correlation'].clip(0.5, 0.99)

    # ADF et Hurst
    df['ADF_Statistic'] = -3.0 + np.random.randn(n) * 0.5
    df['Hurst'] = 0.35 + np.random.rand(n) * 0.2  # < 0.5 = mean reverting
    df['HalfLife'] = 20 + np.random.rand(n) * 10

    # Score de cointegration eleve
    df['Cointegration_Score'] = 70 + np.random.randn(n) * 10
    df['Cointegration_Score'] = df['Cointegration_Score'].clip(0, 100)

    # Les premieres barres sont NaN (pas assez de donnees)
    warmup = sample_config['indicators']['beta_lookback']
    for col in ['Beta', 'Alpha', 'Spread', 'ZScore', 'Spread_Mean', 'Spread_Std',
                'Correlation', 'ADF_Statistic', 'Hurst', 'HalfLife', 'Cointegration_Score']:
        df.loc[:warmup-1, col] = np.nan

    return df


@pytest.fixture
def sample_trades_df():
    """
    DataFrame de trades de test pour metrics.
    """
    return pd.DataFrame([
        {
            'Trade_No': 1,
            'Direction': 'LONG',
            'Entry_DateTime': datetime(2026, 1, 1, 10, 0),
            'Exit_DateTime': datetime(2026, 1, 1, 11, 30),
            'Duration_Min': 90,
            'Entry_GC': 2800.0,
            'Entry_SI': 32.0,
            'Exit_GC': 2798.0,
            'Exit_SI': 32.05,
            'Entry_ZScore': -3.2,
            'Exit_ZScore': -1.8,
            'Exit_Reason': 'TP_ZSCORE',
            'Beta': 1.05,
            'GC_Contracts': 6,
            'SI_Contracts': 1,
            'PnL_Gross': 450.0,
            'Costs': 78.0,
            'PnL_Net': 372.0,
        },
        {
            'Trade_No': 2,
            'Direction': 'SHORT',
            'Entry_DateTime': datetime(2026, 1, 1, 14, 0),
            'Exit_DateTime': datetime(2026, 1, 1, 15, 0),
            'Duration_Min': 60,
            'Entry_GC': 2805.0,
            'Entry_SI': 32.10,
            'Exit_GC': 2808.0,
            'Exit_SI': 32.05,
            'Entry_ZScore': 3.5,
            'Exit_ZScore': 1.5,
            'Exit_Reason': 'TP_ZSCORE',
            'Beta': 1.02,
            'GC_Contracts': 6,
            'SI_Contracts': 1,
            'PnL_Gross': 550.0,
            'Costs': 78.0,
            'PnL_Net': 472.0,
        },
        {
            'Trade_No': 3,
            'Direction': 'LONG',
            'Entry_DateTime': datetime(2026, 1, 2, 9, 0),
            'Exit_DateTime': datetime(2026, 1, 2, 9, 30),
            'Duration_Min': 30,
            'Entry_GC': 2810.0,
            'Entry_SI': 32.20,
            'Exit_GC': 2815.0,
            'Exit_SI': 32.15,
            'Entry_ZScore': -3.1,
            'Exit_ZScore': -3.6,
            'Exit_Reason': 'SL_ZSCORE',
            'Beta': 1.03,
            'GC_Contracts': 6,
            'SI_Contracts': 1,
            'PnL_Gross': -750.0,
            'Costs': 78.0,
            'PnL_Net': -828.0,
        },
    ])


@pytest.fixture
def sample_trades_list():
    """
    Liste de trades au format CSV (valeurs string).
    Reproduit le format retourne par csv.DictReader (attendu par metrics.py).
    PnL_Cumul doit etre coherent : 372, 844, 16.
    """
    return [
        {
            'Trade_No': '1', 'Direction': 'LONG',
            'Entry_DateTime': '2026-01-01 10:00:00',
            'Exit_DateTime': '2026-01-01 11:30:00',
            'Duration_Min': '90.0',
            'Entry_GC': '2800.0', 'Entry_SI': '32.0',
            'Exit_GC': '2798.0', 'Exit_SI': '32.05',
            'Entry_ZScore': '-3.2', 'Exit_ZScore': '-1.8',
            'Exit_Reason': 'TP_ZSCORE',
            'Beta': '1.05', 'GC_Contracts': '6', 'SI_Contracts': '1',
            'PnL_GC': '200.0', 'PnL_SI': '250.0',
            'PnL_Gross': '450.0', 'Costs': '78.0', 'PnL_Net': '372.0',
            'Max_PnL_Intra': '500.0', 'Min_PnL_Intra': '-50.0',
            'PnL_Cumul': '372.0',
        },
        {
            'Trade_No': '2', 'Direction': 'SHORT',
            'Entry_DateTime': '2026-01-01 14:00:00',
            'Exit_DateTime': '2026-01-01 15:00:00',
            'Duration_Min': '60.0',
            'Entry_GC': '2805.0', 'Entry_SI': '32.10',
            'Exit_GC': '2808.0', 'Exit_SI': '32.05',
            'Entry_ZScore': '3.5', 'Exit_ZScore': '1.5',
            'Exit_Reason': 'TP_ZSCORE',
            'Beta': '1.02', 'GC_Contracts': '6', 'SI_Contracts': '1',
            'PnL_GC': '300.0', 'PnL_SI': '250.0',
            'PnL_Gross': '550.0', 'Costs': '78.0', 'PnL_Net': '472.0',
            'Max_PnL_Intra': '600.0', 'Min_PnL_Intra': '-30.0',
            'PnL_Cumul': '844.0',
        },
        {
            'Trade_No': '3', 'Direction': 'LONG',
            'Entry_DateTime': '2026-01-02 09:00:00',
            'Exit_DateTime': '2026-01-02 09:30:00',
            'Duration_Min': '30.0',
            'Entry_GC': '2810.0', 'Entry_SI': '32.20',
            'Exit_GC': '2815.0', 'Exit_SI': '32.15',
            'Entry_ZScore': '-3.1', 'Exit_ZScore': '-3.6',
            'Exit_Reason': 'SL_ZSCORE',
            'Beta': '1.03', 'GC_Contracts': '6', 'SI_Contracts': '1',
            'PnL_GC': '-500.0', 'PnL_SI': '-250.0',
            'PnL_Gross': '-750.0', 'Costs': '78.0', 'PnL_Net': '-828.0',
            'Max_PnL_Intra': '100.0', 'Min_PnL_Intra': '-800.0',
            'PnL_Cumul': '16.0',
        },
    ]
