# QUANT AUDIT V1 -- Strategie GC/SI Spread Mean Reversion

*Date: 2026-02-08*
*Config: b2640_zp20_cp30_adf26_zE3.5_co40_zTP-1.0 (5-min pure Z-Score, 2 ticks slippage)*

---

## 1. Executive Summary

### Forces
- PnL robuste sur 3 ans: $45224 (100 trades, WR 53%)
- Monte Carlo P(perte 100tr) = 0.9% -- tres faible risque de ruine
- Breakeven slippage = 8.0 ticks -- marge de securite 6x vs nominal
- Parametres stables: la plupart robustes a +/-10% (cf. Point 4)

### Faiblesses
- **Regime-dependant**: 2023-2024 perdant, 2025-2026 profitable (Point 1)
- Echantillon limite: 100 trades sur 3 ans (Point 2)
- Aucun filtre de regime n'a tenu en walk-forward OOS (Phase C3)
- Frequence de trading faible (~2.8 trades/mois)

### Risques principaux
- Retour a un regime 2023-style: extrapolation = -$15,320 sur 100 trades (Point 1)
- **ALERTE: Autocorrelation PnL hautement significative** (lag 1: r=0.50, p<0.0001). Block bootstrap P(perte)=17.2% vs i.i.d. 1.0% (Point 10)
- 2026 concentre 80% du PnL ($46K/8 trades) -- risque de recence extreme
- Score prop firm mediocre: 49.7/100, penalise par trailing DD et frequence faible

## 2. Diagnostic: Dependance au regime (Point 1)

### PnL par annee

| Annee | Trades | PnL Total | PnL/Trade | Win Rate | Max Perte |
|-------|--------|-----------|-----------|----------|-----------|
| 2023 | 34 | $-5,208 | $-153 | 47% | $-1,868 |
| 2024 | 34 | $-6,109 | $-180 | 47% | $-2,662 |
| 2025 | 24 | $10,585 | $441 | 58% | $-2,138 |
| 2026 | 8 | $45,956 | $5,744 | 88% | $-1,690 |

### Caracteristiques du spread par annee

*(Bug technique: l'index 5min n'a pas ete correctement decompose par annee. Voir stats annuelles via trades.)*

**Concentration du PnL par periode:**
- 2023: 34 trades, -$5,208 (-$153/trade) -- regime defavorable
- 2024: 34 trades, -$6,109 (-$180/trade) -- regime defavorable
- 2025: 24 trades, +$10,585 (+$441/trade) -- regime favorable
- 2026 (1 mois): 8 trades, +$45,956 (+$5,744/trade) -- **outlier extreme**

**80% du PnL total provient de janvier 2026 (8 trades sur 100)**. Sans 2026, la strategie est a +$750 sur 2.5 ans.

### Analyse

Le changement de regime est le risque #1. Facteurs possibles:
- **Volatilite du spread**: les annees rentables montrent un spread plus volatile (Z-Score range plus large), creant plus d'opportunites de mean-reversion
- **Correlation GC/SI**: une correlation plus haute stabilise le spread et ameliore la qualite des signaux
- **Facteurs macro**: politique monetaire (taux Fed), inflation, geopolitique affectent differemment l'or et l'argent
- **Pas de filtre fonctionnel**: 6 filtres testes en C2, aucun robuste en OOS. Accepter comme risque structurel.

**Recommandation**: Surveiller manuellement la correlation GC/SI sur 40 jours. Si < 0.80, reduire la taille ou suspendre le trading.

## 3. Diagnostic: Sensibilite des parametres (Point 4)

### Sensibilite par parametre (B2 5min zscore, configs >= 50 trades)

| Parametre | Valeur | PnL Moyen | Std | Configs |
|-----------|--------|-----------|-----|---------|
| beta | 1320.0 | $-71,259 | $76,517 | 7764 |
| beta | 2640.0 | $-59,041 | $67,331 | 7692 |
| beta | 3960.0 | $-48,776 | $60,872 | 7690 |
| beta | 5280.0 | $-52,405 | $58,040 | 7707 |
| zp | 20.0 | $-44,254 | $58,466 | 5196 |
| zp | 24.0 | $-49,353 | $69,761 | 6061 |
| zp | 30.0 | $-65,208 | $75,520 | 6336 |
| zp | 48.0 | $-61,121 | $60,347 | 6552 |
| zp | 60.0 | $-66,141 | $64,064 | 6708 |
| cp | 12.0 | $-51,263 | $65,516 | 8028 |
| cp | 24.0 | $-52,622 | $66,730 | 7798 |
| cp | 36.0 | $-70,469 | $71,182 | 7560 |
| cp | 60.0 | $-57,818 | $61,017 | 7467 |
| adf | 26.0 | $-81,404 | $81,066 | 8532 |
| adf | 64.0 | $-56,046 | $60,250 | 7450 |
| adf | 96.0 | $-42,863 | $54,199 | 7404 |
| adf | 128.0 | $-47,802 | $57,878 | 7467 |
| zE | 2.5 | $-106,972 | $75,984 | 11520 |
| zE | 3.0 | $-39,796 | $38,080 | 11067 |
| zE | 3.5 | $-13,747 | $29,105 | 8266 |
| co | 40.0 | $-84,130 | $75,222 | 11472 |
| co | 50.0 | $-52,080 | $57,827 | 10714 |
| co | 60.0 | $-30,373 | $49,788 | 8667 |
| zTP | -1.0 | $-63,005 | $70,729 | 7711 |
| zTP | -0.5 | $-59,645 | $68,224 | 7713 |
| zTP | 0.0 | $-54,200 | $63,869 | 7713 |
| zTP | 0.5 | $-54,750 | $63,085 | 7716 |

### Parametres redondants (confirmes)
- `correlation_min` (0.60): toujours > 0.80 quand Z+Coint satisfaits -- peut etre supprime
- `hurst_max` (1.0): Hurst < 0.45 sur 100% des barres tradees -- deja desactive
- `zscore_sl`: aucun trade ne declenche SL_ZSCORE en mode pure zscore

### Parametres sensibles
- **zTP** (take-profit zscore): parametres le plus impactant. zTP=-1.0 >> zTP=0.0 >> zTP=1.0
- **zE** (entry threshold): 3.5 quasi-exclusif a 2 ticks (42/50 top B1). Tres sensible.
- **beta_lookback**: b2640 domine (27/50 top B1), mais b3960 aussi viable (walk-forward)
- **adf_period**: adf=26 domine en non-HMM (36/50 top B1). Court = reactif.

## 4. Diagnostic: Analyse horaire (Point 8)

| Heure CT | Trades | PnL Total | PnL/Trade | Win Rate |
|----------|--------|-----------|-----------|----------|
| 0:00 | 9 | $-2,516 ** | $-280 | 44% |
| 1:00 | 2 | $-116 | $-58 | 50% |
| 2:00 | 1 | $3,153 | $3,153 | 100% |
| 3:00 | 2 | $1,344 | $672 | 50% |
| 4:00 | 2 | $3,460 | $1,730 | 50% |
| 5:00 | 2 | $-1,156 ** | $-578 | 50% |
| 6:00 | 3 | $1,236 | $412 | 100% |
| 7:00 | 15 | $-6,418 ** | $-428 | 47% |
| 8:00 | 3 | $-3,224 ** | $-1,075 | 0% |
| 9:00 | 2 | $8,982 | $4,491 | 50% |
| 10:00 | 2 | $759 | $380 | 50% |
| 12:00 | 2 | $-2,316 ** | $-1,158 | 0% |
| 13:00 | 1 | $7,729 | $7,729 | 100% |
| 14:00 | 1 | $167 | $167 | 100% |
| 17:00 | 21 | $28,249 | $1,345 | 57% |
| 18:00 | 5 | $40 | $8 | 40% |
| 19:00 | 8 | $2,066 | $258 | 50% |
| 20:00 | 10 | $-2,558 ** | $-256 | 50% |
| 22:00 | 5 | $1,340 | $268 | 60% |
| 23:00 | 4 | $5,003 | $1,251 | 100% |

### Recommandation
Heures a PnL negatif: 0:00 CT, 1:00 CT, 5:00 CT, 7:00 CT, 8:00 CT, 12:00 CT, 20:00 CT
Impact total des heures negatives: $-18,304

**ATTENTION**: Avec ~100 trades, les stats par heure sont fragiles (souvent < 10 trades/heure). Ne pas sur-optimiser. Observer les grands blocs (nuit vs jour) plutot que les heures individuelles.

## 5. Diagnostic: Asymetrie LONG/SHORT (Point 9)

| Direction | Trades | PnL Total | PnL/Trade | PnL Median | Win Rate | Max Gain | Max Perte | Duree Moy |
|-----------|--------|-----------|-----------|------------|----------|----------|-----------|-----------|
| LONG | 57 | $27,318 | $479 | $52 | 53% | $16,743 | $-2,662 | 176 min |
| SHORT | 43 | $17,906 | $416 | $22 | 54% | $9,400 | $-2,138 | 288 min |

### Analyse
- En Monte Carlo C4: LONG P(perte 100tr) = 1.8% vs SHORT = 1.0%
- Les LONG sont legerement plus risques mais cela reste dans les marges statistiques
- **Recommandation**: pas de differenciation des seuils pour V1. A reevaluer avec plus de trades en paper trading.

## 6. Diagnostic: Autocorrelation des trades (Point 10)

| Lag | Correlation | p-value | Significatif |
|-----|-------------|---------|-------------|
| lag_1 | 0.5009 | 0.0 | OUI |
| lag_2 | 0.3948 | 0.0001 | OUI |
| lag_3 | 0.6841 | 0.0 | OUI |

### Bootstrap comparison

**DECOUVERTE CRITIQUE**: l'autocorrelation PnL est **hautement significative** a tous les lags (p < 0.001).

| Methode | P(perte 100 trades) |
|---------|---------------------|
| i.i.d. bootstrap (C4) | 1.0% |
| Block bootstrap (blocs=5) | **17.2%** |

L'autocorrelation positive (r=0.50 lag 1) signifie que les gros PnL (gains ou pertes) tendent a se suivre.
Paradoxalement, le test de runs (p=0.87) montre que la sequence win/loss est aleatoire -- c'est la **magnitude**
des PnL qui est autocorrelee, pas la direction. Cela s'explique par les regimes: en periode favorable, les gains
sont grands; en periode defavorable, les pertes s'accumulent.

**Impact**: Le Monte Carlo C4 (P(perte)=0.9%) est **significativement optimiste**. Le block bootstrap (17.2%)
est une meilleure estimation du risque reel. La strategie reste deployable mais le risque de drawdown prolonge
est **17x plus eleve** que ce que le bootstrap i.i.d. suggerait.

**Recommandation**: utiliser P(perte)=17% comme reference pour le risk management, pas 0.9%.

## 7. Scoring Prop Firm (Point 6)

### Framework de scoring

| Composante | Poids | Score |
|-----------|-------|-------|
| PnL/trade | 20% | -- |
| DD journalier | 15% | -- |
| DD trailing (HWM) | 15% | -- |
| Consistency hebdo | 20% | -- |
| Profit Factor | 15% | -- |
| Trades/mois | 15% | -- |

**Score composite: 49.7/100** (mediocre)

| Metrique | Valeur | Score (0-1) |
|----------|--------|-------------|
| PnL/trade | $452 | 0.90 |
| DD journalier max | -$2,662 | 0.52 |
| DD trailing (HWM) | -$17,341 | 0.00 |
| Consistency hebdo | 50.0% | 0.50 |
| Profit Factor | 2.41 | 0.70 |
| Trades/mois | 2.9 | 0.22 |

**Points faibles prop firm:**
- Trailing DD de -$17,341 est excessif (echouerait la plupart des challenges a $2,500-$5,000 trailing DD)
- Seulement 2.9 trades/mois -- trop peu pour la plupart des programmes
- Consistency 50% -- insuffisant (objectif > 60%)
- Le PnL/trade et PF sont bons, mais ne compensent pas les faiblesses structurelles

Voir `output/reports/prop_firm_scoring.csv` pour les metriques detaillees.

## 8. Recommandations d'exploration (Points 2, 5, 7)

### Point 2 -- Plage de donnees
- 3 ans / 100 trades est **le minimum acceptable** pour validation statistique
- **Recommandation**: etendre a 5 ans si possible (back-adjusted continus)
- Avec 5 ans, on capture potentiellement 2 cycles de regime complets
- Vigilance: liquidite historique GC/SI est stable, pas de biais majeur sur les continus
- **Alternative**: accumuler des trades en paper trading pour augmenter l'echantillon OOS

### Point 5 -- Zones de grid non explorees
- **zE=3.0 en 5min pure zscore**: teste mais domine par zE=3.5. Peu de potentiel.
- **beta > 3960**: non teste. Pourrait capturer des relations a plus long terme.
- **Lookbacks adaptatifs**: non testes. Complexite elevee, gain incertain.
- **Entrees asymetriques LONG/SHORT**: non testees. Potentiellement utile si asymetrie confirmee en Point 9.
- **Raffinement local autour de b2640/zp20/adf26**: deja bien explore (top 20 B1/B2 concentres).
- **Priorite**: faible. L'espace a ete bien couvert (253K configs).

### Point 7 -- Filtre de volatilite
- Les 6 filtres C2 etaient bases sur les proprietes du spread. Approche alternative: volatilite du sous-jacent.
- **Realized vol GC/SI**: calculable directement sur les donnees existantes
- **Ratio vol GC/SI**: potentiellement informatif sur les changements de regime
- **Lecon C3**: un bon filtre doit bloquer significativement les trades en OOS, pas juste modifier le train
- **Priorite**: moyenne. Tenter APRES paper trading, si le regime-risk se materialise.

## 9. Roadmap V2 (Ameliorations futures)

| Amelioration | Pertinence | Complexite | Impact | Priorite |
|-------------|-----------|-----------|--------|----------|
| Sizing dynamique (vol-based) | Haute | Moyenne | Reduit le risque sans bloquer trades | **1** |
| Extension donnees a 5 ans | Haute | Faible | +50% echantillon, 2 cycles de regime | **2** |
| Kalman/EWMA Beta | Moyenne | Moyenne | Beta plus reactif, potentiel PnL+ | 3 |
| Validation multi-TF | Moyenne | Elevee | Filtre de confirmation, moins de trades | 4 |
| HMM regime (Python-only) | Moyenne | Deja fait | +13% consistency, -12% PnL | 5 (si Python-only OK) |
| Entrees asymetriques L/S | Basse | Faible | Impact marginal probablement | 6 |
| Filtre vol sous-jacent | Basse | Moyenne | Incertain (cf. echec filtres C2/C3) | 7 |

## 10. Verdict final

### La strategie est-elle prete pour le paper trading Phase D ?

**OUI, avec reserves importantes.**

La strategie peut passer en paper trading, mais cet audit revele des faiblesses significatives non identifiees precedemment:

### Nouvelles alertes (cet audit)
1. **Autocorrelation PnL critique**: block bootstrap P(perte)=17.2%, pas 0.9%. Le risque reel est 17x plus eleve que le Monte Carlo C4.
2. **Concentration extreme du PnL**: 80% du profit vient de Jan 2026 (8 trades). Sans ces trades, la strategie est flat sur 2.5 ans.
3. **Score prop firm insuffisant**: 49.7/100. Trailing DD et frequence trop faibles pour la plupart des programmes prop.
4. **Bloc 7h-8h CT toxique**: -$9,642 sur 18 trades (47% WR, -$536/trade). Potentiel filtre horaire a explorer.

### Conditions pour le paper trading
1. **Risque reel a 17%**: utiliser cette reference, pas 0.9%, pour le sizing et le risk management.
2. **Surveiller manuellement**: correlation GC/SI quotidienne. Si < 0.80, reduire ou suspendre.
3. **Objectif**: 30+ trades minimum, comparer aux metriques du backtest.
4. **Critere d'arret**: MaxDD > $10,000 OU > 5 pertes consecutives OU 0 trade en 4 semaines = pause et reevaluation.
5. **Considerer le filtre horaire**: bloquer 7h-8h CT pourrait economiser -$9.6K (a valider en WF).
6. **Ne pas viser les prop firms en V1**: le trailing DD est trop eleve. Viser du trading personnel d'abord.

### Ameliorations a considerer AVANT le paper trading
- **Block bootstrap C4bis**: relancer Monte Carlo C4 avec block bootstrap pour avoir des chiffres de risque fiables
- **Filtre horaire 7-8h CT**: 18 trades, echantillon limite mais signal fort (-$536/trade vs +$452 global)
- **Sizing dynamique**: reduire en periode de faible correlation pour limiter le trailing DD

---

*Rapport genere automatiquement par `scripts/quant_audit_v1.py`*