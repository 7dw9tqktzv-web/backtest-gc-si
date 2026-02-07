# ============================================================================
# TEST_GRID_SEARCH_RUNNER.PY - Tests du mode hybrid dans grid_search_runner.py
# ============================================================================

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from grid_search_runner import (
    create_hybrid_entry_exit_generator,
    create_hybrid_label_builder,
    create_hybrid_result_builder,
)


# ============================================================================
# TESTS create_hybrid_entry_exit_generator()
# ============================================================================

class TestHybridEntryExitGenerator:
    """Tests du generateur de variantes hybrid."""

    def test_variant_count(self):
        """Verifie le nombre total de variantes generees."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[2.5, 3.5],
            cointegration_min=[40, 50],
            zscore_tp=[-1.0, 0.0],
            pnl_stop_loss=[-800, -1200],
            pnl_take_profit_cap=[800, 99999],
        )
        variants = gen()
        # 2 zE x 2 co x 2 zTP x 2 SL x 2 TP_cap = 32
        assert len(variants) == 32

    def test_overrides_zscore_sl_disabled(self):
        """Le zSL doit etre desactive (99999) en mode hybrid."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[3.0],
            cointegration_min=[50],
            zscore_tp=[-0.5],
            pnl_stop_loss=[-1200],
        )
        v = gen()[0]
        ov = v["overrides"]
        assert ov["exit.zscore_sl_long"] == -99999
        assert ov["exit.zscore_sl_short"] == 99999

    def test_overrides_dollar_sl_active(self):
        """Le dollar SL doit etre actif avec la valeur demandee."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[3.0],
            cointegration_min=[50],
            zscore_tp=[-0.5],
            pnl_stop_loss=[-1800],
            pnl_take_profit_cap=[2500],
        )
        v = gen()[0]
        ov = v["overrides"]
        assert ov["exit.pnl_stop_loss"] == -1800
        assert ov["exit.pnl_take_profit"] == 2500

    def test_overrides_zscore_tp_signs(self):
        """Les signes zTP doivent etre corrects (long = -zTP, short = zTP)."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[3.5],
            cointegration_min=[40],
            zscore_tp=[-1.0],
            pnl_stop_loss=[-800],
        )
        v = gen()[0]
        ov = v["overrides"]
        # zTP=-1.0 -> long sort quand Z >= 1.0, short sort quand Z <= -1.0
        assert ov["exit.zscore_tp_long"] == 1.0   # -(-1.0)
        assert ov["exit.zscore_tp_short"] == -1.0

    def test_default_tp_cap(self):
        """Sans pnl_take_profit_cap, defaut a [99999]."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[3.0],
            cointegration_min=[50],
            zscore_tp=[0.0],
            pnl_stop_loss=[-800],
        )
        v = gen()[0]
        assert v["TP_cap"] == 99999
        assert v["overrides"]["exit.pnl_take_profit"] == 99999

    def test_negative_sl_normalization(self):
        """Un SL positif doit etre converti en negatif."""
        gen = create_hybrid_entry_exit_generator(
            zscore_entry=[3.0],
            cointegration_min=[50],
            zscore_tp=[0.0],
            pnl_stop_loss=[1200],  # positif par erreur
        )
        v = gen()[0]
        assert v["overrides"]["exit.pnl_stop_loss"] == -1200
        assert v["SL"] == 1200  # meta = valeur absolue


# ============================================================================
# TESTS _hybrid_label_builder
# ============================================================================

class TestHybridLabelBuilder:
    """Tests du label builder hybrid."""

    def setup_method(self):
        self.builder = create_hybrid_label_builder()

    def test_label_without_tp_cap(self):
        """Label sans TPcap quand TP_cap=99999."""
        label = self.builder("b2640_zp20_cp24_adf26", {
            "zE": 3.5, "co": 40, "zTP": -1.0, "SL": 1200, "TP_cap": 99999
        })
        assert label == "b2640_zp20_cp24_adf26_zE3.5_co40_zTP-1.0_SL1200"
        assert "TPcap" not in label

    def test_label_with_tp_cap(self):
        """Label avec TPcap quand TP_cap != 99999."""
        label = self.builder("b3960_zp30_cp96_adf64", {
            "zE": 2.5, "co": 50, "zTP": 0.0, "SL": 2500, "TP_cap": 800
        })
        assert label == "b3960_zp30_cp96_adf64_zE2.5_co50_zTP0.0_SL2500_TPcap800"


# ============================================================================
# TESTS _hybrid_result_builder
# ============================================================================

class TestHybridResultBuilder:
    """Tests du result builder hybrid."""

    def setup_method(self):
        self.builder = create_hybrid_result_builder()
        self.ind_ov = {
            "indicators.beta_lookback": 2640,
            "indicators.zscore_period": 20,
            "indicators.correlation_period": 24,
            "indicators.adf_hurst_period": 26,
        }
        self.ee = {"zE": 3.5, "co": 40, "zTP": -1.0, "SL": 1200, "TP_cap": 99999}
        self.metrics = {
            "trades": 79, "long": 40, "short": 39,
            "win_rate": 73.4, "pnl_net": 25164.0, "pnl_avg": 318.5,
            "profit_factor": 1.34, "max_dd": -2696.0,
            "sharpe": 0.12, "sortino": 0.08,
        }

    def test_result_has_hybrid_columns(self):
        """Le resultat doit contenir zTP, SL, TP_cap (pas zSL)."""
        r = self.builder("test_label", self.ind_ov, self.ee, self.metrics, 60, 5, 0, 14)
        assert r["zTP"] == -1.0
        assert r["SL"] == 1200
        assert r["TP_cap"] == 99999
        assert "zSL" not in r

    def test_result_exit_counts(self):
        """Les compteurs de sortie doivent etre passes correctement."""
        r = self.builder("test_label", self.ind_ov, self.ee, self.metrics, 60, 5, 0, 14)
        assert r["tp_zscore"] == 60
        assert r["tp_dollar"] == 5
        assert r["sl_zscore"] == 0
        assert r["sl_dollar"] == 14

    def test_result_calmar_zero_dd(self):
        """Calmar doit etre 0 si max_dd == 0."""
        self.metrics["max_dd"] = 0
        r = self.builder("test_label", self.ind_ov, self.ee, self.metrics, 0, 0, 0, 0)
        assert r["calmar"] == 0
