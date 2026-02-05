"""
Generic Walk-Forward Runner - driven by YAML config.

Usage:
    python scripts/run_walk_forward.py --config configs/experiments/wf_3y.yaml
"""
import sys
import argparse
from pathlib import Path

import yaml

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from walk_forward_runner import WalkForwardRunner


def run_from_yaml(config_path: str):
    """Charge un YAML et lance le walk-forward correspondant."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert cfg["type"] == "walk_forward", (
        f"Type attendu 'walk_forward', trouve '{cfg['type']}'"
    )

    # Construire configs_to_test en mergeant defaults + overrides + fixed
    # Priorite : defaults < config overrides < fixed_overrides
    defaults = cfg.get("defaults", {})
    fixed = cfg.get("fixed_overrides", {})
    configs_to_test = []
    for c in cfg["configs"]:
        overrides = {**defaults, **c["overrides"], **fixed}
        configs_to_test.append({
            "label": c["label"],
            "overrides": overrides,
        })

    wf = cfg.get("walk_forward", {})
    exec_cfg = cfg.get("execution", {})

    runner = WalkForwardRunner(
        configs_to_test=configs_to_test,
        train_days=wf.get("train_days", 63),
        test_days=wf.get("test_days", 21),
        step_days=wf.get("step_days", 21),
        warmup_bars=wf.get("warmup_bars", 4500),
        timeframe=exec_cfg.get("timeframe", "5min"),
        title=cfg.get("title", "WALK-FORWARD TEST"),
        output_path=exec_cfg.get("output_path", "output/walk_forward_results.csv"),
        selection_criterion=wf.get("selection_criterion", "pnl_net"),
    )

    runner.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Walk-Forward generique -- YAML config"
    )
    parser.add_argument(
        "--config", required=True,
        help="Chemin vers le fichier YAML de l'experience"
    )
    args = parser.parse_args()
    run_from_yaml(args.config)
