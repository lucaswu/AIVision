"""模型设置：逐项显示/浏览替换模型文件，并标注是否存在。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from .. import paths

LABELS = {
    "roi_weights": ("ROI 检测模型", False),
    "primary_weights": ("主检测模型 (RF-DETR)", False),
    "correction_model": ("方向矫正模型", False),
    "location_model": ("焊缝位置检测模型", False),
    "location2_model": ("缺陷位置检测模型", False),
    "gauge_weights": ("像质计 OBB 模型", False),
    "fclip_ckpt": ("像质丝计数模型 (FClip)", False),
    "fclip_config": ("FClip 配置 (yaml)", False),
    "fclip_params": ("FClip 参数 (yaml)", False),
    "ocr_det_model_dir": ("OCR 检测模型目录", True),
    "ocr_rec_model_dir": ("OCR 识别模型目录", True),
    "ocr_orientation_model": ("OCR 方向矫正模型", False),
}


class ModelDialog(QDialog):
    def __init__(self, current: paths.ModelPaths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模型设置")
        self.resize(820, 460)
        self._edits: Dict[str, QLineEdit] = {}
        self._marks: Dict[str, QLabel] = {}

        grid = QGridLayout()
        for row, (key, (title, is_dir)) in enumerate(LABELS.items()):
            grid.addWidget(QLabel(title), row, 0)
            edit = QLineEdit(getattr(current, key))
            edit.textChanged.connect(lambda _=None, k=key: self._refresh(k))
            self._edits[key] = edit
            grid.addWidget(edit, row, 1)
            mark = QLabel()
            mark.setFixedWidth(60)
            self._marks[key] = mark
            grid.addWidget(mark, row, 2)
            btn = QPushButton("浏览…")
            btn.clicked.connect(lambda _=False, k=key, d=is_dir: self._browse(k, d))
            grid.addWidget(btn, row, 3)
            self._refresh(key)
        grid.setColumnStretch(1, 1)

        reset = QPushButton("恢复默认")
        reset.clicked.connect(self._reset)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(reset)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addStretch(1)
        layout.addLayout(bottom)

    def _refresh(self, key: str) -> None:
        ok = Path(self._edits[key].text()).exists()
        self._marks[key].setText("✓ 存在" if ok else "✗ 缺失")
        self._marks[key].setStyleSheet("color: #1a7f37;" if ok else "color: #cf222e;")

    def _browse(self, key: str, is_dir: bool) -> None:
        start = self._edits[key].text()
        if is_dir:
            chosen = QFileDialog.getExistingDirectory(self, "选择目录", start)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "选择文件", start)
        if chosen:
            self._edits[key].setText(chosen)

    def _reset(self) -> None:
        defaults = paths.ModelPaths.defaults().to_dict()
        for key, edit in self._edits.items():
            edit.setText(defaults[key])

    def result_paths(self) -> paths.ModelPaths:
        return paths.ModelPaths(**{k: e.text().strip() for k, e in self._edits.items()})
