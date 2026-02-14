"""
Analyse complete du grid search R2b (micro sizing).
~2.9M configs, semicolon-separated CSV.
"""
import pandas as pd
import numpy as np
import os
import sys
import io

BASE = r"C:\Users\Bonjour\Desktop\backtest_gc_si"
CSV = os.path.join(BASE, "output", "grid_micro_r2b.csv")
OUT_DIR = os.path.join(BASE, "output", "reports")
os.makedirs(OUT_DIR, exist_ok=True)

report_lines = []

def pr(s=""):
    report_lines.append(str(s))

def pr_table(df, max_rows=20):
    """Print df as markdown table."""
    buf = io.StringIO()
    df.head(max_rows).to_markdown(buf, index=False, floatfmt=".2f")
    pr(buf.getvalue())

# =====================================================
# LOAD DATA
# =====================================================
print("Loading CSV in chunks...")
chunks = []
for chunk in pd.read_csv(CSV, sep=";", chunksize=500_000, low_memory=False):
    chunks.append(chunk)
df = pd.concat(chunks, ignore_index=True)
print(f"Loaded {len(df):,} rows")

# =====================================================
# ETAPE 1 — Stats globales
# =====================================================
pr("# Grid Search R2b -- Comprehensive Analysis")
pr(f"\nDate: 2026-02-14")
pr(f"\n## Etape 1 -- Global Statistics\n")

total = len(df)
profitable = (df["pnl_net"] > 0).sum()
pct = profitable / total * 100

pr(f"- **Total configs**: {total:,}")
pr(f"- **Profitable (pnl_net > 0)**: {profitable:,} ({pct:.1f}%)")
pr(f"- **Unprofitable**: {total - profitable:,} ({100-pct:.1f}%)")

pr(f"\n### Trades distribution")
desc_t = df["trades"].describe(percentiles=[0.25, 0.5, 0.75])
pr(f"- Min: {desc_t['min']:.0f}, P25: {desc_t['25%']:.0f}, Median: {desc_t['50%']:.0f}, P75: {desc_t['75%']:.0f}, Max: {desc_t['max']:.0f}")

pr(f"\n### PnL distribution")
desc_p = df["pnl_net"].describe(percentiles=[0.25, 0.5, 0.75])
pr(f"- Min: ${desc_p['min']:,.0f}, P25: ${desc_p['25%']:,.0f}, Median: ${desc_p['50%']:,.0f}, P75: ${desc_p['75%']:,.0f}, Max: ${desc_p['max']:,.0f}")

# =====================================================
# ETAPE 2 — Filtres eliminatoires
# =====================================================
pr(f"\n## Etape 2 -- Elimination Filters\n")

mask = (
    (df["max_dd"] >= -5000) &
    (df["trades"] >= 50) &
    (df["profit_factor"] >= 1.2) &
    (df["profit_factor"] < np.inf) &
    (df["profit_factor"].notna())
)
filt = df[mask].copy()
pr(f"- Filter: max_dd >= -$5,000 AND trades >= 50 AND 1.2 <= PF < inf")
pr(f"- **Survivors**: {len(filt):,} / {total:,} ({len(filt)/total*100:.2f}%)")

# =====================================================
# ETAPE 3 — Scorings
# =====================================================
pr(f"\n## Etape 3 -- Scoring Rankings\n")

def norm01(s):
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)

# Normalize metrics
filt["sharpe_n"] = norm01(filt["sharpe"])
filt["dd_n"] = norm01(filt["max_dd"])  # higher (less negative) = better
filt["wr_n"] = norm01(filt["win_rate"])
filt["pf_n"] = norm01(filt["profit_factor"])
filt["trades_n"] = norm01(filt["trades"])
filt["pnl_n"] = norm01(filt["pnl_net"])

calmar_cap = filt["calmar"].clip(upper=filt["calmar"].quantile(0.99))
filt["calmar_n"] = norm01(calmar_cap)

# Scoring A — Prop Firm
filt["score_A"] = filt["sharpe_n"]*0.35 + filt["dd_n"]*0.25 + filt["wr_n"]*0.25 + filt["pf_n"]*0.15

# Scoring B — Volume
filt["score_B"] = filt["trades_n"]*0.30 + filt["wr_n"]*0.25 + filt["sharpe_n"]*0.20 + filt["pf_n"]*0.15 + filt["dd_n"]*0.10

# Scoring C — Aggressive
filt["score_C"] = filt["pnl_n"]*0.35 + filt["calmar_n"]*0.25 + filt["pf_n"]*0.20 + filt["sharpe_n"]*0.20

dedup_cols = ["beta", "zp", "cp", "adf", "zE", "co", "zTP", "dTP"]
display_cols = ["label", "trades", "win_rate", "pnl_net", "profit_factor", "max_dd",
                "sharpe", "calmar", "tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar", "end_session"]

def top10_dedup(score_col, name):
    sorted_df = filt.sort_values(score_col, ascending=False)
    deduped = sorted_df.drop_duplicates(subset=dedup_cols, keep="first").head(10).copy()
    deduped["rank"] = range(1, len(deduped)+1)
    deduped["score"] = deduped[score_col]
    out = deduped[["rank"] + display_cols + ["score"]]
    pr(f"### Scoring {name}\n")
    pr_table(out)
    pr("")
    return deduped

topA = top10_dedup("score_A", "A -- Prop Firm (Sharpe 35% + MaxDD 25% + WinRate 25% + PF 15%)")
topB = top10_dedup("score_B", "B -- Volume (Trades 30% + WinRate 25% + Sharpe 20% + PF 15% + MaxDD 10%)")
topC = top10_dedup("score_C", "C -- Aggressive (PnL 35% + Calmar 25% + PF 20% + Sharpe 20%)")

# =====================================================
# ETAPE 4 — Cross analyses
# =====================================================
pr(f"\n## Etape 4 -- Cross Analyses\n")

# 4a. Beta regime
def beta_regime(b):
    if b <= 1980:
        return "Court"
    elif b <= 3300:
        return "Moyen"
    else:
        return "Long"

filt["regime"] = filt["beta"].apply(beta_regime)

pr("### 4a. Beta Regime\n")
regime_stats = filt.groupby("regime").agg(
    count=("pnl_net", "size"),
    avg_trades=("trades", "mean"),
    avg_sharpe=("sharpe", "mean"),
    avg_wr=("win_rate", "mean"),
    avg_pnl=("pnl_net", "mean"),
).reindex(["Court", "Moyen", "Long"])
pr_table(regime_stats.reset_index())
pr("")

# 4b. co breakdown
pr("### 4b. Cointegration Score (co) Breakdown\n")
co_stats = filt.groupby("co").agg(
    count=("pnl_net", "size"),
    avg_sharpe=("sharpe", "mean"),
    avg_trades=("trades", "mean"),
    avg_pnl=("pnl_net", "mean"),
)
pr_table(co_stats.reset_index())
pr("")

# 4c. zTP x beta regime
pr("### 4c. zTP x Beta Regime -- Avg Sharpe\n")
pivot_ztp = filt.pivot_table(values="sharpe", index="zTP", columns="regime", aggfunc="mean")
pivot_ztp = pivot_ztp.reindex(columns=["Court", "Moyen", "Long"])
pr_table(pivot_ztp.reset_index())
pr("")

# 4d. dTP breakdown by beta regime
pr("### 4d. dTP Breakdown\n")
dtp_stats = filt.groupby("dTP").agg(
    count=("pnl_net", "size"),
    avg_sharpe=("sharpe", "mean"),
    avg_pnl=("pnl_net", "mean"),
    avg_trades=("trades", "mean"),
)
pr_table(dtp_stats.reset_index())
pr("")

pr("#### dTP x Beta Regime -- Avg Sharpe\n")
pivot_dtp = filt.pivot_table(values="sharpe", index="dTP", columns="regime", aggfunc="mean")
pivot_dtp = pivot_dtp.reindex(columns=["Court", "Moyen", "Long"])
pr_table(pivot_dtp.reset_index())
pr("")

pr("#### dTP x Beta Regime -- Avg PnL\n")
pivot_dtp_pnl = filt.pivot_table(values="pnl_net", index="dTP", columns="regime", aggfunc="mean")
pivot_dtp_pnl = pivot_dtp_pnl.reindex(columns=["Court", "Moyen", "Long"])
pr_table(pivot_dtp_pnl.reset_index())
pr("")

# 4e. High-volume profitable
pr("### 4e. High-Volume Profitable Configs\n")
hv = filt[(filt["trades"] > 100) & (filt["profit_factor"] > 1.5)]
pr(f"- Configs with trades > 100 AND PF > 1.5: **{len(hv):,}**")
if len(hv) > 0:
    hv_top5 = hv.nlargest(5, "sharpe")[display_cols]
    pr("\nTop 5 by Sharpe:\n")
    pr_table(hv_top5)
pr("")

# 4f. zE breakdown
pr("### 4f. zE Breakdown\n")
ze_stats = filt.groupby("zE").agg(
    count=("pnl_net", "size"),
    avg_trades=("trades", "mean"),
    avg_sharpe=("sharpe", "mean"),
    avg_pnl=("pnl_net", "mean"),
)
pr_table(ze_stats.reset_index())
pr("")

# =====================================================
# ETAPE 5 — Comparison with baselines
# =====================================================
pr(f"\n## Etape 5 -- Comparison with R1/R2a Baselines\n")

# R1 baseline
r1_mask = (
    (df["beta"] == 2640) & (df["zp"] == 20) & (df["cp"] == 30) & (df["adf"] == 26) &
    (df["zE"] == 3.5) & (df["co"] == 20) & (df["zTP"] == 1.5) & (df["dTP"] == 300)
)
r1 = df[r1_mask]
if len(r1) > 0:
    pr("### R1 Baseline (b2640_zE3.5_co20_zTP1.5_dTP300)\n")
    r1_show = r1[display_cols].head(5)
    pr_table(r1_show)
    pr("")
else:
    pr("R1 baseline config NOT FOUND in dataset.\n")

# R2a best
r2a_mask = (
    (df["beta"] == 2640) & (df["zp"] == 20) & (df["cp"] == 30) & (df["adf"] == 26) &
    (df["zE"] == 3.5) & (df["co"] == 40) & (df["zTP"] == 0.0) & (df["dTP"] == 800)
)
r2a = df[r2a_mask]
if len(r2a) > 0:
    pr("### R2a Best (b2640_zE3.5_co40_zTP0.0_dTP800)\n")
    r2a_show = r2a[display_cols].head(5)
    pr_table(r2a_show)
    pr("")
else:
    pr("R2a best config NOT FOUND in dataset.\n")

pr("### Top 1 from each scoring (for comparison)\n")
for name, top_df in [("A-PropFirm", topA), ("B-Volume", topB), ("C-Aggressive", topC)]:
    row = top_df.iloc[0]
    pr(f"- **{name}**: {row['label']} | trades={row['trades']:.0f} | PnL=${row['pnl_net']:,.0f} | PF={row['profit_factor']:.2f} | DD=${row['max_dd']:,.0f} | Sharpe={row['sharpe']:.3f}")
pr("")

# =====================================================
# SAVE
# =====================================================
report_text = "\n".join(report_lines)

report_path = os.path.join(OUT_DIR, "R2B_ANALYSIS.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_text)
print(f"\nReport saved: {report_path}")

# Save top CSVs
save_cols = ["label", "beta", "zp", "cp", "adf", "zE", "co", "zTP", "zSL", "dTP", "dSL",
             "feos", "mhb", "mm", "trades", "long", "short", "win_rate", "pnl_net", "pnl_avg",
             "profit_factor", "max_dd", "sharpe", "calmar", "sortino",
             "tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar", "max_hold", "end_session"]

for suffix, top_df in [("topA", topA), ("topB", topB), ("topC", topC)]:
    path = os.path.join(BASE, "output", f"grid_micro_r2b_{suffix}.csv")
    top_df[[c for c in save_cols if c in top_df.columns]].to_csv(path, sep=";", index=False)
    print(f"Saved: {path}")

# Print report
print("\n" + "="*80)
print(report_text)
