"""
Phase 1 - Walk-Forward individuel sur 10 configs candidates.

Rolling cumulatif : train sur fenetres 1..N, test sur fenetre N+1.
6 fenetres de ~6 mois, 5 tests OOS.
Elimination : PnL OOS negatif sur 3+ fenetres.

Usage:
    python scripts/run_wf_phase1.py
"""
import sys
import time
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from optimizer import apply_overrides, compute_metrics
from walk_forward_runner import slice_data, slice_5s


# ============================================================================
# 10 CONFIGS CANDIDATES
# ============================================================================
from wf_configs import CONFIGS, FIXED


# ============================================================================
# WALK-FORWARD WINDOWS (6 x ~6 months, rolling cumulative)
# ============================================================================
# Data: 2023-01-26 to 2026-01-30 (~3 years)
# 6 windows of ~6 months each
WINDOW_BOUNDARIES = [
    date(2023, 1, 26),   # W1 start
    date(2023, 7, 26),   # W2 start
    date(2024, 1, 26),   # W3 start
    date(2024, 7, 26),   # W4 start
    date(2025, 1, 26),   # W5 start
    date(2025, 7, 26),   # W6 start
    date(2026, 1, 30),   # W6 end
]

WARMUP_BARS = 8000  # beta 7920 needs ~8000 bars warmup


def main():
    t_start = time.time()
    print("=" * 120)
    print("PHASE 1 - WALK-FORWARD INDIVIDUEL (10 configs, 5 tests OOS)")
    print("Rolling cumulatif : train W1..N, test W(N+1)")
    print("=" * 120)

    # --- Load data ---
    print("\n[1/3] Chargement des donnees...")
    df_1min, base_config, _ = load_and_prepare_data(verbose=False)
    df_5min = resample_to_5min(df_1min, verbose=False)
    df_5s = load_5s_data(base_config, verbose=False)
    print(f"   {len(df_5min):,} barres 5-min | {len(df_5s):,} barres 5s")

    # --- Build OOS windows ---
    print("\n[2/3] Fenetres OOS :")
    oos_windows = []
    for i in range(5):  # 5 OOS tests
        train_start = WINDOW_BOUNDARIES[0]
        train_end = WINDOW_BOUNDARIES[i + 1]  # cumulative train
        test_start = WINDOW_BOUNDARIES[i + 1]
        test_end = WINDOW_BOUNDARIES[i + 2]
        oos_windows.append({
            "train_start": train_start, "train_end": train_end,
            "test_start": test_start, "test_end": test_end,
        })
        print(f"   OOS {i+1}: Train {train_start} -> {train_end} | Test {test_start} -> {test_end}")

    # --- Run walk-forward ---
    print(f"\n[3/3] Execution (10 configs x 5 fenetres = 50 backtests)...")

    # Results matrix: config x window
    results = {}  # {label: [pnl_w1, pnl_w2, ..., pnl_w5]}
    details = {}  # {label: [{trades, pnl, dd, pf, wr, eod}, ...]}

    for c_idx, cfg_def in enumerate(CONFIGS):
        label = cfg_def["label"]
        overrides = {**cfg_def["overrides"], **FIXED}
        config = apply_overrides(base_config, overrides)

        results[label] = []
        details[label] = []

        for w_idx, window in enumerate(oos_windows):
            # Slice TEST data (with warmup for indicators)
            df_test = slice_data(df_5min, window["test_start"], window["test_end"],
                                 include_warmup=True, warmup_bars=WARMUP_BARS)
            df_5s_test = slice_5s(df_5s, window["test_start"], window["test_end"])

            # Calculate indicators and run backtest
            df_with_ind = calculate_all_indicators(df_test, config, verbose=False)
            trades_df = run_hybrid_backtest(df_with_ind, df_5s_test, config, verbose=False)
            m = compute_metrics(trades_df)

            results[label].append(m["pnl_net"])
            eod_count = len(trades_df[trades_df["Exit_Reason"] == "FLAT_EOD"]) if trades_df is not None and len(trades_df) > 0 else 0
            details[label].append({
                "trades": m["trades"], "pnl": m["pnl_net"], "dd": m["max_dd"],
                "pf": m["profit_factor"], "wr": m["win_rate"],
                "eod": eod_count,
            })

            status = "+" if m["pnl_net"] > 0 else "-"
            print(f"   [{c_idx+1:>2}/10] {label[:35]:<35} OOS {w_idx+1}: {m['trades']:3d} trades, ${m['pnl_net']:>+7,.0f} [{status}]")

    # --- Print results ---
    elapsed = time.time() - t_start
    print(f"\n{'='*120}")
    print(f"RESULTATS PHASE 1 ({elapsed/60:.1f} min)")
    print(f"{'='*120}")

    # Header
    print(f"\n{'Config':<38} ", end="")
    for i in range(5):
        print(f"{'OOS'+str(i+1):>10}", end="")
    print(f" {'TOTAL':>10} {'POS':>4} {'VERDICT':>10}")
    print("-" * 120)

    survivors = []
    for label in [c["label"] for c in CONFIGS]:
        pnls = results[label]
        total = sum(pnls)
        positive = sum(1 for p in pnls if p > 0)
        verdict = "PASS" if positive >= 3 else "FAIL"

        print(f"{label:<38} ", end="")
        for p in pnls:
            marker = "+" if p > 0 else " "
            print(f" ${p:>+7,.0f}{marker}", end="")
        print(f"  ${total:>+8,.0f} {positive:>3}/5  {verdict:>8}")

        if verdict == "PASS":
            survivors.append(label)

    # Detailed stats per config
    print(f"\n\n{'='*120}")
    print("DETAIL PAR CONFIG (OOS seulement)")
    print(f"{'='*120}")
    print(f"{'Config':<38} {'Trades':>7} {'PnL':>9} {'DD':>8} {'PF':>6} {'WR%':>6} {'EOD':>5}")
    print("-" * 80)

    for label in [c["label"] for c in CONFIGS]:
        d = details[label]
        tot_trades = sum(x["trades"] for x in d)
        tot_pnl = sum(x["pnl"] for x in d)
        worst_dd = min(x["dd"] for x in d)
        avg_pf = np.mean([x["pf"] for x in d if x["pf"] > 0]) if any(x["pf"] > 0 for x in d) else 0
        avg_wr = np.mean([x["wr"] for x in d])
        tot_eod = sum(x["eod"] for x in d)
        marker = " <<< PASS" if label in survivors else ""
        print(f"{label:<38} {tot_trades:>7} ${tot_pnl:>+8,.0f} ${worst_dd:>+7,.0f} {avg_pf:>5.2f} {avg_wr:>5.1f}% {tot_eod:>5}{marker}")

    print(f"\n{'='*120}")
    print(f"SURVIVANTS : {len(survivors)}/10")
    for s in survivors:
        print(f"   {s}")
    print(f"{'='*120}")

    # Save results to CSV
    rows = []
    for label in [c["label"] for c in CONFIGS]:
        for w_idx, d in enumerate(details[label]):
            rows.append({
                "config": label, "oos_window": w_idx + 1,
                "test_start": str(oos_windows[w_idx]["test_start"]),
                "test_end": str(oos_windows[w_idx]["test_end"]),
                **d,
            })
    out_path = Path("output/reports/wf_phase1_results.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, sep=";", index=False)
    print(f"\nResultats sauvegardes dans {out_path}")


if __name__ == "__main__":
    main()
