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
    log_gc = df['Log_GC'].values
    log_si = df['Log_SI'].values
    n = len(df)

    # Tableaux numpy pour stocker les resultats (performance)
    betas = np.full(n, np.nan)
    alphas = np.full(n, np.nan)

    # Calcul glissant du Beta via OLS
    for i in range(lookback - 1, n):
        # Fenetre de donnees
        start_idx = i - lookback + 1
        x = log_gc[start_idx:i+1]
        y = log_si[start_idx:i+1]

        # Moyennes
        mean_x = np.mean(x)
        mean_y = np.mean(y)

        # Variance et Covariance
        var_x = np.var(x, ddof=0)  # ddof=0 pour variance population
        cov_xy = np.mean((x - mean_x) * (y - mean_y))

        # Beta et Alpha
        if var_x > 0:
            betas[i] = cov_xy / var_x
            alphas[i] = mean_y - betas[i] * mean_x
        else:
            betas[i] = 1.0
            alphas[i] = 0.0

    # Assignation unique au DataFrame (au lieu de 44000 df.iloc)
    df['Beta'] = betas
    df['Alpha'] = alphas

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
    spread = df['Spread'].values
    n = len(df)

    # Tableau numpy pour stocker les resultats
    adf_values = np.full(n, np.nan)

    for i in range(period, n):
        # Fenetre de donnees
        start_idx = i - period + 1
        spread_window = spread[start_idx:i+1]

        # Verifier les valeurs valides
        if np.any(np.isnan(spread_window)) or np.any(spread_window == 0):
            continue

        # Variables pour la regression
        # Y = DeltaSpread (difference)
        # X = Spread_{t-1} (lag)
        delta_spread = np.diff(spread_window)  # DeltaSpread
        lag_spread = spread_window[:-1]         # Spread_{t-1}

        n_pts = len(delta_spread)
        if n_pts < 20:
            continue

        # Regression OLS : DeltaSpread = gamma x Spread_{t-1}
        sum_xy = np.sum(lag_spread * delta_spread)
        sum_x2 = np.sum(lag_spread ** 2)

        if sum_x2 == 0:
            continue

        gamma = sum_xy / sum_x2

        # Calcul de l'erreur standard de gamma
        residuals = delta_spread - gamma * lag_spread
        ssr = np.sum(residuals ** 2)
        variance = ssr / (n_pts - 1)

        if variance < 0:
            continue

        se_gamma = np.sqrt(variance / sum_x2)

        if se_gamma == 0:
            continue

        # ADF statistic
        adf_values[i] = gamma / se_gamma

    # Assignation unique au DataFrame
    df['ADF_Statistic'] = adf_values

    return df


def calculate_hurst_exponent(
    df: pd.DataFrame,
    period: int = 128
) -> pd.DataFrame:
    """
    Calcule l'exposant de Hurst via la methode R/S (Rescaled Range).

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
    spread = df['Spread'].values
    n = len(df)

    # Tableau numpy pour stocker les resultats
    hurst_values = np.full(n, np.nan)

    # Sous-periodes pour l'analyse R/S (puissances de 2)
    sub_periods = [p for p in [8, 16, 32, 64, 128] if p <= period]

    for i in range(period, n):
        # Fenetre de donnees
        start_idx = i - period + 1
        spread_window = spread[start_idx:i+1]

        # Verifier les valeurs valides
        if np.any(np.isnan(spread_window)):
            continue

        log_n_list = []
        log_rs_list = []

        for sp in sub_periods:
            if sp > len(spread_window):
                continue

            # Prendre les sp dernieres valeurs
            data = spread_window[-sp:]

            # Moyenne
            mean = np.mean(data)

            # Deviations cumulatives
            deviations = data - mean
            cum_deviations = np.cumsum(deviations)

            # Range (R)
            R = np.max(cum_deviations) - np.min(cum_deviations)

            # Ecart-type (S)
            S = np.std(data, ddof=0)

            if S > 1e-10 and R > 1e-10:
                rs = R / S
                log_n_list.append(np.log(sp))
                log_rs_list.append(np.log(rs))

        # Regression lineaire pour estimer H
        if len(log_n_list) >= 3:
            log_n = np.array(log_n_list)
            log_rs = np.array(log_rs_list)

            # H = pente de la regression log(R/S) vs log(n)
            n_points = len(log_n)
            sum_x = np.sum(log_n)
            sum_y = np.sum(log_rs)
            sum_xy = np.sum(log_n * log_rs)
            sum_x2 = np.sum(log_n ** 2)

            denom = n_points * sum_x2 - sum_x ** 2

            if abs(denom) > 1e-10:
                H = (n_points * sum_xy - sum_x * sum_y) / denom

                # Clamp H entre 0.01 et 0.99
                H = max(0.01, min(0.99, H))

                hurst_values[i] = H

    # Assignation unique au DataFrame
    df['Hurst'] = hurst_values

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
    adf_critical: float = -2.86
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

    mask_corr = has_corr & (corr_vals > 0.6)
    score_corr[mask_corr] = 40.0 * (corr_vals[mask_corr] - 0.6) / 0.4
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
    df = calculate_cointegration_score(df)

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
