# Windows 打包与运行

当前仓库里的 [label_rec_no_box.py](/home/cht/code/IQIdet/OCRtrain/tools/label_rec_no_box.py) 是纯 Python + Pillow 工具，可以在 Windows 上打包成单文件 `exe`。

注意：

- 我当前在 Linux 环境下，不能直接产出可靠的 Windows `exe`。
- 但我已经把 Windows 侧所需脚本补齐了，你把整个 `OCRtrain/tools` 目录带到 Windows 机器后，可以直接打包。

## 1. Windows 机器准备

安装：

- Python 3.10 或更高版本
- 安装时勾选 `Add Python to PATH`

然后确认下面命令可用：

```bat
py --version
```

## 2. 构建 exe

在 Windows 的 `cmd` 里进入本目录：

```bat
cd /d D:\path\to\IQIdet\OCRtrain\tools
```

执行：

```bat
build_label_rec_no_box_windows.bat
```

构建成功后，生成文件在：

```text
OCRtrain\tools\dist\label_rec_no_box.exe
```

## 3. 启动标注器

现在不需要再手工传一串路径参数。

直接双击：

```text
dist\label_rec_no_box.exe
```

或者执行：

```bat
run_label_rec_no_box_windows.bat
```

程序会：

- 弹出文件夹选择框，让你选择待标注图片目录
- 自动打开浏览器到标注页面
- 自动在 `exe` 所在目录生成：
  - `<所选文件夹名>.txt`
  - `<所选文件夹名>_labels.tsv`
  - `<所选文件夹名>_session.json`

例如选择目录：

```text
D:\iqi_rec_textdet_v1\det_crops\all
```

则默认生成：

```text
dist\all.txt
dist\all_labels.tsv
dist\all_session.json
```

## 4. 如果你仍然想手工传参

也仍然支持命令行模式：

```bat
dist\label_rec_no_box.exe --image-dir D:\iqi_rec_textdet_v1\det_crops\all --path-root D:\iqi_rec_textdet_v1 --output-file D:\iqi_rec_textdet_v1\all.txt --host 127.0.0.1 --port 8766
```

## 5. 分发给标注人员

最简单的分发方式是把下面这些一起打包给对方：

- `dist\label_rec_no_box.exe`
- `run_label_rec_no_box_windows.bat`
- 需要标注的图片目录

对方只需要双击 `label_rec_no_box.exe` 或 `run_label_rec_no_box_windows.bat`，再在弹窗里选目录即可。
