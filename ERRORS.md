# Erreurs connues -- NE PAS REPRODUIRE

### 1. Override keys : utiliser les VRAIS noms du YAML
Les cles d'override doivent correspondre EXACTEMENT aux cles dans strategy_params.yaml
et lues par pack_config() dans backtest_engine_numba.py.

FAUX (cles fantomes, silencieusement ignorees) :
- entry.zscore_entry -> N'EXISTE PAS
- entry.cointegration_min -> N'EXISTE PAS
- exit.zscore_tp -> N'EXISTE PAS
- exit.dollar_tp -> N'EXISTE PAS
- exit.dollar_sl -> N'EXISTE PAS
- exit.zscore_sl -> N'EXISTE PAS

CORRECT (cles reelles lues par pack_config) :
- entry.zscore_long / entry.zscore_short
- entry.cointegration_score_min
- exit.zscore_tp_long / exit.zscore_tp_short (attention aux signes!)
- exit.zscore_sl_long / exit.zscore_sl_short
- exit.pnl_take_profit / exit.pnl_stop_loss
- exit.max_holding_bars (pas exit.max_hold)

REGLE : avant d'ecrire un override, TOUJOURS verifier la cle exacte dans
pack_config() (backtest_engine_numba.py L114-204) ET strategy_params.yaml.

### 2. apply_overrides() ne validait PAS les cles (CORRIGE 2026-02-18)
apply_overrides() creait silencieusement des cles inexistantes sans erreur.
FIX : warnings.warn() ajoute pour cles inconnues.
Si un backtest donne des resultats inattendus (trades 2-3x differents du grid),
verifier les cles d'override EN PREMIER.

### 3. Signes zTP/zSL : reproduire EXACTEMENT le grid search (CORRIGE 2026-02-18)
NE PAS utiliser abs() sur zTP ! Le grid search fait :
- zscore_tp_long = -zTP (PAS -abs(zTP))
- zscore_tp_short = +zTP (PAS +abs(zTP))
- zscore_sl_long = -abs(zSL)
- zscore_sl_short = +abs(zSL)
- zscore_long = -abs(zE)
- zscore_short = +abs(zE)

abs(zTP) donne des signes inverses pour zTP positif, ce qui change le niveau
de sortie TP_ZSCORE et impacte le PnL (ex: $8K -> $5.7K pour C09).
Reference : grid_search_runner.py L1028-1035, wf_configs.py _make_overrides()

REGLE : toujours copier la formule EXACTE du grid search, ne jamais "simplifier" les signes.

### 4. flat_end_of_session : lire depuis session, pas exit (CORRIGE 2026-02-16)
- pack_config() lisait `config['exit']['flat_end_of_session']` au lieu de `config['session']['flat_end_of_session']`
- Consequence : FLAT_EOD jamais actif dans tous les grid searches R1-R2c
- FIX : `ses.get('flat_end_of_session')` dans pack_config()

### 5. Entry_DateTime pas Entry_Time (colonnes PascalCase)
- Le moteur Numba retourne des colonnes PascalCase : Entry_DateTime, Exit_DateTime, PnL_Net, PnL_Gross, Exit_Reason
- PAS snake_case : entry_time, pnl_net, exit_reason
- Toujours verifier les noms de colonnes avant d'y acceder

### 6. Micro sizing cap vs multiplier (CORRIGE 2026-02-16)
- micro_mult_max etait utilise comme cap sur GC+SI au lieu de multiplicateur SIL
- GC cape a 2 contrats au lieu de 10-13
- FIX : logique smart multiplier identique a position.py
