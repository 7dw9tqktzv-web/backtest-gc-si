"""
Standalone cointegration screening for any pair of Sierra Chart CSV exports.

Usage:
    python scripts/explore_cointegration.py data/raw/CL.txt data/raw/HO.txt
    python scripts/explore_cointegration.py data/raw/CL.txt data/raw/RB.txt --period 5min

Zero imports from src/ -- uses only numpy, pandas, statsmodels.
If screening says NO-GO, nothing in the project was touched.

GO/NO-GO thresholds:
    ADF < -2.86 for >50% of rolling windows  (GO)
    Hurst mean < 0.50                         (GO)
    Half-life < 50 bars (at chosen period)    (GO)
    Correlation rolling mean > 0.70           (GO)
    Correlation rolling P5 > 0.50             (GO)
"""

import argparse
import sys
import numpy as np
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# GO/NO-GO thresholds
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "adf_pct_significant": 0.50,   # >50% of rolling windows with ADF < -2.86
    "adf_critical": -2.86,         # 5% critical value (approx)
    "hurst_mean_max": 0.50,
    "half_life_max_bars": 50,      # bars at chosen period
    "corr_mean_min": 0.70,
    "corr_p5_min": 0.50,
}


# ---------------------------------------------------------------------------
# Data loading (standalone, mirrors SC CSV format)
# ---------------------------------------------------------------------------
def load_sc_csv(filepath: str) -> pd.DataFrame:
    """Load a Sierra Chart 'Bar Data to Text File' export."""
    df = pd.read_csv(filepath, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    df = df.drop(columns=['Date', 'Time'])
    df = df.sort_values('DateTime').reset_index(drop=True)
    return df


def synchronize(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    """Inner join on DateTime, suffixes _L1 / _L2."""
    merged = pd.merge(df1, df2, on='DateTime', how='inner', suffixes=('_L1', '_L2'))
    merged = merged.sort_values('DateTime').reset_index(drop=True)
    return merged


def resample_to_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Resample 1-min bars to the target period."""
    if period == "1min":
        return df
    df_idx = df.set_index('DateTime')
    agg = {
        'Open_L1': 'first', 'High_L1': 'max', 'Low_L1': 'min', 'Last_L1': 'last',
        'Open_L2': 'first', 'High_L2': 'max', 'Low_L2': 'min', 'Last_L2': 'last',
    }
    # Only aggregate columns that exist
    agg = {k: v for k, v in agg.items() if k in df_idx.columns}
    freq_map = {"5min": "5min", "15min": "15min", "1h": "1h", "1d": "1D"}
    freq = freq_map.get(period, period)
    resampled = df_idx.resample(freq).agg(agg).dropna()
    resampled = resampled.reset_index()
    return resampled


# ---------------------------------------------------------------------------
# Statistical tests (standalone implementations)
# ---------------------------------------------------------------------------
def rolling_ols_beta(log_l1: np.ndarray, log_l2: np.ndarray, window: int) -> np.ndarray:
    """Rolling OLS beta: log_l2 = alpha + beta * log_l1 + epsilon."""
    n = len(log_l1)
    beta = np.full(n, np.nan)
    for i in range(window - 1, n):
        x = log_l1[i - window + 1:i + 1]
        y = log_l2[i - window + 1:i + 1]
        x_mean = x.mean()
        y_mean = y.mean()
        cov = ((x - x_mean) * (y - y_mean)).sum()
        var = ((x - x_mean) ** 2).sum()
        if var > 0:
            beta[i] = cov / var
    return beta


def rolling_spread_zscore(log_l1: np.ndarray, log_l2: np.ndarray,
                          beta: np.ndarray, zscore_period: int) -> np.ndarray:
    """Spread = log_l2 - beta * log_l1, then Z-Score on rolling window."""
    n = len(log_l1)
    # Alpha rolling (mean of spread over beta window)
    spread_raw = log_l2 - beta * log_l1
    zscore = np.full(n, np.nan)
    for i in range(zscore_period - 1, n):
        window = spread_raw[i - zscore_period + 1:i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) >= 5:
            zscore[i] = (valid[-1] - valid.mean()) / (valid.std(ddof=1) + 1e-12)
    return zscore


def adf_test(series: np.ndarray) -> float:
    """Augmented Dickey-Fuller test statistic (statsmodels)."""
    from statsmodels.tsa.stattools import adfuller
    try:
        result = adfuller(series, maxlag=1, regression='c')
        return result[0]  # test statistic
    except Exception:
        return 0.0


def rolling_adf(spread: np.ndarray, window: int, step: int = 1) -> np.ndarray:
    """Rolling ADF test statistic on spread."""
    n = len(spread)
    adf_stats = np.full(n, np.nan)
    for i in range(window - 1, n, step):
        seg = spread[i - window + 1:i + 1]
        valid = seg[~np.isnan(seg)]
        if len(valid) >= window * 0.8:
            adf_stats[i] = adf_test(valid)
    # Forward-fill for skipped steps
    if step > 1:
        last_valid = np.nan
        for i in range(n):
            if not np.isnan(adf_stats[i]):
                last_valid = adf_stats[i]
            else:
                adf_stats[i] = last_valid
    return adf_stats


def compute_hurst(series: np.ndarray) -> float:
    """Hurst exponent via R/S analysis."""
    n = len(series)
    if n < 20:
        return np.nan

    max_k = int(np.floor(n / 4))
    if max_k < 4:
        return np.nan

    # Sub-period sizes: powers of 2 that fit
    sizes = []
    s = 4
    while s <= max_k:
        sizes.append(s)
        s *= 2
    if len(sizes) < 2:
        return np.nan

    rs_means = []
    for size in sizes:
        n_chunks = n // size
        rs_values = []
        for j in range(n_chunks):
            chunk = series[j * size:(j + 1) * size]
            mean_c = chunk.mean()
            deviations = np.cumsum(chunk - mean_c)
            r = deviations.max() - deviations.min()
            s_val = chunk.std(ddof=0)
            if s_val > 1e-12:
                rs_values.append(r / s_val)
        if rs_values:
            rs_means.append(np.mean(rs_values))
        else:
            rs_means.append(np.nan)

    # Log-log regression
    valid = [(s, rs) for s, rs in zip(sizes, rs_means) if not np.isnan(rs) and rs > 0]
    if len(valid) < 2:
        return np.nan

    log_sizes = np.log(np.array([v[0] for v in valid]))
    log_rs = np.log(np.array([v[1] for v in valid]))
    # Simple linear regression
    x_mean = log_sizes.mean()
    y_mean = log_rs.mean()
    cov = ((log_sizes - x_mean) * (log_rs - y_mean)).sum()
    var = ((log_sizes - x_mean) ** 2).sum()
    if var > 0:
        return cov / var
    return np.nan


def rolling_hurst(spread: np.ndarray, window: int, step: int = 10) -> np.ndarray:
    """Rolling Hurst exponent on spread."""
    n = len(spread)
    hurst = np.full(n, np.nan)
    for i in range(window - 1, n, step):
        seg = spread[i - window + 1:i + 1]
        valid = seg[~np.isnan(seg)]
        if len(valid) >= window * 0.8:
            hurst[i] = compute_hurst(valid)
    # Forward-fill
    if step > 1:
        last_valid = np.nan
        for i in range(n):
            if not np.isnan(hurst[i]):
                last_valid = hurst[i]
            else:
                hurst[i] = last_valid
    return hurst


def compute_half_life(spread: np.ndarray) -> float:
    """Half-life of mean reversion via AR(1) regression."""
    spread_clean = spread[~np.isnan(spread)]
    if len(spread_clean) < 30:
        return np.nan
    lag = spread_clean[:-1]
    diff = np.diff(spread_clean)
    # diff = phi * lag + const
    x = np.column_stack([lag, np.ones(len(lag))])
    try:
        result = np.linalg.lstsq(x, diff, rcond=None)
        phi = result[0][0]
        if phi >= 0:
            return np.inf  # not mean reverting
        return -np.log(2) / phi
    except Exception:
        return np.nan


def rolling_correlation(l1: np.ndarray, l2: np.ndarray, window: int) -> np.ndarray:
    """Rolling Pearson correlation between log prices."""
    n = len(l1)
    corr = np.full(n, np.nan)
    for i in range(window - 1, n):
        x = l1[i - window + 1:i + 1]
        y = l2[i - window + 1:i + 1]
        valid = ~(np.isnan(x) | np.isnan(y))
        if valid.sum() >= 10:
            xv = x[valid]
            yv = y[valid]
            corr[i] = np.corrcoef(xv, yv)[0, 1]
    return corr


# ---------------------------------------------------------------------------
# Main screening
# ---------------------------------------------------------------------------
def screen_pair(file_l1: str, file_l2: str, period: str = "5min",
                beta_lookback: int = 2640, zscore_period: int = 28,
                corr_period: int = 252, adf_window: int = 500,
                hurst_window: int = 500, no_log: bool = False,
                verbose: bool = True) -> dict:
    """
    Full cointegration screening for a pair.

    Returns dict with all metrics and GO/NO-GO verdict.
    """
    name_l1 = Path(file_l1).stem.split('_')[0]
    name_l2 = Path(file_l2).stem.split('_')[0]
    pair_name = f"{name_l1}/{name_l2}"

    if verbose:
        print(f"\n{'='*70}")
        print(f"  COINTEGRATION SCREENING: {pair_name}")
        print(f"  Period: {period} | Beta: {beta_lookback} | Z-Score: {zscore_period}")
        print(f"{'='*70}")

    # --- Load data ---
    if verbose:
        print(f"\n[1/7] Loading {name_l1}...")
    df1 = load_sc_csv(file_l1)
    if verbose:
        print(f"       {len(df1):,} bars loaded ({df1['DateTime'].iloc[0]} to {df1['DateTime'].iloc[-1]})")
        print(f"[1/7] Loading {name_l2}...")
    df2 = load_sc_csv(file_l2)
    if verbose:
        print(f"       {len(df2):,} bars loaded ({df2['DateTime'].iloc[0]} to {df2['DateTime'].iloc[-1]})")

    # --- Synchronize ---
    if verbose:
        print(f"\n[2/7] Synchronizing...")
    df = synchronize(df1, df2)
    sync_ratio = len(df) / max(len(df1), len(df2)) * 100
    if verbose:
        print(f"       {len(df):,} synchronized bars ({sync_ratio:.1f}% of largest leg)")

    # --- Liquidity analysis (on 1-min before resampling) ---
    if verbose:
        print(f"\n[2b/7] Liquidity analysis (1-min bars)...")
    df_liq = df.copy()
    df_liq['date'] = df_liq['DateTime'].dt.date
    df_liq['hour'] = df_liq['DateTime'].dt.hour

    bars_per_day = df_liq.groupby('date').size()
    hourly_dist = df_liq.groupby('hour').size()
    total_bars = hourly_dist.sum()

    liquidity_stats = {
        "bars_per_day_mean": float(bars_per_day.mean()),
        "bars_per_day_median": float(bars_per_day.median()),
        "bars_per_day_p5": float(bars_per_day.quantile(0.05)),
        "bars_per_day_p95": float(bars_per_day.quantile(0.95)),
        "n_trading_days": len(bars_per_day),
        "hourly_distribution": {int(h): int(c) for h, c in hourly_dist.items()},
    }

    if verbose:
        print(f"       Trading days: {liquidity_stats['n_trading_days']}")
        print(f"       Bars/day: mean={bars_per_day.mean():.0f}, median={bars_per_day.median():.0f}, "
              f"P5={bars_per_day.quantile(0.05):.0f}, P95={bars_per_day.quantile(0.95):.0f}")
        print(f"       Hourly distribution (CT, % of total bars):")
        for h in sorted(hourly_dist.index):
            pct = hourly_dist[h] / total_bars * 100
            bar = "#" * int(pct)
            print(f"         {h:02d}:00  {pct:5.1f}%  {bar}")

    del df_liq

    # --- Resample ---
    if period != "1min":
        if verbose:
            print(f"\n[3/7] Resampling to {period}...")
        df = resample_to_period(df, period)
        if verbose:
            print(f"       {len(df):,} bars after resampling")
    else:
        if verbose:
            print(f"\n[3/7] No resampling (1min)")

    # --- Compute prices (log or raw) ---
    if no_log:
        log_l1 = df['Last_L1'].values.astype(float)
        log_l2 = df['Last_L2'].values.astype(float)
        if verbose:
            print(f"       Mode: raw prices (--no-log)")
    else:
        log_l1 = np.log(df['Last_L1'].values.astype(float))
        log_l2 = np.log(df['Last_L2'].values.astype(float))
    n = len(log_l1)

    # --- Rolling Beta ---
    if verbose:
        print(f"\n[4/7] Rolling OLS Beta (lookback={beta_lookback})...")
    beta = rolling_ols_beta(log_l1, log_l2, beta_lookback)

    # --- Spread ---
    # Alpha: rolling mean of (log_l2 - beta * log_l1) over beta_lookback
    spread_raw = log_l2 - beta * log_l1
    alpha = np.full(n, np.nan)
    for i in range(beta_lookback - 1, n):
        seg = spread_raw[i - beta_lookback + 1:i + 1]
        valid = seg[~np.isnan(seg)]
        if len(valid) > 0:
            alpha[i] = valid.mean()
    spread = log_l2 - beta * log_l1 - alpha
    valid_spread = spread[~np.isnan(spread)]

    if verbose:
        print(f"       Spread computed: {len(valid_spread):,} valid values")
        print(f"       Beta range: [{np.nanmin(beta):.4f}, {np.nanmax(beta):.4f}], mean={np.nanmean(beta):.4f}")

    # --- Rolling ADF ---
    if verbose:
        print(f"\n[5/7] Rolling ADF (window={adf_window}, step=50)...")
    adf_stats = rolling_adf(spread, adf_window, step=50)
    valid_adf = adf_stats[~np.isnan(adf_stats)]
    pct_significant = (valid_adf < THRESHOLDS["adf_critical"]).mean() if len(valid_adf) > 0 else 0.0

    if verbose:
        print(f"       ADF mean: {np.nanmean(valid_adf):.3f}")
        print(f"       ADF < {THRESHOLDS['adf_critical']}: {pct_significant:.1%} of windows")

    # --- Rolling Hurst ---
    if verbose:
        print(f"\n[5/7] Rolling Hurst (window={hurst_window}, step=50)...")
    hurst = rolling_hurst(spread, hurst_window, step=50)
    valid_hurst = hurst[~np.isnan(hurst)]
    hurst_mean = np.nanmean(valid_hurst) if len(valid_hurst) > 0 else np.nan

    if verbose:
        print(f"       Hurst mean: {hurst_mean:.4f}")
        print(f"       Hurst < 0.50: {(valid_hurst < 0.50).mean():.1%}" if len(valid_hurst) > 0 else "       No data")

    # --- Half-life ---
    if verbose:
        print(f"\n[6/7] Half-life of mean reversion...")
    half_life = compute_half_life(valid_spread)
    if verbose:
        if np.isinf(half_life):
            print(f"       Half-life: INF (not mean reverting)")
        else:
            print(f"       Half-life: {half_life:.1f} bars ({period})")

    # --- Rolling Correlation ---
    if verbose:
        print(f"\n[7/7] Rolling Correlation (window={corr_period})...")
    corr = rolling_correlation(log_l1, log_l2, corr_period)
    valid_corr = corr[~np.isnan(corr)]
    corr_mean = np.nanmean(valid_corr) if len(valid_corr) > 0 else np.nan
    corr_p5 = np.nanpercentile(valid_corr, 5) if len(valid_corr) > 0 else np.nan

    if verbose:
        print(f"       Correlation mean: {corr_mean:.4f}")
        print(f"       Correlation P5:   {corr_p5:.4f}")
        print(f"       Correlation min:  {np.nanmin(valid_corr):.4f}" if len(valid_corr) > 0 else "")

    # --- GO/NO-GO verdict ---
    results = {
        "pair": pair_name,
        "period": period,
        "n_bars": n,
        "n_valid_spread": len(valid_spread),
        "liquidity": liquidity_stats,
        "beta_mean": float(np.nanmean(beta)),
        "beta_std": float(np.nanstd(beta)),
        "adf_mean": float(np.nanmean(valid_adf)) if len(valid_adf) > 0 else None,
        "adf_pct_significant": float(pct_significant),
        "hurst_mean": float(hurst_mean) if not np.isnan(hurst_mean) else None,
        "half_life_bars": float(half_life) if not np.isinf(half_life) else None,
        "corr_mean": float(corr_mean) if not np.isnan(corr_mean) else None,
        "corr_p5": float(corr_p5) if not np.isnan(corr_p5) else None,
    }

    # Evaluate each criterion
    checks = {}
    checks["adf"] = pct_significant >= THRESHOLDS["adf_pct_significant"]
    checks["hurst"] = hurst_mean < THRESHOLDS["hurst_mean_max"] if not np.isnan(hurst_mean) else False
    checks["half_life"] = half_life < THRESHOLDS["half_life_max_bars"] if not np.isinf(half_life) else False
    checks["corr_mean"] = corr_mean >= THRESHOLDS["corr_mean_min"] if not np.isnan(corr_mean) else False
    checks["corr_p5"] = corr_p5 >= THRESHOLDS["corr_p5_min"] if not np.isnan(corr_p5) else False

    n_pass = sum(checks.values())
    n_total = len(checks)

    # NO-GO thresholds (hard fail)
    nogo_checks = {}
    nogo_checks["adf"] = pct_significant < 0.30
    nogo_checks["hurst"] = hurst_mean > 0.55 if not np.isnan(hurst_mean) else True
    nogo_checks["half_life"] = half_life > 100 if not np.isinf(half_life) else True
    nogo_checks["corr_mean"] = corr_mean < 0.50 if not np.isnan(corr_mean) else True
    nogo_checks["corr_p5"] = corr_p5 < 0.30 if not np.isnan(corr_p5) else True

    n_nogo = sum(nogo_checks.values())

    if n_nogo > 0:
        verdict = "NO-GO"
    elif n_pass == n_total:
        verdict = "GO"
    else:
        verdict = "GREY ZONE"

    results["checks"] = checks
    results["nogo_checks"] = nogo_checks
    results["verdict"] = verdict

    return results


def print_report(results: dict):
    """Print formatted screening report."""
    pair = results["pair"]
    verdict = results["verdict"]

    print(f"\n{'='*70}")
    print(f"  SCREENING REPORT: {pair}")
    print(f"  Period: {results['period']} | Bars: {results['n_bars']:,} | Valid spread: {results['n_valid_spread']:,}")
    print(f"{'='*70}")

    print(f"\n  Beta:        mean={results['beta_mean']:.4f}, std={results['beta_std']:.4f}")

    # Liquidity section
    liq = results.get("liquidity", {})
    if liq:
        print(f"\n  LIQUIDITY (1-min synchronized bars)")
        print(f"  Trading days:  {liq['n_trading_days']}")
        print(f"  Bars/day:      mean={liq['bars_per_day_mean']:.0f}, median={liq['bars_per_day_median']:.0f}, "
              f"P5={liq['bars_per_day_p5']:.0f}, P95={liq['bars_per_day_p95']:.0f}")
        hourly = liq.get("hourly_distribution", {})
        if hourly:
            total = sum(hourly.values())
            print(f"  Hourly distribution (CT):")
            for h in sorted(hourly.keys()):
                pct = hourly[h] / total * 100
                bar = "#" * int(pct)
                print(f"    {h:02d}:00  {pct:5.1f}%  {bar}")

    # Criteria table
    print(f"\n  {'Criterion':<25} {'Value':>10} {'GO Threshold':>15} {'Status':>10}")
    print(f"  {'-'*60}")

    rows = [
        ("ADF % significant",
         f"{results['adf_pct_significant']:.1%}" if results['adf_pct_significant'] is not None else "N/A",
         f">= {THRESHOLDS['adf_pct_significant']:.0%}",
         results['checks']['adf']),
        ("Hurst mean",
         f"{results['hurst_mean']:.4f}" if results['hurst_mean'] is not None else "N/A",
         f"< {THRESHOLDS['hurst_mean_max']:.2f}",
         results['checks']['hurst']),
        ("Half-life (bars)",
         f"{results['half_life_bars']:.1f}" if results['half_life_bars'] is not None else "INF",
         f"< {THRESHOLDS['half_life_max_bars']}",
         results['checks']['half_life']),
        ("Correlation mean",
         f"{results['corr_mean']:.4f}" if results['corr_mean'] is not None else "N/A",
         f">= {THRESHOLDS['corr_mean_min']:.2f}",
         results['checks']['corr_mean']),
        ("Correlation P5",
         f"{results['corr_p5']:.4f}" if results['corr_p5'] is not None else "N/A",
         f">= {THRESHOLDS['corr_p5_min']:.2f}",
         results['checks']['corr_p5']),
    ]

    for name, value, threshold, passed in rows:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<25} {value:>10} {threshold:>15} {status:>10}")

    n_pass = sum(results['checks'].values())
    n_total = len(results['checks'])

    print(f"\n  Score: {n_pass}/{n_total} criteria passed")

    if verdict == "GO":
        print(f"\n  >>> VERDICT: GO -- Pair is viable for mean reversion strategy <<<")
    elif verdict == "NO-GO":
        nogo_reasons = [k for k, v in results['nogo_checks'].items() if v]
        print(f"\n  >>> VERDICT: NO-GO -- Hard fail on: {', '.join(nogo_reasons)} <<<")
    else:
        print(f"\n  >>> VERDICT: GREY ZONE -- {n_pass}/{n_total} passed, decision humaine requise <<<")

    print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Standalone cointegration screening for any pair of SC CSV exports.",
        epilog="Example: python scripts/explore_cointegration.py data/raw/CL.txt data/raw/HO.txt"
    )
    parser.add_argument("file_l1", help="Path to leg 1 CSV (e.g. CL, GC, ES)")
    parser.add_argument("file_l2", help="Path to leg 2 CSV (e.g. HO, SI, RTY)")
    parser.add_argument("--period", default="5min", choices=["1min", "5min", "15min", "1h"],
                        help="Analysis period (default: 5min)")
    parser.add_argument("--beta-lookback", type=int, default=2640,
                        help="Beta OLS lookback in bars (default: 2640)")
    parser.add_argument("--zscore-period", type=int, default=28,
                        help="Z-Score rolling period in bars (default: 28)")
    parser.add_argument("--corr-period", type=int, default=252,
                        help="Correlation rolling window in bars (default: 252)")
    parser.add_argument("--adf-window", type=int, default=500,
                        help="ADF rolling window in bars (default: 500)")
    parser.add_argument("--hurst-window", type=int, default=500,
                        help="Hurst rolling window in bars (default: 500)")
    parser.add_argument("--no-log", action="store_true",
                        help="Use raw prices instead of log prices (for negative/back-adjusted data)")

    args = parser.parse_args()

    # Validate files exist
    for f in [args.file_l1, args.file_l2]:
        if not Path(f).exists():
            print(f"ERROR: File not found: {f}")
            sys.exit(1)

    results = screen_pair(
        file_l1=args.file_l1,
        file_l2=args.file_l2,
        period=args.period,
        beta_lookback=args.beta_lookback,
        zscore_period=args.zscore_period,
        corr_period=args.corr_period,
        adf_window=args.adf_window,
        hurst_window=args.hurst_window,
        no_log=args.no_log,
    )

    print_report(results)

    # Exit code: 0=GO, 1=NO-GO, 2=GREY
    if results["verdict"] == "GO":
        sys.exit(0)
    elif results["verdict"] == "NO-GO":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
