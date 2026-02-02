# CHANGELOG.md

Historique des optimisations, resultats detailles et ameliorations du backtest GC/SI.

## [2026-02-02] Grid Search -- Phase 3: 3-year comprehensive, 2 ticks slippage

**Configs**: 32,400 | **Profitable**: 115 (0.4%)
Results: `output/grid_search_3y_phase1.csv`

### Top 10 by PnL Net

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |
| 6 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL800 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |
| 7 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL400 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 8 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL600 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 9 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL800 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 10 | b660_zp20_cp50_adf128_zE3.5_co60_TP400_SL800 | 17 | 41.2% | $358 | 1.39 | -$753 | 2.22 |

### Top 10 by Sharpe (min 10 trades)

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 2 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 5 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL400 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 6 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL600 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 7 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL800 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 8 | b660_zp20_cp50_adf128_zE3.5_co60_TP400_SL800 | 17 | 41.2% | $358 | 1.39 | -$753 | 2.22 |
| 9 | b660_zp20_cp20_adf128_zE3.5_co60_TP400_SL800 | 19 | 47.4% | $307 | 1.32 | -$947 | 1.86 |
| 10 | b3960_zp15_cp60_adf64_zE3.5_co50_TP400_SL800 | 11 | 36.4% | $190 | 1.32 | -$552 | 1.78 |

### Key Findings

- 115/32400 configs profitable (0.4%)
- Best PnL: $586 -- b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800
- zscore_entry=3.5 domine (97% des configs rentables)
- zscore_period=15 le plus frequent dans les rentables
- TP=$400 et SL=-$800 dominent les rentables
- Trades moyen: 3155 | median: 1176

## Grid Search Results (32,400 configs, 3 years, 2 ticks slippage)

Tested: 300 indicator groups x 108 entry/exit variants = 32,400 configs total.
- beta_lookback: 660, 1320, 1980, 2640, 3960
- zscore_period: 15, 20, 30, 50, 60
- correlation_period: 20, 30, 50
- adf_hurst_period: 64, 128, 256, 512
- zscore_entry: -2.5/+2.5, -3.0/+3.0, -3.5/+3.5
- cointegration_score_min: 40, 50, 60
- pnl_take_profit: 200, 300, 400
- pnl_stop_loss: -400, -600, -800, -1000

Run with 8 parallel workers (`multiprocessing.Pool`).
Results saved in `output/grid_search_3y_phase1.csv`.

### Key finding: strategy NOT viable with 2 ticks slippage

- **Only 115/32,400 configs profitable (0.4%)**
- **Best PnL: +$586 over 3 years** (nearly breakeven)
- Average cost per trade: ~$160-200 (2 ticks slippage doubles costs vs 1 tick)
- TP_ZSCORE exits lose money even with PnL floor >= $0

### Top 5 by PnL Net (3 years, 2 ticks)

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |

### Top 5 with 1 tick slippage (for comparison)

| # | Config | PnL 2tick | PnL 1tick | Delta |
|---|--------|-----------|-----------|-------|
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | +$586 | +$1,946 | +$1,360 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | +$531 | +$1,891 | +$1,360 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | +$446 | +$1,746 | +$1,300 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | +$446 | +$1,746 | +$1,300 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | +$437 | +$2,547 | +$2,110 |

## Grid Search Results (864 configs, 8 months, 1 tick slippage)

Tested: beta_lookback (1320/1980/2640/3960) x zscore_period (20/30) x correlation_period (30/60) x cointegration_score_min (40/50/60) x zscore_entry (-2.5/+2.5, -3.0/+3.0) x TP (200/300/400) x SL (-400/-600/-800)

### Top 5 by PnL Net

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | beta1320_zp20_cp30_co40_TP400_SL600 | 1,423 | 58.6% | $80,833 | 1.87 | -$20,632 | 3.79 |
| 2 | beta1320_zp20_cp30_co40_TP400_SL400 | 1,423 | 58.1% | $80,433 | 1.88 | -$20,962 | 3.93 |
| 3 | beta1320_zp20_cp30_co40_TP400_SL800 | 1,424 | 58.8% | $79,043 | 1.82 | -$20,417 | 3.56 |
| 4 | beta1980_zp20_cp30_co40_TP400_SL800 | 1,430 | 57.1% | $76,018 | 1.82 | -$23,205 | 3.56 |
| 5 | beta3960_zp30_cp60_co40_TP400_SL800 | 1,525 | 61.0% | $76,002 | 1.63 | -$25,300 | 2.83 |

### Top 5 by Sharpe (risk-adjusted)

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | beta2640_zp20_cp30_co60_zE3_TP200_SL400 | 31 | 90.3% | $2,549 | 6.61 | -$332 | 14.72 |
| 2 | beta2640_zp20_cp30_co50_zE3_TP200_SL400 | 146 | 84.9% | $10,459 | 5.09 | -$574 | 11.65 |
| 3 | beta3960_zp20_cp60_co60_zE3_TP200_SL400 | 39 | 79.5% | $2,408 | 4.63 | -$277 | 11.65 |
| 4 | beta2640_zp20_cp30_co50_zE3_TP200_SL600 | 146 | 84.9% | $10,259 | 4.72 | -$774 | 10.37 |
| 5 | beta2640_zp20_cp60_co60_zE3_TP200_SL400 | 33 | 84.8% | $2,293 | 4.58 | -$410 | 9.50 |

### Key conclusions (8 months)
- **PnL vs Sharpe trade-off**: zero configs in common between the two rankings
- High PnL requires loose filters (co=40, zE=-2.5) and TP=$400
- High Sharpe requires strict filters (co=50-60, zE=-3.0) and TP=$200
- SL value has minimal impact on top PnL configs (SL never hit on Sharpe configs)
- `beta1320` and `beta1980` dominate PnL; `beta2640` dominates Sharpe

## Previous Results (8-month data, 1 tick slippage)

Config: beta=1980, zp=20, cp=30, adf=128, cm=0.60, co=40, TP=$300, SL=-$600

- Trades: 1,473 (844 LONG, 629 SHORT)
- PnL net: +$71,428 | Win rate: 62.3%
- Profit Factor: 1.95 | Max Drawdown: -$20,639
- Sharpe: 4.25
- Two market regimes: May-Sept 2025 (unfavorable, TP_ZSCORE losses) / Oct 2025-Jan 2026 (very favorable)

## Walk-Forward Test (6 windows, 12 configs, 8 months)

6 rolling windows (30-day train / 15-day test), 12 configs tested per window, best selected on train PnL.

### Results per window (out-of-sample)

| # | Test Period | Config Selected | Trades | PnL | WR% | PF | MaxDD |
|---|-------------|-----------------|--------|-----|-----|-----|-------|
| 1 | Jul 18 - Aug 04 | Sh5 (zE3, TP200) | 10 | -$313 | 30% | 0.50 | -$543 |
| 2 | Aug 17 - Sep 28 | Sh5 (zE3, TP200) | 10 | -$4 | 50% | 0.99 | -$423 |
| 3 | Oct 10 - Oct 27 | Sh5 (zE3, TP200) | 17 | +$2,004 | 94% | 112 | $0 |
| 4 | Nov 09 - Nov 25 | PnL3 (TP300, SL600) | 183 | +$2,270 | 58% | 1.22 | -$2,414 |
| 5 | Dec 08 - Dec 24 | PnL3 (TP300, SL600) | 153 | +$9,245 | 70% | 1.89 | -$1,822 |
| 6 | Jan 06 - Jan 22 | PnL6 (TP400, SL800) | 201 | +$31,371 | 83% | 3.40 | -$1,715 |

### Summary
- **Total out-of-sample PnL**: +$44,573 (vs $43,903 in-sample)
- **Retention**: 203% of daily PnL (test > train)
- **Positive windows**: 4/6
- **Verdict**: Strategy is ROBUST out-of-sample, but regime-dependent
- Results saved in `output/walk_forward_results.csv`

## Optimization History

### Phase 1 -- 48-day data (606+ configs, Dec 2025 - Jan 2026)
1. **Etape 1 (22 configs)**: beta_lookback (660-7920) x zscore_period (15/20/30)
2. **Etape 2 (101 configs)**: top 5 indicators x TP (200-600) x SL (400-1200)
3. **Etape 3 (481 configs)**: 6 bases x correlation_period x adf_period x corr_min x coint_min
4. **Hurst filter (12 configs)**: zero impact (redundant with Cointegration Score)

### Phase 2 -- 8-month data (864 configs, May 2025 - Jan 2026)
- Full grid search with optimized grouping (16 indicator groups x 54 entry/exit variants)
- Walk-forward validation: 6 windows, 12 configs each, no overfitting detected
- Log saved in `output/optimization_log.csv` (batch_id="grid_8mois")

### Phase 3 -- 3-year data (32,400 configs, Jan 2023 - Jan 2026, 2 ticks slippage)
- Comprehensive grid search: 300 indicator groups x 108 entry/exit variants
- Run with multiprocessing (8 workers)
- **Result: only 0.4% of configs profitable, best PnL = $586 over 3 years**
- Results saved in `output/grid_search_3y_phase1.csv`
- Script: `run_grid_search_3y.py`

## Completed Improvements

- **Cointegration Score adaptive**: Reweights score proportionally when ADF/Hurst are NaN, instead of penalizing to 0.
- **ACSIL formula verification**: Confirmed Python matches ACSIL v1.4 for StdDev (ddof=1), Correlation (Pearson), and OLS Beta.
- **Hybrid backtest (1min + 5s)**: Dollar exits monitored on 5-second bars for precision. Full 5s approach was tested and rejected (too noisy).
- **Parquet cache**: Synchronized DataFrames cached in `data/processed/` for faster reloads. Invalidated by MD5 hash of source CSV files.
- **Multi-config optimizer**: `optimizer.py` loads data once and runs N backtest configs in a loop. Used by the /optimize skill for grid search.
- **Optimization logging**: `optimizer.py` auto-saves results to `output/optimization_log.csv` with batch IDs. Functions: save_results_to_log, load_log, print_log_summary, delete_batch, keep_top_n.
- **Hurst filter**: Independent `hurst_max` parameter in entry conditions (default 1.0 = disabled). Proven redundant with Cointegration Score on current data.
- **Config fingerprint validation**: `backtest_engine_hybrid.py` exports a `.meta.json` alongside the CSV. `metrics.py` validates config coherence before archiving.
- **Index deduplication**: `metrics.py` replaces existing index.csv entries with same Folder_Path + Days_Loaded instead of creating duplicates.
- **Code factorization**: `common.py` centralizes state constants and shared functions (check_entry_conditions, check_zscore_exit, check_cooldown_reset, calculate_current_pnl, build_config_fingerprint). Removed ~430 lines of duplicated code.
- **Hurst bug fix**: Both backtest engines now pass `hurst=hursts[i]` to check_entry_conditions (was silently ignored before). No impact with default hurst_max=1.0.
- **8-month data upgrade**: Extended from 48 days (GCG26) to 8 months (GCJ26, May 2025 - Jan 2026). Contract rollover handled.
- **Optimized grid search**: `run_grid_search.py` groups 864 configs into 16 indicator combinations, calculates indicators once per group, then loops 54 entry/exit variants.
- **Walk-forward validation**: `run_walk_forward.py` implements 6-window rolling walk-forward (30-day train / 15-day test). Confirmed no overfitting.
- **PnL floor on TP_ZSCORE**: `exit.zscore_tp_min_pnl` parameter in common.py. Only allows TP_ZSCORE exit if current PnL >= threshold (default $0). Tested but insufficient.
- **Slippage 2 ticks default**: `costs.slippage_gc_ticks` and `costs.slippage_si_ticks` set to 2 (was 1). Configurable via optimizer overrides.
- **Hour filter**: `session.entry_start_hour` and `session.entry_end_hour` in backtest_engine_hybrid.py. Blocks new entries outside configured hours (default 0-24 = disabled).
- **GC contracts cap**: `sizing.gc_contracts_max` in position.py. Caps maximum GC contracts per trade (default 0 = no cap).
- **Verbose parameter**: `calculate_all_indicators()` and `run_hybrid_backtest()` accept `verbose=False` to suppress print output during mass backtesting.
- **3-year data upgrade**: Extended from 8 months to 3 years (Jan 2023 - Jan 2026). 801,499 1-min bars, 4,604,839 5s bars.
- **Multiprocessing grid search**: `run_grid_search_3y.py` uses `mp.Pool(8)` for parallel backtesting. 32,400 configs.