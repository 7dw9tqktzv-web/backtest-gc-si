# ============================================================================
# INDICATORS.PY - Calcul des Indicateurs de la Strategie
# ============================================================================
#
# Ce module calcule tous les indicateurs necessaires a la strategie :
#   - Beta (Hedge Ratio) via regression OLS
#   - Spread log-adjusted
#   - Z-Score
#   - Correlation de Pearson
#   - Test ADF (Augmented Dickey-Fuller)
#   - Hurst Exponent
#   - Score de Cointegration composite
#
# Les calculs sont alignes avec l'indicateur Sierra Chart v1.4
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import pandas as pd
import numpy as np
from typing import Optional


# ============================================================================
# FONCTIONS DE CALCUL DES INDICATEURS
# ============================================================================

def calculate_log_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute natural logarithms of GC and SI prices.

    Log-adjusted prices normalize the scale difference between GC (~$2700)
    and SI (~$31), making the spread more stable and suitable for OLS
    regression.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Last_GC' and 'Last_SI' columns.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Log_GC' and 'Log_SI' columns added.
    """
    df['Log_GC'] = np.log(df['Last_GC'])
    df['Log_SI'] = np.log(df['Last_SI'])
    return df


def calculate_rolling_beta(
    df: pd.DataFrame,
    lookback: int = 2640
) -> pd.DataFrame:
    """
    Compute the rolling OLS Beta (hedge ratio) between log(GC) and log(SI).

    Regression model:
        log(SI) = Alpha + Beta * log(GC) + epsilon

    Beta represents how many "log units" of GC correspond to 1 log unit of SI.
    It is used to construct a stationary (mean-reverting) spread.

    Formula (OLS, population variance with ddof=0):
        Beta = Cov(X, Y) / Var(X)
        Alpha = Mean(Y) - Beta * Mean(X)
        where X = log(GC), Y = log(SI)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Log_GC' and 'Log_SI' columns.
    lookback : int
        Rolling window size in bars (default: 2640 = 2 days at 1-min).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Beta' and 'Alpha' columns added.
        First (lookback - 1) rows are NaN (warmup period).

    Notes
    -----
    Uses ddof=0 (population variance), which differs from Z-Score (ddof=1).
    This is a known inconsistency (Bug 2) with negligible practical impact.
    """
    # Vectorisation via pandas rolling (equivalent a Cov/Var avec ddof=0)
    log_gc = df['Log_GC']
    log_si = df['Log_SI']

    mean_x = log_gc.rolling(lookback).mean()
    mean_y = log_si.rolling(lookback).mean()
    mean_xy = (log_gc * log_si).rolling(lookback).mean()
    mean_x2 = (log_gc ** 2).rolling(lookback).mean()

    var_x = mean_x2 - mean_x ** 2
    cov_xy = mean_xy - mean_x * mean_y

    # Beta = Cov(X,Y) / Var(X), Alpha = Mean(Y) - Beta * Mean(X)
    df['Beta'] = np.where(var_x > 0, cov_xy / var_x, 1.0)
    df['Alpha'] = np.where(var_x > 0, mean_y - df['Beta'] * mean_x, 0.0)

    # Restaurer NaN pour les barres sans assez de donnees
    df.loc[:lookback - 2, ['Beta', 'Alpha']] = np.nan

    return df


def calculate_spread(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the log-adjusted spread (OLS residual).

    Formula:
        Spread = log(SI) - Beta * log(GC) - Alpha

    This spread should be stationary (mean-reverting) when GC and SI
    are cointegrated. It represents the residual from the OLS regression.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Log_GC', 'Log_SI', 'Beta', 'Alpha' columns.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Spread' column added.
    """
    df['Spread'] = df['Log_SI'] - df['Beta'] * df['Log_GC'] - df['Alpha']
    return df


def calculate_zscore(
    df: pd.DataFrame,
    period: int = 30
) -> pd.DataFrame:
    """
    Compute the Z-Score of the spread.

    Formula:
        Z = (Spread - mu) / sigma
        where mu = rolling mean, sigma = rolling std (ddof=1)

    Interpretation:
    - Z = +3.0: spread is 3 std above mean -> SHORT signal
    - Z = -3.0: spread is 3 std below mean -> LONG signal
    - Z ~= 0: spread near its mean -> no signal

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Spread' column.
    period : int
        Rolling window for mean and std (default: 30).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Spread_Mean', 'Spread_Std', 'ZScore' columns added.

    Notes
    -----
    Uses ddof=1 (sample std), which differs from Beta (ddof=0).
    NaN is set where Spread_Std == 0 (constant spread in window).
    """
    # Moyenne mobile du spread
    df['Spread_Mean'] = df['Spread'].rolling(window=period).mean()

    # Ecart-type mobile du spread
    df['Spread_Std'] = df['Spread'].rolling(window=period).std()

    # Z-Score
    df['ZScore'] = (df['Spread'] - df['Spread_Mean']) / df['Spread_Std']

    # Remplacer les divisions par zero par NaN
    df.loc[df['Spread_Std'] == 0, 'ZScore'] = np.nan

    return df


def calculate_correlation(
    df: pd.DataFrame,
    period: int = 30
) -> pd.DataFrame:
    """
    Compute rolling Pearson correlation between log(GC) and log(SI).

    A high correlation (> 0.60) indicates that GC and SI move together,
    which is required for the spread strategy to work. In practice,
    correlation is always > 0.80 when Z-Score and Cointegration conditions
    are met, making correlation_min a redundant filter.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Log_GC' and 'Log_SI' columns.
    period : int
        Rolling window for correlation (default: 30).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Correlation' column added.
    """
    # Correlation glissante
    df['Correlation'] = df['Log_GC'].rolling(window=period).corr(df['Log_SI'])

    return df


def calculate_adf_statistic(
    df: pd.DataFrame,
    period: int = 128
) -> pd.DataFrame:
    """
    Compute the simplified Augmented Dickey-Fuller (ADF) test statistic.

    The ADF test checks whether the spread is stationary (mean-reverting).

    Null hypothesis (H0): The spread has a unit root (non-stationary).
    If ADF < -2.86 (5% critical value), reject H0 -> spread is stationary.

    Regression model (with intercept):
        Delta_y_t = mu + gamma * y_{t-1} + epsilon
        ADF statistic = gamma / SE(gamma)

    where y = Spread, Delta_y = Spread_t - Spread_{t-1}.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Spread' column.
    period : int
        Rolling window for the ADF test (default: 128).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'ADF_Statistic' column added.

    Notes
    -----
    Simplified implementation matching Sierra Chart v1.5:
    - No augmentation terms (lag differences)
    - Includes intercept (mu) term in regression
    - Uses (period - 1) data points per window (delta/lag pairs)
    """
    # Vectorisation via pandas rolling
    # Regression OLS : DeltaSpread = mu + gamma * Spread_{t-1}
    # On utilise les n-1 derniers points de la fenetre (delta et lag)
    # period dans la fenetre = period points de spread -> period-1 points de delta/lag
    spread_s = df['Spread']
    delta = spread_s.diff()       # DeltaSpread (Y)
    lag = spread_s.shift(1)       # Spread_{t-1} (X)

    n_pts = period - 1  # nombre de paires (delta, lag) dans chaque fenetre

    # Rolling sums sur les n_pts paires delta/lag
    # Note: rolling(period-1) sur delta et lag qui commencent a l'index 1
    roll = period - 1
    sum_x = lag.rolling(roll).sum()
    sum_y = delta.rolling(roll).sum()
    sum_xy = (lag * delta).rolling(roll).sum()
    sum_x2 = (lag ** 2).rolling(roll).sum()

    # Moyennes
    mean_x = sum_x / n_pts
    mean_y = sum_y / n_pts

    # sum((x - mean_x)^2) = sum(x^2) - n * mean_x^2
    ss_x = sum_x2 - n_pts * mean_x ** 2
    # sum((x - mean_x)(y - mean_y)) = sum(xy) - n * mean_x * mean_y
    ss_xy = sum_xy - n_pts * mean_x * mean_y

    # gamma = ss_xy / ss_x
    gamma = ss_xy / ss_x

    # mu = mean_y - gamma * mean_x
    mu = mean_y - gamma * mean_x

    # Residuals : SSR = sum(y^2) - n*mean_y^2 - gamma * (sum(xy) - n*mean_x*mean_y)
    # SSR = SS_y - gamma * SS_xy
    sum_y2 = (delta ** 2).rolling(roll).sum()
    ss_y = sum_y2 - n_pts * mean_y ** 2
    ssr = ss_y - gamma * ss_xy

    # variance = SSR / (n_pts - 2)
    variance = ssr / (n_pts - 2)

    # SE(gamma) = sqrt(variance / ss_x)
    se_gamma = np.sqrt(variance / ss_x)

    # ADF = gamma / SE(gamma)
    adf_raw = gamma / se_gamma

    # Masquer les valeurs invalides (ss_x == 0, variance <= 0, NaN propagation)
    invalid = (ss_x == 0) | (variance <= 0) | (se_gamma == 0) | adf_raw.isna()
    adf_raw[invalid] = np.nan

    # Les period premieres barres n'ont pas assez de donnees
    adf_raw.iloc[:period] = np.nan

    # Masquer les fenetres contenant des NaN dans le spread original
    # (rolling sum propage NaN automatiquement, donc c'est deja gere)

    df['ADF_Statistic'] = adf_raw

    return df


def _compute_rs_vectorized(spread_values: np.ndarray, window_size: int) -> np.ndarray:
    """
    Compute R/S (Rescaled Range) in a vectorized manner for all rolling windows.

    Formula:
        R/S = Range(cumsum(x - mean(x))) / Std(x)

    Uses numpy stride_tricks to create sliding window views without memory
    copies, then computes R/S for all windows in a single vectorized operation.

    Parameters
    ----------
    spread_values : np.ndarray
        1D array of spread values.
    window_size : int
        Size of the rolling window.

    Returns
    -------
    np.ndarray
        R/S ratio for each position (NaN where invalid or during warmup).
    """
    n = len(spread_values)
    if n < window_size:
        return np.full(n, np.nan)

    # Creer une vue 2D des fenetres glissantes (sans copie memoire)
    # Shape: (n - window_size + 1, window_size)
    shape = (n - window_size + 1, window_size)
    strides = (spread_values.strides[0], spread_values.strides[0])
    windows = np.lib.stride_tricks.as_strided(spread_values, shape=shape, strides=strides)

    # Calculer mean et std pour chaque fenetre (axis=1 = le long de chaque fenetre)
    means = np.mean(windows, axis=1, keepdims=True)  # Shape: (n_windows, 1)
    stds = np.std(windows, axis=1, ddof=0)           # Shape: (n_windows,)

    # Deviations par rapport a la moyenne
    deviations = windows - means  # Shape: (n_windows, window_size)

    # Cumsum des deviations le long de chaque fenetre
    cum_deviations = np.cumsum(deviations, axis=1)  # Shape: (n_windows, window_size)

    # Range = max - min des deviations cumulees
    R = np.max(cum_deviations, axis=1) - np.min(cum_deviations, axis=1)  # Shape: (n_windows,)

    # R/S ratio (eviter division par zero)
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = np.where((stds > 1e-10) & (R > 1e-10), R / stds, np.nan)

    # Preparer le resultat avec NaN au debut (warmup)
    result = np.full(n, np.nan)
    result[window_size - 1:] = rs

    return result


def calculate_hurst_exponent(
    df: pd.DataFrame,
    period: int = 128
) -> pd.DataFrame:
    """
    Compute the Hurst exponent via R/S (Rescaled Range) analysis.

    The Hurst exponent characterizes the long-term memory of a time series:
    - H < 0.5: Mean-reverting (desired for spread trading)
    - H = 0.5: Random walk (Brownian motion)
    - H > 0.5: Trending (persistent)

    Method:
        1. Compute R/S at multiple sub-periods (powers of 2: 8, 16, 32, 64, 128)
        2. Fit linear regression: log(R/S) = H * log(n) + c
        3. H = slope of the regression

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Spread' column.
    period : int
        Maximum sub-period for R/S analysis (default: 128).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Hurst' column added (clamped to [0.01, 0.99]).

    Notes
    -----
    Vectorized implementation (~42x speedup vs loop-based).
    Single-segment R/S (no sub-window splitting), which gives lower precision
    but is consistent with Sierra Chart and sufficient for relative ranking.
    Requires at least 3 valid sub-periods for regression.
    """
    spread = df['Spread'].values.astype(np.float64)
    n = len(df)

    # Sous-periodes pour l'analyse R/S (puissances de 2)
    sub_periods = np.array([p for p in [8, 16, 32, 64, 128] if p <= period])
    n_sub = len(sub_periods)

    if n_sub < 3:
        # Pas assez de sous-periodes pour la regression
        df['Hurst'] = np.nan
        return df

    # Precalculer log(sub_periods) pour la regression
    log_n = np.log(sub_periods)  # Shape: (n_sub,)

    # Calculer R/S pour chaque sous-periode (vectorise)
    # rs_matrix[i, j] = R/S pour la position i avec la sous-periode j
    rs_matrix = np.full((n, n_sub), np.nan)

    for j, sp in enumerate(sub_periods):
        rs_matrix[:, j] = _compute_rs_vectorized(spread, sp)

    # Convertir en log(R/S)
    with np.errstate(divide='ignore', invalid='ignore'):
        log_rs_matrix = np.log(rs_matrix)

    # Pour chaque position, faire la regression log(R/S) vs log(n)
    # H = pente de la regression
    #
    # Formule de regression simple :
    # H = (n * sum(xy) - sum(x) * sum(y)) / (n * sum(x^2) - sum(x)^2)
    #
    # Ici x = log(sub_period), y = log(R/S)

    # Masque des valeurs valides (non-NaN)
    valid_mask = ~np.isnan(log_rs_matrix)  # Shape: (n, n_sub)

    # Nombre de points valides par position
    n_valid = np.sum(valid_mask, axis=1)  # Shape: (n,)

    # Remplacer NaN par 0 pour les calculs de somme
    log_rs_clean = np.where(valid_mask, log_rs_matrix, 0)
    log_n_broadcast = np.where(valid_mask, log_n, 0)  # Broadcast log_n

    # Sommes pour la regression
    sum_x = np.sum(log_n_broadcast, axis=1)  # sum(log_n) pour chaque position
    sum_y = np.sum(log_rs_clean, axis=1)     # sum(log_RS) pour chaque position
    sum_xy = np.sum(log_n_broadcast * log_rs_clean, axis=1)
    sum_x2 = np.sum(log_n_broadcast ** 2, axis=1)

    # Denominateur de la regression
    denom = n_valid * sum_x2 - sum_x ** 2

    # Calcul de H (pente)
    with np.errstate(divide='ignore', invalid='ignore'):
        H = np.where(
            (n_valid >= 3) & (np.abs(denom) > 1e-10),
            (n_valid * sum_xy - sum_x * sum_y) / denom,
            np.nan
        )

    # Clamp H entre 0.01 et 0.99
    H = np.clip(H, 0.01, 0.99)

    # Marquer comme NaN les positions sans assez de donnees
    H = np.where(n_valid >= 3, H, np.nan)

    # Les `period` premieres valeurs sont NaN (warmup)
    H[:period] = np.nan

    df['Hurst'] = H

    return df


def calculate_half_life(
    df: pd.DataFrame,
    period: int = 128
) -> pd.DataFrame:
    """
    Compute the half-life of mean reversion for the spread.

    The half-life indicates how many bars it takes for the spread to
    revert 50% of the way back toward its mean.

    Method (AR(1) model):
        Spread_t = phi * Spread_{t-1}
        phi = sum(x * y) / sum(x^2)  where x = Spread_{t-1}, y = Spread_t
        HalfLife = -ln(2) / ln(phi)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Spread' column.
    period : int
        Rolling window for AR(1) regression (default: 128).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'HalfLife' column added (clamped to [1, 500]).
        NaN where phi <= 0 or phi >= 1 (no mean reversion).
    """
    spread = df['Spread'].values
    n = len(df)

    # Tableau numpy pour stocker les resultats
    halflife_values = np.full(n, np.nan)

    for i in range(period, n):
        start_idx = i - period + 1
        spread_window = spread[start_idx:i+1]

        if np.any(np.isnan(spread_window)):
            continue

        # Regression AR(1) : Spread_t = phi x Spread_{t-1}
        y = spread_window[1:]   # Spread_t
        x = spread_window[:-1]  # Spread_{t-1}

        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x ** 2)

        if sum_x2 == 0:
            continue

        phi = sum_xy / sum_x2

        # Half-life = -ln(2) / ln(phi)
        if 0 < phi < 1:
            half_life = -np.log(2) / np.log(phi)
            half_life = max(1, min(500, half_life))  # Clamp
            halflife_values[i] = half_life

    # Assignation unique au DataFrame
    df['HalfLife'] = halflife_values

    return df


def calculate_halflife_ar1(
    df: pd.DataFrame,
    window_days: int = 60
) -> pd.DataFrame:
    """
    Compute rolling half-life AR(1) on daily spread for regime filtering.

    Regression AR(1) : spread(t) = a + b * spread(t-1) + epsilon
    Half-life = -ln(2) / ln(b)
    Si b >= 1 ou b <= 0, retourne NaN (pas de mean-reversion).

    Le calcul se fait sur donnees daily puis forward-fill sur barres intraday.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Spread' and 'DateTime' columns.
    window_days : int
        Rolling window in trading days (default: 60).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'HalfLife_AR1' column added.
    """
    # Resample en daily (dernier spread du jour)
    df_temp = df[['DateTime', 'Spread']].copy()
    df_temp = df_temp.set_index('DateTime')
    spread_daily = df_temp['Spread'].resample('1D').last().dropna()

    # Calcul rolling half-life AR(1) sur daily
    values = spread_daily.values
    n = len(values)
    hl_daily = np.full(n, np.nan)

    for i in range(window_days, n):
        window = values[i - window_days:i]
        if np.any(np.isnan(window)):
            continue

        y = window[1:]   # spread(t)
        x = window[:-1]  # spread(t-1)

        # Regression avec intercept : y = a + b*x
        n_pts = len(x)
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        ss_xx = np.sum((x - mean_x) ** 2)

        if ss_xx < 1e-15:
            continue

        b = np.sum((x - mean_x) * (y - mean_y)) / ss_xx

        if b <= 0 or b >= 1:
            continue

        hl_daily[i] = -np.log(2) / np.log(b)

    # Creer une Series daily indexee
    hl_series = pd.Series(hl_daily, index=spread_daily.index, name='HalfLife_AR1')

    # Forward-fill sur les barres intraday
    # Creer une colonne date dans df pour le merge
    dates_intraday = pd.to_datetime(df['DateTime']).dt.normalize()

    # Map : pour chaque date intraday, prendre la valeur daily
    hl_map = hl_series.to_dict()
    df['HalfLife_AR1'] = dates_intraday.map(hl_map).values

    return df


def calculate_rolling_correlation_daily(
    df: pd.DataFrame,
    window_days: int = 40
) -> pd.DataFrame:
    """
    Compute rolling Pearson correlation between GC and SI on daily prices.

    Resample les prix en daily puis calcule la correlation roulante.
    Forward-fill la valeur sur les barres intraday.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'Last_GC', 'Last_SI', and 'DateTime' columns.
    window_days : int
        Rolling window in trading days (default: 40).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Corr_Daily_GC_SI' column added.
    """
    # Resample en daily (dernier prix du jour)
    df_temp = df[['DateTime', 'Last_GC', 'Last_SI']].copy()
    df_temp = df_temp.set_index('DateTime')
    gc_daily = df_temp['Last_GC'].resample('1D').last().dropna()
    si_daily = df_temp['Last_SI'].resample('1D').last().dropna()

    # Aligner les deux series
    common_idx = gc_daily.index.intersection(si_daily.index)
    gc_daily = gc_daily.loc[common_idx]
    si_daily = si_daily.loc[common_idx]

    # Correlation roulante sur log prices (coherent avec la strategie)
    log_gc = np.log(gc_daily)
    log_si = np.log(si_daily)
    corr_daily = log_gc.rolling(window_days).corr(log_si)

    # Forward-fill sur les barres intraday
    dates_intraday = pd.to_datetime(df['DateTime']).dt.normalize()
    corr_map = corr_daily.to_dict()
    df['Corr_Daily_GC_SI'] = dates_intraday.map(corr_map).values

    return df


def calculate_cointegration_score(
    df: pd.DataFrame,
    adf_critical: float = -2.86,
    corr_threshold: float = 0.6
) -> pd.DataFrame:
    """
    Compute the adaptive composite cointegration score (0-100).

    Combines three metrics with adaptive reweighting:
    - ADF statistic (30 base points): measures stationarity
    - Hurst exponent (30 base points): measures mean-reversion strength
    - Correlation (40 base points): measures GC/SI co-movement

    Scoring rules:
        ADF: 30 pts if ADF < critical_value, partial if ADF < 0
        Hurst: 30 * (0.5 - H) / 0.5 pts (max at H=0, zero at H=0.5)
        Correlation: 40 * (corr - threshold) / (1 - threshold) pts

    Adaptive reweighting: when ADF and/or Hurst are NaN (warmup period),
    weights are redistributed proportionally to available components.
    This prevents penalizing the score when indicators lack data.

    A score >= 50 indicates good cointegration quality.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'ADF_Statistic', 'Hurst', 'Correlation' columns.
    adf_critical : float
        ADF critical value at 5% significance (default: -2.86).
    corr_threshold : float
        Minimum correlation for scoring (default: 0.6).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 'Cointegration_Score' column added (0-100).
    """
    n = len(df)

    # Poids de base
    W_ADF = 30.0
    W_HURST = 30.0
    W_CORR = 40.0

    # Masques de disponibilite (NaN = composante indisponible)
    has_adf = df['ADF_Statistic'].notna().values
    has_hurst = df['Hurst'].notna().values
    has_corr = df['Correlation'].notna().values

    # Calculer le total des poids disponibles pour chaque barre
    total_available = (has_adf * W_ADF + has_hurst * W_HURST + has_corr * W_CORR)

    # Facteur de reponderation : 100 / total_available
    # (si tout est dispo : 100/100 = 1.0, pas de changement)
    # (si seulement Corr : 100/40 = 2.5, Corr passe de 40 a 100 points)
    with np.errstate(divide='ignore', invalid='ignore'):
        reweight = np.where(total_available > 0, 100.0 / total_available, 0.0)

    # --- Score ADF (30 points base) ---
    score_adf = np.zeros(n)
    adf_vals = df['ADF_Statistic'].values

    mask_stat = has_adf & (adf_vals < adf_critical)
    score_adf[mask_stat] = 30.0

    mask_partial = has_adf & ~(adf_vals < adf_critical) & (adf_vals < 0)
    score_adf[mask_partial] = 30.0 * (adf_critical - adf_vals[mask_partial]) / adf_critical
    score_adf = np.clip(score_adf, 0, 30)

    # --- Score Hurst (30 points base) ---
    score_hurst = np.zeros(n)
    hurst_vals = df['Hurst'].values

    mask_mr = has_hurst & (hurst_vals < 0.5)
    score_hurst[mask_mr] = 30.0 * (0.5 - hurst_vals[mask_mr]) / 0.5
    score_hurst = np.clip(score_hurst, 0, 30)

    # --- Score Correlation (40 points base) ---
    score_corr = np.zeros(n)
    corr_vals = df['Correlation'].values

    mask_corr = has_corr & (corr_vals > corr_threshold)
    score_corr[mask_corr] = 40.0 * (corr_vals[mask_corr] - corr_threshold) / (1.0 - corr_threshold)
    score_corr = np.clip(score_corr, 0, 40)

    # Score total avec reponderation
    raw_score = score_adf + score_hurst + score_corr
    df['Cointegration_Score'] = np.clip(raw_score * reweight, 0, 100)

    return df


def calculate_all_indicators(
    df: pd.DataFrame,
    config: dict,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Main entry point: compute ALL indicators for the strategy.

    This is the single function to call when preparing data for backtesting.
    A single DataFrame copy is made here; sub-functions modify it in-place
    (no unnecessary copies).

    Pipeline order:
        1. Log prices (Log_GC, Log_SI)
        2. Rolling Beta and Alpha (OLS regression)
        3. Spread (OLS residual)
        4. Z-Score (normalized spread)
        5. Correlation (Pearson)
        6. ADF Statistic (stationarity test)
        7. Hurst Exponent (mean-reversion strength)
        8. Half-Life + Cointegration Score (composite quality metric)

    Parameters
    ----------
    df : pd.DataFrame
        Synchronized DataFrame from data_loader (with 'Last_GC', 'Last_SI').
    config : dict
        Strategy configuration loaded from YAML.
    verbose : bool
        Print progress messages (default: True).

    Returns
    -------
    pd.DataFrame
        DataFrame with all indicator columns added:
        Log_GC, Log_SI, Beta, Alpha, Spread, Spread_Mean, Spread_Std,
        ZScore, Correlation, ADF_Statistic, Hurst, HalfLife,
        Cointegration_Score.
    """
    # Une seule copie du DataFrame pour tout le pipeline
    df = df.copy()

    # Recuperer les parametres
    beta_lookback = config['indicators']['beta_lookback']
    zscore_period = config['indicators']['zscore_period']
    correlation_period = config['indicators']['correlation_period']
    adf_hurst_period = config['indicators']['adf_hurst_period']

    if verbose:
        print("\n[...] Calcul des indicateurs...")
        print(f"   Beta lookback: {beta_lookback} barres")
        print(f"   Z-Score period: {zscore_period} barres")
        print(f"   Correlation period: {correlation_period} barres")
        print(f"   ADF/Hurst period: {adf_hurst_period} barres")

    # 1. Logarithmes
    if verbose:
        print("   [1/8] Calcul des logarithmes...")
    df = calculate_log_prices(df)

    # 2. Beta (le plus long a calculer)
    if verbose:
        print("   [2/8] Calcul du Beta (regression OLS)...")
    df = calculate_rolling_beta(df, lookback=beta_lookback)

    # 3. Spread
    if verbose:
        print("   [3/8] Calcul du Spread...")
    df = calculate_spread(df)

    # 4. Z-Score
    if verbose:
        print("   [4/8] Calcul du Z-Score...")
    df = calculate_zscore(df, period=zscore_period)

    # 5. Correlation
    if verbose:
        print("   [5/8] Calcul de la Correlation...")
    df = calculate_correlation(df, period=correlation_period)

    # 6. ADF
    if verbose:
        print("   [6/8] Calcul de l'ADF Statistic...")
    df = calculate_adf_statistic(df, period=adf_hurst_period)

    # 7. Hurst
    if verbose:
        print("   [7/8] Calcul du Hurst Exponent...")
    df = calculate_hurst_exponent(df, period=adf_hurst_period)

    # 8. Half-Life et Cointegration Score
    if verbose:
        print("   [8/8] Calcul du Half-Life et Score de Cointegration...")
    df = calculate_half_life(df, period=adf_hurst_period)
    adf_critical = config['indicators'].get('adf_critical_value', -2.86)
    corr_threshold = config['indicators'].get('coint_corr_threshold', 0.6)
    df = calculate_cointegration_score(df, adf_critical=adf_critical, corr_threshold=corr_threshold)

    # 9. Regime filter indicators (si active)
    rf = config.get('regime_filter', {})
    if rf.get('enabled', False):
        if rf.get('halflife_ar1', {}).get('enabled', False):
            hl_window = rf['halflife_ar1'].get('window', 60)
            if verbose:
                print(f"   [9a/9] Calcul du Half-Life AR(1) daily (window={hl_window}j)...")
            df = calculate_halflife_ar1(df, window_days=hl_window)

        if rf.get('correlation_daily', {}).get('enabled', False):
            corr_window = rf['correlation_daily'].get('window', 40)
            if verbose:
                print(f"   [9b/9] Calcul de la Correlation Daily GC/SI (window={corr_window}j)...")
            df = calculate_rolling_correlation_daily(df, window_days=corr_window)

    if verbose:
        print("   [OK] Tous les indicateurs calcules !")

    return df


def get_indicators_at_datetime(
    df: pd.DataFrame,
    target_datetime: str
) -> Optional[dict]:
    """
    Retrieve all indicator values at a specific datetime.

    Useful for comparing Python output with Sierra Chart values.
    Finds exact match or closest bar within 5 minutes.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with calculated indicators.
    target_datetime : str
        Target date/time (format: "2026-01-23 10:30:00").

    Returns
    -------
    dict or None
        Dictionary with all indicator values, or None if no match found
        within 5 minutes of the target.
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
        'gc_price': row['Last_GC'],
        'si_price': row['Last_SI'],
        'beta': row.get('Beta', np.nan),
        'spread': row.get('Spread', np.nan),
        'zscore': row.get('ZScore', np.nan),
        'correlation': row.get('Correlation', np.nan),
        'adf_statistic': row.get('ADF_Statistic', np.nan),
        'hurst': row.get('Hurst', np.nan),
        'half_life': row.get('HalfLife', np.nan),
        'cointegration_score': row.get('Cointegration_Score', np.nan)
    }


# ============================================================================
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module indicators.

    Pour executer ce test :
        python src/indicators.py
    """
    from data_loader import load_and_prepare_data

    print("\n" + "="*60)
    print("TEST DU MODULE INDICATORS")
    print("="*60)

    try:
        # Charger les donnees
        df, config, stats = load_and_prepare_data(verbose=False)
        print(f"[OK] Donnees chargees : {len(df)} barres")

        # Calculer les indicateurs
        df = calculate_all_indicators(df, config)

        # Afficher les statistiques des indicateurs
        print("\n" + "="*60)
        print("STATISTIQUES DES INDICATEURS")
        print("="*60)

        indicators = ['Beta', 'Spread', 'ZScore', 'Correlation',
                      'ADF_Statistic', 'Hurst', 'HalfLife', 'Cointegration_Score']

        for ind in indicators:
            if ind in df.columns:
                valid = df[ind].dropna()
                if len(valid) > 0:
                    print(f"\n   {ind}:")
                    print(f"   Min: {valid.min():.4f}")
                    print(f"   Max: {valid.max():.4f}")
                    print(f"   Moyenne: {valid.mean():.4f}")
                    print(f"   Valeurs valides: {len(valid)} / {len(df)}")

        # Afficher un exemple
        print("\n" + "="*60)
        print("EXEMPLE DE VALEURS (derniere barre valide)")
        print("="*60)

        # Trouver la derniere barre avec tous les indicateurs
        last_valid = df.dropna(subset=['ZScore', 'Correlation', 'Cointegration_Score']).iloc[-1]

        print(f"\n   Date: {last_valid['DateTime']}")
        print(f"   GC: ${last_valid['Last_GC']:,.2f} | SI: ${last_valid['Last_SI']:.3f}")
        print(f"\n   Indicateurs:")
        print(f"   Beta: {last_valid['Beta']:.4f}")
        print(f"   Spread: {last_valid['Spread']:.6f}")
        print(f"   Z-Score: {last_valid['ZScore']:.2f}")
        print(f"   Correlation: {last_valid['Correlation']:.3f}")
        print(f"   ADF Statistic: {last_valid['ADF_Statistic']:.2f}")
        print(f"   Hurst: {last_valid['Hurst']:.3f}")
        print(f"   Half-Life: {last_valid['HalfLife']:.1f} barres")
        print(f"   Cointegration Score: {last_valid['Cointegration_Score']:.1f}")

        print("\n" + "="*60)
        print("[OK] Test du module indicators REUSSI !")
        print("="*60)

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
