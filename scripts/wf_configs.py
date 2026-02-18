"""
Configs candidates pour walk-forward / Monte Carlo.
Cles d'override alignees sur grid_search_runner.py (_generate_micro_full_combos).

Convention signes (identique au grid search L1028-1035) :
  - zscore_long = -abs(zE), zscore_short = +abs(zE)
  - zscore_tp_long = -zTP, zscore_tp_short = +zTP  (PAS de abs!)
  - zscore_sl_long = -abs(zSL), zscore_sl_short = +abs(zSL)
  - pnl_stop_loss = valeur negative

Les valeurs zTP passees ici doivent etre POSITIVES (comme dans le grid YAML).
Le grid search fait -zTP pour long, +zTP pour short.
"""

def _make_overrides(beta, zp, cp, adf, zE, co, zTP, zSL, dTP, dSL, mhb, es, mm=2):
    """Genere les overrides avec les BONNES cles (matching grid_search_runner).

    zTP : valeur positive du grid (ex: 0.25, 0.5, 1.0).
          Applique comme -zTP pour long, +zTP pour short.
    """
    return {
        "indicators.beta_lookback": beta,
        "indicators.zscore_period": zp,
        "indicators.correlation_period": cp,
        "indicators.adf_hurst_period": adf,
        "entry.zscore_long": -abs(zE),
        "entry.zscore_short": abs(zE),
        "entry.cointegration_score_min": co,
        "exit.zscore_tp_long": -zTP,
        "exit.zscore_tp_short": zTP,
        "exit.zscore_sl_long": -abs(zSL),
        "exit.zscore_sl_short": abs(zSL),
        "exit.pnl_take_profit": dTP,
        "exit.pnl_stop_loss": dSL,
        "exit.max_holding_bars": mhb,
        "session.entry_start_hour": es,
        "sizing.micro_multiplier_max": mm,
    }


CONFIGS = [
    {
        "label": "C01_b4620_zE3.6_dTP225_nohold_es22",
        "overrides": _make_overrides(
            beta=4620, zp=28, cp=30, adf=64,
            zE=3.6, co=20, zTP=0.25, zSL=99,
            dTP=225, dSL=-500, mhb=0, es=22,
        ),
    },
    {
        "label": "C02_b4620_zE3.55_dTP250_mhb18_es18",
        "overrides": _make_overrides(
            beta=4620, zp=28, cp=30, adf=64,
            zE=3.55, co=20, zTP=0.5, zSL=99,
            dTP=250, dSL=-500, mhb=18, es=18,
        ),
    },
    {
        "label": "C03_b7920_zE3.45_dTP175_mhb18_es22",
        "overrides": _make_overrides(
            beta=7920, zp=26, cp=30, adf=48,
            zE=3.45, co=20, zTP=1.0, zSL=99,
            dTP=175, dSL=-500, mhb=18, es=22,
        ),
    },
    {
        "label": "C04_b4620_zE3.6_dTP250_nohold_es22",
        "overrides": _make_overrides(
            beta=4620, zp=28, cp=30, adf=64,
            zE=3.6, co=20, zTP=0.25, zSL=99,
            dTP=250, dSL=-500, mhb=0, es=22,
        ),
    },
    {
        "label": "C05_b4620_zE3.6_dTP250_mhb18_es22",
        "overrides": _make_overrides(
            beta=4620, zp=28, cp=30, adf=64,
            zE=3.6, co=20, zTP=0.5, zSL=99,
            dTP=250, dSL=-500, mhb=18, es=22,
        ),
    },
    {
        "label": "C06_b2640_zE3.4_dTP225_nohold_es22",
        "overrides": _make_overrides(
            beta=2640, zp=26, cp=24, adf=32,
            zE=3.4, co=20, zTP=1.5, zSL=99,
            dTP=225, dSL=-500, mhb=0, es=22,
        ),
    },
    {
        "label": "C07_b2640_zE3.4_dTP200_nohold_es22",
        "overrides": _make_overrides(
            beta=2640, zp=26, cp=24, adf=32,
            zE=3.4, co=20, zTP=1.25, zSL=99,
            dTP=200, dSL=-500, mhb=0, es=22,
        ),
    },
    {
        "label": "C08_b2640_zE3.5_dTP225_mhb18_es0",
        "overrides": _make_overrides(
            beta=2640, zp=28, cp=12, adf=96,
            zE=3.5, co=20, zTP=1.25, zSL=99,
            dTP=225, dSL=-500, mhb=18, es=0,
        ),
    },
    {
        "label": "C09_b2640_zE3.4_dTP200_nohold_es0",
        "overrides": _make_overrides(
            beta=2640, zp=28, cp=12, adf=64,
            zE=3.4, co=20, zTP=0.5, zSL=99,
            dTP=200, dSL=-500, mhb=0, es=0,
        ),
    },
    {
        "label": "C10_b2640_zE3.3_dTP200_nohold_es0",
        "overrides": _make_overrides(
            beta=2640, zp=26, cp=20, adf=32,
            zE=3.3, co=20, zTP=1.0, zSL=99,
            dTP=200, dSL=-500, mhb=0, es=0,
        ),
    },
]

# Fixed overrides for all configs (micro, prop firm session)
FIXED = {
    "contracts.mode": "micro",
    "indicators.period": "5min",
    "exit.zscore_tp_enabled": True,
    "session.flat_end_of_session": True,
    "session.entry_end_hour": 14,
    "session.session_end_time": "14:55",
    "costs.slippage_gc_ticks": 2,
    "costs.slippage_si_ticks": 2,
}
