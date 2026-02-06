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
CAMPAIGNS_DIR = ARCHIVE_DIR / "campaigns"
REPORTS_DIR = BASE_DIR / "output" / "reports"


# ---------------------------------------------------------------------------
# Fonctions privees (helpers)
# ---------------------------------------------------------------------------


def _safe_int(value, default: int = 0) -> int:
    """Convertit en int avec gestion NaN/None."""
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    """Convertit en float avec gestion NaN/None."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


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
        "trades": _safe_int(row.get("trades", 0)),
        "long": _safe_int(row.get("long", 0)),
        "short": _safe_int(row.get("short", 0)),
        "win_rate": _safe_float(row.get("win_rate", 0.0)),
        "pnl_net": _safe_float(row.get("pnl_net", 0.0)),
        "pnl_avg": _safe_float(row.get("pnl_avg", 0.0)),
        "profit_factor": _safe_float(row.get("profit_factor", 0.0)),
        "max_dd": _safe_float(row.get("max_dd", 0.0)),
        "sharpe": _safe_float(row.get("sharpe", 0.0)),
    }

    # Compteurs de sorties (optionnels)
    for col in ("tp_zscore", "tp_dollar", "sl_zscore", "sl_dollar"):
        if col in row.index:
            metrics[col] = _safe_int(row[col])

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
        config["indicators"]["beta_lookback"] = _safe_int(row["beta"])
    if "zp" in row.index:
        config["indicators"]["zscore_period"] = _safe_int(row["zp"])
    if "cp" in row.index:
        config["indicators"]["correlation_period"] = _safe_int(row["cp"])
    if "adf" in row.index:
        config["indicators"]["adf_hurst_period"] = _safe_int(row["adf"])

    # -- Entree --
    if "zE" in row.index:
        config["entry"]["zscore_entry"] = _safe_float(row["zE"])
    if "co" in row.index:
        config["entry"]["cointegration_score_min"] = _safe_int(row["co"])

    # -- Sortie (depend du mode) --
    if exit_mode == "dollar":
        if "TP" in row.index:
            config["exit"]["pnl_take_profit"] = _safe_float(row["TP"])
        if "SL" in row.index:
            config["exit"]["pnl_stop_loss"] = -abs(_safe_float(row["SL"]))
    elif exit_mode == "zscore":
        if "zTP" in row.index:
            config["exit"]["zscore_tp"] = _safe_float(row["zTP"])
        if "zSL" in row.index:
            config["exit"]["zscore_sl"] = _safe_float(row["zSL"])
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
                    val = -abs(_safe_float(val))
                elif col != "mode":
                    val = _safe_float(val)
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
# Fonctions publiques — Campagnes
# ---------------------------------------------------------------------------


def _sanitize_label(label: str) -> str:
    """Sanitize un label pour nom de dossier (. -> p, garder - et _)."""
    return label.replace(".", "p").replace(" ", "_")


def _guess_timeframe_slippage(campaign_name: str) -> tuple:
    """Devine timeframe et slippage depuis le nom de campagne."""
    tf = "5min" if "5min" in campaign_name else "1min"
    slip = "2tick" if "2tick" in campaign_name else "1tick"
    return tf, slip


def _compute_parameter_distribution(
    df: pd.DataFrame, exit_mode: str, top_n: int = 50,
) -> dict:
    """Calcule la distribution des parametres dans les top N rentables (trades>=80)."""
    rentables = df[(df["pnl_net"] > 0) & (df["trades"] >= 80)]
    top = rentables.nlargest(min(top_n, len(rentables)), "pnl_net")

    if len(top) == 0:
        return {}

    # Colonnes indicateurs + entree
    param_cols = ["beta", "zp", "cp", "adf", "zE", "co"]
    # Colonnes sortie selon le mode
    if exit_mode == "zscore":
        param_cols += ["zTP", "zSL"]
    elif exit_mode == "dollar":
        param_cols += ["TP", "SL"]

    dist = {}
    for col in param_cols:
        if col in top.columns:
            counts = top[col].value_counts().sort_index()
            dist[col] = {str(k): int(v) for k, v in counts.items()}

    return dist


def archive_campaign(
    csv_path: str | Path,
    campaign_name: str,
    top_n: int = 20,
    sort_by: str = "pnl_net",
    min_trades: int = 50,
    description: str = "",
) -> dict:
    """
    Archive une campagne complete de grid search.

    Cree la structure :
        output/archive/campaigns/{campaign_name}/
            campaign_meta.json
            full_results.csv
            top{n}/
                01_{config_label}/metrics.json + config.yaml

    Returns:
        dict avec les stats de la campagne (campaign_meta).
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, sep=";")
    df = df.dropna(subset=["pnl_net", "trades"])

    # -- Repertoire campagne --
    campaign_dir = CAMPAIGNS_DIR / campaign_name
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Copier le CSV complet
    shutil.copy2(str(csv_path), str(campaign_dir / "full_results.csv"))

    # -- Stats agregees --
    total_configs = len(df)
    exit_mode = _detect_exit_mode(df)
    tf, slip = _guess_timeframe_slippage(campaign_name)

    filt_50 = df[(df["pnl_net"] > 0) & (df["trades"] >= min_trades)]
    filt_80 = df[(df["pnl_net"] > 0) & (df["trades"] >= 80)]
    filt_ppt = filt_80[filt_80["pnl_avg"] >= 150] if "pnl_avg" in df.columns else pd.DataFrame()

    profitable_configs = len(filt_50)
    profitable_configs_80 = len(filt_80)
    profitable_pct = round(profitable_configs / max(total_configs, 1) * 100, 1)
    pnl_per_trade_ge_150 = len(filt_ppt)

    # Top metrics parmi trades >= min_trades
    df_valid = df[df["trades"] >= min_trades]
    if len(df_valid) > 0:
        best_row = df_valid.loc[df_valid["pnl_net"].idxmax()]
        top_pnl = float(best_row["pnl_net"])
        top_pnl_per_trade = float(best_row.get("pnl_avg", 0))
        top_config_label = str(best_row.get("label", "unknown"))
        top_sharpe = float(df_valid["sharpe"].max()) if "sharpe" in df_valid.columns else 0.0
        top_pf = float(df_valid["profit_factor"].max()) if "profit_factor" in df_valid.columns else 0.0
    else:
        top_pnl = top_pnl_per_trade = top_sharpe = top_pf = 0.0
        top_config_label = "none"

    median_ppt = float(filt_80["pnl_avg"].median()) if len(filt_80) > 0 and "pnl_avg" in filt_80.columns else 0.0

    # -- Distribution des parametres --
    param_dist = _compute_parameter_distribution(df, exit_mode)

    # -- Archiver les top N --
    top_dir_name = f"top{top_n}"
    top_dir = campaign_dir / top_dir_name

    df_top = df_valid.sort_values(by=sort_by, ascending=False).head(top_n) if len(df_valid) > 0 else pd.DataFrame()

    for i, (_, row) in enumerate(df_top.iterrows()):
        label = str(row.get("label", f"config_{i}"))
        label_safe = _sanitize_label(label)
        config_dir = top_dir / f"{i + 1:02d}_{label_safe}"
        config_dir.mkdir(parents=True, exist_ok=True)

        # metrics.json
        metrics = _metrics_from_csv_row(row)
        metrics["rank"] = i + 1
        metrics["archived_at"] = datetime.now().isoformat()
        with open(config_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        # config.yaml
        config_snapshot = _config_from_csv_row(row, exit_mode)
        with open(config_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config_snapshot, f, default_flow_style=False, allow_unicode=True)

    # -- campaign_meta.json --
    campaign_meta = {
        "campaign_name": campaign_name,
        "description": description,
        "archived_at": datetime.now().isoformat(),
        "timeframe": tf,
        "exit_mode": exit_mode,
        "slippage": slip,
        "total_configs": total_configs,
        "profitable_configs": profitable_configs,
        "profitable_configs_80": profitable_configs_80,
        "profitable_pct": profitable_pct,
        "pnl_per_trade_ge_150": pnl_per_trade_ge_150,
        "median_pnl_per_trade": round(median_ppt, 2),
        "top_pnl": round(top_pnl, 2),
        "top_pnl_per_trade": round(top_pnl_per_trade, 2),
        "top_sharpe": round(top_sharpe, 2),
        "top_pf": round(top_pf, 2),
        "top_config_label": top_config_label,
        "parameter_distribution": param_dist,
    }

    with open(campaign_dir / "campaign_meta.json", "w", encoding="utf-8") as f:
        json.dump(campaign_meta, f, indent=2, ensure_ascii=False)

    # -- Resume --
    print(f"[OK] Campagne {campaign_name} archivee")
    print(f"     Total: {total_configs:,} configs")
    print(f"     Rentables (trades>={min_trades}): {profitable_configs:,} ({profitable_pct}%)")
    print(f"     Rentables (trades>=80): {profitable_configs_80:,}")
    print(f"     PnL/trade >= $150: {pnl_per_trade_ge_150}")
    print(f"     Top PnL: ${top_pnl:,.0f} (${top_pnl_per_trade:,.0f}/trade)")
    print(f"     Top {top_n} archivees dans {top_dir}")

    return campaign_meta


def compare_campaigns(
    campaign_names: Optional[List[str]] = None,
    sort_by: str = "top_pnl",
) -> pd.DataFrame:
    """
    Compare plusieurs campagnes archivees cote a cote.

    Lit les campaign_meta.json. Si campaign_names est None,
    compare toutes les campagnes trouvees.

    Affiche un tableau formate et retourne un DataFrame.
    """
    records = []

    if not CAMPAIGNS_DIR.exists():
        print("[INFO] Aucune campagne archivee.")
        return pd.DataFrame()

    for meta_path in sorted(CAMPAIGNS_DIR.glob("*/campaign_meta.json")):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if campaign_names and meta.get("campaign_name") not in campaign_names:
            continue

        records.append({
            "campaign": meta.get("campaign_name", "unknown"),
            "timeframe": meta.get("timeframe", "?"),
            "exit_mode": meta.get("exit_mode", "?"),
            "slippage": meta.get("slippage", "?"),
            "total_configs": meta.get("total_configs", 0),
            "profitable_80": meta.get("profitable_configs_80", 0),
            "profitable_pct": meta.get("profitable_pct", 0.0),
            "ppt_ge_150": meta.get("pnl_per_trade_ge_150", 0),
            "median_ppt": meta.get("median_pnl_per_trade", 0.0),
            "top_pnl": meta.get("top_pnl", 0.0),
            "top_ppt": meta.get("top_pnl_per_trade", 0.0),
            "top_pf": meta.get("top_pf", 0.0),
        })

    if not records:
        print("[INFO] Aucune campagne trouvee.")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=False)
    df = df.reset_index(drop=True)

    # Affichage formate
    print("=" * 120)
    print("COMPARAISON DES CAMPAGNES")
    print("=" * 120)
    print(df.to_string(index=False))
    print()

    return df


def generate_campaign_report(
    campaign_names: List[str],
    output_path: Optional[str | Path] = None,
    title: str = "Phase B Batch 1 -- Resultats",
) -> str:
    """
    Genere un rapport Markdown complet pour un batch de campagnes.

    Returns:
        Chemin du fichier genere.
    """
    if output_path is None:
        output_path = REPORTS_DIR / "campaign_report.md"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Charger les metas
    metas = []
    for name in campaign_names:
        meta_path = CAMPAIGNS_DIR / name / "campaign_meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metas.append(json.load(f))

    if not metas:
        print("[ERREUR] Aucune campagne trouvee.")
        return str(output_path)

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    # -- Section Resume --
    lines.append("## Resume")
    lines.append("")
    lines.append("| Campagne | Configs | Rentables (t>=80) | % | $/t>=$150 | Median $/t | Top PnL | Top $/t | Top PF |")
    lines.append("|----------|---------|-------------------|---|-----------|------------|---------|---------|--------|")
    for m in metas:
        lines.append(
            f"| {m['campaign_name']} | {m['total_configs']:,} "
            f"| {m['profitable_configs_80']:,} | {m['profitable_pct']}% "
            f"| {m['pnl_per_trade_ge_150']} | ${m['median_pnl_per_trade']:,.0f} "
            f"| ${m['top_pnl']:,.0f} | ${m['top_pnl_per_trade']:,.0f} "
            f"| {m['top_pf']:.2f} |"
        )
    lines.append("")

    # -- Section GO / NO-GO --
    lines.append("## GO / NO-GO")
    lines.append("")
    for m in metas:
        name = m["campaign_name"]
        lines.append(f"### {name}")
        lines.append("")

        if "5min" in name:
            go = m["profitable_configs_80"] >= 100
            lines.append(f"- Rentables (trades>=80) : {m['profitable_configs_80']:,} "
                         f"-> **{'GO' if go else 'NO-GO'}** (seuil: >=100)")
        elif "dollar" in name:
            go = m["profitable_pct"] > 15
            lines.append(f"- Taux rentable : {m['profitable_pct']}% "
                         f"-> **{'GO' if go else 'NO-GO'}** (seuil: >15%)")
        else:
            lines.append(f"- Rentables (trades>=50) : {m['profitable_configs']:,} ({m['profitable_pct']}%)")
            lines.append(f"- Informatif (pas de seuil strict)")

        if m["median_pnl_per_trade"] < 150:
            lines.append(f"- Median PnL/trade : ${m['median_pnl_per_trade']:,.0f} -> **WARN** (<$150)")
        if m["top_pnl_per_trade"] < 100:
            lines.append(f"- Top PnL/trade : ${m['top_pnl_per_trade']:,.0f} -> **WARN** (fragile au slippage)")

        lines.append("")

    # -- Section Top 5 par timeframe --
    lines.append("## Top 5 par timeframe")
    lines.append("")

    # Grouper les campagnes par timeframe
    by_tf = {}
    for m in metas:
        tf = m["timeframe"]
        if tf not in by_tf:
            by_tf[tf] = []
        by_tf[tf].append(m)

    for tf, tf_metas in sorted(by_tf.items()):
        slip_vals = set(m["slippage"] for m in tf_metas)
        slip_str = "/".join(sorted(slip_vals))
        lines.append(f"### Top 5 -- {tf} (slippage {slip_str})")
        lines.append("")

        # Charger les full_results.csv de chaque campagne dans ce timeframe
        all_rows = []
        for m in tf_metas:
            csv_p = CAMPAIGNS_DIR / m["campaign_name"] / "full_results.csv"
            if csv_p.exists():
                df_c = pd.read_csv(csv_p, sep=";")
                df_c["campaign"] = m["campaign_name"]
                all_rows.append(df_c)

        if all_rows:
            df_merged = pd.concat(all_rows, ignore_index=True)
            df_merged = df_merged[df_merged["trades"] >= 80]
            top5 = df_merged.nlargest(5, "pnl_net")

            lines.append("| # | Config | Campagne | Trades | WR% | PnL | $/trade | PF | MaxDD | Sharpe |")
            lines.append("|---|--------|----------|--------|-----|-----|---------|-----|-------|--------|")
            for i, (_, r) in enumerate(top5.iterrows(), 1):
                lines.append(
                    f"| {i} | {r['label']} | {r['campaign']} "
                    f"| {int(r['trades'])} | {r['win_rate']:.1f}% "
                    f"| ${r['pnl_net']:,.0f} | ${r.get('pnl_avg', 0):,.0f} "
                    f"| {r['profit_factor']:.2f} | ${r['max_dd']:,.0f} "
                    f"| {r.get('sharpe', 0):+.2f} |"
                )
            lines.append("")

        if tf == "1min":
            lines.append("> ATTENTION: Ces configs sont a 1 tick de slippage. "
                         "L'audit B0 montre que 0/32,400 configs 1min dollar survivent a 2 ticks.")
            lines.append("> B4 top $111K avec PF 1.15 et $67/trade -- volume sans qualite, "
                         "a valider en Phase C4 (stress test slippage).")
            lines.append("")

    # -- Section Decouvertes --
    lines.append("## Decouvertes cles")
    lines.append("")
    for m in metas:
        name = m["campaign_name"]
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- Top config : {m['top_config_label']}")
        lines.append(f"- Top PnL : ${m['top_pnl']:,.0f} (${m['top_pnl_per_trade']:,.0f}/trade, PF {m['top_pf']:.2f})")

        dist = m.get("parameter_distribution", {})
        if dist:
            # Identifier les parametres dominants
            for param, counts in dist.items():
                if not counts:
                    continue
                total = sum(counts.values())
                best_val = max(counts, key=counts.get)
                best_count = counts[best_val]
                pct = best_count / max(total, 1) * 100
                if pct > 70:
                    lines.append(f"- **{param}={best_val} quasi-exclusif** ({best_count}/{total}, {pct:.0f}%)")
                elif pct > 40:
                    lines.append(f"- {param}={best_val} domine ({best_count}/{total}, {pct:.0f}%)")
        lines.append("")

    # -- Section Distribution --
    lines.append("## Distribution des parametres gagnants")
    lines.append("")
    for m in metas:
        name = m["campaign_name"]
        dist = m.get("parameter_distribution", {})
        if not dist:
            continue
        lines.append(f"### {name} (top 50 rentables, trades>=80)")
        lines.append("")
        for param, counts in dist.items():
            if not counts:
                continue
            parts = [f"{v}: {c}x" for v, c in sorted(counts.items(), key=lambda x: -x[1])]
            lines.append(f"- **{param}** : {', '.join(parts)}")
        lines.append("")

    # -- Section Recommandations --
    lines.append("## Recommandations Batch 2")
    lines.append("")
    for m in metas:
        name = m["campaign_name"]
        if "5min" in name and m["profitable_configs_80"] >= 100:
            lines.append(f"- **{name}** GO -> Lancer B2 (5min zscore 1 tick) + B3 (5min hybride)")
        elif "dollar" in name and m["profitable_pct"] > 15:
            lines.append(f"- **{name}** GO -> Lancer B6 (1min dollar zp long)")
            if m["top_pnl_per_trade"] < 100:
                lines.append(f"  - WARN : PnL/trade = ${m['top_pnl_per_trade']:,.0f}, fragile au slippage")
        else:
            lines.append(f"- **{name}** informatif -> Pas de suite directe, utile pour Phase C+")
    lines.append("")
    lines.append("### Points d'attention")
    lines.append("")
    lines.append("- B4 top PnL ($111K) est trompeur -- PF de 1.15 et $67/trade signifient que")
    lines.append("  cette config ne survivra probablement pas au stress test slippage en Phase C4")
    lines.append("- B1 reste le mode le plus prometteur en qualite (PF 2.55, $455/trade)")
    lines.append("- adf=26 doit etre inclus dans les grilles B2/B3 (decouverte majeure B1)")
    lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] Rapport genere : {output_path}")
    return str(output_path)


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
        choices=["archive-top", "generate-rankings", "dashboard", "list",
                 "archive-campaign", "compare", "report"],
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
    parser.add_argument(
        "--campaign",
        type=str,
        default=None,
        help="Nom de la campagne (pour archive-campaign)",
    )
    parser.add_argument(
        "--campaigns",
        type=str,
        default=None,
        help="Liste de campagnes separees par virgules (pour compare/report)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Chemin du fichier de sortie (pour report)",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Description de la campagne",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=50,
        help="Minimum de trades (default: 50)",
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

    elif args.action == "archive-campaign":
        if args.csv is None or args.campaign is None:
            parser.error("--csv et --campaign requis pour archive-campaign")
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"[ERREUR] Fichier introuvable : {csv_path}")
            return
        archive_campaign(
            csv_path=csv_path,
            campaign_name=args.campaign,
            top_n=args.n,
            sort_by=args.sort_by,
            min_trades=args.min_trades,
            description=args.description,
        )

    elif args.action == "compare":
        names = args.campaigns.split(",") if args.campaigns else None
        compare_campaigns(campaign_names=names, sort_by=args.sort_by)

    elif args.action == "report":
        if args.campaigns is None:
            parser.error("--campaigns requis pour report")
        names = args.campaigns.split(",")
        generate_campaign_report(campaign_names=names, output_path=args.output)


if __name__ == "__main__":
    main()
