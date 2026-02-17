#!/usr/bin/env python
"""
PnL Decay barre par barre pour 5 configs R1.
Calcule le PnL non-realise a chaque barre apres entree, agregé sur tous les trades.

Usage:
    python scripts/pnl_decay_r1.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_loader import load_and_prepare_data, load_5s_data, resample_to_5min
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest, warmup_numba
from optimizer import apply_overrides_fast

OUTPUT = Path("output/grid_searches/r1_corrected/r1_pnl_decay.txt")

CONFIGS = [
    {"name": "C1", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -500, "mhb": 0},
    {"name": "C6", "beta": 4620, "zp": 30, "cp": 36, "adf": 64,
     "zE": 3.75, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -500, "mhb": 0},
    {"name": "C9", "beta": 2640, "zp": 30, "cp": 12, "adf": 26,
     "zE": 3.5, "co": 20, "zTP": -0.5, "dTP": 250, "dSL": -1000, "mhb": 0},
    {"name": "C2", "beta": 4620, "zp": 30, "cp": 30, "adf": 64,
     "zE": 3.5, "co": 20, "zTP": 0.0, "dTP": 250, "dSL": -600, "mhb": 0},
    {"name": "C5", "beta": 1980, "zp": 20, "cp": 20, "adf": 48,
     "zE": 3.25, "co": 30, "zTP": -1.5, "dTP": 250, "dSL": -500, "mhb": 0},
]

FIXED = {
    "contracts.mode": "micro",
    "exit.zscore_tp_enabled": True,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
    "session.session_end_time": "14:55",
    "session.entry_start_hour": 18,
    "session.entry_end_hour": 14,
    "session.flat_end_of_session": True,
}

MAX_BARS = 264  # 1 jour complet en 5-min


def build_overrides(cfg):
    return {
        "indicators.beta_lookback": cfg["beta"],
        "indicators.zscore_period": cfg["zp"],
        "indicators.correlation_period": cfg["cp"],
        "indicators.adf_hurst_period": cfg["adf"],
        "entry.zscore_long": -cfg["zE"],
        "entry.zscore_short": cfg["zE"],
        "entry.cointegration_score_min": cfg["co"],
        "exit.zscore_tp_long": -cfg["zTP"],
        "exit.zscore_tp_short": cfg["zTP"],
        "exit.zscore_sl_long": -99.0,
        "exit.zscore_sl_short": 99.0,
        "exit.pnl_take_profit": cfg["dTP"],
        "exit.pnl_stop_loss": cfg["dSL"],
        "exit.max_holding_bars": cfg["mhb"],
        "contracts.micro_multiplier_max": 2,
        **FIXED,
    }


def compute_pnl_decay(trades_df, df_5min, gc_pv, si_pv):
    """Pour chaque trade, calcule le PnL non-realise barre par barre."""
    # Build datetime -> row index lookup from DateTime column
    dt_series = pd.to_datetime(df_5min["DateTime"])
    dt_to_idx = {dt: i for i, dt in enumerate(dt_series)}

    gc_close = df_5min["Last_GC"].values
    si_close = df_5min["Last_SI"].values

    # Collect per-bar unrealized PnL for all trades
    # decay[bar_offset] = list of unrealized PnL values
    decay = {i: [] for i in range(1, MAX_BARS + 1)}

    n_mapped = 0
    for _, trade in trades_df.iterrows():
        entry_dt = pd.Timestamp(trade["Entry_DateTime"])
        exit_dt = pd.Timestamp(trade["Exit_DateTime"])

        entry_idx = dt_to_idx.get(entry_dt)
        exit_idx = dt_to_idx.get(exit_dt)
        if entry_idx is None or exit_idx is None:
            continue

        n_mapped += 1
        direction = 1 if trade["Direction"] == "LONG" else -1
        entry_gc = trade["Entry_GC"]
        entry_si = trade["Entry_SI"]
        gc_c = trade["GC_Contracts"]
        si_c = trade["SI_Contracts"]

        n_bars_held = exit_idx - entry_idx
        if n_bars_held <= 0:
            continue

        for offset in range(1, min(n_bars_held, MAX_BARS) + 1):
            idx = entry_idx + offset
            cur_gc = gc_close[idx]
            cur_si = si_close[idx]

            if direction == 1:
                pnl = ((entry_gc - cur_gc) * gc_pv * gc_c
                       + (cur_si - entry_si) * si_pv * si_c)
            else:
                pnl = ((cur_gc - entry_gc) * gc_pv * gc_c
                       + (entry_si - cur_si) * si_pv * si_c)

            decay[offset].append(pnl)

    return decay, n_mapped


def find_inflection(avgs):
    """Trouve la premiere barre ou pnl_avg decroit 3 barres consecutives."""
    offsets = sorted(avgs.keys())
    for i in range(len(offsets) - 3):
        b0, b1, b2, b3 = offsets[i], offsets[i+1], offsets[i+2], offsets[i+3]
        if (avgs[b1] < avgs[b0] and avgs[b2] < avgs[b1] and avgs[b3] < avgs[b2]):
            return b0
    return None


def find_zero_crossing(avgs):
    """Trouve la premiere barre ou pnl_avg passe sous 0."""
    for offset in sorted(avgs.keys()):
        if avgs[offset] < 0:
            return offset
    return None


def format_decay_table(decay, lines):
    """Formate le tableau de decay."""
    avgs = {}
    # Compute stats for all bars
    for offset in range(1, MAX_BARS + 1):
        vals = decay.get(offset, [])
        if len(vals) < 3:
            break
        avgs[offset] = np.mean(vals)

    # Header
    lines.append("  {:>6} {:>10} {:>10} {:>10} {:>10}".format(
        "Bar", "Open", "PnL Avg", "PnL Med", "% Pos"))
    lines.append("  " + "-" * 55)

    # Display logic: bars 1-60 all, then every 12 until 264
    display_bars = list(range(1, 61))
    display_bars += list(range(72, MAX_BARS + 1, 12))

    last_displayed_offset = 0
    for offset in display_bars:
        vals = decay.get(offset, [])
        if len(vals) < 3:
            continue
        n = len(vals)
        avg = np.mean(vals)
        med = np.median(vals)
        pct_pos = 100.0 * np.sum(np.array(vals) > 0) / n
        lines.append("  {:>6} {:>10} {:>10.1f} {:>10.1f} {:>9.1f}%".format(
            offset, n, avg, med, pct_pos))
        last_displayed_offset = offset

    # Inflection and zero crossing
    inflection = find_inflection(avgs)
    zero_cross = find_zero_crossing(avgs)

    lines.append("")
    if inflection:
        lines.append(f"  POINT D'INFLEXION : barre {inflection} (={inflection*5} min)")
    else:
        lines.append("  POINT D'INFLEXION : non trouve (PnL monte ou fluctue)")
    if zero_cross:
        lines.append(f"  ZERO CROSSING     : barre {zero_cross} (={zero_cross*5} min)")
    else:
        lines.append("  ZERO CROSSING     : jamais (PnL reste positif)")

    return avgs, inflection, zero_cross


def main():
    t0 = time.time()
    print("Chargement des donnees...")
    import yaml
    config_path = "config/strategy_params.yaml"
    with open(config_path, "r") as f:
        base_config = yaml.safe_load(f)

    df_1min, _, _ = load_and_prepare_data(config_path)
    df_5s = load_5s_data(base_config)
    print(f"  {len(df_1min):,} barres 1-min, {len(df_5s):,} barres 5s ({time.time()-t0:.1f}s)")

    warmup_numba()
    print("[OK] Numba warmup done")

    # Get point values from micro config
    gc_pv = 10.0   # MGC point value
    si_pv = 1000.0  # SIL point value

    lines = []
    lines.append("=" * 80)
    lines.append("PNL DECAY BARRE PAR BARRE -- 5 CONFIGS R1")
    lines.append(f"Date : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("PnL = non-realise brut (avant costs) a chaque barre apres entree")
    lines.append("=" * 80)

    summaries = []

    for ci, cfg in enumerate(CONFIGS):
        print(f"\n[{ci+1}/{len(CONFIGS)}] {cfg['name']}...")

        overrides = build_overrides(cfg)
        config = apply_overrides_fast(base_config, overrides)

        # Calculate indicators on 5-min data
        df_5min = resample_to_5min(df_1min)
        df_5min = calculate_all_indicators(df_5min, config)

        trades_df = run_hybrid_backtest(df_5min, df_5s, config, verbose=False)
        n_trades = len(trades_df)
        print(f"  {n_trades} trades")

        if n_trades == 0:
            lines.append(f"\nCONFIG: {cfg['name']} — AUCUN TRADE")
            continue

        # Filter out trades with duration 0 (instant exits on same bar)
        trades_with_duration = trades_df[trades_df["Duration_Min"] > 0]
        print(f"  {len(trades_with_duration)} trades avec duree > 0 (exclu {n_trades - len(trades_with_duration)} instant)")

        decay, n_mapped = compute_pnl_decay(trades_with_duration, df_5min, gc_pv, si_pv)
        print(f"  {n_mapped} trades mappes sur le DataFrame")

        lines.append("")
        lines.append("=" * 80)
        lines.append(f"CONFIG: {cfg['name']}")
        lines.append(f"  beta={cfg['beta']} zp={cfg['zp']} cp={cfg['cp']} adf={cfg['adf']} "
                     f"zE={cfg['zE']} co={cfg['co']} zTP={cfg['zTP']} dTP={cfg['dTP']} "
                     f"dSL={cfg['dSL']} mhb={cfg['mhb']} mm=2")
        lines.append(f"  Trades total: {n_trades}, Trades avec duree>0: {len(trades_with_duration)}, "
                     f"Mappes: {n_mapped}")
        lines.append("=" * 80)
        lines.append("")

        avgs, inflection, zero_cross = format_decay_table(decay, lines)

        # Collect summary data
        summary = {"name": cfg["name"], "inflection": inflection, "zero_cross": zero_cross}
        for b in [6, 12, 18, 24, 36, 48]:
            vals = decay.get(b, [])
            summary[f"avg_{b}"] = np.mean(vals) if len(vals) >= 3 else None
            summary[f"n_{b}"] = len(vals)
        summaries.append(summary)

    # === SYNTHESE ===
    lines.append("")
    lines.append("=" * 80)
    lines.append("SYNTHESE COMPARATIVE")
    lines.append("=" * 80)
    lines.append("")

    # Table header
    hdr = "{:<6} {:>12} {:>12} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
        "Config", "Inflexion", "Zero Cross",
        "Avg @6", "Avg @12", "Avg @18", "Avg @24", "Avg @36", "Avg @48")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for s in summaries:
        infl = f"bar {s['inflection']}" if s['inflection'] else "N/A"
        zc = f"bar {s['zero_cross']}" if s['zero_cross'] else "jamais"
        vals = []
        for b in [6, 12, 18, 24, 36, 48]:
            v = s.get(f"avg_{b}")
            if v is not None:
                vals.append(f"${v:+.0f}")
            else:
                vals.append("N/A")
        lines.append("{:<6} {:>12} {:>12} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
            s["name"], infl, zc, *vals))

    # Recommendation
    lines.append("")
    lines.append("RECOMMANDATION MHB :")
    lines.append("-" * 40)

    best_infl = None
    for s in summaries:
        if s["inflection"] is not None:
            if best_infl is None or s["inflection"] < best_infl:
                best_infl = s["inflection"]

    if best_infl:
        lines.append(f"  Point d'inflexion le plus precoce : barre {best_infl} ({best_infl*5} min)")
        lines.append(f"  MHB suggere : {best_infl} barres (coupe avant que le PnL ne se degrade)")
        lines.append(f"  A tester en R2 : mhb = {max(6, best_infl - 6)}, {best_infl}, {best_infl + 6}, {best_infl + 12}")
    else:
        lines.append("  Aucun point d'inflexion clair trouve.")
        lines.append("  Les trades restent en moyenne positifs -> mhb = 0 (pas de limite)")

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nTermine en {time.time()-t0:.1f}s")
    print(f"Output : {OUTPUT}")


if __name__ == "__main__":
    main()
