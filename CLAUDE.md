# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.4).

**Current status**: Strategy NOT viable with 2 ticks slippage on 3-year data (only 0.4% of 32,400 configs profitable, best PnL = +$586). See CHANGELOG.md for full optimization history and results.

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

# Grid search / walk-forward
python run_grid_search_3y.py           # 32,400 configs, 3 years, multiprocessing
python run_walk_forward.py             # 6-window walk-forward validation

# Post-grid-search analysis
python src/report_generator.py output/grid_search_xxx.csv --description "..."

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

### Data Pipeline
```
Sierra Chart CSV -> data_loader.py -> [Parquet cache] -> indicators.py -> signals.py -> position.py -> backtest_engine.py -> metrics.py
                      (sync GC/SI)    (data/processed/)   (calculate)    (generate)      (sizing)      (simulate)           (analyze)

Sierra Chart 5s CSV -> data_loader.py (load_5s_data) -> [Parquet cache] -> backtest_engine_hybrid.py
                         (sync 5s)                      (data/processed/)    (hybrid simulation)

optimizer.py: loads data once -> loops N configs -> calculate_all_indicators -> run_hybrid_backtest -> comparison table
report_generator.py: grid search CSV -> latest_summary.txt + CHANGELOG.md section (CLI post-analysis)
```

### Key Entry Points
- `load_and_prepare_data()` in `data_loader.py` - returns `(df, config, stats)`
- `load_5s_data(config)` in `data_loader.py` - returns df_5s synchronized
- `calculate_all_indicators(df, config)` in `indicators.py` - returns df with all indicators
- `generate_signals(df, config)` in `signals.py` - returns df with Signal, Exit_Signal, Exit_Reason, State columns
- `build_trade_list(df)` in `signals.py` - returns a DataFrame with one row per trade
- `calculate_position_size(gc_price, si_price, beta, config)` in `position.py` - returns sizing dict
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
  {period}/                                          <- Indicator calculation period
    beta{N}_zp{N}_corr{N}_adf{N}/                   <- Indicator parameters
      zE{N}_{N}_zTP{N}_{N}_zSL{N}_{N}_TP{N}_SL{N}_corr{N}_coint{N}/
        backtest_hybrid.csv, metrics_report.txt, equity_curve.png, params_snapshot.yaml
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
- Note: `correlation_min` has no practical impact (always > 0.80 when other conditions met)
- Note: `hurst_max` is redundant with Cointegration Score (Hurst < 0.45 on all traded bars). Default 1.0 = disabled.

### Exit Conditions (OR logic)
| Condition | LONG | SHORT |
|-----------|------|-------|
| TP Z-Score | >= -2.0 | <= +2.0 |
| SL Z-Score | <= -3.5 | >= +3.5 |
| TP Dollars | +$300 | +$300 |
| SL Dollars | -$600 | -$600 |

- `exit.zscore_tp_enabled` (default true): set to false to disable TP_ZSCORE exits entirely (only dollar + SL_ZSCORE)
- `exit.zscore_tp_min_pnl` (default None): minimum PnL required for TP_ZSCORE exit (e.g., 100 = require $100 profit)

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

### backtest_engine_hybrid.py (Hybrid 1-min + 5s) -- RECOMMENDED
- Indicators and signals computed on 1-minute bars (normal lookbacks)
- When in position, scans 5-second bars between consecutive 1-min bars
- Dollar exits (SL/TP) detected on 5s Last prices (more precise than High/Low)
- Z-Score exits checked on 1-min bars only (after 5s scan finds no dollar trigger)
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

**Parallelisme** : Utiliser `multiprocessing.Pool(12)` pour les grid searches et backtests lourds (12 workers = 12 cores a 100%). Chaque worker consomme ~2-3 Go RAM, donc 12 workers ~= 30 Go sur 63 Go disponibles (~28 Go libres pour l'OS).

## Conventions

- Code in English, comments in French
- Timezone: Chicago Time (CT)
- Session: 17:30 - 15:00 CT
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

- **Slippage is the strategy killer**: 1 tick -> profitable; 2 ticks -> destroyed
- **zscore_entry=-3.5** is the only viable threshold on 3-year data (112/115 profitable configs)
- **zscore_period >= 30** produces zero profitable configs on 3-year data
- **TP_ZSCORE is the core problem**: exits fire when dollar move is too small to cover costs
- **`correlation_min` is redundant**: always > 0.80 when Z-Score + Coint conditions met
- **`hurst_max` is redundant**: Hurst < 0.45 on all traded bars (captured by Cointegration Score)
- **`cointegration_score_min`** is the most impactful secondary parameter (40 vs 60 = +63% PnL on 8-month)
- **TP/SL dollar thresholds** are the most impactful parameters overall
- **Strategy is regime-dependent**: 5 months of losses followed by 3 months of large gains (8-month data)
- **8-month results were overly optimistic**: driven by an exceptionally favorable regime (Oct 2025 - Jan 2026)

## Next Steps (TODO)

### Priority 1 -- Strategy Viability Assessment
- **Re-run with 1 tick slippage**: verify if strategy becomes viable with optimistic slippage
- **Test wider TP/SL ranges**: TP=$500-$1000, SL=-$1500-$2000 (let trades run longer)
- **Remove TP_ZSCORE exits entirely**: rely only on dollar-based TP/SL
- **Multi-timeframe**: test on 5-min or 15-min bars (fewer trades, higher PnL per trade)
- **Alternative cost model**: test with $3 commission (IB) and 1 tick slippage

### Priority 2 -- Code Quality
- **Add pytest tests**: unit tests for indicators, signals, position sizing, and PnL calculations. Required before any heavy refactoring.
- **Merge backtest engines**: once tests exist, merge backtest_engine.py and backtest_engine_hybrid.py (~1286 lines duplicated)
- **Vectorize indicators**: replace O(n*lookback) loops with pandas rolling (beta, ADF, Hurst). Requires non-regression tests.
- **Decompose run_backtest()**: 388 lines, 5+ nesting levels. Split into sub-functions after tests.

### Priority 3 -- Walk-Forward on 3-Year Data
If a viable config is found, validate with walk-forward on the full 3-year dataset (15-20 windows).

## Known Code Issues (non-blocking)

- **Rolling beta**: O(n x lookback) manual loop in indicators.py. Could use pandas rolling.
- **Hurst clamp vs default**: Hurst clamped to [0.01, 0.99] but default hurst_max=1.0. 0.99 would be clearer.
- **backtest_engine.py ~= backtest_engine_hybrid.py**: 95% identical, ~1286 lines duplicated. Requires pytest tests before safe merge.
- **run_backtest() = 388 lines**: 5+ nesting levels. Needs decomposition but requires tests first.

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

## Reference Documentation

- `config/strategy_params.yaml` - All strategy parameters
- `output/backtest_hybrid.csv` - Hybrid backtest with PnL (1-min + 5s, semicolon-separated)
- `output/archive/index.csv` - Global index of all archived runs (semicolon-separated)
- `output/optimization_log.csv` - Optimization history log
- `output/grid_search_3y_phase1.csv` - 3-year grid search results (32,400 configs)
- `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.4.cpp` - ACSIL source code (reference)
- `CHANGELOG.md` - Full optimization history, detailed results tables, completed improvements
