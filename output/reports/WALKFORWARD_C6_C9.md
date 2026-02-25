# Walk-Forward Validation C6 vs C9 + Investigation Regime 2024

Date: 2026-02-14

## Configuration

**C6**: beta=3960, zp=33, cp=27, adf=144, zE=3.25, co=45, zTP=0.0, dTP=250

**C9**: beta=4620, zp=30, cp=30, adf=96, zE=3.5, co=40, zTP=0.0, dTP=250

Parametres fixes (identiques pour les deux):
- Contract mode: micro
- Micro multiplier max: 2
- Slippage: 1 tick per leg
- zSL: -99/+99 (disabled)
- dSL: -99999 (disabled)
- max_holding_bars: 0 (disabled)
- flat_end_of_session: True

# PART 1: WALK-FORWARD VALIDATION

## Schema des fenetres (anchored expanding)

```
Window 1:
  Train: 2023-01-01 to 2024-01-01
  Test:  2024-01-01 to 2024-07-01
Window 2:
  Train: 2023-01-01 to 2024-07-01
  Test:  2024-07-01 to 2025-01-01
Window 3:
  Train: 2023-01-01 to 2025-01-01
  Test:  2025-01-01 to 2025-07-01
Window 4:
  Train: 2023-01-01 to 2025-07-01
  Test:  2025-07-01 to 2026-01-01
Window 5:
  Train: 2023-01-01 to 2026-01-01
  Test:  2026-01-01 to 2026-03-01
```

## Resultats par fenetre

### C6

| Window | Train PnL | Test Trades | Test PnL | Test WR | Test PF | Profitable |
|--------|-----------|-------------|----------|---------|---------|------------|
| 1 | $1,232 | 49 | $147 | 65% | 1.08 | YES |
| 2 | $1,379 | 46 | $-192 | 67% | 0.91 | NO |
| 3 | $1,187 | 32 | $1,235 | 59% | 1.84 | YES |
| 4 | $2,421 | 38 | $3,259 | 76% | 4.00 | YES |
| 5 | $5,681 | 24 | $6,123 | 100% | inf | YES |

### C9

| Window | Train PnL | Test Trades | Test PnL | Test WR | Test PF | Profitable |
|--------|-----------|-------------|----------|---------|---------|------------|
| 1 | $887 | 30 | $-541 | 60% | 0.64 | NO |
| 2 | $346 | 33 | $492 | 76% | 1.39 | YES |
| 3 | $838 | 15 | $1,088 | 87% | 5.40 | YES |
| 4 | $1,926 | 30 | $2,424 | 73% | 2.71 | YES |
| 5 | $4,350 | 15 | $3,853 | 100% | inf | YES |

## Agregats OOS (Out-of-Sample)

| Config | Windows Profitable | Cumul OOS PnL | OOS Sharpe | First 2 Avg | Last 2 Avg | Degradation |
|--------|--------------------|---------------|------------|-------------|------------|-------------|
| C6 | 4/5 (80%) | $10,571 | 1.14 | $-22 | $4,691 | +20948.7% |
| C9 | 4/5 (80%) | $7,316 | 1.21 | $-25 | $3,139 | +12726.5% |

# PART 2: INVESTIGATION REGIME 2024

## A) Trades par mois en 2024

### C6

| Month | Trades | PnL |
|-------|--------|-----|
| 2024-01 | 10.0 | $-153 |
| 2024-02 | 10.0 | $61 |
| 2024-03 | 7.0 | $184 |
| 2024-04 | 11.0 | $137 |
| 2024-05 | 5.0 | $14 |
| 2024-06 | 6.0 | $-95 |
| 2024-07 | 11.0 | $-206 |
| 2024-08 | 6.0 | $-120 |
| 2024-09 | 8.0 | $-277 |
| 2024-10 | 10.0 | $330 |
| 2024-11 | 7.0 | $-91 |
| 2024-12 | 4.0 | $171 |

### C9

| Month | Trades | PnL |
|-------|--------|-----|
| 2024-01 | 4.0 | $-331 |
| 2024-02 | 6.0 | $-274 |
| 2024-03 | 5.0 | $61 |
| 2024-04 | 9.0 | $53 |
| 2024-05 | 4.0 | $-95 |
| 2024-06 | 2.0 | $44 |
| 2024-07 | 5.0 | $-93 |
| 2024-08 | 6.0 | $244 |
| 2024-09 | 4.0 | $30 |
| 2024-10 | 10.0 | $-1 |
| 2024-11 | 4.0 | $132 |
| 2024-12 | 4.0 | $179 |

## B) Losing trades en 2024

| Config | Count | Avg Entry ZScore (abs) | Avg Duration (min) | Exit Type Breakdown |
|--------|-------|------------------------|--------------------|--------------------|
| C6 | 32 | 3.71 | 187 | TP_ZSCORE=32 |
| C9 | 20 | 3.89 | 171 | TP_ZSCORE=20 |

## C) Spread volatility par annee (std daily changes)

| Config | 2023 | 2024 | 2025 | 2026 |
|--------|------|------|------|------|
| C6 | 0.01 | 0.01 | 0.02 | 0.04 |
| C9 | 0.01 | 0.01 | 0.02 | 0.04 |

## D) ADF stationarity par annee (avg ADF_Statistic)

| Config | 2023 | 2024 | 2025 | 2026 |
|--------|------|------|------|------|
| C6 | -1.74 | -1.69 | -1.64 | -1.68 |
| C9 | -1.75 | -1.71 | -1.68 | -1.67 |

---
*Genere par walkforward_c6_c9.py*