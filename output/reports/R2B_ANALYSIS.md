# Grid Search R2b -- Comprehensive Analysis

Date: 2026-02-14

## Etape 1 -- Global Statistics

- **Total configs**: 2,916,000
- **Profitable (pnl_net > 0)**: 457,656 (15.7%)
- **Unprofitable**: 2,458,344 (84.3%)

### Trades distribution
- Min: 0, P25: 73, Median: 317, P75: 666, Max: 1888

### PnL distribution
- Min: $-55,206, P25: $-6,305, Median: $-2,158, P75: $0, Max: $22,571

## Etape 2 -- Elimination Filters

- Filter: max_dd >= -$5,000 AND trades >= 50 AND 1.2 <= PF < inf
- **Survivors**: 75,835 / 2,916,000 (2.60%)

## Etape 3 -- Scoring Rankings

### Scoring A -- Prop Firm (Sharpe 35% + MaxDD 25% + WinRate 25% + PF 15%)

|   rank | label                                                                       |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |   score |
|-------:|:----------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|--------:|
|      1 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2837.00 |            5.54 |  -169.00 |     0.40 |    16.83 |          49 |           3 |           0 |           0 |             0 |    0.89 |
|      2 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP400_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2537.00 |            5.06 |  -169.00 |     0.41 |    15.05 |          49 |           3 |           0 |           0 |             0 |    0.88 |
|      3 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP600_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2824.00 |            5.51 |  -169.00 |     0.39 |    16.75 |          50 |           2 |           0 |           0 |             0 |    0.88 |
|      4 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP300_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2355.00 |            4.76 |  -169.00 |     0.42 |    13.97 |          48 |           4 |           0 |           0 |             0 |    0.88 |
|      5 | b3300_zp18_cp10_adf256_zE3.5_co40_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |       50 |      60.00 |   2727.00 |            4.08 |  -332.00 |     0.46 |     8.21 |          42 |           8 |           0 |           0 |             0 |    0.87 |
|      6 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      67.30 |   3184.00 |            4.79 |  -524.00 |     0.39 |     6.07 |          49 |           3 |           0 |           0 |             0 |    0.87 |
|      7 | b3300_zp18_cp10_adf256_zE3.5_co40_zTP2.0_zSL99_dTP300_nodSL_feos_nohold_mm2 |       50 |      66.00 |   2416.00 |            3.81 |  -349.00 |     0.41 |     6.92 |          42 |           8 |           0 |           0 |             0 |    0.85 |
|      8 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP400_nodSL_feos_nohold_mm2  |       52 |      67.30 |   2592.00 |            4.09 |  -524.00 |     0.40 |     4.95 |          48 |           4 |           0 |           0 |             0 |    0.85 |
|      9 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2  |       52 |      67.30 |   2256.00 |            3.69 |  -524.00 |     0.41 |     4.30 |          47 |           5 |           0 |           0 |             0 |    0.85 |
|     10 | b1980_zp20_cp36_adf96_zE3.25_co50_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |       67 |      62.70 |   2331.00 |            3.98 |  -146.00 |     0.40 |    15.93 |          62 |           5 |           0 |           0 |             0 |    0.84 |

### Scoring B -- Volume (Trades 30% + WinRate 25% + Sharpe 20% + PF 15% + MaxDD 10%)

|   rank | label                                                                       |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |   score |
|-------:|:----------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|--------:|
|      1 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2837.00 |            5.54 |  -169.00 |     0.40 |    16.83 |          49 |           3 |           0 |           0 |             0 |    0.61 |
|      2 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP600_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2824.00 |            5.51 |  -169.00 |     0.39 |    16.75 |          50 |           2 |           0 |           0 |             0 |    0.61 |
|      3 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      67.30 |   3184.00 |            4.79 |  -524.00 |     0.39 |     6.07 |          49 |           3 |           0 |           0 |             0 |    0.60 |
|      4 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP400_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2537.00 |            5.06 |  -169.00 |     0.41 |    15.05 |          49 |           3 |           0 |           0 |             0 |    0.60 |
|      5 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP300_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2355.00 |            4.76 |  -169.00 |     0.42 |    13.97 |          48 |           4 |           0 |           0 |             0 |    0.60 |
|      6 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP400_nodSL_feos_nohold_mm2  |       52 |      67.30 |   2592.00 |            4.09 |  -524.00 |     0.40 |     4.95 |          48 |           4 |           0 |           0 |             0 |    0.58 |
|      7 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP600_nodSL_feos_nohold_mm2  |       52 |      67.30 |   2969.00 |            4.54 |  -524.00 |     0.36 |     5.66 |          50 |           2 |           0 |           0 |             0 |    0.58 |
|      8 | b3300_zp18_cp10_adf256_zE3.5_co40_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |       50 |      60.00 |   2727.00 |            4.08 |  -332.00 |     0.46 |     8.21 |          42 |           8 |           0 |           0 |             0 |    0.58 |
|      9 | b3300_zp18_cp10_adf256_zE3.5_co40_zTP2.0_zSL99_dTP300_nodSL_feos_nohold_mm2 |       50 |      66.00 |   2416.00 |            3.81 |  -349.00 |     0.41 |     6.92 |          42 |           8 |           0 |           0 |             0 |    0.58 |
|     10 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2  |       52 |      67.30 |   2256.00 |            3.69 |  -524.00 |     0.41 |     4.30 |          47 |           5 |           0 |           0 |             0 |    0.58 |

### Scoring C -- Aggressive (PnL 35% + Calmar 25% + PF 20% + Sharpe 20%)

|   rank | label                                                                       |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |   score |
|-------:|:----------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|--------:|
|      1 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2837.00 |            5.54 |  -169.00 |     0.40 |    16.83 |          49 |           3 |           0 |           0 |             0 |    0.67 |
|      2 | b9900_zp60_cp10_adf256_zE3.0_co50_zTP0.0_zSL99_dTP800_nodSL_feos_nohold_mm2 |      390 |      64.10 |  18368.00 |            1.69 | -3106.00 |     0.17 |     5.91 |         368 |          22 |           0 |           0 |             0 |    0.67 |
|      3 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP600_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2824.00 |            5.51 |  -169.00 |     0.39 |    16.75 |          50 |           2 |           0 |           0 |             0 |    0.66 |
|      4 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP400_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2537.00 |            5.06 |  -169.00 |     0.41 |    15.05 |          49 |           3 |           0 |           0 |             0 |    0.65 |
|      5 | b9900_zp60_cp10_adf64_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      806 |      62.30 |  19434.00 |            1.41 | -4399.00 |     0.09 |     4.42 |         772 |          34 |           0 |           0 |             0 |    0.64 |
|      6 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP1.5_zSL99_dTP500_nodSL_feos_nohold_mm2  |       52 |      67.30 |   3184.00 |            4.79 |  -524.00 |     0.39 |     6.07 |          49 |           3 |           0 |           0 |             0 |    0.64 |
|      7 | b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP300_nodSL_feos_nohold_mm2  |       52 |      61.50 |   2355.00 |            4.76 |  -169.00 |     0.42 |    13.97 |          48 |           4 |           0 |           0 |             0 |    0.63 |
|      8 | b9900_zp60_cp20_adf26_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      741 |      64.10 |  18609.00 |            1.46 | -3482.00 |     0.11 |     5.34 |         714 |          27 |           0 |           0 |             0 |    0.63 |
|      9 | b3300_zp18_cp10_adf256_zE3.5_co40_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |       50 |      60.00 |   2727.00 |            4.08 |  -332.00 |     0.46 |     8.21 |          42 |           8 |           0 |           0 |             0 |    0.63 |
|     10 | b5280_zp15_cp36_adf96_zE3.0_co50_zTP1.5_zSL99_dTP400_nodSL_feos_nohold_mm2  |       68 |      52.90 |   3203.00 |            4.87 |  -316.00 |     0.35 |    10.13 |          62 |           6 |           0 |           0 |             0 |    0.62 |


## Etape 4 -- Cross Analyses

### 4a. Beta Regime

| regime   |   count |   avg_trades |   avg_sharpe |   avg_wr |   avg_pnl |
|:---------|--------:|-------------:|-------------:|---------:|----------:|
| Court    |    9617 |       125.38 |         0.10 |    50.58 |   1935.47 |
| Moyen    |   22108 |       110.44 |         0.12 |    53.89 |   1965.42 |
| Long     |   44110 |       197.84 |         0.09 |    58.01 |   3240.33 |

### 4b. Cointegration Score (co) Breakdown

|    co |    count |   avg_sharpe |   avg_trades |   avg_pnl |
|------:|---------:|-------------:|-------------:|----------:|
| 10.00 | 13965.00 |         0.10 |       155.75 |   2541.78 |
| 20.00 | 15043.00 |         0.10 |       162.83 |   2692.16 |
| 30.00 | 15393.00 |         0.10 |       183.39 |   3022.73 |
| 40.00 | 12902.00 |         0.09 |       157.59 |   2578.49 |
| 50.00 | 18532.00 |         0.09 |       156.14 |   2655.15 |

### 4c. zTP x Beta Regime -- Avg Sharpe

|   zTP |   Court |   Moyen |   Long |
|------:|--------:|--------:|-------:|
|  0.00 |    0.10 |    0.12 |   0.09 |
|  0.50 |    0.09 |    0.11 |   0.08 |
|  1.00 |    0.09 |    0.11 |   0.08 |
|  1.50 |    0.10 |    0.13 |   0.10 |
|  2.00 |    0.10 |    0.11 |   0.09 |

### 4d. dTP Breakdown

|    dTP |    count |   avg_sharpe |   avg_pnl |   avg_trades |
|-------:|---------:|-------------:|----------:|-------------:|
|   0.00 |  4803.00 |         0.08 |   2030.56 |        97.61 |
| 300.00 | 21997.00 |         0.11 |   2505.77 |       170.34 |
| 400.00 | 14597.00 |         0.10 |   2880.75 |       180.53 |
| 500.00 | 12614.00 |         0.09 |   2842.93 |       169.82 |
| 600.00 | 10702.00 |         0.09 |   2634.44 |       151.07 |
| 800.00 | 11122.00 |         0.09 |   3058.70 |       158.62 |

#### dTP x Beta Regime -- Avg Sharpe

|    dTP |   Court |   Moyen |   Long |
|-------:|--------:|--------:|-------:|
|   0.00 |    0.07 |    0.10 |   0.08 |
| 300.00 |    0.11 |    0.15 |   0.10 |
| 400.00 |    0.10 |    0.11 |   0.09 |
| 500.00 |    0.09 |    0.10 |   0.08 |
| 600.00 |    0.09 |    0.11 |   0.08 |
| 800.00 |    0.08 |    0.11 |   0.08 |

#### dTP x Beta Regime -- Avg PnL

|    dTP |   Court |   Moyen |    Long |
|-------:|--------:|--------:|--------:|
|   0.00 | 1523.03 | 1609.50 | 2221.93 |
| 300.00 | 1879.26 | 2194.25 | 2828.26 |
| 400.00 | 1806.19 | 1847.38 | 3595.45 |
| 500.00 | 1838.98 | 1797.23 | 3759.74 |
| 600.00 | 2232.88 | 1850.45 | 3308.07 |
| 800.00 | 2127.47 | 2178.31 | 3451.77 |

### 4e. High-Volume Profitable Configs

- Configs with trades > 100 AND PF > 1.5: **4,484**

Top 5 by Sharpe:

| label                                                                       |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |
|:----------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|
| b9900_zp48_cp60_adf48_zE3.5_co50_zTP0.5_zSL99_dTP300_nodSL_feos_nohold_mm2  |      125 |      70.40 |   5998.00 |            2.56 |  -792.00 |     0.34 |     7.58 |         108 |          17 |           0 |           0 |             0 |
| b9900_zp48_cp60_adf48_zE3.5_co50_zTP0.0_zSL99_dTP300_nodSL_feos_nohold_mm2  |      125 |      72.80 |   6738.00 |            2.38 |  -699.00 |     0.32 |     9.64 |         107 |          18 |           0 |           0 |             0 |
| b9900_zp48_cp60_adf48_zE3.5_co50_zTP0.5_zSL99_dTP400_nodSL_feos_nohold_mm2  |      125 |      69.60 |   6446.00 |            2.47 |  -792.00 |     0.31 |     8.14 |         111 |          14 |           0 |           0 |             0 |
| b2640_zp20_cp10_adf128_zE3.5_co30_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |      118 |      53.40 |   4613.00 |            2.50 |  -741.00 |     0.30 |     6.22 |         100 |          18 |           0 |           0 |             0 |
| b9900_zp48_cp60_adf48_zE3.5_co50_zTP0.0_zSL99_dTP400_nodSL_feos_nohold_mm2  |      125 |      72.00 |   7387.00 |            2.38 |  -699.00 |     0.30 |    10.57 |         111 |          14 |           0 |           0 |             0 |

### 4f. zE Breakdown

|   zE |    count |   avg_trades |   avg_sharpe |   avg_pnl |
|-----:|---------:|-------------:|-------------:|----------:|
| 2.75 |  4252.00 |       206.92 |         0.08 |   2490.44 |
| 3.00 |  6320.00 |       211.68 |         0.09 |   3252.03 |
| 3.25 | 13326.00 |       167.60 |         0.08 |   2378.56 |
| 3.50 | 51937.00 |       152.55 |         0.10 |   2737.11 |


## Etape 5 -- Comparison with R1/R2a Baselines

### R1 Baseline (b2640_zE3.5_co20_zTP1.5_dTP300)

| label                                                                      |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |
|:---------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|
| b2640_zp20_cp30_adf26_zE3.5_co20_zTP1.5_zSL99_dTP300_nodSL_feos_nohold_mm2 |      122 |      49.20 |   3137.00 |            1.95 | -1114.00 |     0.20 |     2.82 |         106 |          16 |           0 |           0 |             0 |

### R2a Best (b2640_zE3.5_co40_zTP0.0_dTP800)

| label                                                                      |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |
|:---------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|------------:|------------:|------------:|------------:|--------------:|
| b2640_zp20_cp30_adf26_zE3.5_co40_zTP0.0_zSL99_dTP800_nodSL_feos_nohold_mm2 |       60 |      55.00 |   3755.00 |            2.36 | -1237.00 |     0.24 |     3.04 |          57 |           3 |           0 |           0 |             0 |

### Top 1 from each scoring (for comparison)

- **A-PropFirm**: b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2 | trades=52 | PnL=$2,837 | PF=5.54 | DD=$-169 | Sharpe=0.400
- **B-Volume**: b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2 | trades=52 | PnL=$2,837 | PF=5.54 | DD=$-169 | Sharpe=0.400
- **C-Aggressive**: b1980_zp24_cp30_adf96_zE3.5_co50_zTP2.0_zSL99_dTP500_nodSL_feos_nohold_mm2 | trades=52 | PnL=$2,837 | PF=5.54 | DD=$-169 | Sharpe=0.400


================================================================================
SCORING D ANALYSIS - HIGH RISK (DD TOLERANT)
================================================================================

## Elimination Filters

- max_dd >= -8000 (tolerates up to -$8K drawdown)
- trades >= 50
- profit_factor >= 1.1 AND profit_factor < inf

## Results

**Survivors**: 156268 / 2916000 (5.36%)

## Top 10 Configs (Deduplicated)

|   rank | label                                                                       |   trades |   win_rate |   pnl_net |   profit_factor |   max_dd |   sharpe |   calmar |   score_d |   tp_zscore |   tp_dollar |   sl_zscore |   sl_dollar |   end_session |
|-------:|:----------------------------------------------------------------------------|---------:|-----------:|----------:|----------------:|---------:|---------:|---------:|----------:|------------:|------------:|------------:|------------:|--------------:|
|      1 | b9900_zp60_cp10_adf256_zE3.0_co50_zTP0.0_zSL99_dTP800_nodSL_feos_nohold_mm2 |      390 |       64.1 |     18368 |            1.69 |    -3106 |     0.17 |     5.91 |  0.675925 |         368 |          22 |           0 |           0 |             0 |
|      2 | b9900_zp60_cp10_adf64_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      806 |       62.3 |     19434 |            1.41 |    -4399 |     0.09 |     4.42 |  0.649827 |         772 |          34 |           0 |           0 |             0 |
|      3 | b7920_zp60_cp20_adf26_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      714 |       62   |     19597 |            1.48 |    -5682 |     0.11 |     3.45 |  0.646142 |         686 |          28 |           0 |           0 |             0 |
|      4 | b9900_zp60_cp20_adf26_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      741 |       64.1 |     18609 |            1.46 |    -3482 |     0.11 |     5.34 |  0.645342 |         714 |          27 |           0 |           0 |             0 |
|      5 | b9900_zp60_cp24_adf128_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2 |      763 |       64.2 |     19175 |            1.42 |    -5190 |     0.09 |     3.69 |  0.643975 |         730 |          33 |           0 |           0 |             0 |
|      6 | b9900_zp60_cp20_adf26_zE2.75_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2 |     1032 |       62.2 |     21729 |            1.36 |    -7067 |     0.08 |     3.07 |  0.641364 |         988 |          44 |           0 |           0 |             0 |
|      7 | b9900_zp60_cp10_adf26_zE3.0_co30_zTP0.5_zSL99_dTP800_nodSL_feos_nohold_mm2  |      782 |       62.8 |     18744 |            1.42 |    -5265 |     0.1  |     3.56 |  0.631468 |         751 |          31 |           0 |           0 |             0 |
|      8 | b9900_zp60_cp10_adf256_zE3.0_co50_zTP0.0_zSL99_dTP600_nodSL_feos_nohold_mm2 |      392 |       64.5 |     16271 |            1.62 |    -3106 |     0.16 |     5.24 |  0.630214 |         364 |          28 |           0 |           0 |             0 |
|      9 | b7920_zp60_cp20_adf26_zE3.0_co30_zTP0.0_zSL99_dTP600_nodSL_feos_nohold_mm2  |      705 |       60.9 |     18500 |            1.4  |    -5136 |     0.1  |     3.6  |  0.629071 |         660 |          45 |           0 |           0 |             0 |
|     10 | b3960_zp36_cp20_adf26_zE3.0_co30_zTP0.0_zSL99_dTP600_nodSL_feos_nohold_mm2  |      793 |       62.2 |     19317 |            1.46 |    -6027 |     0.11 |     3.21 |  0.623526 |         753 |          40 |           0 |           0 |             0 |

## Scoring Formula

```
Score_D = 0.40 * PnL_norm + 0.25 * Calmar_norm + 0.20 * Sharpe_norm + 0.15 * PF_norm
```

- All metrics normalized 0-1 (min-max) within filtered set
- Calmar capped at P99 = 3.7100 to mitigate outliers
- Higher PnL, Calmar, Sharpe, and PF are better

