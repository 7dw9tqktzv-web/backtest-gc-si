# Deep Analysis R2c - 10 Top Configs (Sharpe, trades>=80)

Date: 2026-02-14

## Configuration

Parametres fixes :
- Contract mode: micro
- Micro multiplier max: 2
- Slippage: 1 tick per leg
- zSL: -99/+99 (disabled)
- dSL: -99999 (disabled)
- max_holding_bars: 0 (disabled)
- flat_end_of_session: True

## A) Stabilite temporelle

| Config | Famille | Total | 2023 trades | 2023 PnL | 2024 trades | 2024 PnL | 2025 trades | 2025 PnL | 2026 trades | 2026 PnL | Annees+ |
|--------|---------|-------|-------------|----------|-------------|----------|-------------|----------|-------------|----------|---------|
| C1_b4620_zp30_cp27_adf160_dTP300 | B4620 Ultra Court | 139 | 45 | $5 | 50 | $608 | 34 | $2,627 | 10 | $2,804 | 4/4 |
| C2_b4620_zp30_cp27_adf160_dTP250 | B4620 Ultra Court | 139 | 45 | $5 | 50 | $608 | 34 | $2,327 | 10 | $2,304 | 4/4 |
| C3_b4290_zp33_cp30_adf128_dTP300 | B4290 Court | 106 | 31 | $22 | 42 | $343 | 24 | $1,791 | 9 | $2,523 | 4/4 |
| C4_b4290_zp33_cp33_adf112_dTP400 | B4290 Court | 100 | 29 | $-108 | 32 | $483 | 30 | $1,531 | 9 | $2,832 | 3/4 |
| C5_b4290_zp30_cp24_adf160_dTP300 | B4290 Court | 146 | 44 | $1,329 | 50 | $-104 | 40 | $2,806 | 12 | $3,364 | 3/4 |
| C6_b3960_zp33_cp27_adf144_dTP250 | B3960 Equilibre | 258 | 69 | $1,232 | 95 | $-45 | 70 | $4,494 | 24 | $6,123 | 3/4 |
| C7_b4290_zp30_cp24_adf96_dTP300 | B4290 Court | 130 | 34 | $-334 | 53 | $229 | 33 | $3,202 | 10 | $3,102 | 3/4 |
| C8_b4290_zp33_cp33_adf112_dTP350 | B4290 Court | 100 | 29 | $-108 | 32 | $483 | 30 | $1,481 | 9 | $2,432 | 3/4 |
| C9_b4620_zp30_cp30_adf96_dTP250 | B4620 Ultra Court | 174 | 51 | $887 | 63 | $-50 | 45 | $3,512 | 15 | $3,853 | 3/4 |
| C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250 | B4620 Ultra Court | 82 | 32 | $-697 | 31 | $156 | 16 | $1,339 | 3 | $691 | 3/4 |

### Detail par annee

**C1_b4620_zp30_cp27_adf160_dTP300** (B4620 Ultra Court)
  - 2023: 45 trades, PnL $5, WR 64.4%, avg $0.1
  - 2024: 50 trades, PnL $608, WR 68.0%, avg $12.2
  - 2025: 34 trades, PnL $2,627, WR 73.5%, avg $77.3
  - 2026: 10 trades, PnL $2,804, WR 100.0%, avg $280.4

**C2_b4620_zp30_cp27_adf160_dTP250** (B4620 Ultra Court)
  - 2023: 45 trades, PnL $5, WR 64.4%, avg $0.1
  - 2024: 50 trades, PnL $608, WR 68.0%, avg $12.2
  - 2025: 34 trades, PnL $2,327, WR 73.5%, avg $68.4
  - 2026: 10 trades, PnL $2,304, WR 100.0%, avg $230.4

**C3_b4290_zp33_cp30_adf128_dTP300** (B4290 Court)
  - 2023: 31 trades, PnL $22, WR 58.1%, avg $0.7
  - 2024: 42 trades, PnL $343, WR 73.8%, avg $8.2
  - 2025: 24 trades, PnL $1,791, WR 70.8%, avg $74.6
  - 2026: 9 trades, PnL $2,523, WR 100.0%, avg $280.4

**C4_b4290_zp33_cp33_adf112_dTP400** (B4290 Court)
  - 2023: 29 trades, PnL $-108, WR 55.2%, avg $-3.7
  - 2024: 32 trades, PnL $483, WR 62.5%, avg $15.1
  - 2025: 30 trades, PnL $1,531, WR 73.3%, avg $51.0
  - 2026: 9 trades, PnL $2,832, WR 88.9%, avg $314.7

**C5_b4290_zp30_cp24_adf160_dTP300** (B4290 Court)
  - 2023: 44 trades, PnL $1,329, WR 63.6%, avg $30.2
  - 2024: 50 trades, PnL $-104, WR 66.0%, avg $-2.1
  - 2025: 40 trades, PnL $2,806, WR 72.5%, avg $70.1
  - 2026: 12 trades, PnL $3,364, WR 100.0%, avg $280.4

**C6_b3960_zp33_cp27_adf144_dTP250** (B3960 Equilibre)
  - 2023: 69 trades, PnL $1,232, WR 55.1%, avg $17.9
  - 2024: 95 trades, PnL $-45, WR 66.3%, avg $-0.5
  - 2025: 70 trades, PnL $4,494, WR 68.6%, avg $64.2
  - 2026: 24 trades, PnL $6,123, WR 100.0%, avg $255.1

**C7_b4290_zp30_cp24_adf96_dTP300** (B4290 Court)
  - 2023: 34 trades, PnL $-334, WR 52.9%, avg $-9.8
  - 2024: 53 trades, PnL $229, WR 71.7%, avg $4.3
  - 2025: 33 trades, PnL $3,202, WR 84.8%, avg $97.0
  - 2026: 10 trades, PnL $3,102, WR 100.0%, avg $310.2

**C8_b4290_zp33_cp33_adf112_dTP350** (B4290 Court)
  - 2023: 29 trades, PnL $-108, WR 55.2%, avg $-3.7
  - 2024: 32 trades, PnL $483, WR 62.5%, avg $15.1
  - 2025: 30 trades, PnL $1,481, WR 73.3%, avg $49.4
  - 2026: 9 trades, PnL $2,432, WR 88.9%, avg $270.2

**C9_b4620_zp30_cp30_adf96_dTP250** (B4620 Ultra Court)
  - 2023: 51 trades, PnL $887, WR 58.8%, avg $17.4
  - 2024: 63 trades, PnL $-50, WR 68.3%, avg $-0.8
  - 2025: 45 trades, PnL $3,512, WR 77.8%, avg $78.1
  - 2026: 15 trades, PnL $3,853, WR 100.0%, avg $256.9

**C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250** (B4620 Ultra Court)
  - 2023: 32 trades, PnL $-697, WR 53.1%, avg $-21.8
  - 2024: 31 trades, PnL $156, WR 61.3%, avg $5.0
  - 2025: 16 trades, PnL $1,339, WR 68.8%, avg $83.7
  - 2026: 3 trades, PnL $691, WR 100.0%, avg $230.4

## B) Consistency mensuelle

| Config | Mois actifs | % actif | Mois positifs | % positif | Max losing streak | PnL moyen/mois | PnL median/mois |
|--------|-------------|---------|---------------|-----------|-------------------|----------------|-----------------|
| C1_b4620_zp30_cp27_adf160_dTP300 | 34/35 | 97.1% | 23 | 67.6% | 3 | $178 | $64 |
| C2_b4620_zp30_cp27_adf160_dTP250 | 34/35 | 97.1% | 23 | 67.6% | 3 | $154 | $64 |
| C3_b4290_zp33_cp30_adf128_dTP300 | 33/35 | 94.3% | 20 | 60.6% | 4 | $142 | $72 |
| C4_b4290_zp33_cp33_adf112_dTP400 | 31/35 | 88.6% | 20 | 64.5% | 3 | $153 | $69 |
| C5_b4290_zp30_cp24_adf160_dTP300 | 35/35 | 100.0% | 20 | 57.1% | 4 | $211 | $9 |
| C6_b3960_zp33_cp27_adf144_dTP250 | 36/36 | 100.0% | 26 | 72.2% | 4 | $328 | $178 |
| C7_b4290_zp30_cp24_adf96_dTP300 | 32/35 | 91.4% | 21 | 65.6% | 3 | $194 | $72 |
| C8_b4290_zp33_cp33_adf112_dTP350 | 31/35 | 88.6% | 20 | 64.5% | 3 | $138 | $69 |
| C9_b4620_zp30_cp30_adf96_dTP250 | 36/36 | 100.0% | 25 | 69.4% | 3 | $228 | $48 |
| C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250 | 32/36 | 88.9% | 18 | 56.2% | 4 | $46 | $22 |

## C) Analyse par type de sortie

### C1_b4620_zp30_cp27_adf160_dTP300 (B4620 Ultra Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 123 | $12.6 | $1,554 | 186 | -0.3 | -0.05 |
| TP_DOLLAR | 16 | $280.6 | $4,490 | 23 | -1.06 | -0.48 |

### C2_b4620_zp30_cp27_adf160_dTP250 (B4620 Ultra Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 123 | $12.6 | $1,554 | 186 | -0.3 | -0.05 |
| TP_DOLLAR | 16 | $230.6 | $3,690 | 22 | -1.06 | -0.44 |

### C3_b4290_zp33_cp30_adf128_dTP300 (B4290 Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 93 | $11.1 | $1,030 | 169 | -0.45 | -0.0 |
| TP_DOLLAR | 13 | $280.7 | $3,649 | 17 | -1.59 | -1.33 |

### C4_b4290_zp33_cp33_adf112_dTP400 (B4290 Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 91 | $14.4 | $1,311 | 151 | -0.57 | 0.04 |
| TP_DOLLAR | 9 | $380.8 | $3,427 | 8 | -0.64 | -0.31 |

### C5_b4290_zp30_cp24_adf160_dTP300 (B4290 Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 128 | $18.3 | $2,345 | 326 | -0.54 | -0.04 |
| TP_DOLLAR | 18 | $280.6 | $5,050 | 19 | -1.3 | -0.75 |

### C6_b3960_zp33_cp27_adf144_dTP250 (B3960 Equilibre)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 221 | $14.7 | $3,249 | 243 | -0.19 | -0.04 |
| TP_DOLLAR | 37 | $231.2 | $8,554 | 16 | -1.22 | -0.9 |

### C7_b4290_zp30_cp24_adf96_dTP300 (B4290 Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 114 | $15.0 | $1,705 | 166 | -0.63 | 0.03 |
| TP_DOLLAR | 16 | $280.8 | $4,494 | 12 | -0.98 | -0.51 |

### C8_b4290_zp33_cp33_adf112_dTP350 (B4290 Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 91 | $14.4 | $1,311 | 151 | -0.57 | 0.04 |
| TP_DOLLAR | 9 | $330.8 | $2,977 | 7 | -0.64 | -0.31 |

### C9_b4620_zp30_cp30_adf96_dTP250 (B4620 Ultra Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 148 | $14.9 | $2,206 | 257 | -0.47 | 0.02 |
| TP_DOLLAR | 26 | $230.7 | $5,997 | 17 | -0.97 | -0.66 |

### C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250 (B4620 Ultra Court)

| Exit Type | N | PnL avg | PnL total | Duree moy (min) | Z entry avg | Z exit avg |
|-----------|---|---------|-----------|-----------------|-------------|------------|
| TP_ZSCORE | 76 | $1.3 | $99 | 197 | 0.22 | -0.04 |
| TP_DOLLAR | 6 | $231.7 | $1,390 | 14 | -2.71 | -2.26 |

## D) Tableau comparatif final

| Config | Famille | Trades | WR | PnL | PF | DD | Sharpe | Calmar | Annees+ | Mois+ | Max lose streak | TP_Z avg$ | TP_$ avg$ | Duree moy |
|--------|---------|--------|----|-----|----|----|--------|--------|---------|-------|-----------------|-----------|-----------|-----------|
| C1_b4620_zp30_cp27_adf160_dTP300 | B4620 Ultra Court | 139 | 71% | $6,044 | 2.44 | $-1,147 | 4.9 | 1.87 | 4/4 | 67.6% | 3 | $13 | $281 | 168min |
| C2_b4620_zp30_cp27_adf160_dTP250 | B4620 Ultra Court | 139 | 71% | $5,244 | 2.25 | $-1,147 | 4.64 | 1.62 | 4/4 | 67.6% | 3 | $13 | $231 | 167min |
| C3_b4290_zp33_cp30_adf128_dTP300 | B4290 Court | 106 | 71% | $4,679 | 2.28 | $-861 | 4.53 | 1.91 | 4/4 | 60.6% | 4 | $11 | $281 | 151min |
| C4_b4290_zp33_cp33_adf112_dTP400 | B4290 Court | 100 | 66% | $4,738 | 2.24 | $-659 | 4.57 | 2.52 | 3/4 | 64.5% | 3 | $14 | $381 | 138min |
| C5_b4290_zp30_cp24_adf160_dTP300 | B4290 Court | 146 | 70% | $7,395 | 2.42 | $-881 | 4.54 | 2.98 | 3/4 | 57.1% | 4 | $18 | $281 | 288min |
| C6_b3960_zp33_cp27_adf144_dTP250 | B3960 Equilibre | 258 | 67% | $11,803 | 2.38 | $-965 | 4.48 | 4.23 | 3/4 | 72.2% | 4 | $15 | $231 | 210min |
| C7_b4290_zp30_cp24_adf96_dTP300 | B4290 Court | 130 | 72% | $6,198 | 2.36 | $-1,247 | 4.61 | 1.77 | 3/4 | 65.6% | 3 | $15 | $281 | 147min |
| C8_b4290_zp33_cp33_adf112_dTP350 | B4290 Court | 100 | 66% | $4,288 | 2.12 | $-659 | 4.46 | 2.28 | 3/4 | 64.5% | 3 | $14 | $331 | 138min |
| C9_b4620_zp30_cp30_adf96_dTP250 | B4620 Ultra Court | 174 | 71% | $8,203 | 2.38 | $-968 | 4.65 | 2.94 | 3/4 | 69.4% | 3 | $15 | $231 | 221min |
| C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250 | B4620 Ultra Court | 82 | 61% | $1,489 | 1.42 | $-858 | 2.06 | 0.61 | 3/4 | 56.2% | 4 | $1 | $232 | 184min |

## E) Classement par stabilite (annees positives)

Stability Score = nombre d'annees avec PnL positif (max 4)

| Rang | Config | Famille | Annees+ | 2023 | 2024 | 2025 | 2026 | PnL Total | Sharpe |
|------|--------|---------|---------|------|------|------|------|-----------|--------|
| 1 | C1_b4620_zp30_cp27_adf160_dTP300 | B4620 Ultra Court | 4/4 | + | + | + | + | $6,044 | 4.9 |
| 2 | C2_b4620_zp30_cp27_adf160_dTP250 | B4620 Ultra Court | 4/4 | + | + | + | + | $5,244 | 4.64 |
| 3 | C3_b4290_zp33_cp30_adf128_dTP300 | B4290 Court | 4/4 | + | + | + | + | $4,679 | 4.53 |
| 4 | C6_b3960_zp33_cp27_adf144_dTP250 | B3960 Equilibre | 3/4 | + | - | + | + | $11,803 | 4.48 |
| 5 | C9_b4620_zp30_cp30_adf96_dTP250 | B4620 Ultra Court | 3/4 | + | - | + | + | $8,203 | 4.65 |
| 6 | C5_b4290_zp30_cp24_adf160_dTP300 | B4290 Court | 3/4 | + | - | + | + | $7,395 | 4.54 |
| 7 | C7_b4290_zp30_cp24_adf96_dTP300 | B4290 Court | 3/4 | - | + | + | + | $6,198 | 4.61 |
| 8 | C4_b4290_zp33_cp33_adf112_dTP400 | B4290 Court | 3/4 | - | + | + | + | $4,738 | 4.57 |
| 9 | C8_b4290_zp33_cp33_adf112_dTP350 | B4290 Court | 3/4 | - | + | + | + | $4,288 | 4.46 |
| 10 | C10_b4620_zp33_cp36_adf160_zTP0.5_dTP250 | B4620 Ultra Court | 3/4 | - | + | + | + | $1,489 | 2.06 |

---
*Genere par deep_analysis_r2c.py*