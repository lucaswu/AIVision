#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PADDLEOCR_ROOT="${PADDLEOCR_ROOT:-$ROOT_DIR/OCRtrain/third_party/PaddleOCR}"
CONFIG_PATH="${CONFIG_PATH:-$ROOT_DIR/OCRtrain/generated/iqi_en_PP-OCRv5_mobile_rec.yml}"
CHECKPOINT_PATH="${CHECKPOINT_PATH:-$ROOT_DIR/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/latest}"

if [[ ! -f "$PADDLEOCR_ROOT/tools/eval.py" ]]; then
  echo "Missing PaddleOCR source checkout: $PADDLEOCR_ROOT/tools/eval.py"
  exit 1
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing generated config: $CONFIG_PATH"
  exit 1
fi

cd "$PADDLEOCR_ROOT"
"$PYTHON_BIN" tools/eval.py -c "$CONFIG_PATH" \
  -o "Global.pretrained_model=$CHECKPOINT_PATH" "Global.checkpoints=$CHECKPOINT_PATH" "$@"
