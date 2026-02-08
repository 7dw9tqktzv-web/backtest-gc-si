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
import hashlib
import json


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
        print(f"   Periode : {stats['start_date']} -> {stats['end_date']}")
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


# ============================================================================
# CACHE PARQUET - Chargement accelere des donnees synchronisees
# ============================================================================

CACHE_DIR = Path("data/processed")


def _file_hash(filepath):
    """Calcule le hash MD5 d'un fichier source pour detecter les changements."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _cache_is_valid(cache_parquet, meta_path, source_files):
    """Verifie si le cache Parquet est valide par rapport aux fichiers sources."""
    if not cache_parquet.exists() or not meta_path.exists():
        return False
    try:
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        for src_file in source_files:
            expected_hash = meta.get('hashes', {}).get(str(src_file))
            if expected_hash != _file_hash(src_file):
                return False
        return True
    except (json.JSONDecodeError, KeyError):
        return False


def _save_cache(df, cache_parquet, meta_path, source_files, verbose=True):
    """Sauvegarde le DataFrame en Parquet avec metadata de validation."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_parquet, index=False, compression='snappy')
    meta = {
        "rows": len(df),
        "columns": list(df.columns),
        "hashes": {str(f): _file_hash(f) for f in source_files}
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    if verbose:
        size_mb = cache_parquet.stat().st_size / (1024 * 1024)
        print(f"   [CACHE] Sauvegarde : {cache_parquet} ({size_mb:.1f} MB)")


def load_and_prepare_data(
    config_path: str = "config/strategy_params.yaml",
    verbose: bool = True,
    use_cache: bool = True
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

    gc_file = Path(config['data']['gc_file'])
    si_file = Path(config['data']['si_file'])
    cache_parquet = CACHE_DIR / "synchronized_1min.parquet"
    cache_meta = CACHE_DIR / "synchronized_1min.meta.json"

    # 2. Tentative de chargement depuis le cache Parquet
    if use_cache and _cache_is_valid(cache_parquet, cache_meta, [gc_file, si_file]):
        if verbose:
            print("\n[CACHE] Chargement des donnees 1min depuis le cache Parquet...")
        df = pd.read_parquet(cache_parquet)
        if verbose:
            print(f"   {len(df):,} barres chargees depuis le cache")
        stats = validate_data(df, verbose=verbose)
        return df, config, stats

    # 3. Pipeline normal : chargement depuis les CSV
    if verbose:
        print("\n[...] Chargement des donnees depuis les CSV...")

    gc_data = load_sierra_chart_data(gc_file)
    si_data = load_sierra_chart_data(si_file)

    if verbose:
        print(f"   GC charge : {len(gc_data):,} barres")
        print(f"   SI charge : {len(si_data):,} barres")

    # 4. Synchroniser les donnees
    if verbose:
        print("\n[...] Synchronisation GC/SI...")

    df = synchronize_data(gc_data, si_data, method="inner")

    if verbose:
        barres_perdues = len(gc_data) + len(si_data) - 2 * len(df)
        print(f"   Barres apres synchronisation : {len(df):,}")
        if barres_perdues > 0:
            print(f"   [!] Barres non appariees : {barres_perdues}")

    # 5. Sauvegarder le cache Parquet
    if use_cache:
        _save_cache(df, cache_parquet, cache_meta, [gc_file, si_file], verbose=verbose)

    # 6. Valider les donnees
    if verbose:
        print("\n[...] Validation des donnees...")

    stats = validate_data(df, verbose=verbose)

    return df, config, stats


def resample_to_5min(
    df_1min: pd.DataFrame,
    verbose: bool = True,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Resample les donnees 1-min en barres 5-min avec cache Parquet.

    Utilise le OHLC classique pour les prix et la somme pour les volumes.
    Le cache est invalide si les donnees 1-min changent (hash MD5).

    Parametres:
    -----------
    df_1min : pd.DataFrame
        Donnees 1-min synchronisees (depuis load_and_prepare_data)
    verbose : bool
        Si True, affiche les statistiques
    use_cache : bool
        Si True, utilise le cache Parquet si disponible

    Retourne:
    ---------
    pd.DataFrame : Donnees 5-min avec colonnes DateTime, Last_GC, Last_SI, etc.
    """
    cache_parquet = CACHE_DIR / "resampled_5min.parquet"
    cache_meta = CACHE_DIR / "resampled_5min.meta.json"

    # Verifier le cache (invalide par le nombre de lignes 1-min comme proxy)
    if use_cache and cache_parquet.exists() and cache_meta.exists():
        try:
            with open(cache_meta, 'r') as f:
                meta = json.load(f)
            if meta.get('n_1min') == len(df_1min):
                if verbose:
                    print("[CACHE] Chargement des donnees 5-min depuis le cache Parquet...")
                df_5min = pd.read_parquet(cache_parquet)
                if verbose:
                    print(f"   {len(df_5min):,} barres 5-min chargees depuis le cache")
                return df_5min
        except (json.JSONDecodeError, KeyError):
            pass

    if verbose:
        print("[...] Resampling 1-min -> 5-min...")

    # Mettre DateTime en index pour le resampling
    df = df_1min.copy()
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    df = df.set_index('DateTime')

    # Resampling OHLC pour les prix, somme pour les volumes
    agg_dict = {}
    for col in df.columns:
        if col.startswith('Last_'):
            agg_dict[col] = 'last'
        elif col.startswith('High_'):
            agg_dict[col] = 'max'
        elif col.startswith('Low_'):
            agg_dict[col] = 'min'
        elif col.startswith('Volume_'):
            agg_dict[col] = 'sum'
        elif col.startswith('Open_'):
            agg_dict[col] = 'first'
        else:
            agg_dict[col] = 'last'

    df_5min = df.resample('5min').agg(agg_dict).dropna()
    df_5min = df_5min.reset_index()

    if verbose:
        print(f"   {len(df_1min):,} barres 1-min -> {len(df_5min):,} barres 5-min")

    # Sauvegarder le cache
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df_5min.to_parquet(cache_parquet)
        meta = {'n_1min': len(df_1min), 'n_5min': len(df_5min)}
        with open(cache_meta, 'w') as f:
            json.dump(meta, f, indent=2)
        if verbose:
            size_mb = cache_parquet.stat().st_size / (1024 * 1024)
            print(f"   [CACHE] Sauvegarde : {cache_parquet} ({size_mb:.1f} MB)")

    return df_5min


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


def load_5s_data(
    config: dict,
    verbose: bool = True,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Charge et synchronise les donnees GC et SI en barres de 5 secondes.

    Meme logique que load_and_prepare_data() mais utilise les fichiers 5s
    definis dans la config (gc_file_5s / si_file_5s).

    Parametres:
    -----------
    config : dict
        Configuration chargee depuis YAML (doit contenir data.gc_file_5s et data.si_file_5s)
    verbose : bool
        Si True, affiche les statistiques de chargement
    use_cache : bool
        Si True, utilise le cache Parquet si disponible

    Retourne:
    ---------
    pd.DataFrame : DataFrame synchronise avec colonnes _GC et _SI
    """
    gc_file = Path(config['data']['gc_file_5s'])
    si_file = Path(config['data']['si_file_5s'])
    cache_parquet = CACHE_DIR / "synchronized_5s.parquet"
    cache_meta = CACHE_DIR / "synchronized_5s.meta.json"

    # Tentative de chargement depuis le cache Parquet
    if use_cache and _cache_is_valid(cache_parquet, cache_meta, [gc_file, si_file]):
        if verbose:
            print("\n[CACHE] Chargement des donnees 5s depuis le cache Parquet...")
        df_5s = pd.read_parquet(cache_parquet)
        if verbose:
            print(f"   {len(df_5s):,} barres chargees depuis le cache")
            print(f"   Periode : {df_5s['DateTime'].min()} -> {df_5s['DateTime'].max()}")
        return df_5s

    # Pipeline normal : chargement depuis les CSV
    if verbose:
        print("\n[...] Chargement des donnees 5 secondes depuis les CSV...")

    gc_data = load_sierra_chart_data(gc_file)
    si_data = load_sierra_chart_data(si_file)

    if verbose:
        print(f"   GC 5s charge : {len(gc_data):,} barres")
        print(f"   SI 5s charge : {len(si_data):,} barres")

    # Synchroniser (inner join sur DateTime)
    if verbose:
        print("[...] Synchronisation GC/SI 5s...")

    df_5s = synchronize_data(gc_data, si_data, method="inner")

    if verbose:
        barres_perdues = len(gc_data) + len(si_data) - 2 * len(df_5s)
        print(f"   Barres apres synchronisation : {len(df_5s):,}")
        if barres_perdues > 0:
            print(f"   [!] Barres non appariees : {barres_perdues}")
        print(f"   Periode : {df_5s['DateTime'].min()} -> {df_5s['DateTime'].max()}")

    # Sauvegarder le cache Parquet
    if use_cache:
        _save_cache(df_5s, cache_parquet, cache_meta, [gc_file, si_file], verbose=verbose)

    return df_5s


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
