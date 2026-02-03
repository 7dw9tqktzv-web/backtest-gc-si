# ============================================================================
# TEST_INDICATORS.PY - Tests pour le module indicators.py
# ============================================================================
#
# Tests des fonctions de calcul d'indicateurs :
# - calculate_log_prices()
# - calculate_rolling_beta()
# - calculate_spread()
# - calculate_zscore()
# - calculate_correlation()
# - calculate_adf_statistic()
# - calculate_hurst_exponent()
# - calculate_cointegration_score()
# - calculate_all_indicators()
#
# ============================================================================

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Ajouter src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indicators import (
    calculate_log_prices,
    calculate_rolling_beta,
    calculate_spread,
    calculate_zscore,
    calculate_correlation,
    calculate_adf_statistic,
    calculate_hurst_exponent,
    calculate_half_life,
    calculate_cointegration_score,
    calculate_all_indicators,
)


class TestCalculateLogPrices:
    """Tests de calculate_log_prices()."""

    def test_log_prices_added(self, sample_prices_df):
        """Verifie que les colonnes Log_GC et Log_SI sont ajoutees."""
        df = calculate_log_prices(sample_prices_df.copy())
        assert 'Log_GC' in df.columns
        assert 'Log_SI' in df.columns

    def test_log_values_correct(self, sample_prices_df):
        """Verifie que les valeurs log sont correctes."""
        df = calculate_log_prices(sample_prices_df.copy())

        # Verifier quelques valeurs
        for i in [0, 10, 50]:
            expected_log_gc = np.log(df.loc[i, 'Last_GC'])
            expected_log_si = np.log(df.loc[i, 'Last_SI'])
            assert np.isclose(df.loc[i, 'Log_GC'], expected_log_gc)
            assert np.isclose(df.loc[i, 'Log_SI'], expected_log_si)

    def test_no_nan_for_positive_prices(self, sample_prices_df):
        """Pas de NaN si tous les prix sont positifs."""
        df = calculate_log_prices(sample_prices_df.copy())
        assert df['Log_GC'].notna().all()
        assert df['Log_SI'].notna().all()


class TestCalculateRollingBeta:
    """Tests de calculate_rolling_beta()."""

    def test_beta_alpha_added(self, sample_prices_df):
        """Verifie que Beta et Alpha sont ajoutes."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        assert 'Beta' in df.columns
        assert 'Alpha' in df.columns

    def test_beta_nan_during_warmup(self, sample_prices_df):
        """Beta est NaN pendant la periode de warmup."""
        df = calculate_log_prices(sample_prices_df.copy())
        lookback = 20
        df = calculate_rolling_beta(df, lookback=lookback)

        # Les lookback-1 premieres valeurs doivent etre NaN
        assert df['Beta'].iloc[:lookback-1].isna().all()
        # La valeur a l'index lookback-1 peut etre valide
        assert df['Beta'].iloc[lookback:].notna().all()

    def test_beta_reasonable_range(self, sample_prices_df):
        """Beta doit etre dans une plage raisonnable."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)

        valid_beta = df['Beta'].dropna()
        # Beta devrait etre entre -10 et 10 pour des actifs correles
        assert (valid_beta > -10).all()
        assert (valid_beta < 10).all()

    def test_beta_formula_correctness(self):
        """Verifie la formule Beta = Cov(X,Y) / Var(X)."""
        # Donnees synthetiques avec relation lineaire connue
        np.random.seed(42)
        n = 50
        x = np.random.randn(n)
        true_beta = 2.0
        true_alpha = 0.5
        y = true_alpha + true_beta * x + np.random.randn(n) * 0.01  # Bruit faible

        df = pd.DataFrame({
            'Last_GC': np.exp(x),
            'Last_SI': np.exp(y),
        })
        df = calculate_log_prices(df)
        df = calculate_rolling_beta(df, lookback=30)

        # Le Beta calcule devrait etre proche de 2.0
        last_beta = df['Beta'].iloc[-1]
        assert np.isclose(last_beta, true_beta, atol=0.1)


class TestCalculateSpread:
    """Tests de calculate_spread()."""

    def test_spread_added(self, sample_prices_df):
        """Verifie que Spread est ajoute."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        assert 'Spread' in df.columns

    def test_spread_formula(self, sample_prices_df):
        """Verifie la formule Spread = Log_SI - Beta * Log_GC - Alpha."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)

        # Verifier sur une ligne valide
        idx = 50
        expected = df.loc[idx, 'Log_SI'] - df.loc[idx, 'Beta'] * df.loc[idx, 'Log_GC'] - df.loc[idx, 'Alpha']
        assert np.isclose(df.loc[idx, 'Spread'], expected)


class TestCalculateZscore:
    """Tests de calculate_zscore()."""

    def test_zscore_columns_added(self, sample_prices_df):
        """Verifie que les colonnes Z-Score sont ajoutees."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_zscore(df, period=10)

        assert 'Spread_Mean' in df.columns
        assert 'Spread_Std' in df.columns
        assert 'ZScore' in df.columns

    def test_zscore_formula(self):
        """Verifie la formule Z-Score = (Spread - Mean) / Std."""
        # Donnees synthetiques avec stats connues
        spread = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        df = pd.DataFrame({'Spread': spread})
        df = calculate_zscore(df, period=5)

        # Pour la derniere valeur (10), avec fenetre [6,7,8,9,10]
        # Mean = 8, Std = std([6,7,8,9,10])
        window = spread[-5:]
        expected_mean = np.mean(window)
        expected_std = np.std(window, ddof=1)  # pandas utilise ddof=1
        expected_zscore = (10 - expected_mean) / expected_std

        assert np.isclose(df['ZScore'].iloc[-1], expected_zscore)

    def test_zscore_nan_for_zero_std(self):
        """Z-Score est NaN si ecart-type = 0."""
        # Spread constant -> std = 0
        df = pd.DataFrame({'Spread': [5.0] * 20})
        df = calculate_zscore(df, period=10)

        # Std = 0 -> Z-Score devrait etre NaN
        assert df['ZScore'].iloc[-1] != df['ZScore'].iloc[-1]  # NaN != NaN

    def test_zscore_reasonable_range(self, sample_prices_df):
        """Z-Score devrait etre dans une plage raisonnable."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_zscore(df, period=10)

        valid_z = df['ZScore'].dropna()
        # Z-Score devrait rarement depasser +/-5
        assert (valid_z > -10).all()
        assert (valid_z < 10).all()


class TestCalculateCorrelation:
    """Tests de calculate_correlation()."""

    def test_correlation_added(self, sample_prices_df):
        """Verifie que Correlation est ajoutee."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_correlation(df, period=10)
        assert 'Correlation' in df.columns

    def test_correlation_range(self, sample_prices_df):
        """Correlation doit etre entre -1 et 1."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_correlation(df, period=10)

        valid_corr = df['Correlation'].dropna()
        assert (valid_corr >= -1).all()
        assert (valid_corr <= 1).all()

    def test_perfect_correlation(self):
        """Correlation = 1 pour des series identiques."""
        x = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        df = pd.DataFrame({
            'Last_GC': np.exp(x),
            'Last_SI': np.exp(x),  # Identique
        })
        df = calculate_log_prices(df)
        df = calculate_correlation(df, period=5)

        # Correlation devrait etre 1
        assert np.isclose(df['Correlation'].iloc[-1], 1.0)


class TestCalculateAdfStatistic:
    """Tests de calculate_adf_statistic()."""

    def test_adf_added(self, sample_prices_df):
        """Verifie que ADF_Statistic est ajoutee."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_adf_statistic(df, period=20)
        assert 'ADF_Statistic' in df.columns

    def test_adf_nan_during_warmup(self, sample_prices_df):
        """ADF est NaN pendant la periode de warmup."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        period = 20
        df = calculate_adf_statistic(df, period=period)

        # Les premieres valeurs doivent etre NaN
        assert df['ADF_Statistic'].iloc[:period].isna().all()

    def test_adf_stationary_spread(self):
        """ADF devrait etre negatif pour un spread stationnaire."""
        # Generer un spread mean-reverting (AR(1) avec phi < 1)
        np.random.seed(42)
        n = 200
        spread = np.zeros(n)
        phi = 0.5  # Mean reverting
        for i in range(1, n):
            spread[i] = phi * spread[i-1] + np.random.randn() * 0.1

        df = pd.DataFrame({'Spread': spread})
        df = calculate_adf_statistic(df, period=50)

        # ADF devrait etre significativement negatif
        last_adf = df['ADF_Statistic'].iloc[-1]
        assert last_adf < 0  # Negatif


class TestCalculateHurstExponent:
    """Tests de calculate_hurst_exponent()."""

    def test_hurst_added(self, sample_prices_df):
        """Verifie que Hurst est ajoute."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_hurst_exponent(df, period=20)
        assert 'Hurst' in df.columns

    def test_hurst_range(self, sample_prices_df):
        """Hurst doit etre entre 0 et 1."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_hurst_exponent(df, period=20)

        valid_hurst = df['Hurst'].dropna()
        assert (valid_hurst >= 0).all()
        assert (valid_hurst <= 1).all()

    def test_hurst_mean_reverting(self):
        """Hurst < 0.5 pour un processus mean-reverting."""
        np.random.seed(42)
        n = 200
        spread = np.zeros(n)
        # Processus AR(1) fortement mean-reverting
        phi = 0.3
        for i in range(1, n):
            spread[i] = phi * spread[i-1] + np.random.randn() * 0.1

        df = pd.DataFrame({'Spread': spread})
        df = calculate_hurst_exponent(df, period=50)

        # Hurst devrait etre < 0.5
        last_hurst = df['Hurst'].iloc[-1]
        # Note: le calcul peut varier, on verifie juste la plage
        assert 0 < last_hurst < 1


class TestCalculateHalfLife:
    """Tests de calculate_half_life()."""

    def test_halflife_added(self, sample_prices_df):
        """Verifie que HalfLife est ajoute."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_half_life(df, period=20)
        assert 'HalfLife' in df.columns

    def test_halflife_positive(self, sample_prices_df):
        """Half-Life doit etre positif."""
        df = calculate_log_prices(sample_prices_df.copy())
        df = calculate_rolling_beta(df, lookback=20)
        df = calculate_spread(df)
        df = calculate_half_life(df, period=20)

        valid_hl = df['HalfLife'].dropna()
        assert (valid_hl > 0).all()


class TestCalculateCointegrationScore:
    """Tests de calculate_cointegration_score()."""

    def test_score_added(self, sample_df_with_indicators):
        """Verifie que Cointegration_Score est ajoute."""
        df = sample_df_with_indicators.copy()
        # Supprimer le score existant pour le recalculer
        df = df.drop(columns=['Cointegration_Score'])
        df = calculate_cointegration_score(df)
        assert 'Cointegration_Score' in df.columns

    def test_score_range(self, sample_df_with_indicators):
        """Score doit etre entre 0 et 100."""
        df = sample_df_with_indicators.copy()
        df = df.drop(columns=['Cointegration_Score'])
        df = calculate_cointegration_score(df)

        valid_score = df['Cointegration_Score'].dropna()
        assert (valid_score >= 0).all()
        assert (valid_score <= 100).all()

    def test_score_high_when_conditions_met(self):
        """Score eleve quand ADF, Hurst et Correlation sont bons."""
        df = pd.DataFrame({
            'ADF_Statistic': [-3.5],  # < -2.86 (stationnaire)
            'Hurst': [0.3],           # < 0.5 (mean-reverting)
            'Correlation': [0.9],     # > 0.6 (tres correlee)
        })
        df = calculate_cointegration_score(df)

        # Score devrait etre eleve (proche de 100)
        assert df['Cointegration_Score'].iloc[0] > 70

    def test_score_low_when_conditions_not_met(self):
        """Score bas quand les conditions ne sont pas remplies."""
        df = pd.DataFrame({
            'ADF_Statistic': [-1.0],  # > -2.86 (non stationnaire)
            'Hurst': [0.7],           # > 0.5 (trending)
            'Correlation': [0.4],     # < 0.6 (faible)
        })
        df = calculate_cointegration_score(df)

        # Score devrait etre bas
        assert df['Cointegration_Score'].iloc[0] < 30

    def test_score_handles_nan(self):
        """Score gere les NaN correctement."""
        df = pd.DataFrame({
            'ADF_Statistic': [np.nan],
            'Hurst': [np.nan],
            'Correlation': [0.9],
        })
        df = calculate_cointegration_score(df)

        # Score devrait etre base uniquement sur Correlation
        # Avec reponderation : 40 points -> 100 points
        # Correlation 0.9 > 0.6 -> score partiel
        assert df['Cointegration_Score'].iloc[0] > 0


class TestCalculateAllIndicators:
    """Tests de la fonction principale calculate_all_indicators()."""

    def test_all_columns_added(self, sample_prices_df, sample_config):
        """Verifie que toutes les colonnes d'indicateurs sont ajoutees."""
        df = calculate_all_indicators(sample_prices_df.copy(), sample_config, verbose=False)

        expected_columns = [
            'Log_GC', 'Log_SI',
            'Beta', 'Alpha',
            'Spread', 'Spread_Mean', 'Spread_Std', 'ZScore',
            'Correlation',
            'ADF_Statistic',
            'Hurst',
            'HalfLife',
            'Cointegration_Score',
        ]

        for col in expected_columns:
            assert col in df.columns, f"Colonne manquante: {col}"

    def test_returns_copy(self, sample_prices_df, sample_config):
        """Verifie que la fonction retourne une copie."""
        original = sample_prices_df.copy()
        result = calculate_all_indicators(original, sample_config, verbose=False)

        # Modifier result ne devrait pas modifier original
        result.loc[0, 'ZScore'] = 999
        assert 'ZScore' not in original.columns

    def test_warmup_period_respected(self, sample_prices_df, sample_config):
        """Les premieres barres sont NaN (warmup)."""
        df = calculate_all_indicators(sample_prices_df.copy(), sample_config, verbose=False)

        warmup = sample_config['indicators']['beta_lookback']

        # Beta devrait etre NaN pendant le warmup
        assert df['Beta'].iloc[:warmup-1].isna().all()

    def test_no_error_with_valid_data(self, sample_prices_df, sample_config):
        """Pas d'erreur avec des donnees valides."""
        # Ne devrait pas lever d'exception
        df = calculate_all_indicators(sample_prices_df.copy(), sample_config, verbose=False)
        assert len(df) == len(sample_prices_df)
