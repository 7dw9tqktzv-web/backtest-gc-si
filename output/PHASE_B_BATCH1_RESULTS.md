# Phase B Batch 1 -- Resultats

Date: 2026-02-06

## Resume

| Campagne | Configs | Rentables (trades>=50) | % | Trades>=80 | PnL/trade>=$150 | Top PnL |
|----------|---------|------------------------|---|-----------|-----------------|--------|
| B1 5min zscore 2tick | 34,560 | 2,799 | 8.1% | 1,794 | 561 | $49,572 |
| B4 1min dollar 1tick | 9,720 | 2,222 | 22.9% | 1,945 | 43 | $111,583 |
| B5 1min zscore 1tick | 5,832 | 494 | 8.5% | 347 | 24 | $20,896 |

## GO / NO-GO

- **B1** (5min zscore 2tick): 1794 configs rentables avec trades >= 80 (seuil: 100) --> **GO**
- **B4** (1min dollar 1tick): 27.1% configs rentables (seuil: 15%) --> **GO**
- **B5** (1min zscore 1tick): 494 configs rentables trades >= 50 (informatif)

## Top 5 -- 5min (slippage 2 ticks)

Source: B1 (grid_search_B1_5min_zscore_2tick.csv), filtre trades >= 80

| # | Config | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe | Calmar | Sortino |
|---|--------|--------|-----|-----|---------|-----|-------|--------|--------|---------|
| 1 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | 109 | 54.1% | $49,572 | $455 | 2.55 | $-16,339 | +0.20 | +3.03 | +0.74 |
| 2 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | 109 | 54.1% | $49,572 | $455 | 2.55 | $-16,339 | +0.20 | +3.03 | +0.74 |
| 3 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL3.5_pure | 109 | 54.1% | $49,152 | $451 | 2.52 | $-16,700 | +0.20 | +2.94 | +0.74 |
| 4 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | 109 | 54.1% | $47,727 | $438 | 2.82 | $-13,796 | +0.20 | +3.46 | +0.76 |
| 5 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | 109 | 54.1% | $47,727 | $438 | 2.82 | $-13,796 | +0.20 | +3.46 | +0.76 |

## Top 5 -- 1min (slippage 1 tick)

Source: B4 + B5 merged, filtre trades >= 80

| # | Camp. | Config | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe | Calmar | Sortino |
|---|-------|--------|--------|-----|-----|---------|-----|-------|--------|--------|---------|
| 1 | B4 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1200 | 1655 | 59.4% | $111,583 | $67 | 1.15 | $-47,212 | +0.07 | +2.36 | +0.19 |
| 2 | B4 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1000 | 1756 | 56.2% | $109,259 | $62 | 1.14 | $-51,059 | +0.06 | +2.14 | +0.22 |
| 3 | B4 | b2640_zp20_cp30_adf96_zE2.5_co40_TP1000_SL1200 | 1714 | 58.9% | $108,141 | $63 | 1.14 | $-28,262 | +0.06 | +3.83 | +0.18 |
| 4 | B4 | b2640_zp20_cp30_adf96_zE2.5_co40_TP1000_SL1000 | 1825 | 55.0% | $91,019 | $50 | 1.11 | $-33,529 | +0.05 | +2.71 | +0.18 |
| 5 | B4 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL800 | 1918 | 51.0% | $81,909 | $43 | 1.10 | $-46,602 | +0.05 | +1.76 | +0.20 |

> ATTENTION: Ces configs sont a 1 tick de slippage. L'audit B0 montre que 0/32,400 configs 1min dollar survivent a 2 ticks.
> B4 top $111K avec PF 1.15 et $67/trade -- volume sans qualite, a valider en Phase C4 (stress test slippage).

## Distribution des parametres gagnants (top 50 par campagne)

### B1 -- 5min zscore 2tick

- **beta**: 1320: 10, 2640: 27, 3960: 9, 5280: 4
- **zp**: 20: 17, 24: 15, 30: 4, 48: 13, 60: 1
- **cp**: 12: 6, 24: 37, 36: 7
- **adf**: 26: 36, 64: 3, 96: 9, 128: 2
- **zE**: 2.5: 1, 3.0: 7, 3.5: 42
- **co**: 40: 31, 50: 2, 60: 17
- **zTP**: -1.0: 21, -0.5: 15, 0.0: 10, 0.5: 4
- **zSL**: 3.5: 10, 4.5: 19, 5.0: 21

### B4 -- 1min dollar 1tick

- **beta**: 1980: 13, 2640: 37
- **zp**: 15: 19, 20: 25, 24: 6
- **cp**: 24: 11, 30: 11, 48: 28
- **adf**: 64: 12, 96: 29, 128: 9
- **zE**: 2.5: 50
- **co**: 40: 43, 50: 7
- **TP_dollar**: 500: 2, 700: 10, 1000: 38
- **SL_dollar**: 800: 5, 1000: 14, 1200: 31

### B5 -- 1min zscore 1tick

- **beta**: 1320: 10, 1980: 31, 2640: 9
- **zp**: 15: 15, 20: 16, 24: 19
- **cp**: 24: 3, 30: 32, 48: 15
- **adf**: 96: 25, 128: 25
- **zE**: 3.0: 15, 3.5: 35
- **co**: 40: 3, 50: 47
- **zTP**: -1.0: 29, -0.5: 4, 0.0: 11, 0.5: 6
- **zSL**: 3.5: 17, 4.0: 17, 5.0: 16

## Decouvertes

- **B1 5min zscore 2tick**: meilleur PnL = $49,572 (109 trades, WR 54.1%, PF 2.55)
- **B4 1min dollar 1tick**: meilleur PnL = $111,583 (1655 trades, WR 59.4%, PF 1.15)
- **B5 1min zscore 1tick**: meilleur PnL = $20,896 (218 trades, WR 49.1%, PF 1.65)

- **5min vs 1min zscore**: B1 top = $49,572, B5 top = $20,896
- **B1 median trades**: 262
- **B4 median trades**: 515
- **B5 median trades**: 614
- **B1 taux rentable global**: 11.7%
- **B4 taux rentable global**: 27.1%
- **B5 taux rentable global**: 12.7%

## Recommandations pour Batch 2

1. **B1 (GO)**: Lancer walk-forward sur les top 10 configs B1 pour validation out-of-sample.
2. **B4 (GO)**: Confirmer les meilleurs TP/SL en walk-forward. Tester aussi en 2 ticks.
3. **B5 (informatif)**: Le zscore pur en 1min montre du potentiel. A approfondir.
