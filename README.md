# GC/SI Spread Trading Backtest System

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. **Harmonized with Sierra Chart v2.0** (< 0.01% difference on all indicators, automated trading via ACSIL).

## Project Status

| Milestone | Status |
|-----------|--------|
| Python backtest | COMPLETE |
| Grid search (1-min + 5-min) | COMPLETE |
| Walk-forward validation | COMPLETE |
| Statistical validation (Monte Carlo, bootstrap) | COMPLETE |
| Sierra Chart v2.0 (automated trading) | IN PROGRESS |
| Replay validation | **COMPLETE** (5/5 trades match, 85% signal concordance on 158K bars) |

**Production config**: `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL4.0` (5-min pure Z-Score)
- 5-min best: **$59,172** PnL, PF 2.74, 0% slippage attrition
- Breakeven slippage: 8.0 ticks (6x margin vs nominal)
- Block bootstrap P(loss over 100 trades): 19.1% -- sizing 0.5x recommended

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
pytest tests/ -v                       # 223 tests
pytest tests/ --cov=src                # With coverage report
```

### Grid Search and Walk-Forward

```bash
# YAML-driven grid search (unified runner)
python scripts/run_grid_search.py --config configs/experiments/grid_3y.yaml          # 32,400 configs 1-min
python scripts/run_grid_search.py --config configs/experiments/grid_5min.yaml        # 155,520 configs 5-min
python scripts/run_grid_search.py --config configs/experiments/grid_5min_test.yaml   # 12 configs (smoke test)

# YAML-driven walk-forward
python scripts/run_walk_forward.py --config configs/experiments/wf_3y.yaml           # Full 3-year analysis
python scripts/run_walk_forward.py --config configs/experiments/wf_5min_ztp.yaml     # 34-window 5-min zTP
```

## Project Structure

```
backtest_gc_si/
├── config/
│   └── strategy_params.yaml            <- All strategy parameters
├── data/
│   ├── raw/                            <- Sierra Chart CSV exports
│   └── processed/                      <- Parquet cache (auto-generated)
├── src/                                <- Source code
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
│   ├── archive_manager.py             <- Archive + campaign management
│   └── run_helpers.py                  <- Shared utilities for runners
├── scripts/                            <- Execution scripts
│   ├── run_grid_search.py              <- Generic YAML-driven grid search
│   ├── run_walk_forward.py             <- Generic YAML-driven walk-forward
│   └── run_*.py                        <- Special scripts (custom logic)
├── configs/experiments/                <- YAML experiment configs
├── tests/                              <- 223 unit tests (pytest)
├── docs/
│   ├── STRATEGY.md                     <- Strategy theory and indicator formulas
│   └── ARCHITECTURE.md                 <- System architecture and module guide
├── DOC SIERRA/                         <- Sierra Chart ACSIL source + docs
├── output/
│   ├── archive/                        <- Archived backtest results (classified)
│   ├── rankings/                       <- Generated rankings + DASHBOARD.md
│   ├── latest/                         <- Last single-run output
│   └── production/                     <- Active paper trading config
├── CLAUDE.md                           <- Instructions for Claude Code
├── CHANGELOG.md                        <- Full optimization history
└── README.md                           <- This file
```

## Documentation

- **[Strategy Theory](docs/STRATEGY.md)** -- Cointegration, indicators, entry/exit logic, sizing
- **[Architecture](docs/ARCHITECTURE.md)** -- Data pipeline, modules, config system, testing
- **[Changelog](CHANGELOG.md)** -- Detailed optimization history and results

## Configuration (Production)

All parameters are in `config/strategy_params.yaml`.

### Indicators (5-min)
| Parameter | Value | Description |
|-----------|-------|-------------|
| beta_lookback | 2640 | Rolling OLS window |
| zscore_period | 20 | Z-Score normalization window |
| correlation_period | 30 | Pearson correlation window |
| adf_hurst_period | 26 | ADF/Hurst calculation window |

### Entry Conditions
| Parameter | Value |
|-----------|-------|
| Z-Score Entry | +/- 3.5 |
| Correlation min | > 0.60 |
| Cointegration Score min | >= 40 |

### Exit Conditions (pure Z-Score)
| Exit Type | LONG | SHORT |
|-----------|------|-------|
| Z-Score TP | Z >= +1.0 (overshoot) | Z <= -1.0 (overshoot) |
| Z-Score SL | Z <= -4.0 | Z >= +4.0 |

### Transaction Costs
| Component | Value |
|-----------|-------|
| Commission | $4.00 round-trip per contract (standard), $1.50 (micro) |
| Slippage | 1 tick per leg (GC: $10, SI: $25) |

### Contract Modes
| Mode | GC | SI |
|------|----|----|
| Standard | GC (100 oz, $100/pt) | SI (5,000 oz, $5,000/pt) |
| Micro | MGC (10 oz, $10/pt) | SIL (1,000 oz, $1,000/pt) |

## Sierra Chart v2.0 Integration

Python and Sierra Chart produce **identical** indicator values (median Z-Score delta: 0.005, correlation 0.957 on 158K bars).
v2.0 adds automated spread trading: state machine, multi-symbol orders (100% unmanaged), Z-Score + dollar exits.

**Replay validation complete**: 5/5 trades match (directions, contracts, Beta identical). Cross-symbol replay limitation documented (SI fills at live price, no impact on paper trading).

## Key Research Findings

- **5-min pure Z-Score = dominant mode** (best PnL, 0% slippage attrition)
- **1-min dollar exits = dead end** (2 ticks slippage kills profitability)
- **Regime filters = dead end** (6 tested, none survives walk-forward OOS)
- **zTP=-1.0 (overshoot) = game changer** (doubles PnL vs zTP=1.0)
- **Known risk**: regime-dependent (2023-2024 losing, 2025-2026 profitable)

## Data

- **Period**: Jan 2023 -- Jan 2026 (~3 years, 760+ trading days)
- **1-min bars**: 801,499 synchronized
- **5s bars**: 4,604,839 synchronized
- **Source**: Sierra Chart (GCJ26 Gold, SIH26 Silver)

## Testing

223 tests, all passing. Tests use synthetic data (no dependency on real CSV files).

## Next Steps

1. **Paper trading** 4-8 weeks (min 30 trades, compare vs Python backtest)
2. **Production** go-live (if paper trading validates)

---
*Developed with Claude AI -- January/February 2026*
