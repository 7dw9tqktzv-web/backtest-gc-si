#!/usr/bin/env python
# ============================================================================
# RUN_PAPER_TRADING_REF.PY - Reference backtest pour paper trading
# ============================================================================
#
# Lance le backtest Python sur les donnees SC exportees et produit la
# reference des trades attendus pour la periode paper trading.
#
# Usage:
#   python scripts/run_paper_trading_ref.py                          # defaut: depuis 2026-02-01
#   python scripts/run_paper_trading_ref.py --start 2026-01-15       # date custom
#   python scripts/run_paper_trading_ref.py --start 2026-01-15 --all # affiche aussi tous les trades
#
# Sortie:
#   output/production/pt_reference_trades.csv    <- trades periode paper trading
#   output/production/pt_reference_all.csv       <- tous les trades (backtest complet)
#   output/production/pt_reference_report.txt    <- rapport lisible
# ============================================================================

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
from data_loader import load_and_prepare_data, resample_to_5min, load_5s_data
from indicators import calculate_all_indicators
from backtest_engine_numba import run_hybrid_backtest
from backtest_engine_hybrid import export_backtest
from common import build_config_fingerprint


OUTPUT_DIR = Path("output/production")


def run_reference_backtest(config):
    """Lance le backtest complet et retourne le DataFrame des trades."""
    # 1. Charger les donnees 1-min
    df_1min, config, stats = load_and_prepare_data(verbose=False)
    print(f"[OK] Donnees 1-min : {len(df_1min)} barres "
          f"({df_1min.index[0]} -> {df_1min.index[-1]})")

    # 2. Resample si 5-min
    indicator_period = config.get('indicators', {}).get('period', '1min')
    if indicator_period == '5min':
        df_bars = resample_to_5min(df_1min, verbose=False)
        print(f"[OK] Resample 5-min : {len(df_bars)} barres")
    else:
        df_bars = df_1min

    # 3. Indicateurs
    df_bars = calculate_all_indicators(df_bars, config)
    print(f"[OK] Indicateurs {indicator_period} calcules")

    # 4. Donnees 5s
    df_5s = load_5s_data(config, verbose=False)
    print(f"[OK] Donnees 5s : {len(df_5s)} barres")

    # 5. Backtest
    trades_df = run_hybrid_backtest(df_bars, df_5s, config, verbose=False)
    print(f"[OK] Backtest termine : {len(trades_df)} trades")

    return trades_df, config, df_1min


def filter_paper_trading_period(trades_df, start_date):
    """Filtre les trades dont l'entree est >= start_date."""
    if len(trades_df) == 0:
        return trades_df
    mask = pd.to_datetime(trades_df['Entry_DateTime']) >= pd.Timestamp(start_date)
    return trades_df[mask].copy()


def generate_report(trades_all, trades_pt, config, start_date, data_end):
    """Genere le rapport texte."""
    lines = []
    sep = "=" * 70
    lines.append(sep)
    lines.append("PAPER TRADING REFERENCE - Trades attendus par Python")
    lines.append(sep)
    lines.append(f"Date generation  : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Config           : {build_config_fingerprint(config)}")
    lines.append(f"Periode data     : {data_end}")
    lines.append(f"Paper trading    : depuis {start_date}")
    lines.append(f"Slippage         : {config['costs']['slippage_gc_ticks']} ticks GC, "
                 f"{config['costs']['slippage_si_ticks']} ticks SI")
    lines.append(f"Contrats         : {config['contracts']['mode']}")
    lines.append("")

    # Resume backtest complet
    lines.append(f"--- BACKTEST COMPLET ({len(trades_all)} trades) ---")
    if len(trades_all) > 0:
        lines.append(f"PnL net total    : ${trades_all['PnL_Net'].sum():+,.2f}")
        winners = (trades_all['PnL_Net'] > 0).sum()
        lines.append(f"Win rate         : {winners}/{len(trades_all)} "
                     f"({winners/len(trades_all)*100:.1f}%)")
    lines.append("")

    # Trades paper trading
    lines.append(sep)
    lines.append(f"--- PERIODE PAPER TRADING : {len(trades_pt)} trades depuis {start_date} ---")
    lines.append(sep)

    if len(trades_pt) == 0:
        lines.append("Aucun trade sur cette periode.")
        lines.append("Normal si les donnees s'arretent avant la date de debut.")
    else:
        # Metriques PT
        pnl_net = trades_pt['PnL_Net'].sum()
        winners_pt = (trades_pt['PnL_Net'] > 0).sum()
        lines.append(f"PnL net          : ${pnl_net:+,.2f}")
        lines.append(f"Win rate         : {winners_pt}/{len(trades_pt)} "
                     f"({winners_pt/len(trades_pt)*100:.1f}%)")
        lines.append("")

        # Detail de chaque trade
        lines.append(f"{'#':>3} {'Dir':>5} {'Entree':>19} {'Sortie':>19} "
                     f"{'Duree':>6} {'Exit':>10} {'PnL Net':>10} {'Cumul':>10}")
        lines.append("-" * 90)

        cumul = 0.0
        for _, t in trades_pt.iterrows():
            cumul += t['PnL_Net']
            entry_dt = str(t['Entry_DateTime'])[:16]
            exit_dt = str(t['Exit_DateTime'])[:16]
            lines.append(
                f"{int(t['Trade_No']):3d} {t['Direction']:>5} {entry_dt:>19} "
                f"{exit_dt:>19} {t['Duration_Min']:5.0f}m {t['Exit_Reason']:>10} "
                f"${t['PnL_Net']:+9,.2f} ${cumul:+9,.2f}"
            )

    lines.append("")
    lines.append(sep)
    lines.append("Comparer ces trades avec le Trade Activity Log de Sierra Chart.")
    lines.append("Criteres de match : datetime +/- 1 barre, meme direction.")
    lines.append(sep)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Reference backtest pour paper trading")
    parser.add_argument("--start", default="2026-02-01",
                        help="Date de debut paper trading (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true",
                        help="Afficher aussi le resume du backtest complet")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("PAPER TRADING REFERENCE")
    print(f"Periode : depuis {args.start}")
    print("=" * 60 + "\n")

    # Lancer le backtest
    trades_all, config, df_1min = run_reference_backtest(config=None)

    # Filtrer la periode PT
    trades_pt = filter_paper_trading_period(trades_all, args.start)
    first_dt = df_1min['DateTime'].iloc[0] if 'DateTime' in df_1min.columns else df_1min.index[0]
    last_dt = df_1min['DateTime'].iloc[-1] if 'DateTime' in df_1min.columns else df_1min.index[-1]
    data_end = f"{first_dt} -> {last_dt}"

    # Sauvegarder
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # CSV trades PT
    pt_csv = OUTPUT_DIR / "pt_reference_trades.csv"
    if len(trades_pt) > 0:
        # Recalculer PnL_Cumul pour la periode PT seulement
        trades_pt = trades_pt.copy()
        trades_pt['PnL_Cumul'] = trades_pt['PnL_Net'].cumsum().round(2)
    trades_pt.to_csv(pt_csv, index=False, sep=';')
    print(f"\n[OK] {len(trades_pt)} trades PT -> {pt_csv}")

    # CSV tous les trades
    all_csv = OUTPUT_DIR / "pt_reference_all.csv"
    trades_all.to_csv(all_csv, index=False, sep=';')
    print(f"[OK] {len(trades_all)} trades total -> {all_csv}")

    # Rapport texte
    report = generate_report(trades_all, trades_pt, config, args.start, data_end)
    report_path = OUTPUT_DIR / "pt_reference_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"[OK] Rapport -> {report_path}")

    # Afficher le rapport
    print("\n" + report)


if __name__ == "__main__":
    main()
