# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.4).

## Commands

```bash
# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Test modules
python src/data_loader.py
python src/indicators.py
python src/signals.py
python src/position.py

# Run backtests
python src/backtest_engine.py          # 1-min with High/Low dollar exits
python src/backtest_engine_hybrid.py   # Hybrid 1-min + 5s (recommended)
python src/metrics.py                  # Performance analysis + archiving

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

### Data Pipeline
```
Sierra Chart CSV -> data_loader.py -> [Parquet cache] -> indicators.py -> signals.py -> position.py -> backtest_engine.py -> metrics.py
                      (sync GC/SI)    (data/processed/)   (calculate)    (generate)      (sizing)      (simulate)           (analyze)

Sierra Chart 5s CSV -> data_loader_5s.py -> [Parquet cache] -> backtest_engine_hybrid.py
                         (sync 5s)          (data/processed/)    (hybrid simulation)

optimizer.py: loads data once -> loops N configs -> calculate_all_indicators -> run_hybrid_backtest -> comparison table
```

### Module Status
| Module | Status | Purpose |
|--------|--------|---------|
| `common.py` | Complete | Shared state constants and utility functions (entry/exit/cooldown/PnL) |
| `data_loader.py` | Complete | Load/sync GC & SI 1-min data from Sierra Chart exports |
| `data_loader_5s.py` | Complete | Load/sync GC & SI 5-second data from Sierra Chart exports |
| `indicators.py` | Complete | Calculate Beta, Spread, Z-Score, Correlation, ADF, Hurst |
| `signals.py` | Complete | State machine for entry/exit signals (Z-Score based) |
| `position.py` | Complete | Position sizing (dollar neutral with Beta) + PnL calculation |
| `backtest_engine.py` | Complete | Trade simulation with High/Low intra-bar dollar exits |
| `backtest_engine_hybrid.py` | Complete | Hybrid backtest: 1-min signals + 5s dollar exits |
| `metrics.py` | Complete | Performance analysis (10 sections) + archiving |
| `optimizer.py` | Complete | Multi-config backtester (load once, test N configs) |

### Key Entry Points
- `load_and_prepare_data()` in `data_loader.py` - returns `(df, config, stats)`
- `load_5s_data(config)` in `data_loader_5s.py` - returns df_5s synchronized
- `calculate_all_indicators(df, config)` in `indicators.py` - returns df with all indicators
- `generate_signals(df, config)` in `signals.py` - returns df with Signal, Exit_Signal, Exit_Reason, State columns
- `build_trade_list(df)` in `signals.py` - returns a DataFrame with one row per trade
- `export_trade_list(trades_df, filepath)` in `signals.py` - exports trades to CSV
- `calculate_position_size(gc_price, si_price, beta, config)` in `position.py` - returns sizing dict
- `calculate_transaction_costs(gc_contracts, si_contracts, config)` in `position.py` - returns costs dict
- `calculate_trade_pnl(direction, entry_gc, entry_si, exit_gc, exit_si, gc_contracts, si_contracts, config)` in `position.py` - returns PnL dict
- `run_backtest(df, config)` in `backtest_engine.py` - returns trades DataFrame (1-min High/Low)
- `run_hybrid_backtest(df_1min, df_5s, config)` in `backtest_engine_hybrid.py` - returns trades DataFrame (hybrid)
- `run_metrics()` in `metrics.py` - analyzes backtest results, generates report + equity curve, archives everything
- `run_optimization(configs_list)` in `optimizer.py` - loads data once, runs N backtests, returns comparison table
- `apply_overrides(config, overrides)` in `optimizer.py` - applies dotted-key overrides to config dict

### Configuration
All parameters are in `config/strategy_params.yaml`. Never hardcode values.
Key field: `indicators.period` defines the calculation timeframe (1min, 5min, 15min, 1h, 1d).

### Archiving Structure
```
output/archive/
  index.csv                                          <- Global index of all runs
  {period}/                                          <- Indicator calculation period (1min, 5min, etc.)
    beta{N}_zp{N}_corr{N}_adf{N}/                   <- Indicator parameters
      zE{N}_{N}_zTP{N}_{N}_zSL{N}_{N}_TP{N}_SL{N}_corr{N}_coint{N}/
        backtest_hybrid.csv                          <- Trade list copy
        metrics_report.txt                           <- Full performance report
        equity_curve.png                             <- Equity + underwater chart
        params_snapshot.yaml                         <- Config snapshot
```

## Trading Logic

### State Machine (signals.py)
```
FLAT (0)  -> LONG (1) or SHORT (-1)     [entry conditions met]
LONG      -> FLAT                        [TP Z-Score: Z >= -2.0]
LONG      -> COOLDOWN_LONG (2)           [SL Z-Score: Z <= -3.5]
SHORT     -> FLAT                        [TP Z-Score: Z <= +2.0]
SHORT     -> COOLDOWN_SHORT (-2)         [SL Z-Score: Z >= +3.5]
COOLDOWN_LONG  -> FLAT                   [Z >= -1.0]
COOLDOWN_SHORT -> FLAT                   [Z <= +1.0]
```

### Entry Conditions
- LONG spread: Z-Score <= -2.5, Correlation > 0.60, Cointegration Score >= 40, Hurst < hurst_max
- SHORT spread: Z-Score >= 2.5, Correlation > 0.60, Cointegration Score >= 40, Hurst < hurst_max
- Note: hurst_max = 1.0 disables the filter (default). Set to 0.50 for strict mean reversion filtering.
- Note: correlation_min has no practical impact (always > 0.80 when other conditions are met)
- Note: Hurst filter is redundant with Cointegration Score (Hurst < 0.45 on all traded bars)

### Exit Conditions (OR logic)
| Condition | LONG | SHORT |
|-----------|------|-------|
| TP Z-Score | >= -2.0 | <= +2.0 |
| SL Z-Score | <= -3.5 | >= +3.5 |
| TP Dollars | +$300 | +$300 |
| SL Dollars | -$600 | -$600 |

### Key Rules
- After take profit: immediate re-entry allowed if conditions met
- After stop loss: cooldown until Z-Score returns to +/-1.0 (direction-specific)
- Cooldown only blocks same direction (COOLDOWN_LONG blocks LONG, not SHORT)
- Reversal allowed: close LONG and open SHORT on same bar
- Exit priority: SL_DOLLAR > SL_ZSCORE > TP_DOLLAR > TP_ZSCORE
- Single position at a time
- Dollar-based exits (TP $300 / SL -$600) handled in backtest engines, not signals.py

## Backtest Engines

### backtest_engine.py (1-min with High/Low)
- Iterates on 1-minute bars
- Dollar exits use High/Low prices to detect intra-bar SL/TP triggers
- When SL/TP dollar triggered, PnL is fixed at the threshold (-$600 or +$300)
- Z-Score exits use Last price

### backtest_engine_hybrid.py (Hybrid 1-min + 5s) -- RECOMMENDED
- Indicators and signals computed on 1-minute bars (normal lookbacks)
- When in position, scans 5-second bars between consecutive 1-min bars
- Dollar exits (SL/TP) detected on 5s Last prices (more precise than High/Low)
- Z-Score exits checked on 1-min bars only (after 5s scan finds no dollar trigger)
- PnL fixed at threshold when dollar exit triggers
- 5s data used ONLY for price monitoring, no indicators recalculated on 5s

#### Hybrid exit priority per 1-min bar:
```
1a. Scan 5s bars: SL_DOLLAR (-$600) -> break
1a. Scan 5s bars: TP_DOLLAR (+$300) -> break
1b. If no 5s trigger: SL_ZSCORE on 1-min Z-Score
1b. If no 5s trigger: TP_ZSCORE on 1-min Z-Score
```

## Contract Specifications

| Contract | Point Value | Tick Size | Tick Value |
|----------|-------------|-----------|------------|
| GC (Gold) | $100 | $0.10 | $10 |
| SI (Silver) | $5000 | $0.005 | $25 |

Commission: $4.00 round-trip per contract ($2.00 per side). Slippage: 2 ticks per leg (default, configurable via overrides).

## DataFrame Columns

After `calculate_all_indicators()`:
- Prices: `Last_GC`, `Last_SI`, `Log_GC`, `Log_SI`
- Regression: `Beta`, `Alpha`
- Spread: `Spread`, `Spread_Mean`, `Spread_Std`, `ZScore`
- Quality: `Correlation`, `ADF_Statistic`, `Hurst`, `HalfLife`, `Cointegration_Score`

After `generate_signals()`:
- Signals: `Signal` (1=LONG, -1=SHORT, 0=none), `Exit_Signal` (1=exit), `Exit_Reason` (TP_ZSCORE/SL_ZSCORE), `State`

## Conventions

- Code in English, comments in French
- Timezone: Chicago Time (CT)
- Session: 17:30 - 15:00 CT
- User level: Python beginner, Sierra Chart expert
- Approach: Pedagogical, step-by-step with explanations
- No emojis or accented characters in print() statements (Windows cp1252 terminal)

## Position Sizing (position.py)

### Dollar Neutral with Beta (ACSIL v1.4 formula)
```
NotionalGC = GC_price × $100
NotionalSI = SI_price × $5000
GC_contracts = round( (NotionalSI / NotionalGC) × Beta ) , minimum 1
```

### Key Observations
- Beta varies from ~0.03 to ~6.3 on traded bars -> GC contracts range from 1 to 6
- Dollar-based exits (TP/SL $) in backtest engines limit large losses from high-contract trades

## Data

- **Source**: Sierra Chart CSV exports (GCJ26 Gold futures, SIH26 Silver futures)
- **Period**: 2023-01-26 to 2026-01-30 (~3 years, 760+ trading days)
- **1-min bars**: 801,499 synchronized
- **5s bars**: 4,604,839 synchronized
- **Parquet cache**: `data/processed/` (auto-invalidated by MD5 hash)
- **Previous dataset**: 8 months (May 2025 - Jan 2026, 186,639 1-min bars)

## Previous Results (8-month data, 1 tick slippage)

Config: beta=1980, zp=20, cp=30, adf=128, cm=0.60, co=40, TP=$300, SL=-$600

- Trades: 1,473 (844 LONG, 629 SHORT)
- PnL net: +$71,428 | Win rate: 62.3%
- Profit Factor: 1.95 | Max Drawdown: -$20,639
- Sharpe: 4.25
- Two market regimes: May-Sept 2025 (unfavorable, TP_ZSCORE losses) / Oct 2025-Jan 2026 (very favorable)

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

Profile: many trades (1400+), moderate WR (57-61%), high absolute PnL, large MaxDD (-$20k to -$25k).

### Top 5 by Sharpe (risk-adjusted)

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | beta2640_zp20_cp30_co60_zE3_TP200_SL400 | 31 | 90.3% | $2,549 | 6.61 | -$332 | 14.72 |
| 2 | beta2640_zp20_cp30_co50_zE3_TP200_SL400 | 146 | 84.9% | $10,459 | 5.09 | -$574 | 11.65 |
| 3 | beta3960_zp20_cp60_co60_zE3_TP200_SL400 | 39 | 79.5% | $2,408 | 4.63 | -$277 | 11.65 |
| 4 | beta2640_zp20_cp30_co50_zE3_TP200_SL600 | 146 | 84.9% | $10,259 | 4.72 | -$774 | 10.37 |
| 5 | beta2640_zp20_cp60_co60_zE3_TP200_SL400 | 33 | 84.8% | $2,293 | 4.58 | -$410 | 9.50 |

Profile: very few trades (31-146), high WR (80-90%), modest PnL ($2.5k-$10.5k), tiny MaxDD (<$800).

### Key grid search conclusions (8 months)
- **PnL vs Sharpe trade-off**: zero configs in common between the two rankings
- High PnL requires loose filters (co=40, zE=-2.5) and TP=$400
- High Sharpe requires strict filters (co=50-60, zE=-3.0) and TP=$200
- SL value has minimal impact on top PnL configs (SL never hit on Sharpe configs)
- `correlation_min` remains redundant across all 864 configs
- `beta1320` and `beta1980` dominate PnL; `beta2640` dominates Sharpe

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

Run with 8 parallel workers (`multiprocessing.Pool`), completed in ~10 hours.
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

Profile: very few trades (16-29), marginal profitability, only zE=3.5 viable.

### Top 5 with 1 tick slippage (for comparison)

| # | Config | PnL 2tick | PnL 1tick | Delta |
|---|--------|-----------|-----------|-------|
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | +$586 | +$1,946 | +$1,360 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | +$531 | +$1,891 | +$1,360 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | +$446 | +$1,746 | +$1,300 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | +$446 | +$1,746 | +$1,300 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | +$437 | +$2,547 | +$2,110 |

### Key grid search conclusions (3 years)
- **Slippage is the strategy killer**: doubling slippage (1->2 ticks) destroys all profitability
- **zscore_entry=-3.5 is the only viable threshold**: 112/115 profitable configs use zE=3.5
- **zscore_period >= 30 produces zero profitable configs** on 3-year data
- **TP_ZSCORE remains the core problem**: even with PnL floor >= $0, these exits lose money (costs eat small gains)
- **beta=3960 dominates** the top configs (longest lookback = most stable regression)
- **cointegration_score_min=60** dominates (strictest filter reduces bad trades)
- **8-month results were misleading**: the Oct-Jan 2026 regime was exceptionally favorable, inflating PnL
- Strategy is fundamentally cost-sensitive: average PnL per trade ($20-30) barely covers transaction costs

## Walk-Forward Test (6 windows, 12 configs)

Validated the strategy is NOT overfitting. 6 rolling windows (30-day train / 15-day test), 12 configs tested per window, best selected on train PnL.

### Results per window (out-of-sample)

| # | Test Period | Config Selected | Trades | PnL | WR% | PF | MaxDD |
|---|-------------|-----------------|--------|-----|-----|-----|-------|
| 1 | Jul 18 - Aug 04 | Sh5 (zE3, TP200) | 10 | -$313 | 30% | 0.50 | -$543 |
| 2 | Aug 17 - Sep 28 | Sh5 (zE3, TP200) | 10 | -$4 | 50% | 0.99 | -$423 |
| 3 | Oct 10 - Oct 27 | Sh5 (zE3, TP200) | 17 | +$2,004 | 94% | 112 | $0 |
| 4 | Nov 09 - Nov 25 | PnL3 (TP300, SL600) | 183 | +$2,270 | 58% | 1.22 | -$2,414 |
| 5 | Dec 08 - Dec 24 | PnL3 (TP300, SL600) | 153 | +$9,245 | 70% | 1.89 | -$1,822 |
| 6 | Jan 06 - Jan 22 | PnL6 (TP400, SL800) | 201 | +$31,371 | 83% | 3.40 | -$1,715 |

### Walk-forward summary
- **Total out-of-sample PnL**: +$44,573 (vs $43,903 in-sample)
- **Retention**: 203% of daily PnL (test > train)
- **Positive windows**: 4/6
- **Verdict**: Strategy is ROBUST out-of-sample, but regime-dependent
- **Two regimes**: May-Sept 2025 (mean reversion weak, losses) / Oct-Jan 2026 (strong, profits)
- **Config stability**: Sh5 selected 3/6 windows (defensive), PnL3 2/6 (aggressive), PnL6 1/6
- Results saved in `output/walk_forward_results.csv`

## Optimization History

### Phase 1 -- 48-day data (606+ configs, Dec 2025 - Jan 2026)
1. **Etape 1 (22 configs)**: beta_lookback (660-7920) x zscore_period (15/20/30)
2. **Etape 2 (101 configs)**: top 5 indicators x TP (200-600) x SL (400-1200)
3. **Etape 3 (481 configs)**: 6 bases x correlation_period x adf_period x corr_min x coint_min
4. **Hurst filter (12 configs)**: zero impact (redundant with Cointegration Score)

### Phase 2 -- 8-month data (864 configs, May 2025 - Jan 2026)
- Full grid search with optimized grouping (16 indicator groups x 54 entry/exit variants)
- Completed in 28 minutes (grouped indicator calculation)
- Walk-forward validation: 6 windows, 12 configs each, no overfitting detected
- Log saved in `output/optimization_log.csv` (batch_id="grid_8mois")

### Phase 3 -- 3-year data (32,400 configs, Jan 2023 - Jan 2026, 2 ticks slippage)
- Comprehensive grid search: 300 indicator groups x 108 entry/exit variants
- Run with multiprocessing (8 workers), completed in ~10 hours
- Slippage increased to 2 ticks per leg (more realistic)
- **Result: only 0.4% of configs profitable, best PnL = $586 over 3 years**
- Conclusion: strategy is NOT viable with realistic slippage on 3-year data
- Results saved in `output/grid_search_3y_phase1.csv`
- Script: `run_grid_search_3y.py`

### Key optimization conclusions
- `correlation_min` is redundant: correlation always > 0.80 when Z-Score + Coint conditions met
- `hurst_max` is redundant: Hurst < 0.45 on all traded bars (captured by Cointegration Score)
- `cointegration_score_min` is the most impactful secondary parameter (40 vs 60 = +63% PnL on 8-month data)
- TP/SL dollar thresholds are the most impactful parameters overall
- Strategy performance is regime-dependent (5 months of losses followed by 3 months of large gains)
- **Slippage is the critical factor**: 1 tick -> strategy profitable; 2 ticks -> strategy destroyed
- **8-month results were overly optimistic**: driven by an exceptionally favorable 3-month regime (Oct 2025 - Jan 2026)

## Next Steps (TODO)

### Priority 1 -- Strategy Viability Assessment
The 3-year grid search (32,400 configs, 2 ticks slippage) showed the strategy is not viable in its current form. Options:
- **Re-run with 1 tick slippage**: verify if strategy becomes viable with optimistic slippage assumption
- **Test wider TP/SL ranges**: TP=$500-$1000, SL=-$1500-$2000 (let trades run longer to overcome costs)
- **Remove TP_ZSCORE exits entirely**: rely only on dollar-based TP/SL (TP_ZSCORE is the main source of losses)
- **Multi-timeframe**: test on 5-min or 15-min bars (fewer trades, higher PnL per trade, lower cost impact)
- **Alternative cost model**: test with $3 commission (IB) and 1 tick slippage to find the cost threshold

### Priority 2 -- TP_ZSCORE Problem
The fundamental issue: TP_ZSCORE exits fire when the spread mean-reverts in Z-Score space, but the dollar move is often too small to cover transaction costs.
- **PnL floor on TP_ZSCORE** (already implemented, `exit.zscore_tp_min_pnl`): tested at $0, insufficient
- **Higher PnL floor**: test $50, $100, $150 to force meaningful profit before Z-Score exit
- **Disable TP_ZSCORE entirely**: only exit via TP_DOLLAR or SL thresholds
- **Regime filter**: only allow entries when spread volatility is high enough to generate dollar moves

### Priority 3 -- Multi-Timeframe Testing
Test on different bar periods to reduce trade frequency and increase PnL per trade:
- **5-minute bars**: less noise, fewer trades, potentially better PnL per trade
- **15-minute bars**: even less noise, requires longer lookback periods
- Requires resampling data or new Sierra Chart exports at 5min/15min
- The `indicators.period` config field already supports this but data pipeline needs adaptation

### Priority 4 -- Walk-Forward on 3-Year Data
If a viable config is found, validate with walk-forward on the full 3-year dataset (15-20 windows).

### Priority 5 -- Code Optimizations
- Rolling beta: use pandas `.rolling()` or Welford's algorithm (save ~30s per run)
- Cache contract point values outside backtest loop
- Add input validation in position.py (gc_price > 0, beta > 0)
- Add unit tests with pytest for edge cases

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
- **Code factorization**: `common.py` centralizes state constants and shared functions (check_entry_conditions, check_zscore_exit, check_cooldown_reset, calculate_current_pnl, build_config_fingerprint). Removed ~430 lines of duplicated code across signals.py, backtest_engine.py, backtest_engine_hybrid.py, metrics.py.
- **Hurst bug fix**: Both backtest engines now pass `hurst=hursts[i]` to check_entry_conditions (was silently ignored before). No impact with default hurst_max=1.0.
- **8-month data upgrade**: Extended from 48 days (GCG26) to 8 months (GCJ26, May 2025 - Jan 2026). Contract rollover handled.
- **Optimized grid search**: `run_grid_search.py` groups 864 configs into 16 indicator combinations, calculates indicators once per group, then loops 54 entry/exit variants. Reduced time from ~9h to 28 min.
- **Walk-forward validation**: `run_walk_forward.py` implements 6-window rolling walk-forward (30-day train / 15-day test). Confirmed no overfitting (203% out-of-sample retention).
- **PnL floor on TP_ZSCORE**: `exit.zscore_tp_min_pnl` parameter in common.py. Only allows TP_ZSCORE exit if current PnL >= threshold (default $0). Tested but insufficient to fix the TP_ZSCORE problem.
- **Slippage 2 ticks default**: `costs.slippage_gc_ticks` and `costs.slippage_si_ticks` set to 2 (was 1). More realistic worst-case assumption. Configurable via optimizer overrides.
- **Hour filter**: `session.entry_start_hour` and `session.entry_end_hour` in backtest_engine_hybrid.py. Blocks new entries outside configured hours (default 0-24 = disabled). Exits are never filtered.
- **GC contracts cap**: `sizing.gc_contracts_max` in position.py. Caps maximum GC contracts per trade (default 0 = no cap).
- **Verbose parameter**: `calculate_all_indicators()` and `run_hybrid_backtest()` accept `verbose=False` to suppress print output during mass backtesting.
- **3-year data upgrade**: Extended from 8 months to 3 years (Jan 2023 - Jan 2026). 801,499 1-min bars, 4,604,839 5s bars.
- **Multiprocessing grid search**: `run_grid_search_3y.py` uses `mp.Pool(8)` for parallel backtesting. 32,400 configs in ~10 hours.

## Known Code Issues (non-blocking)

- **Rolling beta**: O(n x lookback) manual loop in indicators.py. Could use pandas rolling or Welford's algorithm for ~30s speedup.
- **Hurst clamp vs default**: Hurst clamped to [0.01, 0.99] in indicators.py but default hurst_max=1.0. Functionally correct but misleading -- 0.99 would be clearer.
- **Unused import**: `Tuple` imported but unused in data_loader_5s.py.
- **Hardcoded thresholds**: ADF critical value (-2.86) and correlation threshold (0.6) hardcoded in indicators.py cointegration score calculation. Should reference config values.

## Claude Code Skills

### /backtest-runner
Runs the hybrid backtest and affiche les resultats formates. Compare automatiquement avec le run precedent.
- Sauvegarde les resultats precedents avant execution
- Lance `backtest_engine_hybrid.py` puis `metrics.py`
- Affiche les metriques cles et la comparaison avec le run precedent
- Option de push vers GitHub

### /optimize
Teste differents parametres via langage naturel en francais. Supporte le grid search avec la syntaxe "/" (ex: "teste beta 1320/2640 avec TP 400/600").
- Utilise `optimizer.py` : charge les donnees 1 fois, boucle sur N configs en memoire
- Ne modifie PAS le YAML pendant les tests (travaille en memoire)
- Affiche un tableau comparatif trie par PnL
- Option d'archiver le meilleur resultat

### /compare
Compare tous les backtests archives dans `output/archive/index.csv`.
- Affiche un tableau trie par PnL net (ou autre critere)
- Met en evidence le meilleur run et les tendances

## Parquet Cache

Les donnees synchronisees sont cachees en Parquet dans `data/processed/` apres le premier chargement CSV. Invalidation automatique par hash MD5 des fichiers sources. Les indicateurs ne sont PAS caches (dependent de la config).

## Git Tracking

`.gitignore` exclut : `.venv/`, `__pycache__/`, `data/raw/`, `DOC SIERRA/`, `.idea/`, `.claude/`, `output/`, `results/`

Les donnees brutes Sierra Chart, les resultats de backtest et la documentation ACSIL ne sont pas versionnees.

## Reference Documentation

- `config/strategy_params.yaml` - All strategy parameters
- `output/trade_list.csv` - Z-Score trade list (semicolon-separated, Excel compatible)
- `output/backtest_trades.csv` - Full backtest with PnL in dollars (1-min High/Low, semicolon-separated)
- `output/backtest_hybrid.csv` - Hybrid backtest with PnL in dollars (1-min + 5s, semicolon-separated)
- `output/archive/` - Archived backtest results organized by period/indicators/entry-exit
- `output/archive/index.csv` - Global index of all archived runs (semicolon-separated)
- `output/optimization_log.csv` - Optimization history log
- `DOC SIERRA/files/` - Sierra Chart ACSIL documentation
- `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.4.cpp` - ACSIL source code (reference)
- `README.md` - Documentation du projet en francais (installation, usage, structure)
