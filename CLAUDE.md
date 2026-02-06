# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.5).

**Current status**: **Sierra Chart v1.5 harmonized with Python** (< 0.01% difference on all indicators). Best config: **b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50** (NO_HMM) - $45,500 walk-forward PnL. **Ready for paper trading on Sierra Chart**. See `CHANGELOG.md` for detailed backtest history.

## Commands

```bash
# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/ -v                       # Run all tests
pytest tests/ --cov=src                # Run with coverage
pytest tests/test_common.py -v         # Run specific test file

# Test modules manually
python src/data_loader.py
python src/indicators.py
python src/position.py

# Run backtests
python src/backtest_engine_hybrid.py   # Hybrid 1-min + 5s (recommended)
python src/metrics.py                  # Performance analysis + archiving

# Grid search (YAML-driven, unified runner)
python scripts/run_grid_search.py --config configs/experiments/grid_3y.yaml          # 32,400 configs 1-min
python scripts/run_grid_search.py --config configs/experiments/grid_5min.yaml        # 155,520 configs 5-min
python scripts/run_grid_search.py --config configs/experiments/grid_beta_long.yaml   # 4,050 configs beta long
python scripts/run_grid_search.py --config configs/experiments/grid_ztp_extended.yaml # Extended Z-Score TP
python scripts/run_grid_search.py --config configs/experiments/grid_5min_test.yaml   # 12 configs smoke test

# Walk-forward (YAML-driven, unified runner)
python scripts/run_walk_forward.py --config configs/experiments/wf_base.yaml         # 6-window validation
python scripts/run_walk_forward.py --config configs/experiments/wf_3y.yaml           # Full 3-year analysis
python scripts/run_walk_forward.py --config configs/experiments/wf_5min_ztp.yaml     # 34-window 5-min zTP
python scripts/run_walk_forward.py --config configs/experiments/wf_beta_long.yaml    # 34-window beta long

# Special scripts (custom logic, not YAML-izable)
python scripts/run_grid_no_tp_zscore.py        # 6 TP_ZSCORE modes with manual loop
python scripts/run_grid_search_extended_1tick.py  # 3 TP_ZSCORE modes + custom worker
python scripts/run_grid_search_top100_1tick.py    # Retest top 100 from CSV + comparison
python scripts/run_top5_archive.py                # Archive top 5 with metrics + equity curve

# Post-grid-search analysis
python src/report_generator.py output/grid_search_xxx.csv --description "..."
python src/report_generator.py output/grid.csv -d "desc" --archive --timeframe 1min --slippage 1tick

# Archive management
python src/archive_manager.py --action archive-top --csv output/grid.csv --n 20 --timeframe 1min --slippage 1tick
python src/archive_manager.py --action generate-rankings
python src/archive_manager.py --action dashboard
python src/archive_manager.py --action list --timeframe 1min --exit-mode dollar

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

### Data Pipeline
```
Sierra Chart CSV -> data_loader.py -> [Parquet cache] -> indicators.py -> backtest_engine_hybrid.py -> metrics.py
                      (sync GC/SI)    (data/processed/)   (calculate)    (signals + position + exits)  (analyze)

Sierra Chart 5s CSV -> data_loader.py (load_5s_data) -> [Parquet cache] -> backtest_engine_hybrid.py
                         (sync 5s)                      (data/processed/)    (5s price monitoring)

optimizer.py: loads data once -> loops N configs -> calculate_all_indicators -> run_hybrid_backtest -> comparison table
report_generator.py: grid search CSV -> latest_summary.txt + CHANGELOG.md section (CLI post-analysis)
```

### Source Files (src/)
```
Total: ~6,400 lines
├── metrics.py               (950 lines)  - Performance analysis, equity curve, archiving
├── indicators.py            (811 lines)  - Beta, Z-Score, Correlation, ADF, Hurst
├── backtest_engine_hybrid.py(597 lines)  - Main backtest engine (1min + 5s)
├── archive_manager.py       (577 lines)  - Structured archive management (5 public functions)
├── optimizer.py             (564 lines)  - Multi-config optimization
├── grid_search_runner.py    (552 lines)  - Parallel grid search
├── report_generator.py      (545 lines)  - Post-grid-search analysis + archive integration
├── data_loader.py           (533 lines)  - CSV loading, sync, Parquet cache
├── walk_forward_runner.py   (406 lines)  - Walk-forward validation
├── position.py              (398 lines)  - Dollar-neutral sizing
├── common.py                (260 lines)  - Shared constants and functions
├── run_helpers.py           (174 lines)  - Shared utilities for run scripts
└── __init__.py               (60 lines)
```

### Key Entry Points
- `load_and_prepare_data()` in `data_loader.py` - returns `(df, config, stats)` for 1-min data
- `resample_to_5min(df)` in `data_loader.py` - resamples 1-min to 5-min with Parquet cache
- `load_5s_data(config)` in `data_loader.py` - returns df_5s synchronized
- `calculate_all_indicators(df, config)` in `indicators.py` - returns df with all indicators
- `calculate_position_size(gc_price, si_price, beta, config)` in `position.py` - returns sizing dict
- `calculate_trade_pnl(direction, entry_gc, entry_si, exit_gc, exit_si, gc_contracts, si_contracts, config)` in `position.py` - returns PnL dict
- `run_hybrid_backtest(df_1min, df_5s, config)` in `backtest_engine_hybrid.py` - returns trades DataFrame
- `run_metrics()` in `metrics.py` - analyzes backtest results, generates report + equity curve, archives everything
- `run_optimization(configs_list)` in `optimizer.py` - loads data once, runs N backtests, returns comparison table
- `apply_overrides(config, overrides)` in `optimizer.py` - applies dotted-key overrides to config dict
- `archive_config()` in `archive_manager.py` - archives a single config with metrics JSON + config YAML
- `archive_top_n_from_grid()` in `archive_manager.py` - archives top N from grid search CSV
- `generate_rankings()` in `archive_manager.py` - generates ranking CSVs + DASHBOARD.md
- `generate_dashboard()` in `archive_manager.py` - generates DASHBOARD.md with summary tables
- `list_configs()` in `archive_manager.py` - lists archived configs as DataFrame

### Configuration
All parameters are in `config/strategy_params.yaml`. Never hardcode values.
Key field: `indicators.period` defines the calculation timeframe (1min, 5min, 15min, 1h, 1d).

### Archiving Structure (archive_manager.py)
```
output/
├── archive/                         <- Structured archive (git-tracked: config.yaml + metrics.json)
│   └── {timeframe}/                 <- 1min, 5min
│       └── {exit_mode}/             <- dollar, zscore, hybrid
│           └── {config_name}/       <- e.g. b1320_zp24_cp30_adf96_zE3.5_co50_TP300_SL800
│               ├── config.yaml      <- Config snapshot (saved once per config)
│               └── {result_type}/   <- grid_search, walk_forward, top_pnl, top_sharpe
│                   ├── {slip}_metrics.json   <- Metrics (JSON, parsable)
│                   └── {slip}_trades.csv     <- Trades (gitignored, large)
├── rankings/                        <- Generated ranking CSVs + DASHBOARD.md
│   ├── {tf}_{em}_top{n}.csv        <- Per-category ranking
│   ├── global_top50.csv            <- Cross-category ranking
│   ├── walk_forward_best.csv       <- Walk-forward ranking (if any)
│   └── DASHBOARD.md                <- Human-readable summary
├── raw/                             <- Moved raw grid search CSVs (date-prefixed)
│   └── grid_search/
├── latest/                          <- Last single-run output (quick access)
│   ├── backtest_hybrid.csv
│   ├── metrics_report.txt
│   └── equity_curve.png
└── production/                      <- Active paper trading config

CLI: python src/archive_manager.py --action {archive-top|generate-rankings|dashboard|list}
```

Git tracking: config.yaml and metrics.json are tracked; large files (*_trades.csv, *_equity.png) are gitignored.

## Trading Logic

### State Machine (backtest_engine_hybrid.py)
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
- LONG spread: Z-Score <= -3.5, Correlation > 0.60, Cointegration Score >= 50, Hurst < hurst_max
- SHORT spread: Z-Score >= 3.5, Correlation > 0.60, Cointegration Score >= 50, Hurst < hurst_max
- Note: `correlation_min` has no practical impact (always > 0.80 when other conditions met)
- Note: `hurst_max` is redundant with Cointegration Score (Hurst < 0.45 on all traded bars). Default 1.0 = disabled.

### Exit Conditions (OR logic)
| Condition | LONG | SHORT |
|-----------|------|-------|
| TP Z-Score | >= zscore_tp_long | <= zscore_tp_short |
| SL Z-Score | <= zscore_sl_long | >= zscore_sl_short |
| TP Dollars | +pnl_take_profit | +pnl_take_profit |
| SL Dollars | pnl_stop_loss | pnl_stop_loss |

Default values (1-min best config): TP $1000 / SL -$1200, zTP disabled.

- `exit.zscore_tp_enabled` (default false): set to true to enable TP_ZSCORE exits (disabled in best 1mn config)
- `exit.zscore_tp_min_pnl` (default None): minimum PnL required for TP_ZSCORE exit (e.g., 100 = require $100 profit)

### Key Rules
- After take profit: immediate re-entry allowed if conditions met
- After stop loss: cooldown until Z-Score returns to +/-1.0 (direction-specific)
- Cooldown only blocks same direction (COOLDOWN_LONG blocks LONG, not SHORT)
- Reversal allowed: close LONG and open SHORT on same bar
- Exit priority: SL_DOLLAR > SL_ZSCORE > TP_DOLLAR > TP_ZSCORE
- Single position at a time
- Dollar-based exits (TP $300 / SL -$600) handled in backtest_engine_hybrid.py

## Backtest Engine

### backtest_engine_hybrid.py (Hybrid 1-min + 5s)
- Indicators and signals computed on 1-minute bars (normal lookbacks)
- When in position, scans 5-second bars between consecutive 1-min bars
- Dollar exits (SL/TP) detected on 5s Last prices (precise intra-bar detection)
- Z-Score exits checked on 1-min bars only (after 5s scan finds no dollar trigger)
- 5s data used ONLY for price monitoring, no indicators recalculated on 5s

#### Exit priority per 1-min bar:
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

Commission: $4.00 round-trip per contract ($2.00 per side). Slippage: 1 tick per leg (default in YAML, 2 ticks used in grid searches).

## Position Sizing (position.py)

```
NotionalGC = GC_price * $100
NotionalSI = SI_price * $5000
GC_contracts = round( (NotionalSI / NotionalGC) * Beta ) , minimum 1
```

Beta varies from ~0.03 to ~6.3 on traded bars -> GC contracts range from 1 to 6.

## DataFrame Columns

After `calculate_all_indicators()`:
- Prices: `Last_GC`, `Last_SI`, `Log_GC`, `Log_SI`
- Regression: `Beta`, `Alpha`
- Spread: `Spread`, `Spread_Mean`, `Spread_Std`, `ZScore`
- Quality: `Correlation`, `ADF_Statistic`, `Hurst`, `HalfLife`, `Cointegration_Score`

Signal generation happens inside `backtest_engine_hybrid.py` and is not stored as separate DataFrame columns.

## Hardware

- **CPU**: AMD Ryzen 9 7900X -- 12 cores / 24 threads @ 4.70 GHz
- **RAM**: 64 Go (63.2 Go utilisable)
- **GPU**: 8 Go VRAM (multi-GPU)
- **Stockage**: 2.73 TB (SSD)
- **OS**: Windows 64-bit

**Parallelisme** : Utiliser `multiprocessing.Pool(24)` pour les grid searches (24 threads via hyperthreading). Benchmark: +17.5% vs 12 workers. Chaque worker consomme ~600 Mo RAM (df_5min + df_5s), donc 24 workers ~= 15 Go sur 64 Go disponibles.

## Conventions

- Code in English, comments in French
- Timezone: Chicago Time (CT)
- Session: 17:30 - 15:30 CT (22 hours, 264 bars 5-min per day)
- User level: Python beginner, Sierra Chart expert
- Approach: Pedagogical, step-by-step with explanations

## Gotchas

### Terminal Windows
- **No emojis/accents in print()**: Windows cp1252 encoding crashes on special characters

### Strategy Parameters
- **Slippage is the strategy killer**: 1 tick -> profitable; 2 ticks -> destroyed
- **zscore_period >= 30**: Produces 0 profitable configs on 3-year data
- **zscore_entry=-3.5**: Only viable threshold (112/115 profitable configs)
- **correlation_min is redundant**: Always > 0.80 when Z-Score + Coint conditions met
- **hurst_max is redundant**: Hurst < 0.45 on all traded bars (use Cointegration Score instead)

### Code Quirks
- **ddof inconsistency**: Beta uses ddof=0, Z-Score uses ddof=1 (low impact but confusing)
- **hmmlearn covariance bug**: Getter returns (n_components, n_features, n_features), setter expects (n_components, n_features) - use `model._covars_` directly

### Grid Search
- **24 workers optimal**: AMD Ryzen 9 7900X with 24 threads, each worker ~600 MB RAM
- **grid_temp/ grows to 11+ GB**: Delete after grid search to free space
- **indicator_cache_*.pkl**: Temporary files, safe to delete after run

### Git
- **Never git add -A**: Risk of committing .env or credentials - add files by name

## Data

- **Source**: Sierra Chart CSV exports (GCJ26 Gold futures, SIH26 Silver futures)
- **Period**: 2023-01-26 to 2026-01-30 (~3 years, 760+ trading days)
- **1-min bars**: 801,499 synchronized
- **5s bars**: 4,604,839 synchronized
- **Parquet cache**: `data/processed/` (auto-invalidated by MD5 hash). Indicators are NOT cached (depend on config).

## Key Research Conclusions

### HMM Regime Filter (PYTHON-ONLY - Feb 2026)
HMM filter tested and validated. Limits losses in unfavorable market conditions.
- **Status**: Python-only feature (cannot be replicated bar-by-bar in Sierra Chart)
- **Code**: `regime.py` to be recreated when needed (was removed during cleanup)
- **Walk-forward comparison** (48 windows):
  - NO_HMM: $45,500 PnL, 207 trades, 47% positive windows
  - HMM_DIAG: $40,221 PnL, 160 trades, 60% positive windows
- **Trade-off**: NO_HMM = max PnL, HMM = better consistency + loss protection
- **Config**: `advanced.regime_filter` in YAML (disabled for Sierra Chart deployment)
- **Future work**: Refine HMM or find Sierra Chart-compatible alternative

### 1-min timeframe (completed)
- **Slippage is the strategy killer**: 1 tick -> profitable; 2 ticks -> destroyed
- **zscore_entry=-3.5** is the only viable threshold on 3-year data (112/115 profitable configs)
- **zscore_period >= 30** produces zero profitable configs on 3-year data
- **TP_ZSCORE disabled** is optimal: exits fire when dollar move is too small to cover costs
- **`correlation_min` is redundant**: always > 0.80 when Z-Score + Coint conditions met
- **`hurst_max` is redundant**: Hurst < 0.45 on all traded bars (captured by Cointegration Score)
- **TP/SL dollar thresholds** are the most impactful parameters overall
- **Strategy is regime-dependent**: 2023 weak, 2024-2025 profitable (walk-forward confirms)

### Bug fixes applied (indicators.py, backtest_engine_hybrid.py, optimizer.py, metrics.py)
- **Bug 1**: ADF regression now includes intercept (was missing mu term)
- **Bug 4**: Removed incorrect `spread == 0` skip in ADF calculation
- **Bug 5**: `zscore_tp_min_pnl` filter now uses net PnL (was using gross)
- **Sharpe ratio fix**: Harmonized Sharpe calculation (mean/std per trade, not annualized) between optimizer.py and metrics.py

### Best Configs Summary
See `CHANGELOG.md` for detailed tables. Key findings:
- **5-min pure Z-Score** surpasses 1-min dollar exits (+52% PnL with 2 ticks slippage)
- **zTP=-1.0 (overshoot)** doubles PnL vs zTP=1.0 ($45,224 vs $22,604)
- **b3960 (15 days)** more robust in walk-forward than b2640 (10 days)
- **Strategy is regime-dependent**: profitable 2025-2026, losing 2023-2024

## Sierra Chart Integration (v1.5 - HARMONIZED)

### Indicator Harmonization (Feb 2026)
Python and Sierra Chart v1.5 now produce **identical indicator values** (< 0.01% difference):

| Indicator | Python vs Sierra | Status |
|-----------|------------------|--------|
| Beta | 0.000000 (0.00%) | IDENTICAL |
| ADF Statistic | 0.000272 (0.01%) | NEGLIGIBLE |
| Correlation | 0.000035 (0.00%) | NEGLIGIBLE |
| Z-Score | 0.000334 (0.03%) | NEGLIGIBLE |
| Hurst | 0.000113 (0.01%) | NEGLIGIBLE |

### Key Changes Made
1. **ADF Statistic (v1.4 -> v1.5)**: Added intercept (mu) to regression, matching Python's implementation
2. **Session times**: GC and SI charts must use identical session times (17:00-16:00 CT)
3. **Config alignment**: Python YAML updated to match Sierra Chart optimal settings

### Sierra Chart Files
- **Indicator**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.5.cpp`
- **Spreadsheet export**: `DOC SIERRA/files/DefaultSpreadsheetStudy.txt`
- **Validation scripts**: `compare_sierra_v3.py`, `check_float_precision.py`

### Sierra Chart Settings (must match Python)
```
Beta Lookback: 1320
Z-Score Period: 24
Correlation Period: 24
ADF/Hurst Period: 96
Z-Score Upper Threshold: 3
Z-Score Lower Threshold: -3
Min Cointegration Score: 50
Session Start: 17:00:00 CT
Session End: 15:30:00 CT
```

## Next Steps (TODO)

### Priority 1 -- Paper Trading on Sierra Chart (IN PROGRESS)
Indicator harmonization complete. Remaining tasks for paper trading:

1. **Signal generation in Sierra Chart**: Implement entry/exit logic in v1.5
   - Entry: Z-Score crosses +/-3.0 with Coint Score >= 50
   - Exit: Z-Score TP at +/-2.0, SL at +/-4.5
   - Cooldown logic after stop loss

2. **Position sizing**: Implement dollar-neutral Beta sizing
   - SI: 1 contract (fixed)
   - GC: round((SI_notional / GC_notional) * Beta)

3. **Paper trade execution**: Configure Sierra Chart simulated trading
   - Set up trade simulation on GCJ26 and SIH26
   - Monitor fills, slippage, and execution quality

4. **Validation**: Compare paper trades vs Python backtest
   - Same signals at same timestamps?
   - Same position sizes?
   - Similar PnL per trade?

**Target config**: `b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50` (NO_HMM)
- Walk-forward PnL: $45,500
- 207 trades over 3 years
- 58.1% Win Rate, PF 1.58

### Priority 2 -- Code Quality
- **Add pytest tests**: unit tests for indicators, position sizing, backtest engine, optimizer, metrics (131 tests done)
- **Consolidate run_*.py scripts**: DONE (Phase 1: -66% code, Phase 2: unified YAML runners)
  - 10 scripts replaced by 2 generic runners + 10 YAML configs in `configs/experiments/`
  - 4 special scripts moved to `scripts/` (custom logic not YAML-izable)
- **Clean up validation scripts**: archive or remove compare_*.py, check_*.py, investigate_*.py
- **Increase test coverage**: position.py (48%) needs more tests

### Priority 3 -- Production Deployment
- Validate paper trading results (minimum 2-4 weeks)
- Compare paper vs backtest metrics (Win Rate, PF, avg trade)
- Implement live order execution via Sierra Chart DTC protocol
- Add risk management (daily loss limit, position size caps)
- Document go-live checklist

## Known Code Issues (non-blocking)

- **Bug 2 (ddof)**: Beta uses ddof=0, Z-Score uses ddof=1. Inconsistent but low impact.
- **Bug 3 (Hurst)**: Single-segment implementation, 3-5 point regression. Acceptable for relative ranking.
- **run_hybrid_backtest() = 350+ lines**: 5+ nesting levels. Needs decomposition but requires tests first.
- **Detailed analysis**: see `analyse.md` for comprehensive code review.

## Performance Optimizations
- **Vectorized Beta/ADF**: ~50x speedup using pandas rolling
- **Vectorized Hurst**: ~42x speedup (4.2s -> 0.1s on 160k bars)
- **5s scan short-circuit**: ~12x speedup in pure_zscore mode
- **Pool(24)**: 24 workers via hyperthreading (+17.5% vs 12)
- **5-min resampling**: Parquet cache in `data/processed/`

## Claude Code Skills

### /backtest-runner
Runs the hybrid backtest and affiche les resultats formates. Compare automatiquement avec le run precedent.
- Lance `backtest_engine_hybrid.py` puis `metrics.py`
- Affiche les metriques cles et la comparaison avec le run precedent

### /optimize
Teste differents parametres via langage naturel en francais. Supporte le grid search avec la syntaxe "/" (ex: "teste beta 1320/2640 avec TP 400/600").
- Utilise `optimizer.py` : charge les donnees 1 fois, boucle sur N configs en memoire
- Ne modifie PAS le YAML pendant les tests (travaille en memoire)

### /compare
Compare tous les backtests archives dans `output/archive/index.csv`.
- Affiche un tableau trie par PnL net (ou autre critere)

### /grid-search
Lance un grid search massif en background (milliers de configs), genere un rapport et met a jour le CHANGELOG.
- Utilise `report_generator.py` pour l'analyse post-grid-search
- Pattern Bash background + haiku post-analyse
- Produit: CSV de resultats, `output/latest_summary.txt`, section CHANGELOG.md

## Project Structure

```
backtest_gc_si/
├── config/
│   └── strategy_params.yaml    # All strategy parameters
├── data/
│   ├── raw/                    # Sierra Chart CSV exports (gitignored)
│   └── processed/              # Parquet cache (auto-generated)
├── docs/                       # Documentation
│   ├── STRATEGY.md             # Strategy theory and indicator formulas
│   └── ARCHITECTURE.md         # Project architecture post-refactoring
├── src/                        # Main source code (~6,400 lines)
│   ├── archive_manager.py
│   ├── backtest_engine_hybrid.py
│   ├── common.py
│   ├── data_loader.py
│   ├── grid_search_runner.py
│   ├── indicators.py
│   ├── metrics.py
│   ├── optimizer.py
│   ├── position.py
│   ├── report_generator.py
│   ├── run_helpers.py
│   └── walk_forward_runner.py
├── tests/                      # pytest tests (149 tests)
│   ├── conftest.py
│   ├── test_archive_manager.py
│   ├── test_backtest_engine_hybrid.py
│   ├── test_common.py
│   ├── test_indicators.py
│   ├── test_metrics.py
│   ├── test_optimizer.py
│   ├── test_position.py
│   └── test_run_helpers.py
├── scripts/                    # Execution scripts
│   ├── run_grid_search.py      # Generic YAML-driven grid search runner
│   ├── run_walk_forward.py     # Generic YAML-driven walk-forward runner
│   ├── run_grid_no_tp_zscore.py         # Special: 6 TP_ZSCORE modes
│   ├── run_grid_search_extended_1tick.py # Special: custom worker
│   ├── run_grid_search_top100_1tick.py   # Special: retest from CSV
│   └── run_top5_archive.py              # Special: archiving workflow
├── configs/
│   └── experiments/            # YAML configs for grid search & walk-forward
│       ├── grid_3y.yaml        # 32,400 configs 1-min dollar mode
│       ├── grid_5min.yaml      # 155,520 configs 5-min zscore mode
│       ├── grid_beta_long.yaml # 4,050 configs beta long
│       ├── grid_ztp_extended.yaml # 45,360 configs zscore TP extended
│       ├── grid_5min_test.yaml # 12 configs smoke test
│       ├── grid_5min_hybrid.yaml # 4,032 configs hybrid
│       ├── wf_base.yaml        # Walk-forward 6 windows
│       ├── wf_3y.yaml          # Walk-forward 3 years
│       ├── wf_5min_ztp.yaml    # Walk-forward 5-min zTP
│       └── wf_beta_long.yaml   # Walk-forward beta long
├── output/
│   ├── archive/                # Structured archive (managed by archive_manager.py)
│   ├── rankings/               # Generated ranking CSVs + DASHBOARD.md
│   ├── raw/                    # Moved raw grid search CSVs
│   ├── latest/                 # Last single-run output (quick access)
│   └── *.csv                   # Grid search results
├── DOC SIERRA/                 # Sierra Chart files (gitignored)
├── CLAUDE.md                   # This file
├── CHANGELOG.md                # Optimization history
└── analyse.md                  # Code analysis
```

## Git Tracking

`.gitignore` exclut : `.venv/`, `__pycache__/`, `data/raw/`, `DOC SIERRA/`, `.idea/`, `.claude/`, `results/`, `output_old/`

`output/` uses selective tracking: `archive/` and `rankings/` are tracked (config.yaml + metrics.json), but large files (*_trades.csv, *_equity.png) are gitignored.

## Testing

### Test Structure
```
tests/
├── conftest.py                      # Shared fixtures (sample_config, sample_prices_df, etc.)
├── test_archive_manager.py          # 18 tests - Archive management system
├── test_common.py                   # 32 tests, 100% coverage
├── test_indicators.py               # 33 tests, 72% coverage
├── test_position.py                 # 26 tests, 48% coverage
├── test_backtest_engine_hybrid.py   # 13 tests
├── test_optimizer.py                # 9 tests
├── test_metrics.py                  # 12 tests
└── test_run_helpers.py              # 6 tests
```

### Running Tests
```bash
pytest tests/ -v                    # All tests (149 tests)
pytest tests/ --cov=src             # With coverage report
pytest tests/test_common.py -v      # Single file
pytest -k "test_long"               # Tests matching pattern
```

### Test Coverage (as of 2026-02)
- **common.py**: 100% - Entry/exit conditions, PnL calculation
- **archive_manager.py**: covered (18 tests) - Archive, rankings, dashboard, list
- **indicators.py**: 72% - Z-Score, Beta, Correlation, Hurst, ADF
- **position.py**: 48% - Position sizing, transaction costs
- **backtest_engine_hybrid.py**: covered (13 tests)
- **optimizer.py**: covered (9 tests)
- **metrics.py**: covered (12 tests)
- **run_helpers.py**: covered (6 tests)

### Adding New Tests
Tests use synthetic data (fixtures in conftest.py) to avoid depending on real CSV files. To add tests:
1. Use `sample_config` fixture for config
2. Use `sample_prices_df` for price data
3. Use `sample_df_with_indicators` for data with indicators

## Reference Files
- `config/strategy_params.yaml` - All strategy parameters
- `CHANGELOG.md` - Full optimization history and detailed results
- `analyse.md` - Code analysis and bug documentation
- `docs/STRATEGY.md` - Strategy theory and indicator formulas
- `docs/ARCHITECTURE.md` - Project architecture post-refactoring
- `output/archive/` - Archived configs with metrics reports
- `output/grid_search_*.csv` - Grid search results
- `output/walk_forward_*.csv` - Walk-forward results
- `output/latest_summary.txt` - Last grid search summary (generated by report_generator.py)
