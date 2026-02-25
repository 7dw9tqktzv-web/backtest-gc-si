# Phase C4bis -- Block Bootstrap + Filtre horaire

*Date: 2026-02-08*
*Script: `scripts/phase_c4bis_block_bootstrap.py`*

---

## Resume executif

**GO** -- Block bootstrap P(perte 100tr) = 19.1%. Sizing recommande: reduit (0.5 unite).

## Block Bootstrap vs i.i.d. (horizon 100 trades)

| Methode | P(perte) | PnL P5 | PnL Median | PnL P95 | MaxDD P5 |
|---------|----------|--------|------------|---------|----------|
| i.i.d. (C4) | 0.9% | $10,911 | $45,395 | $85,997 | $-13,877 |
| Block (k=3) | 9.4% | $-6,672 | $30,022 | $76,697 | $-16,162 |
| Block (k=5) | 19.1% | $-14,610 | $19,946 | $78,383 | $-20,730 |
| Block (k=7) | 25.8% | $-19,442 | $16,766 | $77,271 | $-22,873 |
| Block (k=10) | 37.7% | $-21,996 | $8,450 | $69,459 | $-23,612 |

## Block bootstrap k=5, tous horizons

| Horizon | P(perte) | PnL P5 | PnL Median | PnL P95 |
|---------|----------|--------|------------|---------|
| 50 trades | 29.7% | $-11,576 | $10,476 | $50,594 |
| 100 trades | 19.1% | $-14,610 | $19,946 | $78,383 |
| 150 trades | 11.5% | $-9,047 | $34,436 | $98,580 |
| 200 trades | 8.2% | $-6,439 | $48,732 | $122,120 |

## Filtre horaire

| Mode | Trades | PnL | WR | PF | MaxDD | PnL/Trade |
|------|--------|-----|----|----|-------|-----------|
| A: 24h (baseline) | 100 | $45,224 | 53% | 2.41 | $-17,341 | $452 |
| B: Block 0-9h CT | 61 | $49,461 | 56% | 4.45 | $-4,555 | $811 |
| C: Block 0-8h CT | 64 | $46,237 | 53% | 3.64 | $-6,958 | $722 |

**Verdict filtre horaire: MONITOR**

## Verdict final C4bis

- Block bootstrap: **GO** (P(perte)=19.1%, sizing=reduit (0.5 unite))
- Filtre horaire: **MONITOR**

---
*Rapport genere par `scripts/phase_c4bis_block_bootstrap.py`*