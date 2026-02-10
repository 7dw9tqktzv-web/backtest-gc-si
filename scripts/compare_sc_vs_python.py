"""
Compare Sierra Chart vs Python indicator values across the full 5-min dataset.
Produces a comprehensive report on coverage, per-indicator stats, entry signals,
trade state comparison, and worst divergence bars.
"""
import sys
import os
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_loader import load_and_prepare_data, resample_to_5min
from indicators import calculate_all_indicators

# ============================================================================
# 1. LOAD SIERRA CHART DATA
# ============================================================================
print("=" * 80)
print("SIERRA CHART vs PYTHON INDICATOR COMPARISON")
print("=" * 80)

t0 = time.time()

sc_path = os.path.join(os.path.dirname(__file__), '..', 'DOC SIERRA', 'files', 'DefaultSpreadsheetStudy.txt')
print(f"\nLoading SC data from: {sc_path}")

# Read tab-separated, skip header line 1, header on line 2
rows = []
with open(sc_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 0 = title, Line 1 = header, Lines 2+ = data
print(f"  Total lines: {len(lines)}")

for i, line in enumerate(lines[2:], start=3):
    parts = line.strip().split('\t')
    if len(parts) < 50:
        continue
    try:
        dt = parts[0].strip()
        last_gc = parts[4].strip()
        spread_mean = parts[26].strip()
        zscore = parts[29].strip()
        correlation = parts[33].strip()
        adf_stat = parts[36].strip()
        hurst = parts[38].strip()
        half_life = parts[40].strip()
        coint_score = parts[42].strip()
        beta = parts[43].strip()
        trade_state = parts[49].strip()

        rows.append({
            'DateTime': dt,
            'SC_Last_GC': float(last_gc) if last_gc else np.nan,
            'SC_Spread_Mean': float(spread_mean) if spread_mean else np.nan,
            'SC_ZScore': float(zscore) if zscore else np.nan,
            'SC_Correlation': float(correlation) if correlation else np.nan,
            'SC_ADF': float(adf_stat) if adf_stat else np.nan,
            'SC_Hurst': float(hurst) if hurst else np.nan,
            'SC_HalfLife': float(half_life) if half_life else np.nan,
            'SC_CointScore': float(coint_score) if coint_score else np.nan,
            'SC_Beta': float(beta) if beta else np.nan,
            'SC_TradeState': float(trade_state) if trade_state else np.nan,
        })
    except (ValueError, IndexError):
        continue

sc = pd.DataFrame(rows)
sc['DateTime'] = pd.to_datetime(sc['DateTime'])
sc = sc.sort_values('DateTime').reset_index(drop=True)
sc = sc.set_index('DateTime')

print(f"  Parsed SC rows: {len(sc)}")
print(f"  SC date range: {sc.index.min()} to {sc.index.max()}")

# ============================================================================
# 2. LOAD PYTHON DATA
# ============================================================================
print("\nLoading Python data...")
df_1min, config, _ = load_and_prepare_data(verbose=False)
df_5min = resample_to_5min(df_1min, verbose=False)
df_5min = calculate_all_indicators(df_5min, config, verbose=False)

df_5min = df_5min.set_index('DateTime')
print(f"  Python 5-min bars: {len(df_5min)}")
print(f"  Python date range: {df_5min.index.min()} to {df_5min.index.max()}")

# ============================================================================
# 3. MERGE ON DATETIME
# ============================================================================
print("\nMerging on DateTime index...")

# Rename Python columns for clarity
py = df_5min[['Last_GC', 'Spread_Mean', 'ZScore', 'Correlation',
              'ADF_Statistic', 'Hurst', 'HalfLife', 'Cointegration_Score', 'Beta']].copy()
py.columns = ['PY_Last_GC', 'PY_Spread_Mean', 'PY_ZScore', 'PY_Correlation',
              'PY_ADF', 'PY_Hurst', 'PY_HalfLife', 'PY_CointScore', 'PY_Beta']

merged = sc.join(py, how='inner')
print(f"  Overlapping bars: {len(merged)}")
print(f"  Overlap range: {merged.index.min()} to {merged.index.max()}")

# ============================================================================
# 4. PER-INDICATOR COMPARISON
# ============================================================================
print("\n" + "=" * 80)
print("PER-INDICATOR STATISTICS (on overlapping non-NaN bars)")
print("=" * 80)

indicators = [
    ('Z-Score',      'SC_ZScore',     'PY_ZScore'),
    ('Beta',         'SC_Beta',       'PY_Beta'),
    ('Correlation',  'SC_Correlation', 'PY_Correlation'),
    ('ADF Statistic','SC_ADF',        'PY_ADF'),
    ('Hurst',        'SC_Hurst',      'PY_Hurst'),
    ('Coint Score',  'SC_CointScore', 'PY_CointScore'),
    ('Half-Life',    'SC_HalfLife',   'PY_HalfLife'),
    ('Spread Mean',  'SC_Spread_Mean','PY_Spread_Mean'),
]

print(f"\n{'Indicator':<16} {'N bars':>8} {'Mean|D|':>12} {'Max|D|':>12} {'Med|D|':>12} {'Pearson r':>12} {'%<0.01':>8}")
print("-" * 80)

for name, sc_col, py_col in indicators:
    mask = merged[sc_col].notna() & merged[py_col].notna()
    # Filter out SC placeholder values (0.5 for Hurst means "line at 0.5", skip)
    if name == 'Hurst':
        mask &= (merged[sc_col] != 0.5)
    n = mask.sum()
    if n == 0:
        print(f"{name:<16} {'0':>8} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>8}")
        continue
    delta = (merged.loc[mask, sc_col] - merged.loc[mask, py_col]).abs()
    corr = merged.loc[mask, sc_col].corr(merged.loc[mask, py_col])
    pct_small = (delta < 0.01).mean() * 100
    print(f"{name:<16} {n:>8} {delta.mean():>12.6f} {delta.max():>12.6f} {delta.median():>12.6f} {corr:>12.8f} {pct_small:>7.1f}%")

# ============================================================================
# 5. ENTRY SIGNAL COMPARISON
# ============================================================================
print("\n" + "=" * 80)
print("ENTRY SIGNAL COMPARISON")
print("=" * 80)

def find_entries(zscore, coint, corr, prefix):
    """Find bars where entry conditions are met."""
    mask_valid = zscore.notna() & coint.notna() & corr.notna()
    mask_qual = (coint >= 40) & (corr >= 0.6)
    mask_long = (zscore <= -3.5) & mask_qual & mask_valid
    mask_short = (zscore >= 3.5) & mask_qual & mask_valid
    return mask_long, mask_short

sc_long, sc_short = find_entries(merged['SC_ZScore'], merged['SC_CointScore'], merged['SC_Correlation'], 'SC')
py_long, py_short = find_entries(merged['PY_ZScore'], merged['PY_CointScore'], merged['PY_Correlation'], 'PY')

print(f"\nLONG entry signals (Z <= -3.5, Coint >= 40, Corr >= 0.6):")
print(f"  SC: {sc_long.sum()}, Python: {py_long.sum()}")
print(f"  Both agree LONG:    {(sc_long & py_long).sum()}")
print(f"  SC only (not PY):   {(sc_long & ~py_long).sum()}")
print(f"  PY only (not SC):   {(~sc_long & py_long).sum()}")

print(f"\nSHORT entry signals (Z >= 3.5, Coint >= 40, Corr >= 0.6):")
print(f"  SC: {sc_short.sum()}, Python: {py_short.sum()}")
print(f"  Both agree SHORT:   {(sc_short & py_short).sum()}")
print(f"  SC only (not PY):   {(sc_short & ~py_short).sum()}")
print(f"  PY only (not SC):   {(~sc_short & py_short).sum()}")

# Show some divergent bars
for label, sc_mask, py_mask in [("LONG", sc_long, py_long), ("SHORT", sc_short, py_short)]:
    divergent = (sc_mask & ~py_mask) | (~sc_mask & py_mask)
    if divergent.sum() > 0:
        print(f"\n  First 5 divergent {label} signals:")
        div_idx = merged.index[divergent][:5]
        for dt in div_idx:
            row = merged.loc[dt]
            print(f"    {dt}  SC_Z={row['SC_ZScore']:.4f} PY_Z={row['PY_ZScore']:.4f}  "
                  f"SC_Co={row['SC_CointScore']:.1f} PY_Co={row['PY_CointScore']:.1f}  "
                  f"SC_Cr={row['SC_Correlation']:.4f} PY_Cr={row['PY_Correlation']:.4f}")

# ============================================================================
# 6. TRADE STATE COMPARISON
# ============================================================================
print("\n" + "=" * 80)
print("TRADE STATE COMPARISON (SC col[49] vs Python backtest)")
print("=" * 80)

# Run Python backtest to get trade states
# We'll use the hybrid backtest engine
try:
    from backtest_engine_hybrid import run_hybrid_backtest
    from data_loader import load_5s_data

    print("\nRunning Python hybrid backtest for trade state comparison...")
    # Engine expects DataFrame without DateTime as index
    df_5min_reset = df_5min.reset_index()
    df_5s = load_5s_data(config, verbose=False)
    trades_df = run_hybrid_backtest(df_5min_reset, df_5s, config, verbose=False)

    # Build Python trade state series from trades
    # State: 0=FLAT, 1=LONG, -1=SHORT, 2=COOL_L, -2=COOL_S
    # We don't have bar-by-bar state from the engine, so we approximate from trades
    py_state = pd.Series(0.0, index=df_5min.index, name='PY_TradeState')

    for _, trade in trades_df.iterrows():
        entry_dt = trade.get('Entry_DateTime') or trade.get('entry_datetime')
        exit_dt = trade.get('Exit_DateTime') or trade.get('exit_datetime')
        direction = trade.get('Direction') or trade.get('direction')
        if pd.isna(entry_dt) or pd.isna(exit_dt):
            continue
        state_val = 1.0 if direction == 'LONG' else -1.0
        mask = (df_5min.index >= entry_dt) & (df_5min.index <= exit_dt)
        py_state.loc[mask] = state_val

    # Compare on overlapping bars where SC has trade state
    merged['PY_TradeState'] = py_state
    ts_mask = merged['SC_TradeState'].notna() & merged['PY_TradeState'].notna()
    ts_df = merged.loc[ts_mask, ['SC_TradeState', 'PY_TradeState']]

    # Simplify: compare position direction (ignore cooldown distinction)
    sc_dir = ts_df['SC_TradeState'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    py_dir = ts_df['PY_TradeState'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

    match = (sc_dir == py_dir).sum()
    total = len(ts_df)
    print(f"\n  Total bars compared: {total}")
    print(f"  Direction matches:   {match} ({match/total*100:.2f}%)")
    print(f"  Direction mismatches: {total - match} ({(total-match)/total*100:.2f}%)")

    # Breakdown of SC states
    print(f"\n  SC Trade State distribution:")
    for val, label in [(0, 'FLAT'), (1, 'LONG'), (-1, 'SHORT'), (2, 'COOL_L'), (-2, 'COOL_S')]:
        n = (ts_df['SC_TradeState'] == val).sum()
        print(f"    {label:>8}: {n:>6} bars ({n/total*100:.2f}%)")

    # Show mismatched bars
    mismatch_mask = sc_dir != py_dir
    if mismatch_mask.sum() > 0:
        print(f"\n  First 10 mismatched bars:")
        mis_idx = ts_df.index[mismatch_mask][:10]
        for dt in mis_idx:
            row = merged.loc[dt]
            print(f"    {dt}  SC_State={row['SC_TradeState']:.0f}  PY_State={row['PY_TradeState']:.0f}  "
                  f"Z={row['SC_ZScore']:.3f}  Co={row['SC_CointScore']:.1f}")

except Exception as e:
    print(f"\n  [SKIP] Could not run trade state comparison: {e}")

# ============================================================================
# 7. WORST DIVERGENCE BARS (Coint Score)
# ============================================================================
print("\n" + "=" * 80)
print("TOP 10 WORST COINT SCORE DIVERGENCES")
print("=" * 80)

mask_coint = merged['SC_CointScore'].notna() & merged['PY_CointScore'].notna()
coint_df = merged.loc[mask_coint].copy()
coint_df['CointDelta'] = (coint_df['SC_CointScore'] - coint_df['PY_CointScore']).abs()
worst = coint_df.nlargest(10, 'CointDelta')

print(f"\n{'DateTime':<22} {'SC_Coint':>10} {'PY_Coint':>10} {'Delta':>10} {'SC_Z':>10} {'PY_Z':>10} {'Z_Delta':>10}")
print("-" * 84)
for dt, row in worst.iterrows():
    z_delta = abs(row['SC_ZScore'] - row['PY_ZScore']) if pd.notna(row['PY_ZScore']) else np.nan
    print(f"{str(dt):<22} {row['SC_CointScore']:>10.2f} {row['PY_CointScore']:>10.2f} "
          f"{row['CointDelta']:>10.2f} {row['SC_ZScore']:>10.4f} {row['PY_ZScore']:>10.4f} {z_delta:>10.4f}")

# Also show worst Z-Score divergences
print("\n" + "=" * 80)
print("TOP 10 WORST Z-SCORE DIVERGENCES")
print("=" * 80)

mask_z = merged['SC_ZScore'].notna() & merged['PY_ZScore'].notna()
z_df = merged.loc[mask_z].copy()
z_df['ZDelta'] = (z_df['SC_ZScore'] - z_df['PY_ZScore']).abs()
worst_z = z_df.nlargest(10, 'ZDelta')

print(f"\n{'DateTime':<22} {'SC_Z':>10} {'PY_Z':>10} {'Delta':>10} {'SC_Beta':>10} {'PY_Beta':>10}")
print("-" * 74)
for dt, row in worst_z.iterrows():
    print(f"{str(dt):<22} {row['SC_ZScore']:>10.4f} {row['PY_ZScore']:>10.4f} "
          f"{row['ZDelta']:>10.4f} {row['SC_Beta']:>10.4f} {row['PY_Beta']:>10.4f}")

elapsed = time.time() - t0
print(f"\n{'=' * 80}")
print(f"Comparison completed in {elapsed:.1f}s")
print(f"{'=' * 80}")
