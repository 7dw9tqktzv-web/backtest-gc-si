"""
Grid Search 5-min - zTP etendu (0, -0.5, -1.0)
Compare avec le baseline (zTP=1.0, 1.5, 2.0)

Objectif : Valider que zTP=0 ou zTP=-0.5 ameliore systematiquement le PnL

Parametres :
- Indicateurs : memes que grid search initial (1080 groupes)
- zE : 3.5 uniquement (les autres ne fonctionnent pas)
- co : 40, 50
- zTP : -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0 (7 valeurs)
- zSL : 3.5, 4.0, 5.0 (3 valeurs)

Total : 1080 x (1 x 2 x 7 x 3) = 1080 x 42 = 45,360 configs
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from grid_search_runner import GridSearchRunner

# ============================================================================
# CONFIGURATION DU GRID SEARCH
# ============================================================================

INDICATOR_PARAMS = {
    "beta_lookback": [132, 264, 396, 528, 792, 1320, 2640, 3960, 5280],
    "zscore_period": [10, 15, 20, 30, 50, 60, 80, 100],
    "correlation_period": [15, 30, 50, 60, 80],
    "adf_hurst_period": [26, 64, 128],
}

ZSCORE_ENTRY = 3.5  # Fixe (seul qui fonctionne)
COINTEGRATION_MIN_VALUES = [40, 50]
ZSCORE_TP_VALUES = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]  # Etendu !
ZSCORE_SL_VALUES = [3.5, 4.0, 5.0]

FIXED_OVERRIDES = {
    "exit.zscore_tp_enabled": True,
    "exit.zscore_tp_min_pnl": None,
    "exit.pnl_take_profit": 99999,
    "exit.pnl_stop_loss": -99999,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

NUM_WORKERS = 24
OUTPUT_PATH = Path("output/grid_search_5min_ztp_extended.csv")


# ============================================================================
# GENERATEURS PERSONNALISES
# ============================================================================

def generate_entry_exit_variants():
    """Genere toutes les combinaisons entry/exit avec zTP etendu."""
    variants = []
    for co in COINTEGRATION_MIN_VALUES:
        for zTP in ZSCORE_TP_VALUES:
            for zSL in ZSCORE_SL_VALUES:
                variants.append({
                    "overrides": {
                        "entry.zscore_long": -ZSCORE_ENTRY,
                        "entry.zscore_short": ZSCORE_ENTRY,
                        "entry.cointegration_score_min": co,
                        "exit.zscore_tp_long": -zTP,
                        "exit.zscore_tp_short": zTP,
                        "exit.zscore_sl_long": -zSL,
                        "exit.zscore_sl_short": zSL,
                    },
                    "zE": ZSCORE_ENTRY,
                    "co": co,
                    "zTP": zTP,
                    "zSL": zSL,
                })
    return variants


def build_label(group_prefix, variant):
    """Construit un label unique pour une config."""
    return f"{group_prefix}_zE{variant['zE']}_co{variant['co']}_zTP{variant['zTP']}_zSL{variant['zSL']}"


def build_result(label, ind_ov, ee, m, tp_zscore, tp_dollar, sl_zscore, sl_dollar):
    """Construit le dict resultat."""
    beta = ind_ov.get("indicators.beta_lookback", 0)
    zp = ind_ov.get("indicators.zscore_period", 0)
    cp = ind_ov.get("indicators.correlation_period", 0)
    adf = ind_ov.get("indicators.adf_hurst_period", 0)

    return {
        "label": label,
        "beta": beta, "zp": zp, "cp": cp, "adf": adf,
        "zE": ee["zE"], "co": ee["co"],
        "zTP": ee["zTP"], "zSL": ee["zSL"],
        "trades": m["trades"], "long": m["long"], "short": m["short"],
        "win_rate": round(m["win_rate"], 1),
        "pnl_net": round(m["pnl_net"], 0),
        "pnl_avg": round(m["pnl_avg"], 2),
        "profit_factor": round(m["profit_factor"], 2),
        "max_dd": round(m["max_dd"], 0),
        "sharpe": round(m["sharpe"], 2),
        "tp_zscore": tp_zscore, "tp_dollar": tp_dollar,
        "sl_zscore": sl_zscore, "sl_dollar": sl_dollar,
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    runner = GridSearchRunner(
        indicator_params=INDICATOR_PARAMS,
        entry_exit_generator=generate_entry_exit_variants,
        label_builder=build_label,
        result_builder=build_result,
        fixed_overrides=FIXED_OVERRIDES,
        timeframe="5min",
        title="GRID SEARCH 5-MIN - ZTP ETENDU (-1.0 a +2.0)",
    )

    runner.run(
        num_workers=NUM_WORKERS,
        output_path=str(OUTPUT_PATH),
        min_trades_for_sharpe=10,
    )

    # ========================================================================
    # ANALYSES SPECIFIQUES
    # ========================================================================

    if not OUTPUT_PATH.exists():
        print("[ERREUR] Fichier de resultats non trouve")
        sys.exit(1)

    df_all = pd.read_csv(OUTPUT_PATH, sep=";")

    print(f"\n{'='*130}")
    print("COMPARAISON PAR VALEUR DE ZTP")
    print(f"{'='*130}")
    print(f"{'zTP':>6} | {'Configs':>10} | {'Rentables':>10} | {'%':>6} | {'PnL Moy':>12} | {'PnL Max':>12} | {'Trades Moy':>10}")
    print("-" * 130)

    for ztp in sorted(df_all["zTP"].unique()):
        subset = df_all[df_all["zTP"] == ztp]
        profitable = subset[subset["pnl_net"] > 0]
        pct = len(profitable) / len(subset) * 100 if len(subset) > 0 else 0
        pnl_moy = profitable["pnl_net"].mean() if len(profitable) > 0 else 0
        pnl_max = subset["pnl_net"].max()
        trades_moy = subset["trades"].mean()
        print(f"{ztp:>6} | {len(subset):>10,} | {len(profitable):>10,} | {pct:>5.1f}% | ${pnl_moy:>10,.0f} | ${pnl_max:>10,.0f} | {trades_moy:>10.0f}")

    # ========================================================================
    # COMPARAISON AVEC GRID INITIAL
    # ========================================================================

    initial_path = Path("output/grid_search_5min_phase1.csv")
    if initial_path.exists():
        print(f"\n{'='*130}")
        print("COMPARAISON AVEC LE GRID SEARCH INITIAL (zTP=1.0, 1.5, 2.0)")
        print(f"{'='*130}")

        df_initial = pd.read_csv(initial_path, sep=";")
        if "mode" in df_initial.columns:
            df_initial_pure = df_initial[df_initial["mode"] == "pure_zscore"]
        else:
            df_initial_pure = df_initial

        # Top 10 initial
        top10_initial = df_initial_pure.nlargest(10, "pnl_net")
        print("\nTOP 10 INITIAL (zTP=1.0/1.5/2.0):")
        for i, (_, r) in enumerate(top10_initial.iterrows()):
            ztp_val = r.get('zTP', 'N/A')
            print(f"  {i+1}. zTP={ztp_val} | ${r['pnl_net']:>+10,.0f} | {r['trades']} trades | {r['label']}")

        # Top 10 nouveau
        top10_new = df_all.nlargest(10, "pnl_net")
        print("\nTOP 10 NOUVEAU (zTP etendu):")
        for i, (_, r) in enumerate(top10_new.iterrows()):
            print(f"  {i+1}. zTP={r['zTP']} | ${r['pnl_net']:>+10,.0f} | {r['trades']} trades | {r['label']}")

        # Delta
        best_initial = top10_initial.iloc[0]["pnl_net"]
        best_new = top10_new.iloc[0]["pnl_net"]
        print(f"\nMEILLEUR INITIAL : ${best_initial:>+,.0f}")
        print(f"MEILLEUR NOUVEAU : ${best_new:>+,.0f}")
        print(f"DELTA            : ${best_new - best_initial:>+,.0f} ({(best_new - best_initial) / best_initial * 100:>+.1f}%)")
