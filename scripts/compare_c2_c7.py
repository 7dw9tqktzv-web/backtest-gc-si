"""
Compare C2 (b3960, 181 trades, stable) vs C7-Sniper (b1980, 52 trades, unstable).
Identifier les trades supplementaires et comprendre pourquoi C2 est stable.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from optimizer import apply_overrides
from backtest_engine_numba import run_hybrid_backtest

C2_OVERRIDES = {
    "indicators.beta_lookback": 3960, "indicators.zscore_period": 36,
    "indicators.correlation_period": 30, "indicators.adf_hurst_period": 128,
    "entry.zscore_long": -3.25, "entry.zscore_short": 3.25,
    "entry.cointegration_score_min": 50,
    "exit.zscore_tp_long": 0.0, "exit.zscore_tp_short": 0.0,
    "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
    "exit.pnl_take_profit": 300, "exit.pnl_stop_loss": -99999,
    "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
    "session.flat_end_of_session": True,
    "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
    "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
}

C7_OVERRIDES = {
    "indicators.beta_lookback": 1980, "indicators.zscore_period": 24,
    "indicators.correlation_period": 30, "indicators.adf_hurst_period": 96,
    "entry.zscore_long": -3.5, "entry.zscore_short": 3.5,
    "entry.cointegration_score_min": 50,
    "exit.zscore_tp_long": 1.5, "exit.zscore_tp_short": -1.5,
    "exit.zscore_sl_long": -99, "exit.zscore_sl_short": 99,
    "exit.pnl_take_profit": 500, "exit.pnl_stop_loss": -99999,
    "exit.zscore_tp_enabled": True, "exit.max_holding_bars": 0,
    "session.flat_end_of_session": True,
    "contracts.mode": "micro", "sizing.micro_multiplier_max": 2,
    "costs.slippage_gc_ticks": 1, "costs.slippage_si_ticks": 1,
}


def run_bt(config_base, overrides, df_1min, df_5s):
    cfg = apply_overrides(config_base, overrides)
    df_5min = resample_to_5min(df_1min)
    df_ind = calculate_all_indicators(df_5min, cfg)
    return run_hybrid_backtest(df_ind, df_5s, cfg, verbose=False), df_ind


if __name__ == "__main__":
    print("=" * 80)
    print("COMPARE C2 (b3960, stable) vs C7 (b1980, unstable)")
    print("=" * 80)

    # Charger donnees
    print("\nChargement des donnees...")
    df_1min, config_base, _ = load_and_prepare_data("config/strategy_params.yaml")
    df_5s = load_5s_data(config_base)

    # Backtests
    print("\n[1/2] C2 (b3960_zp36_cp30_adf128_zE3.25_co50)...")
    trades_c2, df_ind_c2 = run_bt(config_base, C2_OVERRIDES, df_1min, df_5s)
    print(f"  -> {len(trades_c2)} trades")

    print("\n[2/2] C7 (b1980_zp24_cp30_adf96_zE3.5_co50)...")
    trades_c7, df_ind_c7 = run_bt(config_base, C7_OVERRIDES, df_1min, df_5s)
    print(f"  -> {len(trades_c7)} trades")

    # Convertir les dates
    trades_c2["entry_dt"] = pd.to_datetime(trades_c2["Entry_DateTime"])
    trades_c7["entry_dt"] = pd.to_datetime(trades_c7["Entry_DateTime"])
    trades_c2["entry_date"] = trades_c2["entry_dt"].dt.date
    trades_c7["entry_date"] = trades_c7["entry_dt"].dt.date
    trades_c2["year"] = trades_c2["entry_dt"].dt.year
    trades_c7["year"] = trades_c7["entry_dt"].dt.year

    # ======================================================================
    # 1. Trades uniques a C2 (pas dans C7)
    # ======================================================================
    print("\n" + "=" * 80)
    print("1. TRADES UNIQUES A C2 (absents de C7)")
    print("=" * 80)

    # Matcher par date d'entree (meme jour = meme opportunite)
    c7_dates = set(trades_c7["entry_date"])
    c2_only_mask = ~trades_c2["entry_date"].isin(c7_dates)
    c2_shared_mask = trades_c2["entry_date"].isin(c7_dates)

    c2_only = trades_c2[c2_only_mask].copy()
    c2_shared = trades_c2[c2_shared_mask].copy()

    print(f"\n  C2 total: {len(trades_c2)} trades")
    print(f"  C7 total: {len(trades_c7)} trades")
    print(f"  Trades partages (meme jour): {len(c2_shared)}")
    print(f"  Trades uniques a C2: {len(c2_only)}")

    # PnL des trades uniques
    print(f"\n  PnL des trades uniques a C2: ${c2_only['PnL_Net'].sum():,.0f}")
    print(f"  PnL moyen: ${c2_only['PnL_Net'].mean():,.1f}")
    print(f"  WR: {(c2_only['PnL_Net'] > 0).mean()*100:.1f}%")

    # Par annee
    print("\n  Par annee:")
    for y in sorted(c2_only["year"].unique()):
        sub = c2_only[c2_only["year"] == y]
        print(f"    {y}: {len(sub)} trades, PnL ${sub['PnL_Net'].sum():,.0f}, "
              f"WR {(sub['PnL_Net'] > 0).mean()*100:.1f}%, avg ${sub['PnL_Net'].mean():,.1f}")

    # Par exit type
    print("\n  Par exit type (trades uniques C2):")
    for et in c2_only["Exit_Reason"].value_counts().index:
        sub = c2_only[c2_only["Exit_Reason"] == et]
        print(f"    {et}: {len(sub)} trades, PnL avg ${sub['PnL_Net'].mean():,.1f}, "
              f"total ${sub['PnL_Net'].sum():,.0f}")

    # ======================================================================
    # 2. Trades partages — meme jour, resultats differents?
    # ======================================================================
    print("\n" + "=" * 80)
    print("2. TRADES PARTAGES (meme jour) - C2 vs C7")
    print("=" * 80)

    print(f"\n  PnL partages C2: ${c2_shared['PnL_Net'].sum():,.0f} ({len(c2_shared)} trades)")

    # Trouver les trades C7 sur les memes jours
    c7_shared = trades_c7[trades_c7["entry_date"].isin(set(c2_shared["entry_date"]))].copy()
    print(f"  PnL partages C7: ${c7_shared['PnL_Net'].sum():,.0f} ({len(c7_shared)} trades)")

    # ======================================================================
    # 3. Analyse des indicateurs a l'entree
    # ======================================================================
    print("\n" + "=" * 80)
    print("3. Z-SCORE A L'ENTREE")
    print("=" * 80)

    print(f"\n  C2 (zE=3.25): Z-Score entree moyen = {trades_c2['Entry_ZScore'].mean():.2f}, "
          f"median = {trades_c2['Entry_ZScore'].median():.2f}")
    print(f"  C7 (zE=3.5):  Z-Score entree moyen = {trades_c7['Entry_ZScore'].mean():.2f}, "
          f"median = {trades_c7['Entry_ZScore'].median():.2f}")

    # Z-Score des trades uniques a C2
    print(f"\n  Trades uniques C2: Z-Score entree moyen = {c2_only['Entry_ZScore'].mean():.2f}")
    print(f"  -> Ce sont des trades entre |3.25| et |3.5| que C7 ne prend pas")

    # Distribution Z-Score entree des uniques
    zs = c2_only["Entry_ZScore"].abs()
    print(f"\n  Distribution |Z-Score| entree (trades uniques C2):")
    print(f"    min={zs.min():.2f}  P25={zs.quantile(0.25):.2f}  "
          f"median={zs.median():.2f}  P75={zs.quantile(0.75):.2f}  max={zs.max():.2f}")

    # ======================================================================
    # 4. Effet du beta sur la stabilite
    # ======================================================================
    print("\n" + "=" * 80)
    print("4. EFFET DU BETA SUR LE SPREAD")
    print("=" * 80)

    # Comparer la volatilite du Z-Score entre les deux configs
    zs_c2 = df_ind_c2["ZScore"].dropna()
    zs_c7 = df_ind_c7["ZScore"].dropna()

    print(f"\n  Z-Score stats (sur toutes les barres 5-min):")
    print(f"  C2 (beta=3960): mean={zs_c2.mean():.3f}, std={zs_c2.std():.3f}, "
          f"barres |Z|>3.25 = {(zs_c2.abs() > 3.25).sum()}")
    print(f"  C7 (beta=1980): mean={zs_c7.mean():.3f}, std={zs_c7.std():.3f}, "
          f"barres |Z|>3.5 = {(zs_c7.abs() > 3.5).sum()}")
    print(f"  C7 avec seuil 3.25: barres |Z|>3.25 = {(zs_c7.abs() > 3.25).sum()}")

    # Croisements par annee
    print(f"\n  Barres avec |Z| > seuil par annee:")
    zs_c2_ts = df_ind_c2[["ZScore"]].copy()
    zs_c7_ts = df_ind_c7[["ZScore"]].copy()
    zs_c2_ts["year"] = zs_c2_ts.index.year
    zs_c7_ts["year"] = zs_c7_ts.index.year

    print(f"  {'Annee':>6}  {'C2 |Z|>3.25':>12}  {'C7 |Z|>3.5':>12}  {'C7 |Z|>3.25':>13}")
    for y in [2023, 2024, 2025, 2026]:
        c2_yr = zs_c2_ts[zs_c2_ts["year"] == y]["ZScore"]
        c7_yr = zs_c7_ts[zs_c7_ts["year"] == y]["ZScore"]
        c2_count = (c2_yr.abs() > 3.25).sum()
        c7_count_35 = (c7_yr.abs() > 3.5).sum()
        c7_count_325 = (c7_yr.abs() > 3.25).sum()
        print(f"  {y:>6}  {c2_count:>12}  {c7_count_35:>12}  {c7_count_325:>13}")

    # ======================================================================
    # 5. Duree des trades et sortie
    # ======================================================================
    print("\n" + "=" * 80)
    print("5. DUREE DES TRADES")
    print("=" * 80)

    # Duree pre-calculee par le moteur (Duration_Min)
    dur_c2 = trades_c2["Duration_Min"]
    dur_c7 = trades_c7["Duration_Min"]

    print(f"\n  C2: duree moyenne {dur_c2.mean():.0f} min, median {dur_c2.median():.0f} min")
    print(f"  C7: duree moyenne {dur_c7.mean():.0f} min, median {dur_c7.median():.0f} min")

    # Par exit type
    for label, df in [("C2", trades_c2), ("C7", trades_c7)]:
        print(f"\n  {label} duree par exit type:")
        for et in df["Exit_Reason"].unique():
            sub = df[(df["Exit_Reason"] == et) & (df["Duration_Min"] > 0)]
            if len(sub) > 0:
                print(f"    {et}: {sub['Duration_Min'].mean():.0f} min (median {sub['Duration_Min'].median():.0f})")

    # ======================================================================
    # 6. Synthese
    # ======================================================================
    print("\n" + "=" * 80)
    print("6. SYNTHESE")
    print("=" * 80)

    c2_only_rentable = c2_only["PnL_Net"].sum() > 0
    print(f"""
  C2 prend {len(c2_only)} trades de plus que C7.
  Ces trades uniques sont {'RENTABLES' if c2_only_rentable else 'PERDANTS'}: ${c2_only['PnL_Net'].sum():,.0f} total.

  Deux facteurs expliquent la difference:

  a) zE=3.25 vs 3.5 : C2 entre sur des Z-Scores entre |3.25| et |3.5|
     que C7 ignore. Ces trades "marginaux" sont-ils du signal ou du bruit?
     -> PnL moyen: ${c2_only['PnL_Net'].mean():,.1f}, WR: {(c2_only['PnL_Net'] > 0).mean()*100:.1f}%

  b) beta=3960 vs 1980 : Le spread C2 est plus lisse (std Z={zs_c2.std():.3f})
     vs C7 (std Z={zs_c7.std():.3f}). Un Z-Score de 3.25 sur beta long
     represente un ecart plus "reel" qu'un 3.5 sur beta court.
""")

    print("[OK] Analyse terminee")
