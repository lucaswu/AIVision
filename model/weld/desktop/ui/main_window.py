from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import paths
from ..engine import GpuInfo, ImageOutcome, InferenceEngine, RunConfig, RunSummary
from ..inputs import collect_inputs
from ..settings import UiSettings
from ..worker import EngineProbe, InferenceWorker
from .image_viewer import ImageViewer
from .model_dialog import ModelDialog

MAX_LOG_LINES = 5000
COLUMNS = ["文件", "缺陷数", "焊缝位置", "IQI", "评定等级", "评定结果", "状态"]
STAGE_TEXT = {"initializing": "正在加载模型…", "running": "推理中", "completed": "已完成",
              "cancelled": "已停止"}


def defect_count(result: Dict) -> int:
    return sum(len(r.get("defects") or r.get("detections") or []) for r in result.get("rois") or [])


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(max(0.0, seconds)), 60)
    return f"{m:02d}:{s:02d}"


def timing_text(now_elapsed_s: float, done_elapsed_s: float, infer_elapsed_s: float, done: int, total: int,
                deadline_min: float) -> Tuple[str, bool]:
    """状态栏计时文本，以及是否有超时风险（预计用时超过截止时间；未设截止时间按 40 分钟）。
    done_elapsed_s / infer_elapsed_s 为第 done 幅完成时的总用时 / 推理用时。"""
    from competition.exporter import forecast

    text = f"已用 {fmt_duration(now_elapsed_s)}"
    fc = forecast(done_elapsed_s, infer_elapsed_s, done, total, now_elapsed_s=now_elapsed_s)
    if fc is None:
        return text, False
    limit_s = (deadline_min if deadline_min > 0 else 40.0) * 60
    risk = fc.projected_s > limit_s
    text += f" | 平均 {fc.avg_s:.1f}s/幅 | 预计 {fmt_duration(fc.projected_s)} 完成 | 预计时间分 B={fc.score:.2f}"
    if risk:
        text += f" | ⚠ 预计超过 {limit_s / 60:g} 分钟"
    return text, risk


def competition_cells(ev: Optional[Dict]) -> List[str]:
    """评定等级 / 评定结果（定性 X=定位 定量）两列。"""
    if not ev:
        return ["—", "—"]
    records = "；".join(f"{r['defect_type']} X={r['x_px']} {r['quantity']}" for r in ev.get("records") or [])
    return [ev.get("grade_label") or "—", records or "无缺陷"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIVision 焊缝检测（桌面版）")
        self.resize(1360, 860)

        self._settings = UiSettings.load()
        self._models = paths.ModelPaths.from_dict(self._settings.models)
        self._engine: Optional[InferenceEngine] = None
        self._gpu: Optional[GpuInfo] = None
        self._worker: Optional[InferenceWorker] = None
        self._probe: Optional[EngineProbe] = None
        self._inputs: List[str] = list(self._settings.inputs)
        self._outcomes: Dict[int, ImageOutcome] = {}
        self._last_output: Optional[str] = None
        self._started_at = 0.0
        self._infer_started_at = 0.0   # 第一张开始推理的时间（不含模型加载）
        self._done = 0
        self._total = 0
        self._last_done_at = 0.0       # 最近一幅完成的时间
        self._timing_cfg: Optional[RunConfig] = None

        self._build_ui()
        self._load_settings_into_ui()
        self._start_probe()

    # ------------------------------------------------------------- 构建界面 ----
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        self.gpu_banner = QLabel()
        self.gpu_banner.setWordWrap(True)
        self.gpu_banner.setStyleSheet("background:#fff4ce;color:#7a4b00;padding:6px;border:1px solid #e6c200;")
        self.gpu_banner.setText("正在检测 GPU…")
        outer.addWidget(self.gpu_banner)

        # 输入/输出
        io_box = QGroupBox("路径")
        io = QFormLayout(io_box)
        self.input_edit = QLineEdit()
        self.input_edit.setReadOnly(True)
        self.input_edit.setPlaceholderText("请选择包含图像的目录，或选择若干图像文件")
        btn_dir = QPushButton("选择目录…")
        btn_dir.clicked.connect(self._pick_input_dir)
        btn_files = QPushButton("选择文件…")
        btn_files.clicked.connect(self._pick_input_files)
        row_in = QHBoxLayout()
        row_in.addWidget(self.input_edit, 1)
        row_in.addWidget(btn_dir)
        row_in.addWidget(btn_files)
        io.addRow("输入", row_in)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("结果保存到此目录下的以时间命名的子目录")
        btn_out = QPushButton("选择目录…")
        btn_out.clicked.connect(self._pick_output_dir)
        self.btn_open_out = QPushButton("打开结果目录")
        self.btn_open_out.clicked.connect(self._open_output)
        self.btn_open_out.setEnabled(False)
        row_out = QHBoxLayout()
        row_out.addWidget(self.output_edit, 1)
        row_out.addWidget(btn_out)
        row_out.addWidget(self.btn_open_out)
        io.addRow("输出", row_out)
        self.recursive_cb = QCheckBox("包含子目录")
        self.input_info = QLabel("")
        row_opt = QHBoxLayout()
        row_opt.addWidget(self.recursive_cb)
        row_opt.addWidget(self.input_info, 1)
        io.addRow("", row_opt)
        outer.addWidget(io_box)

        # 参数
        param_box = QGroupBox("参数")
        pf = QFormLayout(param_box)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("检测 (det)", "det")
        self.mode_combo.addItem("分割 (seg)", "seg")
        self.device_combo = QComboBox()
        self.device_combo.addItem("GPU (cuda:0)", "cuda:0")
        self.device_combo.addItem("CPU", "cpu")
        self.conf_spin = self._spin(0.01, 0.99, 0.15)
        self.wide_cb = QCheckBox("横切纵拼推理")
        self.corr_cb = QCheckBox("方向矫正")
        self.loc_cb = QCheckBox("焊缝位置检测")
        self.loc_spin = self._spin(0.01, 0.99, 0.6)
        self.loc2_cb = QCheckBox("缺陷位置检测")
        self.loc2_spin = self._spin(0.01, 0.99, 0.25)
        self.iqi_cb = QCheckBox("IQI 像质计识别")
        self.annot_cb = QCheckBox("保存标注图")
        pf.addRow("模式", self.mode_combo)
        pf.addRow("设备", self.device_combo)
        pf.addRow("主模型置信度", self.conf_spin)
        pf.addRow(self.wide_cb)
        pf.addRow(self.corr_cb)
        pf.addRow(self.loc_cb, self.loc_spin)
        pf.addRow(self.loc2_cb, self.loc2_spin)
        pf.addRow(self.iqi_cb)
        pf.addRow(self.annot_cb)
        btn_models = QPushButton("模型设置…")
        btn_models.clicked.connect(self._edit_models)
        pf.addRow(btn_models)

        # 竞赛评定
        self.comp_cb = QCheckBox("竞赛评定（NB/T 47013.2）")
        self.comp_cb.setToolTip("对每张图输出缺陷定位 X、定性、定量与评定等级，写入 competition_results.json")
        self.spec_edit = QLineEdit()
        self.spec_edit.setPlaceholderText("如 20 / 20+4 / Φ89×6")
        self.spec_edit.setToolTip("影像信息表中找不到的影像使用此规格（可留空）")
        self.info_table_edit = QLineEdit()
        self.info_table_edit.setReadOnly(True)
        self.info_table_edit.setPlaceholderText("《影像信息表》xlsx / csv")
        btn_info = QPushButton("…")
        btn_info.setFixedWidth(28)
        btn_info.clicked.connect(self._pick_info_table)
        btn_info_clear = QPushButton("×")
        btn_info_clear.setFixedWidth(28)
        btn_info_clear.clicked.connect(lambda: self.info_table_edit.setText(""))
        row_info = QHBoxLayout()
        row_info.addWidget(self.info_table_edit, 1)
        row_info.addWidget(btn_info)
        row_info.addWidget(btn_info_clear)
        self.fast_cb = QCheckBox("提速（关闭 IQI/位置检测/灰度值）")
        self.deadline_spin = QDoubleSpinBox()
        self.deadline_spin.setRange(0, 600)
        self.deadline_spin.setDecimals(1)
        self.deadline_spin.setSuffix(" 分钟")
        self.deadline_spin.setSpecialValueText("不限")
        self.deadline_spin.setToolTip("到时仍未处理的影像按无缺陷兜底并导出答案（缺陷识别超时整项 0 分）")
        self.table26_cb = QCheckBox("大中径管根部缺陷严格按表 26 分级")
        self.table26_cb.setToolTip("默认按竞赛规则（9）：超 Ⅲ 级限值判 Ⅳ，其余判 Ⅱ。\n"
                                   "勾选后外径 > 100mm 的管道：任意 3T 内累计 ≤ T 为 Ⅱ 级，总长 ≤ 100mm 为 Ⅲ 级")
        self.split_cb = QCheckBox("气孔框内精细拆分（实验）")
        self.split_cb.setToolTip("在原始高位图上把密集气孔大框拆回逐个气孔、按真实轮廓量长径。\n"
                                 "需用真实底片验证后再用于比赛")
        self.plate_root_cb = QCheckBox("板焊缝上的根部内凹/咬边也填报")
        self.plate_root_cb.setToolTip("默认不填报：第 6 章（板）不对根部内凹/咬边分级，且模型在板上常有贯穿整条焊缝的误检。\n"
                                      "组委会要求板上也必须填报时勾选")
        self.merge_gap_spin = QDoubleSpinBox()
        self.merge_gap_spin.setRange(0, 50)
        self.merge_gap_spin.setDecimals(1)
        self.merge_gap_spin.setSuffix(" mm")
        self.merge_len_combo = QComboBox()
        self.merge_len_combo.addItem("含间隔", "envelope")
        self.merge_len_combo.addItem("各段和", "sum")
        row_merge = QHBoxLayout()
        row_merge.addWidget(self.merge_gap_spin)
        row_merge.addWidget(self.merge_len_combo)
        for w in (self.merge_gap_spin, self.merge_len_combo):
            w.setToolTip("断续未熔合/未焊透/纵向裂纹：间隔 ≤ 该值合并为一个缺陷；\n"
                         "合并后长度取包络（含间隔）或各段之和")
        self._comp_widgets = (self.spec_edit, self.info_table_edit, btn_info, btn_info_clear, self.fast_cb,
                              self.deadline_spin, self.table26_cb, self.split_cb, self.plate_root_cb,
                              self.merge_gap_spin, self.merge_len_combo)
        self.comp_cb.toggled.connect(self._on_competition_toggled)
        pf.addRow(self.comp_cb)
        pf.addRow("影像信息表", row_info)
        pf.addRow("默认规格", self.spec_edit)
        pf.addRow("截止时间", self.deadline_spin)
        pf.addRow(self.fast_cb)
        pf.addRow(self.table26_cb)
        pf.addRow(self.plate_root_cb)
        pf.addRow(self.split_cb)
        pf.addRow("断续合并", row_merge)
        param_box.setFixedWidth(300)

        # 结果表 + 预览
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.viewer = ImageViewer()

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.viewer)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setSizes([200, 520])
        self.table.setMinimumHeight(120)

        mid = QHBoxLayout()
        mid.addWidget(param_box)
        mid.addWidget(split, 1)
        outer.addLayout(mid, 1)

        # 进度/控制/日志
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m")
        self.status_label = QLabel("就绪")
        self.timing_label = QLabel("")
        self._timing_timer = QTimer(self)
        self._timing_timer.setInterval(1000)
        self._timing_timer.timeout.connect(self._update_timing)
        self.btn_start = QPushButton("开始")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        row_run = QHBoxLayout()
        row_run.addWidget(self.progress, 1)
        row_run.addWidget(self.status_label)
        row_run.addWidget(self.timing_label)
        row_run.addWidget(self.btn_start)
        row_run.addWidget(self.btn_stop)
        outer.addLayout(row_run)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_LINES)
        self.log_view.setMaximumHeight(150)
        outer.addWidget(self.log_view)

    @staticmethod
    def _spin(lo: float, hi: float, val: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(0.05)
        s.setDecimals(2)
        s.setValue(val)
        return s

    # ------------------------------------------------------------- 设置 --------
    def _load_settings_into_ui(self) -> None:
        s = self._settings
        self.output_edit.setText(s.output_dir)
        self.recursive_cb.setChecked(s.recursive)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(s.mode)))
        self.device_combo.setCurrentIndex(max(0, self.device_combo.findData(s.device)))
        self.conf_spin.setValue(s.primary_conf)
        self.wide_cb.setChecked(s.wide_slice)
        self.corr_cb.setChecked(s.enable_correction)
        self.loc_cb.setChecked(s.enable_location)
        self.loc_spin.setValue(s.location_conf)
        self.loc2_cb.setChecked(s.enable_location2)
        self.loc2_spin.setValue(s.location2_conf)
        self.iqi_cb.setChecked(s.enable_iqi)
        self.annot_cb.setChecked(s.save_annotated)
        self.spec_edit.setText(s.competition_default_spec)
        self.info_table_edit.setText(s.competition_info_table)
        self.fast_cb.setChecked(s.competition_fast)
        self.table26_cb.setChecked(s.competition_strict_pipe_table26)
        self.split_cb.setChecked(s.competition_split_pores)
        self.plate_root_cb.setChecked(s.competition_report_plate_root)
        self.merge_gap_spin.setValue(s.competition_merge_gap_mm)
        self.merge_len_combo.setCurrentIndex(max(0, self.merge_len_combo.findData(s.competition_intermittent_length)))
        self.deadline_spin.setValue(s.competition_deadline_min)
        self.comp_cb.setChecked(s.enable_competition)
        self._on_competition_toggled(s.enable_competition)
        self._refresh_input_label()

    def _collect_settings(self) -> UiSettings:
        defaults = paths.ModelPaths.defaults().to_dict()
        overrides = {k: v for k, v in self._models.to_dict().items() if v != defaults.get(k)}
        return UiSettings(
            inputs=self._inputs, output_dir=self.output_edit.text().strip(),
            recursive=self.recursive_cb.isChecked(), mode=self.mode_combo.currentData(),
            device=self.device_combo.currentData(), primary_conf=self.conf_spin.value(),
            wide_slice=self.wide_cb.isChecked(), enable_correction=self.corr_cb.isChecked(),
            enable_location=self.loc_cb.isChecked(), location_conf=self.loc_spin.value(),
            enable_location2=self.loc2_cb.isChecked(), location2_conf=self.loc2_spin.value(),
            enable_iqi=self.iqi_cb.isChecked(), save_annotated=self.annot_cb.isChecked(),
            enable_competition=self.comp_cb.isChecked(), competition_default_spec=self.spec_edit.text().strip(),
            competition_info_table=self.info_table_edit.text().strip(),
            competition_fast=self.fast_cb.isChecked(), competition_deadline_min=self.deadline_spin.value(),
            competition_strict_pipe_table26=self.table26_cb.isChecked(),
            competition_split_pores=self.split_cb.isChecked(), competition_report_plate_root=self.plate_root_cb.isChecked(),
            competition_merge_gap_mm=self.merge_gap_spin.value(),
            competition_intermittent_length=self.merge_len_combo.currentData(), models=overrides,
        )

    # ------------------------------------------------------------- GPU/引擎 ----
    def _start_probe(self) -> None:
        self._probe = EngineProbe(self)
        self._probe.ready.connect(self._on_engine_ready)
        self._probe.failed.connect(self._on_engine_failed)
        self._probe.start()

    def _on_engine_ready(self, engine: InferenceEngine, gpu: GpuInfo) -> None:
        self._engine, self._gpu = engine, gpu
        if gpu.available:
            self.gpu_banner.setStyleSheet("background:#dafbe1;color:#1a7f37;padding:6px;border:1px solid #4ac26b;")
            self.gpu_banner.setText(f"GPU：{gpu.name}（{gpu.total_mb} MB）")
        else:
            self.gpu_banner.setStyleSheet("background:#ffebe9;color:#cf222e;padding:6px;border:1px solid #ff8182;")
            self.gpu_banner.setText(f"⚠ {gpu.message}")
            self.device_combo.setCurrentIndex(self.device_combo.findData("cpu"))
            self.device_combo.model().item(0).setEnabled(False)  # 禁用 GPU 选项
        self._update_start_enabled()

    def _on_engine_failed(self, msg: str) -> None:
        self.gpu_banner.setStyleSheet("background:#ffebe9;color:#cf222e;padding:6px;border:1px solid #ff8182;")
        self.gpu_banner.setText(f"⚠ 推理环境初始化失败：{msg}")

    # ------------------------------------------------------------- 路径选择 ----
    def _pick_input_dir(self) -> None:
        start = self._inputs[0] if self._inputs else ""
        chosen = QFileDialog.getExistingDirectory(self, "选择输入目录", start)
        if chosen:
            self._inputs = [chosen]
            self._refresh_input_label()

    def _pick_input_files(self) -> None:
        exts = " ".join(f"*{e} *{e.upper()}" for e in paths.SUPPORTED_IMAGE_EXTS)
        files, _ = QFileDialog.getOpenFileNames(self, "选择图像文件", "", f"图像 ({exts});;所有文件 (*)")
        if files:
            self._inputs = files
            self._refresh_input_label()

    def _pick_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text())
        if chosen:
            self.output_edit.setText(chosen)

    def _refresh_input_label(self) -> None:
        if not self._inputs:
            self.input_edit.setText("")
            self.input_info.setText("")
        else:
            self.input_edit.setText(self._inputs[0] if len(self._inputs) == 1 else f"已选择 {len(self._inputs)} 个文件")
            count = len(collect_inputs([Path(p) for p in self._inputs], self.recursive_cb.isChecked()))
            self.input_info.setText(f"共 {count} 张可处理图像")
        self._update_start_enabled()

    def _update_start_enabled(self) -> None:
        busy = self._worker is not None and self._worker.isRunning()
        self.btn_start.setEnabled(self._engine is not None and bool(self._inputs) and not busy)

    def _pick_info_table(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择《影像信息表》", self.info_table_edit.text(),
                                              "影像信息表 (*.xlsx *.xls *.csv *.json);;所有文件 (*)")
        if path:
            self.info_table_edit.setText(path)

    def _on_competition_toggled(self, on: bool) -> None:
        running = self._worker is not None and self._worker.isRunning()
        for w in self._comp_widgets:
            w.setEnabled(on and not running)

    def _competition_inputs(self, s: UiSettings) -> bool:
        """校验影像信息表与默认规格；有问题时弹窗提示并返回 False。"""
        from competition import info_table, parse_spec

        rows = []
        if s.competition_info_table:
            try:
                rows = info_table.load_info_table(s.competition_info_table)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "影像信息表", f"读取失败：{exc}")
                return False
        if not s.competition_default_spec and not rows:
            QMessageBox.warning(self, "竞赛评定", "请选择《影像信息表》，或填写默认规格")
            return False
        bad = info_table.validate(rows)
        if s.competition_default_spec:
            try:
                parse_spec(s.competition_default_spec)
            except ValueError:
                bad.insert(0, f"默认规格: {s.competition_default_spec}")
        if bad:
            QMessageBox.warning(self, "竞赛评定", "以下规格无法解析：\n" + "\n".join(bad[:20]))
            return False
        self._append_log(f"[竞赛] 影像信息表 {len(rows)} 行")
        return True

    def _edit_models(self) -> None:
        dlg = ModelDialog(self._models, self)
        if dlg.exec():
            self._models = dlg.result_paths()

    def _open_output(self) -> None:
        if self._last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_output))

    # ------------------------------------------------------------- 运行 --------
    def _start(self) -> None:
        out = self.output_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "提示", "请先选择输出目录")
            return
        if not collect_inputs([Path(p) for p in self._inputs], self.recursive_cb.isChecked()):
            QMessageBox.warning(self, "提示", "所选输入中没有支持的图像文件")
            return
        s = self._collect_settings()
        if s.enable_competition and not self._competition_inputs(s):
            return
        cfg = RunConfig(
            inputs=s.inputs, output_dir=out, recursive=s.recursive, mode=s.mode, device=s.device,
            primary_conf=s.primary_conf, wide_slice=s.wide_slice, enable_correction=s.enable_correction,
            enable_location=s.enable_location, location_conf=s.location_conf,
            enable_location2=s.enable_location2, location2_conf=s.location2_conf,
            enable_iqi=s.enable_iqi, save_annotated=s.save_annotated, models=self._models.to_dict(),
            enable_competition=s.enable_competition, competition_default_spec=s.competition_default_spec,
            competition_info_table=s.competition_info_table, competition_fast=s.competition_fast,
            competition_deadline_min=s.competition_deadline_min,
            competition_strict_pipe_table26=s.competition_strict_pipe_table26,
            competition_split_pores=s.competition_split_pores, competition_merge_gap_mm=s.competition_merge_gap_mm,
            competition_intermittent_length=s.competition_intermittent_length,
            competition_plate_root="report" if s.competition_report_plate_root else "drop",
        )
        missing = [k for k in ("roi_weights", "primary_weights") if not Path(self._models.to_dict()[k]).exists()]
        if missing:
            QMessageBox.warning(self, "模型缺失", "必需的模型文件不存在，请在「模型设置」中指定：\n" + "\n".join(
                self._models.to_dict()[k] for k in missing))
            return

        self._settings = s
        s.save()
        self.table.setRowCount(0)
        self._outcomes.clear()
        self.viewer.set_image(None)
        self.log_view.clear()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._started_at = time.time()
        self._infer_started_at = 0.0
        self._done = self._total = 0
        self._last_done_at = 0.0
        self._timing_cfg = cfg
        self.timing_label.setStyleSheet("")
        self._timing_timer.start()
        self._update_timing()

        self._worker = InferenceWorker(self._engine, cfg, self)
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.outcome.connect(self._on_outcome)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._set_running(True)
        self._worker.start()

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.btn_stop.setEnabled(False)
            self.status_label.setText("正在停止（当前图像处理完成后）…")

    def _set_running(self, running: bool) -> None:
        self.btn_stop.setEnabled(running)
        for w in (self.mode_combo, self.device_combo, self.conf_spin, self.wide_cb, self.corr_cb, self.loc_cb,
                  self.loc_spin, self.loc2_cb, self.loc2_spin, self.iqi_cb, self.annot_cb, self.recursive_cb,
                  self.output_edit, self.comp_cb):
            w.setEnabled(not running)
        for w in self._comp_widgets:
            w.setEnabled(not running and self.comp_cb.isChecked())
        self._update_start_enabled()
        if running:
            self.btn_start.setEnabled(False)

    # ------------------------------------------------------------- 信号处理 ----
    def _append_log(self, line: str) -> None:
        if "it/s]" in line or "s/it]" in line:  # tqdm 进度条刷屏，进度已由进度条展示
            return
        self.log_view.appendPlainText(line)

    def _on_progress(self, current: int, total: int, file: str, stage: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)
        text = STAGE_TEXT.get(stage, stage)
        self.status_label.setText(f"{text} {file}".strip())
        if stage == "running":
            if not self._infer_started_at:
                self._infer_started_at = time.time()
            changed = current > self._done
            if changed:
                self._last_done_at = time.time()
            self._done, self._total = current, total
            if changed:
                self._update_timing()

    def _update_timing(self) -> None:
        now = time.time()
        infer = self._last_done_at - self._infer_started_at if self._last_done_at else 0.0
        deadline = self._timing_cfg.competition_deadline_min if (
            self._timing_cfg and self._timing_cfg.enable_competition) else 0.0
        text, risk = timing_text(now - self._started_at, self._last_done_at - self._started_at, infer,
                                 self._done, self._total, deadline)
        self.timing_label.setText(text)
        self.timing_label.setStyleSheet("color:#c00;font-weight:bold;" if risk else "")

    def _on_outcome(self, o: ImageOutcome) -> None:
        self._outcomes[o.index] = o
        row = self.table.rowCount()
        self.table.insertRow(row)
        if o.ok:
            r = o.result or {}
            ocr = r.get("ocr") or {}
            iqi = " / ".join(str(v) for v in (ocr.get("plate_code"), ocr.get("grade")) if v is not None) or "—"
            cells = [o.rel_path, str(defect_count(r)), "✓" if r.get("weld_location") else "—", iqi,
                     *competition_cells(o.competition), "成功"]
        else:
            cells = [o.rel_path, "—", "—", "—", "—", "—", f"失败：{o.error}"]
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, o.index)
            if not o.ok:
                item.setForeground(Qt.GlobalColor.red)
            if col == COLUMNS.index("评定结果"):
                item.setToolTip("\n".join(text.split("；")))
            self.table.setItem(row, col, item)
        if row == 0:
            self.table.selectRow(0)

    def _on_row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        o = self._outcomes.get(index)
        if o is None or not o.ok:
            self.viewer.set_image(None)
            return
        try:
            from utils import cv_io

            image = None
            if o.annotated_path:
                image = cv_io.imread(o.annotated_path)
            if image is None:
                from .. import render

                image = render.render_annotated(o.result)
            self.viewer.set_image(image)
        except Exception as exc:
            self._append_log(f"[警告] 预览失败: {exc}")

    def _on_done(self, s: RunSummary) -> None:
        from competition.exporter import time_score

        self._timing_timer.stop()
        self._set_running(False)
        self._last_output = s.output_dir
        self.btn_open_out.setEnabled(True)
        state = "已停止" if s.cancelled else "完成"
        self.status_label.setText(f"{state}：成功 {s.succeeded}，失败 {s.failed}，耗时 {s.elapsed_s:.1f}s")
        self._append_log(f"输出目录: {s.output_dir}")
        if s.answers_path:
            # 规则：答案导出时间不计；s.elapsed_s 在导出前截取
            score = time_score(s.elapsed_s)
            timing = f"用时 {fmt_duration(s.elapsed_s)}（{s.elapsed_s / 60:.1f} 分钟），时间分 B={score:.2f}"
            self.timing_label.setText(timing)
            self.timing_label.setStyleSheet("color:#c00;font-weight:bold;" if score == 0 else "")
            extra = f"，其中 {s.timed_out} 幅超时兜底" if s.timed_out else ""
            self._append_log(f"竞赛答案: {s.answers_path}{extra}；{timing}")
            QMessageBox.information(self, "竞赛答案", f"答案已导出：\n{s.answers_path}{extra}\n\n{timing}")
        else:
            self.timing_label.setText(f"用时 {fmt_duration(s.elapsed_s)}")

    def _on_failed(self, msg: str) -> None:
        self._timing_timer.stop()
        self._set_running(False)
        self.status_label.setText("运行失败")
        self._append_log(msg)
        QMessageBox.critical(self, "运行失败", msg)

    # ------------------------------------------------------------- 退出 --------
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            if QMessageBox.question(self, "确认", "推理仍在进行，确定退出吗？") != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._worker.wait(30000)
        self._collect_settings().save()
        if self._engine is not None:
            self._engine.close()
        event.accept()
