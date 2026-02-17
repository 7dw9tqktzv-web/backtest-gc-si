#!/usr/bin/env python
"""
Filtre les resultats du grid search R1 (295M lignes, 56 Go).
Lit en chunks pour ne pas saturer la memoire.

Usage:
    python scripts/filter_r1_results.py
"""

import sys
import time
from pathlib import Path

import pandas as pd

INPUT = Path("output/grid_searches/r1_corrected/grid_micro_r1_corrected.csv")
OUTPUT = Path("output/grid_searches/r1_corrected/r1_survivors.csv")
CHUNKSIZE = 500_000

# Filtres de survie
MIN_TRADES = 150
MAX_DD_LIMIT = -3000  # max_dd >= -3000 (prop firm)
MIN_PF = 1.2


def main():
    if not INPUT.exists():
        print(f"[ERREUR] Fichier introuvable : {INPUT}")
        sys.exit(1)

    print(f"Input  : {INPUT}")
    print(f"Output : {OUTPUT}")
    print(f"Filtres : trades >= {MIN_TRADES}, max_dd >= {MAX_DD_LIMIT}, PF >= {MIN_PF}")
    print(f"Chunk  : {CHUNKSIZE:,} lignes")
    print()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    total_rows = 0
    survivors = 0
    header_written = False

    reader = pd.read_csv(INPUT, sep=";", chunksize=CHUNKSIZE)

    for i, chunk in enumerate(reader):
        total_rows += len(chunk)

        mask = (
            (chunk["trades"] >= MIN_TRADES)
            & (chunk["max_dd"] >= MAX_DD_LIMIT)
            & (chunk["profit_factor"] >= MIN_PF)
        )
        filtered = chunk[mask]
        survivors += len(filtered)

        if len(filtered) > 0:
            if not header_written:
                filtered.to_csv(OUTPUT, index=False, sep=";", mode="w")
                header_written = True
            else:
                filtered.to_csv(OUTPUT, index=False, sep=";", mode="a", header=False)

        elapsed = time.time() - t0
        rate = total_rows / elapsed if elapsed > 0 else 0
        print(
            f"  Chunk {i+1:>4} | {total_rows:>12,} lues | "
            f"{survivors:>8,} survivantes | "
            f"{elapsed:.0f}s ({rate/1e6:.1f}M/s)",
            flush=True,
        )

    t_total = time.time() - t0
    pct = 100.0 * survivors / total_rows if total_rows > 0 else 0

    print()
    print("=" * 70)
    print(f"Total configs lues  : {total_rows:>15,}")
    print(f"Survivantes         : {survivors:>15,} ({pct:.2f}%)")
    print(f"Filtrees            : {total_rows - survivors:>15,} ({100-pct:.2f}%)")
    print(f"Temps               : {t_total:.0f}s ({t_total/60:.1f}min)")
    if OUTPUT.exists():
        size_mb = OUTPUT.stat().st_size / 1e6
        print(f"Fichier sortie      : {OUTPUT} ({size_mb:.1f} Mo)")
    print("=" * 70)


if __name__ == "__main__":
    main()
