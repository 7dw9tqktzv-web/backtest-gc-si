"""Analyse des trades heure 7 CT vs calendrier eco US."""
import csv
from datetime import datetime, date
from collections import defaultdict

# ============================================================
# Calendrier eco US majeur — publications a 7:30 CT (8:30 ET)
# Sources: BLS, BEA, Fed, Census Bureau
# ============================================================
# Format: date -> evenement
# NFP = Non-Farm Payrolls (1er vendredi du mois)
# CPI = Consumer Price Index (~10-15 du mois)
# PPI = Producer Price Index (~15 du mois)
# FOMC = Federal Reserve decision (8 fois/an, 13:00 CT)
# RETAIL = Retail Sales (~15 du mois)
# GDP = Gross Domestic Product (fin de mois/trimestre)
# CLAIMS = Weekly Jobless Claims (chaque jeudi 7:30 CT)
# PCE = Personal Consumption Expenditures (fin de mois)

# NFP dates (1er vendredi du mois) - 2022-2026
nfp_dates = [
    # 2022
    "2022-11-04", "2022-12-02",
    # 2023
    "2023-01-06", "2023-02-03", "2023-03-10", "2023-04-07", "2023-05-05",
    "2023-06-02", "2023-07-07", "2023-08-04", "2023-09-01", "2023-10-06",
    "2023-11-03", "2023-12-08",
    # 2024
    "2024-01-05", "2024-02-02", "2024-03-08", "2024-04-05", "2024-05-03",
    "2024-06-07", "2024-07-05", "2024-08-02", "2024-09-06", "2024-10-04",
    "2024-11-01", "2024-12-06",
    # 2025
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02",
    "2025-06-06", "2025-07-03", "2025-08-01", "2025-09-05", "2025-10-03",
    "2025-11-07", "2025-12-05",
    # 2026
    "2026-01-09", "2026-02-06",
]

# CPI dates (~10-15 du mois)
cpi_dates = [
    # 2022
    "2022-11-10", "2022-12-13",
    # 2023
    "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10",
    "2023-06-13", "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12",
    "2023-11-14", "2023-12-12",
    # 2024
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15",
    "2024-06-12", "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10",
    "2024-11-13", "2024-12-11",
    # 2025
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13",
    "2025-06-11", "2025-07-10", "2025-08-12", "2025-09-10", "2025-10-14",
    "2025-11-12", "2025-12-10",
    # 2026
    "2026-01-13", "2026-02-11",
]

# PPI dates (~15 du mois, souvent 1 jour apres ou avant CPI)
ppi_dates = [
    "2023-01-18", "2023-02-16", "2023-03-15", "2023-04-13", "2023-05-11",
    "2023-06-14", "2023-07-13", "2023-08-11", "2023-09-14", "2023-10-11",
    "2023-11-15", "2023-12-13",
    "2024-01-12", "2024-02-16", "2024-03-14", "2024-04-11", "2024-05-14",
    "2024-06-13", "2024-07-12", "2024-08-13", "2024-09-12", "2024-10-11",
    "2024-11-14", "2024-12-12",
    "2025-01-14", "2025-02-13", "2025-03-13", "2025-04-11", "2025-05-15",
    "2025-06-12", "2025-07-15", "2025-08-14", "2025-09-11", "2025-10-15",
    "2025-11-13", "2025-12-11",
    "2026-01-15", "2026-02-12",
]

# FOMC decision dates (13:00 CT statement, pas 7:30)
fomc_dates = [
    "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-17",
    "2026-01-28",
]

# Retail Sales (~15 du mois)
retail_dates = [
    "2023-01-18", "2023-02-15", "2023-03-15", "2023-04-14", "2023-05-16",
    "2023-06-15", "2023-07-18", "2023-08-15", "2023-09-14", "2023-10-17",
    "2023-11-15", "2023-12-14",
    "2024-01-17", "2024-02-15", "2024-03-14", "2024-04-15", "2024-05-15",
    "2024-06-18", "2024-07-16", "2024-08-15", "2024-09-17", "2024-10-17",
    "2024-11-15", "2024-12-17",
    "2025-01-16", "2025-02-14", "2025-03-17", "2025-04-16", "2025-05-15",
    "2025-06-17", "2025-07-16", "2025-08-15", "2025-09-16", "2025-10-16",
    "2025-11-14", "2025-12-16",
    "2026-01-16", "2026-02-17",
]

# Weekly Jobless Claims = chaque jeudi
# On les detecte automatiquement (weekday == 3)

def build_calendar():
    """Construit un dict date -> list d'evenements."""
    cal = defaultdict(list)
    for d in nfp_dates:
        cal[d].append("NFP")
    for d in cpi_dates:
        cal[d].append("CPI")
    for d in ppi_dates:
        cal[d].append("PPI")
    for d in fomc_dates:
        cal[d].append("FOMC")
    for d in retail_dates:
        cal[d].append("RETAIL")
    return cal

def main():
    cal = build_calendar()

    trades = []
    with open('output/backtest_hybrid.csv', 'r') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            trades.append(row)

    # Tous les trades h7
    h7 = []
    for t in trades:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        if dt.hour == 7:
            h7.append(t)

    # Classer chaque trade h7
    news_trades = []
    no_news_trades = []
    claims_only = []

    for t in h7:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        date_str = dt.strftime('%Y-%m-%d')
        events = cal.get(date_str, [])
        is_thursday = dt.weekday() == 3

        if is_thursday and not events:
            events.append("CLAIMS")

        if events:
            news_trades.append((t, events))
        else:
            no_news_trades.append(t)

    print("=" * 80)
    print("  TRADES HEURE 7 CT : CORRELATION AVEC NEWS ECONOMIQUES")
    print("=" * 80)
    print()

    # Stats globales
    news_pnls = [float(t['PnL_Net']) for t, _ in news_trades]
    no_news_pnls = [float(t['PnL_Net']) for t in no_news_trades]

    print(f"  AVEC NEWS:  {len(news_pnls)} trades | PnL ${sum(news_pnls):,.0f} | "
          f"Avg ${sum(news_pnls)/len(news_pnls):,.0f} | "
          f"WR {100*sum(1 for p in news_pnls if p > 0)/len(news_pnls):.0f}%")
    print(f"  SANS NEWS:  {len(no_news_pnls)} trades | PnL ${sum(no_news_pnls):,.0f} | "
          f"Avg ${sum(no_news_pnls)/len(no_news_pnls):,.0f} | "
          f"WR {100*sum(1 for p in no_news_pnls if p > 0)/len(no_news_pnls):.0f}%")

    # Par type d'evenement
    print()
    print("  PAR TYPE D'EVENEMENT:")
    print(f"  {'Event':<10} {'Trades':>7} {'PnL':>10} {'Avg':>8} {'WR':>6}")
    print("  " + "-" * 45)

    event_stats = defaultdict(lambda: {'pnls': []})
    for t, events in news_trades:
        pnl = float(t['PnL_Net'])
        for e in events:
            event_stats[e]['pnls'].append(pnl)

    for event in ['NFP', 'CPI', 'PPI', 'FOMC', 'RETAIL', 'CLAIMS']:
        if event in event_stats:
            pnls = event_stats[event]['pnls']
            wr = 100 * sum(1 for p in pnls if p > 0) / len(pnls)
            print(f"  {event:<10} {len(pnls):>5}   ${sum(pnls):>8,.0f} ${sum(pnls)/len(pnls):>6,.0f} {wr:>5.0f}%")

    # Top 10 meilleurs trades h7 avec news
    print()
    print("  TOP 10 MEILLEURS TRADES HEURE 7 CT:")
    print(f"  {'Date':<20} {'PnL':>8} {'Exit':>12} {'Z-Entry':>8} {'News':>15}")
    print("  " + "-" * 70)

    all_h7_sorted = sorted(
        [(t, cal.get(datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d'), []))
         for t in h7],
        key=lambda x: float(x[0]['PnL_Net']),
        reverse=True
    )

    for t, events in all_h7_sorted[:10]:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        is_thu = dt.weekday() == 3
        if is_thu and not events:
            events = ["CLAIMS"]
        news_str = ", ".join(events) if events else "-"
        print(f"  {t['Entry_DateTime']:<20} ${float(t['PnL_Net']):>6,.0f}   {t['Exit_Reason']:>12} "
              f"{float(t['Entry_ZScore']):>7.2f}   {news_str}")

    # Top 10 pires trades h7
    print()
    print("  TOP 10 PIRES TRADES HEURE 7 CT:")
    print(f"  {'Date':<20} {'PnL':>8} {'Exit':>12} {'Z-Entry':>8} {'News':>15}")
    print("  " + "-" * 70)

    for t, events in all_h7_sorted[-10:]:
        dt = datetime.strptime(t['Entry_DateTime'], '%Y-%m-%d %H:%M:%S')
        is_thu = dt.weekday() == 3
        if is_thu and not events:
            events = ["CLAIMS"]
        news_str = ", ".join(events) if events else "-"
        print(f"  {t['Entry_DateTime']:<20} ${float(t['PnL_Net']):>6,.0f}   {t['Exit_Reason']:>12} "
              f"{float(t['Entry_ZScore']):>7.2f}   {news_str}")

    # Resume
    print()
    print("=" * 80)
    print("  RESUME")
    print("=" * 80)
    news_pct = 100 * len(news_pnls) / len(h7)
    news_pnl_pct = 100 * sum(news_pnls) / (sum(news_pnls) + sum(no_news_pnls)) if (sum(news_pnls) + sum(no_news_pnls)) != 0 else 0
    print(f"  Trades h7 avec news: {len(news_pnls)}/{len(h7)} ({news_pct:.0f}%)")
    print(f"  PnL h7 news: ${sum(news_pnls):,.0f} / ${sum(news_pnls)+sum(no_news_pnls):,.0f} ({news_pnl_pct:.0f}%)")


if __name__ == '__main__':
    main()
