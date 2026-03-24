`OCRtrain/third_party/PaddleOCR` 现在由主仓库以 **git submodule** 方式管理。

首次拉取主仓库后，请执行：

```bash
git submodule update --init --recursive
```

训练脚本依赖以下文件存在：

- `OCRtrain/third_party/PaddleOCR/tools/train.py`
- `OCRtrain/third_party/PaddleOCR/tools/eval.py`
- `OCRtrain/third_party/PaddleOCR/tools/export_model.py`

如果这个目录是空的，或者只有一个 gitlink，请先初始化 submodule，不要手工再拷一份其它 PaddleOCR 到这里。
