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
    Calcule les logarithmes des prix GC et SI.

    Le spread log-adjusted est plus stable que le spread en prix bruts
    car il normalise les differences d'echelle entre GC (~$4500) et SI (~$80).

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonnes 'Last_GC' et 'Last_SI'

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonnes 'Log_GC' et 'Log_SI' ajoutees
    """
    df['Log_GC'] = np.log(df['Last_GC'])
    df['Log_SI'] = np.log(df['Last_SI'])
    return df


def calculate_rolling_beta(
    df: pd.DataFrame,
    lookback: int = 2640
) -> pd.DataFrame:
    """
    Calcule le Beta (hedge ratio) via regression OLS glissante.

    La regression est : Log_SI = Alpha + Beta x Log_GC + erreur

    Le Beta represente combien de "unites log" de GC correspondent a 1 unite log de SI.
    C'est utilise pour construire un spread stationnaire.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonnes 'Log_GC' et 'Log_SI'
    lookback : int
        Nombre de barres pour la regression (defaut: 2640 = 2 jours)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonnes 'Beta' et 'Alpha' ajoutees

    Notes:
    ------
    Formule OLS :
        Beta = Cov(X, Y) / Var(X)
        Alpha = Mean(Y) - Beta x Mean(X)

    ou X = Log_GC et Y = Log_SI
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
    Calcule le spread log-adjusted.

    Spread = Log_SI - Beta x Log_GC - Alpha

    Ce spread devrait etre stationnaire (mean-reverting) si GC et SI
    sont cointegres.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonnes 'Log_GC', 'Log_SI', 'Beta', 'Alpha'

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'Spread' ajoutee
    """
    df['Spread'] = df['Log_SI'] - df['Beta'] * df['Log_GC'] - df['Alpha']
    return df


def calculate_zscore(
    df: pd.DataFrame,
    period: int = 30
) -> pd.DataFrame:
    """
    Calcule le Z-Score du spread.

    Z-Score = (Spread - Moyenne) / Ecart-type

    Un Z-Score de +3 signifie que le spread est a 3 ecarts-types au-dessus
    de sa moyenne -> signal de vente du spread (SHORT).
    Un Z-Score de -3 signifie 3 ecarts-types en-dessous -> signal d'achat (LONG).

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonne 'Spread'
    period : int
        Periode pour le calcul de la moyenne et ecart-type (defaut: 30)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonnes 'Spread_Mean', 'Spread_Std', 'ZScore'
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
    Calcule la correlation de Pearson glissante entre Log_GC et Log_SI.

    Une correlation elevee (>0.7) indique que GC et SI bougent ensemble,
    ce qui est necessaire pour que la strategie de spread fonctionne.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonnes 'Log_GC' et 'Log_SI'
    period : int
        Periode pour le calcul de la correlation (defaut: 30)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'Correlation' ajoutee
    """
    # Correlation glissante
    df['Correlation'] = df['Log_GC'].rolling(window=period).corr(df['Log_SI'])

    return df


def calculate_adf_statistic(
    df: pd.DataFrame,
    period: int = 128
) -> pd.DataFrame:
    """
    Calcule la statistique ADF (Augmented Dickey-Fuller) simplifiee.

    Le test ADF verifie si le spread est stationnaire (mean-reverting).

    Hypothese nulle (H0) : Le spread a une racine unitaire (non stationnaire)
    Si ADF < -2.86 (valeur critique a 5%), on rejette H0 -> le spread est stationnaire.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonne 'Spread'
    period : int
        Periode pour le test ADF (defaut: 128)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'ADF_Statistic' ajoutee

    Notes:
    ------
    Implementation simplifiee (comme dans l'indicateur Sierra Chart) :
    - Regression : DeltaSpread = gamma x Spread_{t-1} + erreur
    - ADF statistic = gamma / SE(gamma)
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
    Calcule R/S (Rescaled Range) de maniere vectorisee pour toutes les fenetres.

    R/S = Range(cumsum(x - mean(x))) / Std(x)

    Utilise numpy stride_tricks pour creer des vues sur les fenetres glissantes,
    puis calcule R/S pour toutes les fenetres en une seule operation.

    Parametres:
    -----------
    spread_values : np.ndarray
        Tableau 1D des valeurs du spread
    window_size : int
        Taille de la fenetre glissante

    Retourne:
    ---------
    np.ndarray : R/S pour chaque position (NaN si invalide)
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
    Calcule l'exposant de Hurst via la methode R/S (Rescaled Range).

    VERSION OPTIMISEE : utilise des operations vectorisees au lieu de boucles Python.
    Speedup typique : 10-50x par rapport a la version avec boucles.

    L'exposant de Hurst indique le comportement de la serie :
    - H < 0.5 : Mean-reverting (ce qu'on veut !)
    - H = 0.5 : Random walk
    - H > 0.5 : Trending

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonne 'Spread'
    period : int
        Periode maximale pour le calcul (defaut: 128)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'Hurst' ajoutee
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
    Calcule le Half-Life du spread (temps de retour a la moyenne).

    Le Half-Life indique en combien de barres le spread revient a 50%
    de sa deviation initiale.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonne 'Spread'
    period : int
        Periode pour le calcul (defaut: 128)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'HalfLife' ajoutee

    Notes:
    ------
    Formule : HalfLife = -ln(2) / ln(phi)
    ou phi est le coefficient d'autocorrelation AR(1)
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


def calculate_cointegration_score(
    df: pd.DataFrame,
    adf_critical: float = -2.86,
    corr_threshold: float = 0.6
) -> pd.DataFrame:
    """
    Calcule le score de cointegration composite (0-100).

    Le score combine trois metriques avec reponderation adaptative :
    - ADF statistic (30 points base) : mesure la stationnarite
    - Hurst exponent (30 points base) : mesure le mean-reversion
    - Correlation (40 points base) : mesure la relation GC/SI

    Quand ADF et/ou Hurst sont NaN, les poids sont redistribues
    proportionnellement aux composantes disponibles pour eviter
    de penaliser le score quand les indicateurs manquent de donnees.

    Un score >= 50 indique une bonne cointegration.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec colonnes 'ADF_Statistic', 'Hurst', 'Correlation'
    adf_critical : float
        Valeur critique ADF a 5% (defaut: -2.86)
    corr_threshold : float
        Seuil de correlation pour le score (defaut: 0.6)

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec colonne 'Cointegration_Score' ajoutee
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
    Fonction principale : calcule TOUS les indicateurs.

    C'est LA fonction a utiliser pour preparer les donnees pour le backtest.
    Une seule copie du DataFrame est faite ici, les sous-fonctions travaillent
    directement dessus (pas de copies inutiles).

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame synchronise (sortie de data_loader)
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    pd.DataFrame : DataFrame avec tous les indicateurs calcules

    Colonnes ajoutees:
    ------------------
    - Log_GC, Log_SI : Logarithmes des prix
    - Beta, Alpha : Parametres de la regression
    - Spread : Spread log-adjusted
    - Spread_Mean, Spread_Std : Moyenne et ecart-type du spread
    - ZScore : Z-Score normalise
    - Correlation : Correlation Pearson
    - ADF_Statistic : Test de stationnarite
    - Hurst : Exposant de Hurst
    - HalfLife : Temps de retour a la moyenne
    - Cointegration_Score : Score composite 0-100
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

    if verbose:
        print("   [OK] Tous les indicateurs calcules !")

    return df


def get_indicators_at_datetime(
    df: pd.DataFrame,
    target_datetime: str
) -> Optional[dict]:
    """
    Recupere toutes les valeurs d'indicateurs a une date specifique.

    Utile pour comparer avec Sierra Chart.

    Parametres:
    -----------
    df : pd.DataFrame
        DataFrame avec indicateurs calcules
    target_datetime : str
        Date/heure cible (format: "2026-01-23 10:30:00")

    Retourne:
    ---------
    dict ou None : Dictionnaire avec toutes les valeurs
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
