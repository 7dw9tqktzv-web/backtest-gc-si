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

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

### Data Pipeline
```
Sierra Chart CSV -> data_loader.py -> indicators.py -> signals.py -> position.py -> backtest_engine.py -> metrics.py
                      (sync GC/SI)    (calculate)    (generate)      (sizing)      (simulate)           (analyze)

Sierra Chart 5s CSV -> data_loader_5s.py -> backtest_engine_hybrid.py
                         (sync 5s)            (hybrid simulation)
```

### Module Status
| Module | Status | Purpose |
|--------|--------|---------|
| `data_loader.py` | Complete | Load/sync GC & SI 1-min data from Sierra Chart exports |
| `data_loader_5s.py` | Complete | Load/sync GC & SI 5-second data from Sierra Chart exports |
| `indicators.py` | Complete | Calculate Beta, Spread, Z-Score, Correlation, ADF, Hurst |
| `signals.py` | Complete | State machine for entry/exit signals (Z-Score based) |
| `position.py` | Complete | Position sizing (dollar neutral with Beta) + PnL calculation |
| `backtest_engine.py` | Complete | Trade simulation with High/Low intra-bar dollar exits |
| `backtest_engine_hybrid.py` | Complete | Hybrid backtest: 1-min signals + 5s dollar exits |
| `metrics.py` | To create | Performance analysis |

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

### Configuration
All parameters are in `config/strategy_params.yaml`. Never hardcode values.

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
- LONG spread: Z-Score <= -3.0, Correlation > 0.70, Cointegration Score >= 50
- SHORT spread: Z-Score >= 3.0, Correlation > 0.70, Cointegration Score >= 50

### Exit Conditions (OR logic)
| Condition | LONG | SHORT |
|-----------|------|-------|
| TP Z-Score | >= -2.0 | <= +2.0 |
| SL Z-Score | <= -3.5 | >= +3.5 |
| TP Dollars | +$400 | +$400 |
| SL Dollars | -$800 | -$800 |

### Key Rules
- After take profit: immediate re-entry allowed if conditions met
- After stop loss: cooldown until Z-Score returns to +/-1.0 (direction-specific)
- Cooldown only blocks same direction (COOLDOWN_LONG blocks LONG, not SHORT)
- Reversal allowed: close LONG and open SHORT on same bar
- Exit priority: SL_DOLLAR > SL_ZSCORE > TP_DOLLAR > TP_ZSCORE
- Single position at a time
- Dollar-based exits (TP $400 / SL -$800) handled in backtest engines, not signals.py

## Backtest Engines

### backtest_engine.py (1-min with High/Low)
- Iterates on 1-minute bars
- Dollar exits use High/Low prices to detect intra-bar SL/TP triggers
- When SL/TP dollar triggered, PnL is fixed at the threshold (-$800 or +$400)
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
1a. Scan 5s bars: SL_DOLLAR (-$800) -> break
1a. Scan 5s bars: TP_DOLLAR (+$400) -> break
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

## Current Results (signals.py on 44,018 bars)

- 66 trades: 43 LONG, 23 SHORT
- 61 TP Z-Score exits, 5 SL Z-Score exits (ratio 12.2)
- Trades are short duration (1-7 min avg), 0.5% time in market
- No trades after Jan 22 due to low correlation/cointegration score in that period
- Trade list exported to `output/trade_list.csv` (semicolon-separated, Excel compatible)

## Position Sizing (position.py)

### Dollar Neutral with Beta (ACSIL v1.4 formula)
```
NotionalGC = GC_price × $100
NotionalSI = SI_price × $5000
GC_contracts = round( (NotionalSI / NotionalGC) × Beta ) , minimum 1
```

### Key Observations
- Beta varies from ~0.03 to ~6.3 on traded bars → GC contracts range from 1 to 6
- Trades with 5 GC contracts are the most problematic (82% of total losses in Z-Score-only backtest)
- Dollar-based exits (TP/SL $) in backtest engines limit large losses

## Current Results (position.py Z-Score-only backtest on 66 trades)

- PnL net total: -$15,513 (without dollar-based exits)
- Win rate: 62.1% (41/66)
- Worst trade: -$14,624 (SHORT #52, 5 GC contracts, GC dropped 36 points)
- Costs total: $7,188 (commission + slippage)
- Note: These results do NOT include TP $400 / SL -$800 exits

## Current Results (backtest_engine_hybrid.py on 84 trades)

- PnL net total: +$15,217
- Win rate: 89.3% (75/84)
- 55 LONG / 29 SHORT
- Exits: 61 TP_DOLLAR, 18 TP_ZSCORE, 3 SL_DOLLAR, 2 SL_ZSCORE
- Best trade: +$397 | Worst trade: -$974
- Max Drawdown: -$974
- Profit Factor: 4.39
- Costs total: $9,168
- Trade list exported to `output/backtest_hybrid.csv` (semicolon-separated)

## Completed Improvements

- **Cointegration Score adaptive**: Reweights score proportionally when ADF/Hurst are NaN, instead of penalizing to 0. No impact on trade count (still 66 trades).
- **ACSIL formula verification**: Confirmed Python matches ACSIL v1.4 for StdDev (ddof=1), Correlation (Pearson), and OLS Beta.
- **Hybrid backtest (1min + 5s)**: Dollar exits monitored on 5-second bars for precision. Indicators stay on 1-minute (no x12 lookbacks). Full 5s approach was tested and rejected (too noisy, 70 SL_ZSCORE from transient threshold crossings).

## Reference Documentation

- `config/strategy_params.yaml` - All strategy parameters
- `output/trade_list.csv` - Z-Score trade list (semicolon-separated, Excel compatible)
- `output/backtest_trades.csv` - Full backtest with PnL in dollars (1-min High/Low, semicolon-separated)
- `output/backtest_hybrid.csv` - Hybrid backtest with PnL in dollars (1-min + 5s, semicolon-separated)
- `DOC SIERRA/files/` - Sierra Chart ACSIL documentation
- `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.4.cpp` - ACSIL source code (reference)
