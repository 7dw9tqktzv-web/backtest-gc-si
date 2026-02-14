"""Analyse grid search R2a results and generate report."""
import pandas as pd
import numpy as np

df = pd.read_csv('output/grid_micro_r2a.csv', sep=';')

# ============================================================
# 1. FILTERS
# ============================================================
f = df.copy()
f = f[(f.max_dd >= -5000) & (f.trades >= 30) & (f.profit_factor >= 1.1)]
n_total = len(df)
n_filtered = len(f)

# ============================================================
# 2. SCORING
# ============================================================
def norm01(s):
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)

f = f.copy()
f['s_sharpe'] = norm01(f['sharpe'])
f['s_maxdd'] = norm01(f['max_dd'])  # higher (less negative) = better
f['s_consist'] = norm01(f['win_rate'])
f['s_pf'] = norm01(f['profit_factor'])
f['s_calmar'] = norm01(f['calmar'])

f['score'] = (0.35 * f['s_sharpe'] + 0.25 * f['s_maxdd'] +
              0.20 * f['s_consist'] + 0.15 * f['s_pf'] + 0.05 * f['s_calmar'])

f = f.sort_values('score', ascending=False).reset_index(drop=True)

# ============================================================
# 3. TOP 10 (deduplicated on exit profile)
# ============================================================
f['exit_key'] = f.apply(lambda r: f"{r.zE}_{r.co}_{r.zTP}_{r.dTP}_{r.dSL}", axis=1)
top10 = f.drop_duplicates(subset='exit_key', keep='first').head(10).copy()
top10['rank'] = range(1, len(top10)+1)

# ============================================================
# 4. PATTERN ANALYSIS
# ============================================================
top50 = f.head(50)

# 4a. dTP in top 50
dtp_counts = top50.dTP.value_counts().sort_index()
dtp_median = top50.dTP.median()
dtp_mean = top50.dTP.mean()

# 4b. dSL impact
dsl_zero = f[f.dSL == 0]
dsl_active = f[f.dSL != 0]

dsl_top50 = top50.dSL.value_counts().sort_index()

# 4c. zTP=3.0 vs zTP=0.0
ztp3 = f[f.zTP == 3.0]
ztp0 = f[f.zTP == 0.0]

# ============================================================
# 5. R1 BASELINE
# ============================================================
r1_baseline = f[(f.dTP == 300) & (f.dSL == 0)]
r1_best = r1_baseline.sort_values('score', ascending=False).head(1)

# ============================================================
# BUILD REPORT
# ============================================================
lines = []
def L(s=''):
    lines.append(s)

L('=' * 80)
L('GRID SEARCH R2a -- MICRO SIZING -- COMPREHENSIVE REPORT')
L('=' * 80)
L('Date: 2026-02-13')
L(f'Total configs: {n_total}')
L(f'After filters (MaxDD>=-$5000, trades>=30, PF>=1.1): {n_filtered} ({n_filtered/n_total*100:.1f}%)')
L()
L('Filters removed:')
L(f'  MaxDD < -$5000: {len(df[df.max_dd < -5000])} configs')
L(f'  Trades < 30:    {len(df[df.trades < 30])} configs')
L(f'  PF < 1.1:       {len(df[df.profit_factor < 1.1])} configs')
L()
L('Scoring: Sharpe 35% + MaxDD_norm 25% + Consistency 20% + PF 15% + Calmar 5%')
L()

L('-' * 80)
L('TOP 10 CONFIGS (deduplicated on exit profile)')
L('-' * 80)
for _, row in top10.iterrows():
    L(f"  #{int(row['rank']):2d}  {row['label']}")
    L(f"       trades={int(row.trades):3d}  WR={row.win_rate:.1f}%  PnL=${row.pnl_net:,.0f}  PF={row.profit_factor:.2f}  MaxDD=${row.max_dd:,.0f}  Sharpe={row.sharpe:.3f}  Calmar={row.calmar:.2f}  Score={row.score:.4f}")
    L(f"       Exits: TP_Z={int(row.tp_zscore)} TP_$={int(row.tp_dollar)} SL_Z={int(row.sl_zscore)} SL_$={int(row.sl_dollar)} MH={int(row.max_hold)} ES={int(row.end_session)}")
    L()

L('-' * 80)
L('PATTERN ANALYSIS')
L('-' * 80)
L()
L('--- 4a. dTP distribution in Top 50 ---')
for val, cnt in dtp_counts.items():
    L(f'  dTP={val:4d}: {cnt:3d} configs ({cnt/50*100:.0f}%)')
L(f'  Median dTP in top 50: {dtp_median:.0f}')
L(f'  Mean dTP in top 50:   {dtp_mean:.0f}')
L()

L('--- 4b. dSL impact (filtered set) ---')
L(f'  {"Metric":<15s} {"dSL=0":>12s} {"dSL active":>12s}')
L(f'  {"count":<15s} {len(dsl_zero):>12d} {len(dsl_active):>12d}')
L(f'  {"avg Sharpe":<15s} {dsl_zero.sharpe.mean():>12.4f} {dsl_active.sharpe.mean():>12.4f}')
L(f'  {"avg PnL":<15s} {dsl_zero.pnl_net.mean():>12.1f} {dsl_active.pnl_net.mean():>12.1f}')
L(f'  {"avg MaxDD":<15s} {dsl_zero.max_dd.mean():>12.1f} {dsl_active.max_dd.mean():>12.1f}')
L()
L('  dSL in Top 50:')
for val, cnt in dsl_top50.items():
    L(f'    dSL={val:5d}: {cnt:3d} configs')
L()

L('  dSL breakdown (all filtered):')
for dsl_val in sorted(f.dSL.unique()):
    sub = f[f.dSL == dsl_val]
    L(f'    dSL={dsl_val:5d}: n={len(sub):4d}  avgSharpe={sub.sharpe.mean():.4f}  avgPnL=${sub.pnl_net.mean():,.0f}  avgMaxDD=${sub.max_dd.mean():,.0f}')
L()

L('--- 4c. zTP=3.0 vs zTP=0.0 (effectively disabled Z-Score TP) ---')
L(f'  {"Metric":<15s} {"zTP=0.0":>12s} {"zTP=3.0":>12s}')
L(f'  {"count":<15s} {len(ztp0):>12d} {len(ztp3):>12d}')
L(f'  {"avg Sharpe":<15s} {ztp0.sharpe.mean():>12.4f} {ztp3.sharpe.mean():>12.4f}')
L(f'  {"avg PnL":<15s} {ztp0.pnl_net.mean():>12.1f} {ztp3.pnl_net.mean():>12.1f}')
L(f'  {"avg MaxDD":<15s} {ztp0.max_dd.mean():>12.1f} {ztp3.max_dd.mean():>12.1f}')
L(f'  {"avg Score":<15s} {ztp0.score.mean():>12.4f} {ztp3.score.mean():>12.4f}')
L()

L('  Full zTP breakdown:')
for ztp_val in sorted(f.zTP.unique()):
    sub = f[f.zTP == ztp_val]
    in_t50 = top50[top50.zTP == ztp_val].shape[0]
    L(f'    zTP={ztp_val:4.1f}: n={len(sub):4d}  avgSharpe={sub.sharpe.mean():.4f}  avgPnL=${sub.pnl_net.mean():,.0f}  avgScore={sub.score.mean():.4f}  in_top50={in_t50}')
L()

L('--- 4d. zE dominance ---')
L(f'  {"zE":<6s} {"count":>6s} {"avgSharpe":>10s} {"avgPnL":>10s} {"avgMaxDD":>10s} {"avgScore":>10s} {"in_top50":>9s}')
for ze_val in sorted(f.zE.unique()):
    sub = f[f.zE == ze_val]
    in_t50 = top50[top50.zE == ze_val].shape[0]
    L(f'  {ze_val:<6.2f} {len(sub):>6d} {sub.sharpe.mean():>10.4f} {sub.pnl_net.mean():>10.0f} {sub.max_dd.mean():>10.0f} {sub.score.mean():>10.4f} {in_t50:>9d}')
L()

L('--- 4e. co dominance ---')
L(f'  {"co":<6s} {"count":>6s} {"avgSharpe":>10s} {"avgPnL":>10s} {"avgMaxDD":>10s} {"avgScore":>10s} {"in_top50":>9s}')
for co_val in sorted(f.co.unique()):
    sub = f[f.co == co_val]
    in_t50 = top50[top50.co == co_val].shape[0]
    L(f'  {co_val:<6d} {len(sub):>6d} {sub.sharpe.mean():>10.4f} {sub.pnl_net.mean():>10.0f} {sub.max_dd.mean():>10.0f} {sub.score.mean():>10.4f} {in_t50:>9d}')
L()

L('-' * 80)
L('R1 BASELINE COMPARISON (dTP=300, dSL=0)')
L('-' * 80)
if len(r1_best) > 0:
    rb = r1_best.iloc[0]
    L(f'  R1 best:     {rb.label}')
    L(f'               trades={int(rb.trades)}  PnL=${rb.pnl_net:,.0f}  PF={rb.profit_factor:.2f}  MaxDD=${rb.max_dd:,.0f}  Sharpe={rb.sharpe:.3f}  Score={rb.score:.4f}')
    L()
    ob = top10.iloc[0]
    L(f'  R2a best:    {ob.label}')
    L(f'               trades={int(ob.trades)}  PnL=${ob.pnl_net:,.0f}  PF={ob.profit_factor:.2f}  MaxDD=${ob.max_dd:,.0f}  Sharpe={ob.sharpe:.3f}  Score={ob.score:.4f}')
    L()
    pnl_delta = ob.pnl_net - rb.pnl_net
    sharpe_delta = ob.sharpe - rb.sharpe
    dd_delta = ob.max_dd - rb.max_dd
    L(f'  Improvement: PnL {pnl_delta:+,.0f}  Sharpe {sharpe_delta:+.3f}  MaxDD {dd_delta:+,.0f}')
else:
    L('  No R1 baseline configs found in filtered set.')
L()

L(f'  All dTP=300/dSL=0 in filtered set: {len(r1_baseline)} configs')
if len(r1_baseline) > 0:
    L(f'  Avg metrics: Sharpe={r1_baseline.sharpe.mean():.4f}  PnL=${r1_baseline.pnl_net.mean():,.0f}  MaxDD=${r1_baseline.max_dd.mean():,.0f}')
L()
L(f'  Top 10 avg:  Sharpe={top10.sharpe.mean():.4f}  PnL=${top10.pnl_net.mean():,.0f}  MaxDD=${top10.max_dd.mean():,.0f}')

L()
L('-' * 80)
L('KEY FINDINGS & RECOMMENDATIONS')
L('-' * 80)

best_dtp = top50.dTP.mode().iloc[0]
best_dsl_in_top50 = top50.dSL.mode().iloc[0]
best_ze = top50.zE.mode().iloc[0]
best_co = top50.co.mode().iloc[0]
best_ztp = top50.zTP.mode().iloc[0]

L(f'  1. Dominant dTP in top 50: {int(best_dtp)} (R1 was 300)')
L(f'  2. Dominant dSL in top 50: {int(best_dsl_in_top50)} (R1 was 0=disabled)')
L(f'  3. Dominant zE in top 50:  {best_ze}')
L(f'  4. Dominant co in top 50:  {int(best_co)}')
L(f'  5. Dominant zTP in top 50: {best_ztp}')
L()

if dsl_active.sharpe.mean() > dsl_zero.sharpe.mean():
    dsl_verdict = f'dSL ACTIVE improves avg Sharpe by {dsl_active.sharpe.mean() - dsl_zero.sharpe.mean():.4f}'
else:
    dsl_verdict = f'dSL=0 (disabled) has better avg Sharpe by {dsl_zero.sharpe.mean() - dsl_active.sharpe.mean():.4f}'
L(f'  dSL verdict: {dsl_verdict}')

if ztp0.score.mean() > ztp3.score.mean():
    L(f'  zTP verdict: zTP=0.0 slightly better than zTP=3.0 (score {ztp0.score.mean():.4f} vs {ztp3.score.mean():.4f})')
else:
    L(f'  zTP verdict: zTP=3.0 slightly better than zTP=0.0 (score {ztp3.score.mean():.4f} vs {ztp0.score.mean():.4f})')
L()

L('=' * 80)
L('END OF REPORT')
L('=' * 80)

report = '\n'.join(lines)
print(report)

# Save report
with open('output/grid_micro_r2a_report.txt', 'w', encoding='utf-8') as fh:
    fh.write(report)

# Save top 10 CSV
top10_out = top10[['rank','label','trades','win_rate','pnl_net','profit_factor','max_dd','sharpe','calmar','score',
                    'zE','co','zTP','dTP','dSL','tp_zscore','tp_dollar','sl_zscore','sl_dollar','end_session']].copy()
top10_out.to_csv('output/grid_micro_r2a_top10.csv', sep=';', index=False)
print('\n--- Files saved ---')
print('Report: output/grid_micro_r2a_report.txt')
print('Top 10: output/grid_micro_r2a_top10.csv')
