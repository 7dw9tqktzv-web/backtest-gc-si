"""
Comparaison Python vs Sierra Chart - Nouvel export avec session times corriges
"""
import pandas as pd
import numpy as np
from src.data_loader import load_and_prepare_data, resample_to_5min
from src.indicators import calculate_all_indicators
import yaml

def main():
    # NOUVELLES valeurs Sierra (session times corriges)
    sierra_data = {
        '2026-01-29 23:55:00': {'Beta': 1.3170965909957886, 'ADF': -4.1955437660217285, 'Corr': 0.8304221630096436, 'ZScore': -0.984348475933075, 'Hurst': 0.8591837882995605},
        '2026-01-29 23:50:00': {'Beta': 1.318608045578003,  'ADF': -4.123228073120117,  'Corr': 0.8271355032920837, 'ZScore': 0.041575685143470764, 'Hurst': 0.9382742047309875},
        '2026-01-29 23:45:00': {'Beta': 1.3201318979263306, 'ADF': -4.10114049911499,   'Corr': 0.8727150559425354, 'ZScore': 0.10495440661907196, 'Hurst': 0.9900000095367432},
        '2026-01-29 23:40:00': {'Beta': 1.3216427564620972, 'ADF': -4.126885890960693,  'Corr': 0.8951995372772217, 'ZScore': 0.846826434135437, 'Hurst': 0.928633451461792},
        '2026-01-29 23:35:00': {'Beta': 1.3231098651885986, 'ADF': -4.001471042633057,  'Corr': 0.8649389147758484, 'ZScore': 1.5326988697052002, 'Hurst': 0.9900000095367432},
        '2026-01-29 23:30:00': {'Beta': 1.3245117664337158, 'ADF': -4.358279705047607,  'Corr': 0.8685623407363892, 'ZScore': 0.8407025933265686, 'Hurst': 0.9900000095367432},
        '2026-01-29 23:00:00': {'Beta': 1.3333821296691895, 'ADF': -3.6980814933776855, 'Corr': 0.8465726375579834, 'ZScore': 1.2952215671539307, 'Hurst': 0.9900000095367432},
        '2026-01-29 22:30:00': {'Beta': 1.3425066471099854, 'ADF': -3.6108453273773193, 'Corr': 0.8890719413757324, 'ZScore': 0.7733521461486816, 'Hurst': 0.8965469598770142},
    }

    # Load Python data with beta_lookback=100 to match Sierra
    with open('config/strategy_params.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Best config from CHANGELOG: b1320_zp24_cp24_adf96_zE3.0_zTP2.0_zSL4.5_co50
    # These values are now in strategy_params.yaml, no override needed
    # config already has: beta_lookback=1320, zscore_period=24, correlation_period=24, adf_hurst_period=96

    print("Loading Python data...")
    df_1min, _, _ = load_and_prepare_data()
    df_5min = resample_to_5min(df_1min)
    df = calculate_all_indicators(df_5min, config)

    if 'DateTime' in df.columns:
        df = df.set_index('DateTime')

    print("\n" + "="*100)
    print("COMPARAISON PYTHON vs SIERRA (SESSION TIMES CORRIGES)")
    print("="*100)

    print(f"\n{'DateTime':<22} {'Indicator':<12} {'Python':>14} {'Sierra':>14} {'Diff':>12} {'Diff %':>10}")
    print("-"*90)

    for ts, sierra in sorted(sierra_data.items(), reverse=True):
        dt = pd.to_datetime(ts)
        if dt not in df.index:
            print(f"{ts:<22} NOT FOUND")
            continue

        row = df.loc[dt]

        for ind_name, sierra_val in sierra.items():
            if ind_name == 'Beta':
                py_val = row['Beta']
            elif ind_name == 'ADF':
                py_val = row['ADF_Statistic']
            elif ind_name == 'Corr':
                py_val = row['Correlation']
            elif ind_name == 'ZScore':
                py_val = row['ZScore']
            elif ind_name == 'Hurst':
                py_val = row['Hurst']
            else:
                continue

            diff = py_val - sierra_val
            diff_pct = abs(diff / sierra_val * 100) if sierra_val != 0 else 0

            marker = ""
            if diff_pct > 1:
                marker = " <-- >1%"
            elif diff_pct > 0.5:
                marker = " <-- >0.5%"

            print(f"{ts:<22} {ind_name:<12} {py_val:>14.6f} {sierra_val:>14.6f} {diff:>12.6f} {diff_pct:>9.2f}%{marker}")

        print()  # Empty line between timestamps


if __name__ == '__main__':
    main()
