# ============================================================================
# VALIDATE_DATA.PY - Script de Validation des Donnees
# ============================================================================
#
# Ce script te permet de comparer les donnees Python avec Sierra Chart.
#
# Utilisation:
#     python validate_data.py
#     python validate_data.py --date "2026-01-23 10:30:00"
#
# ============================================================================

import argparse
from src.data_loader import load_and_prepare_data, get_price_at_datetime


def main():
    # Parser les arguments de ligne de commande
    parser = argparse.ArgumentParser(
        description="Valide les donnees Python contre Sierra Chart"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date/heure a verifier (format: '2026-01-23 10:30:00')"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mode silencieux (moins de details)"
    )

    args = parser.parse_args()

    # Charger les donnees
    print("\n" + "="*70)
    print("VALIDATION DES DONNEES - COMPARAISON AVEC SIERRA CHART")
    print("="*70)

    df, config, stats = load_and_prepare_data(verbose=not args.quiet)

    # Si une date est specifiee, afficher les prix a cette date
    if args.date:
        print(f"\n   Recherche des prix pour : {args.date}")
        print("-" * 50)

        prices = get_price_at_datetime(df, args.date)

        if prices:
            print(f"\n   Date trouvee : {prices['datetime']}")
            print(f"")
            print(f"   GOLD (GC):")
            print(f"      Prix (Last) : ${prices['gc_price']:,.2f}")
            print(f"      Volume      : {prices['gc_volume']:,}")
            print(f"")
            print(f"   SILVER (SI):")
            print(f"      Prix (Last) : ${prices['si_price']:.3f}")
            print(f"      Volume      : {prices['si_volume']:,}")
            print(f"")
            print(f"   RATIO GC/SI : {prices['gc_price'] / prices['si_price']:.2f}")

            if 'note' in prices:
                print(f"\n   [!] Note: {prices['note']}")
        else:
            print(f"\n   [ERREUR] Aucune donnee trouvee pour cette date.")
            print(f"      Verifiez que la date est dans la plage disponible:")
            print(f"      {stats['start_date']} -> {stats['end_date']}")

    # Afficher des dates de reference pour faciliter la comparaison
    print("\n" + "="*70)
    print("DATES DE REFERENCE POUR VALIDATION MANUELLE")
    print("="*70)

    # Premieres barres
    print("\n   Premiere barre disponible:")
    first_row = df.iloc[0]
    print(f"   Date/Heure : {first_row['DateTime']}")
    print(f"   GC: ${first_row['Last_GC']:,.2f} | SI: ${first_row['Last_SI']:.3f}")

    # Dernieres barres
    print("\n   Derniere barre disponible:")
    last_row = df.iloc[-1]
    print(f"   Date/Heure : {last_row['DateTime']}")
    print(f"   GC: ${last_row['Last_GC']:,.2f} | SI: ${last_row['Last_SI']:.3f}")

    # Barre du milieu
    print("\n   Barre du milieu (pour test):")
    mid_row = df.iloc[len(df)//2]
    print(f"   Date/Heure : {mid_row['DateTime']}")
    print(f"   GC: ${mid_row['Last_GC']:,.2f} | SI: ${mid_row['Last_SI']:.3f}")

    print("\n" + "="*70)
    print("INSTRUCTIONS DE VALIDATION")
    print("="*70)
    print("""
    1. Ouvre Sierra Chart avec tes graphiques GC et SI

    2. Navigue jusqu'a une des dates ci-dessus

    3. Compare les prix affiches avec ceux de Python :
       - Le prix 'Last' doit correspondre au prix de cloture de la barre
       - Le volume doit correspondre

    4. Si les valeurs correspondent -> les donnees sont OK
       Si ecart -> verifie le timeframe et la session dans Sierra Chart

    5. Pour verifier une date specifique :
       python validate_data.py --date "2026-01-15 14:30:00"
    """)
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
