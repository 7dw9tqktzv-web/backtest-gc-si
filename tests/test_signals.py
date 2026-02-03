# ============================================================================
# TEST_SIGNALS.PY - Tests pour le module signals.py
# ============================================================================
#
# Tests des fonctions de generation de signaux :
# - generate_signals()
# - get_signal_summary()
# - build_trade_list()
#
# ============================================================================

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ajouter src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from signals import (
    generate_signals,
    get_signal_summary,
    build_trade_list,
    REQUIRED_COLUMNS,
)
from common import (
    STATE_FLAT, STATE_LONG, STATE_SHORT,
    STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
)


class TestGenerateSignals:
    """Tests de la fonction generate_signals()."""

    def test_output_columns_added(self, sample_df_with_indicators, sample_config):
        """Verifie que les colonnes de sortie sont ajoutees."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)

        assert 'Signal' in df.columns
        assert 'Exit_Signal' in df.columns
        assert 'Exit_Reason' in df.columns
        assert 'State' in df.columns

    def test_missing_columns_raises_error(self, sample_prices_df, sample_config):
        """Erreur si colonnes requises manquantes."""
        with pytest.raises(ValueError) as excinfo:
            generate_signals(sample_prices_df, sample_config)

        assert "Colonnes manquantes" in str(excinfo.value)

    def test_signal_values(self, sample_df_with_indicators, sample_config):
        """Signal doit etre 1, -1 ou 0."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)

        unique_signals = df['Signal'].unique()
        for s in unique_signals:
            assert s in [0, 1, -1]

    def test_exit_signal_values(self, sample_df_with_indicators, sample_config):
        """Exit_Signal doit etre 0 ou 1."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)

        unique_exits = df['Exit_Signal'].unique()
        for e in unique_exits:
            assert e in [0, 1]

    def test_state_values(self, sample_df_with_indicators, sample_config):
        """State doit etre une des 5 valeurs valides."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)

        valid_states = [STATE_FLAT, STATE_LONG, STATE_SHORT,
                        STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT]
        unique_states = df['State'].unique()
        for s in unique_states:
            assert s in valid_states

    def test_long_entry_signal(self, sample_config):
        """Signal LONG genere quand conditions remplies."""
        # Creer un DataFrame avec Z-Score tres bas (signal LONG)
        n = 50
        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': [0.0] * 25 + [-3.5] + [0.0] * 24,  # Signal LONG a i=25
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        result = generate_signals(df, sample_config)

        # Il devrait y avoir un signal LONG a l'index 25
        assert result.loc[25, 'Signal'] == 1

    def test_short_entry_signal(self, sample_config):
        """Signal SHORT genere quand conditions remplies."""
        n = 50
        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': [0.0] * 25 + [3.5] + [0.0] * 24,  # Signal SHORT a i=25
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        result = generate_signals(df, sample_config)

        # Il devrait y avoir un signal SHORT a l'index 25
        assert result.loc[25, 'Signal'] == -1

    def test_tp_exit_long(self, sample_config):
        """Exit TP genere quand Z-Score remonte (LONG)."""
        n = 50
        zscore = [0.0] * 10 + [-3.5] + [-2.8] * 10 + [-1.5] + [0.0] * 28
        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,  # Entry a 10, TP a 21
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        result = generate_signals(df, sample_config)

        # Entree LONG a l'index 10
        assert result.loc[10, 'Signal'] == 1
        # TP a l'index 21 (Z >= -2.0)
        assert result.loc[21, 'Exit_Signal'] == 1
        assert result.loc[21, 'Exit_Reason'] == 'TP_ZSCORE'

    def test_sl_triggers_cooldown(self, sample_config):
        """SL LONG declenche cooldown."""
        n = 50
        # Entry a -3.0 (seuil), reste entre -3.0 et -3.5, puis SL a -4.0
        # Apres SL, Z reste a -2.0 (< -1.0) pour maintenir le cooldown
        # Note: zscore_sl_long = -3.5, donc SL declenche quand Z <= -3.5
        # Note: zscore_reset_long = -1.0, donc cooldown reset quand Z >= -1.0
        zscore = [0.0] * 10 + [-3.1] + [-3.2] * 5 + [-4.0] + [-2.0] * 5 + [0.0] * 28
        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,  # Entry a 10, SL a 16, cooldown 17-21, reset 22+
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        result = generate_signals(df, sample_config)

        # Entry LONG a l'index 10 (Z = -3.1 <= -3.0)
        assert result.loc[10, 'Signal'] == 1
        # SL a l'index 16 (Z = -4.0 <= -3.5)
        assert result.loc[16, 'Exit_Signal'] == 1
        assert result.loc[16, 'Exit_Reason'] == 'SL_ZSCORE'
        # Apres SL, etat = COOLDOWN_LONG (Z = -2.0 < -1.0)
        assert result.loc[17, 'State'] == STATE_COOLDOWN_LONG
        assert result.loc[20, 'State'] == STATE_COOLDOWN_LONG
        # Apres reset (Z = 0.0 >= -1.0), etat = FLAT
        assert result.loc[22, 'State'] == STATE_FLAT

    def test_cooldown_prevents_reentry(self, sample_config):
        """Cooldown empeche reentree dans la meme direction."""
        n = 50
        # Entry, SL, puis nouveau signal LONG (qui doit etre bloque)
        zscore = [0.0] * 5 + [-3.5] + [-4.0] + [-3.5] * 10 + [0.0] * 33
        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        result = generate_signals(df, sample_config)

        # Entry a 5
        assert result.loc[5, 'Signal'] == 1
        # SL a 6
        assert result.loc[6, 'Exit_Signal'] == 1
        # Pendant cooldown (7-16), pas de nouveau signal LONG meme si Z <= -3.5
        for i in range(7, 17):
            if result.loc[i, 'State'] == STATE_COOLDOWN_LONG:
                # Pas de signal LONG pendant cooldown
                assert result.loc[i, 'Signal'] != 1

    def test_returns_copy(self, sample_df_with_indicators, sample_config):
        """generate_signals retourne une copie."""
        original = sample_df_with_indicators.copy()
        result = generate_signals(original, sample_config)

        # Modifier result ne devrait pas modifier original
        result.loc[0, 'Signal'] = 999
        assert 'Signal' not in original.columns or original.loc[0, 'Signal'] != 999


class TestGetSignalSummary:
    """Tests de la fonction get_signal_summary()."""

    def test_summary_keys(self, sample_df_with_indicators, sample_config):
        """Verifie que le resume contient les bonnes cles."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        summary = get_signal_summary(df)

        expected_keys = [
            'total_bars',
            'entries_long',
            'entries_short',
            'exits_total',
            'exits_tp_zscore',
            'exits_sl_zscore',
            'total_entries',
            'tp_sl_ratio',
            'time_in_market_pct',
        ]

        for key in expected_keys:
            assert key in summary

    def test_summary_consistency(self, sample_df_with_indicators, sample_config):
        """Verifie la coherence des statistiques."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        summary = get_signal_summary(df)

        # total_entries = entries_long + entries_short
        assert summary['total_entries'] == summary['entries_long'] + summary['entries_short']

        # exits_total >= exits_tp_zscore + exits_sl_zscore
        assert summary['exits_total'] >= summary['exits_tp_zscore'] + summary['exits_sl_zscore']


class TestBuildTradeList:
    """Tests de la fonction build_trade_list()."""

    def test_trade_list_columns(self, sample_df_with_indicators, sample_config):
        """Verifie les colonnes de la liste de trades."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        trades = build_trade_list(df)

        if len(trades) > 0:
            expected_columns = [
                'Trade_No', 'Direction', 'Entry_DateTime', 'Exit_DateTime',
                'Duration_Min', 'Entry_GC', 'Entry_SI', 'Exit_GC', 'Exit_SI',
                'Entry_ZScore', 'Exit_ZScore', 'Exit_Reason'
            ]
            for col in expected_columns:
                assert col in trades.columns

    def test_trade_directions(self, sample_df_with_indicators, sample_config):
        """Direction doit etre LONG ou SHORT."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        trades = build_trade_list(df)

        if len(trades) > 0:
            for direction in trades['Direction'].unique():
                assert direction in ['LONG', 'SHORT']

    def test_trade_duration_positive(self, sample_df_with_indicators, sample_config):
        """Duree doit etre positive."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        trades = build_trade_list(df)

        if len(trades) > 0:
            assert (trades['Duration_Min'] >= 0).all()

    def test_exit_datetime_after_entry(self, sample_df_with_indicators, sample_config):
        """Exit_DateTime doit etre apres Entry_DateTime."""
        df = generate_signals(sample_df_with_indicators.copy(), sample_config)
        trades = build_trade_list(df)

        if len(trades) > 0:
            for _, trade in trades.iterrows():
                assert trade['Exit_DateTime'] >= trade['Entry_DateTime']

    def test_simple_trade_sequence(self, sample_config):
        """Test avec une sequence de trades simple."""
        n = 100
        zscore = (
            [0.0] * 10 +      # Flat
            [-3.5] +          # Entry LONG (10)
            [-2.5] * 10 +     # In position
            [-1.5] +          # Exit TP (21)
            [0.0] * 10 +      # Flat
            [3.5] +           # Entry SHORT (32)
            [2.5] * 10 +      # In position
            [1.5] +           # Exit TP (43)
            [0.0] * 56        # Flat
        )

        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0 + i*0.1 for i in range(n)],
            'Last_SI': [32.0 + i*0.001 for i in range(n)],
            'ZScore': zscore,
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        df = generate_signals(df, sample_config)
        trades = build_trade_list(df)

        # On devrait avoir 2 trades
        assert len(trades) == 2

        # Premier trade = LONG
        assert trades.iloc[0]['Direction'] == 'LONG'
        assert trades.iloc[0]['Exit_Reason'] == 'TP_ZSCORE'

        # Deuxieme trade = SHORT
        assert trades.iloc[1]['Direction'] == 'SHORT'
        assert trades.iloc[1]['Exit_Reason'] == 'TP_ZSCORE'

    def test_still_open_trade(self, sample_config):
        """Trade encore ouvert a la fin des donnees."""
        n = 50
        zscore = [0.0] * 10 + [-3.5] + [-2.8] * 39  # Entry a 10, jamais de sortie

        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        df = generate_signals(df, sample_config)
        trades = build_trade_list(df)

        # Le trade devrait etre marque STILL_OPEN
        assert len(trades) == 1
        assert trades.iloc[0]['Exit_Reason'] == 'STILL_OPEN'


class TestStateMachine:
    """Tests de la machine a etats complete."""

    def test_flat_to_long_to_flat(self, sample_config):
        """Transition FLAT -> LONG -> FLAT (TP)."""
        n = 30
        zscore = [0.0] * 5 + [-3.5] + [-2.5] * 5 + [-1.5] + [0.0] * 18

        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        df = generate_signals(df, sample_config)

        # Avant entry: FLAT
        assert df.loc[4, 'State'] == STATE_FLAT
        # Apres entry: LONG
        assert df.loc[5, 'State'] == STATE_LONG
        # Pendant position: LONG
        assert df.loc[10, 'State'] == STATE_LONG
        # Apres TP: FLAT
        assert df.loc[12, 'State'] == STATE_FLAT

    def test_long_to_cooldown_to_flat(self, sample_config):
        """Transition LONG -> COOLDOWN_LONG -> FLAT."""
        n = 40
        zscore = (
            [0.0] * 5 +       # Flat
            [-3.5] +          # Entry LONG
            [-4.0] +          # SL -> COOLDOWN
            [-2.0] * 5 +      # Cooldown (Z < -1.0)
            [-0.5] +          # Reset -> FLAT
            [0.0] * 27        # Flat
        )

        df = pd.DataFrame({
            'DateTime': [datetime(2026, 1, 1) + timedelta(minutes=i) for i in range(n)],
            'Last_GC': [2800.0] * n,
            'Last_SI': [32.0] * n,
            'ZScore': zscore,
            'Correlation': [0.9] * n,
            'Cointegration_Score': [80.0] * n,
            'Hurst': [0.3] * n,
        })

        df = generate_signals(df, sample_config)

        # Entry: LONG
        assert df.loc[5, 'State'] == STATE_LONG
        # Apres SL: COOLDOWN_LONG
        assert df.loc[7, 'State'] == STATE_COOLDOWN_LONG
        # Pendant cooldown
        assert df.loc[10, 'State'] == STATE_COOLDOWN_LONG
        # Apres reset: FLAT
        assert df.loc[13, 'State'] == STATE_FLAT
