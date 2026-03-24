#!/usr/bin/env python3
"""Gauge detector training."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict

import yaml
from ultralytics import YOLO

try:
    from .custom_augment import patch_random_perspective_rotation, split_augment_config
except ImportError:
    from custom_augment import patch_random_perspective_rotation, split_augment_config


def load_yaml(path: Path | None) -> Dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def drop_none(values: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


def parse_metrics_csv(csv_path: Path) -> Dict[str, Any]:
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {}
    last = rows[-1]
    metrics: Dict[str, Any] = {}
    for key, value in last.items():
        if value is None:
            continue
        value = value.strip()
        if value == "":
            continue
        try:
            metrics[key] = float(value)
        except ValueError:
            metrics[key] = value
    return metrics


def build_train_args(cfg: Dict[str, Any], augment: Dict[str, Any]) -> Dict[str, Any]:
    required = ["model", "data", "run_name"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Missing required gauge params: {', '.join(missing)}")

    project = cfg.get("project", "logs/gauge")
    project_path = Path(project)
    if not project_path.is_absolute():
        repo_root = Path(__file__).resolve().parents[1]
        project_path = (repo_root / project_path).resolve()
    project = str(project_path)
    run_name = cfg["run_name"]

    base_args: Dict[str, Any] = {
        "data": cfg["data"],
        "imgsz": cfg.get("imgsz", 640),
        "epochs": cfg.get("epochs", 200),
        "batch": cfg.get("batch", 16),
        "device": cfg.get("device"),
        "workers": cfg.get("workers", 8),
        "project": project,
        "name": run_name,
        "resume": cfg.get("resume"),
        "optimizer": cfg.get("optimizer"),
        "lr0": cfg.get("lr0"),
        "lrf": cfg.get("lrf"),
        "momentum": cfg.get("momentum"),
        "weight_decay": cfg.get("weight_decay"),
        "patience": cfg.get("patience"),
        "seed": cfg.get("seed"),
        "amp": cfg.get("amp"),
        "cache": cfg.get("cache"),
        "val": cfg.get("val"),
        "save_period": cfg.get("save_period"),
        "exist_ok": cfg.get("exist_ok"),
        "deterministic": cfg.get("deterministic"),
        "cos_lr": cfg.get("cos_lr"),
        "close_mosaic": cfg.get("close_mosaic"),
    }

    extra_args = cfg.get("extra_args", {})
    if extra_args and not isinstance(extra_args, dict):
        raise ValueError("gauge.extra_args must be a mapping if provided.")

    merged = {}
    merged.update(drop_none(base_args))
    merged.update(drop_none(augment))
    if extra_args:
        merged.update(drop_none(extra_args))
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train gauge OBB detector with Ultralytics YOLO.")
    parser.add_argument("--params", default="params.yaml", help="Path to params.yaml.")
    parser.add_argument("--augment", default=None, help="Path to augmentation YAML.")
    parser.add_argument(
        "--metrics-path",
        default=None,
        help="Output JSON metrics file (overrides gauge.metrics_path).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params_path = Path(args.params)
    params = load_yaml(params_path)
    cfg = params.get("gauge_train")
    if cfg is None:
        cfg = params.get("gauge", {})
    if not isinstance(cfg, dict):
        raise ValueError("gauge_train section in params.yaml must be a mapping.")

    augment_path = Path(args.augment) if args.augment else None
    if augment_path is None and cfg.get("augment"):
        augment_path = Path(cfg["augment"])
    augment_cfg = load_yaml(augment_path)
    augment, custom_augment = split_augment_config(augment_cfg)

    metrics_path = args.metrics_path or cfg.get("metrics_path") or "metrics/gauge_metrics.json"
    metrics_path = Path(metrics_path)

    train_args = build_train_args(cfg, augment)
    model = YOLO(cfg["model"])
    with patch_random_perspective_rotation(custom_augment):
        model.train(**train_args)

    run_dir = Path(train_args["project"]) / train_args["name"]
    results_csv = run_dir / "results.csv"
    metrics_payload = parse_metrics_csv(results_csv)
    metrics_payload.update(
        {
            "run_name": cfg["run_name"],
            "model": cfg["model"],
            "data": cfg["data"],
        }
    )

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
