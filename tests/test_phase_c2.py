# ============================================================================
# TEST_PHASE_C2.PY - Tests des filtres de regime Phase C2
# ============================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from phase_c2_multifilter_exploration import (
    realized_vol,
    rolling_adf,
    rolling_halflife,
    rolling_correlation,
    rolling_slope,
)


class TestRealizedVol:
    def test_constant_spread_zero_vol(self):
        """Spread constant -> vol = 0."""
        spread = pd.Series([100.0] * 50, index=pd.date_range("2024-01-01", periods=50))
        vol = realized_vol(spread, 20)
        assert vol.iloc[-1] == 0.0


class TestRollingAdf:
    def test_stationary_white_noise(self):
        """Bruit blanc -> ADF tres negatif (stationnaire)."""
        np.random.seed(42)
        noise = pd.Series(np.random.randn(100), index=pd.date_range("2024-01-01", periods=100))
        adf = rolling_adf(noise, 40)
        last_valid = adf.dropna().iloc[-1]
        assert last_valid < -2.0, f"ADF should be very negative for white noise, got {last_valid}"

    def test_random_walk_less_negative(self):
        """Random walk -> ADF proche de 0."""
        np.random.seed(42)
        rw = pd.Series(np.cumsum(np.random.randn(100)), index=pd.date_range("2024-01-01", periods=100))
        adf = rolling_adf(rw, 40)
        last_valid = adf.dropna().iloc[-1]
        assert last_valid > -3.0, f"ADF should be near 0 for random walk, got {last_valid}"


class TestRollingHalflife:
    def test_mean_reverting_ar1(self):
        """AR(1) avec b=0.9 -> half-life ~ 6.6 jours."""
        np.random.seed(42)
        n = 200
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.9 * x[i - 1] + np.random.randn() * 0.1
        spread = pd.Series(x, index=pd.date_range("2024-01-01", periods=n))
        hl = rolling_halflife(spread, 60)
        last_valid = hl.dropna().iloc[-1]
        expected = -np.log(2) / np.log(0.9)  # ~6.58
        assert 3 < last_valid < 15, f"Half-life should be ~6.6, got {last_valid}"


class TestRollingSlope:
    def test_flat_spread_zero_slope(self):
        """Spread constant -> slope = 0."""
        spread = pd.Series([50.0] * 50, index=pd.date_range("2024-01-01", periods=50))
        slope = rolling_slope(spread, 20)
        last_valid = slope.dropna().iloc[-1]
        assert abs(last_valid) < 1e-10
