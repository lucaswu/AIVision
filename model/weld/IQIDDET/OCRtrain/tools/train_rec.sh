#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
DATASET_ROOT="${DATASET_ROOT:-$ROOT_DIR/local/OCRdatasets/iqi_rec_v1}"
REC_DATASET_DIR="${REC_DATASET_DIR:-$DATASET_ROOT/rec_dataset}"
PADDLEOCR_ROOT="${PADDLEOCR_ROOT:-$ROOT_DIR/OCRtrain/third_party/PaddleOCR}"
PRETRAINED_MODEL="${PRETRAINED_MODEL:-$ROOT_DIR/OCRtrain/en_PP-OCRv5_mobile_rec_pretrained.pdparams}"
SAVE_DIR="${SAVE_DIR:-$ROOT_DIR/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec}"
OUTPUT_CONFIG="${OUTPUT_CONFIG:-$ROOT_DIR/OCRtrain/generated/iqi_en_PP-OCRv5_mobile_rec.yml}"
EPOCH_NUM="${EPOCH_NUM:-200}"
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-64}"
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-64}"
LEARNING_RATE="${LEARNING_RATE:-0.0005}"
EVAL_BATCH_STEP="${EVAL_BATCH_STEP:-100}"

if [[ ! -f "$PADDLEOCR_ROOT/tools/train.py" ]]; then
  echo "Missing PaddleOCR source checkout: $PADDLEOCR_ROOT/tools/train.py"
  echo "Put a PaddleOCR 3.x checkout under OCRtrain/third_party/PaddleOCR first."
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys

import paddle

if not paddle.device.is_compiled_with_cuda():
    sys.exit("Installed Paddle is not a GPU build. OCRtrain only supports GPU training.")

gpu_count = paddle.device.cuda.device_count()
if gpu_count < 1:
    sys.exit("No CUDA device is visible to Paddle. OCRtrain only supports GPU training.")

print(f"Paddle GPU check passed: {gpu_count} visible device(s).")
PY

"$PYTHON_BIN" "$ROOT_DIR/OCRtrain/scripts/prepare_train_config.py" \
  --dataset-root "$DATASET_ROOT" \
  --rec-dataset-dir "$REC_DATASET_DIR" \
  --paddleocr-root "$PADDLEOCR_ROOT" \
  --pretrained-model "$PRETRAINED_MODEL" \
  --save-dir "$SAVE_DIR" \
  --output-config "$OUTPUT_CONFIG" \
  --epoch-num "$EPOCH_NUM" \
  --train-batch-size "$TRAIN_BATCH_SIZE" \
  --eval-batch-size "$EVAL_BATCH_SIZE" \
  --learning-rate "$LEARNING_RATE" \
  --eval-batch-step "$EVAL_BATCH_STEP"

cd "$PADDLEOCR_ROOT"
"$PYTHON_BIN" tools/train.py -c "$OUTPUT_CONFIG" \
  -o Train.loader.num_workers=0 Eval.loader.num_workers=0 Global.print_mem_info=false \
  "$@"
