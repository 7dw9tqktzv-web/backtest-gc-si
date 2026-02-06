"""
test_archive_manager.py - Tests pour le systeme d'archivage
=============================================================
10 tests couvrant les 5 fonctions publiques + 4 helpers de archive_manager.py.
Utilise tmp_path + monkeypatch pour isoler le systeme de fichiers.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src import archive_manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def archive_dirs(tmp_path, monkeypatch):
    """Redirige toutes les constantes de chemin vers tmp_path."""
    monkeypatch.setattr(archive_manager, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(archive_manager, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(archive_manager, "RANKINGS_DIR", tmp_path / "rankings")
    monkeypatch.setattr(archive_manager, "LATEST_DIR", tmp_path / "latest")
    return tmp_path


def _make_grid_csv(path: Path, n: int = 50, mode: str = "dollar") -> Path:
    """Cree un CSV de grid search synthetique avec n lignes."""
    rows = []
    for i in range(n):
        row = {
            "label": f"b1320_zp24_cp30_adf96_zE3.5_co50_TP{300 + i * 10}_SL800",
            "beta": 1320,
            "zp": 24,
            "cp": 30,
            "adf": 96,
            "zE": 3.5,
            "co": 50,
            "trades": 50 + i,
            "long": 25,
            "short": 25 + i,
            "win_rate": 50 + i * 0.5,
            "pnl_net": 1000 + i * 100,
            "pnl_avg": 20 + i,
            "profit_factor": 1.5 + i * 0.01,
            "max_dd": -(500 + i * 10),
            "sharpe": 0.2 + i * 0.01,
            "tp_zscore": 10,
            "tp_dollar": 20,
            "sl_zscore": 5,
            "sl_dollar": 15,
        }
        if mode == "dollar":
            row["TP"] = 300 + i * 10
            row["SL"] = 800
        elif mode == "zscore":
            row["zTP"] = 2.0 + i * 0.1
            row["zSL"] = 4.0 + i * 0.1
            row["mode"] = "no_tp" if i % 2 == 0 else "with_tp"
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(path, sep=";", index=False)
    return path


def _create_archive_entry(
    archive_dir: Path,
    timeframe: str,
    exit_mode: str,
    config_name: str,
    result_type: str,
    slippage: str,
    pnl_net: float,
    trades: int = 100,
) -> Path:
    """Helper pour creer manuellement une entree d'archive avec metrics JSON."""
    result_dir = archive_dir / timeframe / exit_mode / config_name / result_type
    result_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "trades": trades,
        "long": trades // 2,
        "short": trades // 2,
        "win_rate": 55.0,
        "pnl_net": pnl_net,
        "pnl_avg": pnl_net / max(trades, 1),
        "profit_factor": 1.5,
        "max_dd": -500.0,
        "sharpe": 0.3,
        "calmar": pnl_net / 500.0,
        "archived_at": "2026-02-06T10:00:00",
    }

    metrics_path = result_dir / f"{slippage}_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Config YAML au niveau config_name
    config_dir = archive_dir / timeframe / exit_mode / config_name
    config_yaml = config_dir / "config.yaml"
    if not config_yaml.exists():
        with open(config_yaml, "w", encoding="utf-8") as f:
            yaml.dump({"indicators": {"beta_lookback": 1320}}, f)

    return result_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArchiveConfig:
    """Tests pour archive_config()."""

    def test_creates_structure(self, archive_dirs, tmp_path):
        """Verifie la creation de l'arbre de repertoires."""
        result = archive_manager.archive_config(
            config_name="test_config",
            timeframe="1min",
            exit_mode="dollar",
            result_type="grid_search",
            slippage="1tick",
            files={},
            metrics={"pnl_net": 1000, "trades": 50},
            config_snapshot={"indicators": {"beta_lookback": 1320}},
        )

        # Verifier l'arbre
        expected = tmp_path / "archive" / "1min" / "dollar" / "test_config" / "grid_search"
        assert result == expected
        assert result.exists()
        assert result.is_dir()

    def test_saves_all_files(self, archive_dirs, tmp_path):
        """Verifie la sauvegarde de config.yaml, metrics JSON et fichiers copies."""
        # Creer un fichier source a copier
        source_file = tmp_path / "source_trades.csv"
        source_file.write_text("trade_no;pnl\n1;100\n2;200\n", encoding="utf-8")

        result = archive_manager.archive_config(
            config_name="full_config",
            timeframe="5min",
            exit_mode="zscore",
            result_type="top_pnl",
            slippage="2tick",
            files={"trades.csv": str(source_file)},
            metrics={"pnl_net": 5000, "trades": 80, "win_rate": 60.0},
            config_snapshot={"indicators": {"beta_lookback": 2640}},
        )

        # Verifier metrics JSON
        metrics_json = result / "2tick_metrics.json"
        assert metrics_json.exists()

        # Verifier trades CSV copie avec prefixe slippage
        trades_csv = result / "2tick_trades.csv"
        assert trades_csv.exists()
        content = trades_csv.read_text(encoding="utf-8")
        assert "trade_no;pnl" in content

        # Verifier config.yaml au niveau config_name
        config_yaml = result.parent / "config.yaml"
        assert config_yaml.exists()
        with open(config_yaml, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["indicators"]["beta_lookback"] == 2640

    def test_metrics_json_parsable(self, archive_dirs, tmp_path):
        """Verifie que le JSON de metriques est valide et contient les cles requises."""
        archive_manager.archive_config(
            config_name="json_test",
            timeframe="1min",
            exit_mode="dollar",
            result_type="grid_search",
            slippage="1tick",
            files={},
            metrics={"pnl_net": 2000, "trades": 60, "win_rate": 55.0, "sharpe": 0.4},
            config_snapshot={},
            run_name="test_run_2026",
        )

        metrics_path = (
            tmp_path / "archive" / "1min" / "dollar" / "json_test"
            / "grid_search" / "1tick_metrics.json"
        )
        assert metrics_path.exists()

        with open(metrics_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Cles obligatoires
        assert "pnl_net" in data
        assert "trades" in data
        assert "archived_at" in data
        assert "run_name" in data
        assert data["run_name"] == "test_run_2026"
        assert data["pnl_net"] == 2000

    def test_config_yaml_not_overwritten(self, archive_dirs, tmp_path):
        """Verifie que config.yaml n'est pas ecrase si deja present."""
        # Premier appel -> cree config.yaml
        archive_manager.archive_config(
            config_name="dup_config",
            timeframe="1min",
            exit_mode="dollar",
            result_type="grid_search",
            slippage="1tick",
            files={},
            metrics={"pnl_net": 1000},
            config_snapshot={"indicators": {"beta_lookback": 1320}},
        )

        # Deuxieme appel avec config differente -> ne doit PAS ecraser
        archive_manager.archive_config(
            config_name="dup_config",
            timeframe="1min",
            exit_mode="dollar",
            result_type="top_pnl",
            slippage="2tick",
            files={},
            metrics={"pnl_net": 2000},
            config_snapshot={"indicators": {"beta_lookback": 9999}},
        )

        config_yaml = tmp_path / "archive" / "1min" / "dollar" / "dup_config" / "config.yaml"
        with open(config_yaml, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["indicators"]["beta_lookback"] == 1320  # Pas 9999


class TestArchiveTopNFromGrid:
    """Tests pour archive_top_n_from_grid()."""

    def test_dollar_mode(self, archive_dirs, tmp_path):
        """Archive le top 5 d'un CSV dollar, verifie 5 dossiers + metrics."""
        csv_path = tmp_path / "grid_dollar.csv"
        _make_grid_csv(csv_path, n=50, mode="dollar")

        paths = archive_manager.archive_top_n_from_grid(
            csv_path=csv_path,
            n=5,
            sort_by="pnl_net",
            timeframe="1min",
            exit_mode="dollar",
            slippage="1tick",
        )

        assert len(paths) == 5

        # Verifier que chaque dossier contient un metrics JSON
        for p in paths:
            json_files = list(p.glob("*_metrics.json"))
            assert len(json_files) == 1, f"Pas de metrics JSON dans {p}"

    def test_zscore_mode(self, archive_dirs, tmp_path):
        """Archive depuis un CSV zscore, verifie la detection + archivage."""
        csv_path = tmp_path / "grid_zscore.csv"
        _make_grid_csv(csv_path, n=30, mode="zscore")

        paths = archive_manager.archive_top_n_from_grid(
            csv_path=csv_path,
            n=3,
            sort_by="pnl_net",
            timeframe="5min",
            exit_mode="zscore",
            slippage="2tick",
        )

        assert len(paths) == 3

        # Verifier que la config contient les champs zscore
        for p in paths:
            config_yaml = p.parent / "config.yaml"
            assert config_yaml.exists()
            with open(config_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            assert "exit" in cfg
            assert "zscore_tp" in cfg["exit"]

    def test_moves_raw_csv(self, archive_dirs, tmp_path):
        """Verifie que le CSV original est deplace dans raw/grid_search/."""
        csv_path = tmp_path / "grid_to_move.csv"
        _make_grid_csv(csv_path, n=10, mode="dollar")

        archive_manager.archive_top_n_from_grid(
            csv_path=csv_path, n=5, timeframe="1min", slippage="1tick",
        )

        # Le fichier original ne doit plus exister
        assert not csv_path.exists()

        # Il doit etre dans raw/grid_search/
        raw_dir = tmp_path / "raw" / "grid_search"
        assert raw_dir.exists()
        moved_files = list(raw_dir.glob("*grid_to_move.csv"))
        assert len(moved_files) == 1
        # Nom prefixe par la date
        assert moved_files[0].name.startswith("20")


class TestDetectExitMode:
    """Tests pour _detect_exit_mode()."""

    def test_dollar_detection(self):
        """DataFrame avec colonne TP -> dollar."""
        df = pd.DataFrame({"TP": [300], "SL": [800], "trades": [50]})
        assert archive_manager._detect_exit_mode(df) == "dollar"

    def test_zscore_detection(self):
        """DataFrame avec colonne zTP -> zscore."""
        df = pd.DataFrame({"zTP": [2.0], "zSL": [4.0], "mode": ["no_tp"]})
        assert archive_manager._detect_exit_mode(df) == "zscore"

    def test_zscore_priority_over_dollar(self):
        """Si zTP et TP presents, zscore a priorite (verifie en premier)."""
        df = pd.DataFrame({"zTP": [2.0], "TP": [300]})
        assert archive_manager._detect_exit_mode(df) == "zscore"

    def test_default_dollar(self):
        """Sans colonne TP ni zTP -> dollar par defaut."""
        df = pd.DataFrame({"trades": [50], "pnl_net": [1000]})
        assert archive_manager._detect_exit_mode(df) == "dollar"


class TestGenerateRankings:
    """Tests pour generate_rankings()."""

    def test_generates_ranking_csvs(self, archive_dirs, tmp_path):
        """Cree 2 timeframe x 2 exit_mode archives, verifie les CSV generes."""
        archive_dir = tmp_path / "archive"

        # Creer 4 categories
        for tf in ["1min", "5min"]:
            for em in ["dollar", "zscore"]:
                for i in range(3):
                    _create_archive_entry(
                        archive_dir, tf, em,
                        f"config_{tf}_{em}_{i}",
                        "grid_search", "1tick",
                        pnl_net=1000 + i * 500,
                    )

        archive_manager.generate_rankings(top_n=10)

        rankings_dir = tmp_path / "rankings"
        assert rankings_dir.exists()

        # Verifier les fichiers de classement par categorie
        csv_files = list(rankings_dir.glob("*.csv"))
        csv_names = {f.name for f in csv_files}
        assert "1min_dollar_top10.csv" in csv_names
        assert "1min_zscore_top10.csv" in csv_names
        assert "5min_dollar_top10.csv" in csv_names
        assert "5min_zscore_top10.csv" in csv_names
        assert "global_top50.csv" in csv_names

        # Verifier le contenu du global_top50
        global_df = pd.read_csv(rankings_dir / "global_top50.csv", sep=";")
        assert len(global_df) == 12  # 4 categories x 3 configs
        # Trie par pnl_net decroissant
        assert global_df.iloc[0]["pnl_net"] >= global_df.iloc[-1]["pnl_net"]


class TestGenerateDashboard:
    """Tests pour generate_dashboard()."""

    def test_creates_dashboard_md(self, archive_dirs, tmp_path):
        """Verifie la creation de DASHBOARD.md avec les sections attendues."""
        archive_dir = tmp_path / "archive"

        # Creer quelques archives
        for i in range(3):
            _create_archive_entry(
                archive_dir, "1min", "dollar",
                f"config_{i}", "grid_search", "1tick",
                pnl_net=1000 + i * 1000,
            )

        # D'abord generer les rankings (qui appellent le dashboard)
        archive_manager.generate_rankings(top_n=5)

        dashboard_path = tmp_path / "rankings" / "DASHBOARD.md"
        assert dashboard_path.exists()

        content = dashboard_path.read_text(encoding="utf-8")
        assert "# Archive Dashboard" in content
        assert "Last updated:" in content
        assert "Summary" in content
        assert "1min" in content
        assert "dollar" in content

    def test_empty_dashboard(self, archive_dirs, tmp_path):
        """Dashboard sans donnees -> message informatif."""
        content = archive_manager.generate_dashboard()

        assert "# Archive Dashboard" in content
        assert "No ranking files found." in content


class TestListConfigs:
    """Tests pour list_configs()."""

    def test_filters_by_timeframe(self, archive_dirs, tmp_path):
        """Cree des archives 1min et 5min, verifie le filtre par timeframe."""
        archive_dir = tmp_path / "archive"

        # 3 configs en 1min
        for i in range(3):
            _create_archive_entry(
                archive_dir, "1min", "dollar",
                f"config_1min_{i}", "grid_search", "1tick",
                pnl_net=1000 + i * 100,
            )

        # 2 configs en 5min
        for i in range(2):
            _create_archive_entry(
                archive_dir, "5min", "dollar",
                f"config_5min_{i}", "grid_search", "1tick",
                pnl_net=2000 + i * 100,
            )

        # Sans filtre -> toutes les configs
        df_all = archive_manager.list_configs()
        assert len(df_all) == 5

        # Filtre 1min
        df_1min = archive_manager.list_configs(timeframe="1min")
        assert len(df_1min) == 3
        assert all(df_1min["timeframe"] == "1min")

        # Filtre 5min
        df_5min = archive_manager.list_configs(timeframe="5min")
        assert len(df_5min) == 2
        assert all(df_5min["timeframe"] == "5min")

    def test_filters_by_exit_mode(self, archive_dirs, tmp_path):
        """Verifie le filtre par exit_mode."""
        archive_dir = tmp_path / "archive"

        _create_archive_entry(
            archive_dir, "1min", "dollar",
            "cfg_dollar", "grid_search", "1tick", pnl_net=1000,
        )
        _create_archive_entry(
            archive_dir, "1min", "zscore",
            "cfg_zscore", "grid_search", "1tick", pnl_net=2000,
        )

        df_dollar = archive_manager.list_configs(exit_mode="dollar")
        assert len(df_dollar) == 1
        assert df_dollar.iloc[0]["exit_mode"] == "dollar"

        df_zscore = archive_manager.list_configs(exit_mode="zscore")
        assert len(df_zscore) == 1
        assert df_zscore.iloc[0]["exit_mode"] == "zscore"

    def test_sorted_by_pnl_descending(self, archive_dirs, tmp_path):
        """Verifie que le resultat est trie par pnl_net decroissant."""
        archive_dir = tmp_path / "archive"

        for pnl in [500, 3000, 1500]:
            _create_archive_entry(
                archive_dir, "1min", "dollar",
                f"config_pnl_{pnl}", "grid_search", "1tick",
                pnl_net=pnl,
            )

        df = archive_manager.list_configs()
        pnl_values = df["pnl_net"].tolist()
        assert pnl_values == sorted(pnl_values, reverse=True)

    def test_empty_archive(self, archive_dirs):
        """Aucune archive -> DataFrame vide."""
        df = archive_manager.list_configs()
        assert df.empty
