"""
archive_manager.py - Gestion structuree des archives de backtests
================================================================
Ce module centralise l'archivage des resultats :
  - archive_config() : archiver une config individuelle
  - archive_top_n_from_grid() : archiver le top N d'un grid search
  - generate_rankings() : generer les classements (CSV + dashboard)
  - generate_dashboard() : generer DASHBOARD.md
  - list_configs() : lister les configs archivees

Usage CLI :
    python src/archive_manager.py --action generate-rankings
    python src/archive_manager.py --action dashboard
    python src/archive_manager.py --action list --timeframe 1min
    python src/archive_manager.py --action archive-top --csv output/grid.csv --n 20
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE_DIR / "output" / "archive"
RAW_DIR = BASE_DIR / "output" / "raw"
RANKINGS_DIR = BASE_DIR / "output" / "rankings"
LATEST_DIR = BASE_DIR / "output" / "latest"


# ---------------------------------------------------------------------------
# Fonctions privees (helpers)
# ---------------------------------------------------------------------------


def _detect_exit_mode(df: pd.DataFrame) -> str:
    """Detecte le mode de sortie a partir des colonnes du DataFrame."""
    if "zTP" in df.columns:
        return "zscore"
    if "TP" in df.columns:
        return "dollar"
    return "dollar"


def _metrics_from_csv_row(row: pd.Series) -> dict:
    """Extrait les metriques d'une ligne de CSV grid search."""
    metrics = {
        "trades": int(row.get("trades", 0)),
        "long": int(row.get("long", 0)),
        "short": int(row.get("short", 0)),
        "win_rate": float(row.get("win_rate", 0.0)),
        "pnl_net": float(row.get("pnl_net", 0.0)),
        "pnl_avg": float(row.get("pnl_avg", 0.0)),
        "profit_factor": float(row.get("profit_factor", 0.0)),
        "max_dd": float(row.get("max_dd", 0.0)),
        "sharpe": float(row.get("sharpe", 0.0)),
    }

    # Compteurs de sorties (optionnels)
    for col in ("tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar"):
        if col in row.index:
            metrics[col] = int(row[col])

    # Calmar = PnL / |MaxDD|
    if metrics["max_dd"] != 0:
        metrics["calmar"] = metrics["pnl_net"] / abs(metrics["max_dd"])
    else:
        metrics["calmar"] = 0.0

    return metrics


def _config_from_csv_row(row: pd.Series, exit_mode: str) -> dict:
    """Reconstruit un dict de config partiel a partir d'une ligne CSV."""
    config: dict = {
        "indicators": {},
        "entry": {},
        "exit": {},
    }

    # -- Indicateurs --
    if "beta" in row.index:
        config["indicators"]["beta_lookback"] = int(row["beta"])
    if "zp" in row.index:
        config["indicators"]["zscore_period"] = int(row["zp"])
    if "cp" in row.index:
        config["indicators"]["correlation_period"] = int(row["cp"])
    if "adf" in row.index:
        config["indicators"]["adf_hurst_period"] = int(row["adf"])

    # -- Entree --
    if "zE" in row.index:
        config["entry"]["zscore_entry"] = float(row["zE"])
    if "co" in row.index:
        config["entry"]["cointegration_score_min"] = int(row["co"])

    # -- Sortie (depend du mode) --
    if exit_mode == "dollar":
        if "TP" in row.index:
            config["exit"]["pnl_take_profit"] = float(row["TP"])
        if "SL" in row.index:
            config["exit"]["pnl_stop_loss"] = -abs(float(row["SL"]))
    elif exit_mode == "zscore":
        if "zTP" in row.index:
            config["exit"]["zscore_tp"] = float(row["zTP"])
        if "zSL" in row.index:
            config["exit"]["zscore_sl"] = float(row["zSL"])
        if "mode" in row.index:
            config["exit"]["mode"] = str(row["mode"])
    else:
        # hybrid ou inconnu : on prend tout ce qui existe
        for col, key in [("TP", "pnl_take_profit"), ("SL", "pnl_stop_loss"),
                         ("zTP", "zscore_tp"), ("zSL", "zscore_sl"),
                         ("mode", "mode")]:
            if col in row.index:
                val = row[col]
                if col == "SL":
                    val = -abs(float(val))
                config["exit"][key] = val

    return config


def _scan_archive_metrics() -> List[dict]:
    """Parcourt recursivement ARCHIVE_DIR pour trouver tous les *_metrics.json."""
    results: List[dict] = []

    if not ARCHIVE_DIR.exists():
        return results

    for json_path in ARCHIVE_DIR.rglob("*_metrics.json"):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fichier corrompu ou inaccessible, on skip
            continue

        # Derive les champs depuis le chemin :
        # ARCHIVE_DIR / timeframe / exit_mode / config_name / result_type / {slippage}_metrics.json
        result_type_dir = json_path.parent
        config_name_dir = result_type_dir.parent
        exit_mode_dir = config_name_dir.parent
        timeframe_dir = exit_mode_dir.parent

        data["timeframe"] = timeframe_dir.name
        data["exit_mode"] = exit_mode_dir.name
        data["config_name"] = config_name_dir.name
        data["result_type"] = result_type_dir.name

        # Slippage depuis le nom de fichier (ex: "1tick_metrics.json" -> "1tick")
        filename_stem = json_path.stem  # "1tick_metrics"
        slippage_part = filename_stem.replace("_metrics", "")
        data["slippage"] = slippage_part

        results.append(data)

    return results


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------


def archive_config(
    config_name: str,
    timeframe: str,
    exit_mode: str,
    result_type: str,
    slippage: str,
    files: dict,
    metrics: dict,
    config_snapshot: dict,
    run_name: Optional[str] = None,
) -> Path:
    """
    Archive une configuration individuelle.

    Cree la structure de dossiers, copie les fichiers, sauvegarde
    les metriques en JSON et le snapshot de config en YAML.

    Returns:
        Path du repertoire result_type cree.
    """
    # -- Repertoires --
    config_dir = ARCHIVE_DIR / timeframe / exit_mode / config_name
    result_dir = config_dir / result_type
    result_dir.mkdir(parents=True, exist_ok=True)

    # -- Copie des fichiers avec prefixe slippage --
    for target_name, source_path in files.items():
        source = Path(source_path)
        if source.exists():
            dest = result_dir / f"{slippage}_{target_name}"
            shutil.copy2(source, dest)

    # -- Sauvegarde des metriques --
    metrics_to_save = dict(metrics)
    metrics_to_save["archived_at"] = datetime.now().isoformat()
    if run_name is not None:
        metrics_to_save["run_name"] = run_name

    metrics_path = result_dir / f"{slippage}_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_to_save, f, indent=2, ensure_ascii=False)

    # -- Snapshot config (une seule fois par config_name) --
    config_yaml_path = config_dir / "config.yaml"
    if not config_yaml_path.exists():
        with open(config_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_snapshot, f, default_flow_style=False, allow_unicode=True)

    return result_dir


def archive_top_n_from_grid(
    csv_path: str | Path,
    n: int = 20,
    sort_by: str = "pnl_net",
    timeframe: str = "1min",
    exit_mode: str = "dollar",
    slippage: str = "1tick",
    min_trades: int = 0,
) -> List[Path]:
    """
    Archive le top N d'un fichier CSV de grid search.

    Lit le CSV, detecte le mode de sortie, trie, puis archive
    chaque config via archive_config(). Deplace le CSV original
    dans RAW_DIR.

    Returns:
        Liste des paths des repertoires archives.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, sep=";")

    # Auto-detection du mode de sortie
    exit_mode = _detect_exit_mode(df)

    # Filtre sur le nombre minimum de trades
    if min_trades > 0 and "trades" in df.columns:
        df = df[df["trades"] >= min_trades].copy()

    # Tri et selection du top N
    if sort_by not in df.columns:
        print(f"[WARN] Colonne '{sort_by}' absente du CSV, tri par 'pnl_net'")
        sort_by = "pnl_net"

    df_sorted = df.sort_values(by=sort_by, ascending=False).head(n)

    archived_paths: List[Path] = []

    for _, row in df_sorted.iterrows():
        # Nom de la config depuis la colonne "label"
        config_name = str(row.get("label", "unknown"))
        metrics = _metrics_from_csv_row(row)
        config_snapshot = _config_from_csv_row(row, exit_mode)

        # Pas de fichiers individuels a copier depuis un grid search CSV
        result_path = archive_config(
            config_name=config_name,
            timeframe=timeframe,
            exit_mode=exit_mode,
            result_type="grid_search",
            slippage=slippage,
            files={},
            metrics=metrics,
            config_snapshot=config_snapshot,
            run_name=csv_path.stem,
        )
        archived_paths.append(result_path)

    # -- Deplacement du CSV original vers RAW_DIR --
    raw_gs_dir = RAW_DIR / "grid_search"
    raw_gs_dir.mkdir(parents=True, exist_ok=True)

    date_prefix = datetime.now().strftime("%Y-%m-%d")
    dest_csv = raw_gs_dir / f"{date_prefix}_{csv_path.name}"
    shutil.move(str(csv_path), str(dest_csv))

    print(f"[OK] {len(archived_paths)} configs archivees depuis {csv_path.name}")
    print(f"     CSV deplace vers {dest_csv}")

    return archived_paths


def generate_rankings(top_n: int = 20) -> None:
    """
    Genere les classements a partir de toutes les metriques archivees.

    Produit des fichiers CSV par (timeframe, exit_mode), un classement
    global top 50, un classement walk-forward, et un DASHBOARD.md.
    """
    all_metrics = _scan_archive_metrics()

    if not all_metrics:
        print("[INFO] Aucune metrique trouvee dans les archives.")
        return

    RANKINGS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(all_metrics)

    # -- Classements par (timeframe, exit_mode) --
    for (tf, em), group in df.groupby(["timeframe", "exit_mode"]):
        ranked = group.sort_values(by="pnl_net", ascending=False).head(top_n)
        out_path = RANKINGS_DIR / f"{tf}_{em}_top{top_n}.csv"
        ranked.to_csv(out_path, sep=";", index=False)
        print(f"  -> {out_path.name} ({len(ranked)} configs)")

    # -- Classement global top 50 --
    global_ranked = df.sort_values(by="pnl_net", ascending=False).head(50)
    global_path = RANKINGS_DIR / "global_top50.csv"
    global_ranked.to_csv(global_path, sep=";", index=False)
    print(f"  -> global_top50.csv ({len(global_ranked)} configs)")

    # -- Walk-forward --
    wf_df = df[df["result_type"] == "walk_forward"]
    if len(wf_df) > 0:
        wf_ranked = wf_df.sort_values(by="pnl_net", ascending=False)
        wf_path = RANKINGS_DIR / "walk_forward_best.csv"
        wf_ranked.to_csv(wf_path, sep=";", index=False)
        print(f"  -> walk_forward_best.csv ({len(wf_ranked)} configs)")

    # -- Dashboard --
    generate_dashboard()

    print(f"[OK] Rankings generes dans {RANKINGS_DIR}")


def generate_dashboard() -> str:
    """
    Genere un fichier DASHBOARD.md avec un resume des classements.

    Lit tous les CSV de RANKINGS_DIR, formate en tables Markdown,
    et ajoute un resume par timeframe/exit_mode.

    Returns:
        Contenu du fichier DASHBOARD.md.
    """
    RANKINGS_DIR.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# Archive Dashboard")
    lines.append("")
    lines.append(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # -- Tables depuis les CSV de rankings --
    ranking_csvs = sorted(RANKINGS_DIR.glob("*.csv"))

    if not ranking_csvs:
        lines.append("No ranking files found.")
        lines.append("")
    else:
        for csv_path in ranking_csvs:
            try:
                df = pd.read_csv(csv_path, sep=";")
            except Exception:
                continue

            lines.append(f"## {csv_path.stem}")
            lines.append("")

            # Afficher le top 5
            top5 = df.head(5)

            if len(top5) == 0:
                lines.append("No data.")
                lines.append("")
                continue

            # Selectionner les colonnes les plus utiles pour le dashboard
            display_cols = []
            for col in ["config_name", "timeframe", "exit_mode", "slippage",
                         "trades", "pnl_net", "win_rate", "profit_factor",
                         "max_dd", "sharpe", "calmar", "result_type"]:
                if col in top5.columns:
                    display_cols.append(col)

            # Si aucune colonne standard, afficher toutes les colonnes
            if not display_cols:
                display_cols = list(top5.columns)

            top5_display = top5[display_cols]

            # En-tete Markdown
            header = "| " + " | ".join(str(c) for c in top5_display.columns) + " |"
            separator = "| " + " | ".join("---" for _ in top5_display.columns) + " |"
            lines.append(header)
            lines.append(separator)

            # Lignes de donnees
            for _, row in top5_display.iterrows():
                values = []
                for col in top5_display.columns:
                    val = row[col]
                    if isinstance(val, float):
                        values.append(f"{val:.2f}")
                    else:
                        values.append(str(val))
                line = "| " + " | ".join(values) + " |"
                lines.append(line)

            lines.append("")

    # -- Resume : comptage par timeframe/exit_mode --
    all_metrics = _scan_archive_metrics()
    if all_metrics:
        lines.append("## Summary")
        lines.append("")

        df_summary = pd.DataFrame(all_metrics)
        counts = df_summary.groupby(["timeframe", "exit_mode"]).size().reset_index(name="count")

        lines.append("| Timeframe | Exit Mode | Configs |")
        lines.append("| --- | --- | --- |")
        for _, row in counts.iterrows():
            lines.append(f"| {row['timeframe']} | {row['exit_mode']} | {row['count']} |")

        lines.append("")
        lines.append(f"**Total configs archived**: {len(all_metrics)}")
        lines.append("")

    content = "\n".join(lines)

    dashboard_path = RANKINGS_DIR / "DASHBOARD.md"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  -> DASHBOARD.md genere ({len(lines)} lignes)")

    return content


def list_configs(
    timeframe: Optional[str] = None,
    exit_mode: Optional[str] = None,
) -> pd.DataFrame:
    """
    Liste toutes les configs archivees avec leurs metriques.

    Returns:
        DataFrame triee par pnl_net decroissant.
    """
    all_metrics = _scan_archive_metrics()

    if not all_metrics:
        return pd.DataFrame()

    df = pd.DataFrame(all_metrics)

    # Filtrage optionnel
    if timeframe is not None:
        df = df[df["timeframe"] == timeframe]

    if exit_mode is not None:
        df = df[df["exit_mode"] == exit_mode]

    # Tri par PnL decroissant
    if "pnl_net" in df.columns:
        df = df.sort_values(by="pnl_net", ascending=False)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Point d'entree CLI pour l'archive manager."""
    parser = argparse.ArgumentParser(
        description="Gestion des archives de backtests GC/SI"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["archive-top", "generate-rankings", "dashboard", "list"],
        help="Action a executer",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Chemin du CSV (pour archive-top)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=20,
        help="Nombre de configs a archiver (default: 20)",
    )
    parser.add_argument(
        "--sort-by",
        type=str,
        default="pnl_net",
        help="Colonne de tri (default: pnl_net)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Filtre timeframe (1min, 5min)",
    )
    parser.add_argument(
        "--exit-mode",
        type=str,
        default=None,
        help="Filtre exit mode (dollar, zscore, hybrid)",
    )
    parser.add_argument(
        "--slippage",
        type=str,
        default="1tick",
        help="Slippage (default: 1tick)",
    )

    args = parser.parse_args()

    if args.action == "archive-top":
        if args.csv is None:
            parser.error("--csv requis pour l'action archive-top")
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"[ERREUR] Fichier introuvable : {csv_path}")
            return
        archive_top_n_from_grid(
            csv_path=csv_path,
            n=args.n,
            sort_by=args.sort_by,
            timeframe=args.timeframe or "1min",
            exit_mode=args.exit_mode or "dollar",
            slippage=args.slippage,
        )

    elif args.action == "generate-rankings":
        generate_rankings(top_n=args.n)

    elif args.action == "dashboard":
        content = generate_dashboard()
        print(content)

    elif args.action == "list":
        df = list_configs(timeframe=args.timeframe, exit_mode=args.exit_mode)
        if df.empty:
            print("[INFO] Aucune config archivee trouvee.")
        else:
            # Affichage des colonnes principales
            display_cols = []
            for col in ["config_name", "timeframe", "exit_mode", "slippage",
                         "result_type", "trades", "pnl_net", "win_rate",
                         "profit_factor", "max_dd", "sharpe", "calmar"]:
                if col in df.columns:
                    display_cols.append(col)

            if not display_cols:
                display_cols = list(df.columns)

            print(df[display_cols].to_string(index=False))
            print(f"\nTotal : {len(df)} config(s)")


if __name__ == "__main__":
    main()
