# FINAL V1 RANKINGS -- Configuration Rankings for Production

*Generated: 2026-02-08*
*Validation: Phase C complete (C0-C5)*

---

## Config Production Recommandee

| Parametre | Valeur |
|-----------|--------|
| Timeframe | 5-min |
| Exit mode | Pure Z-Score |
| beta_lookback | 2640 (10 jours) |
| zscore_period | 20 |
| correlation_period | 30 |
| adf_hurst_period | 26 |
| zscore_entry | 3.5 |
| cointegration_min | 40 |
| zscore_tp | -1.0 (overshoot) |
| zscore_sl | 4.0 |
| regime_filter | Disabled |
| slippage | 2 ticks (nominal) |

### Performance validee

| Metrique | Backtest 3 ans | Walk-Forward | Monte Carlo (100tr) |
|----------|---------------|-------------|-------------------|
| PnL | $45,224 | $20,553 | $45,395 (median) |
| Trades | 100 | 93 | 100 |
| WR | 53% | 32% fenetres+ | -- |
| PF | 2.41 | -- | -- |
| P(perte) | -- | -- | 0.9% |
| Breakeven slippage | -- | -- | 8.0 ticks |

---

## Top 5 Configs 5-MIN (Phase B + C)

| Rang | Config | PnL | Trades | WR% | PF | Sharpe | WF Robustesse | Validation C4/C5 |
|------|--------|-----|--------|-----|-----|--------|---------------|-----------------|
| **1** | `b3960_zp24_cp12_adf26_zE3.5_zTP-1.0_co50` | $24,694 WF | 153 | ~50% | ~2.0 | -- | **53% fenetres+** | Non testee |
| **2** | `b2640_zp20_cp30_adf26_zE3.5_zTP-1.0_zSL4.0_co40` | **$45,224** | 100 | 53% | 2.41 | 3.02 | 32% fenetres+ | **GO (C4+C5)** |
| **3** | `b2640_zp20_cp30_adf128_zE3.5_zTP1.0_co50` | $7,818 | 23 | **60.9%** | 4.09 | **0.361** | -- | Non testee |
| **4** | `b1320_zp20_cp30_adf64_zE3.5_zTP1.0_co50` | $11,420 | 30 | 53.3% | 3.28 | 0.205 | -- | Non testee |
| **5** | `b3960_zp24_cp60_adf26_zE3.5_zTP-1.0_co50` | $24,694 WF | 153 | ~50% | ~2.0 | -- | **53% fenetres+** | Non testee |

---

## Top 5 Configs 1-MIN (Phase B)

| Rang | Config | PnL | Trades | WR% | PF | Sharpe | Justification |
|------|--------|-----|--------|-----|-----|--------|---------------|
| **1** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL1200_co50` | **$16,585** | 93 | **82.8%** | 2.10 | **0.324** | BEST OVERALL |
| **2** | `b1320_zp20_cp30_adf128_zE3.5_TP1000_SL1200_co50` | $15,890 | 93 | 63.4% | 1.44 | 0.175 | TP large |
| **3** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL1400_co50` | $14,585 | 93 | 82.8% | 1.86 | 0.258 | SL large |
| **4** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL800_co50` | $12,600 | 93 | 76.3% | 1.76 | 0.264 | SL serre |
| **5** | `b1320_zp20_cp30_adf64_zE3.5_TP1000_SL1200_co50` | $14,829 | 62 | 64.5% | 1.69 | 0.250 | ADF64 |

**Note** : Les configs 1-MIN n'ont pas ete validees en walk-forward ni Monte Carlo. Le mode dollar 1-MIN est considere **fragile** (MORT a 2 ticks slippage).

---

## Comparaison Timeframes

| Critere | 1-MIN (dollar) | 5-MIN (Z-Score) | Verdict |
|---------|---------------|-----------------|---------|
| Top PnL (backtest) | $111,583 (B4) | $45,224 (B2) | 1-MIN |
| PnL/Trade | $67 | $452 | **5-MIN** |
| Slippage resistance | MORT a 2 ticks | Breakeven 8 ticks | **5-MIN** |
| Walk-forward | Non teste | $20,553 (32-53% pos.) | **5-MIN** |
| Monte Carlo P(perte) | Non teste | 0.9% | **5-MIN** |
| **Recommandation** | -- | -- | **5-MIN** |

---

## Phase B Campaigns Summary

| Campaign | TF | Exit | Slip | Configs | Rent.(t>=80) | Top PnL | Verdict |
|----------|-----|------|------|---------|-------------|---------|---------|
| B1 | 5min | zscore | 2tick | 34,560 | 1,794 (5.2%) | $49,572 | GO |
| B2 | 5min | zscore | 1tick | 34,560 | 4,036 (15.8%) | $59,172 | **GO -- best** |
| B3 | 5min | hybrid | 2tick | 41,472 | 5,764 (13.9%) | $25,164 | NO-GO |
| B4 | 1min | dollar | 1tick | 9,720 | 1,945 (20.0%) | $111,583 | GO (fragile) |
| B5 | 1min | zscore | 1tick | 5,832 | 347 | $20,896 | Informative |
| B6 | 1min | dollar | 1tick | 86,400 | 1,342 (1.6%) | $53,642 | Dead end |

---

## Dead Ends (ne plus explorer)

| Approche | Raison | Reference |
|----------|--------|-----------|
| 1-min dollar 2 ticks | 0/32,400 configs rentables | Phase 3 grid |
| 1-min zp longs (48-264) | 1.6% rentable (86,400 configs) | B6 |
| Hybrid (zTP + dollar SL) | $25,164 top vs $59,172 B2 | B3 |
| Regime filter Half-life | Inutile seul (-$584) et en combo | C2b |
| Regime filter Correlation | Ne tient pas en OOS | C3 |
| Regime filter Hurst R/S | Structurellement >0.5 | C2 |
| HMM regime filter | Python-only, -$5K vs no filter | Pre-Phase B |

---

## Parametres Sierra Chart (a matcher)

| Parametre | Valeur |
|-----------|--------|
| Beta Lookback | 2640 |
| Z-Score Period | 20 |
| Correlation Period | 30 |
| ADF/Hurst Period | 26 |
| Z-Score Entry Upper | 3.5 |
| Z-Score Entry Lower | -3.5 |
| Z-Score TP Long | 1.0 (sort quand Z remonte a +1.0 = overshoot) |
| Z-Score TP Short | -1.0 (sort quand Z descend a -1.0 = overshoot) |
| Z-Score SL Long | -4.0 |
| Z-Score SL Short | 4.0 |
| Min Cointegration Score | 40 |
| Session Start | 17:00:00 CT |
| Session End | 15:30:00 CT |
| Dollar TP/SL | Disabled (99999/-99999) |
