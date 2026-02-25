# Phase C1 -- Walk-Forward Diagnostique

## Resume

- **Configs** : 330
- **Fenetres** : 15
- **Total runs** : 4950

## Fenetres

| Fenetre | Debut | Fin | Barres | PnL Moyen | % Perte | Statut |
|---------|-------|-----|--------|-----------|---------|--------|
| W01 | 2023-01-26 | 2023-04-13 | 11,148 | $817 | 18% | OK |
| W02 | 2023-04-13 | 2023-06-22 | 11,148 | $-1,539 | 81% | TOXIQUE |
| W03 | 2023-06-22 | 2023-09-14 | 11,148 | $-269 | 57% | OK |
| W04 | 2023-09-14 | 2023-11-13 | 11,148 | $-1,237 | 83% | TOXIQUE |
| W05 | 2023-11-13 | 2024-01-26 | 11,148 | $-941 | 68% | TOXIQUE |
| W06 | 2024-01-26 | 2024-04-09 | 11,148 | $1,682 | 16% | OK |
| W07 | 2024-04-09 | 2024-06-24 | 11,148 | $1,191 | 31% | OK |
| W08 | 2024-06-24 | 2024-09-12 | 11,148 | $-965 | 69% | TOXIQUE |
| W09 | 2024-09-12 | 2024-11-11 | 11,148 | $-330 | 50% | OK |
| W10 | 2024-11-12 | 2025-01-24 | 11,148 | $789 | 37% | OK |
| W11 | 2025-01-24 | 2025-04-04 | 11,148 | $779 | 27% | OK |
| W12 | 2025-04-04 | 2025-06-18 | 11,148 | $84 | 50% | OK |
| W13 | 2025-06-18 | 2025-09-30 | 11,148 | $-749 | 57% | OK |
| W14 | 2025-09-30 | 2025-12-01 | 11,148 | $5,609 | 7% | OK |
| W15 | 2025-12-01 | 2026-01-30 | 11,161 | $22,081 | 0% | OK |

**Fenetres toxiques** : W02, W04, W05, W08

## Top 20 par regularite

| # | Label | % Positives | PnL Total |
|---|-------|-------------|-----------|
| 1 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 80% | $44,218 |
| 2 | b3960_zp24_cp24_adf96_zE2.5_co60_zTP-0.5_zSL5.0_pure | 80% | $36,071 |
| 3 | b3960_zp24_cp24_adf96_zE2.5_co60_zTP-0.5_zSL4.5_pure | 80% | $36,071 |
| 4 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 80% | $44,218 |
| 5 | b3960_zp48_cp24_adf96_zE2.5_co60_zTP-0.5_zSL5.0_pure | 73% | $34,329 |
| 6 | b5280_zp60_cp12_adf128_zE3.0_co60_zTP0.5_zSL4.5_pure | 73% | $16,509 |
| 7 | b5280_zp24_cp36_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 73% | $34,465 |
| 8 | b5280_zp24_cp36_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 73% | $34,465 |
| 9 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 73% | $45,967 |
| 10 | b3960_zp48_cp24_adf96_zE2.5_co60_zTP-0.5_zSL4.5_pure | 73% | $27,479 |
| 11 | b2640_zp48_cp24_adf128_zE2.5_co60_zTP-1.0_zSL4.5_pure | 73% | $28,691 |
| 12 | b2640_zp48_cp24_adf128_zE2.5_co60_zTP-0.5_zSL5.0_pure | 73% | $37,202 |
| 13 | b3960_zp24_cp24_adf96_zE2.5_co60_zTP-1.0_zSL4.5_pure | 73% | $38,961 |
| 14 | b3960_zp48_cp24_adf96_zE2.5_co60_zTP0.0_zSL4.5_pure | 73% | $28,757 |
| 15 | b3960_zp48_cp24_adf96_zE2.5_co60_zTP0.0_zSL5.0_pure | 73% | $36,232 |
| 16 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 73% | $45,967 |
| 17 | b5280_zp60_cp12_adf128_zE3.0_co60_zTP0.5_zSL5.0_pure | 73% | $18,464 |
| 18 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | 73% | $38,215 |
| 19 | b2640_zp48_cp24_adf128_zE2.5_co60_zTP-0.5_zSL4.5_pure | 73% | $32,177 |
| 20 | b3960_zp24_cp12_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 73% | $31,847 |

## Configs fragiles (<30% fenetres positives) : 3/330

## Correlation inter-configs : 0.827

## Verification de coherence (5 premieres configs)

| Label | WF PnL | C0 PnL | Ecart |
|-------|--------|--------|-------|
| b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | $45,967 | $45,967 | 0.0% OK |
| b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | $45,967 | $45,967 | 0.0% OK |
| b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure | $59,172 | $54,055 | 9.5% ALERTE |
| b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL5.0_pure | $59,172 | $54,055 | 9.5% ALERTE |
| b2640_zp24_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | $54,612 | $54,055 | 1.0% OK |

## Conclusions pour C2

- 4 fenetres toxiques identifiees : W02, W04, W05, W08
- Ces fenetres sont les cibles prioritaires pour le filtre de regime C2
- Correlation inter-configs elevee -> les configs respirent ensemble
- Le filtre C2 doit cibler le regime de marche, pas la config individuelle
