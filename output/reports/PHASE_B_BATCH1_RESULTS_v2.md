# Phase B Batch 1 -- Resultats

Date: 2026-02-06

## Resume

| Campagne | Configs | Rentables (t>=80) | % | $/t>=$150 | Median $/t | Top PnL | Top $/t | Top PF |
|----------|---------|-------------------|---|-----------|------------|---------|---------|--------|
| B1_5min_zscore_2tick | 34,560 | 1,794 | 8.1% | 224 | $59 | $49,572 | $455 | 2.83 |
| B5_1min_zscore_1tick | 5,832 | 347 | 8.5% | 0 | $29 | $20,896 | $96 | 2.53 |
| B4_1min_dollar_1tick | 9,720 | 1,945 | 22.9% | 9 | $18 | $111,583 | $67 | 2.85 |

## GO / NO-GO

### B1_5min_zscore_2tick

- Rentables (trades>=80) : 1,794 -> **GO** (seuil: >=100)
- Median PnL/trade : $59 -> **WARN** (<$150)

### B5_1min_zscore_1tick

- Rentables (trades>=50) : 494 (8.5%)
- Informatif (pas de seuil strict)
- Median PnL/trade : $29 -> **WARN** (<$150)
- Top PnL/trade : $96 -> **WARN** (fragile au slippage)

### B4_1min_dollar_1tick

- Taux rentable : 22.9% -> **GO** (seuil: >15%)
- Median PnL/trade : $18 -> **WARN** (<$150)
- Top PnL/trade : $67 -> **WARN** (fragile au slippage)

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

### Top 5 -- 5min (slippage 2tick)

| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |
|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|
| 1 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL4.5_pure | B1_5min_zscore_2tick | 109 | 54.1% | $49,572 | $455 | 2.55 | $-16,339 | +0.20 |
| 2 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL5.0_pure | B1_5min_zscore_2tick | 109 | 54.1% | $49,572 | $455 | 2.55 | $-16,339 | +0.20 |
| 3 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_zSL3.5_pure | B1_5min_zscore_2tick | 109 | 54.1% | $49,152 | $451 | 2.52 | $-16,700 | +0.20 |
| 4 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-0.5_zSL4.5_pure | B1_5min_zscore_2tick | 109 | 54.1% | $47,727 | $438 | 2.82 | $-13,796 | +0.20 |
| 5 | b2640_zp20_cp24_adf26_zE3.5_co40_zTP-0.5_zSL5.0_pure | B1_5min_zscore_2tick | 109 | 54.1% | $47,727 | $438 | 2.82 | $-13,796 | +0.20 |

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

### B5_1min_zscore_1tick (top 50 rentables, trades>=80)

- **beta** : 1980: 25x, 2640: 13x, 1320: 12x
- **zp** : 24: 28x, 15: 18x, 20: 4x
- **cp** : 48: 25x, 30: 24x, 24: 1x
- **adf** : 128: 30x, 96: 20x
- **zE** : 3.5: 29x, 3.0: 21x
- **co** : 50: 42x, 40: 8x
- **zTP** : -1.0: 27x, 0.0: 10x, -0.5: 9x, 0.5: 4x
- **zSL** : 3.5: 19x, 4.0: 16x, 5.0: 15x

### B4_1min_dollar_1tick (top 50 rentables, trades>=80)

- **beta** : 2640: 37x, 1980: 13x
- **zp** : 20: 25x, 15: 19x, 24: 6x
- **cp** : 48: 28x, 24: 11x, 30: 11x
- **adf** : 96: 29x, 64: 12x, 128: 9x
- **zE** : 2.5: 50x
- **co** : 40: 43x, 50: 7x
- **TP** : 1000: 38x, 700: 10x, 500: 2x
- **SL** : 1200: 31x, 1000: 14x, 800: 5x

## Recommandations Batch 2

- **B1_5min_zscore_2tick** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)
- **B5_1min_zscore_1tick** informatif -> Pas de suite directe, utile pour Phase C+
- **B4_1min_dollar_1tick** GO -> Lancer B6 (1min dollar zp long)
  - WARN : PnL/trade = $67, fragile au slippage

### Points d'attention

- B4 top PnL ($111K) est trompeur -- PF de 1.15 et $67/trade signifient que
  cette config ne survivra probablement pas au stress test slippage en Phase C4
- B1 reste le mode le plus prometteur en qualite (PF 2.55, $455/trade)
- adf=26 doit etre inclus dans les grilles B2/B3 (decouverte majeure B1)
