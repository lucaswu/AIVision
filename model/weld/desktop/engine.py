"""桌面版推理引擎：不依赖 FastAPI，直接复用 run_inference_pipeline.InferencePipelineRunner。

逻辑对应 api_server.py 的 _build_runtime_args / _create_runtime_bundle /
_sync_run_inference_direct，差别是：路径可配置、逐张运行（可取消/可回调进度）、
同时可输出标注图。
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import paths
from .inputs import collect_inputs

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int, str, str], None]  # current, total, file, stage
ResultFn = Callable[["ImageOutcome"], None]
CancelFn = Callable[[], bool]


# ---------------------------------------------------------------- 配置/结果 ----

@dataclass
class RunConfig:
    inputs: List[str]                       # 文件或目录
    output_dir: str                         # 输出根目录（其下再建任务子目录）
    recursive: bool = True
    mode: str = "det"                       # det | seg
    device: str = "cuda:0"                  # cuda:0 | cpu
    primary_conf: float = 0.15
    wide_slice: bool = True
    enable_correction: bool = True
    enable_location: bool = True
    location_conf: float = 0.6
    enable_location2: bool = True
    location2_conf: float = 0.25
    enable_iqi: bool = True
    save_annotated: bool = True
    task_name: str = ""                     # 为空则用时间戳
    models: Dict[str, str] = field(default_factory=dict)  # ModelPaths 覆盖项
    # 竞赛评定（缺陷定位/定性/定量/NB/T 47013.2 评级），结果写 competition_results.json
    enable_competition: bool = False
    competition_default_spec: str = ""      # 所有影像共用的规格，如 "20" / "Φ89×6"
    competition_specs: Dict[str, str] = field(default_factory=dict)  # 文件名或编号 → 规格，优先于影像信息表
    competition_info_table: str = ""        # 《影像信息表》.xlsx/.xls/.csv/.json
    competition_fast: bool = True           # 竞赛提速：关闭 IQI/OCR、焊缝位置检测、灰度值，8bit 图不落盘
    competition_strict_pipe_table26: bool = False  # 大中径管根部缺陷严格按表 26 分 Ⅱ/Ⅲ/Ⅳ（默认按规则（9））
    competition_split_pores: bool = False   # 圆形缺陷框内精细拆分（需保留原始高位图，实验功能）
    competition_merge_gap_mm: float = 2.0   # 断续未熔合/未焊透/纵向裂纹：间隔 ≤ 该值合并为一个缺陷
    competition_intermittent_length: str = "envelope"  # envelope（含间隔）| sum（各段之和）
    competition_plate_root: str = "drop"    # 板焊缝上的根部内凹/咬边：drop（默认不填报）| report
    competition_deadline_min: float = 0.0   # >0：从开始计时到该分钟数仍未处理的影像按无缺陷兜底并导出


@dataclass
class ImageOutcome:
    index: int
    total: int
    image_path: str
    rel_path: str
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    annotated_path: Optional[str] = None
    competition: Optional[Dict[str, Any]] = None  # ImageEvaluation.to_dict()
    timed_out: bool = False                       # 竞赛截止时间已到，未推理


@dataclass
class RunSummary:
    output_dir: str
    total: int
    succeeded: int
    failed: int
    cancelled: bool
    elapsed_s: float
    answers_path: Optional[str] = None  # 竞赛答案 xlsx（或 csv）
    timed_out: int = 0


@dataclass
class GpuInfo:
    available: bool
    name: str = ""
    total_mb: int = 0
    message: str = ""


def detect_gpu() -> GpuInfo:
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return GpuInfo(True, props.name, int(props.total_memory // (1024 * 1024)))
        return GpuInfo(False, message="未检测到可用的 NVIDIA GPU（CUDA 不可用）。将使用 CPU 运行，速度会非常慢。")
    except Exception as exc:  # torch 未安装/损坏
        return GpuInfo(False, message=f"无法检测 GPU：{exc}")


# ---------------------------------------------------------------- 日志流 -------

class _LineSink:
    """把 print / tqdm 输出按行转发给回调（tqdm 用 \\r 刷新，一并视为换行）。"""

    def __init__(self, emit: Callable[[str], None]):
        self._emit = emit
        self._buf = ""

    def write(self, data: str) -> int:
        text = str(data)
        self._buf += text.replace("\r", "\n")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._emit(line)
        return len(text)

    def flush(self) -> None:
        if self._buf.strip():
            self._emit(self._buf)
        self._buf = ""

    def isatty(self) -> bool:
        return False


# ---------------------------------------------------------------- 引擎 ---------

class InferenceEngine:
    def __init__(self, log: Optional[LogFn] = None):
        # 默认写到进程原始 stdout：run() 会重定向 sys.stdout 到本引擎的日志流，
        # 若这里再 print 就会递归。
        real_stdout = sys.__stdout__
        self._log = log or (lambda s: (real_stdout.write(s + "\n"), real_stdout.flush()))
        self._rip = None
        self._bundle: Optional[Dict[str, Any]] = None
        self._signature: Optional[Tuple[Any, ...]] = None
        self._gpu = detect_gpu()

    # -- 基础 --
    @property
    def gpu(self) -> GpuInfo:
        return self._gpu

    def set_log(self, log: LogFn) -> None:
        self._log = log

    def log(self, msg: str) -> None:
        self._log(msg)

    def _load_pipeline_module(self):
        """按文件路径加载 run_inference_pipeline.py，避免与 IQIDDET 下同名文件冲突。"""
        if self._rip is not None:
            return self._rip
        # 桌面版默认不启用 TensorRT（Windows 下未验证）；可用环境变量显式打开
        os.environ.setdefault("INFERENCE_USE_TENSORRT", "false")
        os.environ.setdefault("TRT_ENGINE_CACHE_DIR", str(paths.engine_cache_dir()))

        root = str(paths.APP_DIR)
        while root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)

        module_name = "aivision_weld_run_inference_pipeline"
        spec = importlib.util.spec_from_file_location(module_name, paths.APP_DIR / "run_inference_pipeline.py")
        if spec is None or spec.loader is None:
            raise ImportError("无法加载 run_inference_pipeline.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self._rip = module
        return module

    # -- 参数构造 --
    def _build_args(self, cfg: RunConfig, output_dir: Path, file_list: Path) -> argparse.Namespace:
        models = paths.ModelPaths.from_dict(cfg.models)
        gpu = self._gpu.available
        device = cfg.device if gpu and cfg.device.startswith("cuda") else "cpu"
        if device != cfg.device:
            self.log(f"[引擎] 设备 {cfg.device} 不可用，改用 {device}")
        gauge_device = device
        exists = lambda p: bool(p) and os.path.exists(p)  # noqa: E731
        fast = cfg.enable_competition and cfg.competition_fast

        return argparse.Namespace(
            image_dir=None, file_list=str(file_list), output_dir=str(output_dir),
            results_json="inference_results.json", mode=cfg.mode, max_images=None,
            roi_weights=models.roi_weights, roi_conf=0.25, roi_iou=0.45, roi_padding=0.1,
            enhance_mode="windowing", font_path=None, font_size=20,
            primary_weights=models.primary_weights, fusion_iou=0.5, primary_conf=cfg.primary_conf,
            device=device, det_device=device, wide_slice=bool(cfg.wide_slice),
            enable_correction=bool(cfg.enable_correction and exists(models.correction_model)),
            correction_model=models.correction_model, correction_verbose=False, save_corrected_dir=None,
            enable_location=bool(cfg.enable_location and not fast and exists(models.location_model)),
            location_model=models.location_model, location_conf=cfg.location_conf,
            location_verbose=False, save_location_dir=None,
            enable_location2=bool(cfg.enable_location2 and not fast and exists(models.location2_model)),
            location2_model=models.location2_model, location2_conf=cfg.location2_conf,
            location2_verbose=False, save_location2_dir=None,
            enable_iqi=bool(cfg.enable_iqi and not fast), enable_density=not fast, iqi_results_json="iqi_grade_results.json",
            gauge_weights=models.gauge_weights, gauge_conf=0.25, gauge_iou=0.45, gauge_imgsz=640,
            gauge_device=gauge_device, gauge_select="conf",
            fclip_ckpt=models.fclip_ckpt, fclip_config=models.fclip_config,
            fclip_params=models.fclip_params, fclip_device=None,
            ocr_device="gpu" if device.startswith("cuda") else "cpu",
            ocr_det_model_name="PP-OCRv5_server_det", ocr_det_model_dir=models.ocr_det_model_dir,
            ocr_det_limit_side_len=960, ocr_det_limit_type="max",
            ocr_rec_model_name="en_PP-OCRv5_mobile_rec", ocr_rec_model_dir=models.ocr_rec_model_dir,
            enable_ocr_orientation=True, ocr_orientation_model=models.ocr_orientation_model,
            ocr_orientation_device=gauge_device, ocr_number_range="1-19",
        )

    @staticmethod
    def _signature_of(a: argparse.Namespace) -> Tuple[Any, ...]:
        keys = (
            "mode", "roi_weights", "primary_weights", "device", "det_device", "wide_slice",
            "enable_correction", "correction_model", "enable_location", "location_model",
            "enable_location2", "location2_model", "enable_iqi", "gauge_weights", "fclip_ckpt",
            "fclip_config", "fclip_params", "gauge_device", "ocr_device", "ocr_det_model_dir",
            "ocr_rec_model_dir", "ocr_orientation_model", "ocr_orientation_device",
        )
        floats = ("primary_conf", "location_conf", "location2_conf")
        return tuple(getattr(a, k) for k in keys) + tuple(round(float(getattr(a, k)), 6) for k in floats)

    # -- 模型 bundle（常驻复用）--
    def _ensure_bundle(self, args: argparse.Namespace) -> Dict[str, Any]:
        sig = self._signature_of(args)
        if self._bundle is not None and sig == self._signature:
            return self._bundle
        self._release_bundle()
        rip = self._load_pipeline_module()
        self.log("[引擎] 正在加载模型…")

        roi_detector = rip.build_roi_detector(args)
        if roi_detector is None:
            raise ValueError("必须提供 ROI 模型权重")
        font = rip.FontRenderer(font_path=args.font_path, font_size=args.font_size)
        corrector = (
            rip.WeldOrientationCorrector(model_path=args.correction_model, model_type="resnet50")
            if args.enable_correction else None
        )
        locator = (
            rip.WeldSeamLocator(model_path=str(Path(args.location_model)), conf_threshold=args.location_conf)
            if args.enable_location else None
        )
        detector = (
            rip.WeldDefectPositionDetector(model_path=str(Path(args.location2_model)),
                                           conf_threshold=args.location2_conf)
            if args.enable_location2 else None
        )
        iqi = None
        if args.enable_iqi:
            if not rip._IQI_AVAILABLE:
                self.log(f"[警告] IQIInferencer 不可用，跳过 IQI: {getattr(rip, '_IQI_IMPORT_ERROR', '')}")
            else:
                ab = lambda p: str(Path(p).resolve()) if p else p  # noqa: E731
                try:
                    iqi = rip.IQIInferencer(
                        gauge_weights=ab(args.gauge_weights), fclip_ckpt=ab(args.fclip_ckpt),
                        gauge_conf=args.gauge_conf, gauge_iou=args.gauge_iou, gauge_imgsz=args.gauge_imgsz,
                        gauge_device=args.gauge_device, gauge_select=args.gauge_select,
                        ocr_device=args.ocr_device, ocr_det_model_name=args.ocr_det_model_name,
                        ocr_det_model_dir=ab(args.ocr_det_model_dir),
                        ocr_rec_model_name=args.ocr_rec_model_name, ocr_rec_model_dir=ab(args.ocr_rec_model_dir),
                        ocr_det_limit_side_len=args.ocr_det_limit_side_len,
                        ocr_det_limit_type=args.ocr_det_limit_type,
                        enable_ocr_orientation=args.enable_ocr_orientation,
                        ocr_orientation_model=ab(args.ocr_orientation_model),
                        ocr_orientation_device=args.ocr_orientation_device,
                        ocr_number_range=args.ocr_number_range, fclip_device=args.fclip_device,
                        fclip_model_config=ab(args.fclip_config), fclip_params=ab(args.fclip_params),
                    )
                except Exception as exc:
                    self.log(f"[警告] IQIInferencer 初始化失败，跳过 IQI: {exc}")

        runner = rip.InferencePipelineRunner(
            args=args, roi_detector=roi_detector, font_renderer=font, debug_root=None,
            corrector=corrector, locator=locator, detector=detector, iqi_inferencer=iqi,
        )
        self._bundle = {"runner": runner, "iqi": iqi, "font": font}
        self._signature = sig
        self.log("[引擎] 模型加载完成")
        return self._bundle

    def _release_bundle(self) -> None:
        bundle, self._bundle, self._signature = self._bundle, None, None
        if bundle and bundle.get("iqi") is not None:
            try:
                bundle["iqi"].close()
            except Exception:
                pass

    def close(self) -> None:
        self._release_bundle()

    # -- 主流程 --
    def run(
        self,
        cfg: RunConfig,
        on_progress: Optional[ProgressFn] = None,
        on_result: Optional[ResultFn] = None,
        should_cancel: Optional[CancelFn] = None,
    ) -> RunSummary:
        started = time.time()
        progress = on_progress or (lambda *a: None)
        cancelled = should_cancel or (lambda: False)

        items = collect_inputs([Path(p) for p in cfg.inputs], cfg.recursive)
        if not items:
            raise FileNotFoundError("所选输入中没有支持的图像文件")
        task = cfg.task_name or time.strftime("%Y%m%d_%H%M%S")
        out_dir = Path(cfg.output_dir) / task
        out_dir.mkdir(parents=True, exist_ok=True)
        total = len(items)

        file_list = out_dir / "input_files.txt"
        file_list.write_text("\n".join(str(p) for p, _ in items), encoding="utf-8")
        args = self._build_args(cfg, out_dir, file_list)
        if cfg.enable_competition:
            self._prepare_competition(cfg)
            if cfg.competition_fast:
                self.log("[竞赛] 提速模式：已关闭 IQI/OCR、焊缝位置检测与灰度值计算")

        progress(0, total, "", "initializing")
        sink = _LineSink(self.log)
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):  # type: ignore[arg-type]
            bundle = self._ensure_bundle(args)
            summary = self._run_items(cfg, args, bundle, items, out_dir, progress, on_result, cancelled, started)
        sink.flush()
        return summary

    def _run_items(self, cfg, args, bundle, items, out_dir, progress, on_result, cancelled, started) -> RunSummary:
        rip = self._rip
        runner = bundle["runner"]
        total = len(items)
        prepared_root = paths.prepared_cache_dir() / uuid.uuid4().hex[:12]

        # runner 持有任务级可变字段，每次任务前重新赋值（与 api_server 一致）
        runner.args = args
        runner.output_dir = out_dir
        runner.iqi_image_root = None
        runner.iqi_vis_dir = out_dir / "iqi_vis" if runner.iqi_inferencer is not None else None
        runner.debug_root = None

        (out_dir / "run_params.json").write_text(
            json.dumps(self._run_params(cfg, args), ensure_ascii=False, indent=2), encoding="utf-8")

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        evaluations: Optional[List[Dict[str, Any]]] = [] if cfg.enable_competition else None
        failures: Dict[str, str] = {}
        used_names: Dict[str, int] = {}
        was_cancelled = False
        deadline = started + cfg.competition_deadline_min * 60 if (
            cfg.enable_competition and cfg.competition_deadline_min > 0) else None
        in_memory = runner.iqi_inferencer is None
        self._keep_raw = cfg.enable_competition and cfg.competition_split_pores
        timed_out = 0

        try:
            for idx, (src, rel) in enumerate(items):
                if cancelled():
                    was_cancelled = True
                    break
                if deadline is not None and time.time() >= deadline:
                    timed_out = total - idx
                    self.log(f"[竞赛] 已到截止时间 {cfg.competition_deadline_min:g} 分钟，剩余 {timed_out} 幅按无缺陷兜底")
                    for j, (s2, r2) in enumerate(items[idx:], start=idx):
                        failures[s2.name] = "超时未推理，兜底"
                        if on_result:
                            on_result(ImageOutcome(j, total, str(s2), str(r2), False, error="超时未推理",
                                                   timed_out=True))
                    break
                progress(idx, total, src.name, "running")
                outcome = self._run_one(rip, runner, src, rel, idx, total, prepared_root, in_memory)
                if outcome.ok and cfg.save_annotated:
                    try:
                        from . import render

                        outcome.annotated_path = str(
                            render.save_annotated(outcome.result, self._annotated_path(out_dir, rel, used_names))
                        )
                    except Exception as exc:
                        self.log(f"[警告] 标注图生成失败 ({src.name}): {exc}")
                raw_image = outcome.result.pop("_raw_corrected", None) if outcome.ok else None
                if outcome.ok and evaluations is not None:
                    outcome.competition = self._evaluate_competition(cfg, outcome.result, src, rel, raw_image)
                    if outcome.competition is not None:
                        evaluations.append(outcome.competition)
                del raw_image
                if outcome.ok:
                    results.append(outcome.result)
                else:
                    errors.append({"image": str(src), "error": outcome.error or "unknown"})
                    failures[src.name] = "推理失败，兜底"
                if on_result:
                    on_result(outcome)
                progress(idx + 1, total, src.name, "running")
        finally:
            self._write_outputs(rip, args, runner, out_dir, results, errors)
            elapsed = time.time() - started
            answers = None
            if evaluations is not None:
                self._write_competition(out_dir, evaluations)
                answers = self._export_answers(cfg, out_dir, evaluations, items, failures, elapsed)
            shutil.rmtree(prepared_root, ignore_errors=True)

        progress(total if not was_cancelled else len(results) + len(errors), total, "",
                 "cancelled" if was_cancelled else "completed")
        return RunSummary(str(out_dir), total, len(results), len(errors), was_cancelled, elapsed,
                          answers_path=answers, timed_out=timed_out)

    def _run_one(self, rip, runner, src: Path, rel: Path, idx: int, total: int, prepared_root: Path,
                 in_memory: bool = False) -> ImageOutcome:
        try:
            image_input = rip._prepare_image_input(src, prepared_root, in_memory=in_memory,
                                                   keep_raw=getattr(self, "_keep_raw", False))
        except Exception as exc:
            return ImageOutcome(idx, total, str(src), str(rel), False, error=f"读取/预处理失败: {exc}")

        # runner.run 内部吞掉单张异常只打印警告；这里用日志抓取最近的警告作为失败原因
        captured: List[str] = []
        original = self._log
        self._log = lambda s: (captured.append(s), original(s))[1]
        try:
            out = runner.run([image_input])
        except Exception as exc:
            return ImageOutcome(idx, total, str(src), str(rel), False, error=str(exc))
        finally:
            self._log = original
        if not out:
            warn = [s for s in captured if "[警告]" in s] or captured[-3:]
            return ImageOutcome(idx, total, str(src), str(rel), False, error=" | ".join(warn)[:500] or "推理失败")
        return ImageOutcome(idx, total, str(src), str(rel), True, result=out[0])

    def _prepare_competition(self, cfg: RunConfig) -> None:
        """读取《影像信息表》；逐图规格（competition_specs）优先于信息表。"""
        from competition import info_table

        self._info_rows = []
        self._spec_lookup = dict(cfg.competition_specs or {})
        if cfg.competition_info_table:
            rows = info_table.load_info_table(cfg.competition_info_table)
            bad = info_table.validate(rows)
            if bad:
                self.log("[警告] 影像信息表中以下规格无法解析：" + "；".join(bad[:20]))
            self._info_rows = rows
            self._spec_lookup = {**info_table.spec_map(rows), **self._spec_lookup}
            self.log(f"[竞赛] 影像信息表：{len(rows)} 行")

    def _export_answers(self, cfg: RunConfig, out_dir: Path, evaluations, items, failures,
                        elapsed: float) -> Optional[str]:
        from competition.exporter import export_answers, time_score

        try:
            res = export_answers(out_dir, evaluations, [src.name for src, _ in items],
                                 getattr(self, "_info_rows", []), failures)
        except Exception as exc:
            self.log(f"[错误] 竞赛答案导出失败: {exc}")
            return None
        for msg in res.issues[:50]:
            self.log(f"[答案检查] {msg}")
        path = str(res.xlsx_path or res.csv_path)
        self.log(f"[竞赛] 答案已导出：{path}（{res.images} 幅 / {res.rows} 行）；用时 {elapsed / 60:.1f} 分钟，"
                 f"按 40 分钟估计时间分 B={time_score(elapsed):.2f}")
        return path

    def _spec_for(self, cfg: RunConfig, src: Path, rel: Path) -> str:
        specs = getattr(self, "_spec_lookup", None) or cfg.competition_specs or {}
        for key in (str(rel), rel.as_posix(), src.name, src.stem):
            if key in specs and str(specs[key]).strip():
                return str(specs[key])
        return cfg.competition_default_spec

    @staticmethod
    def competition_eval_config(cfg: RunConfig):
        from competition import EvalConfig

        return EvalConfig(
            pipe_root_strict_table26=cfg.competition_strict_pipe_table26,
            split_round_clusters=cfg.competition_split_pores,
            intermittent_merge_gap_mm=cfg.competition_merge_gap_mm,
            intermittent_length_mode=cfg.competition_intermittent_length,
            plate_root_defects=cfg.competition_plate_root,
        )

    def _evaluate_competition(self, cfg: RunConfig, result: Dict[str, Any], src: Path,
                              rel: Path, image=None) -> Optional[Dict[str, Any]]:
        """单张评定失败只记日志，不影响推理结果。"""
        from competition import evaluate_image

        spec = self._spec_for(cfg, src, rel)
        if not str(spec).strip():
            self.log(f"[警告] 竞赛评定跳过 ({src.name}): 未提供规格")
            return None
        try:
            evaluation = evaluate_image(result, spec, self.competition_eval_config(cfg), image=image)
        except Exception as exc:
            self.log(f"[警告] 竞赛评定失败 ({src.name}): {exc}")
            return None
        data = evaluation.to_dict()
        data["rel_path"] = str(rel)
        for msg in evaluation.warnings:
            self.log(f"[评定] {src.name}: {msg}")
        return data

    @staticmethod
    def _write_competition(out_dir: Path, evaluations: List[Dict[str, Any]]) -> None:
        from competition.evaluator import PIXEL_SIZE_MM

        payload = {"schema": "competition_eval_v1", "pixel_size_mm": PIXEL_SIZE_MM, "results": evaluations}
        (out_dir / "competition_results.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _annotated_path(out_dir: Path, rel: Path, used: Dict[str, int]) -> Path:
        base = out_dir / "annotated" / rel.parent / rel.stem
        key = str(base).lower()
        used[key] = used.get(key, 0) + 1
        if used[key] > 1:  # 同名不同扩展名（a.tif / a.png）
            return base.with_name(f"{rel.stem}_{rel.suffix.lstrip('.')}").with_suffix(".jpg")
        return base.with_suffix(".jpg")

    def _write_outputs(self, rip, args, runner, out_dir: Path, results, errors) -> None:
        with open(out_dir / args.results_json, "w", encoding="utf-8") as f:
            json.dump({"mode": args.mode, "results": results}, f, indent=2, ensure_ascii=False)
        if errors:
            (out_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.enable_iqi:
            return
        iqi_path = out_dir / args.iqi_results_json
        if not rip._IQI_AVAILABLE:
            payload: Dict[str, Any] = {"ok": False, "fatal_error": getattr(rip, "_IQI_IMPORT_ERROR", "unknown"),
                                       "results": []}
        else:
            raw = [r.get("ocr") for r in results if r.get("ocr") is not None]
            summary = rip.build_iqi_statistics(raw)
            payload = {
                "schema": "iqi_grade_batch_v1", "ok": True, "fatal_error": None,
                "meta": {
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "image_root": None,
                    **(runner.iqi_inferencer.get_runtime_meta() if runner.iqi_inferencer is not None else {}),
                    "ocr_device": args.ocr_device, "ocr_det_model_name": args.ocr_det_model_name,
                    "ocr_det_model_dir": args.ocr_det_model_dir, "ocr_rec_model_name": args.ocr_rec_model_name,
                    "ocr_rec_model_dir": args.ocr_rec_model_dir,
                    "ocr_det_limit_side_len": args.ocr_det_limit_side_len,
                    "ocr_det_limit_type": args.ocr_det_limit_type, "ocr_number_range": args.ocr_number_range,
                    "enable_ocr_orientation": args.enable_ocr_orientation,
                    "ocr_orientation_model": args.ocr_orientation_model,
                    "ocr_orientation_device": args.ocr_orientation_device,
                    "vis_dir": "iqi_vis" if runner.iqi_inferencer is not None else None,
                },
                "summary": {k: summary[k] for k in (
                    "images_total", "success_total", "failure_total", "result_code_hist",
                    "result_code_hist_named", "iqi_type_hist", "grade_hist", "field_totals",
                    "images_with_general_fields", "images_with_iqi_marker")},
                "results": [rip.build_delivery_record(r) for r in raw],
            }
        iqi_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _run_params(self, cfg: RunConfig, args: argparse.Namespace) -> Dict[str, Any]:
        def fingerprint(p: str) -> Optional[Dict[str, Any]]:
            try:
                st = Path(p).stat()
                return {"size": st.st_size, "mtime": int(st.st_mtime)}
            except OSError:
                return None

        models = paths.ModelPaths.from_dict(cfg.models).to_dict()
        try:
            import torch

            torch_ver = torch.__version__
        except Exception:
            torch_ver = None
        return {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": asdict(cfg),
            "effective": {k: getattr(args, k) for k in (
                "mode", "device", "primary_conf", "wide_slice", "enable_correction", "enable_location",
                "location_conf", "enable_location2", "location2_conf", "enable_iqi")},
            "competition": {"enabled": cfg.enable_competition, "default_spec": cfg.competition_default_spec,
                            "eval_config": asdict(self.competition_eval_config(cfg)),
                            "per_image_specs": len(cfg.competition_specs or {})},
            "models": {k: {"path": v, "file": fingerprint(v)} for k, v in models.items()},
            "gpu": asdict(self._gpu),
            "env": {"python": sys.version.split()[0], "torch": torch_ver, "platform": sys.platform},
        }
