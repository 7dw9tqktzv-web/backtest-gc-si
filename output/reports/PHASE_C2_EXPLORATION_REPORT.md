# Phase C2 -- Exploration Rolling Hurst vs Fenetres Toxiques

## 1. Resume

- **Objectif** : Tester si le Rolling Hurst du spread GC/SI predit les fenetres toxiques C1
- **Methode** : R/S (Rescaled Range) sur spread daily, sous-periodes [8, 16, 32, 64]
- **Lookbacks testes** : 20j, 40j, 60j (donnees daily)
- **Reference** : beta=2640 (champion B2)

## 2. Statistiques Hurst globales

| Lookback | Jours valides | Mean | Std | % < 0.5 | % > 0.5 |
|----------|---------------|------|-----|---------|---------|
| 20j | 768 | 0.841 | 0.197 | 6.6% | 93.4% |
| 40j | 748 | 0.823 | 0.156 | 3.2% | 96.8% |
| 60j | 728 | 0.819 | 0.156 | 3.3% | 96.7% |

## 3. Correlation Hurst vs PnL par fenetre

| Lookback | Pearson r | p-value | Spearman r | p-value |
|----------|-----------|---------|------------|---------|
| 20j | 0.055 | 0.8457 | 0.179 | 0.5243 |
| 40j | -0.023 | 0.9349 | -0.193 | 0.4910 |
| 60j | 0.009 | 0.9755 | -0.332 | 0.2464 |

**Meilleur lookback** : 60j (Spearman r=-0.332)

## 4. Toxique vs Sain

| Categorie | N | Hurst moyen | % trending | PnL moyen |
|-----------|---|-------------|------------|-----------|
| Toxiques (W02/W04/W05/W08) | 4 | 0.882 | 100.0% | $-1,170 |
| Saines (reste) | 11 | 0.795 | 95.5% | $2,880 |
| Meilleures (W14/W15) | 2 | 0.804 | 94.3% | $13,845 |

## 5. Tableau complet

| Fenetre | Dates | PnL | Toxic | H_20 | %T_20 | H_40 | %T_40 | H_60 | %T_60 |
|---------|-------|-----|-------|------|-------|------|-------|------|-------|
| W01 | 2023-01-26 - 2023-04-13 | $817 |  | 0.916 | 100.0% | 0.990 | 100.0% | nan | nan% |
| W02 | 2023-04-13 - 2023-06-22 | $-1,539 | YES | 0.897 | 100.0% | 0.919 | 100.0% | 0.892 | 100.0% |
| W03 | 2023-06-22 - 2023-09-14 | $-269 |  | 0.765 | 89.1% | 0.848 | 100.0% | 0.848 | 100.0% |
| W04 | 2023-09-14 - 2023-11-13 | $-1,237 | YES | 0.705 | 72.5% | 0.863 | 100.0% | 0.863 | 100.0% |
| W05 | 2023-11-13 - 2024-01-26 | $-941 | YES | 0.750 | 88.7% | 0.841 | 100.0% | 0.841 | 100.0% |
| W06 | 2024-01-26 - 2024-04-09 | $1,682 |  | 0.957 | 100.0% | 0.729 | 100.0% | 0.729 | 100.0% |
| W07 | 2024-04-09 - 2024-06-24 | $1,191 |  | 0.819 | 92.6% | 0.924 | 100.0% | 0.924 | 100.0% |
| W08 | 2024-06-24 - 2024-09-12 | $-965 | YES | 0.915 | 100.0% | 0.932 | 100.0% | 0.932 | 100.0% |
| W09 | 2024-09-12 - 2024-11-11 | $-330 |  | 0.851 | 96.1% | 0.730 | 98.0% | 0.730 | 98.0% |
| W10 | 2024-11-12 - 2025-01-24 | $789 |  | 0.820 | 94.6% | 0.750 | 89.3% | 0.750 | 89.3% |
| W11 | 2025-01-24 - 2025-04-04 | $779 |  | 0.845 | 94.2% | 0.608 | 80.8% | 0.608 | 80.8% |
| W12 | 2025-04-04 - 2025-06-18 | $84 |  | 0.902 | 96.2% | 0.883 | 98.1% | 0.883 | 98.1% |
| W13 | 2025-06-18 - 2025-09-30 | $-749 |  | 0.841 | 85.5% | 0.868 | 100.0% | 0.868 | 100.0% |
| W14 | 2025-09-30 - 2025-12-01 | $5,609 |  | 0.826 | 94.3% | 0.740 | 88.7% | 0.740 | 88.7% |
| W15 | 2025-12-01 - 2026-01-30 | $22,081 |  | 0.847 | 100.0% | 0.868 | 100.0% | 0.868 | 100.0% |

## 6. Verdict

- **Moderement discriminant** : Spearman r=-0.332
- Delta Hurst toxique-sain : +0.087
- Meilleur lookback : 60j

## 7. Prochaines etapes

- Si discriminant : integrer comme filtre dans le backtest engine (C2b)
- Si insuffisant : tester Realized Vol du spread et/ou GVZ/VXSLV ratio
- Le filtre doit etre calculable en daily pour Sierra Chart (check quotidien)
