# Phase B Batch 1 -- Resultats

Date: 2026-02-07

## Resume

| Campagne | Configs | Rentables (t>=80) | % | $/t>=$150 | Median $/t | Top PnL | Top $/t | Top PF |
|----------|---------|-------------------|---|-----------|------------|---------|---------|--------|
| B2_5min_zscore_1tick | 34,560 | 4,036 | 15.8% | 703 | $65 | $59,172 | $334 | 3.65 |
| B6_1min_dollar_zp_long_1tick | 86,400 | 1,342 | 1.6% | 3 | $10 | $53,642 | $31 | 1.70 |

## GO / NO-GO

### B2_5min_zscore_1tick

- Rentables (trades>=80) : 4,036 -> **GO** (seuil: >=100)
- Median PnL/trade : $65 -> **WARN** (<$150)

### B6_1min_dollar_zp_long_1tick

- Taux rentable : 1.6% -> **NO-GO** (seuil: >15%)
- Median PnL/trade : $10 -> **WARN** (<$150)
- Top PnL/trade : $31 -> **WARN** (fragile au slippage)

## Top 5 par timeframe

### Top 5 -- 1min (slippage 1tick)

| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |
|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|
| 1 | b2640_zp48_cp24_adf128_zE2.0_co50_TP1500_SL1200 | B6_1min_dollar_zp_long_1tick | 1727 | 44.2% | $53,642 | $31 | 1.07 | $-55,912 | +0.03 |
| 2 | b1320_zp96_cp96_adf128_zE2.5_co50_TP1500_SL1000 | B6_1min_dollar_zp_long_1tick | 1197 | 37.7% | $51,564 | $43 | 1.11 | $-20,440 | +0.04 |
| 3 | b2640_zp48_cp24_adf64_zE2.0_co50_TP1500_SL1200 | B6_1min_dollar_zp_long_1tick | 1932 | 43.4% | $50,502 | $26 | 1.05 | $-42,168 | +0.02 |
| 4 | b1320_zp96_cp96_adf128_zE2.5_co50_TP1500_SL1500 | B6_1min_dollar_zp_long_1tick | 1133 | 40.6% | $48,353 | $43 | 1.10 | $-27,349 | +0.04 |
| 5 | b2640_zp48_cp24_adf64_zE2.0_co50_TP1500_SL1500 | B6_1min_dollar_zp_long_1tick | 1815 | 45.9% | $46,276 | $26 | 1.05 | $-59,975 | +0.02 |

> ATTENTION: Ces configs sont a 1 tick de slippage. L'audit B0 montre que 0/32,400 configs 1min dollar survivent a 2 ticks.
> B4 top $111K avec PF 1.15 et $67/trade -- volume sans qualite, a valider en Phase C4 (stress test slippage).

### Top 5 -- 5min (slippage 1tick)

| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |
|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|
| 1 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure | B2_5min_zscore_1tick | 177 | 66.7% | $59,172 | $334 | 2.74 | $-9,934 | +0.20 |
| 2 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL5.0_pure | B2_5min_zscore_1tick | 177 | 66.7% | $59,172 | $334 | 2.74 | $-9,934 | +0.20 |
| 3 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | B2_5min_zscore_1tick | 109 | 59.6% | $57,882 | $531 | 3.02 | $-11,859 | +0.23 |
| 4 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | B2_5min_zscore_1tick | 109 | 59.6% | $57,882 | $531 | 3.02 | $-11,859 | +0.23 |
| 5 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL3.5_pure | B2_5min_zscore_1tick | 109 | 58.7% | $57,462 | $527 | 2.98 | $-12,080 | +0.23 |

## Decouvertes cles

### B2_5min_zscore_1tick

- Top config : b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure
- Top PnL : $59,172 ($334/trade, PF 3.65)
- beta=2640 domine (30/50, 60%)
- **cp=24 quasi-exclusif** (40/50, 80%)
- **adf=26 quasi-exclusif** (37/50, 74%)
- zE=3.5 domine (35/50, 70%)
- **co=40 quasi-exclusif** (37/50, 74%)
- zTP=-1.0 domine (22/50, 44%)
- zSL=5.0 domine (23/50, 46%)

### B6_1min_dollar_zp_long_1tick

- Top config : b2640_zp48_cp24_adf128_zE2.0_co50_TP1500_SL1200
- Top PnL : $53,642 ($31/trade, PF 1.70)
- zp=48 domine (23/50, 46%)
- cp=96 domine (26/50, 52%)
- adf=128 domine (21/50, 42%)
- co=50 domine (27/50, 54%)
- **TP=1500 quasi-exclusif** (39/50, 78%)

## Distribution des parametres gagnants

### B2_5min_zscore_1tick (top 50 rentables, trades>=80)

- **beta** : 2640: 30x, 3960: 11x, 5280: 6x, 1320: 3x
- **zp** : 24: 20x, 20: 17x, 30: 8x, 48: 4x, 60: 1x
- **cp** : 24: 40x, 12: 7x, 36: 3x
- **adf** : 26: 37x, 96: 13x
- **zE** : 3.5: 35x, 2.5: 11x, 3.0: 4x
- **co** : 40: 37x, 60: 13x
- **zTP** : -1.0: 22x, -0.5: 18x, 0.0: 7x, 0.5: 3x
- **zSL** : 5.0: 23x, 4.5: 18x, 3.5: 9x

### B6_1min_dollar_zp_long_1tick (top 50 rentables, trades>=80)

- **beta** : 3960: 17x, 2640: 12x, 1980: 11x, 1320: 10x
- **zp** : 48: 23x, 72: 14x, 96: 7x, 132: 4x, 198: 2x
- **cp** : 96: 26x, 24: 12x, 48: 12x
- **adf** : 128: 21x, 64: 12x, 26: 9x, 96: 8x
- **zE** : 2.0: 18x, 2.5: 12x, 3.0: 11x, 3.5: 9x
- **co** : 50: 27x, 60: 14x, 40: 9x
- **TP** : 1500: 39x, 1000: 8x, 800: 3x
- **SL** : 1500: 19x, 1200: 18x, 1000: 9x, 800: 4x

## Recommandations Batch 2

- **B2_5min_zscore_1tick** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)
- **B6_1min_dollar_zp_long_1tick** informatif -> Pas de suite directe, utile pour Phase C+

### Points d'attention

- B4 top PnL ($111K) est trompeur -- PF de 1.15 et $67/trade signifient que
  cette config ne survivra probablement pas au stress test slippage en Phase C4
- B1 reste le mode le plus prometteur en qualite (PF 2.55, $455/trade)
- adf=26 doit etre inclus dans les grilles B2/B3 (decouverte majeure B1)
