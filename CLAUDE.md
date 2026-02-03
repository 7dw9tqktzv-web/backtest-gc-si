# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.4).

**Current status**: Walk-forward beta long completed. Best robust config: **b3960 (15 days)** with $24,694 PnL over 34 windows (53% positive). Strategy is **regime-dependent**: profitable 2025-2026, losing 2023-2024. **Next: regime detection filters** before production. See `CHANGELOG.md` for detailed backtest history.

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
python src/signals.py
python src/position.py

# Run backtests
python src/backtest_engine_hybrid.py   # Hybrid 1-min + 5s (recommended)
python src/metrics.py                  # Performance analysis + archiving

# Grid search / walk-forward
python run_grid_search_5min.py         # 155,520 configs 5-min, 3 years, 24 workers (~10h)
python run_grid_search_3y.py           # 32,400 configs 1-min, 3 years, 24 workers
python run_grid_search_beta_long.py    # 4,050 configs beta long (15-30 days)
python run_walk_forward.py             # 6-window walk-forward validation
python run_walk_forward_5min_ztp.py    # 34-window walk-forward 5-min zTP
python run_walk_forward_beta_long.py   # 34-window walk-forward beta long

# Post-grid-search analysis
python src/report_generator.py output/grid_search_xxx.csv --description "..."

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

### Data Pipeline
```
Sierra Chart CSV -> data_loader.py -> [Parquet cache] -> indicators.py -> signals.py -> position.py -> backtest_engine_hybrid.py -> metrics.py
                      (sync GC/SI)    (data/processed/)   (calculate)    (generate)      (sizing)         (simulate)               (analyze)

Sierra Chart 5s CSV -> data_loader.py (load_5s_data) -> [Parquet cache] -> backtest_engine_hybrid.py
                         (sync 5s)                      (data/processed/)    (5s price monitoring)

optimizer.py: loads data once -> loops N configs -> calculate_all_indicators -> run_hybrid_backtest -> comparison table
report_generator.py: grid search CSV -> latest_summary.txt + CHANGELOG.md section (CLI post-analysis)
```

### Key Entry Points
- `load_and_prepare_data()` in `data_loader.py` - returns `(df, config, stats)` for 1-min data
- `resample_to_5min(df)` in `data_loader.py` - resamples 1-min to 5-min with Parquet cache
- `load_5s_data(config)` in `data_loader.py` - returns df_5s synchronized
- `calculate_all_indicators(df, config)` in `indicators.py` - returns df with all indicators
- `generate_signals(df, config)` in `signals.py` - returns df with Signal, Exit_Signal, Exit_Reason, State columns
- `build_trade_list(df)` in `signals.py` - returns a DataFrame with one row per trade
- `calculate_position_size(gc_price, si_price, beta, config)` in `position.py` - returns sizing dict
- `calculate_trade_pnl(direction, entry_gc, entry_si, exit_gc, exit_si, gc_contracts, si_contracts, config)` in `position.py` - returns PnL dict
- `run_hybrid_backtest(df_1min, df_5s, config)` in `backtest_engine_hybrid.py` - returns trades DataFrame
- `run_metrics()` in `metrics.py` - analyzes backtest results, generates report + equity curve, archives everything
- `run_optimization(configs_list)` in `optimizer.py` - loads data once, runs N backtests, returns comparison table
- `apply_overrides(config, overrides)` in `optimizer.py` - applies dotted-key overrides to config dict

### Configuration
All parameters are in `config/strategy_params.yaml`. Never hardcode values.
Key field: `indicators.period` defines the calculation timeframe (1min, 5min, 15min, 1h, 1d).

### Archiving Structure
```
output/archive/
  CLASSEMENT.txt                                     <- Summary with recommendations
  index.csv                                          <- Global index of all runs
  5min/
    top_pnl/                                         <- Top 10 by PnL (01 = best)
      01_b2640_zp20_cp30_adf26_zTP1.0_co40_pnl22604/
      02_...
    top_sharpe/                                      <- Top 10 by Sharpe (01 = best)
      01_b2640_zp20_cp30_adf128_zTP1.0_co50_sh0.361/
      02_...
  1min/
    top_pnl/                                         <- Top 10 by PnL (05+ = robust 3y)
    top_sharpe/                                      <- Top 10 by Sharpe (04+ = robust 3y)

Each folder contains: backtest_hybrid.csv, metrics_report.txt, equity_curve.png, params_snapshot.yaml
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
- Dollar-based exits (TP $300 / SL -$600) handled in backtest engines, not signals.py

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

After `generate_signals()`:
- Signals: `Signal` (1=LONG, -1=SHORT, 0=none), `Exit_Signal` (1=exit), `Exit_Reason` (TP_ZSCORE/SL_ZSCORE), `State`

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
- No emojis or accented characters in print() statements (Windows cp1252 terminal)

## Data

- **Source**: Sierra Chart CSV exports (GCJ26 Gold futures, SIH26 Silver futures)
- **Period**: 2023-01-26 to 2026-01-30 (~3 years, 760+ trading days)
- **1-min bars**: 801,499 synchronized
- **5s bars**: 4,604,839 synchronized
- **Parquet cache**: `data/processed/` (auto-invalidated by MD5 hash). Indicators are NOT cached (depend on config).

## Key Research Conclusions

### 1-min timeframe (completed)
- **Slippage is the strategy killer**: 1 tick -> profitable; 2 ticks -> destroyed
- **zscore_entry=-3.5** is the only viable threshold on 3-year data (112/115 profitable configs)
- **zscore_period >= 30** produces zero profitable configs on 3-year data
- **TP_ZSCORE disabled** is optimal: exits fire when dollar move is too small to cover costs
- **`correlation_min` is redundant**: always > 0.80 when Z-Score + Coint conditions met
- **`hurst_max` is redundant**: Hurst < 0.45 on all traded bars (captured by Cointegration Score)
- **TP/SL dollar thresholds** are the most impactful parameters overall
- **Strategy is regime-dependent**: 2023 weak, 2024-2025 profitable (walk-forward confirms)

### Bug fixes applied (indicators.py, backtest_engine_hybrid.py)
- **Bug 1**: ADF regression now includes intercept (was missing mu term)
- **Bug 4**: Removed incorrect `spread == 0` skip in ADF calculation
- **Bug 5**: `zscore_tp_min_pnl` filter now uses net PnL (was using gross)

### Best Configs Summary
See `CHANGELOG.md` for detailed tables. Key findings:
- **5-min pure Z-Score** surpasses 1-min dollar exits (+52% PnL with 2 ticks slippage)
- **zTP=-1.0 (overshoot)** doubles PnL vs zTP=1.0 ($45,224 vs $22,604)
- **b3960 (15 days)** more robust in walk-forward than b2640 (10 days)
- **Strategy is regime-dependent**: profitable 2025-2026, losing 2023-2024

## Next Steps (TODO)

### Priority 1 -- Regime Detection (CRITICAL)
Strategy is regime-dependent: profitable 2025-2026, losing 2023-2024.
- Create `analyze_regimes.py` to compare winning vs losing periods
- Test filters: volatility (ATR), correlation stability, volume, VIX
- Implement `regime_filter` in backtest engine
- Walk-forward with filter to validate robustness

### Priority 2 -- Code Quality
- **Add pytest tests**: unit tests for indicators, signals, position sizing (112 tests done)
- **Consolidate run_*.py scripts**: reduce duplication (done, -66% code)
- **Remove dead code**: backtest_engine.py deleted (was obsolete)

### Priority 3 -- Production
- Implement regime filter (prerequisite for live trading)
- Deploy best config on Sierra Chart with filter active

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

## Git Tracking

`.gitignore` exclut : `.venv/`, `__pycache__/`, `data/raw/`, `DOC SIERRA/`, `.idea/`, `.claude/`, `output/`, `results/`

## Testing

### Test Structure
```
tests/
├── conftest.py          # Fixtures partagees (sample_config, sample_prices_df, etc.)
├── test_common.py       # Tests common.py (32 tests, 100% coverage)
├── test_indicators.py   # Tests indicators.py (32 tests, 72% coverage)
├── test_signals.py      # Tests signals.py (24 tests, 53% coverage)
└── test_position.py     # Tests position.py (24 tests, 48% coverage)
```

### Running Tests
```bash
pytest tests/ -v                    # All tests (112 tests)
pytest tests/ --cov=src             # With coverage report
pytest tests/test_common.py -v      # Single file
pytest -k "test_long"               # Tests matching pattern
```

### Test Coverage (as of 2026-02)
- **common.py**: 100% - Entry/exit conditions, PnL calculation
- **indicators.py**: 72% - Z-Score, Beta, Correlation, Hurst, ADF
- **signals.py**: 53% - State machine, signal generation
- **position.py**: 48% - Position sizing, transaction costs

### Adding New Tests
Tests use synthetic data (fixtures in conftest.py) to avoid depending on real CSV files. To add tests:
1. Use `sample_config` fixture for config
2. Use `sample_prices_df` for price data
3. Use `sample_df_with_indicators` for data with indicators

## Reference Files
- `config/strategy_params.yaml` - All strategy parameters
- `CHANGELOG.md` - Full optimization history and detailed results
- `analyse.md` - Code analysis and bug documentation
- `output/archive/` - Archived configs with metrics reports
- `output/grid_search_*.csv` - Grid search results
- `output/walk_forward_*.csv` - Walk-forward results
- `output/latest_summary.txt` - Last grid search summary (generated by report_generator.py)
