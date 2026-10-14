# PyQt 桌面版推理端：进展与交接

> 更新时间：2026-10-15。用于换系统/换机器后继续工作。
> 相关文档：[方案](pyqt-desktop-inference-plan.md)、[已确认需求](pyqt-desktop-requirements.md)、[desktop/README](../model/weld/desktop/README.md)

## 1. 一句话状态

桌面版的**引擎、命令行、PyQt6 界面均已实现并在 Linux + RTX 4090 上跑通**（检测 + 方向矫正 + 位置检测 + 标注图）。**尚未在 Windows 实机验证**，且 **IQI（像质计/OCR）全链路尚未在带 PaddleOCR 的环境验证**。

## 2. 已确认的需求（摘要）

- GUI：**PyQt6**；Python 3.10（与现有 requirements 一致）
- 目标机器有 NVIDIA GPU；检测不到 GPU 时界面给出明确提示
- 本期只做**批量推理 + 结果导出**：输出 JSON + 标注图（Excel/CSV 等后期按具体要求再做）
- 模型文件**手工替换**即可，不做热更新/模型包导入
- 单任务串行，完全离线独立运行（不依赖 Docker / Java 后端）
- 默认关闭 TensorRT（Windows 下未验证）

## 3. 代码提交记录（当前分支 `game`，**尚未 push**）

| 提交 | 内容 |
|---|---|
| `82d21ce` | `ocr_runtime.py`：管道读取由 `selectors` 改为"读线程 + queue 超时"，Linux/Windows 共用；新增 `IQIDDET/tests/test_ocr_runtime.py` |
| `7b34458` | 新增 `utils/cv_io.py`（及 IQIDDET 内同步副本 `gauge/imaging/cv_io.py`），推理入口读图/写图改用 imdecode/imencode，支持 Windows 中文路径；`tests/test_cv_io.py` |
| `5048249` | `model/weld/desktop/` 引擎层：`engine.py`、`render.py`、`cli.py`、`paths.py`、`inputs.py`；`ocr_runtime` 子进程显式设置 `PYTHONPATH`；`tests/test_desktop.py` |
| `9a6787a` | PyQt6 界面：`app.py`、`ui/*`、`worker.py`、`settings.py`；`requirements-desktop.txt`、`run_desktop.bat`、`desktop/README.md` |

> 换系统前请先 `git push`（本文档提交后也一并 push），或自行拷贝仓库。工作区里另有与本任务无关的未提交改动（`deploy/README.md`、`push.sh`、若干 zip），未处理。

## 4. 目录与职责

```
model/weld/
├─ desktop/
│  ├─ app.py            入口：python -m desktop.app（GUI）
│  ├─ cli.py            入口：python -m desktop.cli <输入...> -o <输出>（无界面，验收/排错）
│  ├─ engine.py         InferenceEngine：参数构造、模型 bundle 常驻复用、逐张推理、取消、结果落盘
│  ├─ render.py         标注图：先按 correction.label 旋转原图，再画缺陷框/多边形/焊缝关键点/缺陷原点/IQI 摘要
│  ├─ inputs.py         目录/文件展开为图像列表（保留相对路径）
│  ├─ paths.py          路径约定 + ModelPaths（各模型默认路径）
│  ├─ settings.py       界面参数持久化（JSON）
│  ├─ worker.py         QThread：EngineProbe(后台建引擎+GPU检测)、InferenceWorker
│  └─ ui/               main_window.py、image_viewer.py、model_dialog.py
├─ utils/cv_io.py       Unicode 路径安全的 imread/imwrite
├─ requirements-desktop.txt
├─ run_desktop.bat
└─ tests/test_desktop.py, tests/test_cv_io.py
```

设计要点：

- 复用 `run_inference_pipeline.InferencePipelineRunner`，**不引入** `api_server`（FastAPI）；`engine.py` 对应 api_server 的 `_build_runtime_args / _create_runtime_bundle / _sync_run_inference_direct`。
- 逐张调用 `runner.run([img])`，以获得进度、取消、单张结果；`runner.run` 内部吞掉单张异常，引擎通过日志抓取 `[警告]` 行作为失败原因。
- 结果 JSON 与 Docker 版同 schema；`bbox` 等坐标在"方向矫正后"的图像坐标系，所以标注图要先矫正再画。
- 引擎 `run()` 会重定向 `sys.stdout/stderr`，默认日志必须写 `sys.__stdout__`，否则递归（已踩过坑并修复）。
- 默认模型路径：`model/weld/weight/`（主模型取 `primary-weights.pth`，没有则 `0208primary.pth`；可用环境变量 `AIVISION_WEIGHTS_DIR` 改目录）、`model/weld/IQIDDET/models/`。

## 5. 输出结构

```
<输出目录>\<时间戳或任务名>\
  inference_results.json   iqi_grade_results.json(启用IQI)   annotated\   iqi_vis\
  errors.json(有失败时)    run_params.json                    input_files.txt   progress.json
```

16bit/DICOM 转 8bit 的中间图放用户缓存目录（Windows `%LOCALAPPDATA%\AIVision\prepared`），运行后清理。

## 6. 已验证 / 未验证

**已验证（Linux，py11 环境，RTX 4090）**

- CLI 与 GUI（offscreen 驱动）：4 张图（含中文目录名、16bit tif）成功 4、失败 0，约 11 秒
- 停止功能：停止后只保留已完成图像，输出文件完整
- 标注图方向与框位置正确
- 测试：`tests/test_desktop.py`、`tests/test_cv_io.py`、`IQIDDET/tests/test_ocr_runtime.py` 共 10 项通过

**未验证 / 待办（按优先级）**

1. **Windows 实机**（最重要，阶段 0）：torch 2.5.1+cu121 与 paddlepaddle-gpu 3.3.0 在同一环境共存是否有 DLL 冲突；`run_desktop.bat`；PyQt6 窗口；中文路径；DICOM。若冲突：让 OCR 子进程使用独立 Python 环境（`PaddleOCRSubprocessClient` 已有 `python_bin` 参数，只需把它从引擎透传出来）。
2. **IQI 全链路**：本机 py11 缺 `paddleocr`，IQI 一直是关闭状态跑的。需验证：OCR worker 启动、`iqi_grade_results.json`、`iqi_vis/`、结果表 IQI 列（现取 `ocr.plate_code / ocr.grade`，字段名需用真实输出核对）。
3. **与 Docker 版逐字段对比**：同一批图在 Docker 版与桌面版的 `inference_results.json` 应一致，作为验收基线。
4. **主模型版本**：确认 `0208primary.pth` 是否为线上实际使用的 `primary-weights.pth`。
5. TensorRT 的 Windows 适配（可选，默认关闭）。
6. 后续（本期之外）：Excel/CSV 报告（等具体格式要求）、区域 OCR/SNR/双丝分辨率交互工具、公共 core 抽取（让 api_server 与 desktop 共用，需回归 Docker）。

**已知非本任务问题**：`IQIDDET/tests` 里原有的 5 个测试文件（`test_iqi_*`、`test_region_*`）在收集阶段就报 ImportError（引用了已不存在的模块，如 `gauge.region_snr_service`），改动前即如此。

## 7. 换系统后如何继续

### 7.1 取代码

```bash
git checkout game          # 本任务的提交都在此分支（若已 push 则 git pull）
```

### 7.2 Windows 目标机环境（Python 3.10）

```bat
:: 1) PyTorch（CUDA 12.1）
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
:: 2) PaddlePaddle GPU（版本以阶段 0 验证为准）
pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
:: 3) 其余依赖
cd model\weld
pip install -r requirements-desktop.txt
pip install --no-deps -r requirements-rfdetr-nodeps.txt
```

模型文件需放到：`model\weld\weight\`（weldROI4.pt、primary-weights.pth、weld_orientation_model.pth、location_0.pt、location_1.pt）和 `model\weld\IQIDDET\models\`（guagerotation.pt、fclip67.pth.tar、fclip_config.yaml、ocr_orientation_model.pth、PP-OCRv5_server_det\、OCR_rec_inference_best_accuracy0325\）。这些文件体积大、不在 git 里，需单独拷贝；或在界面「模型设置」里逐项指定路径。

### 7.3 验证步骤（建议顺序）

```bat
cd model\weld
:: a) 先不启用 IQI，确认检测链路
python -m desktop.cli D:\imgs -o D:\out --no-iqi
:: b) 再启用 IQI（验证 paddle 与 torch 共存、OCR 子进程）
python -m desktop.cli D:\imgs -o D:\out
:: c) 图形界面
python -m desktop.app        :: 或双击 run_desktop.bat
```

### 7.4 运行测试

```bat
cd model\weld
python -m pytest tests\test_desktop.py tests\test_cv_io.py -q
cd IQIDDET
python -m pytest tests\test_ocr_runtime.py -q
```

### 7.5 回到本机 Linux 开发的环境

py11 环境：`/home/lucas/miniconda3/envs/py11`（已装 torch、ultralytics、PyQt6；**缺 paddleocr**）。无显示器时用 `QT_QPA_PLATFORM=offscreen` 跑 GUI 烟测。测试图可用 `e2e/defect_img_*.bmp`。
