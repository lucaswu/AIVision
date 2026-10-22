import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competition import EvalConfig, evaluate_image, evaluate_results, parse_spec  # noqa: E402
from competition import standards as std  # noqa: E402
from competition.geometry import box_to_original, original_size  # noqa: E402

PX = 0.042


def apply_correction_label(image, label):
    """与 run_inference_pipeline._apply_correction_label 相同的正向变换（numpy 实现，避免重依赖）。"""
    rot = label % 4
    if rot == 1:
        image = np.rot90(image, 1)  # 逆时针 90°
    elif rot == 2:
        image = np.rot90(image, 2)
    elif rot == 3:
        image = np.rot90(image, -1)  # 顺时针 90°
    if label >= 4:
        image = image[:, ::-1]
    return image


def mm(v):
    """mm → 像素。"""
    return v / PX


def det(cls, x1, y1, x2, y2, conf=0.9):
    return {"class_name": cls, "bbox": [mm(x1), mm(y1), mm(x2), mm(y2)], "confidence": conf}


def result(dets, w=300.0, h=60.0, label=0):
    """水平焊缝，坐标单位 mm（矫正后坐标系）。"""
    return {
        "image_path": "/data/7.dcm",
        "width": int(mm(w)), "height": int(mm(h)),
        "correction": {"label": label},
        "rois": [{"roi_index": 0, "bbox": [0, mm(20), mm(w), mm(40)], "detections": dets}],
    }


class SpecTest(unittest.TestCase):
    def test_parse(self):
        s = parse_spec("28")
        self.assertEqual((s.thickness, s.is_pipe, s.chapter), (28.0, False, 6))
        s = parse_spec("20+4")
        self.assertEqual((s.thickness, s.extra_thickness), (20.0, 4.0))
        s = parse_spec("Φ89×6")
        self.assertEqual((s.thickness, s.outer_diameter, s.is_small_pipe, s.chapter), (6.0, 89.0, True, 7))
        self.assertFalse(parse_spec("φ219x12").is_small_pipe)
        self.assertEqual(parse_spec(16).thickness, 16.0)
        with self.assertRaises(ValueError):
            parse_spec("abc")


class StandardTablesTest(unittest.TestCase):
    def test_zone(self):
        self.assertEqual(std.round_zone_mm(parse_spec("25")), (10.0, 10.0))
        self.assertEqual(std.round_zone_mm(parse_spec("40")), (20.0, 10.0))
        self.assertEqual(std.round_zone_mm(parse_spec("120")), (30.0, 10.0))
        self.assertEqual(std.round_zone_mm(parse_spec("Φ89×40")), (10.0, 10.0))

    def test_points(self):
        cases = [(0.4, 0), (0.5, 0), (0.6, 1), (1.0, 1), (1.5, 2), (3.0, 3), (3.5, 6), (5, 10), (7, 15), (9, 25)]
        for d, p in cases:
            self.assertEqual(std.round_points(d, 20), p, d)
        self.assertEqual(std.round_points(0.6, 30), 0)  # 25<T≤50: ≤0.7 不计
        self.assertEqual(std.round_points(1.0, 100), 0)  # T>50: ≤1.4%T

    def test_round_grade(self):
        self.assertEqual([std.round_grade(p, 1.0, 20) for p in (0, 3, 4, 9, 18, 19)], [1, 1, 2, 2, 3, 4])
        self.assertEqual(std.round_grade(1, 10.5, 20), 4)  # 长径 > T/2

    def test_strip_ppt_examples(self):
        self.assertEqual(std.strip_grade([(0, 4)], 9), 2)
        self.assertEqual(std.strip_grade([(0, 30)], 90), 3)
        self.assertEqual(std.strip_grade([(0, 31)], 90), 4)

    def test_strip_group(self):
        # T=10：两段 3mm，间距 5mm ≤ 6L，累计 6 ≤ T → Ⅱ
        self.assertEqual(std.strip_grade([(0, 3), (8, 11)], 10), 2)
        # 累计 12 > T，但 Ⅲ 级间距 ≤ 3L=12 仍成组且 > max(T,6) → Ⅳ
        self.assertEqual(std.strip_grade([(0, 3), (8, 11), (16, 19), (24, 27)], 10), 4)
        # 间距大于 6L 不成组
        self.assertEqual(std.strip_grade([(0, 3), (30, 33)], 10), 2)

    def test_comprehensive(self):
        self.assertEqual(std.comprehensive_grade(2, 2), 3)
        self.assertEqual(std.comprehensive_grade(3, 3), 4)


class GeometryTest(unittest.TestCase):
    def test_inverse_matches_forward_transform(self):
        orig = np.zeros((7, 11), np.uint8)
        x, y = 3, 2
        orig[y, x] = 255
        for label in range(8):
            corr = apply_correction_label(orig, label)
            cy, cx = (int(v) for v in np.argwhere(corr == 255)[0])
            ow, oh = original_size(corr.shape[1], corr.shape[0], label)
            self.assertEqual((ow, oh), (11, 7))
            back = box_to_original([cx, cy, cx + 1, cy + 1], label, ow, oh)
            self.assertEqual(back, (x, y, x + 1, y + 1), label)


class EvaluateImageTest(unittest.TestCase):
    def test_no_defect_is_grade_i(self):
        ev = evaluate_image(result([det("其他", 10, 25, 12, 27)]), "20")
        self.assertEqual((ev.grade, ev.records), (1, []))

    def test_round_points_and_worst_zone(self):
        dets = [det("圆形缺陷", 50, 25, 51.5, 26.5),   # 2 点
                det("圆形缺陷", 55, 30, 56.8, 31.8),   # 2 点（同一评定区）
                det("圆形缺陷", 200, 30, 200.8, 30.8),  # 1 点（远处）
                det("圆形缺陷", 100, 30, 100.3, 30.3)]  # 不计点数
        ev = evaluate_image(result(dets), "20")
        self.assertEqual(len(ev.records), 1)
        r = ev.records[0]
        self.assertEqual((r.defect_type, r.quantity, r.points, r.grade), ("圆形缺陷", "4", 4, 2))
        self.assertAlmostEqual(r.x_mm, 50.0, places=1)
        self.assertEqual(ev.grade, 2)

    def test_comprehensive_rating(self):
        dets = [det("圆形缺陷", 50, 25, 51.5, 26.5), det("圆形缺陷", 54, 25, 55.5, 26.5),
                det("条形缺陷", 47, 28, 51, 29)]
        ev = evaluate_image(result(dets), "20")
        self.assertEqual([r.defect_type for r in ev.records], ["综合评级"])
        r = ev.records[0]
        self.assertEqual(r.quantity, "4.0, 4")
        self.assertAlmostEqual(r.x_mm, 47.0, places=1)
        # 圆形 4 点 Ⅱ 级 + 条形 4mm（≤ max(T/3,4)）Ⅱ 级 → Ⅲ 级
        self.assertEqual((r.grade, ev.grade), (3, 3))

    def test_strip_note3_merge_and_group(self):
        # 2mm + 间距 1mm + 3mm → 同一缺陷 6mm；远处 2mm 与之间距 10 ≤ 6L，按条渣组一起填报
        dets = [det("条形缺陷", 100, 30, 102, 30.5), det("条形缺陷", 103, 30, 106, 30.5),
                det("条形缺陷", 116, 30.2, 118, 30.6)]
        ev = evaluate_image(result(dets), "30")
        self.assertEqual(len(ev.records), 1)
        r = ev.records[0]
        self.assertEqual((r.defect_type, r.quantity, r.member_count), ("条形缺陷", "8.0", 3))
        self.assertAlmostEqual(r.x_mm, 100.0, places=1)
        self.assertEqual(ev.grade, 2)

    def test_transverse_cracks_cluster(self):
        dets = [det("裂纹", 60, 22, 60.5, 27), det("裂纹", 61.5, 23, 62, 30), det("裂纹", 150, 22, 150.5, 25)]
        ev = evaluate_image(result(dets), "20")
        cracks = [r for r in ev.records if r.defect_type == "裂纹"]
        self.assertEqual(len(cracks), 2)
        first = cracks[0]
        self.assertEqual(first.member_count, 2)
        self.assertAlmostEqual(first.x_mm, 60.0, places=1)
        self.assertAlmostEqual(first.length_mm, 7.0, delta=0.1)  # 最长一条的直线长度
        self.assertEqual(ev.grade, 4)

    def test_intermittent_lack_of_fusion(self):
        dets = [det("未熔合", 10, 30, 20, 31), det("未熔合", 21, 30, 25, 31), det("未熔合", 40, 30, 45, 31)]
        ev = evaluate_image(result(dets), "20")
        self.assertEqual([r.quantity for r in ev.records], ["15.0", "5.0"])

    def test_x_uses_original_orientation(self):
        # label=2（原图倒置 180°），矫正后 x∈[50,52] 在原图中为 [W-52, W-50]
        ev = evaluate_image(result([det("圆形缺陷", 50, 25, 52, 27)], label=2), "20")
        self.assertAlmostEqual(ev.records[0].x_mm, 300 - 52, delta=0.05)

    def test_pipe_root_defects(self):
        dets = [det("内凹", 10, 30, 30, 31)]  # 长度 20mm
        # 手动指定限值 15mm: 20 > 15 -> Ⅳ 级
        ev = evaluate_image(result(dets), "Φ89×6", EvalConfig(pipe_root_length_limit_iii_mm=15))
        self.assertEqual((ev.records[0].defect_type, ev.grade), ("根部内凹", 4))
        # 自动推导小径管限值 (0.3 * π * 89 ≈ 83.88mm): 20 <= 83.88 -> Ⅱ 级且无警告
        ev = evaluate_image(result(dets), "Φ89×6")
        self.assertEqual(ev.grade, 2)
        self.assertEqual(ev.warnings, [])
        # 长度 90mm > 83.88mm -> 自动判定为 Ⅳ 级
        dets_long = [det("内凹", 10, 30, 100, 31)]
        ev_long = evaluate_image(result(dets_long), "Φ89×6")
        self.assertEqual(ev_long.grade, 4)

    def test_pipe_root_table26_switch(self):
        # Φ219×8（大中径管，T=8，3T=24）：内凹 12mm + 28mm，总长 40 ≤ 100；任意 24mm 内累计 > T
        dets = [det("内凹", 10, 30, 22, 31), det("内凹", 100, 30, 128, 31)]
        strict = EvalConfig(pipe_root_strict_table26=True)
        self.assertEqual(evaluate_image(result(dets), "Φ219×8").grade, 2)  # 默认按规则（9）
        self.assertEqual(evaluate_image(result(dets), "Φ219×8", strict).grade, 3)
        # 两段各 5mm 相距较远：任意 24mm 内累计 5 ≤ 8 → 严格模式也是 Ⅱ 级
        sparse = [det("内凹", 10, 30, 15, 31), det("内凹", 60, 30, 65, 31)]
        self.assertEqual(evaluate_image(result(sparse), "Φ219×8", strict).grade, 2)
        # 总长 110 > 100 → 两种模式都是 Ⅳ 级
        long = [det("内凹", 10, 30, 120, 31)]
        self.assertEqual(evaluate_image(result(long), "Φ219×8").grade, 4)
        self.assertEqual(evaluate_image(result(long), "Φ219×8", strict).grade, 4)
        # 小径管不受开关影响（表 27 的 Ⅱ/Ⅲ 级长度相同）
        self.assertEqual(evaluate_image(result(dets), "Φ89×6", strict).grade, 2)

    def test_overlapping_root_boxes_merged(self):
        # 同一内凹被拆成 [10,20] 与 [15,25] 两个框 → 一个缺陷 15mm，而不是 20mm
        dets = [det("内凹", 10, 30, 20, 31), det("内凹", 15, 30, 25, 31)]
        ev = evaluate_image(result(dets), "Φ219×8")
        self.assertEqual([(r.defect_type, r.quantity, r.member_count) for r in ev.records],
                         [("根部内凹", "15.0", 2)])
        self.assertAlmostEqual(ev.records[0].x_mm, 10.0, places=1)
        # 不相交的两段仍分别记录
        ev = evaluate_image(result([det("内凹", 10, 30, 15, 31), det("内凹", 60, 30, 65, 31)]), "Φ219×8")
        self.assertEqual(len(ev.records), 2)

    def test_max_window_length_clips(self):
        self.assertAlmostEqual(std.max_window_length([(0, 5), (10, 20)], 12), 10.0)
        self.assertAlmostEqual(std.max_window_length([(0, 5), (8, 12)], 12), 9.0)

    def test_aspect_ratio_reclassification(self):
        # 1. 标为条形缺陷，但框为 2x2mm (长宽比 1.0 <= 3) -> 自动改判为圆形缺陷
        dets = [det("条形缺陷", 10, 20, 12, 22)]
        ev = evaluate_image(result(dets), "20")
        self.assertEqual(ev.records[0].defect_type, "圆形缺陷")
        self.assertTrue(any("改判为圆形缺陷" in w for w in ev.warnings))

        # 2. 标为圆形缺陷，但框为 10x1mm (长宽比 10.0 > 3) -> 自动改判为条形缺陷
        dets2 = [det("圆形缺陷", 10, 20, 20, 21)]
        ev2 = evaluate_image(result(dets2), "20")
        self.assertEqual(ev2.records[0].defect_type, "条形缺陷")
        self.assertTrue(any("改判为条形缺陷" in w for w in ev2.warnings))

    def test_ignored_round_downgrade(self):
        # T=20，长径 <= 0.5mm 的不计点数缺陷
        # 放置 12 个长径 0.4mm 的小气孔在同一个 10x10mm 评定区内
        dets = [det("圆形缺陷", 20 + i * 0.5, 25, 20 + i * 0.5 + 0.4, 25.4) for i in range(12)]
        ev = evaluate_image(result(dets), "20")
        # 没有计点气孔，但因不计点数气孔 > 10 个，从 Ⅰ 级降为 Ⅱ 级
        self.assertEqual(ev.grade, 2)
        self.assertEqual(ev.grade_label, "Ⅱ级")

    def test_no_defect_submission_records(self):
        # 无缺陷底片评为 Ⅰ 级，验证规范填报格式
        ev = evaluate_image(result([]), "20")
        self.assertEqual(ev.grade, 1)
        self.assertFalse(ev.has_defects)
        recs = ev.to_submission_records(fill_no_defect=True)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["defect_type"], "无")
        self.assertEqual(recs[0]["grade_label"], "Ⅰ级")
        self.assertEqual(recs[0]["x_px"], "—")
        self.assertTrue(recs[0]["is_no_defect"])

    def test_evaluate_results_spec_lookup(self):
        out = evaluate_results({"results": [result([])]}, {"7": "20"})
        self.assertEqual(out[0].to_dict()["image_name"], "7.dcm")


class EngineIntegrationTest(unittest.TestCase):
    """桩掉模型加载与推理，只验证引擎把评定结果接入输出。"""

    def _run(self, **cfg_kwargs):
        import json
        import tempfile

        from desktop.engine import ImageOutcome, InferenceEngine, RunConfig

        engine = InferenceEngine(log=lambda s: None)
        engine._ensure_bundle = lambda args: {"runner": type("R", (), {"iqi_inferencer": None})()}

        def fake_run_one(rip, runner, src, rel, idx, total, prepared_root, in_memory=False):
            res = result([det("圆形缺陷", 50, 25, 51.5, 26.5)])
            res["image_path"] = str(src)
            return ImageOutcome(idx, total, str(src), str(rel), True, result=res)

        engine._run_one = fake_run_one
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("1.dcm", "2.dcm"):
                (root / "in" / name).parent.mkdir(exist_ok=True)
                (root / "in" / name).write_bytes(b"x")
            cfg = RunConfig(inputs=[str(root / "in")], output_dir=str(root / "out"), enable_iqi=False,
                            save_annotated=False, task_name="t", **cfg_kwargs)
            outcomes = []
            engine.run(cfg, on_result=outcomes.append)
            out = root / "out" / "t" / "competition_results.json"
            payload = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        return outcomes, payload

    def test_competition_results_written(self):
        outcomes, payload = self._run(enable_competition=True, competition_default_spec="20",
                                      competition_specs={"2": "Φ89×6"})
        self.assertEqual([o.competition["spec"] for o in outcomes], ["20", "Φ89×6"])
        self.assertEqual([r["image_name"] for r in payload["results"]], ["1.dcm", "2.dcm"])
        rec = payload["results"][0]["records"][0]
        self.assertEqual((rec["defect_type"], rec["quantity"], payload["results"][0]["grade_label"]),
                         ("圆形缺陷", "2", "Ⅰ级"))

    def test_disabled_by_default(self):
        outcomes, payload = self._run()
        self.assertIsNone(payload)
        self.assertTrue(all(o.competition is None for o in outcomes))

    def test_missing_spec_skips_image(self):
        outcomes, payload = self._run(enable_competition=True, competition_specs={"1.dcm": "20"})
        self.assertEqual([r["image_name"] for r in payload["results"]], ["1.dcm"])
        self.assertIsNone(outcomes[1].competition)


    def test_info_table_answers_and_deadline(self):
        import tempfile

        from competition.xlsx import write_xlsx

        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "info.xlsx"
            write_xlsx(table, [["《影像信息表》"], ["影像序号", "影像名称", "规格", "材质"],
                               [1, "1.dcm", "20", "Q345R"], [2, "2.dcm", "Φ89×6", "20#"]])
            outcomes, payload = self._run(enable_competition=True, competition_info_table=str(table))
        self.assertEqual([o.competition["spec"] for o in outcomes], ["20", "Φ89×6"])

        outcomes, _ = self._run(enable_competition=True, competition_default_spec="20",
                                competition_deadline_min=1e-9)
        self.assertTrue(all(o.timed_out for o in outcomes))


class InfoTableExportTest(unittest.TestCase):
    def test_xlsx_roundtrip_and_spec_map(self):
        import tempfile

        from competition.info_table import load_info_table, spec_map
        from competition.xlsx import read_xlsx, write_xlsx

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.xlsx"
            write_xlsx(path, [["影像序号", "影像名称", "规格", "材质"], [1, "1.dcm", "28", "Q345R"],
                              [2, "2.dcm", "Φ89×6", "20#"], [3, "", "20+4", ""]])
            self.assertEqual(read_xlsx(path)[1], ["1", "1.dcm", "28", "Q345R"])
            rows = load_info_table(path)
        self.assertEqual([(r.index, r.name, r.spec) for r in rows],
                         [(1, "1.dcm", "28"), (2, "2.dcm", "Φ89×6"), (3, "3", "20+4")])
        m = spec_map(rows)
        self.assertEqual((m["1.dcm"], m["2"], m["3"]), ("28", "Φ89×6", "20+4"))

    def test_export_fills_every_image(self):
        import csv
        import tempfile

        from competition.exporter import export_answers
        from competition.info_table import InfoRow

        ev = evaluate_image(result([det("圆形缺陷", 50, 25, 51.5, 26.5)]), "20").to_dict()
        ev["image_name"] = "2.dcm"
        info = [InfoRow(1, "1.dcm", "28"), InfoRow(2, "2.dcm", "20"), InfoRow(10, "10.dcm", "Φ89×6")]
        with tempfile.TemporaryDirectory() as tmp:
            res = export_answers(Path(tmp), [ev], ["10.dcm", "2.dcm", "1.dcm"], info,
                                 failures={"1.dcm": "超时未推理，兜底"})
            with open(res.csv_path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual([r["影像名称"] for r in rows], ["1.dcm", "2.dcm", "10.dcm"])
        self.assertEqual((rows[0]["缺陷定性"], rows[0]["评定等级"], rows[0]["备注"]), ("无缺陷", "Ⅰ级", "超时未推理，兜底"))
        self.assertEqual((rows[1]["缺陷定性"], rows[1]["缺陷定量"]), ("圆形缺陷", "2"))
        self.assertIn("10.dcm: 未评定（缺少规格）", res.issues)


def pore_cluster_image(polarity=-1):
    """亮焊缝带 + 横向梯度 + 噪声，框 (488,172)-(590,236) 内 7 个小气孔（直径约 7~15px）。"""
    rng = np.random.default_rng(0)
    y = np.arange(400)[:, None]
    x = np.arange(1200)[None, :]
    img = 30000 + 6000 * np.exp(-((y - 200) / 70) ** 2) + 3 * x + rng.normal(0, 150, (400, 1200))
    for cx, cy, r in [(500, 190, 6), (520, 200, 5), (540, 185, 7), (515, 215, 4), (560, 205, 6),
                      (535, 222, 5), (575, 190, 3)]:
        img[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] += polarity * 2500
    return img.astype(np.float32)


def px_result(dets):
    return {"image_path": "/data/7.dcm", "width": 1200, "height": 400, "correction": {"label": 0},
            "rois": [{"roi_index": 0, "bbox": [0, 100, 1200, 300], "detections": dets}]}


class PoreSplitTest(unittest.TestCase):
    BOX = [488, 172, 590, 236]  # 102×64px ≈ 4.3×2.7mm

    def test_split_both_polarities(self):
        from competition.pore_split import SplitConfig, split_pores

        for pol, name in ((-1, "dark"), (1, "bright")):
            boxes = split_pores(pore_cluster_image(pol), self.BOX, SplitConfig(polarity=name))
            self.assertEqual(len(boxes), 7)
            self.assertTrue(all(max(b[2] - b[0], b[3] - b[1]) <= 16 for b in boxes))
        # 默认按暗气孔：亮斑不当作气孔
        self.assertIsNone(split_pores(pore_cluster_image(1), self.BOX))
        self.assertIsNone(split_pores(pore_cluster_image(), [100, 170, 180, 230]))  # 无气孔

    def test_cluster_no_longer_grade_iv(self):
        res = px_result([{"class_name": "圆形缺陷", "bbox": self.BOX, "confidence": 0.9}])
        # 不拆分：整框长径 4.3mm > T/2 = 4 → Ⅳ 级
        self.assertEqual(evaluate_image(res, "8").grade, 4)
        # 开关打开但未给图像：行为不变
        self.assertEqual(evaluate_image(res, "8", EvalConfig(split_round_clusters=True)).grade, 4)
        ev = evaluate_image(res, "8", EvalConfig(split_round_clusters=True), image=pore_cluster_image())
        self.assertLess(ev.grade, 4)
        self.assertTrue(any("拆分为 7 个气孔" in w for w in ev.warnings))


class WideRoundBoxTest(unittest.TestCase):
    def test_wide_round_box_not_turned_into_strip(self):
        # 300×26mm 的“圆形缺陷”大框（真实底片中整条焊缝/密集气孔区）：短边 26mm > 条形评定区宽 4mm，不改判条形
        ev = evaluate_image(result([det("圆形缺陷", 5, 20, 295, 46)], w=300, h=60), "20")
        self.assertEqual([r.defect_type for r in ev.records], ["圆形缺陷"])
        # 窄长框（短边 1mm）仍按长宽比改判为条形缺陷
        ev = evaluate_image(result([det("圆形缺陷", 50, 30, 60, 31)]), "20")
        self.assertEqual([r.defect_type for r in ev.records], ["条形缺陷"])


class IntermittentMergeTest(unittest.TestCase):
    def test_fixed_gap_and_length_mode(self):
        # 间隔 1.5mm ≤ 2mm → 一个缺陷；长度默认含间隔 41.5，各段和 40
        close_pair = [det("未熔合", 10, 30, 30, 30.5), det("未熔合", 31.5, 30, 51.5, 30.5)]
        self.assertEqual([r.quantity for r in evaluate_image(result(close_pair), "20").records], ["41.5"])
        ev = evaluate_image(result(close_pair), "20", EvalConfig(intermittent_length_mode="sum"))
        self.assertEqual([r.quantity for r in ev.records], ["40.0"])
        # 间隔 3mm > 2mm → 分开记录，即使两段都很长（真实底片 板6_2：两段长未熔合相隔 43mm 曾被合并）
        far_pair = [det("未熔合", 10, 30, 30, 30.5), det("未熔合", 33, 30, 53, 30.5)]
        self.assertEqual(len(evaluate_image(result(far_pair), "20").records), 2)


class PlateRootAndCorrectionTest(unittest.TestCase):
    def test_plate_root_switch(self):
        dets = [det("内凹", 10, 30, 30, 31)]
        # 默认：板上的根部内凹/咬边不填报
        ev = evaluate_image(result(dets), "20")
        self.assertEqual((ev.records, ev.grade), ([], 1))
        self.assertTrue(any("按配置不填报" in w for w in ev.warnings))
        self.assertEqual(len(evaluate_image(result(dets), "20", EvalConfig(plate_root_defects="report")).records), 1)
        # 管道不受该开关影响
        self.assertEqual(len(evaluate_image(result(dets), "Φ89×6").records), 1)

    def test_low_correction_confidence_warns(self):
        res = result([])
        res["correction"]["confidence"] = 0.6
        self.assertTrue(any("方向矫正置信度" in w for w in evaluate_image(res, "20").warnings))
        res["correction"]["confidence"] = 0.99
        self.assertFalse(any("方向矫正置信度" in w for w in evaluate_image(res, "20").warnings))


class EngineRawImageTest(unittest.TestCase):
    def test_raw_image_used_and_not_serialized(self):
        import json
        import tempfile

        from desktop.engine import ImageOutcome, InferenceEngine, RunConfig

        engine = InferenceEngine(log=lambda s: None)
        engine._ensure_bundle = lambda args: {"runner": type("R", (), {"iqi_inferencer": None})()}
        seen = []

        def fake_run_one(rip, runner, src, rel, idx, total, prepared_root, in_memory=False):
            seen.append(engine._keep_raw)
            res = px_result([{"class_name": "圆形缺陷", "bbox": PoreSplitTest.BOX, "confidence": 0.9}])
            res["image_path"] = str(src)
            res["_raw_corrected"] = pore_cluster_image()
            return ImageOutcome(idx, total, str(src), str(rel), True, result=res)

        engine._run_one = fake_run_one
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "in").mkdir()
            (root / "in" / "1.dcm").write_bytes(b"x")
            cfg = RunConfig(inputs=[str(root / "in")], output_dir=str(root / "out"), enable_iqi=False,
                            save_annotated=False, task_name="t", enable_competition=True,
                            competition_default_spec="8", competition_split_pores=True)
            outcomes = []
            engine.run(cfg, on_result=outcomes.append)
            saved = json.loads((root / "out" / "t" / "inference_results.json").read_text(encoding="utf-8"))
        self.assertEqual(seen, [True])
        self.assertNotIn("_raw_corrected", saved["results"][0])
        self.assertLess(outcomes[0].competition["grade"], 4)


class TimeScoreTest(unittest.TestCase):
    def test_time_score_and_forecast(self):
        from competition.exporter import forecast, time_score

        self.assertEqual(time_score(20 * 60), 5.0)
        self.assertEqual(time_score(45 * 60), 0.0)
        self.assertIsNone(forecast(30, 0, 0, 600))
        # 加载 60s 后推理 100 幅用 300s（3s/幅），剩 500 幅 → 总 360 + 1500 = 1860s = 31 分钟
        fc = forecast(360, 300, 100, 600)
        self.assertAlmostEqual(fc.avg_s, 3.0)
        self.assertAlmostEqual(fc.projected_s, 1860.0)
        self.assertEqual(fc.score, 2.25)


class StandardClauseTest(unittest.TestCase):
    def test_aspect_reclassify(self):
        # 模型给“条形缺陷”但长宽比 2 → 按标准为圆形缺陷（长径 2mm → 2 点）
        ev = evaluate_image(result([det("条形缺陷", 50, 25, 52, 26)]), "20")
        self.assertEqual([(r.defect_type, r.quantity) for r in ev.records], [("圆形缺陷", "2")])
        ev = evaluate_image(result([det("条形缺陷", 50, 25, 52, 26)]), "20",
                            EvalConfig(reclassify_by_aspect=False))
        self.assertEqual(ev.records[0].defect_type, "条形缺陷")

    def test_many_uncounted_pores_lower_grade_i(self):
        # 1 个计点气孔（Ⅰ 级）+ 11 个 0.4mm 不计点数气孔在同一评定区 → 降为 Ⅱ 级
        dets = [det("圆形缺陷", 50, 25, 50.8, 25.8)]
        dets += [det("圆形缺陷", 51 + 0.6 * i, 27, 51.4 + 0.6 * i, 27.4) for i in range(11)]
        ev = evaluate_image(result(dets), "20")
        self.assertEqual(ev.grade, 2)
        ev = evaluate_image(result(dets[:11]), "20")
        self.assertEqual(ev.grade, 1)


if __name__ == "__main__":
    unittest.main()
