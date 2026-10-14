# AIVision 桌面版

在本机直接运行焊缝检测推理（不需要 Docker / 后端 / 前端）。

## 运行

```bash
# 在 model/weld 目录下
python -m desktop.app                       # 图形界面（PyQt6）
python -m desktop.cli <输入目录或文件...> -o <输出目录>   # 无界面
```

Windows 可双击 `run_desktop.bat`（可传入 python.exe 路径作为第一个参数）。
依赖见 `requirements-desktop.txt`。

## 模型文件

默认读取（均可在界面「模型设置」中逐项替换，设置保存在用户配置目录）：

| 模型 | 默认路径 |
|---|---|
| ROI / 位置 / 矫正 / 主模型 | `model/weld/weight/`（主模型取 `primary-weights.pth`，没有则取 `0208primary.pth`）；可用环境变量 `AIVISION_WEIGHTS_DIR` 改目录 |
| IQI（像质计 / FClip / OCR） | `model/weld/IQIDDET/models/` |

## 输出

```
<输出目录>\<时间戳>\
  inference_results.json     与 Docker 版同 schema
  iqi_grade_results.json     启用 IQI 时
  annotated\                 标注图（保持输入的相对子目录）
  iqi_vis\                   IQI 调试图
  errors.json                失败清单（有失败时）
  run_params.json            本次参数、模型文件指纹、环境
```

16bit / DICOM 转 8bit 的中间图放在用户缓存目录，运行结束自动清理。

## 说明

- 默认不启用 TensorRT；需要时设置环境变量 `INFERENCE_USE_TENSORRT=true`，引擎缓存在用户缓存目录。
- 未检测到 NVIDIA GPU 时界面顶部显示红色提示，并自动切换到 CPU（速度非常慢）。
- 配置：Windows `%APPDATA%\AIVision\settings.json`，Linux `~/.config/AIVision/settings.json`。
