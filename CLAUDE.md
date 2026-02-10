# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.5).

**Current status**: **Phase D IN PROGRESS — Replay validation**. ACSIL v2.0 corrige: 100% unmanaged (sc.BuyOrder/SellOrder pour GC et SI), SI-first pattern avec order verification, IsFullRecalculation guard via goto. Leg GC validee (10 trades, $25,740 PnL GC-only, 80% win rate). Leg SI: a tester en replay. Config production : `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL4.0` (5-min pure Z-Score). **223 tests passing**. See `CHANGELOG.md` for detailed history.

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

# Archive management (campaigns)
python src/archive_manager.py --action archive-campaign --csv output/grid.csv --campaign NOM --n 20 --min-trades 50
python src/archive_manager.py --action compare                                     # Compare all campaigns
python src/archive_manager.py --action report --campaigns C1,C2 --output out.md    # Generate report
python src/archive_manager.py --action dashboard
python src/archive_manager.py --action list

# Archive management (legacy — single configs)
python src/archive_manager.py --action archive-top --csv output/grid.csv --n 20 --timeframe 1min --slippage 1tick
python src/archive_manager.py --action generate-rankings

# Validate data at specific datetime
python validate_data.py --date "2026-01-23 10:30:00"
```

## Architecture

See `docs/ARCHITECTURE.md` for full data pipeline diagram and module descriptions.

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
- `archive_campaign()` in `archive_manager.py` - archives a full campaign (meta + CSV + top N)
- `compare_campaigns()` in `archive_manager.py` - compares campaigns side by side
- `generate_campaign_report()` in `archive_manager.py` - generates Markdown report with GO/NO-GO

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

CLI: python src/archive_manager.py --action {archive-campaign|compare|report|archive-top|generate-rankings|dashboard|list}

output/archive/campaigns/               <- Phase B campaign archives
    {campaign_name}/
        campaign_meta.json               <- Campaign stats
        full_results.csv                 <- Full CSV (gitignored)
        top20/
            01_{config_label}/
                config.yaml + metrics.json
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

Configurable via `contracts.mode` dans `strategy_params.yaml` :

| Spec | GC (standard) | MGC (micro) | SI (standard) | SIL (micro) |
|------|---------------|-------------|---------------|-------------|
| Taille | 100 oz | 10 oz | 5,000 oz | 1,000 oz |
| Point Value | $100 | $10 | $5,000 | $1,000 |
| Tick Size | $0.10 | $0.10 | $0.005 | $0.005 |
| Tick Value | $10 | $1 | $25 | $5 |
| Ratio vs standard | 1x | 1/10 | 1x | 1/5 |

Mode par defaut : `standard`. Basculer a `micro` pour sizing 0.5x (recommandation C4bis).

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
- Regime filter (if enabled): `HalfLife_AR1` (daily, forward-filled), `Corr_Daily_GC_SI` (daily, forward-filled)

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
- **correlation_min is redundant**: Always > 0.80 when Z-Score + Coint conditions met
- **Correlation Daily (regime filter) != correlation_min**: Daily log-price corr on 40-day window, distinct from intraday bar-level correlation
- **hurst_max is redundant**: Hurst < 0.45 on all traded bars (use Cointegration Score instead)
- See "Research Conclusions" section for grid search findings

### Code Quirks
- **ddof inconsistency**: Beta uses ddof=0, Z-Score uses ddof=1 (low impact but confusing)
- **hmmlearn covariance bug**: Getter returns (n_components, n_features, n_features), setter expects (n_components, n_features) - use `model._covars_` directly
- **MGC/SIL ratios asymetriques** : MGC = 1/10 de GC, SIL = 1/5 de SI. Le sizing dollar-neutral est recalcule automatiquement via `get_contract_specs()`

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

## Research Conclusions (Summary)

See `CHANGELOG.md` for detailed tables, numbers, and phase-by-phase results.

### Key Verdicts
- **5-min pure Z-Score = dominant mode** (B2 best: $59,172, PF 2.74, 0% slippage attrition)
- **1min dollar = dead end** (2 ticks: 0/32,400 profitable; 1 tick: volume sans qualite)
- **Regime filters = dead end** (6 tested C2, none survives walk-forward OOS C3)
- **Block bootstrap P(perte 100tr) = 19.1%** (k=5), sizing 0.5x recommande
- **Breakeven slippage = 8.0 ticks** (C5), marge 6x vs nominal
- **Filtre horaire 0-9h CT**: MONITOR (PF 4.45, echantillon 61 trades)
- **HMM regime filter**: Python-only, NO_HMM > HMM en PnL, HMM > en consistance. Disabled for SC.
- **Config production**: `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0` (5-min pure Z-Score, no filter)
- **Known risk**: regime-dependent (2023-2024 losing, 2025-2026 profitable, 80% PnL on Jan 2026)

### Key Parameter Findings
- **zTP=-1.0 (overshoot) = game changer**: doubles PnL vs zTP=1.0
- **adf=26 dominates non-HMM** (36/50 top B1) — always include in grids
- **zE=3.5 quasi-exclusif a 2 ticks** (42/50) — trades rares mais qualite
- **co=40 > co=60 in non-HMM** (31/50 vs 17/50, opposite of HMM audit)

## Sierra Chart Integration (v2.0 - TRADING AUTOMATISE)

Python and Sierra Chart v1.5/v2.0 produce **identical indicator values** (< 0.01% difference).
v2.0 = v1.5 indicators + automated spread trading (state machine, multi-symbol orders, Z-Score + dollar exits).
Guards corriges pour adf=26 (period < 20 au lieu de < 50). 28 inputs total.

### Sierra Chart Files
- **v2.0 (trading)**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v2.0.cpp`
- **v1.5 (indicateur ref)**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.5.cpp`
- **v1.4 (legacy)**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1_4.cpp`
- **Spreadsheet export**: `DOC SIERRA/files/DefaultSpreadsheetStudy.txt`
- **ACSIL docs**: `DOC SIERRA/files/01-05_*.md`, `SierraChart_*.md`
- **ACSIL skill**: `.claude/skills/sierra-acsil/` (reference docs for trading functions)

### Sierra Chart Settings (production config, must match Python)
```
Beta Lookback: 2640
Z-Score Period: 20
Correlation Period: 30
ADF/Hurst Period: 26
Z-Score Entry LONG: -3.5
Z-Score Entry SHORT: 3.5
Min Cointegration Score: 40
Correlation Minimum: 0.6
Z-Score TP Long: 1.0 (overshoot)
Z-Score TP Short: -1.0 (overshoot)
Z-Score SL Long: -4.0
Z-Score SL Short: 4.0
Cooldown Reset Long: -1.0
Cooldown Reset Short: 1.0
Session Start: 17:30:00 CT
Session End: 15:30:00 CT
SI Symbol: SIH26_FUT_CME (format underscore, pas SIH26.CME)
```

### ACSIL Order Functions (GC/SI spread) — 100% unmanaged
```
LONG spread (Buy SI + Sell GC):
  Entry:  sc.SellOrder(GC)     + sc.BuyOrder(SI, Symbol=SIH26_FUT_CME)
  Exit:   sc.BuyOrder(GC)      + sc.SellOrder(SI, Symbol=SIH26_FUT_CME)

SHORT spread (Sell SI + Buy GC):
  Entry:  sc.BuyOrder(GC)      + sc.SellOrder(SI, Symbol=SIH26_FUT_CME)
  Exit:   sc.SellOrder(GC)     + sc.BuyOrder(SI, Symbol=SIH26_FUT_CME)
```
- Tout en `sc.BuyOrder/SellOrder` (unmanaged) — NE PAS mixer avec managed (BuyEntry/SellEntry/BuyExit/SellExit)
- `sc.SendOrdersToTradeService = 1` requis pour ordres cross-symbole
- `sc.SubmitOrder()` n'existe PAS dans ACSIL
- Le Spread Order Entry Study est GUI-only, pas d'API ACSIL
- SI-first pattern: soumettre SI d'abord, verifier rc, puis GC. Si GC echoue, reverser SI.

### Replay Validation (Feb 2026)
GC leg validated (10 trades, directions OK). SI leg: v2.0 corrige (100% unmanaged + IsFullRecalculation guard + order verification). A tester en replay.

### ACSIL Gotchas (Phase D learnings)
- **NE PAS mixer managed et unmanaged**: managed (BuyEntry/SellEntry) + unmanaged (BuyOrder/SellOrder) = conflits avec variables managed (MaximumPositionAllowed, SupportReversals, etc.)
- **DRAWSTYLE_IGNORE** necessaire pour subgraphs trading (Hidden ne suffit pas, compresse le chart)
- **Format symbole**: utiliser `SIH26_FUT_CME` (underscores) pas `SIH26.CME` (point)
- **IsFullRecalculation**: utiliser `goto SkipTrading` (pas `return`) pour preserver le text box
- **Replay mode**: "Standard Replay" fonctionne, "Accurate Trading Back Test" non
- **Jan 1 = holiday**: commencer le replay le 5 janvier

## Roadmap (TODO)

Phase B (grid search) and Phase C (statistical validation) are **complete**. See `CHANGELOG.md`.

### Phase D -- Sierra Chart Deployment (IN PROGRESS)
- [ ] Tester v2.0 corrige en replay (100% unmanaged, SI-first, order verification)
- [ ] Validation replay SC vs Python backtest complet (GC+SI, Janvier 2026)
- [ ] Text box mise a jour + logging ameliore
- [ ] Paper trading 4-8 weeks (min 30 trades, compare vs Python backtest)
- [ ] Production go-live (if paper trading validates)

### Phase C+ -- Trade Augmentation (future)
- [ ] Analyze losing trades, volatility filter, hourly filter, relaxed zE with filters

## Known Code Issues (non-blocking)

See `analyse.md` for comprehensive code review. Key issues:
- **ddof inconsistency**: Beta ddof=0, Z-Score ddof=1 (low impact)
- **run_hybrid_backtest() = 350+ lines**: needs decomposition

## Claude Code Skills

### /backtest-runner
Runs the hybrid backtest and affiche les resultats formates. Compare automatiquement avec le run precedent.
- Lance `backtest_engine_hybrid.py` puis `metrics.py`
- Affiche les metriques cles et la comparaison avec le run precedent

### /optimize
Teste differents parametres via langage naturel en francais. Supporte le grid search avec la syntaxe "/" (ex: "teste beta 1320/2640 avec TP 400/600").
- Utilise `optimizer.py` : charge les donnees 1 fois, boucle sur N configs en memoire
- Ne modifie PAS le YAML pendant les tests (travaille en memoire)

### /results
Archive et analyse les resultats de grid search. Supporte l'archivage de campagnes,
la comparaison inter-campagnes, et la generation de rapports.
```bash
python src/archive_manager.py --action archive-campaign --csv output/grid.csv --campaign NOM --top-n 20
python src/archive_manager.py --action compare
python src/archive_manager.py --action report --campaigns C1,C2,C3
python src/archive_manager.py --action dashboard
python src/archive_manager.py --action list
```

### /grid-search
Lance un grid search massif en background (milliers de configs), genere un rapport et met a jour le CHANGELOG.
- YAML configs dans `configs/experiments/B*.yaml` (Phase B) et `grid_*.yaml` (legacy)
- Utilise `scripts/run_grid_search.py --config <yaml>` (YAML-driven runner)
- Runner supports 3 modes: "dollar", "zscore", and "hybrid" (zTP + dollar SL)
- Produit: CSV de resultats, `output/latest_summary.txt`, section CHANGELOG.md

## Git Tracking

`.gitignore` exclut : `.venv/`, `__pycache__/`, `data/raw/`, `DOC SIERRA/`, `.idea/`, `.claude/`, `results/`, `output_old/`

`output/` uses selective tracking: `archive/` and `rankings/` are tracked (config.yaml + metrics.json), but large files (*_trades.csv, *_equity.png) are gitignored.

## Testing

223 tests, all passing. Tests use synthetic data (fixtures in `conftest.py`), no dependency on real CSV files.
Key fixtures: `sample_config`, `sample_prices_df`, `sample_df_with_indicators`.

## Skills & References
- **ACSIL/Sierra Chart**: Read `.claude/skills/sierra-acsil/SKILL.md` before any C++ Sierra Chart work
- **Strategy logic**: Refer to `docs/STRATEGY.md` for indicator formulas and entry/exit rules
- **Architecture**: Refer to `docs/ARCHITECTURE.md` for module interactions

## Reference Files
- `config/strategy_params.yaml` - All strategy parameters
- `CHANGELOG.md` - Full optimization history and detailed results
- `analyse.md` - Code analysis and bug documentation
- `output/archive/` - Archived configs with metrics reports
- `output/latest_summary.txt` - Last grid search summary (generated by report_generator.py)
