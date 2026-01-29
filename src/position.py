# ============================================================================
# POSITION.PY - Sizing des Positions (Dollar Neutral avec Beta)
# ============================================================================
#
# Ce module calcule le nombre de contrats pour chaque leg du spread.
# Le sizing est "dollar neutral ajuste par Beta" :
#
#   1. On fixe le nombre de contrats SI (defaut: 1)
#   2. On calcule le nombre de contrats GC pour etre dollar-neutral :
#      GC_contracts = (SI_notional / GC_notional) x Beta
#   3. On arrondit au contrat entier le plus proche
#
# Formule identique a l'ACSIL v1.4 (lignes 988-991) :
#   NotionalGC = GCPrice * GC_POINT_VALUE
#   NotionalSI = SIPrice * SI_POINT_VALUE
#   ContractsGCForOneSI = NotionalSI / NotionalGC
#   AdjustedContractsGC = ContractsGCForOneSI * Beta
#
# Auteur: Assistant IA
# Date: Janvier 2026
# ============================================================================

import numpy as np
import pandas as pd


# ============================================================================
# FONCTION PRINCIPALE DE SIZING
# ============================================================================

def calculate_position_size(
    gc_price: float,
    si_price: float,
    beta: float,
    config: dict
) -> dict:
    """
    Calcule le nombre de contrats pour chaque leg du spread.

    Le mode "dollar_neutral_beta" reproduit exactement le calcul de
    l'indicateur Sierra Chart v1.4 :
      - Notional GC = prix GC x valeur du point ($100)
      - Notional SI = prix SI x valeur du point ($5000)
      - GC contrats = (Notional SI / Notional GC) x Beta

    Parametres:
    -----------
    gc_price : float
        Prix actuel du Gold (GC)
    si_price : float
        Prix actuel du Silver (SI)
    beta : float
        Beta OLS actuel (hedge ratio)
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    dict : Informations de sizing avec les cles :
        - si_contracts : int, nombre de contrats SI
        - gc_contracts : int, nombre de contrats GC (arrondi)
        - gc_contracts_raw : float, nombre de contrats GC (exact)
        - notional_gc : float, valeur notionnelle GC par contrat
        - notional_si : float, valeur notionnelle SI par contrat
        - notional_gc_total : float, exposition GC totale
        - notional_si_total : float, exposition SI totale
        - imbalance_pct : float, desequilibre en % entre les deux legs
    """
    mode = config['sizing']['mode']
    si_contracts = config['sizing']['si_contracts']

    gc_point_value = config['contracts']['gc_point_value']   # 100
    si_point_value = config['contracts']['si_point_value']   # 5000

    if mode == "dollar_neutral_beta":
        # Formule ACSIL v1.4
        notional_gc = gc_price * gc_point_value
        notional_si = si_price * si_point_value

        gc_for_one_si = notional_si / notional_gc
        gc_contracts_raw = gc_for_one_si * beta * si_contracts
        gc_contracts = round(gc_contracts_raw)

        # Securite : minimum 1 contrat
        gc_contracts = max(gc_contracts, 1)

    elif mode == "dollar_neutral":
        # Dollar neutral sans ajustement Beta
        notional_gc = gc_price * gc_point_value
        notional_si = si_price * si_point_value

        gc_contracts_raw = (notional_si / notional_gc) * si_contracts
        gc_contracts = round(gc_contracts_raw)
        gc_contracts = max(gc_contracts, 1)

    elif mode == "fixed":
        # Nombre fixe de contrats (1 GC pour 1 SI)
        gc_contracts = si_contracts
        gc_contracts_raw = float(si_contracts)
        notional_gc = gc_price * gc_point_value
        notional_si = si_price * si_point_value

    else:
        raise ValueError(f"Mode de sizing inconnu : '{mode}'. "
                         f"Options : 'dollar_neutral_beta', 'dollar_neutral', 'fixed'")

    # Calculer les expositions totales
    notional_gc_total = gc_contracts * gc_price * gc_point_value
    notional_si_total = si_contracts * si_price * si_point_value

    # Desequilibre entre les deux legs (0% = parfaitement neutre)
    avg_notional = (notional_gc_total + notional_si_total) / 2
    if avg_notional > 0:
        imbalance_pct = abs(notional_gc_total - notional_si_total) / avg_notional * 100
    else:
        imbalance_pct = 0.0

    return {
        'si_contracts': si_contracts,
        'gc_contracts': gc_contracts,
        'gc_contracts_raw': round(gc_contracts_raw, 4),
        'notional_gc': round(notional_gc, 2),
        'notional_si': round(notional_si, 2),
        'notional_gc_total': round(notional_gc_total, 2),
        'notional_si_total': round(notional_si_total, 2),
        'imbalance_pct': round(imbalance_pct, 2),
    }


# ============================================================================
# CALCUL DES COUTS DE TRANSACTION
# ============================================================================

def calculate_transaction_costs(
    gc_contracts: int,
    si_contracts: int,
    config: dict
) -> dict:
    """
    Calcule les couts de transaction pour un trade (entree + sortie).

    Couts inclus :
    - Commission : $5.00 round-trip par contrat (chaque leg)
    - Slippage : 1 tick par leg, a l'entree et a la sortie

    Parametres:
    -----------
    gc_contracts : int
        Nombre de contrats GC
    si_contracts : int
        Nombre de contrats SI
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    dict : Details des couts :
        - commission_gc : float, commission totale GC
        - commission_si : float, commission totale SI
        - commission_total : float, commission totale
        - slippage_gc : float, slippage total GC en $
        - slippage_si : float, slippage total SI en $
        - slippage_total : float, slippage total en $
        - total_cost : float, cout total (commission + slippage)
    """
    commission = config['costs']['commission_per_contract']    # $5.00
    slip_gc_ticks = config['costs']['slippage_gc_ticks']       # 1
    slip_si_ticks = config['costs']['slippage_si_ticks']       # 1

    gc_tick_value = config['contracts']['gc_tick_value']        # $10
    si_tick_value = config['contracts']['si_tick_value']        # $25

    # Commissions (round-trip = entree + sortie)
    commission_gc = commission * gc_contracts
    commission_si = commission * si_contracts
    commission_total = commission_gc + commission_si

    # Slippage : on paye le slippage a l'entree ET a la sortie (x2)
    # Pour chaque leg du spread
    slippage_gc = slip_gc_ticks * gc_tick_value * gc_contracts * 2
    slippage_si = slip_si_ticks * si_tick_value * si_contracts * 2
    slippage_total = slippage_gc + slippage_si

    return {
        'commission_gc': round(commission_gc, 2),
        'commission_si': round(commission_si, 2),
        'commission_total': round(commission_total, 2),
        'slippage_gc': round(slippage_gc, 2),
        'slippage_si': round(slippage_si, 2),
        'slippage_total': round(slippage_total, 2),
        'total_cost': round(commission_total + slippage_total, 2),
    }


# ============================================================================
# CALCUL DU PNL D'UN TRADE
# ============================================================================

def calculate_trade_pnl(
    direction: int,
    entry_gc: float,
    entry_si: float,
    exit_gc: float,
    exit_si: float,
    gc_contracts: int,
    si_contracts: int,
    config: dict
) -> dict:
    """
    Calcule le PnL d'un trade spread complet.

    Pour un LONG spread (on est long le spread = long SI, short GC) :
      - PnL SI = (exit_SI - entry_SI) x SI_point_value x SI_contracts
      - PnL GC = (entry_GC - exit_GC) x GC_point_value x GC_contracts
      (On est SHORT GC donc on gagne quand GC baisse)

    Pour un SHORT spread (on est short le spread = short SI, long GC) :
      - PnL SI = (entry_SI - exit_SI) x SI_point_value x SI_contracts
      - PnL GC = (exit_GC - entry_GC) x GC_point_value x GC_contracts
      (On est LONG GC donc on gagne quand GC monte)

    Parametres:
    -----------
    direction : int
        1 = LONG spread, -1 = SHORT spread
    entry_gc, entry_si : float
        Prix d'entree GC et SI
    exit_gc, exit_si : float
        Prix de sortie GC et SI
    gc_contracts, si_contracts : int
        Nombre de contrats pour chaque leg
    config : dict
        Configuration chargee depuis YAML

    Retourne:
    ---------
    dict : Details du PnL :
        - pnl_gc : float, PnL de la leg GC
        - pnl_si : float, PnL de la leg SI
        - pnl_gross : float, PnL brut (avant couts)
        - costs : float, couts de transaction totaux
        - pnl_net : float, PnL net (apres couts)
    """
    gc_point_value = config['contracts']['gc_point_value']   # 100
    si_point_value = config['contracts']['si_point_value']   # 5000

    if direction == 1:
        # LONG spread : long SI, short GC
        pnl_si = (exit_si - entry_si) * si_point_value * si_contracts
        pnl_gc = (entry_gc - exit_gc) * gc_point_value * gc_contracts
    elif direction == -1:
        # SHORT spread : short SI, long GC
        pnl_si = (entry_si - exit_si) * si_point_value * si_contracts
        pnl_gc = (exit_gc - entry_gc) * gc_point_value * gc_contracts
    else:
        raise ValueError(f"Direction invalide : {direction}. Utiliser 1 (LONG) ou -1 (SHORT)")

    pnl_gross = pnl_gc + pnl_si

    # Couts de transaction
    costs = calculate_transaction_costs(gc_contracts, si_contracts, config)

    pnl_net = pnl_gross - costs['total_cost']

    return {
        'pnl_gc': round(pnl_gc, 2),
        'pnl_si': round(pnl_si, 2),
        'pnl_gross': round(pnl_gross, 2),
        'costs': costs['total_cost'],
        'pnl_net': round(pnl_net, 2),
    }


# ============================================================================
# POINT D'ENTREE POUR TEST
# ============================================================================

if __name__ == "__main__":
    """
    Test du module position.

    Pour executer ce test :
        python src/position.py
    """
    from data_loader import load_and_prepare_data
    from indicators import calculate_all_indicators

    print("\n" + "="*60)
    print("TEST DU MODULE POSITION")
    print("="*60)

    try:
        # 1. Charger les donnees et la config
        df, config, stats = load_and_prepare_data(verbose=False)
        print(f"[OK] Donnees chargees : {len(df)} barres")

        # 2. Calculer les indicateurs (pour avoir Beta)
        df = calculate_all_indicators(df, config)
        print(f"[OK] Indicateurs calcules")

        # 3. Test de sizing sur quelques exemples
        print("\n" + "="*60)
        print("EXEMPLES DE SIZING")
        print("="*60)

        # Prendre 3 points dans le temps
        test_indices = [len(df)//4, len(df)//2, 3*len(df)//4]

        for idx in test_indices:
            row = df.iloc[idx]
            gc_price = row['Last_GC']
            si_price = row['Last_SI']
            beta = row['Beta']

            if np.isnan(beta):
                continue

            size = calculate_position_size(gc_price, si_price, beta, config)

            print(f"\n   Date       : {row['DateTime']}")
            print(f"   GC         : ${gc_price:,.2f}  |  SI : ${si_price:.3f}")
            print(f"   Beta       : {beta:.4f}")
            print(f"   Mode       : {config['sizing']['mode']}")
            print(f"   Contrats   : {size['gc_contracts']} GC / {size['si_contracts']} SI "
                  f"(GC exact: {size['gc_contracts_raw']:.4f})")
            print(f"   Notionnel  : GC ${size['notional_gc_total']:,.0f} "
                  f"| SI ${size['notional_si_total']:,.0f}")
            print(f"   Desequilibre : {size['imbalance_pct']:.1f}%")

        # 4. Test des couts de transaction
        print("\n" + "="*60)
        print("COUTS DE TRANSACTION (exemple)")
        print("="*60)

        # Utiliser le dernier sizing calcule
        costs = calculate_transaction_costs(
            size['gc_contracts'], size['si_contracts'], config
        )
        print(f"\n   Pour {size['gc_contracts']} GC + {size['si_contracts']} SI :")
        print(f"   Commission  : ${costs['commission_total']:.2f} "
              f"(GC: ${costs['commission_gc']:.2f}, SI: ${costs['commission_si']:.2f})")
        print(f"   Slippage    : ${costs['slippage_total']:.2f} "
              f"(GC: ${costs['slippage_gc']:.2f}, SI: ${costs['slippage_si']:.2f})")
        print(f"   Cout total  : ${costs['total_cost']:.2f}")

        # 5. Test du calcul de PnL
        print("\n" + "="*60)
        print("CALCUL PNL (exemple avec Trade #1)")
        print("="*60)

        # Simuler le trade #1 du trade_list.csv
        # LONG, entry GC=4241.4 SI=62.45, exit GC=4240.7 SI=62.375
        entry_gc, entry_si = 4241.4, 62.45
        exit_gc, exit_si = 4240.7, 62.375

        # Chercher le Beta le plus proche de ce prix GC (avec Beta valide)
        valid_beta = df[df['Beta'].notna() & (df['Last_GC'] >= entry_gc - 1) & (df['Last_GC'] <= entry_gc + 1)]
        if len(valid_beta) > 0:
            beta_val = valid_beta.iloc[0]['Beta']
        else:
            # Fallback : prendre le premier Beta non-NaN
            beta_val = df['Beta'].dropna().iloc[0]

        size_t1 = calculate_position_size(entry_gc, entry_si, beta_val, config)

        pnl = calculate_trade_pnl(
            direction=1,
            entry_gc=entry_gc, entry_si=entry_si,
            exit_gc=exit_gc, exit_si=exit_si,
            gc_contracts=size_t1['gc_contracts'],
            si_contracts=size_t1['si_contracts'],
            config=config
        )

        print(f"\n   Trade LONG spread")
        print(f"   GC : {entry_gc} -> {exit_gc} (short {size_t1['gc_contracts']} contrats)")
        print(f"   SI : {entry_si} -> {exit_si} (long {size_t1['si_contracts']} contrat)")
        print(f"   Beta: {beta_val:.4f}")
        print(f"")
        print(f"   PnL GC     : ${pnl['pnl_gc']:+,.2f}")
        print(f"   PnL SI     : ${pnl['pnl_si']:+,.2f}")
        print(f"   PnL brut   : ${pnl['pnl_gross']:+,.2f}")
        print(f"   Couts      : -${pnl['costs']:.2f}")
        print(f"   PnL net    : ${pnl['pnl_net']:+,.2f}")

        print("\n" + "="*60)
        print("[OK] Test du module position REUSSI !")
        print("="*60)

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
