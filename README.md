# Backtest GC/SI - Spread Mean Reversion

Systeme de backtesting Python pour la strategie de spread trading Gold/Silver basee sur la cointegration et la mean reversion.

## Structure du Projet

```
backtest_gc_si/
│
├── config/
│   └── strategy_params.yaml          <- Tous les parametres (modifie ici!)
│
├── data/
│   └── raw/                          <- Exports Sierra Chart (.txt)
│       ├── GCJ26_FUT_CME_scid_BarData.txt      <- GC 1-minute
│       ├── SIH26_FUT_CME_scid_BarData.txt      <- SI 1-minute
│       ├── GCJ26_FUT_CME_5s.scid_BarData.txt   <- GC 5-secondes
│       └── SIH26_FUT_CME_5s.scid_BarData.txt   <- SI 5-secondes
│
├── output/
│   ├── trade_list.csv                <- Liste des trades Z-Score (genere auto)
│   ├── backtest_trades.csv           <- Backtest 1-min High/Low (genere auto)
│   ├── backtest_hybrid.csv           <- Backtest hybride 1min+5s (genere auto)
│   ├── optimization_log.csv          <- Historique des tests d'optimisation
│   └── archive/                      <- Resultats archives par parametres
│       ├── index.csv                 <- Index global de tous les runs
│       └── {period}/{indicators}/{entry_exit}/
│           ├── backtest_hybrid.csv
│           ├── metrics_report.txt
│           ├── equity_curve.png
│           └── params_snapshot.yaml
│
├── src/
│   ├── __init__.py
│   ├── common.py                     <- [OK] Constantes et fonctions partagees
│   ├── data_loader.py                <- [OK] Chargement/sync donnees 1-minute
│   ├── data_loader_5s.py             <- [OK] Chargement/sync donnees 5-secondes
│   ├── indicators.py                 <- [OK] Beta, Z-Score, Correlation, ADF, Hurst
│   ├── signals.py                    <- [OK] Signaux entree/sortie (Z-Score)
│   ├── position.py                   <- [OK] Sizing dollar-neutral + PnL
│   ├── backtest_engine.py            <- [OK] Simulation 1-min (High/Low dollar exits)
│   ├── backtest_engine_hybrid.py     <- [OK] Simulation hybride 1min + 5s
│   ├── optimizer.py                  <- [OK] Multi-config backtester
│   └── metrics.py                    <- [OK] Analyse performances + archivage
│
├── run_grid_search.py                <- Grid search 864 configs (optimise)
├── run_walk_forward.py               <- Walk-forward test (6 fenetres)
├── requirements.txt                  <- Dependances Python
├── validate_data.py                  <- Script de validation vs Sierra Chart
├── CLAUDE.md                         <- Instructions pour Claude Code
└── README.md                         <- Ce fichier
```

## Installation

### Prerequis
- Python 3.9 ou plus recent
- pip (gestionnaire de packages Python)

### Installer les dependances
```bash
cd backtest_gc_si
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Utilisation

### Tester chaque module
```bash
python src/data_loader.py       # Test chargement des donnees 1-min
python src/data_loader_5s.py    # Test chargement des donnees 5s
python src/indicators.py        # Test calcul des indicateurs
python src/signals.py           # Test generation des signaux + export CSV
python src/position.py          # Test sizing + calcul PnL
```

### Lancer les backtests
```bash
python src/backtest_engine.py          # Backtest 1-min (High/Low dollar exits)
python src/backtest_engine_hybrid.py   # Backtest hybride 1min + 5s (recommande)
python src/metrics.py                  # Analyse performances + archivage
```

### Valider les donnees a une date precise
```bash
python validate_data.py --date "2026-01-23 10:30:00"
```

### Utiliser dans un script
```python
from src.data_loader import load_and_prepare_data
from src.data_loader_5s import load_5s_data
from src.indicators import calculate_all_indicators
from src.backtest_engine_hybrid import run_hybrid_backtest

# Pipeline hybride complet
df_1min, config, stats = load_and_prepare_data()
df_1min = calculate_all_indicators(df_1min, config)
df_5s = load_5s_data(config)
trades = run_hybrid_backtest(df_1min, df_5s, config)
```

## Configuration

Tous les parametres sont dans `config/strategy_params.yaml`.

### Indicateurs (calcules sur barres 1-minute)
| Parametre | Valeur | Description |
|-----------|--------|-------------|
| Beta Lookback | 1980 barres | Fenetre regression OLS (~1.5 jours) |
| Z-Score Period | 20 barres | Moyenne/ecart-type du spread |
| Correlation Period | 30 barres | Correlation Pearson glissante |
| ADF/Hurst Period | 128 barres | Tests de stationnarite |

### Conditions d'entree
| Parametre | Valeur |
|-----------|--------|
| Z-Score Entry LONG | <= -2.5 |
| Z-Score Entry SHORT | >= +2.5 |
| Correlation min | > 0.60 |
| Cointegration Score min | >= 40 |

### Conditions de sortie (Z-Score)
| Parametre | LONG | SHORT |
|-----------|------|-------|
| Take Profit | Z >= -2.0 | Z <= +2.0 |
| Stop Loss | Z <= -3.5 | Z >= +3.5 |

### Conditions de sortie (Dollars)
| Parametre | Valeur |
|-----------|--------|
| PnL Take Profit | +$300 |
| PnL Stop Loss | -$600 |

### Reentree apres Stop Loss
| Parametre | Valeur |
|-----------|--------|
| Reset LONG | Z remonte a -1.0 |
| Reset SHORT | Z redescend a +1.0 |

### Couts de transaction
| Parametre | Valeur |
|-----------|--------|
| Commission | $4.00 round-trip par contrat ($2.00 par side) |
| Slippage | 1 tick par leg |

## Deux moteurs de backtest

### backtest_engine.py (1-min High/Low)
- Itere sur les barres 1-minute
- Sorties dollars detectees via High/Low intra-barre
- PnL fixe au seuil quand SL/TP dollar touche

### backtest_engine_hybrid.py (Hybride 1min + 5s) -- RECOMMANDE
- Indicateurs calcules sur barres 1-minute (lookbacks normaux)
- Quand en position : scan des barres 5-secondes pour detecter SL/TP dollar
- Si aucun trigger 5s : verification des sorties Z-Score sur la barre 1-min
- Plus precis que High/Low car utilise les prix Last reels a 5s d'intervalle
- Les donnees 5s servent uniquement au suivi PnL, pas au calcul d'indicateurs

## Avancement

1. [x] **data_loader.py** - Chargement et synchronisation GC/SI 1-minute
2. [x] **data_loader_5s.py** - Chargement et synchronisation GC/SI 5-secondes
3. [x] **indicators.py** - Beta, Spread, Z-Score, Correlation, ADF, Hurst, Cointegration Score
4. [x] **signals.py** - Machine a etats (FLAT/LONG/SHORT/COOLDOWN), signaux Z-Score
5. [x] **position.py** - Sizing dollar-neutral avec Beta, couts de transaction, calcul PnL
6. [x] **backtest_engine.py** - Simulation 1-min avec sorties dollar High/Low
7. [x] **backtest_engine_hybrid.py** - Simulation hybride 1min + 5s
8. [x] **metrics.py** - Analyse performances (10 sections) + archivage automatique

## Donnees

- **Barres 1-min synchronisees** : 186,639
- **Barres 5s synchronisees** : 1,312,336
- **Periode** : 25 mai 2025 - 30 jan 2026 (~8 mois, 182 jours de trading)
- **Source** : Sierra Chart exports (GCJ26 Gold futures, SIH26 Silver futures)

## Resultats

### Backtest hybride (config par defaut, 8 mois)
- 1,473 trades (844 LONG, 629 SHORT)
- PnL net : +$71,428, Win Rate : 62.3%
- Profit Factor : 1.95, Max Drawdown : -$20,639
- Sharpe : 4.25

### Grid search (864 configs)
- Meilleur PnL : $80,833 (beta1320, zp20, cp30, co40, TP400, SL600)
- Meilleur Sharpe : 14.72 (beta2640, zp20, cp30, co60, zE3, TP200, SL400)

### Walk-forward (6 fenetres, hors echantillon)
- PnL total hors echantillon : +$44,573
- 4/6 fenetres positives
- Retention : 203% du PnL/jour (test > train)
- Verdict : strategie robuste, pas d'overfitting

### Regimes de marche identifies
- Mai - Septembre 2025 : mean reversion faible, strategie en perte
- Octobre 2025 - Janvier 2026 : mean reversion forte, strategie tres profitable

## Scripts utilitaires

```bash
python run_grid_search.py      # Grid search 864 configs (groupement optimise, ~28 min)
python run_walk_forward.py     # Walk-forward 6 fenetres x 12 configs (~3 min)
```

---
*Developpe avec Claude AI - Janvier/Fevrier 2026*
