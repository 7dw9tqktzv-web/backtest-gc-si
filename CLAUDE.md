# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting system for a Gold/Silver (GC/SI) spread trading strategy based on cointegration and mean reversion. The strategy replicates a Sierra Chart ACSIL indicator (v2.0).

**Current status**: Phase D — Fast grid engine merge. Grid search R1 corrige pret a lancer (~20M configs, ~4h). Paper trading SC en cours (C6).
**Config production standard**: `b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL4.0` (5-min, standard). OBSOLETE — optimisee sans FLAT_EOD ni session prop firm, ne sert plus de reference.
**Config production micro**: A DETERMINER — grid search R1 corrige avec sizing smart + FLAT_EOD + session 18:00-14:55 CT + slippage 2 ticks.
**210 tests passing**. See `CHANGELOG.md` for detailed history.

SC paper trading tourne avec C6 en l'etat (plugin C++ correct, sera remplacee post-R1).

### Output Structure
- Grid searches : `output/grid_searches/r1|r2a|r2b|r2c/`
- Reports : `output/reports/` (PNL_DECAY, WALKFORWARD, MONTE_CARLO, R2B/R2C deep analysis)
- Plots : `output/plots/pnl_decay|monte_carlo/`
- Logs : `output/logs/`
- Legacy (standard pipeline) : `output/legacy/`

## Commands

```bash
pytest tests/ -v                                                    # Run all tests
python src/backtest_engine_numba.py                                 # Backtest (Numba JIT)
python src/metrics.py                                               # Performance analysis
python scripts/run_grid_search.py --config configs/experiments/<yaml>  # Grid search
python scripts/validate_fast_engine.py                              # Validate fast engine parity (300 configs)
python scripts/benchmark_fast_engine.py                             # Benchmark fast vs reference engine
python src/archive_manager.py --action {archive-campaign|compare|report|dashboard|list}
```

See `scripts/` for all available scripts (grid search, walk-forward, paper trading, analysis).

## Architecture

See `docs/ARCHITECTURE.md` for full data pipeline diagram and module descriptions.

### Key Entry Points
- `run_hybrid_backtest(df_1min, df_5s, config)` in `backtest_engine_numba.py` — backtest unitaire
- `scripts/run_grid_search.py --config <yaml>` — grid search massif (auto-detect fast engine)
- `calculate_all_indicators(df, config)` in `indicators.py` — indicateurs sur df 1-min ou 5-min
- `pack_config(config)` in `backtest_engine_numba.py` — convertit dict config en numpy array cfg[]

### Configuration
All parameters are in `config/strategy_params.yaml`. Never hardcode values.
Key field: `indicators.period` defines the calculation timeframe (1min, 5min, 15min, 1h, 1d).

### Archiving
Archive structure: `output/archive/{timeframe}/{exit_mode}/{config_name}/` with `config.yaml` + `metrics.json` (git-tracked) and `*_trades.csv` (gitignored).

## Trading Logic

5 states: FLAT, LONG, SHORT, COOLDOWN_LONG, COOLDOWN_SHORT. Exit priority: SL_DOLLAR > TP_DOLLAR > SL_ZSCORE > TP_ZSCORE > MAX_HOLD > FLAT_EOD. Single position at a time. Cooldown blocks same direction only. Reversal allowed on same bar. See `docs/STRATEGY.md` for entry/exit conditions and parameter values.

## Backtest Engines

Trois moteurs coexistent, chacun avec un role precis :

| Moteur | Fichier | Usage | Vitesse |
|--------|---------|-------|---------|
| **Numba** | `src/backtest_engine_numba.py` | Backtests unitaires, analyses ponctuelles, reference pour validation | ~0.04s/config (pure zscore), ~1.5s/config (dollar exits avec scan 5s) |
| **Fast Grid** | `src/fast_grid_engine.py` | Grid searches massifs (micro_full). Factorise le scan 5s par (zE, co, mm) | ~13x plus rapide que Numba pour grids |
| **Hybrid** | `src/backtest_engine_hybrid.py` | Tests unitaires (Python pur, pas de dependance Numba) | ~0.4s/config |

### Quand utiliser quel moteur

- **Backtest d'une config** : `run_hybrid_backtest()` depuis `backtest_engine_numba.py`
- **Grid search micro_full** : automatique — `grid_search_runner.py` detecte `exit_mode=micro_full` et utilise le fast engine
- **Tests unitaires** : `backtest_engine_hybrid.py` (210 tests, fixtures synthetiques)
- **Validation de parite** : `scripts/validate_fast_engine.py` (300 configs, 181K trades valides)

### Architecture Fast Grid Engine

Principe : pour un meme (groupe indicateur, zE, co, mm), les entrees sont identiques. Seules les sorties changent. On scanne les 5s UNE SEULE FOIS par groupe d'entrees, puis on replay N combos de sortie en O(1) par entree.

4 composants Numba dans `fast_grid_engine.py` :
1. `scan_entries()` — identifie toutes les entrees potentielles (ignore l'etat)
2. `build_paths_and_thresholds()` — scan forward unique, pre-calcule les seuils de croisement pour tous les zTP/zSL/dTP/dSL
3. `precompute_cooldown_reset()` — arrays de reset cooldown O(1) via backward scan
4. `replay_state_machine()` — replay rapide sans scan 5s, gere cooldown + reversal same-bar

Integration : `_process_indicator_group_fast()` dans `grid_search_runner.py`. Detection auto si `exit_mode == "micro_full"`.

### Architecture Config Vector (Numba)

Tous les parametres sont dans un numpy array `cfg[]`. Pour ajouter un parametre : ajouter `CFG_xxx` + extraction dans `pack_config()` + utiliser `cfg[CFG_xxx]` dans le kernel + incrementer `CFG_SIZE`.

### Regles moteurs

- Tout nouveau script dans `scripts/` importe depuis `backtest_engine_numba`. JAMAIS depuis hybrid.
- Ne jamais modifier `backtest_engine_hybrid.py` sauf bug de reference.
- Si on modifie la logique trading dans le kernel Numba, mettre a jour `backtest_engine_hybrid.py` ET `fast_grid_engine.py` en miroir.
- Tests unitaires (`tests/`) restent sur l'engine hybrid (Python pur).
- Benchmark de parite Numba : `python scripts/benchmark_numba.py`
- Validation parite Fast Grid : `python scripts/validate_fast_engine.py` (critere : 100% identique trade par trade)

## Contract Specifications

Configurable via `contracts.mode` dans `strategy_params.yaml` :

| Spec | GC (standard) | MGC (micro) | SI (standard) | SIL (micro) |
|------|---------------|-------------|---------------|-------------|
| Taille | 100 oz | 10 oz | 5,000 oz | 1,000 oz |
| Point Value | $100 | $10 | $5,000 | $1,000 |
| Tick Size | $0.10 | $0.10 | $0.005 | $0.005 |
| Tick Value | $10 | $1 | $25 | $5 |
| Ratio vs standard | 1x | 1/10 | 1x | 1/5 |

Mode par defaut : `standard`. Mode `micro` : smart multiplier (teste 1x..Nx SIL, garde meilleur arrondi dollar-neutral). GC libre (1-20 contrats typiques).
Commission: standard $4.00 RT, micro $1.88 RT. Slippage: 1 tick per leg (default in YAML, 2 ticks in grid searches).

## Position Sizing

Voir `docs/STRATEGY.md` pour les formules de sizing (standard et micro smart multiplier).
`FlatEndOfSession`: force exit at session_end_time CT (OBLIGATOIRE pour prop firm intraday). `MaxHoldingBars`: force exit after N bars.

## DataFrame Columns

Voir `calculate_all_indicators()` dans `indicators.py` pour les colonnes ajoutees au DataFrame. Signal generation dans `backtest_engine_numba.py` (pas de colonnes signal separees).

## Hardware

AMD Ryzen 9 7900X (12c/24t), 64 Go RAM, Windows 64-bit. Grid searches: `multiprocessing.Pool(24)`, ~600 Mo/worker (~15 Go total).

## Conventions

- Code in English, comments in French
- Timezone: Chicago Time (CT)
- Session: 17:30 - 15:30 CT (22 hours, 264 bars 5-min per day)
- User level: Python beginner, Sierra Chart expert
- Approach: Pedagogical, step-by-step with explanations

## Post-Edit Rules
Apres CHAQUE modification de code dans `src/` :
1. Lancer `pyright src/` — 0 errors obligatoire (warnings tolerees)
2. Lancer `pytest tests/ -v` — 0 failures obligatoire
3. Si la logique backtest a change : relancer le backtest de reference et comparer les metriques

## Plugin Usage Rules
**Auto** : pyright, context7
**Explicites** : comprehensive-review, unit-testing, quantitative-trading

## CRITICAL: HUMAN-ONLY Decisions
Ne JAMAIS modifier autonomement :
- `config/strategy_params.yaml`
- Choix des parametres d'entree/sortie (zE, zTP, dTP, dSL, mhb, mm)
- Seuils de filtres (cointegration_min, correlation_min, ADF gate)
- Decisions go/no-go entre phases (R1->R2->R3->paper->live)

Claude Code peut PROPOSER mais ne doit JAMAIS APPLIQUER sans validation explicite.

## Gotchas

### Terminal Windows
- **No emojis/accents in print()**: Windows cp1252 encoding crashes on special characters

### Strategy Parameters
- **correlation_min is redundant**: Always > 0.80 when Z-Score + Coint conditions met
- **hurst_max is redundant**: Hurst < 0.45 on all traded bars (use Cointegration Score instead)

### Code Quirks
- **ddof inconsistency**: Beta uses ddof=0, Z-Score uses ddof=1 (low impact but confusing)
- **Hurst min_sub_periods=2**: avec adf_hurst_period=26, seules les sous-periodes 8 et 16 sont disponibles (32 > 26)
- **MGC/SIL ratios asymetriques** : MGC = 1/10 de GC, SIL = 1/5 de SI. Sizing recalcule via `get_contract_specs()`

### Grid Search
- **Fast engine auto** : `exit_mode=micro_full` → fast engine. Autre mode → moteur Numba standard.
- **24 workers optimal**, ~600 MB/worker (~15 Go total)
- **Benchmark fast engine** : `python scripts/benchmark_fast_engine.py` (13.4x sur 1,792 variants/groupe)
- **stdout buffering**: use `PYTHONUNBUFFERED=1` or redirect to log file
- **Session prop firm** : entry_start=18:00 CT, entry_end=14:00 CT, FLAT_EOD=14:55 CT. Ces valeurs sont dans le YAML R1, pas hardcodees dans le moteur.
- **Lancer hors Claude Code** pour eviter crash si VS Code/Claude ferme :
  ```powershell
  Start-Process -NoNewWindow -FilePath ".venv\Scripts\python.exe" -ArgumentList "-u scripts/run_grid_search.py --config <yaml>" -RedirectStandardOutput "output/grid.log" -RedirectStandardError "output/grid_err.log"
  ```
  Toujours utiliser `python -u` (unbuffered) sinon stdout PowerShell ne montre rien.

### pack_config() Numba
- **Toujours verifier la source des parametres** : `ext` = exit, `ses` = session, `siz` = sizing. Le bug flat_end_of_session venait d'une lecture depuis `ext` au lieu de `ses`.
- **flat_end_of_session est OBLIGATOIRE** pour le prop firm (intraday). Ne jamais le desactiver.

### Git
- **Never git add -A**: Risk of committing .env or credentials - add files by name

## Data

- **Source**: Sierra Chart CSV exports (GCJ26 Gold futures, SIH26 Silver futures)
- **Period**: 2023-01-26 to 2026-01-30 (~3 years, 760+ trading days)
- **1-min bars**: 801,499 synchronized | **5s bars**: 4,604,839 synchronized
- **5s raw files** : `data/raw/GCJ26_FUT_CME_5secondes.scid_BarData.txt` + `SIH26_FUT_CME_5secondes.scid_BarData.txt` (chemins dans `config/strategy_params.yaml`)
- **Parquet cache**: `data/processed/` (auto-invalidated by MD5 hash). Indicators are NOT cached.

## Research Conclusions

- **Configs production** : voir status en haut du fichier. Details dans `CHANGELOG.md`.
- **5-min pure Z-Score = dominant mode**, 1min dollar = dead end, regime filters = dead end (none survives OOS)
- **Known risk**: regime-dependent (2023-2024 losing/flat, 2025-2026 profitable)
- See `CHANGELOG.md` for detailed tables and phase-by-phase results

## Sierra Chart Integration

v2.0 = automated spread trading (100% unmanaged orders). Python and SC produce identical indicator values (< 0.01% difference). 5/5 trades validated via replay.
- **Standard**: `F:\SierreChart_Backtest_2\ACS_Source\GC_SI_SpreadMeanReversion_v2.0.cpp` (GC/SI)
- **Micro**: `F:\SierreChart_Backtest_GC_SI_micro\ACS_Source\GC_SI_SpreadMeanReversion_v2.0_micro.cpp` (MGC/SIL, SCDLLName="GC_SI_SpreadMeanReversion_Micro", config C6, fixed x2 SIL)
- **SC Instance micro**: `F:\SierreChart_Backtest_GC_SI_micro\` — MGC chart + SIL chart, continuous contracts, volume rollover, back adjusted
- **Compilation**: via SC `Analysis > Build Custom Studies DLL` (pas le .bat)
- **Skill**: `.claude/skills/sierra-acsil/SKILL.md` — read FIRST for any ACSIL work
- **Critical gotchas**: NE PAS mixer managed/unmanaged orders. NE JAMAIS reset TradeState dans `IsFullRecalculation` (utiliser TradingInitialized PersistentInt flag).
- **Cross-symbol replay limitation**: SIL fills at live price during replay, not replay price (SC Support Board #22882). PnL unreliable for cross-symbol trades in replay mode.
- **Paper trading activation**: Input 16 = Yes + `Trade > Auto Trading Enabled` (Sim1 mode)
- See `CHANGELOG.md` for replay validation details

## Roadmap (TODO)

### Phase D -- Re-optimisation + Paper Trading (IN PROGRESS)
- [x] Grid search micro R1->R2c (INVALIDE — sizing cap=2 + FLAT_EOD OFF)
- [x] Deploy C6 in Sierra Chart v2.0 micro — plugin C++ correct, paper trading actif
- [x] Code review + fix sizing smart multiplier + fix flat_end_of_session path
- [x] Fast grid engine (scan 5s factorise, 13.4x speedup, 300/300 parite)
- [ ] **Grid search R1 micro CORRIGE** (~20M configs, ~4h, `configs/experiments/grid_micro_r1_corrected.yaml`) — NEXT
- [ ] Analyse top configs (4 scorings : PnL, Calmar, Consistency, Balanced)
- [ ] PnL decay + calibrage max_holding_bars
- [ ] Grid search R2 affinages sur top configs R1
- [ ] Walk-Forward + Monte Carlo sur config retenue
- [ ] Mise a jour plugin SC avec config validee
- [ ] Paper trading 4-8 weeks (min 30 trades)
- [ ] Production go-live

### Phase E -- MCP IBKR Volatility / Regime Dashboard (IN PROGRESS)
Branche: `feature/mcp-ibkr-volatility`. Serveur: `mcp_servers/ibkr_volatility/server.py`.
Skill: `.claude/skills/ibkr-volatility/SKILL.md`. Data: `data/vol_metrics/`.
- [x] MCP server minimal (ping, connect_tws) — chaine Claude Code -> TWS validee
- [x] get_iv_snapshot — IV ATM pour GC (OG) et SI (SO) via modelGreeks
- [x] backfill_iv_history — V30/HV30 2Y daily via ContFuture + Parquet
- [x] get_regime_dashboard — ratio IV, percentiles, deltas abs+pct, VRP z-scores, signaux
- [x] Filtre outliers V30 ContFuture (5%-100%), flag data_quality: filtered_contfuture
- [x] get_risk_reversal — RR25/RR10 via delta matching (code pret, a tester lundi)
- [ ] Valider get_iv_snapshot + get_risk_reversal marche ouvert — NEXT
- [ ] Ajouter signaux skew divergent (RR25 GC vs SI de signe oppose) dans dashboard
- [ ] Collecte daily automatique RR25/RR10 -> daily_snapshots.parquet
- [ ] Merge branche dans master une fois stabilise

### Future Tests (apres paper trading)
- [ ] Validation sur timeframes plus longs (15min, 1h)
- [ ] Focus sessions US uniquement
- [ ] TP dynamique en fonction de la volatilite

## Known Code Issues
- `run_hybrid_backtest()` dans backtest_engine_hybrid.py = 350+ lines (reference only, le kernel Numba est deja decompose en helpers inlines).
- **Bug end_session reference worker** : `_process_indicator_group` dans `grid_search_runner.py` compare a `'END_SESSION'` au lieu de `'FLAT_EOD'`. Le compteur `end_session` est toujours 0 dans les CSV du moteur standard. Pas bloquant (le fast worker est correct).
- **Calmar calcule en double** : le fast worker met `calmar` dans le dict `m`, puis `_micro_full_result_builder` le recalcule depuis `m["pnl_net"] / abs(m["max_dd"])`. Meme resultat, travail redondant. Ne pas diverger les deux calculs.

## Claude Code Skills
- **/backtest-runner** : Lance backtest hybrid + metrics, compare avec run precedent
- **/optimize** : Teste parametres via langage naturel FR, syntaxe "/" pour grid (ex: "teste beta 1320/2640")
- **/archive** : Archive campagnes, compare, genere rapports via `archive_manager.py`
- **/grid-search** : Grid search massif en background, genere rapport + CHANGELOG

## Git Tracking

`.gitignore` exclut : `.venv/`, `__pycache__/`, `data/raw/`, `DOC SIERRA/`, `.idea/`, `.claude/`
`output/` selective: `archive/` tracked (config.yaml + metrics.json), large files gitignored.

## Testing

210 tests, all passing. Synthetic data (fixtures in `conftest.py`), no dependency on real CSV files.

## Mandatory Pre-Read Rules

Before ANY action, Claude Code MUST read the relevant file FIRST:

| Trigger | Read FIRST |
|---------|-----------|
| C++ / Sierra Chart / ACSIL / .cpp | `.claude/skills/sierra-acsil/SKILL.md` |
| IBKR / TWS / IV / options / greeks / vol / regime / mcp_servers | `.claude/skills/ibkr-volatility/SKILL.md` |
| Backtest / optimizer / grid search | `docs/ARCHITECTURE.md` |
| Grid search micro_full / fast engine | `src/fast_grid_engine.py` (header + composants) |
| Entry/exit logic / state machine | `docs/STRATEGY.md` |
| Config changes / parameters | `config/strategy_params.yaml` |
| Phase history / past results | `CHANGELOG.md` |
