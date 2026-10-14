"""无界面运行：python -m desktop.cli <输入路径...> -o <输出目录>。用于验收与排错。"""

from __future__ import annotations

import argparse
import sys

from .engine import InferenceEngine, RunConfig


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AIVision 桌面版（无界面）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--mode", choices=["det", "seg"], default="det")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--primary-conf", type=float, default=0.15)
    p.add_argument("--no-iqi", action="store_true")
    p.add_argument("--no-location", action="store_true")
    p.add_argument("--no-location2", action="store_true")
    p.add_argument("--no-correction", action="store_true")
    p.add_argument("--no-wide-slice", action="store_true")
    p.add_argument("--no-annotated", action="store_true")
    p.add_argument("--no-recursive", action="store_true")
    p.add_argument("--task-name", default="")
    a = p.parse_args(argv)

    cfg = RunConfig(
        inputs=a.inputs, output_dir=a.output, recursive=not a.no_recursive, mode=a.mode, device=a.device,
        primary_conf=a.primary_conf, wide_slice=not a.no_wide_slice, enable_correction=not a.no_correction,
        enable_location=not a.no_location, enable_location2=not a.no_location2, enable_iqi=not a.no_iqi,
        save_annotated=not a.no_annotated, task_name=a.task_name,
    )
    engine = InferenceEngine()
    if not engine.gpu.available:
        print(f"[警告] {engine.gpu.message}", flush=True)
    try:
        s = engine.run(
            cfg,
            on_progress=lambda c, t, f, st: print(f"[{st}] {c}/{t} {f}", flush=True),
            on_result=lambda o: print(("  OK " if o.ok else "  FAIL ") + o.rel_path + (f" -> {o.error}" if o.error else ""),
                                      flush=True),
        )
    finally:
        engine.close()
    print(f"完成: 成功 {s.succeeded} / 失败 {s.failed} / 共 {s.total}，耗时 {s.elapsed_s:.1f}s，输出: {s.output_dir}")
    return 0 if s.failed == 0 and not s.cancelled else 1


if __name__ == "__main__":
    sys.exit(main())
