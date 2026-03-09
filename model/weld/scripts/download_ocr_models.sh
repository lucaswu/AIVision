#!/bin/bash
# 预下载 PaddleOCR 模型到本地 weight/paddleocr_cache/ 目录
# 该目录会在 Docker 构建时被 COPY 到镜像的 /root/.paddleocr/
# 从而实现离线环境下无需联网即可使用 PaddleOCR 模型
#
# 用法：在有网络的机器上运行此脚本，再将代码（含模型）传到离线机器构建镜像
#
# PaddleOCR 运行时会将模型缓存到：
#   ~/.paddleocr/whl/det/{lang}/{model_name}/
#   ~/.paddleocr/whl/rec/{lang}/{model_name}/
#   ~/.paddleocr/whl/cls/{model_name}/
# 本脚本完全复现上述目录结构。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEIGHT_DIR="$SCRIPT_DIR/../weight"
CACHE_DIR="$WEIGHT_DIR/paddleocr_cache/whl"

echo "PaddleOCR 模型缓存目录: $CACHE_DIR"

# ── 辅助函数 ────────────────────────────────────────────────────────────────

download_model() {
    local MODEL_NAME="$1"
    local URL="$2"
    local TARGET_DIR="$3"

    if [ -f "$TARGET_DIR/inference.pdmodel" ] && [ -f "$TARGET_DIR/inference.pdiparams" ]; then
        echo "✓ 已存在，跳过: $MODEL_NAME"
        return 0
    fi

    mkdir -p "$TARGET_DIR"
    local TMP_TAR
    TMP_TAR="$(mktemp /tmp/paddleocr_XXXXXX.tar)"

    echo "→ 下载: $MODEL_NAME"
    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$TMP_TAR" "$URL"
    else
        curl -L --progress-bar -o "$TMP_TAR" "$URL"
    fi

    echo "→ 解压: $MODEL_NAME → $TARGET_DIR"
    # PaddleOCR 的 tar 包含一个顶层目录（模型名），用 --strip-components=1 去掉
    tar -xf "$TMP_TAR" -C "$TARGET_DIR" --strip-components=1
    rm -f "$TMP_TAR"

    echo "✓ 完成: $MODEL_NAME"
}

copy_or_download() {
    local MODEL_NAME="$1"
    local URL="$2"
    local TARGET_DIR="$3"
    local SRC_DIR="$WEIGHT_DIR/$MODEL_NAME"

    if [ -f "$TARGET_DIR/inference.pdmodel" ] && [ -f "$TARGET_DIR/inference.pdiparams" ]; then
        echo "✓ 已存在，跳过: $MODEL_NAME"
        return
    fi

    # 优先使用 weight/ 目录下已有的模型（避免重复下载）
    if [ -f "$SRC_DIR/inference.pdmodel" ] && [ -f "$SRC_DIR/inference.pdiparams" ]; then
        echo "→ 从 weight/ 复制: $MODEL_NAME"
        mkdir -p "$TARGET_DIR"
        cp "$SRC_DIR"/inference.pd* "$TARGET_DIR/"
        echo "✓ 完成: $MODEL_NAME"
        return
    fi

    download_model "$MODEL_NAME" "$URL" "$TARGET_DIR"
}

# ── 中文检测模型 ─────────────────────────────────────────────────────────────
copy_or_download "ch_PP-OCRv4_det_infer" \
    "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar" \
    "$CACHE_DIR/det/ch/ch_PP-OCRv4_det_infer"

# ── 中文识别模型 ─────────────────────────────────────────────────────────────
copy_or_download "ch_PP-OCRv4_rec_infer" \
    "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar" \
    "$CACHE_DIR/rec/ch/ch_PP-OCRv4_rec_infer"

# ── 方向分类模型（中英文通用）───────────────────────────────────────────────
copy_or_download "ch_ppocr_mobile_v2.0_cls_infer" \
    "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar" \
    "$CACHE_DIR/cls/ch_ppocr_mobile_v2.0_cls_infer"

# ── 英文检测模型 ─────────────────────────────────────────────────────────────
download_model "en_PP-OCRv3_det_infer" \
    "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar" \
    "$CACHE_DIR/det/en/en_PP-OCRv3_det_infer"

# ── 英文识别模型 ─────────────────────────────────────────────────────────────
download_model "en_PP-OCRv4_rec_infer" \
    "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar" \
    "$CACHE_DIR/rec/en/en_PP-OCRv4_rec_infer"

# ── 完成 ─────────────────────────────────────────────────────────────────────
echo ""
echo "所有 PaddleOCR 模型已就绪:"
find "$CACHE_DIR" -name "inference.pdmodel" | sort | while read -r f; do
    dir=$(dirname "$f")
    size=$(du -sh "$dir" 2>/dev/null | cut -f1)
    echo "  [$size] ${dir#$CACHE_DIR/}"
done
echo ""
echo "下一步: 执行 bash rebuild.sh 构建镜像（可在离线机器上进行）"
