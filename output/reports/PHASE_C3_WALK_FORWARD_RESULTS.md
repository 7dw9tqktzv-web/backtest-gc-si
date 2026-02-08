# Phase C3 -- Walk-Forward Final avec filtre Correlation

*Date: 2026-02-08*
*Script: `scripts/phase_c3_walk_forward.py`*
*Config de reference: 9 configs candidates (b3960 + b2640 variants)*

---

## Resume executif

**NO-GO** -- Le filtre Correlation Daily (seuil 0.86) ne tient pas en walk-forward hors-echantillon. Le PnL total passe de $21,666 a $19,730 (-$1,936). Le filtre ne bloque que 5/135 trades directement ; son effet principal est indirect (il change la config selectionnee en TRAIN).

---

## Resultats globaux

| Metrique | Sans Filtre | Avec Filtre (0.86) | Delta |
|----------|-------------|-------------------|-------|
| PnL total | $21,666 | $19,730 | -$1,936 |
| Trades | 135 | 130 | -5 |
| Fenetres positives | 15/34 (44%) | 15/34 (44%) | 0 |
| PF | 1.71 | 1.80 | +0.09 |
| MaxDD | -$16,876 | -$15,607 | +$1,269 |
| PnL/trade | $160 | $152 | -$8 |

---

## Detail par fenetre (34 fenetres, 63j train / 21j test)

| W | Periode TEST | Config sans filtre | Config avec filtre | Tr NF | Tr F | PnL NF | PnL F | Delta |
|---|-------------|-------------------|-------------------|-------|------|--------|-------|-------|
| 1 | 2023-05-29 / 2023-06-21 | zTP-1.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 4 | 6 | -$1,602 | -$2,263 | -$661 |
| 2 | 2023-06-22 / 2023-07-25 | zTP-1.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 3 | 2 | -$1,368 | -$49 | +$1,319 |
| 3 | 2023-07-26 / 2023-08-18 | zTP-1.0_b2640_zp20_cp30_adf26_co40 | zTP-1.0_b2640_zp20_cp30_adf26_co40 | 1 | 1 | -$1,163 | -$1,163 | $0 |
| 4 | 2023-08-20 / 2023-09-22 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | zTP1.0_b2640_zp20_cp30_adf26_co40 | 5 | 2 | $493 | -$370 | -$863 |
| 5 | 2023-09-24 / 2023-10-17 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 4 | 7 | $843 | $400 | -$443 |
| 6 | 2023-10-18 / 2023-11-10 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | 6 | 7 | -$1,793 | -$2,406 | -$613 |
| 7 | 2023-11-12 / 2023-12-15 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 4 | 4 | -$2,037 | -$4,476 | -$2,439 |
| 8 | 2023-12-17 / 2024-01-11 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | b3960_zp24_cp48_adf26_co50_zTP-1.0 | 4 | 5 | -$952 | -$880 | +$72 |
| 9 | 2024-01-12 / 2024-02-05 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 4 | 4 | -$3,097 | -$2,902 | +$195 |
| 10 | 2024-02-06 / 2024-02-29 | zTP1.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 1 | 1 | -$173 | $67 | +$240 |
| 11 | 2024-03-12 / 2024-04-05 | zTP0.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | 4 | 4 | $13 | $658 | +$645 |
| 12 | 2024-04-07 / 2024-04-30 | zTP-0.5_b2640_zp20_cp30_adf26_co40 | zTP-0.5_b2640_zp20_cp30_adf26_co40 | 8 | 8 | $1,041 | $1,041 | $0 |
| 13 | 2024-05-14 / 2024-06-06 | zTP0.0_b2640_zp20_cp30_adf26_co40 | zTP0.0_b2640_zp20_cp30_adf26_co40 | 7 | 6 | $1,641 | $1,899 | +$258 |
| 14 | 2024-06-07 / 2024-07-10 | zTP0.0_b2640_zp20_cp30_adf26_co40 | zTP0.0_b2640_zp20_cp30_adf26_co40 | 2 | 2 | -$776 | -$776 | $0 |
| 15 | 2024-07-11 / 2024-08-04 | zTP0.0_b2640_zp20_cp30_adf26_co40 | zTP0.0_b2640_zp20_cp30_adf26_co40 | 4 | 4 | -$3,831 | -$3,831 | $0 |
| 16 | 2024-08-05 / 2024-08-28 | zTP1.0_b2640_zp20_cp30_adf26_co40 | zTP0.0_b2640_zp20_cp30_adf26_co40 | 1 | 1 | -$103 | -$858 | -$755 |
| 17 | 2024-08-29 / 2024-09-29 | zTP1.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 3 | 6 | -$899 | $467 | +$1,366 |
| 18 | 2024-09-30 / 2024-10-23 | zTP1.0_b2640_zp20_cp30_adf26_co40 | zTP1.0_b2640_zp20_cp30_adf26_co40 | 6 | 6 | -$1,013 | -$1,013 | $0 |
| 19 | 2024-10-24 / 2024-11-17 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | 2 | 2 | -$956 | -$956 | $0 |
| 20 | 2024-11-18 / 2024-12-20 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | 3 | 3 | -$459 | -$459 | $0 |
| 21 | 2024-12-22 / 2025-01-14 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | 1 | 1 | $682 | $682 | $0 |
| 22 | 2025-01-15 / 2025-02-07 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 3 | 3 | $1,391 | $1,391 | $0 |
| 23 | 2025-02-09 / 2025-03-13 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 3 | 3 | -$1,819 | -$1,819 | $0 |
| 24 | 2025-03-14 / 2025-04-07 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 3 | 2 | $4,581 | $1,919 | -$2,662 |
| 25 | 2025-04-08 / 2025-05-14 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 3 | 3 | $916 | $916 | $0 |
| 26 | 2025-05-15 / 2025-06-08 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 1 | 0 | $547 | $0 | -$547 |
| 27 | 2025-06-09 / 2025-07-16 | b3960_zp24_cp48_adf26_co50_zTP-1.0 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 2 | 3 | -$3,041 | $2,726 | +$5,767 |
| 28 | 2025-07-17 / 2025-08-10 | b3960_zp24_cp12_adf26_co50_zTP-1.0 | b3960_zp24_cp48_adf26_co50_zTP-1.0 | 4 | 2 | -$1,912 | -$261 | +$1,651 |
| 29 | 2025-08-11 / 2025-09-29 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | 9 | 5 | -$3,632 | -$60 | +$3,572 |
| 30 | 2025-09-30 / 2025-10-23 | zTP0.0_b2640_zp20_cp30_adf26_co40 | b3960_zp24_cp12_adf26_co40_zTP-1.0 | 5 | 7 | $3,545 | $1,324 | -$2,221 |
| 31 | 2025-10-24 / 2025-11-17 | zTP-0.5_b2640_zp20_cp30_adf26_co40 | zTP-0.5_b2640_zp20_cp30_adf26_co40 | 2 | 2 | $5,124 | $5,124 | $0 |
| 32 | 2025-11-18 / 2025-12-11 | b3960_zp24_cp60_adf26_co50_zTP-1.0 | zTP-1.0_b2640_zp20_cp30_adf26_co40 | 6 | 1 | $5,664 | -$153 | -$5,817 |
| 33 | 2025-12-12 / 2026-01-05 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | 4 | 4 | $14,014 | $14,014 | $0 |
| 34 | 2026-01-06 / 2026-01-29 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | b3960_zp24_cp24_adf26_co40_zTP-1.0 | 13 | 13 | $11,797 | $11,797 | $0 |

---

## Analyse des fenetres toxiques (identifiees en C1)

Fenetres toxiques C1 (W02, W04, W05, W08) -- correspondance approximative dans le WF C3 :

- **W09 (2024-01-12 / 2024-02-05)** : NF -$3,097 -> F -$2,902 (+$195). Legerement ameliore.
- **W27 (2025-06-09 / 2025-07-16)** : NF -$3,041 -> F +$2,726 (+$5,767). **Neutralisee avec succes.**
- **W28 (2025-07-17 / 2025-08-10)** : NF -$1,912 -> F -$261 (+$1,651). **Quasiment neutralisee.**
- **W29 (2025-08-11 / 2025-09-29)** : NF -$3,632 -> F -$60 (+$3,572). **Neutralisee avec succes.**

Mais le filtre empire d'autres fenetres :
- **W07 (2023-11-12 / 2023-12-15)** : NF -$2,037 -> F -$4,476 (-$2,439). **Degradee.**
- **W32 (2025-11-18 / 2025-12-11)** : NF +$5,664 -> F -$153 (-$5,817). **Catastrophe** (bon trade bloque).

---

## Analyse par periode

| Periode | PnL sans filtre | PnL avec filtre | Delta |
|---------|----------------|-----------------|-------|
| 2023 (W01-W08) | -$7,579 | -$11,207 | -$3,628 |
| 2024 (W09-W20) | -$7,613 | -$5,701 | +$1,912 |
| 2025-2026 (W21-W34) | $36,858 | $36,638 | -$220 |

Le filtre empire significativement 2023 (-$3,628) et n'ameliore que legerement 2024 (+$1,912). L'effet net est negatif.

---

## Sensibilite au seuil

Les seuils 0.84, 0.86 et 0.88 ont ete testes. Resultats stables mais tous inferieurs au baseline sans filtre. Le seuil n'a pas d'impact significatif car le filtre agit principalement de maniere indirecte (via la selection de config en TRAIN).

---

## Conclusion

Le filtre Correlation Daily est un **faux positif** : performant en backtest complet (PF 7.84 avec seuil 0.86) mais inefficace en walk-forward OOS. Le mecanisme d'echec est l'**effet indirect** : le filtre modifie les metriques TRAIN, ce qui change la config selectionnee pour chaque fenetre TEST. Ce changement est imprevisible (parfois benefique, parfois deletere).

**Decision definitive** : aucun filtre de regime teste (HMM, Half-life, Correlation, Hurst, ADF, Vol, Slope) ne fonctionne en conditions reelles. La strategie procedera sans filtre pour les phases C4/C5.
