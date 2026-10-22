# AIVision 推理端 PyQt 桌面版方案（Windows 直接运行 Python）

> 状态：**方案草案，待确认后实现**。本文只做调研与设计，尚未改动任何代码。

## 1. 目标与范围

**目标**：把 `model/weld` 下的推理能力做成一个 PyQt 桌面程序，在 Windows 上直接 `python` 运行（不依赖 Docker / nginx / Java 后端 / MinIO / 前端）。

用户流程：

1. 选择**输入路径**（一个目录，或若干图片文件）
2. 选择**输出路径**
3. 调整少量参数（模式、置信度、各功能开关、设备）
4. 点击「开始」→ 进度条 + 日志 + 结果列表
5. 结果写入输出路径，可在界面内预览（图像 + 检测框）

**范围内**：焊缝缺陷检测（ROI → 主模型 RF-DETR → 融合）、方向矫正、焊缝位置检测（location_0 / location_1）、IQI 像质计识别（gauge OBB + FClip + PaddleOCR）、灰度值计算、结果导出。

**范围外**（桌面版不需要，保持 Docker 方案不变）：FastAPI 服务、模型热更新（model_agent / model_runtime_manager / revision_sets / bundle 安装）、nginx + mTLS 控制面、任务队列/租约、TensorRT 后台异步构建后的"原地热替换"。

## 2. 现状调研结论

### 2.1 推理链路在容器里的形态

```
Java api_gateway ──HTTP──▶ model/weld/api_server.py (FastAPI, uvicorn)
                              │  /inference/submit  → BackgroundTasks
                              │  _sync_run_inference_direct()
                              ▼
                   InferencePipelineRunner  (run_inference_pipeline.py)
                   ├─ WeldROIDetector        (weldROI4.pt, YOLO)
                   ├─ 主模型 RF-DETR          (primary-weights.pth)   ← utils/detection_pipeline.py
                   ├─ WeldOrientationCorrector (weld_orientation_model.pth)
                   ├─ WeldSeamLocator         (location_0.pt, YOLO pose)
                   ├─ WeldDefectPositionDetector (location_1.pt)
                   └─ IQIInferencer           (IQIDDET: guagerotation.pt + fclip67 + PaddleOCR 子进程)
```

关键事实：

- **核心推理类与 HTTP 完全解耦**。`InferencePipelineRunner.run(image_inputs)` 输入 `PreparedImageInput` 列表，返回 `List[dict]`，没有任何 FastAPI 依赖。桌面版可直接复用。
- `api_server.py`（1970 行）里与"推理"相关、需要被抽取复用的只有三块：
  - `_build_runtime_args()`：构造 argparse.Namespace（所有模型路径、阈值、开关）
  - `_create_runtime_bundle()`：按 args 实例化各模型 + runner
  - `_sync_run_inference_direct()`：准备输入 → `runner.run()` → 写 `inference_results.json` / `iqi_grade_results.json`
- `run_inference_pipeline.py` 本身就有 `main()` CLI（`--image-dir / --output-dir / --enable-*`），但它是一次性脚本、无进度回调、模型每次重新加载，不适合直接作为 GUI 后端。
- 路径全部写死为容器路径：`/app/model/weights/*`、`/app/data/files`、`/app/data/results`、`/app/model/engine_cache`。桌面版需要统一替换为可配置路径。
- 输出产物（与现有后端消费格式一致，桌面版保持不变以便日后互通）：
  - `inference_results.json`：`{"mode", "results":[{image_path, width, height, rois[{bbox, defects/detections[{bbox,class_name,conf}]}], weld_location, defect_position, correction{label,rotation,flip}, ocr, grayscale_density, grayscale_density_regions}]}`
  - `iqi_grade_results.json`：`schema: iqi_grade_batch_v1`，含 summary 统计与逐图 delivery record
  - `iqi_vis/`：IQI 调试可视化图
  - `progress.json`：进度（容器里由 API 轮询）
- 支持的输入格式：`.jpg .jpeg .png .bmp .tif .tiff .dcm .dicom .dic .diconde`（16bit/DICOM 会先转 8bit，进入 `prepared_inputs/`）。
- **推理流水线本身不输出带框的标注图**（框是前端画的）。桌面版要自己画。

### 2.2 模型与依赖

| 文件 | 来源 | 大小 |
|---|---|---|
| `weight/weldROI4.pt` | ROI 检测 | 51MB |
| `weight/0208primary.pth` | 主模型（容器内名为 primary-weights.pth） | **1.5GB** |
| `weight/weld_orientation_model.pth` | 方向矫正 | 94MB |
| `weight/location_0.pt` / `location_1.pt` | 焊缝位置 / 缺陷位置 | 6MB / 52MB |
| `IQIDDET/models/guagerotation.pt` | 像质计 OBB | 6MB |
| `IQIDDET/models/fclip67.pth.tar` + `fclip_config.yaml` | 像质丝计数 | 459MB |
| `IQIDDET/models/PP-OCRv5_server_det/`、`OCR_rec_inference_best_accuracy0325/` | PaddleOCR 离线模型 | — |
| `IQIDDET/models/ocr_orientation_model.pth` | 文本方向矫正 | 85MB |

依赖（`requirements.txt`）：torch 2.5.1+cu121、ultralytics 8.4.167、rfdetr（`--no-deps` 单独装）、paddlepaddle-gpu 3.3.0 + paddleocr 3.4.0、tensorrt 11.3（可选）、opencv、pydicom 等。**无需** fastapi/uvicorn/cryptography 等服务端依赖。

### 2.3 迁移到 Windows 的风险点（已在代码中确认）

| # | 风险 | 位置 | 处理 |
|---|---|---|---|
| 1 | **OCR 子进程读取用 `selectors` 监听管道**，Windows 不支持对管道 `select`，IQI 的 OCR 会直接报错/卡死 | `IQIDDET/src/gauge/runtime/ocr_runtime.py:86-95` | 改为后台读线程 + `queue.Queue(timeout)`，跨平台。**必须修改**，改动约 20 行，不影响 Linux |
| 2 | 子进程用 `sys.executable` 启动 `ocr_paddle_worker.py` | `ocr_runtime.py:71` | 直接 python 运行下无问题；若走 PyInstaller 打包会失效（见 §6） |
| 3 | TensorRT engine 缓存目录默认 `/app/model/engine_cache`；`libcudart.so` 符号链接修复为 Linux 专用 | `utils/trt_backend.py:112-150` | 设置 `TRT_ENGINE_CACHE_DIR=%LOCALAPPDATA%\AIVision\engine_cache`；非 Linux 跳过符号链接修复（已有 try/except，不致命）。**首期默认关闭 TensorRT**（`INFERENCE_USE_TENSORRT=false`），稳定后再作为"加速选项"开放 |
| 4 | `main()` 里的 cuDNN/cuBLAS 符号链接块是 Linux 专用 | `run_inference_pipeline.py:810-823` | GUI 不走 `main()`，无影响 |
| 5 | 中文/含空格路径下 `cv2.imread` 在 Windows 读不到 | `utils/pipeline_utils.load_image` 等 | 实现阶段需核查，统一改为 `np.fromfile + cv2.imdecode`，写图用 `imencode().tofile()` |
| 6 | `PYTHONPATH` 顺序依赖（`IQIDDET/src` 必须在 `IQIDDET` 之前，且两处存在同名 `run_inference_pipeline.py`） | Dockerfile.ai ENV、`api_server._load_weld_pipeline_module` | 桌面版入口里按同样顺序设置 `sys.path`，用 `importlib` 按文件路径加载（沿用 api_server 的做法） |
| 7 | PaddlePaddle 与 PyTorch 在同进程各自带 CUDA/cuDNN DLL，Windows 上可能出现 DLL 冲突 | 运行时 | 这是 Windows 上最大的不确定项，**阶段 0 先做环境验证**（见 §7）；OCR 已是独立子进程，本身起到隔离作用 |
| 8 | 显存：ROI + RF-DETR(1.5GB 权重) + 3 个 YOLO + FClip + orientation + Paddle 同时常驻 | — | 提供"功能开关"，关闭不需要的模块则不加载；设备可选 CPU |

## 3. 总体方案

### 3.1 架构

```
┌────────────────────────── PyQt 进程 ───────────────────────────┐
│  MainWindow (UI线程)                                           │
│    ├─ 输入/输出路径、参数面板、开始/停止                         │
│    ├─ 进度条 + 日志窗口 + 结果表格 + 图像预览(叠加框)            │
│    └─ 信号/槽 ◀──────────────┐                                  │
│                              │ Qt Signals                       │
│  InferenceWorker (QThread)   │                                  │
│    └─ desktop.engine.InferenceEngine                            │
│         ├─ 首次/参数变更时构建 bundle（模型常驻复用）            │
│         ├─ 逐张调用 runner.run([img])  → 进度/取消/单张结果信号  │
│         └─ 写 inference_results.json / iqi_grade_results.json …  │
│                         │                                       │
│                         └─ spawn ─▶ ocr_paddle_worker (子进程)   │
└─────────────────────────────────────────────────────────────────┘
```

要点：

1. **推理放 QThread**，UI 不阻塞；日志通过重定向 `stdout/stderr` 到 Qt 信号（复用 api_server 里 `_PrefixedStream` 的思路）。
2. **逐张调用 `runner.run([one_image])`**：这样每张图结束后可发进度信号、响应"停止"（图与图之间中断）、并立即把单张结果推给界面预览。`runner` 的内部状态（`args`、`output_dir`、`iqi_vis_dir`…）按 api_server 的做法在每次任务前赋值。
3. **模型常驻**：同一个窗口生命周期内，参数中"影响模型构建"的项（权重路径、设备、各 enable 开关、置信度阈值等）不变则复用 bundle；变更才重建。沿用 `_build_runtime_signature` 的签名思路。
4. **不引入服务**：不起 HTTP 端口，不依赖数据库。

### 3.2 代码组织（新增，不动现有 Docker 流程）

```
model/weld/
├─ desktop/                       # 新增：桌面版全部代码
│  ├─ __init__.py
│  ├─ app.py                      # 入口：python -m desktop.app
│  ├─ paths.py                    # 路径解析（程序目录/权重目录/缓存目录/用户配置）
│  ├─ settings.py                 # 配置读写（JSON，%APPDATA%\AIVision\settings.json）
│  ├─ engine.py                   # InferenceEngine：args 构造 + bundle 构建 + 逐张运行 + 结果落盘
│  ├─ worker.py                   # QThread 封装 + 信号
│  ├─ render.py                   # 在原图上叠加缺陷框/位置/IQI 并保存（OpenCV/PIL，中文字体）
│  ├─ export.py                   # CSV/Excel 汇总导出
│  └─ ui/
│     ├─ main_window.py
│     ├─ param_panel.py
│     ├─ result_table.py
│     └─ image_viewer.py          # 缩放/拖拽 + 框叠加
├─ run_desktop.bat                # 双击启动（调用指定 python 环境）
└─ requirements-desktop.txt       # 在 requirements.txt 基础上：去服务端依赖 + 加 PyQt
```

**与 api_server.py 的关系**——两种做法，推荐 A：

- **A（推荐，首期）**：`desktop/engine.py` 自包含，参照 api_server 的三块逻辑重写一份，路径改为可配置。优点：不碰线上 Docker 代码，零回归风险。缺点：有少量重复。
- **B（后续）**：把三块逻辑抽到 `inference_core.py`，api_server 与 desktop 共用。更干净，但要改动并回归 Docker 路径，建议桌面版稳定后再做。

### 3.3 模型/路径配置

桌面版不使用 `/app/model/...`，改为"程序根目录相对 + 可在设置中覆盖"：

```
<程序目录>\
  weights\                 # 对应容器 /app/model/weights
    weldROI4.pt
    primary-weights.pth    # 即 0208primary.pth，或界面选择任意 .pth
    weld_orientation_model.pth
    location_0.pt
    location_1.pt
  IQIDDET\models\...       # 与现有目录结构一致
```

- 界面「模型设置」页列出每个模型的路径、存在性（✓/✗）、文件大小，允许单独浏览替换（用于自行更新模型，无需热更新机制）。
- 缺失的可选模型（orientation / location_0 / location_1 / IQI）自动置灰对应开关，行为与 api_server 一致（`os.path.exists` 判定）。

### 3.4 界面设计

```
┌ AIVision 焊缝检测 ─────────────────────────────────────────────┐
│ 输入  [D:\xray\batch01                 ] [选择目录] [选择文件]   │
│ 输出  [D:\xray\out\batch01             ] [选择目录]   ☑ 递归子目录│
├ 参数 ──────────────┬ 结果 ─────────────────────────────────────┤
│ 模式  (●)检测 ( )分割│ 文件名        缺陷数  位置  IQI等级  状态  │
│ 设备  [cuda:0 ▾]    │ A001.tif       3      ✓    W12/…    OK    │
│ 主模型置信度 [0.15] │ A002.dcm       0      ✓    —        OK    │
│ ☑ 横切纵拼          │ A003.png       —      —    —        失败  │
│ ☑ 方向矫正          ├────────────────────────────────────────────┤
│ ☑ 焊缝位置检测 [0.6]│ [图像预览：叠加缺陷框/位置线，滚轮缩放]      │
│ ☑ 缺陷位置检测2[0.25]│                                            │
│ ☑ IQI 像质计识别    │                                            │
│ ☐ 保存标注图        │                                            │
├────────────────────┴────────────────────────────────────────────┤
│ [████████░░░░] 126/300  A126.tif  阶段: running   [开始] [停止]  │
│ 日志 …                                                          │
└──────────────────────────────────────────────────────────────────┘
```

功能清单：

- 输入：目录（可递归，保持相对子目录结构输出）/ 多选文件 / 拖拽
- 参数：对应 `InferenceRequest` 的全部字段（mode / device / primary_conf / wide_slice / enable_location+conf / enable_location2+conf / enable_iqi），另加"保存标注图""输出格式"
- 运行：开始 / 停止（当前图完成后中断）；启动时展示模型加载阶段（`initializing`）
- 结果：表格 + 点击行预览；双击打开输出目录
- 失败处理：单张失败不终止批次，记录到 `errors.json` 并在表格标红
- 参数记忆：关闭时保存到 settings.json，下次启动恢复；最近使用的输入/输出路径

### 3.5 输出目录结构

```
<输出路径>\<任务名或时间戳>\
  inference_results.json        # 与 Docker 版同 schema（便于与后端/前端对比、回归）
  iqi_grade_results.json        # 启用 IQI 时
  summary.csv                   # 每图一行：文件、缺陷数、各类缺陷计数、位置、IQI 等级、灰度值、状态
  annotated\                    # 勾选"保存标注图"时：叠加框后的 jpg/png（保持相对子目录）
  iqi_vis\                      # IQI 调试图（已有）
  errors.json                   # 失败清单
  run_params.json               # 本次运行参数 + 模型文件指纹 + 版本，便于追溯
  run.log
```

`prepared_inputs/`（16bit/DICOM 转 8bit 的中间图）放到用户缓存目录而非输出目录，运行结束可清理，避免污染输出。

## 4. 技术选型

| 项 | 方案 | 说明 |
|---|---|---|
| GUI 框架 | **PyQt5** 或 **PySide6** | API 几乎一致，代码用 `QtCore.Signal` 兼容层。若无商用授权顾虑选 PyQt；有顾虑选 PySide6（LGPL）。**需你确认** |
| Python | 3.10 | 与现有 requirements 验证环境一致 |
| 并发 | QThread + 信号 | 推理单线程串行（与 api_server 的 `_runtime_execution_lock` 语义一致） |
| 配置 | JSON | 无需引入新依赖 |
| 标注图绘制 | OpenCV + PIL（中文字体） | 复用 `utils.pipeline_utils.FontRenderer` |
| 汇总导出 | CSV（标准库）；Excel 可选 openpyxl | |

## 5. 实施步骤

| 阶段 | 内容 | 产出/验收 |
|---|---|---|
| **0 环境验证**（最先做） | 在目标 Windows 机器上建 py3.10 环境，装 torch/paddle/ultralytics/rfdetr；用现有 `run_inference_pipeline.py --image-dir … --enable-iqi` 命令行跑通 10 张图 | 确认 torch+paddle DLL 不冲突、GPU 可用、DICOM/16bit 正常；记录最终可用的版本组合 |
| 1 跨平台修复 | 修 `ocr_runtime.py` 的管道读取；图像读写中文路径；TRT 路径 Windows 适配/默认关闭 | Windows 下 IQI 流程跑通；Linux/Docker 测试（`IQIDDET/tests`、`tests/`）全绿 |
| 2 引擎层 `desktop/engine.py` | args 构造、bundle 构建与复用、逐张运行、结果落盘、取消 | 无 GUI 的脚本调用，输出 JSON 与 Docker 版**逐字段对比一致**（同一批图） |
| 3 GUI 主体 | 窗口、参数面板、进度/日志、结果表、预览、设置页 | 手工走通完整流程；异常输入（空目录、无权限、损坏图、中途停止）行为合理 |
| 4 标注图与导出 | `render.py`、`summary.csv`、`run_params.json` | 抽样核对标注与 JSON 一致 |
| 5 交付 | `requirements-desktop.txt`、`run_desktop.bat`、使用说明（含模型放置、显卡/驱动要求） | 干净机器按文档 30 分钟内可跑起来 |
| 6（可选） | 区域 OCR / 区域 SNR / 双丝分辨率的交互工具页（对应 `/inference/recognize`、`/region-snr`、`/double-wire`）；TensorRT 加速开关；抽取公共 core（方案 B） | 视需求 |

## 6. 交付形态

- **推荐：Python 环境 + 启动 bat**（用户说的"直接执行 python"）。可用 conda-pack / embeddable Python + 离线 wheel 目录，内网机器也能装；路径、权重、DLL 问题最少，排错容易。
- 不推荐首期做 **PyInstaller 单 exe**：torch + paddle + CUDA 体积巨大（数 GB），paddle 子进程用 `sys.executable` 启动 `ocr_paddle_worker.py` 在冻结环境下需额外改造，隐式导入（rfdetr / paddlex）也容易漏。如确有单文件需求，放到后续再评估。

## 7. 风险与待确认事项

**需要你确认的决策**

1. GUI 框架：PyQt5 / PyQt6 / PySide6？（默认 PyQt5）
2. 目标机器：是否有 NVIDIA GPU？显存多大？驱动/CUDA 版本？无 GPU 时是否接受 CPU 慢速运行（RF-DETR + Paddle 在 CPU 上会很慢）？
3. 功能范围：首期是否只做"批量推理 + 结果查看/导出"？区域 OCR / SNR / 双丝分辨率交互工具是否需要？
4. 输出需求：除 `inference_results.json` 外，是否需要固定格式的 Excel/CSV 报告（列定义）？是否需要标注图？
5. 模型分发：桌面版模型文件由谁放置、如何更新？是否需要"导入模型包"（沿用现有 bundle zip 格式）？首期按"手工替换文件"处理。
6. 并发：是否需要同时处理多个任务？首期按单任务串行。
7. 是否需要与现有 Java 后端/平台对接（上传结果、读取任务）？方案按"完全离线独立"设计。

**主要风险**

- Windows 下 PyTorch 与 PaddlePaddle(GPU) 共存、cuDNN 版本冲突 → 阶段 0 验证，必要时 OCR 子进程使用独立 Python 环境（`ocr_runtime` 已是子进程，改一个解释器路径参数即可）。
- 1.5GB 主模型加载时间 + 多模型显存占用 → 功能开关、启动时显示加载进度。
- 容器内长期验证过的版本组合（TensorRT 11.3 / modelopt 等）在 Windows 上未验证 → 首期不启用 TensorRT。
- 现有测试大多针对 Linux/Docker，Windows 无回归保障 → 阶段 2 用"同批图与 Docker 结果逐字段对比"作为验收基线。

---

## 8. 竞赛专项适配（2026年无损检测射线AI大赛）

针对《2026年全国无损检测射线AI智能评片技能大赛》的专项技术方案、评定规则引擎设计及待办工作清单，详见：
👉 **[`competition-implementation-plan.md`](competition-implementation-plan.md)**
（包含 NB/T 47013.2-2015 评定引擎、0.042mm 像素折算、影像查重、最左 X 定位与标准 Excel 导出的完整实施分解）

