# Monte Carlo Bootstrap - C6 Config (i.i.d. + Block k=5)

Date: 2026-02-14

## Configuration

- **Config**: C6_b3960_zp33_cp27_adf144_dTP250
- **Parametres**: beta=3960, zp=33, cp=27, adf=144
- **Entree**: zE=3.25, co=45
- **Sortie**: zTP=0.0, dTP=$250
- **Contract mode**: micro (MGC/SIL)
- **Micro multiplier max**: 2
- **Slippage**: 1 tick per leg
- **Autres**: zSL=-99/+99, dSL=-99999, mhb=0, flat_end_of_session=True

## Methodologie

- **Nombre de trades reels**: 258
- **Nombre de chemins**: 1,000 par methode
- **Trades par chemin**: 200 (tires avec remplacement)
- **Methode 1**: i.i.d. (trades independants)
- **Methode 2**: Block bootstrap k=5 (blocs de 5 trades consecutifs)
- **Random seed**: 42

---
# METHODE 1 : Bootstrap i.i.d.

## A) Distribution des resultats sur 200 trades

| Metrique | Median | P5 | P25 | P75 | P95 |
|----------|--------|----|----|----|----|
| PnL final ($) | $9,312 | $5,648 | $7,832 | $10,799 | $13,005 |
| Max DD ($) | $-846 | $-1,497 | $-1,047 | $-675 | $-511 |
| Sharpe | 2.78 | 1.67 | 2.33 | 3.28 | 3.96 |

## B) Risque prop firm

| Critere | % Chemins |
|---------|-----------|
| Hit -$3,000 DD | 0.0% (0/1000) |
| Hit -$5,000 DD | 0.0% (0/1000) |
| Profitable apres 50 trades | 98.5% (985/1000) |
| Profitable apres 100 trades | 99.9% (999/1000) |
| Profitable apres 200 trades | 100.0% (1000/1000) |

## C) Objectif $300/jour

- **PnL moyen par trade**: $45.75
- **Trades necessaires par jour**: 6.56
- **Trades observes par jour**: 0.24 (~7.1/mois)
- **Revenue journalier estime**: $10.77

**Conclusion**: Objectif $300/jour NON ATTEINT. Manque $289.23/jour.
  - Pour atteindre $300/jour, il faudrait 6.56 trades/jour (actuellement 0.24).
  - Soit **27.9x plus de trades** que le rythme actuel.

## D) Equity curves (percentiles)

### Table percentiles (tous les 10 trades)

| Trade # | P5 | P25 | P50 (Median) | P75 | P95 |
|---------|----|----|--------------|-----|-----|
| 1 | $-190 | $-32 | $28 | $117 | $234 |
| 10 | $-352 | $131 | $454 | $724 | $1,266 |
| 20 | $-277 | $458 | $935 | $1,392 | $2,046 |
| 30 | $77 | $851 | $1,362 | $1,968 | $2,747 |
| 40 | $319 | $1,217 | $1,840 | $2,449 | $3,440 |
| 50 | $541 | $1,619 | $2,295 | $3,003 | $4,059 |
| 60 | $985 | $1,997 | $2,764 | $3,576 | $4,787 |
| 70 | $1,182 | $2,373 | $3,308 | $4,217 | $5,510 |
| 80 | $1,446 | $2,796 | $3,781 | $4,787 | $6,137 |
| 90 | $1,919 | $3,256 | $4,242 | $5,324 | $6,633 |
| 100 | $2,215 | $3,553 | $4,755 | $5,809 | $7,284 |
| 110 | $2,560 | $4,028 | $5,205 | $6,311 | $7,801 |
| 120 | $2,812 | $4,416 | $5,650 | $6,824 | $8,418 |
| 130 | $3,240 | $4,859 | $6,093 | $7,307 | $9,051 |
| 140 | $3,537 | $5,306 | $6,554 | $7,793 | $9,594 |
| 150 | $3,845 | $5,809 | $7,017 | $8,327 | $10,136 |
| 160 | $4,294 | $6,188 | $7,521 | $8,696 | $10,714 |
| 170 | $4,715 | $6,631 | $7,956 | $9,242 | $11,354 |
| 180 | $4,991 | $7,023 | $8,441 | $9,729 | $11,807 |
| 190 | $5,390 | $7,468 | $8,855 | $10,204 | $12,424 |
| 200 | $5,648 | $7,832 | $9,312 | $10,799 | $13,005 |

**Graphique sauvegarde**: `output/reports/monte_carlo_c6_equity_iid.png`

---
# METHODE 2 : Block Bootstrap k=5

## A) Distribution des resultats sur 200 trades

| Metrique | Median | P5 | P25 | P75 | P95 |
|----------|--------|----|----|----|----|
| PnL final ($) | $8,843 | $3,709 | $6,679 | $10,953 | $13,597 |
| Max DD ($) | $-1,055 | $-1,962 | $-1,343 | $-835 | $-593 |
| Sharpe | 2.61 | 1.21 | 2.02 | 3.27 | 4.15 |

## B) Risque prop firm

| Critere | % Chemins |
|---------|-----------|
| Hit -$3,000 DD | 0.2% (2/1000) |
| Hit -$5,000 DD | 0.0% (0/1000) |
| Profitable apres 50 trades | 93.9% (939/1000) |
| Profitable apres 100 trades | 98.0% (980/1000) |
| Profitable apres 200 trades | 99.9% (999/1000) |

## D) Equity curves (percentiles)

### Table percentiles (tous les 10 trades)

| Trade # | P5 | P25 | P50 (Median) | P75 | P95 |
|---------|----|----|--------------|-----|-----|
| 1 | $-190 | $-25 | $31 | $120 | $234 |
| 10 | $-530 | $-5 | $297 | $861 | $1,750 |
| 20 | $-479 | $213 | $783 | $1,442 | $2,524 |
| 30 | $-474 | $493 | $1,253 | $2,071 | $3,423 |
| 40 | $-330 | $806 | $1,703 | $2,559 | $4,094 |
| 50 | $-95 | $1,150 | $2,035 | $3,189 | $4,740 |
| 60 | $63 | $1,384 | $2,510 | $3,629 | $5,419 |
| 70 | $77 | $1,774 | $2,929 | $4,178 | $5,942 |
| 80 | $472 | $2,083 | $3,442 | $4,732 | $6,613 |
| 90 | $663 | $2,359 | $3,882 | $5,248 | $7,191 |
| 100 | $931 | $2,857 | $4,165 | $5,760 | $7,920 |
| 110 | $1,213 | $3,219 | $4,691 | $6,366 | $8,444 |
| 120 | $1,455 | $3,611 | $5,069 | $6,793 | $9,038 |
| 130 | $1,942 | $3,949 | $5,545 | $7,264 | $9,635 |
| 140 | $2,126 | $4,402 | $6,050 | $7,697 | $10,277 |
| 150 | $2,390 | $4,845 | $6,556 | $8,240 | $10,796 |
| 160 | $2,586 | $5,061 | $6,997 | $8,789 | $11,418 |
| 170 | $2,823 | $5,510 | $7,537 | $9,361 | $12,201 |
| 180 | $3,190 | $6,009 | $7,934 | $9,916 | $12,551 |
| 190 | $3,529 | $6,319 | $8,385 | $10,487 | $13,311 |
| 200 | $3,709 | $6,679 | $8,843 | $10,953 | $13,597 |

**Graphique sauvegarde**: `output/reports/monte_carlo_c6_equity_block.png`

---
# COMPARAISON

## E) Comparaison i.i.d. vs Block Bootstrap (k=5)

| Metrique | i.i.d. | Block k=5 | Ratio |
|----------|--------|-----------|-------|
| PnL median | $9,312 | $8,843 | 0.95x |
| PnL P5 (worst) | $5,648 | $3,709 | 0.66x |
| MaxDD median | $-846 | $-1,055 | 1.25x |
| MaxDD P5 (worst) | $-1,497 | $-1,962 | 1.31x |
| Sharpe median | 2.78 | 2.61 | 0.94x |
| Hit -$3K DD | 0.0% | 0.2% | 2.0x |
| Profitable 200 trades | 100.0% | 99.9% | - |

---
*Genere par monte_carlo_c6.py*