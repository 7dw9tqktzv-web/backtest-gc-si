# GC/SI Spread Trading Backtest System

Python backtesting system for a Gold/Silver spread trading strategy based on cointegration and mean reversion. **Harmonized with Sierra Chart v1.5** (< 0.01% difference on all indicators).

## Project Status

| Milestone | Status |
|-----------|--------|
| Python backtest | COMPLETE |
| Walk-forward validation | COMPLETE |
| Sierra Chart v1.5 harmonization | COMPLETE |
| Code refactoring (Phases 1-4) | COMPLETE |
| Paper trading | IN PROGRESS |

**Best config**: `b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50`
- Walk-forward PnL (3 years): **$45,500**
- 207 trades, 58.1% Win Rate, PF 1.58

## Quick Start

### Installation

```bash
cd backtest_gc_si
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt
```

### Run Backtest

```bash
python src/backtest_engine_hybrid.py   # Hybrid backtest (1-min + 5s)
python src/metrics.py                  # Performance analysis + archiving
```

### Run Tests

```bash
pytest tests/ -v                       # 131 tests
pytest tests/ --cov=src                # With coverage report
```

### Grid Search and Walk-Forward

```bash
# YAML-driven grid search (unified runner)
python scripts/run_grid_search.py --config configs/experiments/grid_3y.yaml          # 32,400 configs
python scripts/run_grid_search.py --config configs/experiments/grid_5min_test.yaml   # 12 configs (smoke test)

# YAML-driven walk-forward
python scripts/run_walk_forward.py --config configs/experiments/wf_3y.yaml           # Full 3-year analysis
```

## Project Structure

```
backtest_gc_si/
├── config/
│   └── strategy_params.yaml            <- All strategy parameters
├── data/
│   ├── raw/                            <- Sierra Chart CSV exports
│   └── processed/                      <- Parquet cache (auto-generated)
├── src/                                <- Source code (6,152 lines, 10 modules)
│   ├── common.py                       <- State machine constants + shared functions
│   ├── data_loader.py                  <- CSV loading, sync, Parquet cache
│   ├── indicators.py                   <- Beta, Z-Score, Correlation, ADF, Hurst
│   ├── position.py                     <- Dollar-neutral sizing + PnL calculation
│   ├── backtest_engine_hybrid.py       <- Hybrid backtest engine (1-min + 5s)
│   ├── optimizer.py                    <- Multi-config backtester
│   ├── metrics.py                      <- Performance analysis + archiving
│   ├── grid_search_runner.py           <- Parallel grid search (24 workers)
│   ├── walk_forward_runner.py          <- Walk-forward validation
│   ├── report_generator.py             <- Post-grid-search analysis
│   └── run_helpers.py                  <- Shared utilities for runners
├── scripts/                            <- Execution scripts
│   ├── run_grid_search.py              <- Generic YAML-driven grid search
│   ├── run_walk_forward.py             <- Generic YAML-driven walk-forward
│   └── run_*.py                        <- Special scripts (custom logic)
├── configs/experiments/                <- YAML experiment configs
│   ├── grid_3y.yaml                    <- 32,400 configs (1-min dollar mode)
│   ├── grid_5min.yaml                  <- 155,520 configs (5-min Z-Score mode)
│   ├── grid_5min_test.yaml             <- 12 configs (smoke test)
│   └── wf_*.yaml                       <- Walk-forward configs
├── tests/                              <- 131 unit tests (pytest)
├── docs/
│   ├── STRATEGY.md                     <- Strategy theory and indicator formulas
│   └── ARCHITECTURE.md                 <- System architecture and module guide
├── output/
│   └── archive/                        <- Archived backtest results (classified)
├── CLAUDE.md                           <- Instructions for Claude Code
├── CHANGELOG.md                        <- Full optimization history
└── README.md                           <- This file
```

## Documentation

- **[Strategy Theory](docs/STRATEGY.md)** -- Cointegration, indicators, entry/exit logic, sizing
- **[Architecture](docs/ARCHITECTURE.md)** -- Data pipeline, modules, config system, testing
- **[Changelog](CHANGELOG.md)** -- Detailed optimization history and results

## Configuration

All parameters are in `config/strategy_params.yaml`. Key settings:

### Indicators
| Parameter | Value | Description |
|-----------|-------|-------------|
| beta_lookback | 1320 | Rolling OLS window (~5 trading days) |
| zscore_period | 24 | Z-Score normalization window |
| correlation_period | 24 | Pearson correlation window |
| adf_hurst_period | 96 | ADF/Hurst calculation window |

### Entry Conditions
| Parameter | Value |
|-----------|-------|
| Z-Score Entry | +/- 3.0 |
| Correlation min | > 0.60 |
| Cointegration Score min | >= 50 |

### Exit Conditions
| Exit Type | LONG | SHORT |
|-----------|------|-------|
| Z-Score TP | Z >= -2.0 | Z <= +2.0 |
| Z-Score SL | Z <= -4.5 | Z >= +4.5 |
| Dollar TP | +$500 | +$500 |
| Dollar SL | -$1,200 | -$1,200 |

### Transaction Costs
| Component | Value |
|-----------|-------|
| Commission | $4.00 round-trip per contract |
| Slippage | 1 tick per leg (GC: $10, SI: $25) |

## Sierra Chart v1.5 Harmonization

Python and Sierra Chart produce **identical** indicator values (< 0.01% difference):

| Indicator | Difference |
|-----------|------------|
| Beta | 0.00% |
| ADF Statistic | 0.01% |
| Correlation | 0.00% |
| Z-Score | 0.03% |
| Hurst | 0.01% |

Sierra Chart settings must match Python config (see [STRATEGY.md](docs/STRATEGY.md) for details).

## Walk-Forward Results (48 windows, 3 years)

| Config | PnL | Trades | Win Rate | PF | Positive Windows |
|--------|-----|--------|----------|----|------------------|
| **NO_HMM** | **$45,500** | 207 | 58.1% | 1.58 | 47% |
| HMM_DIAG | $40,221 | 160 | 60.2% | 2.39 | 60% |

## Data

- **Period**: Jan 2023 -- Jan 2026 (~3 years)
- **1-min bars**: 801,499 synchronized
- **5s bars**: 4,604,839 synchronized
- **Source**: Sierra Chart (GCJ26 Gold, SIH26 Silver)

## Testing

131 tests across 7 files, all passing in ~0.4s:

| Module | Tests | Coverage |
|--------|-------|----------|
| common.py | 32 | 100% |
| indicators.py | 33 | 72% |
| position.py | 26 | 48% |
| backtest_engine_hybrid.py | 13 | ~30% |
| optimizer.py | 9 | ~25% |
| metrics.py | 12 | ~15% |
| run_helpers.py | 6 | ~60% |

## Next Steps

1. **Paper trading** on Sierra Chart with optimal config
2. **Validate** paper trades vs Python backtest
3. **Production** after validation (2-4 weeks minimum)

---
*Developed with Claude AI -- January/February 2026*
