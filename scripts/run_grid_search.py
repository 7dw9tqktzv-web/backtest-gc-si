"""
Generic Grid Search Runner - driven by YAML config.

Usage:
    python scripts/run_grid_search.py --config configs/experiments/grid_3y.yaml

Supports two exit modes:
    - "dollar"  : TP/SL en dollars (create_standard_*)
    - "zscore"  : TP/SL en Z-Score (create_zscore_*)
"""
import sys
import argparse
from pathlib import Path

import yaml

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from grid_search_runner import (
    GridSearchRunner,
    create_standard_entry_exit_generator,
    create_standard_label_builder,
    create_standard_result_builder,
    create_zscore_entry_exit_generator,
    create_zscore_label_builder,
    create_zscore_result_builder,
)


def run_from_yaml(config_path: str):
    """Charge un YAML et lance le grid search correspondant."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert cfg["type"] == "grid_search", (
        f"Type attendu 'grid_search', trouve '{cfg['type']}'"
    )

    exit_mode = cfg["exit_mode"]
    ee = cfg["entry_exit"]

    if exit_mode == "dollar":
        ee_gen = create_standard_entry_exit_generator(
            zscore_entry=ee["zscore_entry"],
            cointegration_min=ee["cointegration_min"],
            pnl_take_profit=ee["pnl_take_profit"],
            pnl_stop_loss=ee["pnl_stop_loss"],
        )
        label_builder = create_standard_label_builder()
        result_builder = create_standard_result_builder()

    elif exit_mode == "zscore":
        ee_gen = create_zscore_entry_exit_generator(
            zscore_entry=ee["zscore_entry"],
            cointegration_min=ee["cointegration_min"],
            zscore_tp=ee["zscore_tp"],
            zscore_sl=ee["zscore_sl"],
            dollar_modes=ee.get("dollar_modes", ["pure_zscore"]),
        )
        label_builder = create_zscore_label_builder()
        result_builder = create_zscore_result_builder()

    else:
        raise ValueError(f"exit_mode inconnu : '{exit_mode}' (dollar ou zscore)")

    exec_cfg = cfg.get("execution", {})

    runner = GridSearchRunner(
        indicator_params=cfg["indicators"],
        entry_exit_generator=ee_gen,
        label_builder=label_builder,
        result_builder=result_builder,
        fixed_overrides=cfg.get("fixed_overrides", {}),
        timeframe=exec_cfg.get("timeframe", "1min"),
        title=cfg.get("title", "GRID SEARCH"),
    )

    runner.run(
        num_workers=exec_cfg.get("num_workers", 24),
        output_path=exec_cfg.get("output_path", "output/grid_search_results.csv"),
        min_trades_for_sharpe=exec_cfg.get("min_trades_for_sharpe", 20),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Grid Search generique -- YAML config"
    )
    parser.add_argument(
        "--config", required=True,
        help="Chemin vers le fichier YAML de l'experience"
    )
    args = parser.parse_args()
    run_from_yaml(args.config)
