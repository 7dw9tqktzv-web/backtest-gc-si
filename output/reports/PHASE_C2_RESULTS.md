# Phase C2 -- Exploration Multi-Filtres de Regime

## 1. Contexte

- Rolling Hurst R/S = NO-GO (H toujours > 0.5, spread structurellement persistent)
- Test de 5 filtres alternatifs sur spread daily, 3 lookbacks (20/40/60j)
- Comparaison avec 15 fenetres C1 (4 toxiques, 11 saines)

## 2. Correlations Spearman (filtre vs PnL moyen par fenetre)

| Filtre | lb=20 | lb=40 | lb=60 | Verdict |
|--------|-------|-------|-------|---------|
| Realized Vol | +0.486* | +0.107 | +0.073 | AMBIGU |
| Rolling ADF | +0.061 | -0.146 | -0.407 | AMBIGU |
| Half-life | -0.211 | -0.314 | -0.547* | PROMETTEUR |
| Correlation GC/SI | +0.436 | +0.429 | +0.543* | PROMETTEUR |
| Spread Slope (|abs|) | +0.014 | -0.096 | -0.288 | NON-DISCR. |

## 3. Separation Toxiques vs Saines (moyennes par fenetre)

| Filtre | Lookback | Toxiques | Saines | Delta |
|--------|----------|----------|--------|-------|
| Realized Vol | 20j | 0.0122 | 0.0171 | -0.0049 |
| Realized Vol | 40j | 0.0153 | 0.0179 | -0.0026 |
| Realized Vol | 60j | 0.0167 | 0.0185 | -0.0018 |
| Rolling ADF | 20j | -2.0442 | -2.0097 | -0.0344 |
| Rolling ADF | 40j | -2.2590 | -2.6363 | +0.3773 |
| Rolling ADF | 60j | -2.6013 | -3.1945 | +0.5933 |
| Half-life | 20j | 3.1472 | 7.6676 | -4.5204 |
| Half-life | 40j | 4.9167 | 3.6718 | +1.2449 |
| Half-life | 60j | 4.8710 | 3.2760 | +1.5949 |
| Correlation GC/SI | 20j | 0.7182 | 0.7742 | -0.0560 |
| Correlation GC/SI | 40j | 0.6639 | 0.7634 | -0.0994 |
| Correlation GC/SI | 60j | 0.6244 | 0.7320 | -0.1075 |
| Spread Slope (|abs|) | 20j | 0.0010 | 0.0013 | -0.0002 |
| Spread Slope (|abs|) | 40j | 0.0006 | 0.0005 | +0.0001 |
| Spread Slope (|abs|) | 60j | 0.0003 | 0.0003 | +0.0000 |

## 4. Verdict

- **Meilleur filtre** : Half-life (lb=60, |r|=0.547)
- Post-filter applique -- voir section 5

## 5. Recommandations pour C3

- Integrer Half-life comme filtre dans le backtest engine
- Re-lancer C3 Walk-Forward eliminatoire avec le filtre
