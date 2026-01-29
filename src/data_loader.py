# ============================================================================
# DATA_LOADER.PY - Chargement et Synchronisation des Données GC/SI
# ============================================================================
# 
# Ce module est responsable de :
#   1. Charger les fichiers CSV exportés depuis Sierra Chart
#   2. Nettoyer et formater les données
#   3. Synchroniser les timestamps entre GC et SI
#   4. Créer un DataFrame unifié prêt pour les calculs
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import yaml


def load_config(config_path: str = "config/strategy_params.yaml") -> dict:
    """
    Charge le fichier de configuration YAML.
    
    Paramètres:
    -----------
    config_path : str
        Chemin vers le fichier YAML de configuration
        
    Retourne:
    ---------
    dict : Dictionnaire contenant tous les paramètres
    
    Exemple:
    --------
    >>> config = load_config()
    >>> print(config['indicators']['beta_lookback'])
    2640
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def load_sierra_chart_data(filepath: str) -> pd.DataFrame:
    """
    Charge un fichier de données exporté depuis Sierra Chart.
    
    Format attendu (export "Bar Data to Text File"):
        Date, Time, Open, High, Low, Last, Volume, NumberOfTrades, BidVolume, AskVolume
        2025/12/8, 17:30:00, 4222.0, 4222.0, 4221.5, 4221.5, 17, 17, 6, 11
    
    Paramètres:
    -----------
    filepath : str
        Chemin vers le fichier .txt exporté de Sierra Chart
        
    Retourne:
    ---------
    pd.DataFrame : DataFrame avec les colonnes nettoyées et une colonne DateTime
    
    Notes:
    ------
    - Les espaces après les virgules sont gérés automatiquement
    - Une colonne 'DateTime' est créée en combinant Date et Time
    - Les colonnes sont renommées pour être plus explicites
    """
    # Lecture du fichier CSV avec gestion des espaces
    df = pd.read_csv(filepath, skipinitialspace=True)
    
    # Nettoyer les noms de colonnes (enlever les espaces)
    df.columns = df.columns.str.strip()
    
    # Créer la colonne DateTime en combinant Date et Time
    df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    
    # Supprimer les colonnes Date et Time originales (on garde DateTime)
    df = df.drop(columns=['Date', 'Time'])
    
    # Réorganiser les colonnes avec DateTime en premier
    cols = ['DateTime'] + [col for col in df.columns if col != 'DateTime']
    df = df[cols]
    
    # Trier par DateTime (au cas où les données ne seraient pas ordonnées)
    df = df.sort_values('DateTime').reset_index(drop=True)
    
    return df


def synchronize_data(
    gc_data: pd.DataFrame, 
    si_data: pd.DataFrame,
    method: str = "inner"
) -> pd.DataFrame:
    """
    Synchronise les données GC et SI sur les mêmes timestamps.
    
    Paramètres:
    -----------
    gc_data : pd.DataFrame
        Données Gold chargées avec load_sierra_chart_data()
    si_data : pd.DataFrame
        Données Silver chargées avec load_sierra_chart_data()
    method : str
        Méthode de jointure :
        - "inner" : Garde seulement les timestamps présents dans les deux
        - "outer" : Garde tous les timestamps, remplit les manquants avec NaN
        
    Retourne:
    ---------
    pd.DataFrame : DataFrame unifié avec suffixes _GC et _SI
    
    Exemple:
    --------
    >>> gc = load_sierra_chart_data("data/raw/GC.txt")
    >>> si = load_sierra_chart_data("data/raw/SI.txt")
    >>> merged = synchronize_data(gc, si)
    >>> print(merged.columns)
    ['DateTime', 'Open_GC', 'High_GC', 'Low_GC', 'Last_GC', 'Volume_GC', ...,
     'Open_SI', 'High_SI', 'Low_SI', 'Last_SI', 'Volume_SI', ...]
    """
    # Fusion des deux DataFrames sur DateTime
    merged = pd.merge(
        gc_data, 
        si_data, 
        on='DateTime', 
        how=method,
        suffixes=('_GC', '_SI')
    )
    
    # Trier par DateTime
    merged = merged.sort_values('DateTime').reset_index(drop=True)
    
    return merged


def validate_data(df: pd.DataFrame, verbose: bool = True) -> dict:
    """
    Valide la qualité des données et retourne des statistiques.
    
    Paramètres:
    -----------
    df : pd.DataFrame
        DataFrame synchronisé (sortie de synchronize_data)
    verbose : bool
        Si True, affiche les statistiques dans la console
        
    Retourne:
    ---------
    dict : Dictionnaire contenant les statistiques de validation
    
    Statistiques calculées:
    -----------------------
    - Nombre total de barres
    - Période couverte (date début / date fin)
    - Nombre de jours de trading
    - Valeurs manquantes par colonne
    - Prix min/max/moyen pour GC et SI
    """
    stats = {}
    
    # Statistiques générales
    stats['total_bars'] = len(df)
    stats['start_date'] = df['DateTime'].min()
    stats['end_date'] = df['DateTime'].max()
    stats['trading_days'] = df['DateTime'].dt.date.nunique()
    
    # Valeurs manquantes
    stats['missing_values'] = df.isnull().sum().to_dict()
    
    # Statistiques de prix
    if 'Last_GC' in df.columns:
        stats['gc_price_min'] = df['Last_GC'].min()
        stats['gc_price_max'] = df['Last_GC'].max()
        stats['gc_price_mean'] = df['Last_GC'].mean()
        
    if 'Last_SI' in df.columns:
        stats['si_price_min'] = df['Last_SI'].min()
        stats['si_price_max'] = df['Last_SI'].max()
        stats['si_price_mean'] = df['Last_SI'].mean()
    
    # Affichage si verbose
    if verbose:
        print("=" * 60)
        print("VALIDATION DES DONNÉES")
        print("=" * 60)
        print(f"\n   Statistiques Generales:")
        print(f"   Nombre total de barres : {stats['total_bars']:,}")
        print(f"   Période : {stats['start_date']} → {stats['end_date']}")
        print(f"   Jours de trading : {stats['trading_days']}")
        
        print(f"\n   Prix Gold (GC):")
        print(f"   Min: ${stats.get('gc_price_min', 'N/A'):,.2f}")
        print(f"   Max: ${stats.get('gc_price_max', 'N/A'):,.2f}")
        print(f"   Moyenne: ${stats.get('gc_price_mean', 'N/A'):,.2f}")
        
        print(f"\n   Prix Silver (SI):")
        print(f"   Min: ${stats.get('si_price_min', 'N/A'):.3f}")
        print(f"   Max: ${stats.get('si_price_max', 'N/A'):.3f}")
        print(f"   Moyenne: ${stats.get('si_price_mean', 'N/A'):.3f}")
        
        # Vérifier les valeurs manquantes
        missing = {k: v for k, v in stats['missing_values'].items() if v > 0}
        if missing:
            print(f"\n   [!] Valeurs manquantes detectees:")
            for col, count in missing.items():
                print(f"   {col}: {count} ({count/len(df)*100:.2f}%)")
        else:
            print(f"\n   [OK] Aucune valeur manquante")
        
        print("=" * 60)
    
    return stats


def load_and_prepare_data(
    config_path: str = "config/strategy_params.yaml",
    verbose: bool = True
) -> Tuple[pd.DataFrame, dict, dict]:
    """
    Fonction principale : charge, synchronise et valide les données.
    
    C'est LA fonction à utiliser pour préparer les données du backtest.
    
    Paramètres:
    -----------
    config_path : str
        Chemin vers le fichier de configuration YAML
    verbose : bool
        Si True, affiche les statistiques de validation
        
    Retourne:
    ---------
    Tuple contenant :
        - df : pd.DataFrame - Données synchronisées prêtes pour le backtest
        - config : dict - Configuration chargée depuis YAML
        - stats : dict - Statistiques de validation
    
    Exemple:
    --------
    >>> df, config, stats = load_and_prepare_data()
    >>> print(f"Données chargées : {len(df)} barres")
    >>> print(f"Beta lookback configuré : {config['indicators']['beta_lookback']}")
    """
    # 1. Charger la configuration
    config = load_config(config_path)
    
    if verbose:
        print("\n[...] Chargement des donnees...")
    
    # 2. Charger les fichiers GC et SI
    gc_data = load_sierra_chart_data(config['data']['gc_file'])
    si_data = load_sierra_chart_data(config['data']['si_file'])
    
    if verbose:
        print(f"   GC chargé : {len(gc_data):,} barres")
        print(f"   SI chargé : {len(si_data):,} barres")
    
    # 3. Synchroniser les données
    if verbose:
        print("\n[...] Synchronisation GC/SI...")
    
    df = synchronize_data(gc_data, si_data, method="inner")
    
    if verbose:
        barres_perdues = len(gc_data) + len(si_data) - 2 * len(df)
        print(f"   Barres après synchronisation : {len(df):,}")
        if barres_perdues > 0:
            print(f"   [!] Barres non appariees : {barres_perdues}")
    
    # 4. Valider les données
    if verbose:
        print("\n[...] Validation des donnees...")
    
    stats = validate_data(df, verbose=verbose)
    
    return df, config, stats


def get_price_at_datetime(
    df: pd.DataFrame, 
    target_datetime: str,
    tolerance_minutes: int = 1
) -> Optional[dict]:
    """
    Récupère les prix à une date/heure spécifique (utile pour le debug).
    
    Paramètres:
    -----------
    df : pd.DataFrame
        Données synchronisées
    target_datetime : str
        Date et heure cible (format: "2026-01-23 10:30:00")
    tolerance_minutes : int
        Tolérance en minutes si l'heure exacte n'existe pas
        
    Retourne:
    ---------
    dict ou None : Dictionnaire avec les prix GC et SI, ou None si non trouvé
    
    Exemple:
    --------
    >>> prices = get_price_at_datetime(df, "2026-01-23 10:30:00")
    >>> print(f"GC: {prices['gc_price']}, SI: {prices['si_price']}")
    """
    target = pd.to_datetime(target_datetime)
    
    # Chercher la correspondance exacte d'abord
    exact_match = df[df['DateTime'] == target]
    
    if len(exact_match) > 0:
        row = exact_match.iloc[0]
        return {
            'datetime': row['DateTime'],
            'gc_price': row['Last_GC'],
            'si_price': row['Last_SI'],
            'gc_volume': row['Volume_GC'],
            'si_volume': row['Volume_SI']
        }
    
    # Sinon, chercher la barre la plus proche dans la tolérance
    time_diff = abs(df['DateTime'] - target)
    closest_idx = time_diff.idxmin()
    
    if time_diff[closest_idx] <= pd.Timedelta(minutes=tolerance_minutes):
        row = df.loc[closest_idx]
        return {
            'datetime': row['DateTime'],
            'gc_price': row['Last_GC'],
            'si_price': row['Last_SI'],
            'gc_volume': row['Volume_GC'],
            'si_volume': row['Volume_SI'],
            'note': f"Barre la plus proche (écart: {time_diff[closest_idx]})"
        }
    
    return None


# ============================================================================
# POINT D'ENTRÉE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module data_loader.
    
    Pour exécuter ce test :
        python src/data_loader.py
    
    Ce test va :
        1. Charger les fichiers de données
        2. Les synchroniser
        3. Afficher les statistiques
        4. Montrer quelques lignes d'exemple
    """
    print("\n" + "="*60)
    print("TEST DU MODULE DATA_LOADER")
    print("="*60)
    
    try:
        # Charger et préparer les données
        df, config, stats = load_and_prepare_data(verbose=True)
        
        # Afficher les premières lignes
        print("\n   Apercu des donnees (5 premieres lignes):")
        print("-" * 60)
        print(df[['DateTime', 'Last_GC', 'Last_SI', 'Volume_GC', 'Volume_SI']].head())
        
        # Afficher les dernières lignes
        print("\n   Apercu des donnees (5 dernieres lignes):")
        print("-" * 60)
        print(df[['DateTime', 'Last_GC', 'Last_SI', 'Volume_GC', 'Volume_SI']].tail())
        
        # Test de get_price_at_datetime
        print("\n   Test de recuperation de prix a une date specifique:")
        test_date = df['DateTime'].iloc[len(df)//2].strftime("%Y-%m-%d %H:%M:%S")
        prices = get_price_at_datetime(df, test_date)
        if prices:
            print(f"   Date: {prices['datetime']}")
            print(f"   GC: ${prices['gc_price']:,.2f}")
            print(f"   SI: ${prices['si_price']:.3f}")
        
        print("\n[OK] Test du module data_loader REUSSI !")

    except FileNotFoundError as e:
        print(f"\n[ERREUR] Fichier non trouve - {e}")
        print("   Verifiez que les fichiers sont dans data/raw/")

    except Exception as e:
        print(f"\n[ERREUR] Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
