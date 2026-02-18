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

### 3. Signes zTP/zSL : TOUJOURS utiliser abs() dans wf_configs
Le grid YAML utilise des valeurs NEGATIVES pour zTP (ex: -0.25, -0.5).
Le grid search fait -zTP → -(-0.25) = +0.25 pour zscore_tp_long. Correct.

Mais wf_configs.py passe zTP en POSITIF (0.25). Donc :
- abs(0.25) = +0.25  ← CORRECT (c'est ce qu'on veut)
- -(0.25)  = -0.25   ← FAUX (signe inverse, TP premature)

REGLE : wf_configs utilise des valeurs POSITIVES + abs(). Ne JAMAIS remplacer
abs() par -zTP sauf si on passe aussi des valeurs negatives.
Convention wf_configs._make_overrides() :
- zscore_tp_long = +abs(zTP) (retour vers 0)
- zscore_tp_short = -abs(zTP)
- zscore_sl_long = -abs(zSL)
- zscore_sl_short = +abs(zSL)
- zscore_long = -abs(zE)
- zscore_short = +abs(zE)
Reference : grid_search_runner.py L1029-1035, wf_configs.py _make_overrides()

ERREUR COMMISE : commit eb3c933 a remplace abs() par -zTP, cassant les signes.
Reverte par 4b944df. Ne pas reproduire.

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
