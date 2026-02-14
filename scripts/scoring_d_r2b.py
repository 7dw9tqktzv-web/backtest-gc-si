#!/usr/bin/env python3
"""
Scoring D analysis for R2b grid search (High Risk, DD tolerant).
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
csv_path = Path("C:\\Users\\Bonjour\\Desktop\\backtest_gc_si\\output\\grid_micro_r2b.csv")
output_dir = Path("C:\\Users\\Bonjour\\Desktop\\backtest_gc_si\\output")
reports_dir = Path("C:\\Users\\Bonjour\\Desktop\\backtest_gc_si\\output\\reports")

# Ensure reports directory exists
reports_dir.mkdir(parents=True, exist_ok=True)

print("Loading R2b grid search CSV (2.9M rows)...")
df = pd.read_csv(csv_path, sep=";")

print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
print(f"Columns: {list(df.columns)}")

# Step 1: Apply elimination filters (Scoring D)
print("\n" + "="*80)
print("SCORING D ANALYSIS - HIGH RISK (DD TOLERANT)")
print("="*80)

print(f"\nInitial dataset: {len(df)} configs")

# Filter 1: max_dd >= -8000
df_d = df[df['max_dd'] >= -8000].copy()
print(f"After max_dd >= -8000: {len(df_d)} configs (eliminated {len(df) - len(df_d)})")

# Filter 2: trades >= 50
df_d = df_d[df_d['trades'] >= 50].copy()
print(f"After trades >= 50: {len(df_d)} configs (eliminated {len(df) - len(df_d)})")

# Filter 3: profit_factor >= 1.1 AND < inf
df_d = df_d[(df_d['profit_factor'] >= 1.1) & (df_d['profit_factor'] != np.inf)].copy()
print(f"After PF >= 1.1 (exclude inf): {len(df_d)} configs (eliminated {len(df) - len(df_d)})")

survivors = len(df_d)
print(f"\nSurvivors after Scoring D filters: {survivors} ({100*survivors/len(df):.2f}%)")

if survivors == 0:
    print("ERROR: No configs survived Scoring D filters!")
    exit(1)

# Step 2: Normalize metrics (0-1 scale using min-max)
print("\nNormalizing metrics within filtered set...")

# PnL: higher is better
pnl_min = df_d['pnl_net'].min()
pnl_max = df_d['pnl_net'].max()
df_d['pnl_norm'] = (df_d['pnl_net'] - pnl_min) / (pnl_max - pnl_min)

# Calmar: higher is better, cap at P99 to avoid outliers
calmar_p99 = df_d['calmar'].quantile(0.99)
df_d['calmar_capped'] = df_d['calmar'].clip(upper=calmar_p99)
calmar_min = df_d['calmar_capped'].min()
calmar_max = df_d['calmar_capped'].max()
df_d['calmar_norm'] = (df_d['calmar_capped'] - calmar_min) / (calmar_max - calmar_min)

# Sharpe: higher is better
sharpe_min = df_d['sharpe'].min()
sharpe_max = df_d['sharpe'].max()
if sharpe_max > sharpe_min:
    df_d['sharpe_norm'] = (df_d['sharpe'] - sharpe_min) / (sharpe_max - sharpe_min)
else:
    df_d['sharpe_norm'] = 0.5

# PF: higher is better
pf_min = df_d['profit_factor'].min()
pf_max = df_d['profit_factor'].max()
df_d['pf_norm'] = (df_d['profit_factor'] - pf_min) / (pf_max - pf_min)

# Step 3: Compute Scoring D
df_d['score_d'] = (
    0.40 * df_d['pnl_norm'] +
    0.25 * df_d['calmar_norm'] +
    0.20 * df_d['sharpe_norm'] +
    0.15 * df_d['pf_norm']
)

# Step 4: Sort by score and deduplicate on indicator params
df_d_sorted = df_d.sort_values('score_d', ascending=False).reset_index(drop=True)

dedup_cols = ['beta', 'zp', 'cp', 'adf', 'zE', 'co', 'zTP', 'dTP']
df_d_top = df_d_sorted.drop_duplicates(subset=dedup_cols, keep='first').head(10).copy()

# Step 5: Format output table
result_cols = [
    'label', 'trades', 'win_rate', 'pnl_net', 'profit_factor',
    'max_dd', 'sharpe', 'calmar', 'score_d',
    'tp_zscore', 'tp_dollar', 'sl_zscore', 'sl_dollar', 'end_session'
]

df_d_top_display = df_d_top[result_cols].copy()
df_d_top_display.insert(0, 'rank', range(1, len(df_d_top_display) + 1))

print("\n" + "="*80)
print("TOP 10 SCORING D (Deduplicated)")
print("="*80)
print(df_d_top_display.to_string(index=False))

# Save to CSV
output_csv = output_dir / "grid_micro_r2b_topD.csv"
df_d_top_display.to_csv(output_csv, sep=";", index=False)
print(f"\nSaved Top 10 to: {output_csv}")

# Append to R2B_ANALYSIS.md
report_path = reports_dir / "R2B_ANALYSIS.md"
with open(report_path, "a", encoding="utf-8") as f:
    f.write("\n\n" + "="*80 + "\n")
    f.write("SCORING D ANALYSIS - HIGH RISK (DD TOLERANT)\n")
    f.write("="*80 + "\n\n")

    f.write("## Elimination Filters\n\n")
    f.write(f"- max_dd >= -8000 (tolerates up to -$8K drawdown)\n")
    f.write(f"- trades >= 50\n")
    f.write(f"- profit_factor >= 1.1 AND profit_factor < inf\n\n")

    f.write(f"## Results\n\n")
    f.write(f"**Survivors**: {survivors} / {len(df)} ({100*survivors/len(df):.2f}%)\n\n")

    f.write("## Top 10 Configs (Deduplicated)\n\n")
    f.write(df_d_top_display.to_markdown(index=False))
    f.write("\n\n")

    f.write("## Scoring Formula\n\n")
    f.write("```\nScore_D = 0.40 * PnL_norm + 0.25 * Calmar_norm + 0.20 * Sharpe_norm + 0.15 * PF_norm\n")
    f.write("```\n\n")
    f.write("- All metrics normalized 0-1 (min-max) within filtered set\n")
    f.write(f"- Calmar capped at P99 = {calmar_p99:.4f} to mitigate outliers\n")
    f.write("- Higher PnL, Calmar, Sharpe, and PF are better\n\n")

print(f"Appended Scoring D analysis to: {report_path}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Configs eliminated by DD filter (-8000): {len(df) - len(df[(df['max_dd'] >= -8000)])}")
print(f"Configs eliminated by trades filter (50): {len(df[(df['max_dd'] >= -8000)]) - len(df_d[(df_d['trades'] >= 50)])}")
print(f"Configs eliminated by PF filter (1.1): {len(df[(df['max_dd'] >= -8000) & (df['trades'] >= 50)]) - survivors}")
print(f"\nFinal survivors: {survivors} ({100*survivors/len(df):.2f}%)")
print(f"Top config: {df_d_top.iloc[0]['label']} (Score D: {df_d_top.iloc[0]['score_d']:.4f})")
