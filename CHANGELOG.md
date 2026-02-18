# CHANGELOG.md

Historique des optimisations, resultats detailles et ameliorations du backtest GC/SI.

---


## [2026-02-18] Phase D — Walk-Forward + Monte Carlo validation (10 configs micro)

### Contexte
Selection de 10 configs candidates depuis R2a+R2b (30M configs). Filtres : trades>=200, PnL>=7000, DD>=-2500.
8 configs choisies manuellement par l'utilisateur + 2 suggestions Claude (C09, C10).

### 10 Configs testees

| # | Config | Trades (grid) | PnL (grid) | DD (grid) |
|---|--------|---------------|------------|-----------|
| C01 | b4620_zE3.6_dTP225_nohold_es22 | 152 | $8,750 | -$1,175 |
| C02 | b4620_zE3.55_dTP250_mhb18_es18 | 248 | $9,645 | -$2,408 |
| C03 | b7920_zE3.45_dTP175_mhb18_es22 | 200 | $8,038 | -$710 |
| C04 | b4620_zE3.6_dTP250_nohold_es22 | 151 | $9,119 | -$1,100 |
| C05 | b4620_zE3.6_dTP250_mhb18_es22 | 151 | $8,711 | -$1,030 |
| C06 | b2640_zE3.4_dTP225_nohold_es22 | 217 | $9,167 | -$1,274 |
| C07 | b2640_zE3.4_dTP200_nohold_es22 | 219 | $8,575 | -$765 |
| C08 | b2640_zE3.5_dTP225_mhb18_es0 | 170 | $7,899 | -$1,085 |
| C09 | b2640_zE3.4_dTP200_nohold_es0 | 238 | $8,101 | -$908 |
| C10 | b2640_zE3.3_dTP200_nohold_es0 | 260 | $7,949 | -$1,290 |

Toutes en micro, 5-min, session prop firm (es->14h, FLAT_EOD 14:55), slippage 2 ticks, mm_max=2.

### Phase 1 — Walk-Forward individuel (script: `scripts/run_wf_phase1.py`)
- Rolling cumulatif : train W1..N, test W(N+1). 6 fenetres de ~6 mois, 5 tests OOS.
- Critere : PnL OOS positif sur >= 3/5 fenetres.

| Config | OOS1 | OOS2 | OOS3 | OOS4 | OOS5 | POS | Verdict |
|--------|------|------|------|------|------|-----|---------|
| C01 | -$2,904 | -$62 | -$193 | -$1,110 | -$9,061 | 0/5 | FAIL |
| C02 | -$1,650 | -$1,365 | +$32 | -$207 | -$460 | 1/5 | FAIL |
| **C03** | -$774 | +$1,223 | +$1,554 | +$215 | -$6,153 | **3/5** | **PASS** |
| C04 | -$2,904 | -$62 | -$193 | -$1,110 | -$9,061 | 0/5 | FAIL |
| C05 | -$1,385 | -$248 | +$124 | -$137 | +$3,077 | 2/5 | FAIL |
| C06 | -$868 | +$559 | -$235 | +$220 | -$3,629 | 2/5 | FAIL |
| C07 | -$868 | +$559 | -$235 | +$220 | -$3,629 | 2/5 | FAIL |
| C08 | -$2,454 | -$17 | -$535 | -$652 | +$4,527 | 1/5 | FAIL |
| **C09** | -$1,869 | +$465 | +$329 | -$1,094 | +$4,039 | **3/5** | **PASS** |
| C10 | -$1,020 | +$669 | -$337 | -$163 | -$3,390 | 1/5 | FAIL |

**Survivants Phase 1 : 2/10** (C03, C09). C05 repris pour Phase 2 (PnL OOS total positif +$1,430).

### Phase 2 — Monte Carlo OOS (script: `scripts/run_wf_phase2_mc.py`)
- 1000 resamplings bootstrap sur trades OOS concatenes.
- Criteres : PnL P5 >= $0 ET DD P95 >= -$3,000.

| Config | Trades OOS | PnL P5 | PnL P50 | DD P95 | Verdict |
|--------|-----------|--------|---------|--------|---------|
| C03 | 77 | -$10,160 | -$3,756 | -$1,918 | FAIL (PnL) |
| C05 | 80 | -$5,421 | +$1,259 | -$1,469 | FAIL (PnL) |
| C09 | 88 | -$5,726 | +$1,491 | -$1,706 | FAIL (PnL) |

**Survivants Phase 2 : 0/3.** DD OK pour les 3, mais PnL P5 negatif (pas assez d'edge avec ~80 trades).

### Phase 2b — Analyse par annee + MC in-sample (script: `scripts/run_phase2b_yearly_mc.py`)

**Anomalie detectee** : le moteur standalone Numba produit 84-92 trades vs 200-260 dans le grid search pour les memes configs. Ecart ~2x non explique — investigation en cours.

| Config | 2023 | 2024 | 2025 | 2026 (1 mois) | TOTAL | MC IS PnL P5 |
|--------|------|------|------|---------------|-------|-------------|
| C03 | -$723 (24tr) | +$1,778 (27tr) | -$1,788 (30tr) | -$2,501 (7tr) | **-$3,234** (88tr) | -$10,068 FAIL |
| C05 | -$1,275 (31tr) | -$409 (33tr) | -$932 (24tr) | +$3,871 (4tr) | **+$1,255** (92tr) | -$5,907 FAIL |
| C09 | -$1,544 (29tr) | +$797 (25tr) | +$577 (28tr) | +$3,187 (2tr) | **+$3,018** (84tr) | -$4,447 FAIL |

Exit reasons : C03/C05 dominees par MAX_HOLD (62-64%), C09 dominee par TP_ZSCORE (89%).

### Conclusions provisoires
- **Ecart trades grid vs standalone** : probleme majeur a investiguer (mismatch config propagation probable)
- **C09 meilleur candidat structurel** : 3/4 annees positives, 89% TP_ZSCORE, PnL median MC +$2,934
- **MC trop strict pour ~85 trades** : avg PnL +$14-36/trade insuffisant pour passer P5 > $0

---

## [2026-02-16] CRITICAL — Double bug sizing + FLAT_EOD invalide tous les grid searches

### Code Review complete (src/ + MCP + tests)
Review exhaustive declenchee apres premier trade paper trading. 6 bugs src/, 6 bugs MCP, 4 modules sans tests (2,400 lignes).

### Bug #1 — Micro sizing Numba (CRITIQUE)
- **Fichier** : `backtest_engine_numba.py:_calc_size()`
- **Probleme** : `micro_mult_max` utilise comme cap sur GC+SI au lieu de multiplicateur SIL
- **Impact** : GC cape a 2 contrats au lieu de 10-13. Dollar neutral completement casse.
- **Fix** : Logique smart multiplier identique a `position.py` — teste 1x..Nx SIL, garde meilleur arrondi
- **Avant/Apres (sans FLAT_EOD)** : $11,803 / PF 2.33 / DD -$965 → $14,757 / PF 2.32 / DD -$1,794

### Bug #2 — flat_end_of_session jamais actif dans Numba (CRITIQUE)
- **Fichier** : `backtest_engine_numba.py:pack_config()` ligne 186
- **Probleme** : `ext.get('flat_end_of_session')` lit `config['exit']`, mais le parametre est dans `config['session']`
- **Impact** : FLAT_EOD = OFF dans TOUS les grid searches R1-R2c, meme avec override `session.flat_end_of_session: True`
- **Fix** : `ses.get('flat_end_of_session')` (lit depuis `config['session']`)

### Bug #3 — pack_config ne resolvait pas les contract specs micro/standard
- **Fix** : auto-resolution `contracts.gc_point_value` etc. depuis `contracts.mode`

### Impact combine (sizing + FLAT_EOD)

| Metrique | Ancien (2 bugs) | Sizing fixe seul | Sizing + FLAT_EOD |
|----------|-----------------|-------------------|-------------------|
| Trades   | 258             | 262               | 290               |
| PnL Net  | $11,803         | $14,757           | $7,959            |
| PF       | 2.33            | 2.32              | 1.64              |
| Max DD   | -$965           | -$1,794           | -$2,086           |
| Costs    | ~$5K            | $7,873            | ~$8.5K            |

### Corrections MCP server (5 fixes)
- `all([])` → check `len(tickers) > 0` avant continue
- `ib.isConnected()` check dans boucles polling
- `ib.reqCurrentTime()` protege par `isConnected()` dans 3 tools
- `min(strikes)` → check liste vide
- Hybrid : `END_SESSION` → `FLAT_EOD` (parite Numba)

### Consequences
- **Grid searches R1-R2c : INVALIDES** — tous tournes avec sizing cap=2 et FLAT_EOD=OFF
- **Config C6 : NON VALIDEE** — selectionnee sur metriques fausses
- **SC live : CORRECT** — le plugin C++ fait le bon calcul (sizing libre + FLAT_EOD ON)
- **Action** : relancer grid search R1 complet avec moteur corrige

### Premier trade paper trading (avant decouverte bugs)
- 2026-02-16 00:57 CT : ENTRY SHORT 10 MGC @ 5018.30 / 2 SIL @ 76.86, Z=3.26
- 2026-02-16 01:01 CT : EXIT TP_DOLLAR $257 net ($280 gross - $23 comm), 1 barre
- Sizing SC coherent avec moteur Numba corrige (10 MGC / 2 SIL)

---

## [2026-02-16] Fix -- Entry Hour Wrap-around + Optimizer 5min Resample + Cleanup

### Bugs corriges (commit ddaf96a)
- **Entry hour wrap-around** : `entry_start_h > entry_end_h` (ex: 21h-6h overnight) retournait toujours False. Ajoute gestion overnight dans les 2 moteurs.
- **Optimizer 5-min resample** : `optimizer.py` calculait sur 1-min quand `period: "5min"` (Z-Score lookback 5x trop court). Fix : appel `resample_to_5min()` dans run_single_config().
- **Session times mismatch** : grid_search_runner ecrit `session.flat_end_of_session` mais pack_config lit `exit.flat_end_of_session` (non corrige, impact mineur).

### Cleanup tests orphelins
- Supprime `tests/test_phase_c1.py` et `tests/test_phase_c2.py` (importaient des modules supprimes : phase_c1_walkforward, phase_c2_multifilter_exploration)
- Tests : 210 passed (vs 223 avant, 13 tests retires)

---

## [2026-02-15] Phase E -- MCP IBKR Volatility Server (IN PROGRESS)

**Branche** : `feature/mcp-ibkr-volatility` | **Serveur** : `mcp_servers/ibkr_volatility/server.py`

### Architecture
- **Framework** : FastMCP + ib_insync, port TWS 7497, clientId 50
- **Data** : `data/vol_metrics/*.parquet`
- **Fix** : nest_asyncio.apply() obligatoire (conflit event loop FastMCP/ib_insync)

### Outils implementes
1. **ping** -- test connectivite MCP
2. **connect_tws** -- connexion TWS, retourne compte + heure serveur
3. **get_iv_snapshot** -- IV ATM pour GC (OG) et SI (SO) via modelGreeks
4. **backfill_iv_history** -- V30/HV30 2Y daily via ContFuture + Parquet (filtre outliers 5%-100%)
5. **get_regime_dashboard** -- ratio IV, percentiles, VRP z-scores, signaux couleur
6. **get_risk_reversal** -- RR25/RR10 via delta matching (code pret, a tester marche ouvert)

### Prochaines etapes
- [ ] Valider get_iv_snapshot + get_risk_reversal marche ouvert
- [ ] Signaux skew divergent (RR25 GC vs SI de signe oppose)
- [ ] Collecte daily automatique -> daily_snapshots.parquet
- [ ] Merge dans master une fois stabilise

---

## [2026-02-11] Phase D -- Sierra Chart Micro Deployment + Replay Validation

### Deploiement SC v2.0 micro
- **Instance** : `F:\SierreChart_Backtest_GC_SI_micro\`
- **Study** : `GC_SI_SpreadMeanReversion_v2.0_micro.cpp` (SCDLLName="GC_SI_SpreadMeanReversion_Micro")
- **Config** : C6 b3960_zp33_cp27_adf144_zE3.25_co45_zTP0.0_dTP250, fixed x2 SIL
- **Compilation** : via SC `Analysis > Build Custom Studies DLL`
- **Paper trading** : Input 16 = Yes + `Trade > Auto Trading Enabled` (Sim1 mode)

### Bug fix : Full Recalc reset (commit 4cf1223)
- **Symptome** : Position oubliee apres reconnexion data, aucune sortie generee
- **Cause** : `TradeState = STATE_FLAT` dans `if (sc.Index == 0 || sc.IsFullRecalculation)` -- AutoLoop reprocesse depuis index 0 sur full recalc, resetant l'etat trading
- **Fix** : PersistentInt(9) `TradingInitialized` flag, init trading seulement si flag==0
- **Regle** : NE JAMAIS reset l'etat trading sur IsFullRecalculation dans un study AutoLoop

### Bug fix : Indicateurs 5-min + Hurst sub-periods (commit 4cf1223)
- **Bug 1** : `backtest_engine_hybrid.py` main ignorait `indicators.period: "5min"` -- calculait sur 1-min (20-min lookback au lieu de 100-min). Grid searches corrects (utilisaient resample_to_5min).
- **Bug 2** : Hurst exigeait 3 sub-periods minimum, mais adf_hurst_period=26 n'en a que 2 (8, 16). SC accepte 2 -- Python retournait NaN -- Coint Score gonfle de +20pts.

### Replay validation (1 mois Jan 2026)
- **5/5 trades** : entree + sortie identiques SC vs Python
- **158,241 barres** comparees : Z-Score median delta 0.005 (<0.1%), 85% concordance signaux entree
- **Limitation cross-symbol** : SC remplit les ordres cross-symbol au prix live, pas au prix replay (SC Support Board #22882). PnL unreliable en replay pour cross-symbol.

### Trades 17:30 CT = artefacts de gap
- 18/258 trades C6 entrent a 17:30 (premiere barre) -- 16/18 sont des artefacts
- Z-Score perd ~55% de valeur absolue en 30 min (gap donnees 15:30->17:30)
- Impact PnL : ~$1,810 / $11,803 (15%) -- PnL reel sans artefacts ~$9,993
- Pas de fix code : signal visuel ignorable en live

---

## [2026-02-14] CONFIG MICRO RETENUE -- GO Paper Trading

### Config retenue : C6
- **Nom complet** : `b3960_zp33_cp27_adf144_zE3.25_co45_zTP0.0_dTP250`
- **Mode** : micro (MGC/SIL), multiplier max = 2, slippage 1 tick
- **Resultats backtest** : 258 trades, $11,803 PnL, PF 2.33, DD -$965, Sharpe 0.26, Calmar 12.23
- **Consistency** : 72.2% mois positifs, 3/4 ans rentables (2024 flat -$45)
- **Walk-Forward** : 4/5 fenetres profitables, $10,571 cumul OOS, Sharpe 1.14
- **Monte Carlo i.i.d.** : median $9,312 / 200 trades, 0% hit -$3K DD, 100% profitable
- **Monte Carlo block k=5** : median $8,843 / 200 trades, 0.2% hit -$3K DD, 99.9% profitable

### Backup : C9
- `b4620_zp30_cp30_adf96_zE3.5_co40_zTP0.0_dTP250`
- 174 trades, $8,203 PnL, OOS Sharpe 1.21

### Parametres fixes (identiques C6/C9)
- zSL=99 (disabled), dSL=0 (disabled), mhb=0 (disabled)
- flat_end_of_session=True

### Pipeline de validation complete
1. Grid Search R1 (252K configs) -> R2a/R2b/R2c (affinages successifs)
2. PnL Decay Analysis (intra-trade bar-par-bar)
3. Deep Analysis temporelle (10 configs, stabilite annuelle)
4. Walk-Forward 5 fenetres anchored expanding
5. Monte Carlo bootstrap (i.i.d. + block k=5)
6. **Verdict : GO paper trading avec C6**

### Reorganisation output/
Fichiers micro reorganises dans structure propre :
- `output/grid_searches/r1|r2a|r2b|r2c/` -- resultats grid search
- `output/reports/` -- rapports d'analyse (inchange)
- `output/plots/pnl_decay|monte_carlo/` -- graphiques
- `output/logs/` -- logs grid search
- `output/configs_archive/` -- copies YAML
- `output/legacy/` -- anciens fichiers pipeline standard (phases B/C)

---

## [2026-02-14] Monte Carlo Bootstrap C6 (i.i.d. + Block k=5)

### Resultats i.i.d. (1,000 chemins, 200 trades)
| Metrique | Median | P5 | P95 |
|----------|--------|----|----|
| PnL final | $9,312 | $5,648 | $13,005 |
| Max DD | -$846 | -$1,497 | -$511 |
| Sharpe | 2.78 | 1.67 | 3.96 |

### Resultats Block k=5 (1,000 chemins, 200 trades)
| Metrique | Median | P5 | P95 |
|----------|--------|----|----|
| PnL final | $8,843 | $4,421 | $13,372 |
| Max DD | -$1,055 | -$2,130 | -$524 |
| Sharpe | 2.54 | 1.14 | 3.89 |

### Risque prop firm
| Critere | i.i.d. | Block k=5 |
|---------|--------|-----------|
| Hit -$3K DD | 0.0% | 0.2% |
| Profitable 200 trades | 100.0% | 99.9% |

### Scripts et fichiers
- Script: `scripts/monte_carlo_c6.py`
- Rapport: `output/reports/MONTE_CARLO_C6.md`
- Graphiques: `output/plots/monte_carlo/`

---

## [2026-02-14] Walk-Forward Validation C6 & C9

### Contexte
Validation OOS des 2 configs finalistes issues du R2c. Protocole anchored expanding window (5 fenetres, train cumulatif depuis 2023).

### Configs testees
- **C6** (Primary) : b3960_zp33_cp27_adf144_zE3.25_co45_zTP0.0_dTP250 -- 258 trades
- **C9** (Backup) : b4620_zp30_cp30_adf96_zE3.5_co40_zTP0.0_dTP250 -- 174 trades

### Resultats Walk-Forward

| Config | Windows profit. | Cumul OOS PnL | OOS Sharpe | Pire window |
|--------|-----------------|---------------|------------|-------------|
| **C6** | **4/5 (80%)** | **$10,571** | **1.14** | W2 -$192 |
| **C9** | **4/5 (80%)** | **$7,316** | **1.21** | W1 -$541 |

#### Detail par fenetre

| Window | Test Period | C6 PnL | C6 WR | C9 PnL | C9 WR |
|--------|-------------|--------|-------|--------|-------|
| W1 | Jan-Jun 2024 | $147 | 65% | -$541 | 60% |
| W2 | Jul-Dec 2024 | -$192 | 67% | $492 | 76% |
| W3 | Jan-Jun 2025 | $1,235 | 59% | $1,088 | 87% |
| W4 | Jul-Dec 2025 | $3,259 | 76% | $2,424 | 73% |
| W5 | Jan 2026 | $6,123 | 100% | $3,853 | 100% |

Pas de degradation : performance ameliore au fil du temps (W3-W5 >> W1-W2).

### Investigation regime 2024
- **Trades perdants 2024 = 100% TP_ZSCORE** (32/32 C6, 20/20 C9). Zero TP_DOLLAR perdant.
- Spread volatilite identique 2023 vs 2024 (std=0.01). ADF identique (-1.74 vs -1.69).
- **Conclusion** : 2024 flat = bruit statistique sur TP_ZSCORE, pas un probleme structurel.

### Classement final
1. **C6** -- Primary prop firm (volume + consistency 72.2% mois+)
2. **C9** -- Backup solide (meilleur Sharpe OOS 1.21)
3. C1 -- Conservateur (4/4 ans, DD -$1,147)
4. C3 -- Reserve (106 trades, trop peu)
5. ~~C5~~ -- Elimine (consistency insuffisante 57.1%)

### Scripts et fichiers
- Script: `scripts/walkforward_c6_c9.py`
- Rapport: `output/reports/WALKFORWARD_C6_C9.md`


## [2026-02-14] Grid Search Micro R2c -- Affinage C2 Sweet Spot

### Contexte
Suite au R2b (2.9M configs), C2 (b3960_zp36_cp30_adf128_zE3.25_co50) etait le seul profil stable 4/4 ans. R2c affine autour de ce sweet spot avec 200,000 configs (625 groupes indicateurs x 320 exits).

### Grille R2c
- beta: [3300, 3630, 3960, 4290, 4620]
- zp: [30, 33, 36, 39, 42], cp: [24, 27, 30, 33, 36], adf: [96, 112, 128, 144, 160]
- zE: [3.0, 3.125, 3.25, 3.375, 3.5], co: [40, 45, 50, 55]
- zTP: [0.0, 0.5, 1.0, 1.5], dTP: [250, 300, 350, 400]
- Fixes: zSL=99, dSL=0, mhb=0, mm=2, micro mode, slippage 1 tick

### Resultats globaux
- 200,000 configs, 84,734 profitables (42.4%)
- Filtre (trades>=80, PF>=1.3, DD>=-$3,000): 15,387 configs (7.7%)

### Top 3 Sharpe (filtres)

| Rk | Config | Trades | WR | PnL | PF | DD | Sharpe |
|----|--------|--------|----|-----|----|----|--------|
| 1 | b4620_zp30_cp27_adf160_zE3.5_co45_zTP0.0_dTP300 | 139 | 71% | $6,044 | 2.44 | -$1,147 | 0.320 |
| 2 | b4620_zp30_cp27_adf160_zE3.5_co45_zTP0.0_dTP250 | 139 | 71% | $5,244 | 2.25 | -$1,147 | 0.300 |
| 3 | b4290_zp33_cp30_adf128_zE3.5_co50_zTP0.0_dTP300 | 106 | 71% | $4,679 | 2.28 | -$861 | 0.290 |

Best PnL: C6 b3960_zp33_cp27_adf144_zE3.25_co45_zTP0.0_dTP250 -- 258 trades, $11,803 PnL, Calmar 12.23

### Deep Analysis -- Stabilite temporelle (10 configs)

**3 configs stables 4/4 ans:**

| Config | Trades | PnL | Mois+ | 2023 | 2024 | 2025 | 2026 |
|--------|--------|-----|-------|------|------|------|------|
| C1 b4620_zp30_cp27_adf160_dTP300 | 139 | $6,044 | 67.6% | $5 | $608 | $2,627 | $2,804 |
| C2 b4620_zp30_cp27_adf160_dTP250 | 139 | $5,244 | 67.6% | $5 | $608 | $2,327 | $2,304 |
| C3 b4290_zp33_cp30_adf128_dTP300 | 106 | $4,679 | 60.6% | $22 | $343 | $1,791 | $2,523 |

**Meilleure consistency mensuelle:** C6 b3960 (72.2% mois+, $328/mois moyen) mais 3/4 ans (-$45 en 2024)

### Conclusions cles
- **zTP=0.0 domine** : pure mean reversion avec dollar TP = meilleur profil
- **Beta long confirme** : b3960-4620 (15-18 jours) = zone optimale
- **TP_ZSCORE profitable** : $11-18 avg (vs breakeven en R2b) grace au beta plus long
- **Neighborhood MARGINAL** : aucune config "STABLE" par voisinage, toutes MARGINAL
- **C1/C2 = meme config** (seul dTP differe), C1 (dTP300) legerement meilleur

### Scripts et fichiers
- Config: `configs/experiments/grid_micro_r2c.yaml`
- Analyse: `scripts/deep_analysis_r2c.py`
- Rapports: `output/grid_searches/r2c/grid_micro_r2c_report.txt`, `output/reports/R2C_DEEP_ANALYSIS.md`
- Donnees: `output/grid_searches/r2c/grid_micro_r2c.csv`


## [2026-02-08] Phase C4bis -- Block Bootstrap + Filtre horaire

### Contexte
L'audit quant (QUANT_AUDIT_V1.md) a revele une autocorrelation PnL forte (r=0.50 lag 1, p<0.0001), invalidant le bootstrap i.i.d. de C4 (P(perte)=0.9%). Le block bootstrap preserve la structure temporelle des trades.

### Block Bootstrap (1000 sims, seed=42)

#### Comparaison i.i.d. vs block (horizon 100 trades)

| Methode | P(perte) | PnL P5 | PnL Median | PnL P95 | MaxDD P5 |
|---------|----------|--------|------------|---------|----------|
| i.i.d. (C4) | 0.9% | $10,911 | $45,395 | $85,997 | -$13,877 |
| Block k=3 | 9.4% | -$6,672 | $30,022 | $76,697 | -$16,162 |
| **Block k=5** | **19.1%** | **-$14,610** | **$19,946** | **$78,383** | **-$20,730** |
| Block k=7 | 25.8% | -$19,442 | $16,766 | $77,271 | -$22,873 |
| Block k=10 | 37.7% | -$21,996 | $8,450 | $69,459 | -$23,612 |

Ratio de sous-estimation i.i.d. : **21x** (0.9% vs 19.1%)

#### Block k=5, tous horizons

| Horizon | P(perte) | PnL P5 | PnL Median | PnL P95 |
|---------|----------|--------|------------|---------|
| 50 trades | 29.7% | -$11,576 | $10,476 | $50,594 |
| 100 trades | 19.1% | -$14,610 | $19,946 | $78,383 |
| 150 trades | 11.5% | -$9,047 | $34,436 | $98,580 |
| 200 trades | 8.2% | -$6,439 | $48,732 | $122,120 |

#### Autocorrelation confirmee
- Lag 1: r=0.5009, p<0.001 (magnitude des PnL)
- Test de runs: p=0.87 (sequence win/loss aleatoire)
- => L'autocorrelation vient des regimes, pas de la direction

### Filtre horaire

| Mode | Trades | PnL | WR | PF | MaxDD | PnL/Trade |
|------|--------|-----|----|----|-------|-----------|
| A: 24h (baseline) | 100 | $45,224 | 53% | 2.41 | -$17,341 | $452 |
| B: Block 0-9h CT | 61 | $49,461 | 56% | 4.45 | -$4,555 | $811 |
| C: Block 0-8h CT | 64 | $46,237 | 53% | 3.64 | -$6,958 | $722 |

- Mode B ameliore PF (x1.8), MaxDD (x3.8 mieux), PnL (+$4.2K) mais perd 39 trades
- Amelioration < $5,000 => pas de walk-forward
- Verdict: **MONITOR** -- a surveiller en paper trading

### Verdict global C4bis
- Block bootstrap: **GO** (P(perte 100tr) = 19.1% < 20%)
- Sizing recommande: **0.5x** (P(perte) entre 10-20%)
- Filtre horaire: **MONITOR** (prometteur mais echantillon insuffisant)
- **Le risque reel est 21x plus eleve que le Monte Carlo i.i.d.**

### Scripts
- `scripts/phase_c4bis_block_bootstrap.py`
- `scripts/quant_audit_v1.py`

### Fichiers generes
- `output/phase_c4bis_block_bootstrap_results.csv`
- `output/phase_c4bis_summary.csv`
- `output/phase_c4bis_hourly_filter.csv`
- `output/reports/PHASE_C4BIS_RESULTS.md`
- `output/reports/QUANT_AUDIT_V1.md`


## [2026-02-08] Phase C5 -- Slippage Stress Test (GO)

**Script**: `scripts/phase_c5_slippage_stress.py` | **Configs testees**: 2 (b3960 WF best, b2640 B2 top) x 4 slippages

### Resultats

| Slippage | b3960 (WF best) | b2640 (B2 top) |
|----------|-----------------|----------------|
| 1 tick | $32,948 | $52,804 |
| 2 ticks | $23,928 | $45,224 |
| 2.5 ticks | $19,418 | $41,434 |
| 3 ticks | $14,908 | $37,644 |

### Marges de securite

| Config | Cout/tick/trade | Breakeven | Marge vs 2 ticks |
|--------|----------------|-----------|------------------|
| b3960 | $74 | 4.7 ticks | 2.7 ticks |
| b2640 | $76 | 8.0 ticks | 6.0 ticks |

### Monte Carlo a 2.5 ticks

- b3960 : P(perte 100tr) = 8.0%
- b2640 : P(perte 100tr) = 3.0%

### Verdict

**GO** -- Les deux configs survivent largement. Config production recommandee : **b2640** (marge de securite 6.0 ticks, breakeven 8.0 ticks).

---


## [2026-02-08] Phase C4 -- Monte Carlo Bootstrap 1000 simulations (GO)

**Script**: `scripts/phase_c4_monte_carlo.py` | **Source**: backtest complet 3 ans, config b2640 (100 trades, WR 53%, PnL moyen $452)

### Resultats

| Horizon | P(perte) | PnL P5 | PnL Median | PnL P95 |
|---------|----------|--------|------------|---------|
| 50 trades | 5.1% | -$21 | $20,441 | $49,911 |
| 100 trades | 0.9% | $10,911 | $45,395 | $85,997 |
| 150 trades | 0.4% | $26,540 | $65,454 | $119,433 |
| 200 trades | 0.1% | $40,278 | $88,624 | $144,414 |

### Criteres GO/NO-GO (100 trades)

- P(perte) = 0.9% < seuil 30% -- **GO**
- MaxDD P5 = -$13,877 > seuil -$25,000 -- **GO**
- MaxDD median = -$7,014

### Analyse par direction

- LONG : P(perte 100tr) = 1.8%
- SHORT : P(perte 100tr) = 1.0%

### Attention

Le bootstrap melange les epoques et masque le risque de regime (2023-2024 perdants, 2025-2026 tres profitables). C'est une borne optimiste.

### Verdict

**GO** -- Strategie validee statistiquement. P(perte) tres faible a tous les horizons.

---


## [2026-02-08] Phase C3 -- Walk-Forward Final avec filtre Correlation (NO-GO)

**Script**: `scripts/phase_c3_walk_forward.py` | **Fenetres**: 34 (63j train / 21j test) | **Seuil Correlation**: 0.86

### Resultats globaux

| Metrique | Sans Filtre | Avec Filtre (0.86) | Delta |
|----------|-------------|-------------------|-------|
| PnL total | $21,666 | $19,730 | -$1,936 |
| Trades | 135 | 130 | -5 |
| Fenetres positives | 15/34 (44%) | 15/34 (44%) | 0 |
| PF | 1.71 | 1.80 | +0.09 |
| MaxDD | -$16,876 | -$15,607 | +$1,269 |

### Diagnostic

Le filtre ne bloque que 5/135 trades directement. L'effet principal est indirect : il change les metriques TRAIN et donc la config selectionnee par fenetre. Parfois en bien (W27 : -$3,041 -> +$2,726), parfois en mal (W32 : +$5,664 -> -$153).

### Verdict

**NO-GO** -- Le filtre Correlation ne tient pas en walk-forward hors-echantillon. L'avantage observe en backtest complet (PF 7.84) etait du sur-ajustement sur les periodes toxiques connues. **Conclusion definitive : aucun filtre de regime teste ne fonctionne en OOS.**

---


## [2026-02-08] Phase C2b -- Integration filtre regime + Analyse sensibilite

**Scripts**: `scripts/phase_c2b_comparison.py`, `scripts/phase_c2b_sensitivity.py`
**Tests**: `tests/test_phase_c2b.py` (15 tests)

### Implementation

- 2 indicateurs ajoutes dans `indicators.py` : `calculate_halflife_ar1()`, `calculate_rolling_correlation_daily()`
- Blocage des entrees dans `backtest_engine_hybrid.py` (logique OR, ne touche pas les positions ouvertes)
- Section `regime_filter` dans `strategy_params.yaml` (enabled: false par defaut)
- 15 tests unitaires, 203 tests total

### Resultats comparaison A/B/C/D

| Mode | PnL | Delta | Trades | WR | PF | MaxDD | Sharpe |
|------|-----|-------|--------|-----|-----|-------|--------|
| A: Baseline | $30,184 | - | 100 | 52% | 2.65 | -$8,175 | 0.194 |
| B: Half-life seul | $29,600 | -$584 | 88 | 52% | 2.79 | -$8,123 | 0.204 |
| C: Correlation seule | $35,001 | +$4,817 | 33 | 64% | 10.82 | -$1,450 | 0.433 |
| D: Combines | $35,001 | +$4,817 | 33 | 64% | 10.82 | -$1,450 | 0.433 |

### Analyse sensibilite seuil Correlation

Signal robuste : degradation progressive de 0.80 a 0.98 (pas d'effet de seuil brutal = pas de curve-fitting).
- Sweet spot : seuil 0.86 (52 trades, $38,037, PF 7.84, MaxDD -$1,563)
- Chute nette a 0.93+ (filtre trop agressif, bloque les bons trades)

### Conclusions

- **Half-life AR(1)** : inutile en combinaison (D = C), quasi-inutile seul (-$584)
- **Correlation Daily** : game changer en backtest complet -- mais doit etre valide en walk-forward (-> C3)
- Seuil retenu pour C3 : **0.86**

---


## [2026-02-07] Grid Search -- Phase B3 - 5min Hybride (zTP + dollar SL) 2 ticks - 41472 configs

**Configs**: 41,472 | **Profitable**: 5,764 (13.9%)
Results: `output/grid_search_B3_5min_hybrid_2tick.csv`

### Top 10 by PnL Net

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b2640_zp30_cp24_adf26_zE3.5_co40_zTP-1.0_SL1200_TPcap2500 | 249 | 58.2% | $25,164 | 1.34 | -$9,567 | 0.10 |
| 2 | b3960_zp24_cp96_adf128_zE3.5_co40_zTP-0.5_SL2500_TPcap800 | 113 | 67.3% | $22,347 | 2.38 | -$7,378 | 0.31 |
| 3 | b2640_zp30_cp24_adf26_zE3.5_co40_zTP-0.5_SL1200_TPcap2500 | 251 | 58.6% | $22,098 | 1.32 | -$10,292 | 0.09 |
| 4 | b3960_zp30_cp96_adf96_zE3.5_co40_zTP0.0_SL2500_TPcap800 | 156 | 67.9% | $21,754 | 1.87 | -$6,339 | 0.22 |
| 5 | b2640_zp24_cp24_adf26_zE3.5_co40_zTP0.0_SL2500_TPcap2500 | 178 | 57.9% | $21,662 | 1.55 | -$9,291 | 0.13 |
| 6 | b2640_zp30_cp24_adf26_zE3.5_co40_zTP-1.0_SL2500 | 247 | 57.1% | $21,146 | 1.23 | -$13,636 | 0.06 |
| 7 | b3960_zp30_cp96_adf128_zE3.5_co40_zTP-0.5_SL2500_TPcap800 | 172 | 66.3% | $20,979 | 1.62 | -$10,434 | 0.18 |
| 8 | b3960_zp30_cp96_adf128_zE3.5_co40_zTP0.0_SL2500_TPcap800 | 172 | 66.9% | $20,894 | 1.68 | -$8,629 | 0.18 |
| 9 | b3960_zp24_cp96_adf128_zE3.5_co40_zTP-1.0_SL2500_TPcap800 | 113 | 69.9% | $20,877 | 2.07 | -$9,051 | 0.26 |
| 10 | b2640_zp30_cp24_adf26_zE3.5_co40_zTP-1.0_SL2500_TPcap2500 | 249 | 59.0% | $20,849 | 1.25 | -$9,372 | 0.08 |


### Top 10 by Sharpe (min 10 trades)

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP0.0_SL1800_TPcap800 | 25 | 80.0% | $6,874 | 5.71 | -$663 | 0.74 |
| 2 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP0.0_SL1200_TPcap800 | 25 | 80.0% | $6,874 | 5.71 | -$663 | 0.74 |
| 3 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP0.0_SL800_TPcap800 | 25 | 80.0% | $6,874 | 5.71 | -$663 | 0.74 |
| 4 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP0.0_SL2500_TPcap800 | 25 | 80.0% | $6,874 | 5.71 | -$663 | 0.74 |
| 5 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP-0.5_SL2500_TPcap800 | 25 | 80.0% | $6,519 | 4.21 | -$1,399 | 0.62 |
| 6 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP-0.5_SL1200_TPcap800 | 25 | 80.0% | $6,519 | 4.21 | -$1,399 | 0.62 |
| 7 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP-0.5_SL1800_TPcap800 | 25 | 80.0% | $6,519 | 4.21 | -$1,399 | 0.62 |
| 8 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP-0.5_SL800_TPcap800 | 25 | 80.0% | $6,454 | 4.08 | -$1,464 | 0.60 |
| 9 | b2640_zp20_cp96_adf128_zE3.5_co50_zTP-1.0_SL800_TPcap2500 | 25 | 68.0% | $13,180 | 5.29 | -$2,190 | 0.57 |
| 10 | b2640_zp20_cp96_adf64_zE3.5_co50_zTP-1.0_SL1800_TPcap800 | 25 | 76.0% | $7,054 | 3.43 | -$1,718 | 0.56 |


### Comparison vs previous

| Metric | grid_search_B6_1min_dollar_zp_long_1tick | Current | Delta |
| --- | --- | --- | --- |
| Total configs | 86,400 | 41,472 | -44,928 |
| Profitable | 1342 (1.6%) | 5764 (13.9%) | -- |
| Best PnL | 53,642 | 25,164 | -28,478 |
| Best Sharpe | 0 | 1 | +1 |
| Avg PnL | -68,669 | -44,216 | +24,453 |
| Median PnL | -58,836 | -24,196 | +34,640 |


### Key Findings

- 5764/41472 configs profitable (13.9%)
- Best PnL: $25,164 -- b2640_zp30_cp24_adf26_zE3.5_co40_zTP-1.0_SL1200_TPcap2500
- zscore_entry=3.5 domine (86% des configs rentables)
- zscore_period=24 le plus frequent dans les rentables
- Trades moyen: 540 | median: 384


## [2026-02-06] Phase B Batch 1 -- Grid Search (50,112 configs)

### B1 -- 5min Z-Score pur, 2 ticks (34,560 configs) -- 18 min
- Rentables (trades>=50): 2,799/34,560 (8.1%), trades>=80: 1,794
- Top config: b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0, $49,572 PnL, 109 trades, PF 2.55, $455/trade
- **GO** pour B2/B3 (1,794 >> seuil 100)
- Decouvertes: adf=26 domine (36/50 top), beta=2640 optimal, zTP negatif confirme, cp=24 domine

### B5 -- 1min Z-Score pur, 1 tick (5,832 configs) -- 15 min
- Rentables (trades>=50): 494/5,832 (8.5%), trades>=80: 347
- Top config: b1980_zp15_cp30_adf96_zE3.0_co50_zTP-1.0, $20,896 PnL, 218 trades, PF 1.65, $96/trade
- Conclusion: zscore pur en 1min = viable mais nettement inferieur au 5min
- Decouvertes: co=50 domine (47/50 top), b1980 optimal, zTP=-1.0 domine

### B4 -- 1min Dollar, 1 tick (9,720 configs) -- 102 min
- Rentables (trades>=50): 2,222/9,720 (22.9%), trades>=80: 1,945
- Top config: b2640_zp20_cp48_adf96_zE2.5_co40_TP1000_SL1200, $111,583 PnL, 1655 trades, PF 1.15, $67/trade
- **GO** pour B6 (22.9% > seuil 15%)
- Decouvertes: zE=2.5 exclusif (50/50 top), TP=1000/SL=1200 dominent, PnL/trade faible malgre PnL total eleve
- Configs qualite (PnL/MaxDD): b1980_zp20_cp48_adf96_zE3.5_co50_TP500_SL800, PnL/MaxDD=12.33

### Rapport detaille: output/PHASE_B_BATCH1_RESULTS.md

---

## [2026-02-05] Fix Sharpe Ratio : harmonisation optimizer.py / metrics.py

**Bug**: `optimizer.py` et `metrics.py` utilisaient deux formules de Sharpe differentes.
- `optimizer.py` : `(mean/std) * sqrt(252)` -- annualisation fixe (suppose 1 trade/jour)
- `metrics.py` : `mean/std` par trade, puis `* sqrt(trades_per_year)` pour annualiser

Avec ~68 trades/an : `sqrt(252)=15.9` vs `sqrt(68)=8.2` -> **ratio ~1.94x** sur le Sharpe annualise.

**Fix**: `optimizer.py` utilise maintenant `mean/std` (Sharpe par trade, non annualise), coherent avec `metrics.py`. L'annualisation reste disponible dans `metrics.py:compute_advanced_metrics()` via `sharpe_annualise`.

**Impact**: Les valeurs de Sharpe dans les grid search futurs seront ~15.9x plus petites (division par sqrt(252)). Les anciens CSV ne sont pas modifies. Test de coherence ajoute (`test_sharpe_coherence_optimizer_metrics`).

---

## [2026-02-05] TOP 5 Configurations par Timeframe (Analyse Quantitative)

**Analyse**: Revue complete de tous les backtests archives et walk-forward pour identifier les configs optimales.

### TOP 5 Configurations 1-MIN (Dollar exits, 1 tick slippage, 3 ans)

| Rang | Config | PnL | Trades | WR% | PF | Sharpe | Justification |
|------|--------|-----|--------|-----|-----|--------|---------------|
| **1** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL1200_co50` | **$16,585** | 93 | **82.8%** | 2.10 | **0.324** | **BEST OVERALL** - Meilleur Sharpe, WR exceptionnel |
| **2** | `b1320_zp20_cp30_adf128_zE3.5_TP1000_SL1200_co50` | $15,890 | 93 | 63.4% | 1.44 | 0.175 | TP large = plus de variance, meme trades |
| **3** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL1400_co50` | $14,585 | 93 | 82.8% | 1.86 | 0.258 | SL large = moins de stops prematures |
| **4** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL800_co50` | $12,600 | 93 | 76.3% | 1.76 | 0.264 | SL serre = drawdown mieux controle |
| **5** | `b1320_zp20_cp30_adf64_zE3.5_TP1000_SL1200_co50` | $14,829 | 62 | 64.5% | 1.69 | 0.250 | ADF64 = plus de trades, filtre moins strict |

**Patterns dominants 1-MIN**:
- `beta_lookback=1320` (1 jour) optimal pour reactivite
- `zscore_entry=3.5` seul seuil viable sur 3 ans
- `adf_hurst_period=128` filtre les trades de haute qualite
- `TP=$500` avec `WR=82.8%` > `TP=$1000` avec `WR=63.4%`
- Dollar exits > Z-Score exits pour ce timeframe

**Config active dans YAML**: #1 (`b1320_zp20_cp30_adf128_zE3.5_TP500_SL1200_co50`)

---

### TOP 5 Configurations 5-MIN (Pure Z-Score, 2 ticks slippage, 3 ans)

| Rang | Config | PnL | Trades | WR% | PF | Sharpe | WF Robustesse | Justification |
|------|--------|-----|--------|-----|-----|--------|---------------|---------------|
| **1** | `b3960_zp24_cp12_adf26_zE3.5_zTP-1.0_co50` | $24,694 WF | 153 | ~50% | ~2.0 | - | **53% fenetres+** | **BEST WF** - Beta long = plus stable |
| **2** | `b2640_zp20_cp30_adf26_zE3.5_zTP-1.0_zSL4.0_co40` | **$45,224** | 100 | 53% | 2.41 | 3.02 | 32% fenetres+ | **MAX PNL** - Overshoot capture le momentum |
| **3** | `b2640_zp20_cp30_adf128_zE3.5_zTP1.0_co50` | $7,818 | 23 | **60.9%** | 4.09 | **0.361** | - | **MAX SHARPE** - ADF strict = haute qualite |
| **4** | `b1320_zp20_cp30_adf64_zE3.5_zTP1.0_co50` | $11,420 | 30 | 53.3% | 3.28 | 0.205 | - | Meilleur compromis PnL/Sharpe/Trades |
| **5** | `b3960_zp24_cp60_adf26_zE3.5_zTP-1.0_co50` | $24,694 WF | 153 | ~50% | ~2.0 | - | **53% fenetres+** | 2eme config WF, cp60 = filtre correl strict |

**Patterns dominants 5-MIN**:
- `zTP=-1.0` (overshoot) double le PnL vs `zTP=1.0` (+100%)
- `beta_lookback=3960` (15j) plus robuste en walk-forward que `b2640` (10j)
- `zscore_entry=3.5` seul seuil viable (98% des configs rentables)
- `adf=26` pour max PnL, `adf=128` pour max Sharpe
- Pure Z-Score exits > Dollar exits pour ce timeframe

**Walk-Forward Comparison**:
- b2640 (10j): $20,553 PnL, **32% fenetres positives** (instable)
- b3960 (15j): $24,694 PnL, **53% fenetres positives** (recommande)

---

### Recommandations Finales

| Objectif | Config | Timeframe | Commentaire |
|----------|--------|-----------|-------------|
| **Paper Trading (securite)** | `b1320_zp20_cp30_adf128_zE3.5_TP500_SL1200_co50` | **1-MIN** | WR 82.8%, Sharpe 0.324, 1 tick slippage |
| **Max PnL (plus risque)** | `b2640_zp20_cp30_adf26_zE3.5_zTP-1.0_co40` | 5-MIN | $45,224 mais 32% WF positives |
| **Max Robustesse WF** | `b3960_zp24_cp12_adf26_zE3.5_zTP-1.0_co50` | 5-MIN | 53% WF positives, beta long |
| **Max Sharpe** | `b2640_zp20_cp30_adf128_zE3.5_zTP1.0_co50` | 5-MIN | Sharpe 0.361, 23 trades haute qualite |

**ATTENTION**: Toutes les configs 5-MIN sont **regime-dependantes** (2023-24 perdant, 2025-26 profitable). Un filtre de regime est recommande avant production.

---

## [2026-02-03] Walk-Forward Beta Long (34 windows, 63d train / 21d test)

**Script**: `run_walk_forward_beta_long.py` | **Configs testees**: Top 5 beta long (b3960)

### Objectif

Valider la robustesse des configs avec beta long (15 jours = 3960 barres 5-min) sur 34 fenetres walk-forward. Comparaison avec le walk-forward b2640 (10 jours).

### Resultats globaux

| Metrique | Beta Long (b3960) | Beta Court (b2640) | Delta |
|----------|-------------------|-------------------|-------|
| PnL total TEST | **+$24,694** | +$20,553 | **+$4,141 (+20%)** |
| Trades TEST | 153 | 93 | +60 |
| Fenetres positives | **18/34 (53%)** | 11/34 (32%) | **+21%** |
| Fenetres negatives | 16/34 (47%) | 22/34 (65%) | -18% |

### Analyse par periode

| Periode | Fenetres | PnL TEST | Trades | Win% | Verdict |
|---------|----------|----------|--------|------|---------|
| 2023 | 1-9 | -$8,885 | 44 | 3/9 (33%) | Perdant |
| 2024 | 10-21 | -$1,156 | 45 | 7/12 (58%) | Equilibre |
| 2025-2026 | 22-34 | +$34,735 | 64 | 8/13 (62%) | **Tres profitable** |

### Top 5 fenetres

| # | Window | Periode TEST | Config | Trades | PnL | WR% |
|---|--------|-------------|--------|--------|-----|-----|
| 1 | 33 | Dec 12 - Jan 05 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-1.0 | 4 | +$14,014 | 100% |
| 2 | 34 | Jan 06 - Jan 29 | b3960_zp24_cp24_adf26_zE3.5_co40_zTP-1.0 | 13 | +$11,797 | 77% |
| 3 | 32 | Nov 18 - Dec 11 | b3960_zp24_cp60_adf26_zE3.5_co50_zTP-1.0 | 6 | +$5,664 | 83% |
| 4 | 31 | Oct 24 - Nov 17 | b3960_zp24_cp60_adf26_zE3.5_co50_zTP-1.0 | 5 | +$4,905 | 100% |
| 5 | 24 | Mar 14 - Apr 07 | b3960_zp24_cp12_adf26_zE3.5_co40_zTP-1.0 | 3 | +$4,581 | 100% |

### Configs selectionnees (frequence)

| Config | Fenetres | % |
|--------|----------|---|
| b3960_zp24_cp12_adf26_zE3.5_co50_zTP-1.0 | 11 | 32% |
| b3960_zp24_cp60_adf26_zE3.5_co50_zTP-1.0 | 10 | 29% |
| b3960_zp24_cp12_adf26_zE3.5_co40_zTP-1.0 | 8 | 24% |
| b3960_zp24_cp24_adf26_zE3.5_co40_zTP-1.0 | 3 | 9% |
| Autres | 2 | 6% |

### Conclusion

**Beta long (b3960) surpasse beta court (b2640)** en walk-forward:
- +20% de PnL total
- +21% de fenetres positives
- Meilleure performance sur 2024 (equilibre vs perte)
- zp=24 (2h en 5-min) domine vs zp=20

**Recommandation** : Utiliser b3960 (15 jours) plutot que b2640 (10 jours) pour plus de robustesse.

---

## [2026-02-03] Grid Search Beta Long (4,050 configs)

**Script**: `run_grid_search_beta_long.py` | **Resultats**: `output/grid_search_beta_long.csv`

### Objectif

Tester des lookbacks beta plus longs (15, 20, 30 jours) avec zTP=0 et zTP=-1.0 pour verifier si des beta plus longs ameliorent la robustesse.

### Grille testee

| Parametre | Valeurs | Description |
|-----------|---------|-------------|
| beta_lookback | 3960, 5280, 7920 | 15j, 20j, 30j (264 barres/jour) |
| zscore_period | 12, 24, 36, 48, 60 | 1h-5h |
| correlation_period | 12, 24, 36, 48, 60 | 1h-5h |
| adf_hurst_period | 26, 64, 128 | |
| entry_zscore | 2.5, 3.0, 3.5 | |
| cointegration_min | 40, 50, 60 | |
| zscore_tp | 0.0, -1.0 | Sortie a 0 ou overshoot |

**Total** : 225 groupes x 18 variantes = 4,050 configs

### Resultats par beta

| Beta | Jours | Configs rentables | % | PnL Max | Observation |
|------|-------|-------------------|---|---------|-------------|
| 3960 | 15j | 147 | 10.9% | $10,733 | **Meilleur ratio** |
| 5280 | 20j | 89 | 6.6% | $8,916 | Degrade |
| 7920 | 30j | 32 | 2.4% | $4,209 | Trop long |

### Resultats par zTP

| zTP | Configs rentables | % | PnL Max |
|-----|-------------------|---|---------|
| -1.0 | 198 | 14.6% | $10,733 |
| 0.0 | 70 | 5.2% | $2,848 |

### Conclusion

**Beta court reste optimal pour le PnL brut**, mais beta long (3960) offre une meilleure robustesse en walk-forward (voir section precedente). Le trade-off est:
- b2640 (10j) : $45,224 backtest, $20,553 walk-forward (32% positives)
- b3960 (15j) : $10,733 backtest, $24,694 walk-forward (53% positives)

---

## [2026-02-03] Walk-Forward 5-min zTP=-1.0 (34 windows, 63d train / 21d test)

**Script**: `run_walk_forward_5min_ztp.py` | **Resultats**: `output/walk_forward_5min_ztp_results.csv`

### Objectif

Valider la meilleure config zTP=-1.0 (b2640_zp20_cp30_adf26_zE3.5_co40) sur 34 fenetres walk-forward.

### Resultats globaux

| Metrique | Valeur |
|----------|--------|
| PnL total TEST | +$20,553 |
| Trades TEST | 93 |
| Fenetres positives | 11/34 (32%) |
| Fenetres negatives | 22/34 (65%) |
| Fenetres inactives | 1/34 (3%) |

### Analyse par periode

| Periode | Fenetres | PnL TEST | Verdict |
|---------|----------|----------|---------|
| 2023 | 1-9 | -$9,435 | **Perdant** |
| 2024 | 10-21 | -$9,859 | **Perdant** |
| 2025-2026 | 22-34 | +$39,847 | **Tres profitable** |

### Concentration du PnL

La fenetre #34 (dec 2025 - jan 2026) genere **$32,366**, soit **157% du PnL total**.

### Configs selectionnees (frequence)

| zTP | Fenetres | % |
|-----|----------|---|
| zTP=-1.0 | 13 | 38% |
| zTP=0.0 | 13 | 38% |
| zTP=1.0 | 8 | 24% |

### Conclusion

**Strategie regime-dependante** : profitable uniquement en 2025-2026, perdante en 2023-2024. La performance est concentree sur quelques fenetres exceptionnelles. **Filtre de regime requis** avant production.

---

## [2026-02-03] Grid Search zTP Etendu (45,360 configs)

**Script**: `run_grid_search_ztp_extended.py` | **Resultats**: `output/grid_search_5min_ztp_extended.csv`

### Objectif

Tester des valeurs de zTP plus agressives (-1.0 "overshoot") pour capturer le momentum du retour a la moyenne.

### Grille testee

| Parametre | Valeurs |
|-----------|---------|
| zscore_tp | -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0 |
| Autres | Identiques au grid search initial |

**Total** : 6,480 groupes x 7 zTP = 45,360 configs

### Resultats par zTP

| zTP | Configs rentables | % | PnL Max | Gain vs zTP=1.0 |
|-----|-------------------|---|---------|-----------------|
| **-1.0** | 909 | **14.0%** | **$45,224** | **+100%** |
| -0.5 | 823 | 12.7% | $41,954 | +86% |
| 0.0 | 620 | 9.6% | $36,909 | +63% |
| 0.5 | 446 | 6.9% | $23,564 | +4% |
| 1.0 | 220 | 3.4% | $22,604 | (baseline) |
| 1.5 | 231 | 3.6% | $13,304 | -41% |
| 2.0 | 161 | 2.5% | $8,929 | -60% |

### Top 5 configs zTP=-1.0

| # | Config | Trades | PnL Net | WR | PF | Sharpe |
|---|--------|--------|---------|-----|-----|--------|
| 1 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL4.0 | 100 | $45,224 | 53% | 2.41 | 3.02 |
| 2 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL5.0 | 100 | $45,224 | 53% | 2.41 | 3.02 |
| 3 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0_zSL3.5 | 100 | $44,644 | 52% | 2.38 | 2.99 |
| 4 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP-0.5_zSL4.0 | 100 | $41,954 | 52% | 2.50 | 2.99 |
| 5 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP-0.5_zSL5.0 | 100 | $41,954 | 52% | 2.50 | 2.99 |

### Interpretation

**zTP=-1.0 (overshoot)** signifie attendre que le Z-Score depasse 0 de l'autre cote avant de sortir. Cela capture le momentum du retour a la moyenne et **double le PnL** par rapport a la sortie classique (zTP=1.0).

### Archive

Les top 5 PnL et top 5 Sharpe sont archives dans `output/archive/5min_ztp_extended/` avec metrics_report.txt complet (10 sections).

---

## [2026-02-03] Archivage Top 20 Configs 5-MIN (PnL + Sharpe)

**Archives**: 20 configs | **Localisation**: `output/archive/5min/` et `output/archive/_ranking/`

### Objectif

Archiver les meilleures configs 5-min identifiees par le grid search (155,520 configs) avec rapports complets, courbes d'equity et classement par categorie.

### Structure des archives

```
output/archive/
    CLASSEMENT.txt           <- Resume complet
    index.csv                <- 36 configs (16 x 1min + 20 x 5min)
    _ranking/                <- Classements par categorie
        5min_top_pnl/        <- Top 10 par PnL
        5min_top_sharpe/     <- Top 10 par Sharpe
        1min_top_pnl/        <- Top 10 par PnL
        1min_top_sharpe/     <- Top 10 par Sharpe
    5min/                    <- 20 archives detaillees
    1min/                    <- 16 archives detaillees
```

### Top 10 par PnL Net (5-min, deduplique)

| # | Config | Trades | WR% | PnL Net | MaxDD | Sharpe | Calmar |
|---|--------|--------|-----|---------|-------|--------|--------|
| 1 | b2640_zp20_cp30_adf26_zTP1.0_co40 | 100 | 41.0% | $22,604 | -$12,985 | 0.146 | 1.74 |
| 2 | b2640_zp20_cp30_adf26_zTP1.0_co40 (zSL4) | 100 | 42.0% | $21,314 | -$14,372 | 0.135 | 1.48 |
| 3 | b2640_zp20_cp15_adf26_zTP1.0_co50 | 81 | 43.2% | $13,969 | -$8,396 | 0.157 | 1.66 |
| 4 | b2640_zp20_cp30_adf26_zTP1.5_co40 | 100 | 39.0% | $13,304 | -$10,416 | 0.102 | 1.28 |
| 5 | b2640_zp20_cp15_adf26_zTP1.0_co50 (zSL3.5) | 81 | 43.2% | $13,229 | -$9,136 | 0.148 | 1.45 |
| 6 | b2640_zp20_cp50_adf26_zTP1.0_co40 | 104 | 42.3% | $12,312 | -$10,770 | 0.084 | 1.14 |
| 7 | b5280_zp20_cp30_adf128_zTP1.0_co40 | 68 | 47.1% | $11,446 | -$10,402 | 0.133 | 1.10 |
| 8 | b1320_zp20_cp30_adf64_zTP1.0_co50 | 30 | 53.3% | $11,420 | -$2,212 | 0.205 | 5.16 |
| 9 | b2640_zp20_cp15_adf128_zTP1.0_co50 | 36 | 50.0% | $11,299 | -$4,917 | 0.219 | 2.30 |
| 10 | b2640_zp20_cp30_adf128_zTP1.0_co50 | 23 | 60.9% | $7,818 | -$1,859 | 0.361 | 4.21 |

### Top 10 par Sharpe (5-min, min 10 trades)

| # | Config | Trades | WR% | PnL Net | MaxDD | Sharpe | Calmar |
|---|--------|--------|-----|---------|-------|--------|--------|
| 1 | b2640_zp20_cp30_adf128_zTP1.0_co50 | 23 | 60.9% | $7,818 | -$1,859 | **0.361** | 4.21 |
| 2 | b2640_zp20_cp80_adf128_zTP1.0_co50 | 24 | 50.0% | $5,549 | -$1,113 | 0.289 | 4.99 |
| 3 | b2640_zp20_cp30_adf128_zTP1.5_co50 | 23 | 56.5% | $2,758 | -$850 | 0.278 | 3.24 |
| 4 | b2640_zp20_cp50_adf128_zTP1.0_co50 | 21 | 42.9% | $4,808 | -$2,633 | 0.260 | 1.83 |
| 5 | b5280_zp20_cp30_adf128_zTP1.5_co50 | 27 | 44.4% | $4,134 | -$1,961 | 0.258 | 2.11 |
| 6 | b2640_zp20_cp30_adf64_zTP1.0_co50 | 26 | 53.8% | $4,768 | -$2,063 | 0.244 | 2.31 |
| 7 | b2640_zp20_cp30_adf128_zTP2.0_co50 | 23 | 56.5% | $3,468 | -$1,224 | 0.237 | 2.83 |
| 8 | b2640_zp20_cp50_adf128_zTP1.5_co50 | 21 | 42.9% | $2,518 | -$1,408 | 0.231 | 1.79 |
| 9 | b2640_zp20_cp15_adf128_zTP1.0_co50 | 36 | 50.0% | $11,299 | -$4,917 | 0.219 | 2.30 |
| 10 | b5280_zp20_cp30_adf64_zTP1.5_co50 | 24 | 45.8% | $2,425 | -$1,896 | 0.208 | 1.28 |

### Patterns dominants

| Parametre | Valeur dominante | Frequence | Observation |
|-----------|------------------|-----------|-------------|
| beta_lookback | 2640 | 80% | 2 jours de barres 5-min |
| zscore_period | 20 | 100% | 1h40 de lookback Z-Score |
| zscore_entry | 3.5 | 100% | Seul seuil viable |
| mode | pure_zscore | 100% | SL -$2000 degrade la perf |
| zscore_tp | 1.0 | 65% | Retour a 1 sigma optimal |
| adf_hurst_period | 128 (Sharpe) / 26 (PnL) | - | ADF strict = moins trades mais plus stables |

### Recommandations

| Objectif | Config recommandee | PnL | Sharpe | Trades |
|----------|-------------------|-----|--------|--------|
| Max PnL | b2640_zp20_cp30_adf26_zTP1.0_co40 | $22,604 | 0.146 | 100 |
| Max Sharpe | b2640_zp20_cp30_adf128_zTP1.0_co50 | $7,818 | 0.361 | 23 |
| Compromis | b1320_zp20_cp30_adf64_zTP1.0_co50 | $11,420 | 0.205 | 30 |

### Prochaines etapes

1. **Walk-forward validation** sur top 5 configs 5-min (34 fenetres)
2. **Comparaison par annee** : 2023 vs 2024 vs 2025
3. **Test live paper trading** sur la config recommandee

---

## [2026-02-03] Grid Search 5-MIN -- Phase 4: Pure Z-Score exits, 2 ticks slippage

**Configs**: 155,520 | **Profitable**: 938 (0.6%) | **Duration**: 10.3h
Results: `output/grid_search_5min_phase1.csv`

### Objectif

Tester le timeframe 5-min avec des exits purement Z-Score (pas de TP/SL dollar), pour verifier si la mean-reversion fonctionne mieux sur un timeframe plus lent.

### Grille testee

**Indicateurs (1,080 groupes)**:
- beta_lookback: 132, 264, 396, 528, 792, 1320, 2640, 3690, 5280
- zscore_period: 10, 15, 20, 30, 50, 60, 80, 100
- correlation_period: 15, 30, 50, 60, 80
- adf_hurst_period: 26, 64, 128

**Entry/Exit (144 variantes par groupe)**:
- zscore_entry: 2.0, 2.5, 3.0, 3.5
- cointegration_min: 40, 50
- zscore_tp: 1.0, 1.5, 2.0
- zscore_sl: 3.5, 4.0, 5.0
- mode: pure_zscore (no dollar exits) | safety (SL -$2000)

**Fixes**: zscore_tp_enabled=True, slippage=2 ticks

### Top 10 by PnL Net

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.0_zSL3.5_pure | 100 | 41.0% | $22,604 | 2.03 | -$12,985 | 2.32 |
| 2 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.0_zSL4.0_pure | 100 | 42.0% | $21,314 | 1.91 | -$14,372 | 2.14 |
| 3 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.0_zSL5.0_pure | 100 | 42.0% | $21,314 | 1.91 | -$14,372 | 2.14 |
| 4 | b2640_zp20_cp15_adf26_zE3.5_co50_zTP1.0_zSL4.0_pure | 81 | 43.2% | $13,969 | 1.83 | -$8,396 | 2.48 |
| 5 | b2640_zp20_cp15_adf26_zE3.5_co50_zTP1.0_zSL5.0_pure | 81 | 43.2% | $13,969 | 1.83 | -$8,396 | 2.48 |
| 6 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.5_zSL4.0_pure | 100 | 39.0% | $13,304 | 1.71 | -$10,416 | 1.63 |
| 7 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.5_zSL5.0_pure | 100 | 39.0% | $13,304 | 1.71 | -$10,416 | 1.63 |
| 8 | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.5_zSL3.5_pure | 100 | 39.0% | $13,294 | 1.70 | -$10,426 | 1.64 |
| 9 | b2640_zp20_cp15_adf26_zE3.5_co50_zTP1.0_zSL3.5_pure | 81 | 43.2% | $13,229 | 1.75 | -$9,136 | 2.34 |
| 10 | b2640_zp20_cp50_adf26_zE3.5_co40_zTP1.0_zSL4.0_pure | 104 | 42.3% | $12,312 | 1.51 | -$10,770 | 1.34 |

### Top 10 by Sharpe (min 10 trades)

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.0_zSL3.5_pure | 23 | 60.9% | $7,818 | 4.09 | -$1,859 | 5.72 |
| 2 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.0_zSL4.0_pure | 23 | 60.9% | $7,818 | 4.09 | -$1,859 | 5.72 |
| 3 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.0_zSL5.0_pure | 23 | 60.9% | $7,818 | 4.09 | -$1,859 | 5.72 |
| 4 | b2640_zp20_cp80_adf128_zE3.5_co50_zTP1.0_zSL3.5_pure | 24 | 50.0% | $5,549 | 3.17 | -$1,113 | 4.58 |
| 5 | b2640_zp20_cp80_adf128_zE3.5_co50_zTP1.0_zSL4.0_pure | 24 | 50.0% | $5,549 | 3.17 | -$1,113 | 4.58 |
| 6 | b2640_zp20_cp80_adf128_zE3.5_co50_zTP1.0_zSL5.0_pure | 24 | 50.0% | $5,549 | 3.17 | -$1,113 | 4.58 |
| 7 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.5_zSL3.5_pure | 23 | 56.5% | $2,758 | 2.70 | -$850 | 4.41 |
| 8 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.5_zSL4.0_pure | 23 | 56.5% | $2,758 | 2.70 | -$850 | 4.41 |
| 9 | b2640_zp20_cp30_adf128_zE3.5_co50_zTP1.5_zSL5.0_pure | 23 | 56.5% | $2,758 | 2.70 | -$850 | 4.41 |
| 10 | b2640_zp20_cp50_adf128_zE3.5_co50_zTP1.0_zSL3.5_pure | 21 | 42.9% | $4,808 | 2.54 | -$2,633 | 4.12 |

### Analyse par parametre

| Parametre | Meilleure valeur | Configs rentables | Observation |
| --- | --- | --- | --- |
| beta_lookback | 2640 | 268 (1.6%) | Lookback 2 jours 5-min optimal |
| zscore_period | 20 | 295 (1.5%) | zp=10 et zp=15 ont 0-3% rentables |
| zscore_entry | 3.5 | 922 (2.4%) | zE=2.0/2.5/3.0 ont 0% rentables |
| zscore_tp | 1.0 | 327 (0.6%) | TP agressif (retour a 1 sigma) |
| cointegration_min | 50 | 663 (0.9%) | Filtre plus strict = meilleur |
| mode | pure_zscore | 621 (0.8%) | Safety (-$2000 SL) degrade: 317 (0.4%) |

### Comparaison 5-min vs 1-min

| Metrique | 5-min (pure Z-Score) | 1-min (dollar exits) | Delta |
| --- | --- | --- | --- |
| Meilleure config | b2640_zp20_cp30_adf26_zE3.5_co40_zTP1.0_zSL3.5_pure | beta1320_zE3.5_TP1000/SL1200_tpzOFF | - |
| PnL Net | $22,604 | $14,829 | +$7,775 (+52%) |
| Trades | 100 | 62 | +38 |
| Win Rate | 41.0% | 64.5% | -23.5% |
| Sharpe | 2.32 | 0.95 | +1.37 |
| Max Drawdown | -$12,985 | -$6,338 | -$6,647 |

### Key Findings

1. **5-min Z-Score surpasse 1-min dollar** : +$7,775 (+52%) mais avec plus de drawdown
2. **zE=3.5 obligatoire** : 922/938 configs rentables utilisent zE=3.5 (98%)
3. **Pure Z-Score > Safety** : le filet SL -$2000 coupe des trades gagnants
4. **beta=2640 domine** : equivalent a 2 jours de barres 5-min
5. **zp=20 optimal** : 1h40 de lookback pour le Z-Score
6. **zTP=1.0 (retour a 1 sigma)** : sortie agressive fonctionne mieux
7. **adf=26 pour PnL, adf=128 pour Sharpe** : ADF court = plus de trades = plus de PnL
8. **Win rate faible (41%)** : compense par gros gains moyens (PF=2.03)

### Prochaines etapes

1. **Walk-forward sur top 5 configs 5-min** : valider robustesse hors-echantillon
2. **Comparer regimes** : verifier si 5-min performe mieux sur 2023-2024 (mauvais pour 1-min)
3. **Tester beta=1320 en 5-min** : le beta 1-min optimal pourrait aussi fonctionner en 5-min

---

## [2026-02-02] Grid Search -- Phase 3: 3-year comprehensive, 2 ticks slippage

**Configs**: 32,400 | **Profitable**: 115 (0.4%)
Results: `output/grid_search_3y_phase1.csv`

### Top 10 by PnL Net

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |
| 6 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL800 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |
| 7 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL400 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 8 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL600 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 9 | b3960_zp20_cp60_adf256_zE3.5_co60_TP400_SL800 | 9 | 55.6% | $373 | 1.96 | -$271 | 4.25 |
| 10 | b660_zp20_cp50_adf128_zE3.5_co60_TP400_SL800 | 17 | 41.2% | $358 | 1.39 | -$753 | 2.22 |

### Top 10 by Sharpe (min 10 trades)

| # | Config | Trades | WR% | PnL | PF | MaxDD | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 2 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 5 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL400 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 6 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL600 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 7 | b3960_zp20_cp60_adf64_zE3.5_co60_TP300_SL800 | 10 | 50.0% | $220 | 1.44 | -$296 | 2.60 |
| 8 | b660_zp20_cp50_adf128_zE3.5_co60_TP400_SL800 | 17 | 41.2% | $358 | 1.39 | -$753 | 2.22 |
| 9 | b660_zp20_cp20_adf128_zE3.5_co60_TP400_SL800 | 19 | 47.4% | $307 | 1.32 | -$947 | 1.86 |
| 10 | b3960_zp15_cp60_adf64_zE3.5_co50_TP400_SL800 | 11 | 36.4% | $190 | 1.32 | -$552 | 1.78 |

### Key Findings

- 115/32400 configs profitable (0.4%)
- Best PnL: $586 -- b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800
- zscore_entry=3.5 domine (97% des configs rentables)
- zscore_period=15 le plus frequent dans les rentables
- TP=$400 et SL=-$800 dominent les rentables
- Trades moyen: 3155 | median: 1176

## Grid Search Results (32,400 configs, 3 years, 2 ticks slippage)

Tested: 300 indicator groups x 108 entry/exit variants = 32,400 configs total.
- beta_lookback: 660, 1320, 1980, 2640, 3960
- zscore_period: 15, 20, 30, 50, 60
- correlation_period: 20, 30, 50
- adf_hurst_period: 64, 128, 256, 512
- zscore_entry: -2.5/+2.5, -3.0/+3.0, -3.5/+3.5
- cointegration_score_min: 40, 50, 60
- pnl_take_profit: 200, 300, 400
- pnl_stop_loss: -400, -600, -800, -1000

Run with 8 parallel workers (`multiprocessing.Pool`).
Results saved in `output/grid_search_3y_phase1.csv`.

### Key finding: strategy NOT viable with 2 ticks slippage

- **Only 115/32,400 configs profitable (0.4%)**
- **Best PnL: +$586 over 3 years** (nearly breakeven)
- Average cost per trade: ~$160-200 (2 ticks slippage doubles costs vs 1 tick)
- TP_ZSCORE exits lose money even with PnL floor >= $0

### Top 5 by PnL Net (3 years, 2 ticks)

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | 18 | 50.0% | $586 | 1.49 | -$880 | 2.86 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | 18 | 61.1% | $531 | 1.53 | -$734 | 3.28 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | 16 | 43.8% | $446 | 1.53 | -$823 | 2.91 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | 29 | 44.8% | $437 | 1.26 | -$721 | 1.59 |

### Top 5 with 1 tick slippage (for comparison)

| # | Config | PnL 2tick | PnL 1tick | Delta |
|---|--------|-----------|-----------|-------|
| 1 | b3960_zp20_cp30_adf64_zE3.5_co60_TP400_SL800 | +$586 | +$1,946 | +$1,360 |
| 2 | b3960_zp20_cp30_adf64_zE3.5_co60_TP300_SL800 | +$531 | +$1,891 | +$1,360 |
| 3 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL600 | +$446 | +$1,746 | +$1,300 |
| 4 | b660_zp20_cp60_adf128_zE3.5_co60_TP400_SL800 | +$446 | +$1,746 | +$1,300 |
| 5 | b3960_zp15_cp20_adf256_zE3.5_co40_TP400_SL600 | +$437 | +$2,547 | +$2,110 |

## Grid Search Results (864 configs, 8 months, 1 tick slippage)

Tested: beta_lookback (1320/1980/2640/3960) x zscore_period (20/30) x correlation_period (30/60) x cointegration_score_min (40/50/60) x zscore_entry (-2.5/+2.5, -3.0/+3.0) x TP (200/300/400) x SL (-400/-600/-800)

### Top 5 by PnL Net

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | beta1320_zp20_cp30_co40_TP400_SL600 | 1,423 | 58.6% | $80,833 | 1.87 | -$20,632 | 3.79 |
| 2 | beta1320_zp20_cp30_co40_TP400_SL400 | 1,423 | 58.1% | $80,433 | 1.88 | -$20,962 | 3.93 |
| 3 | beta1320_zp20_cp30_co40_TP400_SL800 | 1,424 | 58.8% | $79,043 | 1.82 | -$20,417 | 3.56 |
| 4 | beta1980_zp20_cp30_co40_TP400_SL800 | 1,430 | 57.1% | $76,018 | 1.82 | -$23,205 | 3.56 |
| 5 | beta3960_zp30_cp60_co40_TP400_SL800 | 1,525 | 61.0% | $76,002 | 1.63 | -$25,300 | 2.83 |

### Top 5 by Sharpe (risk-adjusted)

| # | Config | Trades | WR% | PnL Net | PF | MaxDD | Sharpe |
|---|--------|--------|-----|---------|-----|-------|--------|
| 1 | beta2640_zp20_cp30_co60_zE3_TP200_SL400 | 31 | 90.3% | $2,549 | 6.61 | -$332 | 14.72 |
| 2 | beta2640_zp20_cp30_co50_zE3_TP200_SL400 | 146 | 84.9% | $10,459 | 5.09 | -$574 | 11.65 |
| 3 | beta3960_zp20_cp60_co60_zE3_TP200_SL400 | 39 | 79.5% | $2,408 | 4.63 | -$277 | 11.65 |
| 4 | beta2640_zp20_cp30_co50_zE3_TP200_SL600 | 146 | 84.9% | $10,259 | 4.72 | -$774 | 10.37 |
| 5 | beta2640_zp20_cp60_co60_zE3_TP200_SL400 | 33 | 84.8% | $2,293 | 4.58 | -$410 | 9.50 |

### Key conclusions (8 months)
- **PnL vs Sharpe trade-off**: zero configs in common between the two rankings
- High PnL requires loose filters (co=40, zE=-2.5) and TP=$400
- High Sharpe requires strict filters (co=50-60, zE=-3.0) and TP=$200
- SL value has minimal impact on top PnL configs (SL never hit on Sharpe configs)
- `beta1320` and `beta1980` dominate PnL; `beta2640` dominates Sharpe

## Previous Results (8-month data, 1 tick slippage)

Config: beta=1980, zp=20, cp=30, adf=128, cm=0.60, co=40, TP=$300, SL=-$600

- Trades: 1,473 (844 LONG, 629 SHORT)
- PnL net: +$71,428 | Win rate: 62.3%
- Profit Factor: 1.95 | Max Drawdown: -$20,639
- Sharpe: 4.25
- Two market regimes: May-Sept 2025 (unfavorable, TP_ZSCORE losses) / Oct 2025-Jan 2026 (very favorable)

## Walk-Forward Test (6 windows, 12 configs, 8 months)

6 rolling windows (30-day train / 15-day test), 12 configs tested per window, best selected on train PnL.

### Results per window (out-of-sample)

| # | Test Period | Config Selected | Trades | PnL | WR% | PF | MaxDD |
|---|-------------|-----------------|--------|-----|-----|-----|-------|
| 1 | Jul 18 - Aug 04 | Sh5 (zE3, TP200) | 10 | -$313 | 30% | 0.50 | -$543 |
| 2 | Aug 17 - Sep 28 | Sh5 (zE3, TP200) | 10 | -$4 | 50% | 0.99 | -$423 |
| 3 | Oct 10 - Oct 27 | Sh5 (zE3, TP200) | 17 | +$2,004 | 94% | 112 | $0 |
| 4 | Nov 09 - Nov 25 | PnL3 (TP300, SL600) | 183 | +$2,270 | 58% | 1.22 | -$2,414 |
| 5 | Dec 08 - Dec 24 | PnL3 (TP300, SL600) | 153 | +$9,245 | 70% | 1.89 | -$1,822 |
| 6 | Jan 06 - Jan 22 | PnL6 (TP400, SL800) | 201 | +$31,371 | 83% | 3.40 | -$1,715 |

### Summary
- **Total out-of-sample PnL**: +$44,573 (vs $43,903 in-sample)
- **Retention**: 203% of daily PnL (test > train)
- **Positive windows**: 4/6
- **Verdict**: Strategy is ROBUST out-of-sample, but regime-dependent
- Results saved in `output/walk_forward_results.csv`

## Optimization History

### Phase 1 -- 48-day data (606+ configs, Dec 2025 - Jan 2026)
1. **Etape 1 (22 configs)**: beta_lookback (660-7920) x zscore_period (15/20/30)
2. **Etape 2 (101 configs)**: top 5 indicators x TP (200-600) x SL (400-1200)
3. **Etape 3 (481 configs)**: 6 bases x correlation_period x adf_period x corr_min x coint_min
4. **Hurst filter (12 configs)**: zero impact (redundant with Cointegration Score)

### Phase 2 -- 8-month data (864 configs, May 2025 - Jan 2026)
- Full grid search with optimized grouping (16 indicator groups x 54 entry/exit variants)
- Walk-forward validation: 6 windows, 12 configs each, no overfitting detected
- Log saved in `output/optimization_log.csv` (batch_id="grid_8mois")

### Phase 3 -- 3-year data (32,400 configs, Jan 2023 - Jan 2026, 2 ticks slippage)
- Comprehensive grid search: 300 indicator groups x 108 entry/exit variants
- Run with multiprocessing (8 workers)
- **Result: only 0.4% of configs profitable, best PnL = $586 over 3 years**
- Results saved in `output/grid_search_3y_phase1.csv`
- Script: `run_grid_search_3y.py`

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
- **Code factorization**: `common.py` centralizes state constants and shared functions (check_entry_conditions, check_zscore_exit, check_cooldown_reset, calculate_current_pnl, build_config_fingerprint). Removed ~430 lines of duplicated code.
- **Hurst bug fix**: Both backtest engines now pass `hurst=hursts[i]` to check_entry_conditions (was silently ignored before). No impact with default hurst_max=1.0.
- **8-month data upgrade**: Extended from 48 days (GCG26) to 8 months (GCJ26, May 2025 - Jan 2026). Contract rollover handled.
- **Optimized grid search**: `run_grid_search.py` groups 864 configs into 16 indicator combinations, calculates indicators once per group, then loops 54 entry/exit variants.
- **Walk-forward validation**: `run_walk_forward.py` implements 6-window rolling walk-forward (30-day train / 15-day test). Confirmed no overfitting.
- **PnL floor on TP_ZSCORE**: `exit.zscore_tp_min_pnl` parameter in common.py. Only allows TP_ZSCORE exit if current PnL >= threshold (default $0). Tested but insufficient.
- **Slippage 2 ticks default**: `costs.slippage_gc_ticks` and `costs.slippage_si_ticks` set to 2 (was 1). Configurable via optimizer overrides.
- **Hour filter**: `session.entry_start_hour` and `session.entry_end_hour` in backtest_engine_hybrid.py. Blocks new entries outside configured hours (default 0-24 = disabled).
- **GC contracts cap**: `sizing.gc_contracts_max` in position.py. Caps maximum GC contracts per trade (default 0 = no cap).
- **Verbose parameter**: `calculate_all_indicators()` and `run_hybrid_backtest()` accept `verbose=False` to suppress print output during mass backtesting.
- **3-year data upgrade**: Extended from 8 months to 3 years (Jan 2023 - Jan 2026). 801,499 1-min bars, 4,604,839 5s bars.
- **Multiprocessing grid search**: `run_grid_search_3y.py` uses `mp.Pool(8)` for parallel backtesting. 32,400 configs.