# ============================================================================
# DATA_LOADER_5S.PY - Chargement et Synchronisation des Donnees 5 Secondes
# ============================================================================
#
# Ce module charge les fichiers CSV GC et SI en barres de 5 secondes.
# Il reutilise la meme logique que data_loader.py (load_sierra_chart_data +
# synchronize_data) mais pour les fichiers 5s.
#
# Utilise par :
#   - backtest_engine_hybrid.py (Approche A : suivi PnL intra-trade)
#   - backtest_engine_full5s.py (Approche B : tout recalcule sur 5s)
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import pandas as pd
from pathlib import Path
from typing import Tuple

from data_loader import (load_config, load_sierra_chart_data, synchronize_data,
                         _cache_is_valid, _save_cache, CACHE_DIR)


def load_5s_data(
    config: dict,
    verbose: bool = True,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Charge et synchronise les donnees GC et SI en barres de 5 secondes.

    Meme logique que load_and_prepare_data() de data_loader.py mais
    utilise les fichiers 5s definis dans la config (gc_file_5s / si_file_5s).

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
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module data_loader_5s.

    Pour executer ce test :
        python src/data_loader_5s.py
    """
    print("\n" + "="*60)
    print("TEST DU MODULE DATA_LOADER_5S")
    print("="*60)

    try:
        config = load_config()
        df_5s = load_5s_data(config, verbose=True)

        # Apercu des donnees
        print("\n   Apercu des donnees (5 premieres lignes):")
        print("-" * 60)
        print(df_5s[['DateTime', 'Last_GC', 'Last_SI']].head())

        print("\n   Apercu des donnees (5 dernieres lignes):")
        print("-" * 60)
        print(df_5s[['DateTime', 'Last_GC', 'Last_SI']].tail())

        # Intervalle entre barres
        dt_diff = df_5s['DateTime'].diff().dropna()
        print(f"\n   Intervalle median entre barres : {dt_diff.median()}")
        print(f"   Intervalle min : {dt_diff.min()}")
        print(f"   Intervalle max : {dt_diff.max()}")

        print("\n[OK] Test du module data_loader_5s REUSSI !")

    except FileNotFoundError as e:
        print(f"\n[ERREUR] Fichier non trouve - {e}")
        print("   Verifiez que les fichiers 5s sont dans data/raw/")

    except Exception as e:
        print(f"\n[ERREUR] Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
