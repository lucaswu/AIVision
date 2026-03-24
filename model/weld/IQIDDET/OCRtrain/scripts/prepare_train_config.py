#!/usr/bin/env python3
"""Generate a concrete PaddleOCR training config from the PaddleOCR submodule base config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from common import REPO_ROOT, get_default_dataset_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a GPU training config for PaddleOCR recognition.")
    parser.add_argument(
        "--dataset-root",
        default=str(get_default_dataset_root()),
        help="Dataset root under local/OCRdatasets.",
    )
    parser.add_argument(
        "--rec-dataset-dir",
        help="Directory containing train.txt/val.txt/dict.txt. Defaults to <dataset-root>/rec_dataset.",
    )
    parser.add_argument(
        "--paddleocr-root",
        default=str(REPO_ROOT / "OCRtrain" / "third_party" / "PaddleOCR"),
        help="PaddleOCR source checkout root.",
    )
    parser.add_argument("--base-config", help="Optional explicit base config path.")
    parser.add_argument(
        "--pretrained-model",
        default=str(REPO_ROOT / "OCRtrain" / "en_PP-OCRv5_mobile_rec_pretrained.pdparams"),
        help="Pretrained .pdparams file.",
    )
    parser.add_argument(
        "--save-dir",
        default=str(REPO_ROOT / "OCRtrain" / "runs" / "iqi_en_PP-OCRv5_mobile_rec"),
        help="Training output directory.",
    )
    parser.add_argument(
        "--output-config",
        default=str(REPO_ROOT / "OCRtrain" / "generated" / "iqi_en_PP-OCRv5_mobile_rec.yml"),
        help="Generated config path.",
    )
    parser.add_argument("--epoch-num", type=int, default=200, help="Training epochs.")
    parser.add_argument("--train-batch-size", type=int, default=64, help="Train batch size per card.")
    parser.add_argument("--eval-batch-size", type=int, default=64, help="Eval batch size per card.")
    parser.add_argument("--learning-rate", type=float, default=0.0005, help="Base learning rate.")
    parser.add_argument("--eval-batch-step", type=int, default=100, help="Run evaluation every N training steps.")
    parser.add_argument(
        "--use-space-char",
        action="store_true",
        help="Enable space as a recognized character. Disabled by default for IQI gauge training.",
    )
    return parser.parse_args()


def deep_set(root: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = root
    for key in parts[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[parts[-1]] = value


def find_base_config(paddleocr_root: Path) -> Path:
    patterns = [
        "**/en_PP-OCRv5_mobile_rec.yml",
        "**/en_PP-OCRv5_mobile_rec.yaml",
        "**/*en*PP-OCRv5*mobile*rec*.yml",
        "**/*en*PP-OCRv5*mobile*rec*.yaml",
    ]
    matches: List[Path] = []
    for pattern in patterns:
        matches.extend(sorted(paddleocr_root.glob(pattern)))
    if not matches:
        raise FileNotFoundError(
            f"Could not find en_PP-OCRv5_mobile_rec config under {paddleocr_root}. "
            "Initialize the PaddleOCR submodule first or pass --base-config."
        )
    return matches[0]


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root).resolve()
    rec_dataset_dir = Path(args.rec_dataset_dir).resolve() if args.rec_dataset_dir else dataset_root / "rec_dataset"
    paddleocr_root = Path(args.paddleocr_root).resolve()
    base_config = Path(args.base_config).resolve() if args.base_config else find_base_config(paddleocr_root)
    pretrained_model = Path(args.pretrained_model).resolve()
    save_dir = Path(args.save_dir).resolve()
    output_config = Path(args.output_config).resolve()

    if not base_config.exists():
        raise FileNotFoundError(base_config)
    if not pretrained_model.exists():
        raise FileNotFoundError(pretrained_model)
    for required in ["train.txt", "val.txt", "dict.txt"]:
        path = rec_dataset_dir / required
        if not path.exists():
            raise FileNotFoundError(path)

    config = yaml.safe_load(base_config.read_text(encoding="utf-8"))
    updates = {
        "Global.pretrained_model": str(pretrained_model),
        "Global.checkpoints": "",
        "Global.character_dict_path": str(rec_dataset_dir / "dict.txt"),
        "Global.save_model_dir": str(save_dir),
        "Global.epoch_num": args.epoch_num,
        "Global.use_gpu": True,
        "Global.use_space_char": args.use_space_char,
        "Global.eval_batch_step": [0, args.eval_batch_step],
        "Train.dataset.data_dir": str(dataset_root),
        "Train.dataset.label_file_list": [str(rec_dataset_dir / "train.txt")],
        "Eval.dataset.data_dir": str(dataset_root),
        "Eval.dataset.label_file_list": [str(rec_dataset_dir / "val.txt")],
        "Train.sampler.first_bs": args.train_batch_size,
        "Train.loader.batch_size_per_card": args.train_batch_size,
        "Eval.loader.batch_size_per_card": args.eval_batch_size,
        "Optimizer.lr.learning_rate": args.learning_rate,
    }
    for key, value in updates.items():
        deep_set(config, key, value)

    output_config.parent.mkdir(parents=True, exist_ok=True)
    output_config.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")

    meta = {
        "paddleocr_root": str(paddleocr_root),
        "base_config": str(base_config),
        "generated_config": str(output_config),
        "dataset_root": str(dataset_root),
        "rec_dataset_dir": str(rec_dataset_dir),
        "pretrained_model": str(pretrained_model),
        "save_dir": str(save_dir),
        "device": "gpu",
        "use_space_char": args.use_space_char,
        "epoch_num": args.epoch_num,
        "train_batch_size": args.train_batch_size,
        "eval_batch_size": args.eval_batch_size,
        "learning_rate": args.learning_rate,
        "eval_batch_step": args.eval_batch_step,
    }
    (output_config.parent / "iqi_en_PP-OCRv5_mobile_rec.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
