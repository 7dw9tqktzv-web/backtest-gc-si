# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v1.5).

**Current status**: **Phase C COMPLETE — Validation statistique terminee**. Config production : `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0` (5-min pure Z-Score). Block bootstrap P(perte 100tr) = 19.1% (sizing 0.5x recommande). Specs contrats configurables (standard GC/SI vs micro MGC/SIL). Slippage breakeven = 8.0 ticks. Filtres de regime = NO-GO en walk-forward. Filtre horaire 0-9h CT = MONITOR (PF 4.45 mais echantillon 61 trades). **220 tests passing**. Next: Phase D — Sierra Chart deployment + paper trading. See `CHANGELOG.md` for detailed history.

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
Total: ~7,500 lines
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
- **5min zscore pur = mode dominant**: 0% attrition slippage 2->1 tick, PF 2.74 top
- **1min dollar 2 ticks = MORT**: 0/32,400 configs. Definitif.
- **zp longs en 1min = impasse**: 1.6% rentables (B6, 86,400 configs). Definitif.
- **adf=26 domine en non-HMM**: 36/50 top B1 — toujours inclure dans les grilles
- **zTP negatif (overshoot) = game changer**: -1.0 et -0.5 dominent (36/50 top B1)
- **co=40 > co=60 en non-HMM**: contraire a l'audit HMM (31/50 vs 17/50)
- **zE=3.5 quasi-exclusif a 2 ticks**: 42/50 — trades rares mais qualite
- **zSL sans effet reel**: strategie "nue" cote protection
- **B3 hybrid (zTP + dollar SL) = NO-GO**: $25,164 top vs $59,172 B2 — dollar SL ne libere pas zE=2.5, 80% sorties via TP_ZSCORE
- **1min dollar = volume sans qualite**: $67/trade B4, $10/trade B6 — ne PAS investir plus
- **correlation_min is redundant**: Always > 0.80 when Z-Score + Coint conditions met
- **Correlation Daily (regime filter) != correlation_min**: Daily log-price corr on 40-day window, distinct from intraday bar-level correlation
- **hurst_max is redundant**: Hurst < 0.45 on all traded bars (use Cointegration Score instead)

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

## Phase B Grid Search Results (253,916 configs)

| Campaign | TF | Exit | Slip | Configs | Rent.(t>=80) | Top PnL | Verdict |
|----------|-----|------|------|---------|-------------|---------|---------|
| B1_5min_zscore_2tick | 5min | zscore | 2tick | 34,560 | 1,794 (5.2%) | $49,572 | GO |
| B2_5min_zscore_1tick | 5min | zscore | 1tick | 34,560 | 4,036 (15.8%) | $59,172 | **GO — best** |
| B3_5min_hybride_2tick | 5min | hybrid | 2tick | 41,472 | 3,302 (11.5%) | $25,164 | NO-GO |
| B4_1min_dollar_1tick | 1min | dollar | 1tick | 9,720 | 1,945 (20.0%) | $111,583 | GO (fragile) |
| B5_1min_zscore_1tick | 1min | zscore | 1tick | 5,832 | 347 | $20,896 | informative |
| B6_1min_dollar_zp_long_1tick | 1min | dollar | 1tick | 86,400 | 1,342 (1.6%) | $53,642 | dead end |

Archives: `output/archive/campaigns/` (7 campaigns), reports: `output/reports/PHASE_B_FINAL_RESULTS.md`

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

### 1-min timeframe (completed — Phase B confirms)
- **1min dollar 2 ticks = DEAD**: 0/32,400 configs profitable. Definitive.
- **zp longs (48-264) in 1min = dead end**: 1.6% profitable (B6, 86,400 configs). Definitive.
- **1min dollar = volume without quality**: $67/trade B4, $10/trade B6 — do NOT invest more
- **zE=2.5 dominates 1min dollar** (50/50 top B4) — opens more trades but low quality
- **TP_ZSCORE disabled** is optimal: exits fire when dollar move is too small to cover costs
- **TP/SL dollar thresholds** are the most impactful parameters overall
- **Strategy is regime-dependent**: 2023 weak, 2024-2025 profitable (walk-forward confirms)

### Phase C — Statistical Validation (Complete, Feb 2026)

| Phase | Description | Verdict |
|-------|-------------|---------|
| C0 | Prop firm scoring (34,560 -> 330 configs) | GO |
| C1 | Walk-forward diagnostic (15 fenetres, 4 toxiques: W02/W04/W05/W08) | Informative |
| C2 | Regime filter exploration (6 filtres sur spread daily) | Half-life + Correlation prometteurs |
| C2b | Filter integration + sensitivity analysis | Correlation seuil 0.86 = sweet spot |
| C3 | Walk-forward avec filtre Correlation | **NO-GO** — ne tient pas en OOS |
| C4 | Monte Carlo Bootstrap (1000 sims) | **GO** — P(perte 100tr) = 0.9% |
| C4bis | Block Bootstrap (1000 sims, k=3/5/7/10) | **GO** — P(perte 100tr) = 19.1% (k=5), sizing 0.5x |
| C4bis | Filtre horaire 0-9h CT | **MONITOR** — +$4.2K PnL, PF 4.45, -39 trades |
| C5 | Slippage stress test (1/2/2.5/3 ticks) | **GO** — breakeven 8.0 ticks |

#### C2/C2b — Regime Filter Exploration
6 filters tested on daily spread to predict toxic windows from C1:

| Filter | Spearman r | p-value | Verdict |
|--------|-----------|---------|---------|
| Realized Vol (20j) | -0.295 | 0.306 | NO-GO |
| Rolling ADF (40j) | +0.376 | 0.186 | NO-GO |
| Half-life AR(1) (60j) | -0.547 | 0.043 | Promising (C2) -> NO-GO (C3) |
| Correlation GC/SI (40j) | +0.543 | 0.045 | Promising (C2) -> NO-GO (C3) |
| Spread Slope (20j) | +0.099 | 0.736 | NO-GO |
| Rolling Hurst R/S (daily) | -0.332 | 0.250 | NO-GO structurel (>0.5) |

- **C2b sensitivity analysis** : seuil Correlation teste de 0.80 a 0.98. Degradation progressive (pas de curve-fitting). Sweet spot a 0.86 (52 trades, PF 7.84, MaxDD -$1,563).
- **C3 walk-forward** : le filtre ne tient pas en OOS. N'a bloque que 5/135 trades. L'effet principal est indirect (change la config selectionnee en train, parfois en bien, parfois en mal). **Conclusion definitive : aucun filtre de regime teste ne tient en walk-forward.**
- **Code** : `scripts/phase_c2b_comparison.py`, `scripts/phase_c2b_sensitivity.py`, `scripts/phase_c3_walk_forward.py`
- **Tests** : `tests/test_phase_c2b.py` (15 tests)

#### C4bis — Block Bootstrap + Filtre horaire (Feb 2026)

L'audit quant a revele une autocorrelation PnL forte (r=0.50 lag 1, p<0.0001), invalidant le bootstrap i.i.d. de C4.

**Block Bootstrap (1000 sims, horizon 100 trades):**

| Methode | P(perte) | PnL Median | MaxDD P5 |
|---------|----------|------------|----------|
| i.i.d. (C4) | 0.9% | $45,395 | -$13,877 |
| Block k=3 | 9.4% | $30,022 | -$16,162 |
| Block k=5 | **19.1%** | $19,946 | -$20,730 |
| Block k=7 | 25.8% | $16,766 | -$22,873 |
| Block k=10 | 37.7% | $8,450 | -$23,612 |

- **Ratio sous-estimation i.i.d.: 21x** (0.9% vs 19.1%)
- Verdict: **GO** (P(perte) < 20%), sizing 0.5x recommande
- L'autocorrelation vient des regimes (magnitude, pas direction -- runs test p=0.87)

**Filtre horaire:**

| Mode | Trades | PnL | PF | MaxDD |
|------|--------|-----|----|-------|
| A: 24h (baseline) | 100 | $45,224 | 2.41 | -$17,341 |
| B: Block 0-9h CT | 61 | $49,461 | 4.45 | -$4,555 |
| C: Block 0-8h CT | 64 | $46,237 | 3.64 | -$6,958 |

- Mode B (0-9h) ameliore PF (2.41->4.45), MaxDD (-$17.3K->-$4.6K), PnL (+$4.2K)
- Amelioration < $5,000 => pas de walk-forward (echantillon trop petit)
- Verdict: **MONITOR** -- a surveiller en paper trading
- **Code**: `scripts/phase_c4bis_block_bootstrap.py`

#### C4 — Monte Carlo Bootstrap
1000 simulations de reechantillonnage sur les trades du backtest 3 ans (config b2640, 100 trades).

| Horizon | P(perte) | PnL P5 | PnL Median | PnL P95 |
|---------|----------|--------|------------|---------|
| 50 trades | 5.1% | -$21 | $20,441 | $49,911 |
| 100 trades | 0.9% | $10,911 | $45,395 | $85,997 |
| 150 trades | 0.4% | $26,540 | $65,454 | $119,433 |
| 200 trades | 0.1% | $40,278 | $88,624 | $144,414 |

- LONG et SHORT equilibres (P(perte 100tr) = 1.8% vs 1.0%)
- **Attention** : bootstrap melange les epoques, masque le risque de regime (2023-2024 perdants)
- **Code** : `scripts/phase_c4_monte_carlo.py`

#### C5 — Slippage Stress Test

| Slippage | b3960 (WF best) | b2640 (B2 top) |
|----------|-----------------|----------------|
| 1 tick | $32,948 | $52,804 |
| 2 ticks | $23,928 | $45,224 |
| 2.5 ticks | $19,418 | $41,434 |
| 3 ticks | $14,908 | $37,644 |

| Config | Cout/tick/trade | Breakeven | Marge vs 2 ticks |
|--------|----------------|-----------|------------------|
| b3960 | $74 | 4.7 ticks | 2.7 ticks |
| b2640 | $76 | 8.0 ticks | 6.0 ticks |

- Monte Carlo a 2.5 ticks : b3960 P(perte)=8.0%, b2640 P(perte)=3.0%
- **Config production recommandee** : b2640 (marge de securite 6.0 ticks)
- **Code** : `scripts/phase_c5_slippage_stress.py`

### Phase C Validation — Final Conclusions (Feb 2026)
- **Regime filters = dead end**: 6 filters tested (C2), 2 promising (Half-life, Correlation), integrated in backtest engine (C2b), but neither survives walk-forward OOS (C3). Definitive.
- **Block bootstrap corrige le risque**: P(perte 100tr) = 19.1% (k=5), pas 0.9% (i.i.d.). Autocorrelation PnL r=0.50 lag 1 due aux regimes. Sizing 0.5x recommande.
- **Filtre horaire 0-9h CT prometteur**: PF 4.45 vs 2.41, MaxDD -$4.6K vs -$17.3K. MONITOR (echantillon 61 trades).
- **Breakeven slippage = 8.0 ticks** (C5): marge de securite 6x vs nominal.
- **Config production**: `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0` (5-min pure Z-Score, no regime filter)
- **Known risk**: strategy is regime-dependent (2023-2024 losing, 2025-2026 profitable). 80% du PnL concentre sur Jan 2026 (8 trades). No filter found to mitigate this. Accept as structural risk.

### Bug fixes applied (indicators.py, backtest_engine_hybrid.py, optimizer.py, metrics.py)
- **Bug 1**: ADF regression now includes intercept (was missing mu term)
- **Bug 4**: Removed incorrect `spread == 0` skip in ADF calculation
- **Bug 5**: `zscore_tp_min_pnl` filter now uses net PnL (was using gross)
- **Sharpe ratio fix**: Harmonized Sharpe calculation (mean/std per trade, not annualized) between optimizer.py and metrics.py

### Best Configs Summary (Phase B)
See `CHANGELOG.md` for detailed tables. Key findings:
- **5-min pure Z-Score = dominant mode**: $59,172 top (B2), PF 2.74, 0% slippage attrition
- **zTP=-1.0 (overshoot) = game changer**: doubles PnL vs zTP=1.0
- **adf=26 dominates non-HMM** (36/50 top B1) — always include in grids
- **b2640 optimal** (27/50 top B1), cp=24 (37/50), zE=3.5 (42/50)
- **co=40 > co=60 in non-HMM**: 31/50 vs 17/50 (opposite of HMM audit)
- **1min dollar = volume without quality**: $67/trade B4, $10/trade B6
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

## Roadmap (TODO)

### Immediate: Pause Refactor
- [ ] Clean metrics.py (remove legacy archiving, keep standalone analysis)
- [ ] Clean optimizer.py (remove redundant log/display)

### Phase C -- Statistical Validation
- [x] C0: Prop firm scoring (34,560 -> 330 configs, weighted scoring)
- [x] C1: Walk-Forward diagnostic (15 windows, 4 toxic: W02/W04/W05/W08)
- [x] C2: Regime filter exploration (Half-life + Correlation prometteurs)
- [x] C2b: Filter integration + sensitivity (Correlation 0.86 sweet spot)
- [x] C3: Walk-Forward final avec filtre (NO-GO — ne tient pas en OOS)
- [x] C4: Monte Carlo Bootstrap 1000 sims (GO — P(perte 100tr) = 0.9%)
- [x] C4bis: Block Bootstrap (GO — P(perte 100tr) = 19.1% k=5, sizing 0.5x) + Filtre horaire (MONITOR)
- [x] C5: Slippage stress test 2.5 et 3 ticks (GO — breakeven 8.0 ticks)

### Phase C+ -- Trade Augmentation
- [ ] Analyze losing trades (quant-analyst)
- [ ] Volatility filter (GVZ, realized vol, VIX)
- [ ] Hourly filter (analysis per session hour)
- [ ] Retest relaxed zE (2.5/2.0) WITH filters
- [ ] Re-validate (WF + MC + slippage) enriched configs

### Phase D -- Sierra Chart Deployment     <-- NEXT
- [ ] Final selection: b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0 (5-min pure Z-Score)
- [ ] ACSIL C++ implementation (entry/exit automation, v1.5 indicators already harmonized)
- [ ] Paper trading 4-8 weeks (min 30 trades, compare vs Python backtest)
- [ ] Production go-live (if paper trading validates)

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
├── src/                        # Main source code (~7,500 lines)
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
├── tests/                      # pytest tests (220 tests)
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
│       ├── B1_5min_zscore_2tick.yaml   # Phase B1: 34,560 configs
│       ├── B2_5min_zscore_1tick.yaml   # Phase B2: 34,560 configs
│       ├── B4_1min_dollar_1tick.yaml   # Phase B4: 9,720 configs
│       ├── B5_1min_zscore_1tick.yaml   # Phase B5: 5,832 configs
│       ├── B3_5min_hybrid_2tick.yaml        # Phase B3: 41,472 configs (hybrid)
│       ├── B6_1min_dollar_zp_long_1tick.yaml # Phase B6: 86,400 configs
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
├── test_archive_manager.py          # 26 tests - Archive management + campaigns
├── test_common.py                   # 32 tests, 100% coverage
├── test_indicators.py               # 33 tests, 72% coverage
├── test_position.py                 # 26 tests, 48% coverage
├── test_backtest_engine_hybrid.py   # 13 tests
├── test_optimizer.py                # 9 tests
├── test_metrics.py                  # 12 tests
├── test_run_helpers.py              # 6 tests
└── test_phase_c2b.py                # 15 tests - Regime filter indicators + blocking
```

### Running Tests
```bash
pytest tests/ -v                    # All tests (220 tests)
pytest tests/ --cov=src             # With coverage report
pytest tests/test_common.py -v      # Single file
pytest -k "test_long"               # Tests matching pattern
```

### Test Coverage (as of 2026-02)
- **common.py**: 100% - Entry/exit conditions, PnL calculation
- **archive_manager.py**: covered (26 tests) - Archive, campaigns, rankings, dashboard, list
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
