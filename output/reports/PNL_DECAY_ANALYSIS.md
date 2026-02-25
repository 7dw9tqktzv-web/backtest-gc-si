# PnL Decay Analysis - Grid Micro R1

## Familles analysees

| # | Config | Trades | PnL | WR | PF | DD | Sharpe |
|---|--------|--------|-----|----|----|-----|--------|
| 1 | zE3.5_co20_zTP1.5 | 123 | $4478 | 48.8% | 2.15 | $-955 | 0.26 |
| 2 | zE3.5_co20_zTP2.0 | 123 | $4198 | 50.4% | 2.04 | $-1035 | 0.24 |
| 3 | zE3.5_co20_zTP1.0 | 123 | $4359 | 48.8% | 2.00 | $-1090 | 0.24 |
| 4 | zE3.5_co20_zTP0.0 | 123 | $4470 | 52.0% | 1.93 | $-1239 | 0.23 |
| 5 | zE3.5_co20_zTP0.5 | 123 | $4344 | 49.6% | 1.99 | $-1225 | 0.24 |
| 6 | zE3.25_co40_zTP0.5 | 141 | $3615 | 54.6% | 1.77 | $-683 | 0.18 |
| 7 | zE3.5_co20_zTP0.75 | 123 | $4187 | 48.8% | 1.94 | $-1297 | 0.23 |
| 8 | zE3.5_co30_zTP1.5 | 102 | $2949 | 45.1% | 1.86 | $-657 | 0.21 |

## Etape A : Analyse 1-min

### F1_zE3.5_co20_zTP1.5

| Exit Type | N | PnL avg | MFE avg | MAE avg | Decay | Peak bar |
|-----------|---|---------|---------|---------|-------|----------|
| TP_ZSCORE | 45 | $-17 | $104 | $-80 | -0.25 | 1 |
| TP_DOLLAR | 27 | $255 | $905 | $0 | 0.59 | 0 |
| END_SESSION | 50 | $-33 | $57 | $-42 | 0.09 | 2 |

### Contribution PnL par exit type

- **END_SESSION**: $-1634 (-36%)
- **TP_ZSCORE**: $-779 (-17%)
- **TP_DOLLAR**: $6894 (154%)

### Benchmarks Z-Score (PnL moyen aux seuils)

| Famille | Z=1.5 | Z=1.0 | Z=0.5 | Z=0.0 | Exit reel |
|---------|-------|-------|-------|-------|-----------|
| zTP=1.5 | $nan | $nan | $37 | $60 | $37 |
| zTP=2.0 | $nan | $nan | $37 | $37 | $35 |
| zTP=1.0 | $nan | $nan | $37 | $60 | $36 |
| zTP=0.0 | $-87 | $-36 | $-76 | $-33 | $36 |
| zTP=0.5 | $nan | $45 | $-99 | $-42 | $35 |
| zTP=0.5 | $60 | $92 | $51 | $22 | $26 |
| zTP=0.75 | $nan | $nan | $37 | $71 | $34 |
| zTP=1.5 | $nan | $nan | $37 | $60 | $29 |

## Etape B : Analyse 5s (Top 3)

### F1_zE3.5_co20_zTP1.5

**TP_DOLLAR** (27 trades):
- MFE apres trigger $300: avg=$905, med=$465, max=$3431
- -> dTP trop agressif, le trade continuait. Tester $400-500

**END_SESSION** (32 trades):
- Point mort moyen: 3 min
- PnL au point mort: avg=$12
- -> MHB recommande: 32 min (median + 30 min marge)

**MAE 5s** (123 trades):
- Avg: $145, P5: $-253, Min: $-792
- -> SL recommande: $-303 (P5 x 1.2)

### F4_zE3.5_co20_zTP0.0

**TP_DOLLAR** (27 trades):
- MFE apres trigger $300: avg=$905, med=$465, max=$3431
- -> dTP trop agressif, le trade continuait. Tester $400-500

**END_SESSION** (38 trades):
- Point mort moyen: 3 min
- PnL au point mort: avg=$16
- -> MHB recommande: 32 min (median + 30 min marge)

**MAE 5s** (123 trades):
- Avg: $122, P5: $-436, Min: $-792
- -> SL recommande: $-523 (P5 x 1.2)

### F6_zE3.25_co40_zTP0.5

**TP_DOLLAR** (21 trades):
- MFE apres trigger $300: avg=$692, med=$415, max=$1961
- -> dTP trop agressif, le trade continuait. Tester $400-500

**END_SESSION** (36 trades):
- Point mort moyen: 3 min
- PnL au point mort: avg=$17
- -> MHB recommande: 32 min (median + 30 min marge)

**MAE 5s** (141 trades):
- Avg: $34, P5: $-364, Min: $-792
- -> SL recommande: $-436 (P5 x 1.2)


## Recommandations R2

Basees sur l'analyse PnL decay :

- **mhb**: 32 min (median point mort 2 + 30 min marge)
- **dTP**: tester $400-500 (MFE post-trigger avg=$845)
- **dSL**: $-456 (P5 MAE $-381 x 1.2)

### Z-Score TP optimal
- **zTP optimal**: 1.5 (meilleur Calmar dans la zone zE=3.5/co=20)

---
*Genere par pnl_decay_analysis.py*