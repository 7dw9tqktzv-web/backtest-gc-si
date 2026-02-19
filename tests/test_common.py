# ============================================================================
# TEST_COMMON.PY - Tests pour le module common.py
# ============================================================================
#
# Tests des fonctions partagees :
# - check_entry_conditions()
# - check_zscore_exit()
# - check_cooldown_reset()
# - calculate_current_pnl()
# - build_config_fingerprint()
#
# ============================================================================

import pytest
import numpy as np
import sys
from pathlib import Path

# Ajouter src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from common import (
    STATE_FLAT, STATE_LONG, STATE_SHORT,
    STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
    check_entry_conditions,
    check_zscore_exit,
    check_cooldown_reset,
    calculate_current_pnl,
    build_config_fingerprint,
)


class TestStateConstants:
    """Tests des constantes d'etat."""

    def test_state_values(self):
        """Verifie que les constantes ont les bonnes valeurs."""
        assert STATE_FLAT == 0
        assert STATE_LONG == 1
        assert STATE_SHORT == -1
        assert STATE_COOLDOWN_LONG == 2
        assert STATE_COOLDOWN_SHORT == -2

    def test_state_parity_with_numba_engine(self):
        """Verifie que les constantes common.py == backtest_engine_numba.py.

        Note: seuls _FLAT, _LONG, _SHORT sont dupliques dans le Numba engine.
        Les cooldowns (STATE_COOLDOWN_LONG/SHORT) sont importes directement
        depuis common.py par le Numba engine, donc pas de risque de desync.
        """
        from backtest_engine_numba import _FLAT, _LONG, _SHORT
        assert _FLAT == STATE_FLAT, f"_FLAT={_FLAT} != STATE_FLAT={STATE_FLAT}"
        assert _LONG == STATE_LONG, f"_LONG={_LONG} != STATE_LONG={STATE_LONG}"
        assert _SHORT == STATE_SHORT, f"_SHORT={_SHORT} != STATE_SHORT={STATE_SHORT}"


class TestCheckEntryConditions:
    """Tests de la fonction check_entry_conditions()."""

    def test_long_entry_when_flat(self, sample_config):
        """LONG autorise quand FLAT et conditions remplies."""
        result = check_entry_conditions(
            zscore=-3.5,  # <= -3.0
            correlation=0.85,  # > 0.60
            cointegration_score=70,  # >= 50
            state=STATE_FLAT,
            config=sample_config,
            hurst=0.4
        )
        assert result == 1  # LONG

    def test_short_entry_when_flat(self, sample_config):
        """SHORT autorise quand FLAT et conditions remplies."""
        result = check_entry_conditions(
            zscore=3.5,  # >= 3.0
            correlation=0.85,
            cointegration_score=70,
            state=STATE_FLAT,
            config=sample_config,
            hurst=0.4
        )
        assert result == -1  # SHORT

    def test_no_entry_when_zscore_neutral(self, sample_config):
        """Pas d'entree quand Z-Score dans la zone neutre."""
        result = check_entry_conditions(
            zscore=0.0,  # Zone neutre
            correlation=0.85,
            cointegration_score=70,
            state=STATE_FLAT,
            config=sample_config
        )
        assert result == 0  # Pas d'entree

    def test_no_entry_low_correlation(self, sample_config):
        """Pas d'entree si correlation trop basse."""
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.50,  # < 0.60
            cointegration_score=70,
            state=STATE_FLAT,
            config=sample_config
        )
        assert result == 0

    def test_no_entry_low_cointegration(self, sample_config):
        """Pas d'entree si score de cointegration trop bas."""
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.85,
            cointegration_score=40,  # < 50
            state=STATE_FLAT,
            config=sample_config
        )
        assert result == 0

    def test_no_long_when_already_long(self, sample_config):
        """Pas d'entree LONG si deja en position LONG."""
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_LONG,
            config=sample_config
        )
        assert result == 0

    def test_no_short_when_already_short(self, sample_config):
        """Pas d'entree SHORT si deja en position SHORT."""
        result = check_entry_conditions(
            zscore=3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_SHORT,
            config=sample_config
        )
        assert result == 0

    def test_no_long_during_cooldown_long(self, sample_config):
        """Pas d'entree LONG pendant cooldown LONG."""
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_COOLDOWN_LONG,
            config=sample_config
        )
        assert result == 0

    def test_short_allowed_during_cooldown_long(self, sample_config):
        """Entree SHORT autorisee pendant cooldown LONG."""
        result = check_entry_conditions(
            zscore=3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_COOLDOWN_LONG,
            config=sample_config
        )
        assert result == -1  # SHORT autorise

    def test_hurst_filter_blocks_entry(self, sample_config):
        """Filtre Hurst bloque l'entree si Hurst trop eleve."""
        sample_config['entry']['hurst_max'] = 0.45  # Activer le filtre
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_FLAT,
            config=sample_config,
            hurst=0.55  # > 0.45
        )
        assert result == 0

    def test_hurst_filter_allows_entry(self, sample_config):
        """Filtre Hurst autorise l'entree si Hurst assez bas."""
        sample_config['entry']['hurst_max'] = 0.45
        result = check_entry_conditions(
            zscore=-3.5,
            correlation=0.85,
            cointegration_score=70,
            state=STATE_FLAT,
            config=sample_config,
            hurst=0.35  # < 0.45
        )
        assert result == 1


class TestCheckZscoreExit:
    """Tests de la fonction check_zscore_exit()."""

    def test_tp_long_exit(self, sample_config):
        """Take Profit LONG declenche quand Z-Score remonte."""
        should_exit, reason = check_zscore_exit(
            zscore=-1.5,  # >= -2.0
            state=STATE_LONG,
            config=sample_config
        )
        assert should_exit is True
        assert reason == 'TP_ZSCORE'

    def test_sl_long_exit(self, sample_config):
        """Stop Loss LONG declenche quand Z-Score baisse trop."""
        should_exit, reason = check_zscore_exit(
            zscore=-4.0,  # <= -3.5
            state=STATE_LONG,
            config=sample_config
        )
        assert should_exit is True
        assert reason == 'SL_ZSCORE'

    def test_tp_short_exit(self, sample_config):
        """Take Profit SHORT declenche quand Z-Score redescend."""
        should_exit, reason = check_zscore_exit(
            zscore=1.5,  # <= 2.0
            state=STATE_SHORT,
            config=sample_config
        )
        assert should_exit is True
        assert reason == 'TP_ZSCORE'

    def test_sl_short_exit(self, sample_config):
        """Stop Loss SHORT declenche quand Z-Score monte trop."""
        should_exit, reason = check_zscore_exit(
            zscore=4.0,  # >= 3.5
            state=STATE_SHORT,
            config=sample_config
        )
        assert should_exit is True
        assert reason == 'SL_ZSCORE'

    def test_no_exit_long_in_range(self, sample_config):
        """Pas de sortie LONG si Z-Score dans la zone neutre."""
        should_exit, reason = check_zscore_exit(
            zscore=-2.5,  # Entre -3.5 et -2.0
            state=STATE_LONG,
            config=sample_config
        )
        assert should_exit is False
        assert reason == ''

    def test_no_exit_short_in_range(self, sample_config):
        """Pas de sortie SHORT si Z-Score dans la zone neutre."""
        should_exit, reason = check_zscore_exit(
            zscore=2.5,  # Entre 2.0 et 3.5
            state=STATE_SHORT,
            config=sample_config
        )
        assert should_exit is False
        assert reason == ''

    def test_sl_priority_over_tp_long(self, sample_config):
        """SL a priorite sur TP (cas limite impossible en pratique)."""
        # Ce cas ne peut pas arriver en pratique car -4 < -3.5 < -2.0
        # Mais on teste que SL est verifie en premier
        should_exit, reason = check_zscore_exit(
            zscore=-4.0,  # SL trigger
            state=STATE_LONG,
            config=sample_config
        )
        assert reason == 'SL_ZSCORE'

    def test_tp_disabled(self, sample_config):
        """Pas de TP si zscore_tp_enabled = False."""
        sample_config['exit']['zscore_tp_enabled'] = False
        should_exit, reason = check_zscore_exit(
            zscore=-1.5,  # Normalement TP
            state=STATE_LONG,
            config=sample_config
        )
        assert should_exit is False
        assert reason == ''


class TestCheckCooldownReset:
    """Tests de la fonction check_cooldown_reset()."""

    def test_cooldown_long_reset(self, sample_config):
        """Cooldown LONG se termine quand Z-Score remonte a -1.0."""
        result = check_cooldown_reset(
            zscore=-0.5,  # >= -1.0
            state=STATE_COOLDOWN_LONG,
            config=sample_config
        )
        assert result is True

    def test_cooldown_long_not_reset(self, sample_config):
        """Cooldown LONG continue si Z-Score encore bas."""
        result = check_cooldown_reset(
            zscore=-2.0,  # < -1.0
            state=STATE_COOLDOWN_LONG,
            config=sample_config
        )
        assert result is False

    def test_cooldown_short_reset(self, sample_config):
        """Cooldown SHORT se termine quand Z-Score redescend a +1.0."""
        result = check_cooldown_reset(
            zscore=0.5,  # <= 1.0
            state=STATE_COOLDOWN_SHORT,
            config=sample_config
        )
        assert result is True

    def test_cooldown_short_not_reset(self, sample_config):
        """Cooldown SHORT continue si Z-Score encore haut."""
        result = check_cooldown_reset(
            zscore=2.0,  # > 1.0
            state=STATE_COOLDOWN_SHORT,
            config=sample_config
        )
        assert result is False

    def test_no_reset_for_non_cooldown_state(self, sample_config):
        """Pas de reset pour les etats non-cooldown."""
        result = check_cooldown_reset(
            zscore=0.0,
            state=STATE_FLAT,
            config=sample_config
        )
        assert result is False


class TestCalculateCurrentPnl:
    """Tests de la fonction calculate_current_pnl()."""

    def test_long_spread_profit(self, sample_config):
        """PnL positif pour LONG spread quand spread s'elargit."""
        # LONG spread = long SI, short GC
        # Profit si SI monte et/ou GC baisse
        pnl = calculate_current_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            current_gc=2798.0,  # GC baisse -> profit (short GC)
            current_si=32.05,   # SI monte -> profit (long SI)
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )
        # PnL GC = (2800 - 2798) * 100 * 6 = 1200
        # PnL SI = (32.05 - 32.0) * 5000 * 1 = 250
        # Total = 1450
        assert np.isclose(pnl, 1450.0)

    def test_long_spread_loss(self, sample_config):
        """PnL negatif pour LONG spread quand spread se resserre."""
        pnl = calculate_current_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            current_gc=2805.0,  # GC monte -> perte (short GC)
            current_si=31.95,   # SI baisse -> perte (long SI)
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )
        # PnL GC = (2800 - 2805) * 100 * 6 = -3000
        # PnL SI = (31.95 - 32.0) * 5000 * 1 = -250
        # Total = -3250
        assert np.isclose(pnl, -3250.0)

    def test_short_spread_profit(self, sample_config):
        """PnL positif pour SHORT spread quand spread se resserre."""
        # SHORT spread = short SI, long GC
        # Profit si SI baisse et/ou GC monte
        pnl = calculate_current_pnl(
            direction=-1,
            entry_gc=2800.0,
            entry_si=32.0,
            current_gc=2805.0,  # GC monte -> profit (long GC)
            current_si=31.95,   # SI baisse -> profit (short SI)
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )
        # PnL GC = (2805 - 2800) * 100 * 6 = 3000
        # PnL SI = (32.0 - 31.95) * 5000 * 1 = 250
        # Total = 3250
        assert np.isclose(pnl, 3250.0)

    def test_pnl_with_no_move(self, sample_config):
        """PnL = 0 si prix inchanges."""
        pnl = calculate_current_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            current_gc=2800.0,
            current_si=32.0,
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )
        assert pnl == 0.0


class TestBuildConfigFingerprint:
    """Tests de la fonction build_config_fingerprint()."""

    def test_fingerprint_format(self, sample_config):
        """Verifie le format de l'empreinte."""
        fp = build_config_fingerprint(sample_config)

        # Doit contenir les parametres cles
        assert 'beta20' in fp  # beta_lookback
        assert 'zp10' in fp    # zscore_period
        assert 'corr10' in fp  # correlation_period
        assert 'adf20' in fp   # adf_hurst_period
        assert 'TP300' in fp   # pnl_take_profit
        assert 'SL-600' in fp  # pnl_stop_loss

    def test_fingerprint_changes_with_config(self, sample_config):
        """Deux configs differentes produisent des empreintes differentes."""
        fp1 = build_config_fingerprint(sample_config)

        sample_config['indicators']['beta_lookback'] = 100
        fp2 = build_config_fingerprint(sample_config)

        assert fp1 != fp2

    def test_fingerprint_deterministic(self, sample_config):
        """Meme config produit toujours la meme empreinte."""
        fp1 = build_config_fingerprint(sample_config)
        fp2 = build_config_fingerprint(sample_config)
        assert fp1 == fp2
