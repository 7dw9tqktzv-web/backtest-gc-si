# ============================================================================
# REPORT_GENERATOR.PY - Analyse post-grid-search et generation de rapports
# ============================================================================
#
# Genere automatiquement :
#   1. Un resume compact (output/latest_summary.txt, ~20 lignes)
#   2. Une section CHANGELOG.md formatee en markdown
#   3. Des tableaux top N par PnL et Sharpe
#
# Usage CLI :
#   python src/report_generator.py output/grid_search_xxx.csv --description "Phase 2+3: ..."
#
# ============================================================================

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================================
# CHARGEMENT DU CSV
# ============================================================================

def load_grid_csv(path: str) -> pd.DataFrame:
    """
    Charge un CSV de grid search (separateur ;).
    Detecte automatiquement les colonnes disponibles.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV introuvable : {path}")

    df = pd.read_csv(p, sep=';')
    print(f"[report] Charge {len(df)} lignes depuis {p.name}")
    print(f"[report] Colonnes : {', '.join(df.columns)}")
    return df


# ============================================================================
# STATISTIQUES RESUMEES
# ============================================================================

def compute_summary_stats(df: pd.DataFrame) -> dict:
    """
    Calcule les statistiques globales du grid search.
    Retourne un dict avec les metriques cles.
    """
    total = len(df)
    profitable = df[df['pnl_net'] > 0]
    n_profitable = len(profitable)
    pct_profitable = (n_profitable / total * 100) if total > 0 else 0

    stats = {
        'total': total,
        'profitable': n_profitable,
        'pct_profitable': round(pct_profitable, 1),
        'best_pnl': None,
        'best_pnl_label': '',
        'best_sharpe': None,
        'best_sharpe_label': '',
        'avg_pnl': round(df['pnl_net'].mean(), 0),
        'median_pnl': round(df['pnl_net'].median(), 0),
    }

    if n_profitable > 0:
        best_pnl_row = df.loc[df['pnl_net'].idxmax()]
        stats['best_pnl'] = round(best_pnl_row['pnl_net'], 0)
        stats['best_pnl_label'] = best_pnl_row['label']

        # Sharpe : filtrer min 10 trades pour eviter les outliers
        df_min_trades = df[df['trades'] >= 10]
        if len(df_min_trades) > 0 and 'sharpe' in df.columns:
            best_sharpe_row = df_min_trades.loc[df_min_trades['sharpe'].idxmax()]
            stats['best_sharpe'] = round(best_sharpe_row['sharpe'], 2)
            stats['best_sharpe_label'] = best_sharpe_row['label']

    return stats


# ============================================================================
# TABLEAUX TOP N
# ============================================================================

def build_top_n_table(df: pd.DataFrame, sort_by: str = 'pnl_net',
                      n: int = 10, min_trades: int = 0) -> str:
    """
    Construit un tableau markdown des top N configs.
    Colonnes adaptatives selon ce qui est disponible dans le DataFrame.
    """
    df_filtered = df.copy()
    if min_trades > 0:
        df_filtered = df_filtered[df_filtered['trades'] >= min_trades]

    if len(df_filtered) == 0:
        return "_Aucune config avec >= {min_trades} trades._\n"

    # Trier (descending pour pnl et sharpe, ascending pour max_dd)
    ascending = False
    df_sorted = df_filtered.sort_values(sort_by, ascending=ascending).head(n)

    # Colonnes de base toujours presentes
    cols = ['label', 'trades', 'win_rate', 'pnl_net', 'profit_factor', 'max_dd']
    # Ajouter sharpe si disponible
    if 'sharpe' in df.columns:
        cols.append('sharpe')
    # Ajouter colonnes exit si disponibles
    for exit_col in ['tp_zscore', 'tp_dollar', 'sl_zscore', 'sl_dollar']:
        if exit_col in df.columns:
            pass  # On les inclut pas dans le tableau compact

    # Filtrer colonnes existantes
    cols = [c for c in cols if c in df_sorted.columns]

    # Headers
    header_map = {
        'label': 'Config',
        'trades': 'Trades',
        'win_rate': 'WR%',
        'pnl_net': 'PnL',
        'profit_factor': 'PF',
        'max_dd': 'MaxDD',
        'sharpe': 'Sharpe',
    }

    headers = ['#'] + [header_map.get(c, c) for c in cols]
    sep = ['---'] * len(headers)

    lines = []
    lines.append('| ' + ' | '.join(headers) + ' |')
    lines.append('| ' + ' | '.join(sep) + ' |')

    for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
        values = [str(rank)]
        for c in cols:
            val = row[c]
            if c == 'pnl_net':
                values.append(f"${val:,.0f}")
            elif c == 'max_dd':
                values.append(f"-${abs(val):,.0f}")
            elif c == 'win_rate':
                values.append(f"{val:.1f}%")
            elif c == 'profit_factor':
                values.append(f"{val:.2f}")
            elif c == 'sharpe':
                values.append(f"{val:.2f}")
            elif c == 'trades':
                values.append(f"{int(val):,}")
            else:
                values.append(str(val))
        lines.append('| ' + ' | '.join(values) + ' |')

    return '\n'.join(lines) + '\n'


# ============================================================================
# RECHERCHE DE GRID SEARCHES PRECEDENTS
# ============================================================================

def find_previous_grid_searches(current_path: str) -> list:
    """
    Scanne output/grid_search*.csv pour trouver les fichiers precedents.
    Retourne la liste triee par date de modification (plus recent en premier),
    en excluant le fichier courant.
    """
    output_dir = Path('output')
    if not output_dir.exists():
        return []

    current = Path(current_path).resolve()
    results = []
    for f in output_dir.glob('grid_search*.csv'):
        if f.resolve() != current:
            results.append(f)

    # Trier par date de modification (plus recent d'abord)
    results.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return results


# ============================================================================
# COMPARAISON AVEC UN GRID SEARCH PRECEDENT
# ============================================================================

def compare_with_previous(df: pd.DataFrame, prev_path: str) -> str:
    """
    Genere un tableau comparatif entre le grid search courant et un precedent.
    """
    try:
        df_prev = pd.read_csv(prev_path, sep=';')
    except Exception as e:
        return f"_Impossible de charger {prev_path}: {e}_\n"

    stats_curr = compute_summary_stats(df)
    stats_prev = compute_summary_stats(df_prev)

    prev_name = Path(prev_path).stem

    lines = []
    lines.append(f'| Metric | {prev_name} | Current | Delta |')
    lines.append('| --- | --- | --- | --- |')

    rows = [
        ('Total configs', stats_prev['total'], stats_curr['total']),
        ('Profitable', f"{stats_prev['profitable']} ({stats_prev['pct_profitable']}%)",
         f"{stats_curr['profitable']} ({stats_curr['pct_profitable']}%)", None),
        ('Best PnL', stats_prev['best_pnl'], stats_curr['best_pnl']),
        ('Best Sharpe', stats_prev['best_sharpe'], stats_curr['best_sharpe']),
        ('Avg PnL', stats_prev['avg_pnl'], stats_curr['avg_pnl']),
        ('Median PnL', stats_prev['median_pnl'], stats_curr['median_pnl']),
    ]

    for row in rows:
        if len(row) == 4:
            # Texte brut, pas de delta calculable
            name, prev_val, curr_val, _ = row
            lines.append(f'| {name} | {prev_val} | {curr_val} | -- |')
        else:
            name, prev_val, curr_val = row
            if prev_val is not None and curr_val is not None:
                delta = curr_val - prev_val
                sign = '+' if delta >= 0 else ''
                if isinstance(delta, float):
                    lines.append(f'| {name} | {prev_val:,.0f} | {curr_val:,.0f} | {sign}{delta:,.0f} |')
                else:
                    lines.append(f'| {name} | {prev_val:,} | {curr_val:,} | {sign}{delta:,} |')
            else:
                pv = str(prev_val) if prev_val is not None else 'N/A'
                cv = str(curr_val) if curr_val is not None else 'N/A'
                lines.append(f'| {name} | {pv} | {cv} | -- |')

    return '\n'.join(lines) + '\n'


# ============================================================================
# EXTRACTION DES CONCLUSIONS CLES (HEURISTIQUES)
# ============================================================================

def extract_key_findings(df: pd.DataFrame, summary: dict) -> list:
    """
    Genere des bullet points de conclusions automatiques.
    Analyse les patterns dans les configs profitables.
    """
    findings = []

    # 1. Taux de profitabilite
    findings.append(
        f"{summary['profitable']}/{summary['total']} configs profitable "
        f"({summary['pct_profitable']}%)"
    )

    # 2. Best PnL
    if summary['best_pnl'] is not None:
        findings.append(
            f"Best PnL: ${summary['best_pnl']:,.0f} -- {summary['best_pnl_label']}"
        )

    # 3. Analyser zscore_entry si la colonne existe
    if 'zE' in df.columns:
        profitable = df[df['pnl_net'] > 0]
        if len(profitable) > 0:
            ze_counts = profitable['zE'].value_counts()
            dominant = ze_counts.index[0]
            pct = ze_counts.iloc[0] / len(profitable) * 100
            if pct > 70:
                findings.append(
                    f"zscore_entry={dominant} domine ({pct:.0f}% des configs rentables)"
                )

    # 4. Analyser zscore_period si disponible
    if 'zp' in df.columns:
        profitable = df[df['pnl_net'] > 0]
        if len(profitable) > 0:
            zp_counts = profitable['zp'].value_counts()
            zp_dominant = zp_counts.index[0]
            findings.append(f"zscore_period={zp_dominant} le plus frequent dans les rentables")

    # 5. Analyser TP/SL dollar si disponibles
    if 'TP' in df.columns and 'SL' in df.columns:
        profitable = df[df['pnl_net'] > 0]
        if len(profitable) > 0:
            tp_counts = profitable['TP'].value_counts()
            sl_counts = profitable['SL'].value_counts()
            findings.append(
                f"TP=${tp_counts.index[0]} et SL=-${sl_counts.index[0]} dominent les rentables"
            )

    # 6. Nombre moyen de trades
    findings.append(f"Trades moyen: {df['trades'].mean():.0f} | median: {df['trades'].median():.0f}")

    # 7. Slippage comparison si on detecte des colonnes differentes
    # (sera utile pour des CSV avec 1tick vs 2tick)

    return findings


# ============================================================================
# GENERATION DE LA SECTION CHANGELOG
# ============================================================================

def generate_changelog_section(
    description: str,
    csv_path: str,
    summary: dict,
    top_pnl_table: str,
    top_sharpe_table: str,
    comparison_table: str,
    findings: list,
) -> str:
    """
    Genere une section markdown complete pour CHANGELOG.md.
    """
    now = datetime.now().strftime('%Y-%m-%d')
    csv_name = Path(csv_path).name

    lines = []
    lines.append(f'## [{now}] Grid Search -- {description}')
    lines.append('')
    lines.append(f'**Configs**: {summary["total"]:,} | '
                 f'**Profitable**: {summary["profitable"]:,} ({summary["pct_profitable"]}%)')
    lines.append(f'Results: `output/{csv_name}`')
    lines.append('')

    # Top 10 PnL
    lines.append('### Top 10 by PnL Net')
    lines.append('')
    lines.append(top_pnl_table)
    lines.append('')

    # Top 10 Sharpe
    lines.append('### Top 10 by Sharpe (min 10 trades)')
    lines.append('')
    lines.append(top_sharpe_table)
    lines.append('')

    # Comparaison
    if comparison_table:
        lines.append('### Comparison vs previous')
        lines.append('')
        lines.append(comparison_table)
        lines.append('')

    # Key findings
    lines.append('### Key Findings')
    lines.append('')
    for f in findings:
        lines.append(f'- {f}')
    lines.append('')

    return '\n'.join(lines)


# ============================================================================
# INSERTION DANS CHANGELOG.MD (AVEC DEDUP)
# ============================================================================

def prepend_to_changelog(section: str) -> None:
    """
    Insere une section en tete de CHANGELOG.md.
    Si une section avec le meme header existe deja, elle est remplacee.
    """
    changelog_path = Path('CHANGELOG.md')

    if not changelog_path.exists():
        changelog_path.write_text(f'# CHANGELOG.md\n\n{section}', encoding='utf-8')
        print('[report] CHANGELOG.md cree')
        return

    content = changelog_path.read_text(encoding='utf-8')

    # Extraire le header de la nouvelle section pour dedup
    first_line = section.strip().split('\n')[0]
    # Pattern : ## [date] Grid Search -- description
    match = re.match(r'## \[[\d-]+\] Grid Search -- (.+)', first_line)
    if match:
        desc = re.escape(match.group(1))
        # Supprimer la section existante avec la meme description (meme date ou autre)
        pattern = rf'## \[[\d-]+\] Grid Search -- {desc}\n.*?(?=\n## |\Z)'
        content = re.sub(pattern, '', content, flags=re.DOTALL)
        # Nettoyer les lignes vides multiples laissees par la suppression
        content = re.sub(r'\n{3,}', '\n\n', content).strip()

    # Inserer apres le titre principal "# CHANGELOG.md" et sa description
    # On cherche la premiere ligne ## existante
    insert_match = re.search(r'\n(## )', content)
    if insert_match:
        pos = insert_match.start()
        new_content = content[:pos] + '\n\n' + section + '\n' + content[pos:]
    else:
        # Pas de section ## existante, ajouter a la fin
        new_content = content.rstrip() + '\n\n' + section

    changelog_path.write_text(new_content, encoding='utf-8')
    print(f'[report] CHANGELOG.md mis a jour')


# ============================================================================
# ECRITURE DU RESUME COMPACT
# ============================================================================

def write_summary(
    csv_path: str,
    description: str,
    summary: dict,
    findings: list,
    changelog_updated: bool = True,
) -> str:
    """
    Ecrit output/latest_summary.txt (compact, ~20 lignes max).
    C'est ce fichier que le contexte principal Claude lit.
    Retourne le contenu du fichier.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    csv_name = Path(csv_path).name

    lines = []
    lines.append('GRID SEARCH SUMMARY')
    lines.append(f'Date: {now}')
    lines.append(f'Description: {description}')
    lines.append(f'CSV: output/{csv_name}')
    lines.append(f'Total: {summary["total"]:,} | Profitable: {summary["profitable"]:,} '
                 f'({summary["pct_profitable"]}%)')

    if summary['best_pnl'] is not None:
        lines.append(f'Best PnL: ${summary["best_pnl"]:,.0f} -- {summary["best_pnl_label"]}')
    if summary['best_sharpe'] is not None:
        lines.append(f'Best Sharpe: {summary["best_sharpe"]:.2f} -- {summary["best_sharpe_label"]}')

    lines.append(f'Avg PnL: ${summary["avg_pnl"]:,.0f} | Median: ${summary["median_pnl"]:,.0f}')
    lines.append('Findings:')
    # Limiter a 5 findings pour rester compact
    for f in findings[:5]:
        lines.append(f'- {f}')

    lines.append(f'CHANGELOG: {"Updated" if changelog_updated else "Not updated"}')

    content = '\n'.join(lines) + '\n'

    output_path = Path('output/latest_summary.txt')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    print(f'[report] Resume ecrit dans {output_path} ({len(lines)} lignes)')

    return content


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def run_report(csv_path: str, description: str, no_changelog: bool = False,
               archive: bool = False, timeframe: str = "1min",
               exit_mode: str = "dollar", slippage: str = "1tick") -> str:
    """
    Pipeline complet : charge CSV -> analyse -> CHANGELOG -> resume.
    Retourne le contenu du resume.
    """
    print(f'[report] === Analyse de {csv_path} ===')

    # 1. Charger les donnees
    df = load_grid_csv(csv_path)

    # 2. Statistiques
    summary = compute_summary_stats(df)
    print(f'[report] {summary["profitable"]}/{summary["total"]} configs profitable '
          f'({summary["pct_profitable"]}%)')

    # 3. Tableaux top N
    top_pnl = build_top_n_table(df, sort_by='pnl_net', n=10)
    top_sharpe = build_top_n_table(df, sort_by='sharpe', n=10, min_trades=10)

    # 4. Comparaison avec precedent
    comparison = ''
    prev_files = find_previous_grid_searches(csv_path)
    if prev_files:
        comparison = compare_with_previous(df, str(prev_files[0]))
        print(f'[report] Comparaison avec {prev_files[0].name}')

    # 5. Conclusions
    findings = extract_key_findings(df, summary)

    # 6. CHANGELOG
    changelog_updated = False
    if not no_changelog:
        section = generate_changelog_section(
            description=description,
            csv_path=csv_path,
            summary=summary,
            top_pnl_table=top_pnl,
            top_sharpe_table=top_sharpe,
            comparison_table=comparison,
            findings=findings,
        )
        prepend_to_changelog(section)
        changelog_updated = True

    # 7. Resume compact
    content = write_summary(
        csv_path=csv_path,
        description=description,
        summary=summary,
        findings=findings,
        changelog_updated=changelog_updated,
    )

    # 8. Archiver les top 20 si demande
    if archive:
        from .archive_manager import archive_top_n_from_grid, generate_rankings
        print('[report] Archivage des top 20...')
        paths = archive_top_n_from_grid(csv_path, n=20, timeframe=timeframe,
                                         exit_mode=exit_mode, slippage=slippage)
        print(f'[report] {len(paths)} configs archivees')
        generate_rankings()
        print('[report] Rankings mis a jour')

    print('[report] === Termine ===')
    return content


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Analyse post-grid-search et generation de rapports'
    )
    parser.add_argument('csv_path', help='Chemin vers le CSV de grid search')
    parser.add_argument('--description', '-d', default='Grid Search',
                        help='Description pour le CHANGELOG (ex: "Phase 2+3: no TP zscore")')
    parser.add_argument('--no-changelog', action='store_true',
                        help='Ne pas mettre a jour CHANGELOG.md')
    parser.add_argument('--archive', action='store_true',
                        help='Archiver les top 20 configs')
    parser.add_argument('--timeframe', default='1min',
                        help='Timeframe pour archivage (default: 1min)')
    parser.add_argument('--exit-mode', default='dollar',
                        help='Exit mode pour archivage (default: dollar)')
    parser.add_argument('--slippage', default='1tick',
                        help='Slippage pour archivage (default: 1tick)')

    args = parser.parse_args()
    run_report(args.csv_path, args.description, args.no_changelog,
               archive=args.archive, timeframe=args.timeframe,
               exit_mode=args.exit_mode, slippage=args.slippage)


if __name__ == '__main__':
    main()
