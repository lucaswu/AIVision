from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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

    def _fmt_item(r: Dict) -> str:
        dtype = r.get("defect_type", "")
        qty = r.get("quantity", "")
        x_val = r.get("x_mm")
        if x_val is not None:
            try:
                val = float(x_val)
                x_str = str(int(val)) if val.is_integer() else f"{val:.2f}".rstrip("0").rstrip(".")
                x_part = f" X={x_str}mm"
            except (ValueError, TypeError):
                x_part = f" X={x_val}mm"
        elif r.get("x_px") is not None:
            x_part = f" X={r['x_px']}px"
        else:
            x_part = ""
        return f"{dtype}{x_part} {qty}".strip()

    records = "；".join(_fmt_item(r) for r in ev.get("records") or [])
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

        # 参数（三列水平排布，全部参数在界面直观展开，无需滚动滑条）
        param_box = QGroupBox("参数")
        param_layout = QHBoxLayout(param_box)
        param_layout.setContentsMargins(12, 8, 12, 8)
        param_layout.setSpacing(16)

        # 第 1 列：基础检测与模型设置
        col1 = QWidget()
        pf1 = QFormLayout(col1)
        pf1.setContentsMargins(0, 0, 0, 0)
        pf1.setSpacing(6)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("检测 (det)", "det")
        self.mode_combo.addItem("分割 (seg)", "seg")
        self.device_combo = QComboBox()
        self.device_combo.addItem("GPU (cuda:0)", "cuda:0")
        self.device_combo.addItem("CPU", "cpu")
        self.conf_spin = self._spin(0.01, 0.99, 0.15)
        self.wide_cb = QCheckBox("横切纵拼推理")
        self.corr_cb = QCheckBox("方向矫正（weld_orientation_model）")
        self.corr_cb.setToolTip("默认不勾选（不做 weld_orientation_model.pth 旋转矫正以节省时间）；勾选后对底片执行自动方向校准")
        self.loc_cb = QCheckBox("焊缝位置检测")
        self.loc_spin = self._spin(0.01, 0.99, 0.6)
        self.loc2_cb = QCheckBox("缺陷位置检测")
        self.loc2_spin = self._spin(0.01, 0.99, 0.25)
        self.iqi_cb = QCheckBox("IQI 像质计识别")
        self.annot_cb = QCheckBox("保存标注图")
        pf1.addRow("模式", self.mode_combo)
        pf1.addRow("设备", self.device_combo)
        pf1.addRow("主模型置信度", self.conf_spin)
        pf1.addRow(self.wide_cb)
        pf1.addRow(self.corr_cb)
        pf1.addRow(self.loc_cb, self.loc_spin)
        pf1.addRow(self.loc2_cb, self.loc2_spin)
        pf1.addRow(self.iqi_cb)
        pf1.addRow(self.annot_cb)
        btn_models = QPushButton("模型设置…")
        btn_models.clicked.connect(self._edit_models)
        pf1.addRow(btn_models)

        # 第 2 列：竞赛评定与标准规则
        col2 = QWidget()
        pf2 = QFormLayout(col2)
        pf2.setContentsMargins(0, 0, 0, 0)
        pf2.setSpacing(6)
        self.comp_cb = QCheckBox("竞赛评定（NB/T 47013.2）")
        self.comp_cb.setToolTip("对每张图输出缺陷定位 X、定性、定量与评定等级，写入 competition_results.json")
        self.man_machine_cb = QCheckBox("人机大战赛项（自动推断工艺）")
        self.man_machine_cb.setToolTip(
            "勾选：参加【人机大战】赛项，系统将根据规格自动推断焊缝形式、焊接方法、施焊位置；\n"
            "未勾选（默认）：参加【缺陷识别】赛项，工艺三属性按规定不考核，提交时填 -1（答案表留空）。"
        )
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
        self.fast_cb.setToolTip("关闭 IQI/OCR、焊缝位置检测与灰度值计算，并默认取消保存标注图以最大化大批量推理速度")
        self.fast_cb.toggled.connect(self._on_fast_toggled)
        self.deadline_spin = QDoubleSpinBox()
        self.deadline_spin.setRange(0, 600)
        self.deadline_spin.setDecimals(1)
        self.deadline_spin.setSuffix(" 分钟")
        self.deadline_spin.setSpecialValueText("不限")
        self.deadline_spin.setToolTip("到时仍未处理的影像按无缺陷兜底并导出答案（缺陷识别超时整项 0 分）")
        self.table26_cb = QCheckBox("大中径管根部缺陷严格按表 26 分级")
        self.table26_cb.setToolTip("默认按竞赛规则（9）：超 Ⅲ 级限值判 Ⅳ，其余判 Ⅱ。\n"
                                   "勾选后外径 > 100mm 的管道：任意 3T 内累计 ≤ T 为 Ⅱ 级，总长 ≤ 100mm 为 Ⅲ 级")
        self.plate_root_cb = QCheckBox("板焊缝上的根部内凹/咬边也填报")
        self.plate_root_cb.setToolTip("默认不填报：第 6 章（板）不对根部内凹/咬边分级，且模型在板上常有贯穿整条焊缝的误检。\n"
                                      "组委会要求板上也必须填报时勾选")
        pf2.addRow(self.comp_cb)
        pf2.addRow(self.man_machine_cb)
        pf2.addRow("影像信息表", row_info)
        pf2.addRow("默认规格", self.spec_edit)
        pf2.addRow("截止时间", self.deadline_spin)
        pf2.addRow(self.fast_cb)
        pf2.addRow(self.table26_cb)
        pf2.addRow(self.plate_root_cb)

        # 第 3 列：后处理与远洋提交
        col3 = QWidget()
        pf3 = QFormLayout(col3)
        pf3.setContentsMargins(0, 0, 0, 0)
        pf3.setSpacing(6)
        self.split_cb = QCheckBox("气孔框内精细拆分（实验）")
        self.split_cb.setToolTip("在原始高位图上把密集气孔大框拆回逐个气孔、按真实轮廓量长径。\n"
                                 "需用真实底片验证后再用于比赛")
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
        self.student_name_edit = QLineEdit("13858120789")
        self.student_name_edit.setReadOnly(True)
        self.student_name_edit.setToolTip("学员姓名（已固定：13858120789，不可编辑）")
        self.student_pwd_edit = QLineEdit("13858120789")
        self.student_pwd_edit.setReadOnly(True)
        self.student_pwd_edit.setToolTip("考核号（已固定：13858120789，不可编辑）")
        self.changci_edit = QLineEdit("122")
        self.changci_edit.setReadOnly(True)
        self.changci_edit.setToolTip("场次号（已固定：122，不可编辑）")
        row_student = QHBoxLayout()
        row_student.addWidget(self.student_name_edit, 1)
        row_student.addWidget(self.student_pwd_edit, 1)
        self.submit_online_cb = QCheckBox("推理后自动在线提交")
        self.submit_online_cb.setToolTip("推理与导出完成后，自动 POST 提交至远洋评分服务器 (http://www.farain.com:3030/testing/ai/ray/submit)")
        btn_manual_submit = QPushButton("远洋系统在线提交…")
        btn_manual_submit.setToolTip("选择已有的 submission_farain.json 提交至远洋评分系统")
        btn_manual_submit.clicked.connect(self._manual_submit_farain)
        pf3.addRow(self.split_cb)
        pf3.addRow("断续合并", row_merge)
        pf3.addRow("学员/考核号", row_student)
        pf3.addRow("场次号", self.changci_edit)
        pf3.addRow(self.submit_online_cb)
        pf3.addRow(btn_manual_submit)

        param_layout.addWidget(col1, 1)
        param_layout.addWidget(col2, 1)
        param_layout.addWidget(col3, 1)

        self._comp_widgets = (self.man_machine_cb, self.spec_edit, self.info_table_edit, btn_info, btn_info_clear, self.fast_cb,
                              self.deadline_spin, self.table26_cb, self.split_cb, self.plate_root_cb,
                              self.merge_gap_spin, self.merge_len_combo,
                              self.student_name_edit, self.student_pwd_edit, self.changci_edit,
                              self.submit_online_cb, btn_manual_submit)
        self.comp_cb.toggled.connect(self._on_competition_toggled)

        # 结果表 + 预览（内部保留对象用于数据管理与测试兼容，界面隐藏不显示）
        self.table = QTableWidget(0, len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 65)
        self.table.setColumnWidth(4, 75)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(6, 65)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.hide()

        self.viewer = ImageViewer(self)
        self.viewer.hide()

        self._split = QSplitter(Qt.Orientation.Vertical, self)
        self._split.addWidget(self.table)
        self._split.addWidget(self.viewer)
        self._split.hide()

        # 总体评定结果看板（与参数形成上下排布，位于参数下方，独占拉伸）
        self.summary_box = QGroupBox("总体评定结果")
        summary_vbox = QVBoxLayout(self.summary_box)
        summary_vbox.setContentsMargins(12, 10, 12, 10)
        summary_vbox.setSpacing(6)
        self.summary_detail_label = QLabel()
        self.summary_detail_label.setWordWrap(True)
        self.summary_detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_vbox.addWidget(self.summary_detail_label, 1)
        self._reset_summary_box()

        # 上下垂直布局：上方参数面板，下方总体评定结果看板
        outer.addWidget(param_box)
        outer.addWidget(self.summary_box, 1)

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
        report_plate = getattr(s, "competition_report_plate_root", False) or getattr(s, "competition_plate_root", "drop") == "report"
        self.plate_root_cb.setChecked(bool(report_plate))
        self.merge_gap_spin.setValue(s.competition_merge_gap_mm)
        self.merge_len_combo.setCurrentIndex(max(0, self.merge_len_combo.findData(s.competition_intermittent_length)))
        self.deadline_spin.setValue(s.competition_deadline_min)
        # 固定显示姓名、考核号、场次号，只读不可编辑
        self.student_name_edit.setText("13858120789")
        self.student_name_edit.setReadOnly(True)
        self.student_pwd_edit.setText("13858120789")
        self.student_pwd_edit.setReadOnly(True)
        self.changci_edit.setText("122")
        self.changci_edit.setReadOnly(True)
        self.submit_online_cb.setChecked(s.submit_farain_online)
        self.comp_cb.setChecked(s.enable_competition)
        self.man_machine_cb.setChecked(s.competition_man_machine)
        self._on_competition_toggled(s.enable_competition)
        self._refresh_input_label()

    def _collect_settings(self) -> UiSettings:
        defaults = paths.ModelPaths.defaults().to_dict()
        overrides = {k: v for k, v in self._models.to_dict().items() if v != defaults.get(k)}
        report_plate = self.plate_root_cb.isChecked()
        return UiSettings(
            inputs=self._inputs, output_dir=self.output_edit.text().strip(),
            recursive=self.recursive_cb.isChecked(), mode=self.mode_combo.currentData(),
            device=self.device_combo.currentData(), primary_conf=self.conf_spin.value(),
            wide_slice=self.wide_cb.isChecked(),
            enable_correction=self.corr_cb.isChecked(),
            enable_location=self.loc_cb.isChecked(), location_conf=self.loc_spin.value(),
            enable_location2=self.loc2_cb.isChecked(), location2_conf=self.loc2_spin.value(),
            enable_iqi=self.iqi_cb.isChecked(), save_annotated=self.annot_cb.isChecked(),
            enable_competition=self.comp_cb.isChecked(),
            competition_man_machine=self.man_machine_cb.isChecked(),
            competition_default_spec=self.spec_edit.text().strip(),
            competition_info_table=self.info_table_edit.text().strip(),
            competition_fast=self.fast_cb.isChecked(), competition_deadline_min=self.deadline_spin.value(),
            competition_strict_pipe_table26=self.table26_cb.isChecked(),
            competition_split_pores=self.split_cb.isChecked(),
            competition_report_plate_root=report_plate,
            competition_plate_root="report" if report_plate else "drop",
            competition_round_scale=getattr(self._settings, "competition_round_scale", 0.42),
            competition_small_pipe_arc_expand=getattr(self._settings, "competition_small_pipe_arc_expand", True),
            competition_merge_gap_mm=self.merge_gap_spin.value(),
            competition_intermittent_length=self.merge_len_combo.currentData(),
            student_name="13858120789",
            student_password="13858120789",
            changci="122",
            submit_farain_online=self.submit_online_cb.isChecked(),
            models=overrides,
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
        # 固定姓名、考核号和场次号只读显示，不可编辑
        self.student_name_edit.setReadOnly(True)
        self.student_pwd_edit.setReadOnly(True)
        self.changci_edit.setReadOnly(True)
        self.corr_cb.setEnabled(not running)
        if on and self.fast_cb.isChecked():
            self.annot_cb.setChecked(False)

    def _on_fast_toggled(self, on: bool) -> None:
        if on and self.comp_cb.isChecked():
            self.annot_cb.setChecked(False)

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
            primary_conf=s.primary_conf, wide_slice=s.wide_slice,
            enable_correction=s.enable_correction,
            enable_location=s.enable_location, location_conf=s.location_conf,
            enable_location2=s.enable_location2, location2_conf=s.location2_conf,
            enable_iqi=s.enable_iqi, save_annotated=s.save_annotated, models=self._models.to_dict(),
            enable_competition=s.enable_competition,
            competition_man_machine=s.competition_man_machine,
            competition_default_spec=s.competition_default_spec,
            competition_info_table=s.competition_info_table, competition_fast=s.competition_fast,
            competition_deadline_min=s.competition_deadline_min,
            competition_strict_pipe_table26=s.competition_strict_pipe_table26,
            competition_split_pores=s.competition_split_pores, competition_merge_gap_mm=s.competition_merge_gap_mm,
            competition_intermittent_length=s.competition_intermittent_length,
            competition_plate_root="report" if (getattr(s, "competition_report_plate_root", False) or getattr(s, "competition_plate_root", "drop") == "report") else "drop",
            competition_round_scale=getattr(s, "competition_round_scale", 0.42),
            competition_small_pipe_arc_expand=getattr(s, "competition_small_pipe_arc_expand", True),
            student_name=s.student_name, student_password=s.student_password, changci=s.changci,
            submit_farain_online=s.submit_farain_online, submit_farain_url=s.submit_farain_url,
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
        self._reset_summary_box()
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

    def _reset_summary_box(self) -> None:
        self.summary_box.setTitle("总体评定结果（全目录汇总）")
        self.summary_box.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #d0d7de; border-radius: 8px; margin-top: 4px; padding: 6px; background-color: #f6f8fa; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #24292f; font-size: 13px; }"
        )
        self.summary_detail_label.setText(
            "<table width='100%' cellpadding='8' cellspacing='8' style='border-collapse:separate;'>"
            "<tr>"
            "<td width='34%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            "<h4 style='color:#24292f; margin:0 0 6px 0;'>📋 状态：就绪</h4>"
            "<p style='color:#57606a; margin:0; line-height:160%; font-size:12px;'>请在上方确认各栏参数，点击下方<b>「开始」</b>按钮启动全目录批量推理。</p>"
            "</td>"
            "<td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            "<h4 style='color:#24292f; margin:0 0 6px 0;'>⚡ 竞赛评定流水线</h4>"
            "<p style='color:#57606a; margin:0; line-height:160%; font-size:12px;'>模型检测 ➔ 竞赛评定（定性/定量/定级） ➔ 答案表导出 ➔ <b>远洋系统在线提交评分</b>。</p>"
            "</td>"
            "<td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            "<h4 style='color:#24292f; margin:0 0 6px 0;'>📊 结果看板</h4>"
            "<p style='color:#57606a; margin:0; line-height:160%; font-size:12px;'>全目录推理完成后，此处将横向呈现等级分布、缺陷汇总及远洋系统得分。</p>"
            "</td>"
            "</tr>"
            "</table>"
        )

    def _update_running_summary(self) -> None:
        total = self._total or len(self._inputs)
        done = len(self._outcomes)
        if total == 0:
            return
        pct = (done / total) * 100
        grades = {"Ⅰ级": 0, "Ⅱ级": 0, "Ⅲ级": 0, "Ⅳ级": 0}
        defects = 0
        for o in self._outcomes.values():
            if o.ok and o.competition:
                g = o.competition.get("grade_label")
                if g in grades:
                    grades[g] += 1
                defects += len(o.competition.get("records") or [])
        text = (
            "<table width='100%' cellpadding='8' cellspacing='8' style='border-collapse:separate;'>"
            "<tr>"
            "<td width='34%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            f"<h4 style='color:#0969da; margin:0 0 6px 0;'>⏳ 正在推理：已完成 {done} / {total} 幅（{pct:.1f}%）</h4>"
            "<p style='color:#57606a; margin:0; font-size:12px;'>正在批量处理中，请稍候…</p>"
            "</td>"
            "<td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            "<div style='font-weight:bold; margin-bottom:6px;'>当前等级分布：</div>"
            f"<span style='color:#1a7f37;font-weight:bold;'>Ⅰ级: {grades['Ⅰ级']}</span>&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<span style='color:#0969da;font-weight:bold;'>Ⅱ级: {grades['Ⅱ级']}</span>&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<span style='color:#d97706;font-weight:bold;'>Ⅲ级: {grades['Ⅲ级']}</span>&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<span style='color:#cf222e;font-weight:bold;'>Ⅳ级: {grades['Ⅳ级']}</span>"
            "</td>"
            "<td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>"
            "<div style='font-weight:bold; margin-bottom:6px;'>检出缺陷统计：</div>"
            f"<div style='font-size:13px;'>已检出 <b>{defects}</b> 处缺陷</div>"
            "</td>"
            "</tr>"
            "</table>"
        )
        self.summary_box.setTitle(f"总体评定结果（推理中: {done}/{total}）")
        self.summary_detail_label.setText(text)

    def _update_completed_summary(self, s: RunSummary) -> None:
        from competition.exporter import time_score

        grades = {"Ⅰ级": 0, "Ⅱ级": 0, "Ⅲ级": 0, "Ⅳ级": 0}
        defect_counts: Dict[str, int] = {}
        total_defects = 0
        for o in self._outcomes.values():
            if o.ok and o.competition:
                g = o.competition.get("grade_label")
                if g in grades:
                    grades[g] += 1
                for rec in o.competition.get("records") or []:
                    dtype = rec.get("defect_type") or "未知缺陷"
                    defect_counts[dtype] = defect_counts.get(dtype, 0) + 1
                    total_defects += 1

        qual_count = grades["Ⅰ级"] + grades["Ⅱ级"]
        qual_rate = (qual_count / s.succeeded * 100) if s.succeeded > 0 else 0.0
        score = time_score(s.elapsed_s) if s.answers_path else None
        avg_s = (s.elapsed_s / s.total) if s.total > 0 else 0.0

        defect_parts = [f"{k}: <b>{v}</b>" for k, v in sorted(defect_counts.items(), key=lambda x: -x[1])]
        defect_str = "，".join(defect_parts) if defect_parts else "无缺陷"

        farain_part = ""
        if s.submit_response:
            if s.submit_response.get("success"):
                mark = None
                resp_data = s.submit_response.get("data")
                if isinstance(resp_data, dict):
                    mark = resp_data.get("mark")
                    if mark is None:
                        mark = resp_data.get("score")
                elif isinstance(resp_data, (int, float, str)) and resp_data != "":
                    mark = resp_data

                if mark is not None:
                    farain_part = (
                        f"<b>远洋系统在线评分：</b>"
                        f"<span style='color:#1a7f37;font-weight:bold;'>已成功（系统评分：<span style='font-size:15px;color:#1a7f37;'>{mark}</span> 分）</span>"
                    )
                else:
                    farain_part = (
                        f"<b>远洋系统在线评分：</b>"
                        f"<span style='color:#1a7f37;font-weight:bold;'>已成功（服务端已接收提交，当前无回传分值）</span>"
                    )
            else:
                err = s.submit_response.get('error_msg') or '未知错误'
                farain_part = f"<b>远洋系统在线评分：</b><span style='color:#cf222e;font-weight:bold;'>提交失败：{err}</span>"
        elif s.submission_json_path:
            farain_part = f"<b>远洋系统在线评分：</b><span style='color:#0969da;'>已生成远洋JSON (未勾选在线提交)</span>"
        else:
            farain_part = f"<b>远洋系统在线评分：</b><span style='color:#57606a;'>未生成提交文件</span>"

        time_part = f"<b>竞赛时间分 B：</b><b style='color:#0969da;font-size:15px;'>{score:.2f}</b> / 10.00" if score is not None else ""

        answers_info = ""
        if s.answers_path:
            answers_info += f"<div><b>竞赛答案：</b><code>{Path(s.answers_path).name}</code></div>"
        if s.submission_json_path:
            answers_info += f"<div style='margin-top:2px;'><b>远洋JSON：</b><code>{Path(s.submission_json_path).name}</code>（断网可直接拷入 U 盘）</div>"

        html = f"""
        <table width='100%' cellpadding='8' cellspacing='8' style='border-collapse:separate;'>
            <tr>
                <td width='34%' valign='top' style='background:#ffffff; border:1px solid #b4e0be; border-radius:6px; padding:10px 12px;'>
                    <h4 style='color:#1a7f37; margin:0 0 6px 0; font-size:14px;'>🏆 全目录概况</h4>
                    <div><b>图像总量：</b>共 <b>{s.total}</b> 幅（成功 <span style='color:#1a7f37;font-weight:bold;'>{s.succeeded}</span>，失败 <span style='color:#cf222e;font-weight:bold;'>{s.failed}</span>）</div>
                    <div><b>总耗时：</b>{fmt_duration(s.elapsed_s)}（{s.elapsed_s:.1f}s，平均 {avg_s:.2f}s/幅）</div>
                    <div style='margin-top:4px; padding-top:4px; border-top:1px dashed #d0d7de;'>
                        {time_part}<br/>
                        {farain_part}
                    </div>
                </td>
                <td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>
                    <h4 style='color:#24292f; margin:0 0 6px 0; font-size:14px;'>📊 NB/T 47013.2 等级分布</h4>
                    <div style='font-size:13px; margin-bottom:6px;'>
                        <span style='color:#1a7f37;font-weight:bold;'>Ⅰ级: {grades['Ⅰ级']}</span> 幅 &nbsp;|&nbsp;
                        <span style='color:#0969da;font-weight:bold;'>Ⅱ级: {grades['Ⅱ级']}</span> 幅 &nbsp;|&nbsp;
                        <span style='color:#d97706;font-weight:bold;'>Ⅲ级: {grades['Ⅲ级']}</span> 幅 &nbsp;|&nbsp;
                        <span style='color:#cf222e;font-weight:bold;'>Ⅳ级: {grades['Ⅳ级']}</span> 幅
                    </div>
                    <div>
                        <b>综合合格率 (Ⅰ+Ⅱ级)：</b><span style='font-size:14px;font-weight:bold;color:#0969da;'>{qual_rate:.1f}%</span><br/>
                        （合格 <b>{qual_count}</b> 幅 / 不合格 <b>{grades['Ⅲ级'] + grades['Ⅳ级']}</b> 幅）
                    </div>
                </td>
                <td width='33%' valign='top' style='background:#ffffff; border:1px solid #d0d7de; border-radius:6px; padding:10px 12px;'>
                    <h4 style='color:#24292f; margin:0 0 6px 0; font-size:14px;'>🔍 缺陷分类检出汇总（共 {total_defects} 处）</h4>
                    <div style='font-size:12px; line-height:150%;'>{defect_str}</div>
                    <div style='margin-top:4px; padding-top:4px; border-top:1px dashed #d0d7de; font-size:11px; color:#57606a;'>
                        {answers_info}
                    </div>
                </td>
            </tr>
        </table>
        """
        self.summary_box.setTitle("总体评定结果（全目录推理完成）")
        self.summary_box.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 2px solid #2da44e; border-radius: 8px; margin-top: 4px; padding: 6px; background-color: #f0fdf4; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #1a7f37; font-size: 13px; }"
        )
        self.summary_detail_label.setText(html)

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
        self._update_running_summary()

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
        self._update_completed_summary(s)
        if s.answers_path:
            # 规则：答案导出时间不计；s.elapsed_s 在导出前截取
            score = time_score(s.elapsed_s)
            timing = f"用时 {fmt_duration(s.elapsed_s)}（{s.elapsed_s / 60:.1f} 分钟），时间分 B={score:.2f}"
            self.timing_label.setText(timing)
            self.timing_label.setStyleSheet("color:#c00;font-weight:bold;" if score == 0 else "")
            extra = f"，其中 {s.timed_out} 幅超时兜底" if s.timed_out else ""
            self._append_log(f"竞赛答案: {s.answers_path}{extra}；{timing}")
            if s.submission_json_path:
                self._append_log(f"远洋系统 JSON: {s.submission_json_path}")
            msg = f"答案已导出：\n{s.answers_path}{extra}\n\n{timing}"
            if s.submission_json_path:
                msg += f"\n\n远洋评分系统标准 JSON：\n{s.submission_json_path}\n（可直接拷贝至 U 盘交付）"
            if s.submit_response:
                if s.submit_response.get("success"):
                    mark = None
                    resp_data = s.submit_response.get("data")
                    if isinstance(resp_data, dict):
                        mark = resp_data.get("mark")
                        if mark is None:
                            mark = resp_data.get("score")
                    elif isinstance(resp_data, (int, float, str)) and resp_data != "":
                        mark = resp_data
                    mark_str = f"，系统评分：{mark} 分" if mark is not None else "（服务端已接收）"
                    msg += f"\n\n【远洋评分系统】在线提交成功 (code: 0){mark_str}！"
                else:
                    msg += f"\n\n【远洋评分系统】在线提交失败：{s.submit_response.get('error_msg')}"
            QMessageBox.information(self, "竞赛答案", msg)
        else:
            self.timing_label.setText(f"用时 {fmt_duration(s.elapsed_s)}")

    def _manual_submit_farain(self) -> None:
        """手动选择一个 submission_farain.json 并提交到远洋评分服务器。"""
        import json
        from competition.client import submit_to_server

        start = self._last_output or ""
        path, _ = QFileDialog.getOpenFileName(self, "选择要提交的远洋 JSON 文件", start, "JSON (*.json);;所有文件 (*)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", f"无法解析 JSON: {exc}")
            return
        s = self._collect_settings()
        url = s.submit_farain_url or "http://www.farain.com:3030/testing/ai/ray/submit"
        self._append_log(f"[手动提交] 正在提交 {path} 至 {url} ...")
        resp = submit_to_server(payload, url=url)
        if resp.success:
            mark = resp.data.get("mark") if isinstance(resp.data, dict) else None
            mark_str = f"，系统评分：{mark} 分" if mark is not None else ""
            self._append_log(f"[手动提交] 提交成功 (code: 0){mark_str}！")
            QMessageBox.information(self, "提交成功", f"远洋评分系统提交成功！{mark_str}\n文件: {path}")
        else:
            self._append_log(f"[手动提交失败] code: {resp.code}, 原因: {resp.error_msg}")
            QMessageBox.warning(self, "提交失败", f"远洋评分系统返回错误：\n{resp.error_msg}\n\n请检查姓名、考核号或场次号是否匹配。")

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
