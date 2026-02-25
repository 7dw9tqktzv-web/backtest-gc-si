# Phase C0 -- Scoring & Pre-selection Prop Firm

## Resume

- **Source** : B2 (5min zscore 1tick, champion Phase B)
- **Depart** : 34,560 configs
- **Survivantes** : 330 configs apres filtrage
- **Top selectionnees** : 330 pour Phase C1 Walk-Forward

## Entonnoir de filtrage

| Filtre | Restantes | Eliminees |
|--------|-----------|-----------|
| Depart | 34,560 | - |
| trades >= 150 | 23,885 | -10,675 |
| pnl_net > 0 | 2,168 | -21,717 |
| profit_factor > 1.3 | 469 | -1,699 |
| max_dd > -15000 | 371 | -98 |
| pnl_avg > 80 | 330 | -41 |

## Formule de scoring

Normalisation min-max (0-1) sur les survivantes, puis somme ponderee :

| Metrique | Poids | Justification |
|----------|-------|---------------|
| Sortino | 0.25 | Penalise uniquement le downside risk |
| Profit Factor | 0.25 | Qualite des trades |
| $/trade | 0.20 | Robustesse au slippage reel |
| Calmar | 0.20 | PnL/MaxDD -- protection du capital |
| PnL Net | 0.10 | PnL absolu (reduit -- consistance > max PnL) |

Sortino+Calmar = 45% : consistance et protection du capital priment.

## Top 20 configs

| Rank | Label | Trades | PnL | PF | Sharpe | Sortino | Calmar | $/trade | MaxDD | WR% | Score |
|------|-------|--------|-----|-----|--------|---------|--------|---------|-------|-----|-------|
| 1 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 160 | $45,967 | 2.24 | 0.20 | 0.343 | 7.49 | $287.3 | $-4,311 | 65.6% | 0.944 |
| 2 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 160 | $45,967 | 2.24 | 0.20 | 0.343 | 7.49 | $287.3 | $-4,311 | 65.6% | 0.944 |
| 3 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure | 177 | $54,055 | 2.25 | 0.20 | 0.315 | 5.96 | $305.4 | $-9,934 | 66.7% | 0.910 |
| 4 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL5.0_pure | 177 | $54,055 | 2.25 | 0.20 | 0.315 | 5.96 | $305.4 | $-9,934 | 66.7% | 0.910 |
| 5 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | 177 | $54,055 | 2.25 | 0.21 | 0.304 | 5.33 | $305.4 | $-10,239 | 65.5% | 0.880 |
| 6 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | 177 | $54,055 | 2.25 | 0.21 | 0.304 | 5.33 | $305.4 | $-10,239 | 65.5% | 0.880 |
| 7 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL3.5_pure | 177 | $50,092 | 2.25 | 0.17 | 0.264 | 5.76 | $283.0 | $-8,700 | 62.1% | 0.829 |
| 8 | b3960_zp20_cp24_adf96_zE2.5_co60_zTP-1.0_zSL4.5_pure | 162 | $37,675 | 2.10 | 0.17 | 0.363 | 6.60 | $232.6 | $-5,711 | 62.3% | 0.826 |
| 9 | b3960_zp20_cp24_adf96_zE2.5_co60_zTP-1.0_zSL5.0_pure | 162 | $37,675 | 2.10 | 0.17 | 0.363 | 6.60 | $232.6 | $-5,711 | 62.3% | 0.826 |
| 10 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 177 | $52,692 | 2.17 | 0.16 | 0.286 | 4.94 | $297.7 | $-10,674 | 63.8% | 0.820 |
| 11 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 177 | $52,692 | 2.17 | 0.16 | 0.286 | 4.94 | $297.7 | $-10,674 | 63.8% | 0.820 |
| 12 | b3960_zp20_cp24_adf96_zE2.5_co60_zTP-1.0_zSL3.5_pure | 162 | $37,245 | 2.08 | 0.17 | 0.363 | 6.52 | $229.9 | $-5,711 | 62.3% | 0.815 |
| 13 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-1.0_zSL3.5_pure | 177 | $48,752 | 2.08 | 0.18 | 0.263 | 5.91 | $275.4 | $-8,255 | 60.5% | 0.777 |
| 14 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 169 | $44,218 | 2.07 | 0.20 | 0.294 | 5.40 | $261.6 | $-8,195 | 64.5% | 0.762 |
| 15 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 169 | $44,218 | 2.07 | 0.20 | 0.294 | 5.40 | $261.6 | $-8,195 | 64.5% | 0.762 |
| 16 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP-0.5_zSL3.5_pure | 177 | $48,107 | 2.05 | 0.15 | 0.260 | 4.90 | $271.8 | $-9,815 | 58.8% | 0.730 |
| 17 | b3960_zp30_cp24_adf96_zE2.5_co60_zTP-0.5_zSL5.0_pure | 211 | $41,946 | 1.97 | 0.15 | 0.256 | 7.49 | $198.8 | $-5,394 | 64.9% | 0.707 |
| 18 | b3960_zp24_cp24_adf96_zE2.5_co60_zTP-1.0_zSL3.5_pure | 188 | $38,431 | 1.89 | 0.14 | 0.277 | 7.49 | $204.4 | $-4,977 | 62.2% | 0.700 |
| 19 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure | 160 | $35,622 | 2.03 | 0.18 | 0.233 | 6.75 | $222.6 | $-5,281 | 68.8% | 0.685 |
| 20 | b5280_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL5.0_pure | 160 | $35,622 | 2.03 | 0.18 | 0.233 | 6.75 | $222.6 | $-5,281 | 68.8% | 0.685 |

## Diversite des parametres (top 50)

- **beta** : 1320=4, 2640=12, 3960=26, 5280=8
- **zp** : 20=11, 24=32, 30=7
- **cp** : 12=3, 24=43, 36=2, 60=2
- **adf** : 26=30, 96=18, 128=2
- **zE** : 2.5=18, 3.0=2, 3.5=30
- **co** : 40=26, 50=6, 60=18
- **zTP** : -1.0=14, -0.5=21, 0.0=13, 0.5=2
- **zSL** : 3.5=11, 4.5=19, 5.0=20

## Clusters (beta, zp, adf) -- top 330

| Cluster | Configs | % du pool |
|---------|---------|-----------|
| b3960_zp24_adf26 | 26 | 7.9% |
| b3960_zp30_adf96 | 25 | 7.6% |
| b1320_zp30_adf26 | 22 | 6.7% |
| b3960_zp20_adf96 | 20 | 6.1% |
| b3960_zp24_adf96 | 19 | 5.8% |
| b1320_zp24_adf26 | 19 | 5.8% |
| b3960_zp30_adf26 | 19 | 5.8% |
| b2640_zp24_adf26 | 18 | 5.5% |
| b5280_zp24_adf26 | 16 | 4.8% |
| b1320_zp30_adf64 | 16 | 4.8% |

Bonne diversite : cluster dominant = 7.9%.

## Distribution des scores

- Min : 0.027
- Q25 : 0.147
- Median : 0.232
- Q75 : 0.403
- Max : 0.944
- Ecart top1-top50 : 0.438

## Recommandation

Pool de 330 configs selectionne pour Phase C1 Walk-Forward diagnostique.
Fichier : `output/phase_c0_top500.csv`
