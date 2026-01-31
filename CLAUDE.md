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

Commission: $4.00 round-trip per contract ($2.00 per side). Slippage: 1 tick per leg.

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

## Current Results (Config A -- best PnL, 44,018 bars, 48 days)

Config A: beta=1980, zp=20, cp=30, adf=128, cm=0.60, co=40, TP=$300, SL=-$600

- PnL net total: +$60,567
- Win rate: 90.2% (395/438)
- 252 LONG / 186 SHORT
- Exits: 356 TP_DOLLAR, 76 TP_ZSCORE, 6 SL_DOLLAR, 0 SL_ZSCORE
- Best trade: +$499 | Worst trade: -$750
- Max Drawdown: -$765
- Profit Factor: 6.90
- Sharpe (per trade): 14.44
- Costs total: $50,388 (45% of gross PnL)
- Avg trade duration: 0.4 min | 9.1 trades/day
- Trade list exported to `output/backtest_hybrid.csv` (semicolon-separated)

## Optimization History (606+ configs tested)

### 3-step grid search process
1. **Etape 1 (22 configs)**: beta_lookback (660-7920) x zscore_period (15/20/30)
   - Finding: beta=660 and beta=1980 dominate. zp=15 and zp=20 best.
2. **Etape 2 (101 configs)**: top 5 indicators x TP (200-600) x SL (400-1200)
   - Finding: **TP=$300 + SL=-$600 is optimal**. Smaller TP captures profits faster on mean reversion.
3. **Etape 3 (481 configs)**: 6 bases x correlation_period x adf_period x corr_min x coint_min
   - Finding: cointegration_score_min=40 doubles PnL vs 60. correlation_min has zero impact.

### Hurst filter test (12 configs)
- Tested hurst_max = 0.45/0.50/0.55/1.0 on 3 winning configs
- Result: **zero impact** -- Hurst < 0.45 on all traded bars (redundant with Cointegration Score)

### 3 archived winning configs

| Config | Params | Trades | WR% | PnL Net | PF | MaxDD | Sharpe | Profile |
|--------|--------|--------|-----|---------|-----|-------|--------|---------|
| A | co=40, cp=30 | 438 | 90.2% | $60,567 | 6.90 | -$765 | 14.4 | Max PnL |
| B | co=50, cp=60 | 231 | 92.6% | $35,127 | 12.99 | -$750 | 20.2 | Max risk-adjusted |
| E | co=50, cp=30 | 250 | 90.8% | $37,136 | 10.19 | -$765 | 17.7 | Balanced |

Common params: beta=1980, zp=20, TP=$300, SL=-$600, cm=0.60, adf=128

### Key optimization conclusions
- `correlation_min` is redundant: correlation is always > 0.80 when Z-Score + Coint conditions are met
- `hurst_max` is redundant: Hurst < 0.45 on all traded bars (already captured by Cointegration Score)
- `cointegration_score_min` is the most impactful secondary parameter (40 vs 60 = +63% PnL)
- TP/SL dollar thresholds are the most impactful parameters overall (TP300/SL600 vs TP600/SL1000 = +106% PnL)
- Optimization log saved in `output/optimization_log.csv` (top 50 + Hurst test batch)

## Next Steps (TODO)

### Priority 1 -- Validation
- **Walk-forward test**: Split data into train (30 days) / test (18 days), optimize on train, validate on test. Critical to detect overfitting on 606 configs.
- **Cost stress test**: Run Config A with slippage=2 ticks and commission=$5 to verify robustness.

### Priority 2 -- Additional parameter tests
- **Z-Score entry thresholds**: Test zscore_long=-2.0/-3.0, zscore_short=+2.0/+3.0 (never tested, kept at default -2.5/+2.5)
- **Z-Score exit thresholds**: Test zscore_tp_long=-1.5/-1.0, etc. (low impact expected since 81% exits are TP_DOLLAR)

### Priority 3 -- More data
- **Extend data period**: 48 days is limited. 6-12 months would validate robustness across different market conditions (trending, ranging, volatile).
- **Paper trading**: Run strategy in real-time simulation before committing capital.

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
