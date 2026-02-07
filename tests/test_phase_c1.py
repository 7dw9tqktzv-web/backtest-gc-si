# ============================================================================
# TEST_PHASE_C1.PY - Tests du walk-forward diagnostique Phase C1
# ============================================================================

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from phase_c1_walkforward import csv_row_to_overrides, build_windows


# ============================================================================
# TESTS csv_row_to_overrides
# ============================================================================

class TestCsvRowToOverrides:
    """Tests des conventions de signe."""

    def test_signs_ztp_negative(self):
        """zTP=-1.0 -> tp_long=+1.0, tp_short=-1.0 (overshoot)."""
        row = {"beta": 2640, "zp": 24, "cp": 24, "adf": 26,
               "zE": 3.5, "co": 40, "zTP": -1.0, "zSL": 4.5}
        ov = csv_row_to_overrides(row)
        assert ov["entry.zscore_long"] == -3.5
        assert ov["entry.zscore_short"] == 3.5
        assert ov["exit.zscore_tp_long"] == 1.0      # -(-1.0)
        assert ov["exit.zscore_tp_short"] == -1.0
        assert ov["exit.zscore_sl_long"] == -4.5
        assert ov["exit.zscore_sl_short"] == 4.5

    def test_signs_ztp_zero(self):
        """zTP=0.0 -> tp_long=0.0, tp_short=0.0."""
        row = {"beta": 2640, "zp": 24, "cp": 24, "adf": 26,
               "zE": 3.5, "co": 40, "zTP": 0.0, "zSL": 4.5}
        ov = csv_row_to_overrides(row)
        assert ov["exit.zscore_tp_long"] == 0.0
        assert ov["exit.zscore_tp_short"] == 0.0

    def test_signs_ztp_positive(self):
        """zTP=0.5 -> tp_long=-0.5, tp_short=0.5."""
        row = {"beta": 5280, "zp": 20, "cp": 24, "adf": 96,
               "zE": 2.5, "co": 60, "zTP": 0.5, "zSL": 5.0}
        ov = csv_row_to_overrides(row)
        assert ov["exit.zscore_tp_long"] == -0.5
        assert ov["exit.zscore_tp_short"] == 0.5

    def test_dollar_exits_disabled(self):
        """Mode zscore pur : dollar exits desactives."""
        row = {"beta": 2640, "zp": 24, "cp": 24, "adf": 26,
               "zE": 3.5, "co": 40, "zTP": 0.0, "zSL": 4.5}
        ov = csv_row_to_overrides(row)
        assert ov["exit.pnl_take_profit"] == 99999
        assert ov["exit.pnl_stop_loss"] == -99999


# ============================================================================
# TESTS build_windows
# ============================================================================

class TestBuildWindows:
    """Tests de la construction des fenetres."""

    @pytest.fixture
    def mock_df_5min(self):
        """DataFrame 5min synthetique (1500 barres)."""
        dates = pd.date_range("2023-01-26", periods=1500, freq="5min")
        return pd.DataFrame({"DateTime": dates, "Last_GC": 1900.0, "Last_SI": 23.0})

    def test_window_count(self, mock_df_5min):
        """15 fenetres exactement."""
        windows = build_windows(mock_df_5min)
        assert len(windows) == 15

    def test_windows_cover_all_bars(self, mock_df_5min):
        """Les fenetres couvrent toutes les barres sans trou."""
        windows = build_windows(mock_df_5min)
        total = sum(w["bars"] for w in windows)
        assert total == len(mock_df_5min)

    def test_windows_no_overlap(self, mock_df_5min):
        """Pas de chevauchement entre fenetres consecutives."""
        windows = build_windows(mock_df_5min)
        for i in range(len(windows) - 1):
            assert windows[i]["end_idx"] == windows[i + 1]["start_idx"]

    def test_windows_equal_size(self, mock_df_5min):
        """Tailles similaires (ecart max = derniere fenetre)."""
        windows = build_windows(mock_df_5min)
        sizes = [w["bars"] for w in windows]
        # Toutes sauf la derniere ont la meme taille
        assert len(set(sizes[:-1])) == 1
