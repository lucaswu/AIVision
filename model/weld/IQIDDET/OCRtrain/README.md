# IQI OCR 识别训练工程

本目录用于微调 `en_PP-OCRv5_mobile_rec`，目标是让文字识别输入尽可能贴近当前业务推理链路。

当前采用的训练样本生成路径是：

`原图 -> (可选)方向矫正 -> Gauge ROI 检测 -> ROI 透视裁剪 -> 旋转/灰度增强 -> TextDetection 自动框 -> crop -> 人工转录 -> PaddleOCR rec 训练`

这里**不训练文本检测模型**，直接复用当前推理时的 ROI 检测和 PaddleOCR 文本检测结果，只训练文本识别模型。

## Git 仓库约定

`OCRtrain/` 现在会纳入主仓库版本控制，但只提交代码、脚本和文档。

以下内容默认继续忽略，不进入主仓库历史：

- `OCRtrain/generated/`
- `OCRtrain/runs/`
- `OCRtrain/en_PP-OCRv5_mobile_rec_pretrained.pdparams`
- `OCRtrain/ocr_rec_dataset_examples/`
- Windows 打包产物和缓存目录

`OCRtrain/third_party/PaddleOCR` 改为 **git submodule** 管理。

首次拉取仓库建议直接使用：

```bash
git clone --recursive <your-repo-url>
```

如果你已经 clone 过主仓库，再补一次：

```bash
git submodule update --init --recursive
```

## 目录约定

本目录下的关键文件：

- `en_PP-OCRv5_mobile_rec_pretrained.pdparams`
  识别模型预训练权重，本地自行准备，不纳入 git。
- `scripts/build_source_split.py`
  从 `IQIdata/ori/img` 构建 9:1 软链接数据切分。
- `scripts/export_text_crops.py`
  复用当前 ROI 流程导出 `roi/` 和 `det_crops/`。
- `scripts/transcribe_server.py`
  极简人工转录 Web 工具。
- `scripts/build_rec_dataset.py`
  将人工转录结果转换为 PaddleOCR 识别训练格式。
- `scripts/prepare_train_config.py`
  从 `third_party/PaddleOCR` 基础配置生成训练配置。
- `tools/train_rec.sh`
  启动训练。
- `tools/eval_rec.sh`
  评估训练结果。
- `tools/export_rec.sh`
  导出推理模型。

数据默认落在：

- `local/OCRdatasets/iqi_rec_v1/source/`
- `local/OCRdatasets/iqi_rec_v1/roi/`
- `local/OCRdatasets/iqi_rec_v1/det_crops/`
- `local/OCRdatasets/iqi_rec_v1/annotations/`
- `local/OCRdatasets/iqi_rec_v1/rec_dataset/`
- `local/OCRdatasets/iqi_rec_v1/manifests/`

## PaddleOCR 源码依赖

`pip install paddleocr` 只够推理，不包含官方训练入口 `tools/train.py`。

训练时依赖 `OCRtrain/third_party/PaddleOCR`，这个目录现在由主仓库以 **git submodule** 方式引用官方 PaddleOCR 仓库。

拉完主仓库后，先执行：

```bash
git submodule update --init --recursive
```

如果你是在 Windows 或新机器上第一次拉代码，这一步不要跳过。

最低要求是以下文件存在：

- `OCRtrain/third_party/PaddleOCR/tools/train.py`
- `OCRtrain/third_party/PaddleOCR/tools/eval.py`
- `OCRtrain/third_party/PaddleOCR/tools/export_model.py`

## 步骤 1：构建原图 train/val 切分

默认从 `IQIdata/ori/img` 读取原图，按 9:1 切分，并在 `local/OCRdatasets/iqi_rec_v1/source/` 下建立软链接。

```bash
python OCRtrain/scripts/build_source_split.py \
  --image-dir IQIdata/ori/img \
  --output-root local/OCRdatasets/iqi_rec_v1 \
  --val-ratio 0.1 \
  --seed 20260315
```

输出：

- `manifests/source_train.txt`
- `manifests/source_val.txt`
- `manifests/source_train.jsonl`
- `manifests/source_val.jsonl`
- `manifests/split_meta.json`

如果你后续想做“同家族样本不跨集合”的切分，可以额外传 `--group-regex`。

## 步骤 2：直接从原图导出 TextDetection crop

当前 `export_text_crops.py` 已改成**不依赖像质计 ROI 检测**，而是直接对原图做 PaddleOCR `TextDetection`，并把每个文本框裁成 crop。

适用场景：

- 你希望把所有铅字牌都纳入 OCR 训练
- 你有多份历史数据，目录结构不统一
- 你希望直接从多层目录里的原图批量抽取文本框

示例：

```bash
python OCRtrain/scripts/export_text_crops.py \
  --dataset-root local/OCRdatasets/iqi_rec_textdet_v1 \
  --image-root IQIdata/ori \
  --image-root datasets/images \
  --text-det-device gpu \
  --text-det-model-name PP-OCRv5_server_det \
  --enhance-mode windowing \
  --vis
```

`--image-root` 可以重复传，也可以在一个参数里写逗号分隔路径：

```bash
python OCRtrain/scripts/export_text_crops.py \
  --dataset-root local/OCRdatasets/iqi_rec_textdet_v1 \
  --image-root IQIdata/ori,datasets/images \
  --text-det-device gpu \
  --text-det-model-name PP-OCRv5_server_det
```

如果你不想全量导出，可以加随机抽样比例，例如只处理 30%：

```bash
python OCRtrain/scripts/export_text_crops.py \
  --dataset-root local/OCRdatasets/iqi_rec_textdet_v1 \
  --image-root IQIdata/ori \
  --image-root datasets/images \
  --sample-ratio 0.3 \
  --sample-seed 20260315 \
  --text-det-device gpu \
  --text-det-model-name PP-OCRv5_server_det \
  --enhance-mode windowing
```

输出：

- `det_crops/all/...`
- `vis/text_det/all/...`
- `manifests/source_images_all.jsonl`
- `manifests/crops_all.jsonl`
- `manifests/errors_text_det_all.jsonl`
- `manifests/export_text_crops_stats.json`

说明：

- `det_crops/all/` 是待标注的文本 crop。
- `source_images_all.jsonl` 记录每张原图的检测状态和导出数量。
- `crops_all.jsonl` 记录每个 crop 的来源原图、polygon、score 和保存路径。
- `--vis` 会额外保存全图文本框可视化。

注意：

- 当前环境里 PaddleOCR 的 CPU 文本检测容易触发 oneDNN/PIR 兼容性错误。
- 这个脚本默认建议 `--text-det-device gpu`。
- 如果 GPU 不可用，错误会原样写进 manifest，不会自动兜底。
- `--sample-ratio` 默认是 `1.0`，表示全量处理；小于 `1.0` 时会先对全部来源图随机抽样，再做文本检测。

## 步骤 3：人工转录 crop

这里提供了一个极简 Web 标注器，专门用于“看 crop，录入文字”。

启动：

```bash
python OCRtrain/scripts/transcribe_server.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --manifest local/OCRdatasets/iqi_rec_v1/manifests/crops_train.jsonl \
  --labels-tsv local/OCRdatasets/iqi_rec_v1/annotations/crops_train_labels.tsv
```

如果你手头已经是单张文本 crop，不想依赖检测 manifest，也可以直接用无框标注器。

现在这个工具支持：

- 直接录入文本标签
- 中文界面
- `左转 / 右转 / 水平镜像 / 重置预览`
- 点击保存类按钮时把当前预览矫正真正写回 crop 文件
- 自动把原始 crop 备份到 `image_dir/.label_backup/`
- `跳过 => ~` 快捷标注，按一次就把当前样本写成 `~`，不需要手工输入

示例：

```bash
python OCRtrain/tools/label_rec_no_box.py \
  --image-dir local/OCRdatasets/iqi_rec_textdet_v1/det_crops/all \
  --path-root local/OCRdatasets/iqi_rec_textdet_v1 \
  --output-file local/OCRdatasets/iqi_rec_textdet_v1/all.txt
```

默认地址：

- `http://127.0.0.1:8766`

这个工具会同时写两个文件：

- `train.txt` 或你指定的 `rec_gt.txt`
- 同目录下的 `train_labels.tsv`
- 同目录下的 `train_session.json`

其中 `all.txt` 格式直接兼容 PaddleOCR 识别训练：

```text
det_crops/all/sample.png<TAB>LABEL_TEXT
```

`TSV` 会额外保留 `ok / skip / pending` 状态，便于断点续标。

如果某个 crop 不是像质计铅字牌，可以直接点 `Skip => ~`。
这个操作会把样本按 `~` 写入训练标签，不需要标注员手工输入 `~`。
这里约定 `~` 是“非目标字符区域 / 应拒识”的专用标签。

交互说明：

- `保存` 直接保存当前文字。
- `跳过 => ~` 直接把当前样本标成 `~`，快捷键是 `Ctrl+Q`。
- `保存并下一张` 按回车或 `Ctrl+E` 会触发它。
- `左转 / 右转 / 水平镜像 / 重置预览` 用于矫正当前 crop 方向。
- 只有点击保存类按钮后，矫正操作才会真正写回文件。
- 右侧会显示完整待标注队列，分别表示 `已标注 / 拒识 / 旧跳过 / 待处理`。
- 当 `--image-dir / --output-file / --labels-tsv / --path-root` 解析后的路径不变时，会自动从 `*_session.json` 恢复到上次看到的样本。

默认地址：

- `http://127.0.0.1:8766`

如果你要把标注器打包给 Windows 标注人员使用，直接看：

- `OCRtrain/tools/label_rec_no_box_windows.md`

当前 Windows 版支持：

- 双击 `label_rec_no_box.exe`
- 弹窗选择待标注图片目录
- 自动在 `exe` 当前目录生成 `txt / labels.tsv / session.json`

转录器特点：

- 一次只看一个 crop
- 输入文字后回车默认 `Save + Next`
- 支持 `ok / skip / unclear`
- 输出 TSV

TSV 格式：

```text
sample_id    text    status    crop_rel_path
```

如果你使用上面的 `label_rec_no_box.py` 直接输出到 `local/OCRdatasets/iqi_rec_v1/`，后续训练时记得把：

- `train.txt`
- `val.txt`
- `dict.txt`

放在同一个目录下，并把 `REC_DATASET_DIR` 指向这个目录。

验证集同理，再启动一次：

```bash
python OCRtrain/scripts/transcribe_server.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --manifest local/OCRdatasets/iqi_rec_v1/manifests/crops_val.jsonl \
  --labels-tsv local/OCRdatasets/iqi_rec_v1/annotations/crops_val_labels.tsv
```

## 步骤 4：生成 PaddleOCR 识别训练集

人工转录完成后，生成 `train.txt / val.txt / dict.txt`：

```bash
python OCRtrain/scripts/build_rec_dataset.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --output-dir local/OCRdatasets/iqi_rec_v1/rec_dataset \
  --dict-mode preset_plus_labels \
  --drop-empty
```

输出：

- `rec_dataset/train.txt`
- `rec_dataset/val.txt`
- `rec_dataset/dict.txt`
- `rec_dataset/build_meta.json`

`train.txt` / `val.txt` 格式与官方示例一致：

```text
det_crops/train/xxx/sample.png<TAB>LABEL_TEXT
```

这里的路径是**相对于 dataset root** 的。

更短路径：

如果你已经通过 `label_rec_no_box.py` 直接生成了：

- `local/OCRdatasets/iqi_rec_v1/train.txt`
- `local/OCRdatasets/iqi_rec_v1/val.txt`

那么可以跳过 `build_rec_dataset.py`，只需要在同目录补一个 `dict.txt` 即可。

`dict.txt` 要求：

- 每行一个字符
- 必须覆盖训练标签里会出现的全部字符
- 大小写敏感，`i` 和 `I` 是两个不同字符
- 如果你采用“拒识字符”方案，`~` 也必须放进 `dict.txt`

当前工程默认会在训练配置里关闭空格字符，也就是 `Global.use_space_char=false`，避免模型额外学习输出空格。

例如标签字符集是 `0-9 + J B N i F E`，并约定 `~` 表示“非铅字牌 / 应拒识”，则 `dict.txt` 可以写成：

```text
0
1
2
3
4
5
6
7
8
9
J
B
N
i
F
E
~
```

## 步骤 5：准备训练配置

训练配置不是手写死的，而是从 `third_party/PaddleOCR` 里自动找到 `en_PP-OCRv5_mobile_rec` 的基础配置，然后注入：

- `Global.pretrained_model`
- `Global.character_dict_path`
- `Train/Eval.dataset.*`
- `Train/Eval.loader.batch_size_per_card`
- `Optimizer.lr.learning_rate`
- `Global.epoch_num`
- `Global.save_model_dir`

当前工程只保留 **GPU 训练** 路径，不再维护 CPU 训练分支。

单独执行：

```bash
python OCRtrain/scripts/prepare_train_config.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --rec-dataset-dir local/OCRdatasets/iqi_rec_v1/rec_dataset \
  --paddleocr-root OCRtrain/third_party/PaddleOCR \
  --pretrained-model OCRtrain/en_PP-OCRv5_mobile_rec_pretrained.pdparams \
  --save-dir OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec \
  --output-config OCRtrain/generated/iqi_en_PP-OCRv5_mobile_rec.yml
```

## 步骤 6：训练

直接使用 wrapper：

```bash
bash OCRtrain/tools/train_rec.sh
```

如果你采用的是“直接在 dataset root 下维护 `train.txt / val.txt / dict.txt`”的方式，训练命令推荐写成：

```bash
PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
REC_DATASET_DIR=/home/cht/code/IQIdet/local/OCRdatasets/iqi_rec_v1 \
TRAIN_BATCH_SIZE=64 \
EVAL_BATCH_SIZE=64 \
EPOCH_NUM=200 \
bash OCRtrain/tools/train_rec.sh
```

可通过环境变量覆盖默认值，例如：

```bash
PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
TRAIN_BATCH_SIZE=32 \
EVAL_BATCH_SIZE=32 \
EPOCH_NUM=100 \
bash OCRtrain/tools/train_rec.sh
```

`train_rec.sh` 会自动：

- 检查 Paddle 是否能看到 GPU
- 强制生成 GPU 训练配置
- 默认追加 `Train.loader.num_workers=0`
- 默认追加 `Eval.loader.num_workers=0`
- 默认追加 `Global.print_mem_info=false`

默认依赖：

- `DATASET_ROOT=local/OCRdatasets/iqi_rec_v1`
- `REC_DATASET_DIR=$DATASET_ROOT/rec_dataset`
- `PADDLEOCR_ROOT=OCRtrain/third_party/PaddleOCR`
- `PRETRAINED_MODEL=OCRtrain/en_PP-OCRv5_mobile_rec_pretrained.pdparams`

## 步骤 7：评估与导出

评估：

```bash
bash OCRtrain/tools/eval_rec.sh
```

导出：

```bash
bash OCRtrain/tools/export_rec.sh
```

如果你当前使用默认输出目录，推荐直接执行：

```bash
PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
CHECKPOINT_PATH=/home/cht/code/IQIdet/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/latest \
EXPORT_DIR=/home/cht/code/IQIdet/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/inference \
bash OCRtrain/tools/export_rec.sh
```

可以通过环境变量指定 checkpoint：

```bash
CHECKPOINT_PATH=/abs/path/to/best_accuracy \
bash OCRtrain/tools/eval_rec.sh
```

```bash
CHECKPOINT_PATH=/abs/path/to/best_accuracy \
EXPORT_DIR=/abs/path/to/export_dir \
bash OCRtrain/tools/export_rec.sh
```

## 当前项目的正式训练最短路径

如果你要按当前工程实际情况直接开跑，可以按下面顺序执行。

1. 导出训练样本 crop：

```bash
python OCRtrain/scripts/export_text_crops.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --subset all \
  --gauge-weights logs/gauge/gauge2/weights/best.pt \
  --sample-ratio 0.3 \
  --sample-seed 20260315 \
  --text-det-device gpu \
  --text-det-model-name PP-OCRv5_server_det \
  --enhance-mode windowing
```

如果正式推理要开方向矫正，这一步也改成：

```bash
python OCRtrain/scripts/export_text_crops.py \
  --dataset-root local/OCRdatasets/iqi_rec_v1 \
  --subset all \
  --gauge-weights logs/gauge/gauge2/weights/best.pt \
  --enable-correction \
  --correction-model local/weld_orientation_model.pth \
  --sample-ratio 0.3 \
  --sample-seed 20260315 \
  --text-det-device gpu \
  --text-det-model-name PP-OCRv5_server_det \
  --enhance-mode windowing
```

2. 标注训练集：

```bash
python OCRtrain/tools/label_rec_no_box.py \
  --image-dir local/OCRdatasets/iqi_rec_v1/det_crops/train \
  --path-root local/OCRdatasets/iqi_rec_v1 \
  --output-file local/OCRdatasets/iqi_rec_v1/train.txt
```

3. 标注验证集：

```bash
python OCRtrain/tools/label_rec_no_box.py \
  --image-dir local/OCRdatasets/iqi_rec_v1/det_crops/val \
  --path-root local/OCRdatasets/iqi_rec_v1 \
  --output-file local/OCRdatasets/iqi_rec_v1/val.txt
```

4. 准备 `dict.txt`，放到 `local/OCRdatasets/iqi_rec_v1/dict.txt`。

如果某个 crop 不是铅字牌，但你希望模型学会拒识，请把它标成 `~`，不要点 `skip`。

5. 开始训练：

```bash
PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
REC_DATASET_DIR=/home/cht/code/IQIdet/local/OCRdatasets/iqi_rec_v1 \
TRAIN_BATCH_SIZE=64 \
EVAL_BATCH_SIZE=64 \
EPOCH_NUM=200 \
bash OCRtrain/tools/train_rec.sh
```

6. 导出推理模型：

```bash
PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
CHECKPOINT_PATH=/home/cht/code/IQIdet/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/latest \
EXPORT_DIR=/home/cht/code/IQIdet/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/inference \
bash OCRtrain/tools/export_rec.sh
```

7. 导出完成后，在 `run_inference_pipeline.py` 里使用：

```bash
--ocr-rec-model-dir /home/cht/code/IQIdet/OCRtrain/runs/iqi_en_PP-OCRv5_mobile_rec/inference
```

## 建议的标注规范

建议在开始大规模标注前先统一以下规则：

- 是否全部转大写
- 是否保留空格
- 是否保留 `- / . : ( ) [ ]`
- `Ni` 是否统一成 `NI`

如果你决定统一标签规范，最好在人工转录阶段就统一，不要等训练后再洗标签。

## 当前默认模型选择

导出 crop 时，文本检测默认使用：

- `PP-OCRv5_server_det`

训练时，文本识别目标模型是：

- `en_PP-OCRv5_mobile_rec`

预训练权重默认读取：

- `OCRtrain/en_PP-OCRv5_mobile_rec_pretrained.pdparams`

## 参考

- PaddleOCR 3.x 文本识别模块文档  
  https://www.paddleocr.ai/latest/version3.x/module_usage/text_recognition.html
- PaddleOCR OCR 数据集格式  
  https://www.paddleocr.ai/main/en/datasets/ocr_datasets.html
