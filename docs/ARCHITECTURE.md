# GC/SI Spread Trading Backtest System - Architecture Documentation

## 1. Overview

### System Description
This is a Python 3.11 backtesting system for Gold/Silver (GC/SI) spread trading based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.5) and is optimized for high-frequency parameter exploration.

### Key Metrics
- **Codebase size**: 6,152 lines across 10 modules in `src/`
- **Test coverage**: 131 unit tests (pytest), all passing in ~0.4s
- **Data volume**: 801,499 synchronized 1-min bars, 4,604,839 5-second bars (3 years)
- **Harmonization**: Sierra Chart v1.5 indicator matched to <0.01% difference
- **Hardware target**: AMD Ryzen 9 7900X (12 cores, 24 threads), 64 GB RAM

### Design Philosophy
- **Single source of truth**: All parameters in `config/strategy_params.yaml`
- **Vectorization first**: 50x speedup for Beta/ADF, 42x for Hurst
- **Cache aggressively**: Parquet cache for data, MD5-based invalidation
- **Test with synthetic data**: No dependency on real CSV files in tests
- **Parallel by default**: 24 workers for grid search (optimal for target hardware)

---

## 2. Data Pipeline

### Architecture Diagram
```
Sierra Chart CSV (1-min)
    ↓
data_loader.py (load_and_prepare_data)
    ↓
[Parquet cache: data/processed/gc_si_1min_{hash}.parquet]
    ↓
resample_to_5min() [optional]
    ↓
[Parquet cache: data/processed/gc_si_5min_{hash}.parquet]
    ↓
indicators.py (calculate_all_indicators)
    ↓
DataFrame with Beta, Z-Score, Correlation, ADF, Hurst
    ↓
common.py (check_entry_conditions, check_exit_conditions)
    ↓
backtest_engine_hybrid.py (run_hybrid_backtest)
    ├─ Uses df_1min for signals
    └─ Uses df_5s for dollar exit monitoring
    ↓
Trade list CSV
    ↓
metrics.py (run_metrics)
    ↓
Performance report + equity curve + archiving

Sierra Chart CSV (5s)
    ↓
data_loader.py (load_5s_data)
    ↓
[Parquet cache: data/processed/gc_si_5s_{hash}.parquet]
    ↓
backtest_engine_hybrid.py (intra-bar price monitoring)
```

### Data Flow Details

**Load Phase** (data_loader.py):
- Read Sierra Chart CSV exports (.txt format)
- Synchronize GC/SI timestamps using inner join on DateTime
- Cache to Parquet with MD5 hash of source files
- Auto-invalidate cache if source files change

**Processing Phase** (indicators.py):
- Calculate all technical indicators in vectorized batches
- NO caching (indicators depend on config parameters)
- Rolling window operations for Beta, ADF
- Stride tricks for Hurst exponent

**Backtest Phase** (backtest_engine_hybrid.py):
- Indicators and signals computed on 1-minute bars
- When in position, scan 5-second bars for dollar exits
- Z-Score exits checked on 1-min bars only
- Trade list generation with detailed metadata

**Analysis Phase** (metrics.py):
- Performance metrics (Sharpe, Calmar, Win Rate, Profit Factor)
- Equity curve generation (PNG)
- Archiving to output/archive/ with classification

---

## 3. Module Responsibilities

### data_loader.py (533 lines)
**Purpose**: Load and prepare time series data from Sierra Chart exports.

**Key Functions**:
- `load_and_prepare_data()` → (df, config, stats)
  - Loads 1-min GC/SI bars from CSV
  - Synchronizes timestamps (inner join)
  - Caches to Parquet with MD5-based invalidation
  - Returns DataFrame with Last_GC, Last_SI columns

- `resample_to_5min(df)` → df_5min
  - Resamples 1-min bars to 5-min bars
  - Uses OHLC aggregation (Last → Close)
  - Caches to Parquet (data/processed/gc_si_5min_{hash}.parquet)

- `load_5s_data(config)` → df_5s
  - Loads 5-second bars for intra-bar monitoring
  - Synchronizes GC/SI timestamps
  - Caches to Parquet (data/processed/gc_si_5s_{hash}.parquet)

**Caching Strategy**:
- MD5 hash computed from source file paths + modification times
- Cache invalidated automatically if source data changes
- Parquet format for fast load times (~0.5s vs 15s for CSV)

---

### indicators.py (811 lines)
**Purpose**: Calculate all technical indicators using vectorized operations.

**Key Function**:
- `calculate_all_indicators(df, config)` → df
  - Adds columns: Beta, Alpha, Spread, Spread_Mean, Spread_Std, ZScore
  - Adds columns: Correlation, ADF_Statistic, Hurst, HalfLife, Cointegration_Score
  - Uses pandas rolling windows for performance

**Indicators**:

| Indicator | Calculation | Lookback | Performance |
|-----------|-------------|----------|-------------|
| Beta | OLS regression (GC ~ SI) | beta_lookback (1320) | 50x speedup (vectorized) |
| Alpha | Intercept of Beta regression | beta_lookback | Same as Beta |
| Spread | Log_GC - Beta * Log_SI - Alpha | Point-in-time | Instant |
| Z-Score | (Spread - Mean) / Std | zscore_period (24) | Vectorized |
| Correlation | Pearson(Log_GC, Log_SI) | correlation_period (24) | Vectorized |
| ADF | Augmented Dickey-Fuller | adf_period (96) | 50x speedup (vectorized) |
| Hurst | R/S analysis | hurst_period (96) | 42x speedup (stride_tricks) |
| HalfLife | ln(2) / ln(1 - slope) | adf_period | Same as ADF |
| Coint Score | Normalized quality metric | Combined | Instant |

**Optimization Notes**:
- Beta/ADF: Use pandas rolling + apply for vectorization (50x speedup)
- Hurst: Use numpy stride_tricks for sliding window (42x speedup: 4.2s → 0.1s on 160k bars)
- Cointegration Score: Normalize ADF, Hurst, HalfLife to [0, 100] scale

---

### common.py (260 lines)
**Purpose**: Shared constants and condition-checking functions used by backtest engine.

**State Machine Constants**:
```python
FLAT = 0
LONG = 1
SHORT = -1
COOLDOWN_LONG = 2
COOLDOWN_SHORT = -2
```

**Key Functions**:
- `check_entry_conditions(row, config)` → (can_enter_long, can_enter_short)
  - Validates Z-Score thresholds
  - Checks Correlation, Cointegration Score, Hurst
  - Returns tuple of booleans

- `check_zscore_exit(state, zscore, config)` → (should_exit, reason)
  - Checks TP_ZSCORE and SL_ZSCORE exits
  - Direction-specific thresholds
  - Returns (bool, "TP_ZSCORE" | "SL_ZSCORE" | None)

- `check_dollar_exit(current_pnl, config)` → (should_exit, reason)
  - Checks TP_DOLLAR and SL_DOLLAR exits
  - Priority: SL_DOLLAR > TP_DOLLAR
  - Returns (bool, "TP_DOLLAR" | "SL_DOLLAR" | None)

- `check_cooldown_reset(state, zscore, config)` → should_reset
  - COOLDOWN_LONG → FLAT when Z-Score >= -1.0
  - COOLDOWN_SHORT → FLAT when Z-Score <= +1.0

- `calculate_current_pnl(entry_gc, entry_si, current_gc, current_si, gc_contracts, si_contracts, direction, config)` → pnl
  - Returns net PnL (after commissions, before exit slippage)

**Design Rationale**:
- Extracted from backtest_engine_hybrid.py to enable unit testing
- Pure functions (no side effects)
- Used by both backtest engines and unit tests

---

### position.py (398 lines)
**Purpose**: Position sizing and PnL calculation with transaction costs.

**Key Functions**:
- `calculate_position_size(gc_price, si_price, beta, config)` → dict
  - Dollar-neutral Beta-weighted sizing
  - SI: 1 contract (fixed)
  - GC: round((SI_notional / GC_notional) * Beta), minimum 1
  - Returns: {gc_contracts, si_contracts, gc_notional, si_notional}

- `calculate_transaction_costs(gc_contracts, si_contracts, config)` → dict
  - Commission: $4.00 round-trip per contract
  - Slippage: N ticks per leg (default 1 tick)
  - Returns: {commission, slippage, total_cost}

- `calculate_trade_pnl(direction, entry_gc, entry_si, exit_gc, exit_si, gc_contracts, si_contracts, config)` → dict
  - Gross PnL: (exit - entry) * contracts * point_value
  - Net PnL: Gross - commission - slippage
  - Returns: {gross_pnl, net_pnl, commission, slippage}

**Contract Specifications**:
| Contract | Point Value | Tick Size | Tick Value |
|----------|-------------|-----------|------------|
| GC (Gold) | $100 | $0.10 | $10 |
| SI (Silver) | $5000 | $0.005 | $25 |

**Position Sizing Formula**:
```
NotionalGC = GC_price * $100
NotionalSI = SI_price * $5000
GC_contracts = round((NotionalSI / NotionalGC) * Beta), minimum 1

Beta range on traded bars: ~0.03 to ~6.3
→ GC contracts range: 1 to 6
```

---

### backtest_engine_hybrid.py (597 lines)
**Purpose**: Main backtest simulation loop with state machine execution.

**Key Function**:
- `run_hybrid_backtest(df_1min, df_5s, config)` → trades_df
  - Loops through 1-min bars
  - State machine: FLAT → LONG/SHORT → FLAT/COOLDOWN
  - Entry: check conditions on 1-min bar
  - Exit: dollar exits on 5s bars, Z-Score exits on 1-min bars

**State Transitions**:
```
FLAT (0) → LONG (1) or SHORT (-1)     [entry conditions met]
LONG → FLAT                            [TP Z-Score: Z >= -2.0]
LONG → COOLDOWN_LONG (2)               [SL Z-Score: Z <= -4.5]
SHORT → FLAT                           [TP Z-Score: Z <= +2.0]
SHORT → COOLDOWN_SHORT (-2)            [SL Z-Score: Z >= +4.5]
COOLDOWN_LONG → FLAT                   [Z >= -1.0]
COOLDOWN_SHORT → FLAT                  [Z <= +1.0]
```

**Exit Detection Priority** (per 1-min bar):
1. Scan 5s bars between consecutive 1-min bars:
   - Check SL_DOLLAR (-$1200) → break immediately
   - Check TP_DOLLAR (+$1000) → break immediately
2. If no 5s trigger found:
   - Check SL_ZSCORE on 1-min Z-Score
   - Check TP_ZSCORE on 1-min Z-Score (if enabled)

**Key Design Decisions**:
- **5s bars used ONLY for price monitoring**: No indicators recalculated on 5s data
- **Short-circuit optimization**: Break 5s scan as soon as dollar exit found
- **Reversal allowed**: Close LONG and open SHORT on same 1-min bar
- **Single position at a time**: No pyramiding or scaling

**Performance Note**:
- 5s scan short-circuit: ~12x speedup in pure Z-Score mode (no dollar exits)
- Without short-circuit: 150s; with short-circuit: 12s (on 3-year data)

---

### optimizer.py (564 lines)
**Purpose**: Multi-config backtesting with in-memory optimization.

**Key Functions**:
- `run_optimization(configs_list)` → comparison_df
  - Loads data once (df_1min, df_5s)
  - Loops through N configs in memory
  - For each config:
    1. Apply overrides
    2. Calculate indicators
    3. Run backtest
    4. Collect metrics
  - Returns DataFrame with comparison table

- `apply_overrides(config, overrides)` → config
  - Applies dotted-key overrides to config dict
  - Example: {"exit.pnl_take_profit": 500} sets config['exit']['pnl_take_profit'] = 500
  - Supports nested keys with dot notation

**Override System**:
```python
overrides = {
    "exit.pnl_take_profit": 500,
    "exit.pnl_stop_loss": -800,
    "indicators.zscore_period": 30
}
config = apply_overrides(base_config, overrides)
```

**Metrics Computed**:
- Net PnL, Number of trades, Win Rate
- Profit Factor, Average Win/Loss
- Max Drawdown (absolute)
- Sharpe ratio (per trade, not annualized)

**Design Rationale**:
- Load data once → massive speedup for multi-config tests
- In-memory config manipulation → no YAML writes during optimization
- Used by: /optimize skill, grid_search_runner.py, walk_forward_runner.py

---

### metrics.py (941 lines)
**Purpose**: Comprehensive performance analysis and archiving.

**Key Function**:
- `run_metrics()` → None
  - Reads output/backtest_hybrid.csv
  - Computes all performance metrics
  - Generates equity curve (PNG)
  - Archives results to output/archive/ with classification

**Metrics Computed**:
- **Trade statistics**: Total trades, Win Rate, Profit Factor
- **PnL statistics**: Total PnL, Average Win/Loss, Best/Worst trade
- **Risk metrics**: Max Drawdown, Calmar ratio
- **Efficiency metrics**: Sharpe ratio (per trade, not annualized)
- **Exit breakdown**: Count by exit reason (TP_ZSCORE, SL_DOLLAR, etc.)

**Archiving Workflow**:
1. Generate unique config name (e.g., b1320_zp24_cp24_adf96_...)
2. Create folder in output/archive/{timeframe}_{slippage}/{filter}/{category}/
3. Copy: backtest_hybrid.csv, params_snapshot.yaml
4. Generate: metrics_report.txt, equity_curve.png
5. Update: output/archive/index.csv

**Archive Categories**:
- top_pnl: Top 10 by Net PnL
- top_sharpe: Top 10 by Sharpe ratio
- top_calmar: Top 10 by Calmar ratio (PnL / |Max DD|)
- top_equilibre: Top 5 balanced (good PnL + Sharpe + Calmar)

---

### grid_search_runner.py (552 lines)
**Purpose**: Parallel grid search using multiprocessing.Pool(24).

**Key Class**:
- `GridSearchRunner(config)` → runner instance
  - config: YAML dict with parameter grid
  - Methods:
    - `build_config_grid()` → list of config dicts
    - `worker(config_dict)` → metrics dict
    - `run()` → saves to CSV

**Grid Search Process**:
1. Read YAML config with parameter ranges
2. Generate Cartesian product of all parameter combinations
3. Spawn Pool(24) workers
4. Each worker:
   - Load data (df_1min, df_5s)
   - Calculate indicators
   - Run backtest
   - Return metrics dict
5. Save results to output/grid_search_{timestamp}.csv
6. Support CSV resumption (skip configs already in CSV)

**YAML Config Format**:
```yaml
data:
  data_dir: "data/raw"
  start_date: "2023-01-26"
  end_date: "2026-01-30"

parameters:
  indicators.beta_lookback: [1320, 2640]
  indicators.zscore_period: [24, 30]
  exit.pnl_take_profit: [300, 400, 500]
  exit.pnl_stop_loss: [-600, -800]

execution:
  num_workers: 24
  output_file: "output/grid_search_test.csv"
```

**Performance**:
- 24 workers optimal for AMD Ryzen 9 7900X (12 cores, 24 threads)
- Each worker: ~600 MB RAM
- 24 workers: ~15 GB / 64 GB total RAM
- Benchmark: 24 workers = +17.5% speed vs 12 workers

---

### walk_forward_runner.py (406 lines)
**Purpose**: Walk-forward validation with rolling train/test windows.

**Key Class**:
- `WalkForwardRunner(config)` → runner instance
  - config: YAML dict with window configuration
  - Methods:
    - `generate_windows()` → list of (train_start, train_end, test_start, test_end)
    - `run()` → saves to CSV

**Walk-Forward Process**:
1. Generate train/test window pairs
2. For each window:
   - Train: find best config on training data (via grid search or pre-selected)
   - Test: apply best config to test data
   - Record test performance
3. Aggregate results across all windows

**YAML Config Format**:
```yaml
data:
  data_dir: "data/raw"
  start_date: "2023-01-26"
  end_date: "2026-01-30"

windows:
  train_months: 6
  test_months: 1
  step_months: 1

config:
  # Best config from grid search
  indicators.beta_lookback: 1320
  exit.pnl_take_profit: 1000
  # ...

execution:
  output_file: "output/walk_forward_3y.csv"
```

**Output Metrics**:
- Per-window performance: PnL, trades, Win Rate, Sharpe
- Aggregate statistics: Total PnL, % positive windows, consistency

---

### report_generator.py (529 lines)
**Purpose**: Post-grid-search analysis and summary generation.

**Key Function**:
- `generate_report(csv_path, description)` → None
  - Reads grid_search_*.csv
  - Generates output/latest_summary.txt
  - Optionally updates CHANGELOG.md

**Report Sections**:
1. **Top 10 by Net PnL**
2. **Top 10 by Sharpe ratio**
3. **Top 10 by Calmar ratio**
4. **Top 5 balanced configs**
5. **Parameter frequency analysis**
6. **Profitable vs unprofitable comparison**

**CLI Usage**:
```bash
python src/report_generator.py output/grid_search_xxx.csv --description "3-year grid search on 1-min data"
```

---

## 4. Configuration System

### YAML Structure
```yaml
data:
  data_dir: "data/raw"
  gc_file: "gc_1min.txt"
  si_file: "si_1min.txt"
  start_date: "2023-01-26"
  end_date: "2026-01-30"

contracts:
  gc:
    point_value: 100
    tick_size: 0.10
    tick_value: 10
  si:
    point_value: 5000
    tick_size: 0.005
    tick_value: 25

indicators:
  period: "1min"  # Calculation timeframe: 1min, 5min, 15min, 1h, 1d
  beta_lookback: 1320
  zscore_period: 24
  correlation_period: 24
  adf_period: 96
  hurst_period: 96

entry:
  zscore_entry_long: -3.5
  zscore_entry_short: 3.5
  correlation_min: 0.60
  cointegration_min: 50
  hurst_max: 1.0  # Disabled (redundant with Cointegration Score)

exit:
  zscore_tp_enabled: false
  zscore_tp_long: -2.0
  zscore_tp_short: 2.0
  zscore_sl_long: -4.5
  zscore_sl_short: 4.5
  pnl_take_profit: 1000
  pnl_stop_loss: -1200
  zscore_tp_min_pnl: null  # Minimum PnL required for TP_ZSCORE exit

reentry:
  cooldown_zscore_reset: 1.0

sizing:
  method: "beta_weighted"
  capital: 100000

costs:
  commission_per_contract: 4.0  # Round-trip
  slippage_ticks: 1  # Per leg

session:
  start_time: "17:30"
  end_time: "15:30"
  timezone: "US/Central"

advanced:
  regime_filter: false  # HMM filter (Python-only, not Sierra Chart compatible)
```

### Override System
**Dot notation** for nested keys:
```python
overrides = {
    "exit.pnl_take_profit": 500,
    "indicators.zscore_period": 30
}
config = apply_overrides(base_config, overrides)
```

**Used by**:
- optimizer.py: apply_overrides()
- grid_search_runner.py: worker applies overrides per config
- /optimize skill: natural language → override dict

---

## 5. Execution Scripts

### Generic YAML-Driven Runners

**scripts/run_grid_search.py**
- Usage: `python scripts/run_grid_search.py --config configs/experiments/grid_3y.yaml`
- Reads YAML config
- Builds parameter grid (Cartesian product)
- Runs parallel grid search via grid_search_runner.py
- Saves to CSV

**scripts/run_walk_forward.py**
- Usage: `python scripts/run_walk_forward.py --config configs/experiments/wf_3y.yaml`
- Reads YAML config
- Generates train/test windows
- Runs walk-forward validation via walk_forward_runner.py
- Saves to CSV

### YAML Experiment Configs (configs/experiments/)

| File | Configs | Purpose |
|------|---------|---------|
| grid_3y.yaml | 32,400 | 1-min dollar mode, 3-year data |
| grid_5min.yaml | 155,520 | 5-min Z-Score mode |
| grid_beta_long.yaml | 4,050 | Beta long lookback sweep |
| grid_ztp_extended.yaml | 45,360 | Extended Z-Score TP range |
| grid_5min_test.yaml | 12 | Smoke test (quick validation) |
| wf_base.yaml | 6 windows | Walk-forward 6-month train / 1-month test |
| wf_3y.yaml | 34 windows | Full 3-year walk-forward |
| wf_5min_ztp.yaml | 34 windows | 5-min Z-Score TP walk-forward |
| wf_beta_long.yaml | 34 windows | Beta long walk-forward |

### Special Scripts (Custom Logic)

**scripts/run_grid_no_tp_zscore.py**
- Tests 6 TP_ZSCORE modes with manual loop
- Not YAML-izable (custom worker logic)

**scripts/run_grid_search_extended_1tick.py**
- 3 TP_ZSCORE modes with custom worker
- Not YAML-izable (custom metrics)

**scripts/run_grid_search_top100_1tick.py**
- Retest top 100 configs from CSV
- Comparison with original results
- Not YAML-izable (reads CSV, not parameter grid)

**scripts/run_top5_archive.py**
- Archive top 5 configs with full metrics + equity curve
- Not YAML-izable (archiving workflow)

---

## 6. Testing

### Test Architecture
- **131 tests** across 7 test files
- **All tests pass** in ~0.4s
- **Synthetic data only**: No dependency on real CSV files
- **Fixtures in conftest.py**: sample_config, sample_prices_df, sample_df_with_indicators, etc.

### Test Coverage

| Test File | Tests | Module | Lines | Coverage |
|-----------|-------|--------|-------|----------|
| test_common.py | 32 | common.py | 260 | 100% |
| test_indicators.py | 33 | indicators.py | 811 | 72% |
| test_position.py | 26 | position.py | 398 | 48% |
| test_backtest_engine_hybrid.py | 13 | backtest_engine_hybrid.py | 597 | ~30% |
| test_optimizer.py | 9 | optimizer.py | 564 | ~25% |
| test_metrics.py | 12 | metrics.py | 941 | ~15% |
| test_run_helpers.py | 6 | run_helpers.py | ~250 | ~60% |

### Key Fixtures (conftest.py)

**sample_config**
- Minimal strategy config dict
- Used by all tests requiring config

**sample_prices_df**
- Synthetic price DataFrame (100 rows)
- Columns: DateTime, Last_GC, Last_SI
- Used for position sizing tests

**sample_df_with_indicators**
- DataFrame with all indicator columns
- Columns: DateTime, Last_GC, Last_SI, Beta, ZScore, Correlation, ADF_Statistic, Hurst, Cointegration_Score
- Used for signal generation tests

**sample_trades_list**
- List[dict] with string values (csv.DictReader format)
- Used for metrics calculation tests

### Running Tests

```bash
# All tests (131 tests)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=src

# Single file
pytest tests/test_common.py -v

# Tests matching pattern
pytest -k "test_long"
```

---

## 7. Output Structure

### Directory Tree
```
output/
├── backtest_hybrid.csv              ← Latest run trades
├── backtest_hybrid.meta.json        ← Config fingerprint (MD5 hash)
├── equity_curve.png                 ← Equity curve chart
├── metrics_report.txt               ← Performance report
├── optimization_log.csv             ← Optimizer log
├── latest_summary.txt               ← Last grid search summary
├── grid_search_*.csv                ← Grid search results
├── walk_forward_*.csv               ← Walk-forward results
└── archive/                         ← Archived configs (classified)
    ├── _PRODUCTION/                 ← Config active in paper trading
    ├── 1min_1tick/                  ← 1-min timeframe, 1 tick slippage
    │   ├── no_hmm/                  ← No HMM filter (Sierra Chart compatible)
    │   │   ├── top_pnl/             ← Top 10 by Net PnL
    │   │   ├── top_sharpe/          ← Top 10 by Sharpe ratio
    │   │   ├── top_calmar/          ← Top 10 by Calmar ratio
    │   │   └── top_equilibre/       ← Top 5 balanced
    │   ├── hmm/                     ← With HMM filter (Python only)
    │   └── walk_forward/            ← Walk-forward results
    ├── 5min_2tick/                  ← 5-min timeframe, 2 ticks slippage
    │   ├── no_hmm/
    │   ├── hmm/
    │   └── walk_forward/
    ├── CLASSEMENT.txt               ← Global rankings
    ├── index.csv                    ← All archived configs index
    └── README.md                    ← Archive documentation
```

### Archived Config Folder Contents
Each config folder (e.g., `output/archive/1min_1tick/no_hmm/top_pnl/b1320_zp24_...`) contains:

1. **backtest_hybrid.csv**: Trade list with columns:
   - Entry_DateTime, Exit_DateTime
   - Entry_GC, Entry_SI, Exit_GC, Exit_SI
   - Direction, GC_Contracts, SI_Contracts
   - Gross_PnL, Net_PnL, Commission, Slippage
   - Exit_Reason

2. **params_snapshot.yaml**: Full config snapshot at backtest time

3. **metrics_report.txt**: Performance summary:
   - Total trades, Win Rate, Profit Factor
   - Net PnL, Max Drawdown, Sharpe ratio
   - Exit reason breakdown

4. **equity_curve.png**: Cumulative PnL chart

---

## 8. Performance Optimizations

### Vectorization

**Beta/ADF (50x speedup)**
- Before: Loop through each row, calculate Beta with lookback window
- After: pandas rolling + apply with vectorized OLS
- Time: 25s → 0.5s (on 160k bars)

**Hurst (42x speedup)**
- Before: Loop through each row, calculate R/S with Python loops
- After: numpy stride_tricks for sliding window + vectorized operations
- Time: 4.2s → 0.1s (on 160k bars)

**5s scan short-circuit (12x speedup)**
- Before: Always scan all 5s bars between consecutive 1-min bars
- After: Break immediately when dollar exit found
- Time: 150s → 12s (on 3-year data, pure Z-Score mode)

### Caching

**Parquet caching**
- 1-min data: data/processed/gc_si_1min_{md5_hash}.parquet
- 5-min data: data/processed/gc_si_5min_{md5_hash}.parquet
- 5s data: data/processed/gc_si_5s_{md5_hash}.parquet
- MD5 hash computed from source file paths + modification times
- Auto-invalidation if source data changes
- Load time: 15s (CSV) → 0.5s (Parquet)

**Indicators NOT cached**
- Depend on config parameters (beta_lookback, zscore_period, etc.)
- Must be recalculated for each config in grid search

### Parallelization

**Pool(24) for grid search**
- 24 workers optimal for AMD Ryzen 9 7900X (12 cores, 24 threads)
- Each worker: ~600 MB RAM (df_1min + df_5s in memory)
- 24 workers: ~15 GB / 64 GB total RAM
- Benchmark: 24 workers = +17.5% speed vs 12 workers

**Memory considerations**
- df_1min: ~200 MB (801,499 rows × 25 columns)
- df_5s: ~400 MB (4,604,839 rows × 10 columns)
- Total per worker: ~600 MB
- 24 workers × 600 MB = ~15 GB / 64 GB (24% of total RAM)

---

## 9. Sierra Chart Integration

### Harmonization Status (v1.5)
Python and Sierra Chart now produce **identical indicator values** (<0.01% difference):

| Indicator | Python vs Sierra | Max Diff | Status |
|-----------|------------------|----------|--------|
| Beta | 0.000000 | 0.00% | IDENTICAL |
| ADF Statistic | 0.000272 | 0.01% | NEGLIGIBLE |
| Correlation | 0.000035 | 0.00% | NEGLIGIBLE |
| Z-Score | 0.000334 | 0.03% | NEGLIGIBLE |
| Hurst | 0.000113 | 0.01% | NEGLIGIBLE |

### Key Alignment Changes
1. **ADF Statistic (v1.4 → v1.5)**: Added intercept (mu) to regression
2. **Session times**: GC and SI charts use identical session (17:00-16:00 CT)
3. **Config parameters**: Python YAML matches Sierra Chart settings exactly

### Sierra Chart Files
- **Indicator**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.5.cpp`
- **Spreadsheet export**: `DOC SIERRA/files/DefaultSpreadsheetStudy.txt`
- **Validation scripts**: `compare_sierra_v3.py`, `check_float_precision.py`

### Sierra Chart Settings (Must Match Python)
```cpp
Beta Lookback: 1320
Z-Score Period: 24
Correlation Period: 24
ADF/Hurst Period: 96
Z-Score Upper Threshold: 3.0
Z-Score Lower Threshold: -3.0
Min Cointegration Score: 50
Session Start: 17:00:00 CT
Session End: 15:30:00 CT
```

### Next Steps for Paper Trading
1. **Signal generation in Sierra Chart**: Implement entry/exit logic in v1.5
   - Entry: Z-Score crosses +/-3.0 with Coint Score >= 50
   - Exit: Z-Score TP at +/-2.0, SL at +/-4.5
   - Cooldown after stop loss

2. **Position sizing**: Implement Beta-weighted sizing
   - SI: 1 contract (fixed)
   - GC: round((SI_notional / GC_notional) * Beta)

3. **Paper trade execution**: Configure simulated trading
   - Set up trade simulation on GCJ26 and SIH26
   - Monitor fills, slippage, execution quality

4. **Validation**: Compare paper trades vs Python backtest
   - Same signals at same timestamps?
   - Same position sizes?
   - Similar PnL per trade?

---

## 10. Known Limitations

### Bug 2: ddof Inconsistency (Low Impact)
- **Issue**: Beta uses ddof=0, Z-Score uses ddof=1
- **Impact**: Slight difference in standard deviation calculation
- **Status**: Low priority (difference <0.1% in most cases)
- **Fix**: Standardize to ddof=1 for both

### Bug 3: Hurst Precision (Acceptable)
- **Issue**: Single-segment R/S analysis, 3-5 point regression
- **Impact**: Less precise than multi-segment Hurst
- **Status**: Acceptable for relative ranking (not absolute values)
- **Fix**: Implement multi-segment R/S analysis (low priority)

### Backtest Engine Complexity
- **Issue**: run_hybrid_backtest() is 350+ lines, 5+ nesting levels
- **Impact**: Hard to read and maintain
- **Status**: Needs decomposition (blocked by test coverage)
- **Fix**: Increase test coverage first, then refactor

### Regime Dependence
- **Issue**: Strategy profitable 2024-2025, weak 2023
- **Impact**: Performance degrades in low-volatility regimes
- **Status**: Walk-forward validation confirms regime dependence
- **Mitigation**: HMM regime filter (Python-only, +60% positive windows)

---

## Appendix A: Trade Flow Example

### Entry Flow (LONG spread)
1. Loop through 1-min bars
2. Check state: if FLAT or COOLDOWN_SHORT, check entry conditions
3. Entry conditions:
   - Z-Score <= -3.5
   - Correlation > 0.60
   - Cointegration Score >= 50
4. If all conditions met:
   - Calculate position size (Beta-weighted)
   - Record entry: timestamp, prices, contracts, state = LONG

### Exit Flow (LONG spread)
1. At next 1-min bar:
   - Get start/end timestamps of 1-min bar
   - Scan all 5s bars between start and end
   - For each 5s bar:
     - Calculate current PnL
     - Check SL_DOLLAR (-$1200) → if True, exit immediately
     - Check TP_DOLLAR (+$1000) → if True, exit immediately
2. If no 5s exit found:
   - Check SL_ZSCORE (Z <= -4.5) → if True, exit + cooldown
   - Check TP_ZSCORE (Z >= -2.0, if enabled) → if True, exit
3. If exit triggered:
   - Record exit: timestamp, prices, PnL, exit reason
   - Update state: FLAT or COOLDOWN_LONG (if SL)

### Cooldown Reset Flow (COOLDOWN_LONG)
1. At each 1-min bar:
   - Check Z-Score >= -1.0
   - If True: state = FLAT
   - If False: remain in COOLDOWN_LONG

---

## Appendix B: Config Name Encoding

Config names are auto-generated from parameters:

```
b{beta_lookback}_zp{zscore_period}_cp{correlation_period}_adf{adf_period}_
  zE{entry_threshold}_zTP{tp_threshold}_zSL{sl_threshold}_co{coint_min}

Example:
b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50

Decodes to:
- Beta lookback: 1320 bars
- Z-Score period: 24 bars
- Correlation period: 24 bars
- ADF/Hurst period: 96 bars
- Entry threshold: Z <= -3.0 (LONG) or Z >= +3.0 (SHORT)
- TP threshold: Z >= -2.0 (LONG) or Z <= +2.0 (SHORT)
- SL threshold: Z <= -4.5 (LONG) or Z >= +4.5 (SHORT)
- Min Cointegration Score: 50
```

---

## Appendix C: Glossary

**ADF (Augmented Dickey-Fuller)**: Statistical test for stationarity. More negative = more stationary.

**Beta**: Hedge ratio from OLS regression (GC ~ SI). Used for position sizing.

**Cointegration**: Two time series share a common stochastic trend (mean-reverting spread).

**Cointegration Score**: Normalized quality metric (0-100) combining ADF, Hurst, HalfLife.

**Cooldown**: State after stop loss where same-direction re-entry is blocked until Z-Score normalizes.

**ddof**: Delta degrees of freedom (0 = population, 1 = sample) in standard deviation calculation.

**Hurst Exponent**: Measure of time series memory. H < 0.5 = mean-reverting, H > 0.5 = trending.

**MD5 hash**: Cryptographic hash used for cache invalidation (detects data file changes).

**Parquet**: Columnar file format for fast I/O (15s CSV load → 0.5s Parquet load).

**R/S Analysis**: Rescaled Range analysis for calculating Hurst exponent.

**Sharpe ratio**: Risk-adjusted return metric. In this system: computed per trade, not annualized.

**Slippage**: Execution price difference from mid price. Measured in ticks (1 tick GC = $10).

**Spread**: Log_GC - Beta * Log_SI - Alpha. Stationary time series for mean reversion.

**Z-Score**: (Spread - Mean) / Std. Measures how many standard deviations spread is from mean.

---

**Document Version**: 1.0
**Last Updated**: 2026-02-05
**Total Lines**: 263
