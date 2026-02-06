# ============================================================================
# TEST_BACKTEST_ENGINE_HYBRID.PY - Tests du moteur de backtest hybride
# ============================================================================
#
# Tests de la fonction run_hybrid_backtest() avec donnees synthetiques.
# Chaque test utilise des DataFrames minimaux avec ZScore controle
# pour verifier un comportement precis du moteur.
#
# ============================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from backtest_engine_hybrid import run_hybrid_backtest


# ============================================================================
# HELPERS : construction de DataFrames synthetiques
# ============================================================================

def _make_1min(n, zscores, gc_prices=None, si_prices=None,
               correlation=0.85, coint_score=70, beta=1.0, hurst=0.35,
               start_dt=None):
    """
    Construit un df_1min minimal pour les tests.

    Args:
        n: nombre de barres
        zscores: liste de n valeurs ZScore (peut contenir np.nan)
        gc_prices: prix GC (defaut: 2800.0 constant)
        si_prices: prix SI (defaut: 32.0 constant)
    """
    if start_dt is None:
        start_dt = datetime(2026, 1, 5, 18, 0, 0)  # Lundi 18h CT
    dts = [start_dt + timedelta(minutes=i) for i in range(n)]

    if gc_prices is None:
        gc_prices = [2800.0] * n
    if si_prices is None:
        si_prices = [32.0] * n

    return pd.DataFrame({
        'DateTime': dts,
        'Last_GC': gc_prices,
        'Last_SI': si_prices,
        'ZScore': zscores,
        'Correlation': [correlation] * n,
        'Cointegration_Score': [coint_score] * n,
        'Beta': [beta] * n,
        'Hurst': [hurst] * n,
    })


def _make_5s(n_bars, gc_prices=None, si_prices=None, start_dt=None):
    """
    Construit un df_5s minimal.

    Args:
        n_bars: nombre de barres 5s
        gc_prices: liste ou valeur unique (defaut: 2800.0)
        si_prices: liste ou valeur unique (defaut: 32.0)
    """
    if start_dt is None:
        start_dt = datetime(2026, 1, 5, 18, 0, 0)
    dts = [start_dt + timedelta(seconds=5 * i) for i in range(n_bars)]

    if gc_prices is None:
        gc_prices = [2800.0] * n_bars
    elif isinstance(gc_prices, (int, float)):
        gc_prices = [gc_prices] * n_bars

    if si_prices is None:
        si_prices = [32.0] * n_bars
    elif isinstance(si_prices, (int, float)):
        si_prices = [si_prices] * n_bars

    return pd.DataFrame({
        'DateTime': dts,
        'Last_GC': gc_prices,
        'Last_SI': si_prices,
    })


# ============================================================================
# TESTS
# ============================================================================

class TestRunHybridBacktest:
    """Tests du moteur de backtest hybride run_hybrid_backtest()."""

    def test_no_trades_when_zscore_flat(self, sample_config):
        """Aucun trade si le Z-Score reste dans la zone neutre."""
        n = 6
        df_1min = _make_1min(n, zscores=[np.nan, 0.0, 0.5, -0.5, 0.2, -0.1])
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)
        assert len(trades) == 0

    def test_single_long_trade_zscore_tp(self, sample_config):
        """Un trade LONG avec sortie TP_ZSCORE."""
        # Bar 0: NaN (skip), bar 1: Z=0 (pas d'entree), bar 2: Z=-3.1 (entree LONG)
        # Bar 3: Z=-2.5 (pas encore TP), bar 4: Z=-1.5 (>= -2.0 -> TP_ZSCORE)
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -1.5, 0.0]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)  # Prix stables -> pas de trigger dollar

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) == 1
        t = trades.iloc[0]
        assert t['Direction'] == 'LONG'
        assert t['Exit_Reason'] == 'TP_ZSCORE'
        assert t['Entry_ZScore'] == -3.1
        assert t['Trade_No'] == 1

    def test_single_short_trade_zscore_tp(self, sample_config):
        """Un trade SHORT avec sortie TP_ZSCORE."""
        n = 6
        zscores = [np.nan, 0.0, 3.1, 2.5, 1.5, 0.0]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) == 1
        t = trades.iloc[0]
        assert t['Direction'] == 'SHORT'
        assert t['Exit_Reason'] == 'TP_ZSCORE'
        assert t['Entry_ZScore'] == 3.1

    def test_dollar_tp_exit(self, sample_config):
        """Sortie TP_DOLLAR detectee sur barres 5s."""
        # Entree LONG bar 2, puis les barres 5s entre bar 2 et bar 3
        # montrent SI qui monte assez pour trigger TP ($300)
        # PnL LONG = (entry_gc - gc_5s)*100*1 + (si_5s - entry_si)*5000*1
        # Si SI monte de +0.07 : PnL_SI = 0.07 * 5000 = $350 >= $300 -> TP
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -2.5, 0.0]
        df_1min = _make_1min(n, zscores)

        # 5s bars : 12 par minute, prix stables sauf entre bar 2 et bar 3
        n_5s = n * 12
        start_dt = datetime(2026, 1, 5, 18, 0, 0)
        dts_5s = [start_dt + timedelta(seconds=5 * i) for i in range(n_5s)]
        gc_5s = [2800.0] * n_5s
        si_5s = [32.0] * n_5s

        # Entre bar 2 (18:02) et bar 3 (18:03) : indices 5s = 24 a 35
        # Faire monter SI progressivement pour trigger TP
        for k in range(24, 36):
            si_5s[k] = 32.0 + 0.07 * (k - 23) / 12  # SI monte

        df_5s = pd.DataFrame({
            'DateTime': dts_5s, 'Last_GC': gc_5s, 'Last_SI': si_5s
        })

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) >= 1
        t = trades.iloc[0]
        assert t['Exit_Reason'] == 'TP_DOLLAR'
        assert t['PnL_Gross'] == sample_config['exit']['pnl_take_profit']
        # PnL_GC et PnL_SI sont NaN pour les dollar exits
        assert np.isnan(t['PnL_GC'])
        assert np.isnan(t['PnL_SI'])

    def test_dollar_sl_exit(self, sample_config):
        """Sortie SL_DOLLAR detectee sur barres 5s."""
        # LONG : SI baisse -> PnL_SI negatif -> SL
        # Si SI baisse de -0.13 : PnL_SI = -0.13 * 5000 = -$650 >= SL (-$600)
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -2.5, 0.0]
        df_1min = _make_1min(n, zscores)

        n_5s = n * 12
        start_dt = datetime(2026, 1, 5, 18, 0, 0)
        dts_5s = [start_dt + timedelta(seconds=5 * i) for i in range(n_5s)]
        gc_5s = [2800.0] * n_5s
        si_5s = [32.0] * n_5s

        # SI baisse entre bar 2 et bar 3
        for k in range(24, 36):
            si_5s[k] = 32.0 - 0.13 * (k - 23) / 12

        df_5s = pd.DataFrame({
            'DateTime': dts_5s, 'Last_GC': gc_5s, 'Last_SI': si_5s
        })

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) >= 1
        t = trades.iloc[0]
        assert t['Exit_Reason'] == 'SL_DOLLAR'
        assert t['PnL_Gross'] == sample_config['exit']['pnl_stop_loss']

    def test_exit_priority_sl_before_tp(self, sample_config):
        """SL_DOLLAR a priorite sur TP_DOLLAR dans le scan 5s."""
        # Les barres 5s montrent d'abord SL (SI baisse fort) puis TP
        # Le moteur doit sortir en SL_DOLLAR (break au premier trigger)
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -2.5, 0.0]
        df_1min = _make_1min(n, zscores)

        n_5s = n * 12
        start_dt = datetime(2026, 1, 5, 18, 0, 0)
        dts_5s = [start_dt + timedelta(seconds=5 * i) for i in range(n_5s)]
        gc_5s = [2800.0] * n_5s
        si_5s = [32.0] * n_5s

        # SI chute fort d'abord (SL), puis remonte (TP) -- mais SL deja declenche
        for k in range(24, 30):
            si_5s[k] = 32.0 - 0.15 * (k - 23) / 6  # SL rapide
        for k in range(30, 36):
            si_5s[k] = 32.0 + 0.10  # TP apres (ne devrait pas etre atteint)

        df_5s = pd.DataFrame({
            'DateTime': dts_5s, 'Last_GC': gc_5s, 'Last_SI': si_5s
        })

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) >= 1
        assert trades.iloc[0]['Exit_Reason'] == 'SL_DOLLAR'

    def test_cooldown_after_sl_zscore(self, sample_config):
        """Cooldown bloque la reentree meme direction apres SL_ZSCORE."""
        # Bar 0: NaN, bar 1: Z=0, bar 2: Z=-3.1 (entry LONG)
        # Bar 3: Z=-3.6 (SL_ZSCORE, <= -3.5) -> COOLDOWN_LONG
        # Bar 4: Z=-3.1 (conditions OK mais COOLDOWN -> bloque)
        # Bar 5: Z=-0.5 (>= -1.0 -> cooldown reset)
        # Bar 6: Z=-3.1 (entry LONG OK)
        # Bar 7: Z=-1.5 (TP_ZSCORE)
        n = 8
        zscores = [np.nan, 0.0, -3.1, -3.6, -3.1, -0.5, -3.1, -1.5]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        # 2 trades: premier SL_ZSCORE, deuxieme TP_ZSCORE
        assert len(trades) == 2
        assert trades.iloc[0]['Exit_Reason'] == 'SL_ZSCORE'
        assert trades.iloc[1]['Exit_Reason'] == 'TP_ZSCORE'
        assert trades.iloc[1]['Direction'] == 'LONG'

    def test_reentry_after_tp_zscore(self, sample_config):
        """Reentree autorisee apres TP_ZSCORE si conditions toujours OK."""
        # Bar 0: NaN, bar 1: Z=0, bar 2: Z=-3.1 (entry LONG)
        # Bar 3: Z=-1.5 (TP_ZSCORE, >= -2.0) -> FLAT
        # Bar 4: Z=-3.1 (entry LONG nouveau)
        # Bar 5: Z=-1.5 (TP_ZSCORE)
        n = 6
        zscores = [np.nan, 0.0, -3.1, -1.5, -3.1, -1.5]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) >= 2
        assert trades.iloc[0]['Exit_Reason'] == 'TP_ZSCORE'
        assert trades.iloc[1]['Exit_Reason'] == 'TP_ZSCORE'

    def test_position_sizing(self, sample_config):
        """Verifie le sizing dollar-neutral (GC_Contracts, SI_Contracts)."""
        # Beta=1.0, GC=2800, SI=32
        # GC_contracts = round((32*5000)/(2800*100) * 1.0) = round(0.571) = 1
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -1.5, 0.0]
        df_1min = _make_1min(n, zscores, beta=1.0)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) == 1
        t = trades.iloc[0]
        assert t['GC_Contracts'] == 1
        assert t['SI_Contracts'] == 1

    def test_empty_dataframe(self, sample_config):
        """DataFrame 1min vide retourne un DataFrame de trades vide."""
        df_1min = pd.DataFrame(columns=[
            'DateTime', 'Last_GC', 'Last_SI', 'ZScore',
            'Correlation', 'Cointegration_Score', 'Beta', 'Hurst'
        ])
        df_5s = pd.DataFrame(columns=['DateTime', 'Last_GC', 'Last_SI'])

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)
        assert len(trades) == 0

    def test_still_open_trade(self, sample_config):
        """Trade encore ouvert a la fin -> Exit_Reason=STILL_OPEN."""
        # Z entre en LONG bar 2, mais jamais de sortie avant la fin
        n = 5
        zscores = [np.nan, 0.0, -3.1, -2.8, -2.6]  # Reste entre -3.5 et -2.0
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) == 1
        assert trades.iloc[0]['Exit_Reason'] == 'STILL_OPEN'

    def test_costs_applied(self, sample_config):
        """Les couts (commission + slippage) sont bien deduits du PnL."""
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -1.5, 0.0]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        assert len(trades) == 1
        t = trades.iloc[0]
        # Costs > 0 (commission + slippage)
        assert t['Costs'] > 0
        # PnL_Net = PnL_Gross - Costs
        assert np.isclose(t['PnL_Net'], t['PnL_Gross'] - t['Costs'])

    def test_trades_df_columns(self, sample_config):
        """Verifie que toutes les 22 colonnes sont presentes."""
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -1.5, 0.0]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, sample_config, verbose=False)

        expected_cols = [
            'Trade_No', 'Direction', 'Entry_DateTime', 'Exit_DateTime',
            'Duration_Min', 'Entry_GC', 'Entry_SI', 'Exit_GC', 'Exit_SI',
            'Entry_ZScore', 'Exit_ZScore', 'Exit_Reason', 'Beta',
            'GC_Contracts', 'SI_Contracts', 'PnL_GC', 'PnL_SI',
            'PnL_Gross', 'Costs', 'PnL_Net', 'Max_PnL_Intra',
            'Min_PnL_Intra', 'PnL_Cumul',
        ]
        for col in expected_cols:
            assert col in trades.columns, f"Colonne manquante : {col}"

    def test_pure_zscore_mode_skips_5s_scan(self, sample_config):
        """En mode pure Z-Score (TP/SL extremes), le scan 5s est saute
        mais les sorties Z-Score fonctionnent toujours."""
        import copy
        cfg = copy.deepcopy(sample_config)
        cfg['exit']['pnl_take_profit'] = 99999
        cfg['exit']['pnl_stop_loss'] = -99999

        # Bar 0: NaN, bar 1: Z=0, bar 2: Z=-3.1 (entree LONG)
        # Bar 3: Z=-2.5, bar 4: Z=-1.5 (>= -2.0 -> TP_ZSCORE)
        n = 6
        zscores = [np.nan, 0.0, -3.1, -2.5, -1.5, 0.0]
        df_1min = _make_1min(n, zscores)
        df_5s = _make_5s(n * 12)

        trades = run_hybrid_backtest(df_1min, df_5s, cfg, verbose=False)

        assert len(trades) == 1
        t = trades.iloc[0]
        assert t['Exit_Reason'] == 'TP_ZSCORE'
        assert t['Direction'] == 'LONG'
