"""无界面运行：python -m desktop.cli <输入路径...> -o <输出目录>。用于验收与排错。"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import InferenceEngine, RunConfig


def _load_spec_map(path: str) -> dict:
    """JSON：{"1.dcm": "28", "2": "Φ89×6", ...}（《影像信息表》解析器完成前的临时输入方式）。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("--spec-map 需为 {文件名或编号: 规格} 的 JSON 对象")
    return {str(k): str(v) for k, v in data.items()}


def _competition_brief(ev) -> str:
    if not ev:
        return ""

    def _fmt_item(r: dict) -> str:
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

    items = "; ".join(_fmt_item(r) for r in ev.get("records") or [])
    return f"  [{ev['grade_label']}] {items}"


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
    p.add_argument("--spec", default="", help="开启竞赛评定：所有影像共用的规格，如 20、20+4、Φ89×6")
    p.add_argument("--spec-map", default="", help="开启竞赛评定：逐图规格 JSON {文件名或编号: 规格}，优先于 --spec")
    p.add_argument("--info-table", default="", help="开启竞赛评定：《影像信息表》.xlsx/.xls/.csv")
    p.add_argument("--deadline-min", type=float, default=0.0,
                   help="竞赛截止分钟数（如 37）：到时剩余影像按无缺陷兜底并导出答案")
    p.add_argument("--strict-pipe-table26", action="store_true",
                   help="大中径管根部内凹/咬边严格按表 26 分 Ⅱ/Ⅲ/Ⅳ 级（默认按竞赛规则（9）只评 Ⅱ/Ⅳ）")
    p.add_argument("--split-pores", action="store_true",
                   help="圆形缺陷框内精细拆分：密集气孔大框拆回逐个气孔、按真实轮廓量长径（实验）")
    p.add_argument("--merge-gap", type=float, default=2.0, help="断续未熔合/未焊透/纵向裂纹：间隔 ≤ 该值（mm）合并为一个缺陷")
    p.add_argument("--intermittent-length", choices=["envelope", "sum"], default="envelope",
                   help="断续缺陷合并后的长度：envelope 含间隔 / sum 各段之和")
    p.add_argument("--report-plate-root", action="store_true",
                   help="板焊缝（第 6 章）上检出的根部内凹/咬边也填报（默认不填报）")
    p.add_argument("--no-fast", action="store_true", help="竞赛评定时不关闭 IQI/位置检测/灰度值")
    p.add_argument("--student-name", default="", help="远洋评分系统：学员姓名")
    p.add_argument("--exam-id", "--password", dest="exam_id", default="", help="远洋评分系统：考核号")
    p.add_argument("--changci", default="", help="远洋评分系统：场次号")
    p.add_argument("--submit-online", action="store_true", help="竞赛答案导出后自动 POST 提交至远洋评分服务器")
    p.add_argument("--submit-url", default="http://www.farain.com:3030/testing/ai/ray/submit",
                   help="远洋评分服务器接口地址")
    a = p.parse_args(argv)
    spec_map = _load_spec_map(a.spec_map) if a.spec_map else {}

    cfg = RunConfig(
        inputs=a.inputs, output_dir=a.output, recursive=not a.no_recursive, mode=a.mode, device=a.device,
        primary_conf=a.primary_conf, wide_slice=not a.no_wide_slice, enable_correction=not a.no_correction,
        enable_location=not a.no_location, enable_location2=not a.no_location2, enable_iqi=not a.no_iqi,
        save_annotated=not a.no_annotated, task_name=a.task_name,
        enable_competition=bool(a.spec or spec_map or a.info_table), competition_default_spec=a.spec,
        competition_specs=spec_map, competition_info_table=a.info_table, competition_fast=not a.no_fast,
        competition_deadline_min=a.deadline_min, competition_strict_pipe_table26=a.strict_pipe_table26,
        competition_split_pores=a.split_pores, competition_merge_gap_mm=a.merge_gap,
        competition_intermittent_length=a.intermittent_length,
        competition_plate_root="report" if a.report_plate_root else "drop",
        student_name=a.student_name, student_password=a.exam_id, changci=a.changci,
        submit_farain_online=a.submit_online, submit_farain_url=a.submit_url,
    )
    engine = InferenceEngine()
    if not engine.gpu.available:
        print(f"[警告] {engine.gpu.message}", flush=True)
    try:
        s = engine.run(
            cfg,
            on_progress=lambda c, t, f, st: print(f"[{st}] {c}/{t} {f}", flush=True),
            on_result=lambda o: print(("  OK " if o.ok else "  FAIL ") + o.rel_path + (f" -> {o.error}" if o.error else "")
                                      + _competition_brief(o.competition), flush=True),
        )
    finally:
        engine.close()
    print(f"完成: 成功 {s.succeeded} / 失败 {s.failed} / 共 {s.total}，耗时 {s.elapsed_s:.1f}s，输出: {s.output_dir}")
    if s.answers_path:
        print(f"竞赛答案: {s.answers_path}" + (f"（{s.timed_out} 幅超时兜底）" if s.timed_out else ""))
    return 0 if s.failed == 0 and not s.cancelled else 1


if __name__ == "__main__":
    sys.exit(main())
