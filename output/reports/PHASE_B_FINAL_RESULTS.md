# Phase B Batch 1 -- Resultats

Date: 2026-02-07

## Resume

| Campagne | Configs | Rentables (t>=80) | % | $/t>=$150 | Median $/t | Top PnL | Top $/t | Top PF |
|----------|---------|-------------------|---|-----------|------------|---------|---------|--------|
| B1_5min_zscore_2tick | 34,560 | 1,794 | 8.1% | 224 | $59 | $49,572 | $455 | 2.83 |
| B2_5min_zscore_1tick | 34,560 | 4,036 | 15.8% | 703 | $65 | $59,172 | $334 | 3.65 |
| B3_5min_hybride_2tick | 41,472 | 3,302 | 11.5% | 21 | $28 | $25,164 | $101 | 3.22 |
| B4_1min_dollar_1tick | 9,720 | 1,945 | 22.9% | 9 | $18 | $111,583 | $67 | 2.85 |
| B5_1min_zscore_1tick | 5,832 | 347 | 8.5% | 0 | $29 | $20,896 | $96 | 2.53 |
| B6_1min_dollar_zp_long_1tick | 86,400 | 1,342 | 1.6% | 3 | $10 | $53,642 | $31 | 1.70 |

## GO / NO-GO

### B1_5min_zscore_2tick

- Rentables (trades>=80) : 1,794 -> **GO** (seuil: >=100)
- Median PnL/trade : $59 -> **WARN** (<$150)

### B2_5min_zscore_1tick

- Rentables (trades>=80) : 4,036 -> **GO** (seuil: >=100)
- Median PnL/trade : $65 -> **WARN** (<$150)

### B3_5min_hybride_2tick

- Rentables (trades>=80) : 3,302 -> **GO** (seuil: >=100)
- Median PnL/trade : $28 -> **WARN** (<$150)

### B4_1min_dollar_1tick

- Taux rentable : 22.9% -> **GO** (seuil: >15%)
- Median PnL/trade : $18 -> **WARN** (<$150)
- Top PnL/trade : $67 -> **WARN** (fragile au slippage)

### B5_1min_zscore_1tick

- Rentables (trades>=50) : 494 (8.5%)
- Informatif (pas de seuil strict)
- Median PnL/trade : $29 -> **WARN** (<$150)
- Top PnL/trade : $96 -> **WARN** (fragile au slippage)

### B6_1min_dollar_zp_long_1tick

- Taux rentable : 1.6% -> **NO-GO** (seuil: >15%)
- Median PnL/trade : $10 -> **WARN** (<$150)
- Top PnL/trade : $31 -> **WARN** (fragile au slippage)

## Top 5 par timeframe

### Top 5 -- 1min (slippage 1tick)

| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |
|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|
| 1 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1200 | B4_1min_dollar_1tick | 1655 | 59.4% | $111,583 | $67 | 1.15 | $-47,212 | +0.07 |
| 2 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1000 | B4_1min_dollar_1tick | 1756 | 56.2% | $109,259 | $62 | 1.14 | $-51,059 | +0.06 |
| 3 | b2640_zp20_cp30_adf96_zE2.5_co40_TP1000_SL1200 | B4_1min_dollar_1tick | 1714 | 58.9% | $108,141 | $63 | 1.14 | $-28,262 | +0.06 |
| 4 | b2640_zp20_cp30_adf96_zE2.5_co40_TP1000_SL1000 | B4_1min_dollar_1tick | 1825 | 55.0% | $91,019 | $50 | 1.11 | $-33,529 | +0.05 |
| 5 | b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL800 | B4_1min_dollar_1tick | 1918 | 51.0% | $81,909 | $43 | 1.10 | $-46,602 | +0.05 |

> ATTENTION: Ces configs sont a 1 tick de slippage. L'audit B0 montre que 0/32,400 configs 1min dollar survivent a 2 ticks.
> B4 top $111K avec PF 1.15 et $67/trade -- volume sans qualite, a valider en Phase C4 (stress test slippage).

### Top 5 -- 5min (slippage 1tick/2tick)

| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |
|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|
| 1 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL4.5_pure | B2_5min_zscore_1tick | 177 | 66.7% | $59,172 | $334 | 2.74 | $-9,934 | +0.20 |
| 2 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_zSL5.0_pure | B2_5min_zscore_1tick | 177 | 66.7% | $59,172 | $334 | 2.74 | $-9,934 | +0.20 |
| 3 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | B2_5min_zscore_1tick | 109 | 59.6% | $57,882 | $531 | 3.02 | $-11,859 | +0.23 |
| 4 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | B2_5min_zscore_1tick | 109 | 59.6% | $57,882 | $531 | 3.02 | $-11,859 | +0.23 |
| 5 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL3.5_pure | B2_5min_zscore_1tick | 109 | 58.7% | $57,462 | $527 | 2.98 | $-12,080 | +0.23 |

## Decouvertes cles

### B1_5min_zscore_2tick

- Top config : b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure
- Top PnL : $49,572 ($455/trade, PF 2.83)
- beta=2640 domine (28/50, 56%)
- **cp=24 quasi-exclusif** (38/50, 76%)
- **adf=26 quasi-exclusif** (40/50, 80%)
- **zE=3.5 quasi-exclusif** (41/50, 82%)
- co=40 domine (34/50, 68%)
- zSL=5.0 domine (22/50, 44%)

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

### B3_5min_hybride_2tick

- Top config : b2640_zp30_cp24_adf26_zE3.5_co40_zTP-1.0_SL1200_TPcap2500
- Top PnL : $25,164 ($101/trade, PF 3.22)
- beta=2640 domine (35/50, 70%)
- zp=30 domine (22/50, 44%)
- cp=24 domine (31/50, 62%)
- adf=26 domine (34/50, 68%)
- **zE=3.5 quasi-exclusif** (49/50, 98%)
- **co=40 quasi-exclusif** (48/50, 96%)
- zTP=-1.0 domine (24/50, 48%)

### B4_1min_dollar_1tick

- Top config : b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1200
- Top PnL : $111,583 ($67/trade, PF 2.85)
- **beta=2640 quasi-exclusif** (37/50, 74%)
- zp=20 domine (25/50, 50%)
- cp=48 domine (28/50, 56%)
- adf=96 domine (29/50, 58%)
- **zE=2.5 quasi-exclusif** (50/50, 100%)
- **co=40 quasi-exclusif** (43/50, 86%)
- **TP=1000 quasi-exclusif** (38/50, 76%)
- SL=1200 domine (31/50, 62%)

### B5_1min_zscore_1tick

- Top config : b1980_zp15_cp30_adf96_zE3.0_co50_zTP-1.0_zSL3.5_pure
- Top PnL : $20,896 ($96/trade, PF 2.53)
- beta=1980 domine (25/50, 50%)
- zp=24 domine (28/50, 56%)
- cp=48 domine (25/50, 50%)
- adf=128 domine (30/50, 60%)
- zE=3.5 domine (29/50, 58%)
- **co=50 quasi-exclusif** (42/50, 84%)
- zTP=-1.0 domine (27/50, 54%)

### B6_1min_dollar_zp_long_1tick

- Top config : b2640_zp48_cp24_adf128_zE2.0_co50_TP1500_SL1200
- Top PnL : $53,642 ($31/trade, PF 1.70)
- zp=48 domine (23/50, 46%)
- cp=96 domine (26/50, 52%)
- adf=128 domine (21/50, 42%)
- co=50 domine (27/50, 54%)
- **TP=1500 quasi-exclusif** (39/50, 78%)

## Distribution des parametres gagnants

### B1_5min_zscore_2tick (top 50 rentables, trades>=80)

- **beta** : 2640: 28x, 3960: 10x, 1320: 8x, 5280: 4x
- **zp** : 20: 19x, 24: 15x, 48: 9x, 30: 6x, 60: 1x
- **cp** : 24: 38x, 36: 7x, 12: 5x
- **adf** : 26: 40x, 96: 10x
- **zE** : 3.5: 41x, 3.0: 8x, 2.5: 1x
- **co** : 40: 34x, 60: 14x, 50: 2x
- **zTP** : -1.0: 19x, -0.5: 15x, 0.0: 12x, 0.5: 4x
- **zSL** : 5.0: 22x, 4.5: 19x, 3.5: 9x

### B2_5min_zscore_1tick (top 50 rentables, trades>=80)

- **beta** : 2640: 30x, 3960: 11x, 5280: 6x, 1320: 3x
- **zp** : 24: 20x, 20: 17x, 30: 8x, 48: 4x, 60: 1x
- **cp** : 24: 40x, 12: 7x, 36: 3x
- **adf** : 26: 37x, 96: 13x
- **zE** : 3.5: 35x, 2.5: 11x, 3.0: 4x
- **co** : 40: 37x, 60: 13x
- **zTP** : -1.0: 22x, -0.5: 18x, 0.0: 7x, 0.5: 3x
- **zSL** : 5.0: 23x, 4.5: 18x, 3.5: 9x

### B3_5min_hybride_2tick (top 50 rentables, trades>=80)

- **beta** : 2640: 35x, 3960: 12x, 5280: 2x, 1320: 1x
- **zp** : 30: 22x, 24: 21x, 20: 7x
- **cp** : 24: 31x, 96: 13x, 48: 6x
- **adf** : 26: 34x, 128: 10x, 64: 3x, 96: 3x
- **zE** : 3.5: 49x, 3.0: 1x
- **co** : 40: 48x, 50: 2x
- **zTP** : -1.0: 24x, -0.5: 13x, 0.0: 13x

### B4_1min_dollar_1tick (top 50 rentables, trades>=80)

- **beta** : 2640: 37x, 1980: 13x
- **zp** : 20: 25x, 15: 19x, 24: 6x
- **cp** : 48: 28x, 24: 11x, 30: 11x
- **adf** : 96: 29x, 64: 12x, 128: 9x
- **zE** : 2.5: 50x
- **co** : 40: 43x, 50: 7x
- **TP** : 1000: 38x, 700: 10x, 500: 2x
- **SL** : 1200: 31x, 1000: 14x, 800: 5x

### B5_1min_zscore_1tick (top 50 rentables, trades>=80)

- **beta** : 1980: 25x, 2640: 13x, 1320: 12x
- **zp** : 24: 28x, 15: 18x, 20: 4x
- **cp** : 48: 25x, 30: 24x, 24: 1x
- **adf** : 128: 30x, 96: 20x
- **zE** : 3.5: 29x, 3.0: 21x
- **co** : 50: 42x, 40: 8x
- **zTP** : -1.0: 27x, 0.0: 10x, -0.5: 9x, 0.5: 4x
- **zSL** : 3.5: 19x, 4.0: 16x, 5.0: 15x

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

- **B1_5min_zscore_2tick** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)
- **B2_5min_zscore_1tick** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)
- **B3_5min_hybride_2tick** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)
- **B4_1min_dollar_1tick** GO -> Lancer B6 (1min dollar zp long)
  - WARN : PnL/trade = $67, fragile au slippage
- **B5_1min_zscore_1tick** informatif -> Pas de suite directe, utile pour Phase C+
- **B6_1min_dollar_zp_long_1tick** informatif -> Pas de suite directe, utile pour Phase C+

### Points d'attention

- B4 top PnL ($111K) est trompeur -- PF de 1.15 et $67/trade signifient que
  cette config ne survivra probablement pas au stress test slippage en Phase C4
- B1 reste le mode le plus prometteur en qualite (PF 2.55, $455/trade)
- adf=26 doit etre inclus dans les grilles B2/B3 (decouverte majeure B1)
