"""Qt 线程封装：把阻塞的推理放到后台线程，通过信号回到界面。"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from .engine import GpuInfo, ImageOutcome, InferenceEngine, RunConfig, RunSummary


class EngineProbe(QThread):
    """后台创建引擎并检测 GPU（首次 import torch 较慢，不阻塞界面）。"""

    ready = pyqtSignal(object, object)  # engine, GpuInfo
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            engine = InferenceEngine()
            self.ready.emit(engine, engine.gpu)
        except Exception as exc:  # pragma: no cover - 环境问题
            self.failed.emit(str(exc))


class InferenceWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int, str, str)  # current, total, file, stage
    outcome = pyqtSignal(object)               # ImageOutcome
    done = pyqtSignal(object)                  # RunSummary
    failed = pyqtSignal(str)

    def __init__(self, engine: InferenceEngine, cfg: RunConfig, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._cfg = cfg
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        self._engine.set_log(self.log.emit)
        try:
            summary: RunSummary = self._engine.run(
                self._cfg,
                on_progress=self.progress.emit,
                on_result=lambda o: self.outcome.emit(o),
                should_cancel=self._cancel.is_set,
            )
            self.done.emit(summary)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
