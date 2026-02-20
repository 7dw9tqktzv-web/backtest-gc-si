# Paper Trading Journal - C09 Micro

**Config**: b2640_zp28_cp12_adf64_zE3.4_co20_zTP-0.5_dTP200_dSL-500_nohold_mm2_es0
**Start**: 2026-02-20
**Objectif**: 30+ trades, 4-8 semaines
**Instance SC**: F:\SierreChart_Backtest_GC_SI_micro\ (MGC/SIL, Sim1)

---

## Trades Auto (C09 - zE=3.4)

| # | Date CT | Dir | MGC qty | SIL qty | Entry Z | Exit Z | Exit Reason | PnL net | Bars | Notes |
|---|---------|-----|---------|---------|---------|--------|-------------|---------|------|-------|
| A1 | 2026-02-20 09:16 | SHORT | 11 @ 5014.60 | 2 @ 79.955 | 3.43 | 3.29 | TP_DOLLAR | +$203 | 0 | Premier trade auto. Beta=3.42. Sortie instantanee. |

**Cumul auto**: 1 trade, +$203, WR 100%

---

## Trades Manuels (zE < 3.4)

| # | Date CT | Dir | MGC qty | SIL qty | Entry Z | Exit Z | Exit Reason | PnL net | Bars | Notes |
|---|---------|-----|---------|---------|---------|--------|-------------|---------|------|-------|
| M1 | 2026-02-20 05:58-06:34 | LONG | 11 @ 5037.0→5040.4 | 2 @ 80.400→80.205 | ~3.0-3.2 | | TP? | +$739 | ~36 | MGC +$353, SIL +$386 |
| M2 | 2026-02-20 07:50-08:04 | SHORT | 11 @ 5062.1→5060.5 | 2 @ 80.700→80.800 | ~3.0-3.2 | | TP? | +$351 | ~14 | MGC +$155, SIL +$196 |
| M3 | 2026-02-20 09:07-09:18 | LONG | 11 @ 5014.1→5061.6 | 2 @ 79.905→81.380 | ~3.0-3.2 | | | +$2,250 | ~11 | Monster trade. MGC +$5,204, SIL -$2,954 |

**Cumul manuel**: 3 trades, +$3,340 gross, WR 100%

---

## Resume Quotidien

### 2026-02-20
- **Auto**: 1 trade SHORT, +$203 net (TP_DOLLAR, 0 bars)
- **Manuel**: 3 trades a Z~3.0-3.2 (+$739, +$351, +$2,250)
- **Erreur**: petit trade 09:06 (+$33) = erreur manuelle, ignore
- **Total journee**: +$3,462 gross (TAL SC), 4/4 gagnants + 1 erreur
- **Conditions**: Z-Score eleve (>3.0), regime tres favorable
- **Observations**: Trade M3 exceptionnel (+$2,250), spread explose de 47pts MGC en 11 min. Tous les trades gagnants.

---

## Statistiques Globales

| Metrique | Auto (C09) | Manuel | Total |
|----------|-----------|--------|-------|
| Trades | 1 | 3 | 4 |
| PnL gross | +$227 | +$3,340 | +$3,567 |
| Win Rate | 100% | 100% | 100% |
| Avg PnL/trade | +$227 | +$1,113 | +$892 |
| Meilleur trade | +$227 | +$2,250 | +$2,250 |
| Pire trade | +$227 | +$351 | +$227 |

---

## Notes de Session

- Separer auto vs manuel pour evaluer objectivement C09
- Les trades manuels a zE < 3.4 sont informatifs mais NE DOIVENT PAS influencer la config auto
- Regime actuel (fev 2026) = favorable — ne pas extrapoler
