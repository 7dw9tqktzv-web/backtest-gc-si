"""
Grid Search 5-min - Beta longs (15j, 20j, 30j)
Test des lookbacks plus longs avec zTP=0 et zTP=-1.0

Parametres :
- Beta : 3960, 5280, 7920 (15j, 20j, 30j)
- Z-Score periode : 12, 24, 36, 48, 60 (1h-5h)
- Correlation periode : 12, 24, 36, 48, 60 (1h-5h)
- ADF periode : 26, 64, 128
- Entry Z-Score : 2.5, 3.0, 3.5
- Coint min : 40, 50, 60
- TP Z-Score : 0, -1.0
- SL Z-Score : 4.0

Total : 225 groupes x 18 variantes = 4,050 configs
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
    "beta_lookback": [3960, 5280, 7920],
    "zscore_period": [12, 24, 36, 48, 60],
    "correlation_period": [12, 24, 36, 48, 60],
    "adf_hurst_period": [26, 64, 128],
}

ENTRY_ZSCORE_VALUES = [2.5, 3.0, 3.5]
COINTEGRATION_MIN_VALUES = [40, 50, 60]
ZSCORE_TP_VALUES = [0.0, -1.0]
ZSCORE_SL = 4.0

FIXED_OVERRIDES = {
    "exit.zscore_tp_enabled": True,
    "exit.zscore_tp_min_pnl": None,
    "exit.pnl_take_profit": 99999,
    "exit.pnl_stop_loss": -99999,
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}

NUM_WORKERS = 24
OUTPUT_PATH = Path("output/grid_search_beta_long.csv")


# ============================================================================
# GENERATEURS PERSONNALISES
# ============================================================================

def generate_entry_exit_variants():
    """Genere toutes les combinaisons entry/exit."""
    variants = []
    for zE in ENTRY_ZSCORE_VALUES:
        for co in COINTEGRATION_MIN_VALUES:
            for zTP in ZSCORE_TP_VALUES:
                variants.append({
                    "overrides": {
                        "entry.zscore_long": -zE,
                        "entry.zscore_short": zE,
                        "entry.cointegration_score_min": co,
                        "exit.zscore_tp_long": -zTP,
                        "exit.zscore_tp_short": zTP,
                        "exit.zscore_sl_long": -ZSCORE_SL,
                        "exit.zscore_sl_short": ZSCORE_SL,
                    },
                    "zE": zE,
                    "co": co,
                    "zTP": zTP,
                    "zSL": ZSCORE_SL,
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
        "tp_zscore": tp_zscore, "sl_zscore": sl_zscore,
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
        title="GRID SEARCH 5-MIN - BETA LONGS (15j, 20j, 30j)",
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

    print(f"\n{'='*100}")
    print("ANALYSE PAR BETA")
    print(f"{'='*100}")
    for beta in sorted(df_all["beta"].unique()):
        subset = df_all[df_all["beta"] == beta]
        profitable = subset[subset["pnl_net"] > 0]
        pct = len(profitable) / len(subset) * 100
        pnl_max = subset["pnl_net"].max()
        pnl_moy = profitable["pnl_net"].mean() if len(profitable) > 0 else 0
        days = beta / 264
        print(f"  beta={beta:>4} ({days:>4.0f}j) | {len(profitable):>4}/{len(subset):>4} rentables ({pct:>5.1f}%) | "
              f"PnL max=${pnl_max:>+10,.0f} | PnL moy=${pnl_moy:>+8,.0f}")

    print(f"\n{'='*100}")
    print("ANALYSE PAR ENTRY Z-SCORE")
    print(f"{'='*100}")
    for zE in sorted(df_all["zE"].unique()):
        subset = df_all[df_all["zE"] == zE]
        profitable = subset[subset["pnl_net"] > 0]
        pct = len(profitable) / len(subset) * 100
        pnl_max = subset["pnl_net"].max()
        print(f"  zE={zE:>3} | {len(profitable):>4}/{len(subset):>4} rentables ({pct:>5.1f}%) | PnL max=${pnl_max:>+10,.0f}")

    print(f"\n{'='*100}")
    print("ANALYSE PAR TP Z-SCORE")
    print(f"{'='*100}")
    for zTP in sorted(df_all["zTP"].unique()):
        subset = df_all[df_all["zTP"] == zTP]
        profitable = subset[subset["pnl_net"] > 0]
        pct = len(profitable) / len(subset) * 100
        pnl_max = subset["pnl_net"].max()
        print(f"  zTP={zTP:>4} | {len(profitable):>4}/{len(subset):>4} rentables ({pct:>5.1f}%) | PnL max=${pnl_max:>+10,.0f}")
