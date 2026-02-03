# Analyse approfondie du code source - GC/SI Spread Trading

> Analyse complete de chaque module, identification des bugs, problemes de logique trading,
> et suggestions d'amelioration pour rendre la strategie robuste.

---

## Table des matieres

1. [Problemes critiques (impact direct sur la rentabilite)](#1-problemes-critiques)
2. [Analyse par fichier](#2-analyse-par-fichier)
3. [Problemes transversaux de la strategie](#3-problemes-transversaux)
4. [Suggestions d'amelioration](#4-suggestions-damelioration)
5. [Prioritisation](#5-prioritisation)

---

## 1. Problemes critiques

Ces problemes ont un impact direct sur les resultats du backtest et/ou la viabilite de la strategie.

### 1.1 Les seuils TP/SL dollar comparent le PnL BRUT, pas le PnL NET

**Fichiers** : `common.py:191-237`, `backtest_engine_hybrid.py:200-250`

`calculate_current_pnl()` retourne le PnL brut (sans couts). Les seuils TP_DOLLAR (+$300) et SL_DOLLAR (-$600) sont compares a ce PnL brut. Resultat :
- Un trade qui touche TP_DOLLAR a +$300 brut realise en fait +$100 a +$180 net (apres commissions + slippage)
- Un trade qui touche SL_DOLLAR a -$600 brut realise en fait -$720 a -$800 net

**Impact** : Le ratio risque/rendement reel est de ~1:5 a 1:8 au lieu du 1:2 prevu. C'est probablement le probleme le plus impactant sur la rentabilite.

**Correction** : Soustraire les couts estimes du PnL avant de comparer aux seuils, OU ajuster les seuils pour tenir compte des couts (TP = +$300 + couts, SL = -$600 + couts).

### 1.2 Le slippage est un cout fixe post-trade, pas integre aux prix

**Fichier** : `position.py:185-186`

Le slippage est modele comme un cout fixe applique apres le trade (`slippage_gc = slip_gc_ticks * tick_value * contracts * 2`). En realite, le slippage affecte les prix d'entree et de sortie, ce qui change le PnL. Le modele actuel :
- Surestime le PnL pour les trades gagnants (prix "justes" utilises pour le calcul)
- Sous-estime les pertes pour les trades perdants

### 1.3 Le sizing variable cree un risque inconsistant

**Fichier** : `position.py`

Avec Beta variant de ~0.03 a ~6.3, les contrats GC vont de 1 a 6. Un trade a 6 GC a une exposition par tick 6x plus grande qu'un trade a 1 GC, mais les memes seuils TP/SL dollar. Resultat :
- Trades a faible Beta (1 GC) : necessitent des mouvements de spread enormes pour toucher TP
- Trades a fort Beta (6 GC) : touchent TP/SL tres rapidement, souvent sur du bruit

**Impact** : Le profil de risque est totalement different d'un trade a l'autre. Certains trades sont quasi-impossibles a gagner, d'autres sont des pile-ou-face rapides.

### 1.4 Le filtre min_pnl de TP_ZSCORE utilise aussi le PnL brut

**Fichier** : `backtest_engine_hybrid.py:293-296`

`zscore_tp_min_pnl` (ex: $200) est compare au PnL brut. Un trade avec PnL brut +$210 sortira sur TP_ZSCORE, mais apres couts, il sera en perte. Le filtre ne protege pas reellement contre les sorties non-rentables.

---

## 2. Analyse par fichier

### 2.1 `data_loader.py` (534 lignes)

**Role** : Charge les CSV Sierra Chart, synchronise GC/SI, gere le cache Parquet.

| Probleme | Severite | Detail |
|---|---|---|
| Pas de gestion de timezone | Faible | Les timestamps sont traites comme naive (pas de tzinfo). Correct si les donnees sont deja en CT, mais fragile. |
| Pas de validation des prix aberrants | Moyenne | Un prix a $0 ou $99999 dans le CSV passerait silencieusement dans le pipeline. |
| Inner join silencieux | Faible | Les barres ou un seul instrument a trade sont supprimees sans log detaille des gaps. |
| MD5 pour cache lent sur 5s | Faible | Lecture complete du CSV 5s (4.6M barres) pour calculer le hash. Pourrait utiliser taille + date de modif. |

### 2.2 `indicators.py` (763 lignes)

**Role** : Calcule tous les indicateurs techniques (Beta, Z-Score, Correlation, ADF, Hurst, HalfLife, Cointegration Score).

| Probleme | Severite | Detail |
|---|---|---|
| **Beta ddof=0 vs Z-Score ddof=1** | **Haute** | `calculate_rolling_beta()` utilise `np.var(ddof=0)` (variance population). `calculate_zscore()` utilise `pd.rolling().std()` qui default a `ddof=1` (ecart-type echantillon). Ecart de 3-5% sur des fenetres de 20-30 barres. Peut decaler les seuils Z-Score. |
| **Z-Score lookback trop court** | **Haute** | Z-Score period = 20 barres (20 min) vs Beta lookback = 1320-1980 barres. Le Z-Score normalise le spread sur seulement 20 min de donnees, ce qui rend la moyenne et l'ecart-type tres volatils. Les seuils +/-2.5 sont moins extremes qu'ils ne paraissent. |
| **ADF sans constante** | Haute | L'implementation ADF fait une regression de delta_spread sur lagged_spread SANS intercept. Le test ADF standard inclut un intercept. La valeur critique -2.86 (5%, avec constante) n'est pas valide pour cette version du test. Le score de cointegration pourrait etre systematiquement biaise. |
| **ADF skip si spread == 0** | Moyenne | `if np.any(spread_window == 0)` saute la fenetre. Cree des gaps NaN dans ADF_Statistic -> NaN dans Cointegration_Score -> bloque potentiellement des trades valides. |
| **Hurst implementation incorrecte** | Haute | L'analyse R/S utilise un seul segment par sous-periode au lieu de segments non-chevauchants moyennes. Regression sur 3-5 points seulement. L'estimateur Hurst est tres bruite et peu fiable. |
| **O(n * lookback) boucles** | Perf | Beta, ADF, Hurst, HalfLife : boucles Python lentes. ~2 milliards d'operations pour Beta seul sur 800K barres. |

### 2.3 `signals.py` (509 lignes)

**Role** : Machine a etats pour les signaux Z-Score d'entree/sortie.

| Probleme | Severite | Detail |
|---|---|---|
| Re-entree same-bar apres sortie | Faible | Apres TP_ZSCORE, une nouvelle entree est possible sur la meme barre. En live, il y aurait un delai. |
| Module peu utilise | Info | Le moteur hybrid a sa propre machine a etats. `signals.py` n'est utilise que pour l'analyse standalone. |

### 2.4 `position.py` (399 lignes)

**Role** : Sizing des positions (dollar-neutral avec Beta) et calcul du PnL.

| Probleme | Severite | Detail |
|---|---|---|
| **PnL brut vs net** (cf. 1.1) | **Critique** | Les seuils dollar sont compares au PnL brut |
| **Sizing variable** (cf. 1.3) | **Critique** | GC 1-6 contrats selon Beta |
| Slippage post-trade (cf. 1.2) | Haute | Pas integre aux prix d'execution |
| Round() asymetrique | Moyenne | `round(gc_raw)` cree un biais systematique. 1.4 -> 1 (sous-hedge), 1.5 -> 2 (sur-hedge) |
| Slippage par jambe, pas par spread | Moyenne | 2 ticks GC + 2 ticks SI != slippage reel d'un spread trade |

### 2.5 `backtest_engine.py` (689 lignes)

**Role** : Moteur backtest 1-min avec High/Low pour les sorties dollar.

| Probleme | Severite | Detail |
|---|---|---|
| High/Low simultanes irrealistes | Haute | Le PnL worst-case utilise GC High + SI Low simultanement, mais ces extremes ne se produisent pas forcement en meme temps. |
| Pas de re-entree apres sortie Z-Score | Moyenne | Contrairement au hybrid, pas de re-entree same-bar apres TP_ZSCORE/SL_ZSCORE. Incoherence entre les deux engines. |
| Module largement duplique | Info | ~1286 lignes en commun avec hybrid engine |

### 2.6 `backtest_engine_hybrid.py` (596 lignes)

**Role** : Moteur recommande. Indicateurs 1-min + monitoring 5s pour les sorties dollar.

| Probleme | Severite | Detail |
|---|---|---|
| **PnL brut pour TP/SL** (cf. 1.1) | **Critique** | `calculate_current_pnl()` retourne le brut |
| **min_pnl brut** (cf. 1.4) | Haute | Le filtre TP_ZSCORE compare au PnL brut |
| Pas de re-entree apres TP_ZSCORE | Moyenne | Apres une sortie Z-Score, pas de verification des conditions d'entree sur la meme barre. Seulement apres les sorties dollar. |
| Prix d'entree = close de la barre signal | Moyenne | L'entree se fait au Last price de la barre ou le signal est genere. En live, le fill serait au prix de la barre suivante. C'est un leger look-ahead bias. |
| Exit_ZScore de la barre 1-min, pas 5s | Faible | Lors d'une sortie dollar sur une barre 5s, le Z-Score rapporte est celui de la barre 1-min courante, pas du moment exact de sortie. |
| pd.Timestamp() dans la boucle | Perf | Creation de Timestamp 800K fois dans la boucle. Pre-calculer les heures serait plus rapide. |

### 2.7 `metrics.py` (942 lignes)

**Role** : Analyse post-backtest, rapport, equity curve, archivage.

| Probleme | Severite | Detail |
|---|---|---|
| Sharpe non-annualise correctement | Moyenne | `sharpe * sqrt(trades_per_year)` suppose des trades independants et identiquement distribues. Les trades d'une strategie mean-reversion sont correles (clustering par regime). |
| Sharpe inconsistant avec optimizer.py | Moyenne | `metrics.py` annualise par sqrt(trades/an), `optimizer.py` annualise par sqrt(252). Resultats differents pour les memes donnees. |
| CSV parsing avec csv.DictReader | Faible | Plus lent et fragile que pandas. |

### 2.8 `optimizer.py` (565 lignes)

| Probleme | Severite | Detail |
|---|---|---|
| Recalcul des indicateurs a chaque config | Perf | Pas de groupement par parametres indicateurs (contrairement au grid search script) |
| Ecrasement du CSV a chaque config | Faible | `output/backtest_hybrid.csv` ecrase a chaque iteration |

### 2.9 `run_grid_search_3y.py`

| Probleme | Severite | Detail |
|---|---|---|
| Pickle des DataFrames entiers pour chaque worker | Perf/Memoire | 4.6M barres serialisees 300 fois. Utiliser de la memoire partagee serait beaucoup plus efficace. |
| Resume fragile | Faible | Ecriture CSV incomplete possible en cas d'interruption |

---

## 3. Problemes transversaux de la strategie

### 3.1 Le Z-Score ne correspond pas au PnL dollar

Le Z-Score est calcule sur le spread en log-space (`Log_SI - Beta * Log_GC - Alpha`). Le PnL est en dollar-space. La relation entre un mouvement de Z-Score et le PnL dollar est **non-lineaire** et depend de :
- Beta courant
- Nombre de contrats GC (qui depend de Beta)
- Prix actuels de GC et SI
- Spread_Std (ecart-type du spread)

Un mouvement de 0.5 en Z-Score peut representer $50 ou $500 selon ces parametres. Les seuils Z-Score fixes (+/-2.5, +/-2.0) n'ont pas la meme signification en dollars d'un trade a l'autre.

### 3.2 Asymetrie cout/gain structurelle

Avec les parametres par defaut (TP=$300, SL=-$600) :
- Gain brut max : +$300 -> net ~+$140 (apres ~$160 de couts)
- Perte brute max : -$600 -> net ~-$760 (apres ~$160 de couts)
- Ratio risque/rendement reel : **1:5.4** au lieu du 1:2 nominal

Pour etre rentable avec ce ratio, il faut un win rate > 84%. Le walk-forward montre un win rate de 79.2%, ce qui est insuffisant.

### 3.3 Regime-dependance non geree

Les resultats montrent clairement :
- 2023 : mediocre (beaucoup d'inactivite, fenetres negatives)
- 2024 H1 : mixte
- 2024 H2 - 2025 : fortement positif

La strategie ne detecte pas les changements de regime. Elle trade avec les memes parametres quelle que soit la dynamique du marche. Un mecanisme de detection de regime (ex: rolling cointegration score sur longue periode, ou ratio de trades gagnants sur N derniers trades) pourrait couper les pertes dans les periodes defavorables.

### 3.4 Rollover de contrats invisible

Les donnees couvrent 3 ans mais referencent des contrats specifiques (GCJ26, SIH26). Sur 3 ans, il y a eu ~12 rollovers GC et ~6 rollovers SI. Si les CSV sont des donnees "continues" (back-adjusted), les prix sont corrects mais les spreads aux points de rollover peuvent avoir des discontinuites artificielles qui generent de faux signaux.

### 3.5 Pas de filtre de volume/liquidite

La strategie entre sans considerer le volume. Les periodes de faible liquidite (nuit, jours feries) ont des spreads bid/ask plus larges. Le slippage de 1-2 ticks est probablement optimiste pendant ces periodes.

---

## 4. Suggestions d'amelioration

### 4.1 Corrections immediates (impact fort, effort faible)

#### A. Utiliser le PnL NET pour les seuils TP/SL dollar

Modifier `backtest_engine_hybrid.py` pour estimer les couts AVANT de comparer aux seuils :

```python
# Au lieu de :
if current_pnl >= tp_dollar:  # PnL brut
# Faire :
estimated_costs = calculate_estimated_costs(gc_contracts, si_contracts, config)
if (current_pnl - estimated_costs) >= tp_dollar:  # PnL net
```

Ou plus simplement, ajuster les seuils : si les couts sont ~$160, utiliser TP_DOLLAR = +$460 (pour obtenir +$300 net) et SL_DOLLAR = -$440 (pour limiter la perte nette a -$600).

#### B. Corriger le filtre min_pnl de TP_ZSCORE

Meme correction : comparer `current_pnl - estimated_costs` au lieu de `current_pnl`.

#### C. Uniformiser ddof dans les calculs

Choisir ddof=0 ou ddof=1 et l'appliquer partout (Beta ET Z-Score). Verifier la reference ACSIL pour savoir lequel est correct.

### 4.2 Ameliorations structurelles (impact fort, effort moyen)

#### D. Sizing a risque fixe

Au lieu de `GC_contracts = round((NotionalSI / NotionalGC) * Beta)`, calculer le nombre de contrats pour que le SL corresponde a une perte fixe :

```python
# Objectif : SL = -$600 net pour tous les trades
max_loss_per_gc_tick = gc_contracts * $10  # $10/tick GC
max_loss_per_si_tick = si_contracts * $25  # $25/tick SI
# Ajuster gc_contracts pour normaliser le risque
```

Cela require une refonte du sizing mais normalise le profil de risque.

#### E. Seuils TP/SL adaptatifs bases sur le Z-Score-to-Dollar mapping

Calculer le "dollar par Z-Score unit" au moment de l'entree :

```python
dollar_per_zscore = Spread_Std * position_notional  # approximation
# Si dollar_per_zscore < seuil_min, ne pas entrer (le trade ne peut pas couvrir les couts)
```

Cela filtre les trades ou le mouvement de spread necessaire pour TP est trop petit par rapport aux couts.

#### F. Ajouter un intercept au test ADF

Modifier `calculate_adf_statistic()` pour inclure une constante dans la regression :

```python
# Au lieu de : X = lagged_spread (1 variable)
# Faire : X = [lagged_spread, 1] (avec intercept)
```

Puis utiliser les bonnes valeurs critiques. Cela peut changer significativement le score de cointegration.

#### G. Corriger l'estimateur Hurst

Implementer une vraie analyse R/S avec segments non-chevauchants et plus de points de regression. Ou utiliser un estimateur plus robuste (Detrended Fluctuation Analysis - DFA).

Note : Hurst est actuellement desactive (hurst_max=1.0) car redondant avec le score de cointegration. Si la correction de l'ADF change le score de cointegration, Hurst pourrait redevenir utile.

### 4.3 Ameliorations strategiques (impact potentiellement fort)

#### H. Remplacer TP_ZSCORE par un trailing stop dollar

Au lieu de sortir quand le Z-Score revient vers 0 (mouvement potentiellement petit en dollars), utiliser un trailing stop :

```python
# Apres entree, tracker le PnL max atteint
if current_pnl > highest_pnl:
    highest_pnl = current_pnl
# Sortir si le PnL recule de X depuis le max
if current_pnl < highest_pnl - trailing_stop:
    exit("TRAILING_STOP")
```

Cela laisse courir les profits et protege les gains acquis.

#### I. Sortie temporelle (time stop)

Ajouter une duree maximale par trade (ex: 240 barres = 4h). Si le trade n'a pas touche TP ou SL, sortir au marche. Cela evite les trades qui stagnent pendant des heures et qui finissent par toucher SL.

#### J. Filtre de regime base sur la cointegration glissante

Ne trader que lorsque le Cointegration_Score est > seuil depuis N barres consecutives :

```python
# Rolling minimum du score de cointegration sur 60 barres
coint_regime = Cointegration_Score.rolling(60).min() > 50
# Seulement entrer si coint_regime == True
```

Cela evite d'entrer pendant les periodes ou la cointegration est instable (regimes defavorables de 2023).

#### K. Filtre de volume ou de volatilite

Calculer la volatilite recente (ex: ATR sur 20 barres) et :
- Ne pas entrer si ATR < seuil (marche trop calme, spread ne bougera pas assez)
- Ne pas entrer si ATR > seuil (marche trop volatile, slippage potentiellement > 2 ticks)

#### L. Z-Score sur les rendements plutot que les niveaux

Au lieu de `ZScore = (Spread - Mean) / Std` ou Spread est en niveaux log, calculer :
```python
Spread_Returns = Spread.diff()
ZScore = Spread_Returns.rolling(N).apply(zscore_func)
```

Un Z-Score sur les rendements est plus stationnaire et moins sensible aux changements de regime du spread.

#### M. Filtre Kalman pour le Beta

Remplacer le rolling OLS par un filtre de Kalman pour estimer Beta. Avantages :
- Pas de lookback fixe (adaptatif)
- Poids decroissants sur les observations passees
- Estimation plus lisse, moins de bruit dans le sizing

### 4.4 Ameliorations de performance (effort faible-moyen)

#### N. Vectoriser les indicateurs

Remplacer les boucles Python par des operations pandas/numpy vectorisees :
- `calculate_rolling_beta()` : utiliser `pd.rolling().cov()` et `pd.rolling().var()`
- `calculate_zscore()` : deja vectorise (OK)
- ADF/Hurst : plus complexe, mais possible avec scipy

#### O. Memoire partagee pour le multiprocessing

Utiliser `multiprocessing.shared_memory` ou `numpy.memmap` pour partager les DataFrames entre workers au lieu de les pickle-iser.

---

## 5. Prioritisation

### Tier 1 - Corrections critiques (a faire en premier)

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| A | PnL NET pour seuils TP/SL dollar | Corrige le ratio risque/rendement reel | Faible |
| B | PnL NET pour filtre min_pnl TP_ZSCORE | Evite les sorties TP_ZSCORE perdantes | Faible |
| C | Uniformiser ddof | Corrige un biais potentiel de 3-5% sur le Z-Score | Faible |

### Tier 2 - Ameliorations structurelles (impact fort)

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| D | Sizing a risque fixe | Normalise le risque, resultats plus consistants | Moyen |
| E | Filtre dollar/Z-Score a l'entree | Elimine les trades ou le TP est inatteignable | Moyen |
| H | Trailing stop au lieu de TP_ZSCORE | Laisse courir les profits, meilleur ratio rendement | Moyen |
| J | Filtre de regime cointegration | Evite les periodes defavorables (2023) | Faible |

### Tier 3 - Ameliorations strategiques (validation requise)

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| F | Corriger ADF (intercept) | Score de cointegration plus fiable | Moyen |
| G | Corriger Hurst | Estimateur plus fiable (si reactive) | Moyen |
| I | Sortie temporelle (time stop) | Evite les trades qui stagnent | Faible |
| K | Filtre volatilite/volume | Reduit le slippage effectif | Moyen |
| L | Z-Score sur rendements | Plus stationnaire, moins regime-dependant | Moyen |
| M | Filtre Kalman pour Beta | Sizing plus stable | Haut |

### Tier 4 - Performance et qualite de code

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| N | Vectoriser indicateurs | Grid search 10-50x plus rapide | Moyen-Haut |
| O | Memoire partagee multiprocessing | Grid search 2-3x plus rapide | Moyen |

---

## Conclusion

La strategie a deux problemes fondamentaux :

1. **L'asymetrie cout/gain** (section 3.2) : les couts de transaction mangent une part enorme du TP dollar, creant un ratio risque/rendement reel de 1:5 au lieu de 1:2. Les corrections A et B du Tier 1 adressent ce probleme.

2. **La deconnexion Z-Score/dollar** (section 3.1) : le Z-Score est en log-space, le PnL en dollar-space. Les seuils Z-Score fixes n'ont pas le meme sens economique d'un trade a l'autre. Les corrections D et E du Tier 2 adressent ce probleme.

Avant de tester le 5-min timeframe ou tout autre changement de paradigme, il faut d'abord corriger ces problemes dans le code existant. Les corrections du Tier 1 sont rapides et pourraient a elles seules transformer les resultats.
