# Backtest GC/SI - Spread Mean Reversion

Systeme de backtesting Python pour la strategie de spread trading Gold/Silver basee sur la cointegration et la mean reversion. **Harmonise avec Sierra Chart v1.5** (< 0.01% de difference sur tous les indicateurs).

## Statut du Projet

| Etape | Statut |
|-------|--------|
| Backtest Python | COMPLETE |
| Walk-forward validation | COMPLETE |
| Harmonisation Sierra Chart v1.5 | COMPLETE |
| Paper trading | EN COURS |

**Meilleure config**: `b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50`
- PnL walk-forward (3 ans): **$45,500**
- 207 trades, 58.1% Win Rate, PF 1.58

## Structure du Projet

```
backtest_gc_si/
│
├── config/
│   └── strategy_params.yaml          <- Tous les parametres (modifie ici!)
│
├── data/
│   ├── raw/                          <- Exports Sierra Chart (.txt)
│   └── processed/                    <- Cache Parquet (auto-genere)
│
├── output/
│   ├── backtest_hybrid.csv           <- Derniers trades
│   ├── archive/                      <- Resultats archives CLASSES
│   │   ├── CLASSEMENT.txt            <- Resume avec recommandations
│   │   ├── index.csv                 <- Index global de tous les runs
│   │   └── hmm_grid_search/          <- Archives HMM filter
│   └── grid_search_*.csv             <- Resultats grid search
│
├── src/
│   ├── common.py                     <- Constantes et fonctions partagees
│   ├── data_loader.py                <- Chargement/sync donnees 1-min et 5-min
│   ├── indicators.py                 <- Beta, Z-Score, Correlation, ADF, Hurst
│   ├── signals.py                    <- Signaux entree/sortie (Z-Score)
│   ├── position.py                   <- Sizing dollar-neutral + PnL
│   ├── backtest_engine_hybrid.py     <- Simulation hybride 1min + 5s
│   ├── optimizer.py                  <- Multi-config backtester
│   ├── metrics.py                    <- Analyse performances + archivage
│   └── regime.py                     <- Filtre HMM (optionnel)
│
├── tests/                            <- 112 tests unitaires
├── DOC SIERRA/                       <- Indicateur Sierra Chart v1.5
├── CLAUDE.md                         <- Instructions pour Claude Code
├── CHANGELOG.md                      <- Historique complet des optimisations
└── README.md                         <- Ce fichier
```

## Installation

```bash
cd backtest_gc_si
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt
```

## Utilisation

### Lancer le backtest
```bash
python src/backtest_engine_hybrid.py   # Backtest hybride 1min + 5s
python src/metrics.py                  # Analyse performances + archivage
```

### Lancer les tests
```bash
pytest tests/ -v                       # 112 tests
pytest tests/ --cov=src                # Avec coverage
```

### Grid search et walk-forward
```bash
python run_grid_search_hmm_full.py     # 129,600 configs (~3h)
python run_walk_forward_hmm.py         # 48 fenetres walk-forward
```

## Configuration Optimale

Parametres dans `config/strategy_params.yaml` (harmonises avec Sierra Chart v1.5):

### Indicateurs
| Parametre | Valeur | Description |
|-----------|--------|-------------|
| beta_lookback | 1320 | ~5 jours de trading (5-min bars) |
| zscore_period | 24 | ~2 heures |
| correlation_period | 24 | ~2 heures |
| adf_hurst_period | 96 | ~8 heures |

### Conditions d'entree
| Parametre | Valeur |
|-----------|--------|
| Z-Score Entry | +/- 3.0 |
| Correlation min | > 0.60 |
| Cointegration Score min | >= 50 |

### Conditions de sortie
| Parametre | LONG | SHORT |
|-----------|------|-------|
| Z-Score TP | >= +2.0 | <= -2.0 |
| Z-Score SL | <= -4.5 | >= +4.5 |

### Couts de transaction
| Parametre | Valeur |
|-----------|--------|
| Commission | $4.00 round-trip par contrat |
| Slippage | 1-2 ticks par leg |

## Harmonisation Sierra Chart v1.5

Python et Sierra Chart produisent des valeurs **identiques** (< 0.01% de difference):

| Indicateur | Difference |
|------------|------------|
| Beta | 0.00% |
| ADF Statistic | 0.01% |
| Correlation | 0.00% |
| Z-Score | 0.03% |
| Hurst | 0.01% |

### Fichiers Sierra Chart
- **Indicateur**: `DOC SIERRA/files/GC_SI_SpreadMeanReversion_v1.5.cpp`
- **Validation**: `compare_sierra_v3.py`

### Parametres Sierra Chart (doivent matcher Python)
```
Beta Lookback: 1320
Z-Score Period: 24
Correlation Period: 24
ADF/Hurst Period: 96
Z-Score Upper/Lower Threshold: +/-3
Min Cointegration Score: 50
Session: 17:00 - 15:30 CT
```

## Resultats Walk-Forward (48 fenetres, 3 ans)

| Config | PnL | Trades | Win Rate | PF | Fenetres + |
|--------|-----|--------|----------|-----|------------|
| **NO_HMM** | **$45,500** | 207 | 58.1% | 1.58 | 47% |
| HMM_DIAG | $40,221 | 160 | 60.2% | 2.39 | 60% |

- **NO_HMM**: Maximum PnL, 98% des fenetres valides
- **HMM_DIAG**: Maximum consistance (60% fenetres positives)

## Donnees

- **Periode**: 26 jan 2023 - 30 jan 2026 (~3 ans)
- **Barres 1-min**: 801,499 synchronisees
- **Barres 5s**: 4,604,839 synchronisees
- **Source**: Sierra Chart (GCJ26 Gold, SIH26 Silver)

## Prochaines Etapes

1. **Paper trading** sur Sierra Chart avec config optimale
2. **Validation** des trades paper vs backtest Python
3. **Production** apres validation (2-4 semaines minimum)

---
*Developpe avec Claude AI - Janvier/Fevrier 2026*
