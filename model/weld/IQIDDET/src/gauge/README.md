# src/gauge

像质计（IQI）等级识别系统的核心包。按职责分为六层：

| 层 | 目录 | 职责 | 依赖约束 |
|----|------|------|---------|
| 交付层 | `app/` | 对外门面、模型生命周期、delivery payload | 可依赖所有层 |
| 编排层 | `pipeline/` | PipelineRunner、StageContext、7 个 Stage | domain, imaging, services |
| 业务层 | `domain/` | IQI 规则、等级计算、记录构建、统计 | stdlib + models only |
| 图像层 | `imaging/` | 几何变换、预处理、可视化 | OpenCV + NumPy |
| 运行时层 | `runtime/` | 子进程/线程池/锁/shutdown | stdlib + OpenCV/NumPy |
| 适配层 | `services/` | 模型适配器（OCR/FClip/ROI/Orientation/Region） | 模型库 |

完整架构说明见仓库根目录 `ARCHITECTURE.md`。
