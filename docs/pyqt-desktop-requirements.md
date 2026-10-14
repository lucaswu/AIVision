# PyQt 桌面推理端：已确认需求

> 对应方案：[pyqt-desktop-inference-plan.md](pyqt-desktop-inference-plan.md)。本文记录已确认的决策，与方案文档 §7 的待确认项冲突时，以本文为准。

## 已确认决策

| # | 项 | 结论 |
|---|---|---|
| 1 | GUI 框架 | **PyQt6**（代码中信号用 `pyqtSignal`，枚举用 PyQt6 的完整限定写法，如 `Qt.AlignmentFlag.AlignCenter`） |
| 2 | 运行硬件 | 目标机器**继续使用 NVIDIA GPU**。启动时检测 CUDA 是否可用；**无 GPU 时在界面上明确提示**（如顶部红色警告条 + 设备下拉自动切到 CPU 并说明速度会很慢），不静默降级 |
| 3 | 功能范围 | **仅做批量推理 + 结果导出**。区域 OCR / 区域 SNR / 双丝分辨率交互工具、模型热更新、与后端对接均不在本期 |
| 4 | 输出内容 | 保存 **JSON 结果 + 标注图**。固定格式的 Excel/CSV 报告**暂不做**，后期按具体要求再整改（因此本期不实现 `summary.csv`/`export.py`，但输出层预留扩展点） |
| 5 | 模型分发 | **手工替换模型文件**即可，不做模型包导入/热更新；界面提供「模型设置」页，可浏览替换各模型路径并显示是否存在 |

## 由此调整的实施范围

- 保留：`desktop/engine.py`、`worker.py`、`render.py`（标注图）、`ui/*`、`settings.py`、`paths.py`
- 取消：`export.py`（CSV/Excel 汇总）；方案 §5 阶段 4 仅保留"标注图 + run_params.json"
- 输出目录结构（本期）：

```
<输出路径>\<任务名或时间戳>\
  inference_results.json
  iqi_grade_results.json   # 启用 IQI 时
  annotated\               # 标注图，保持输入的相对子目录
  iqi_vis\
  errors.json
  run_params.json
  run.log
```

- 标注图：本期默认开启保存（用户明确要求保存标注图），可在界面关闭。

## 仍沿用方案中的默认约定

- 单任务串行，不支持同时多任务
- 完全离线独立运行，不依赖 Docker / Java 后端 / MinIO
- 首期默认关闭 TensorRT（`INFERENCE_USE_TENSORRT=false`），稳定后再作为加速选项开放
- 交付形态：Python 环境 + 启动 bat
- Windows 环境验证（torch 与 paddle GPU 共存）作为实施的第一步

## 跨平台修复策略

`IQIDDET/src/gauge/runtime/ocr_runtime.py` 的管道读取（`selectors` + 管道）统一改为"后台读线程 + `queue.Queue` 带超时"的实现，**Linux 与 Windows 共用同一份代码**，不做平台分支。Docker 版行为（超时语义、错误信息）保持不变，并以现有测试回归。
