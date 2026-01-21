# char_height_craft.py
import os, json, argparse
import cv2
import numpy as np
import pandas as pd

# ---- 计算“字符高度”的三个口径 ----
def heights_from_quad(poly4: np.ndarray):
    """
    poly4: (4,2) float32, 顺时针四边形
    返回: h_minRect, h_bodyAvg, h_vertical
    """
    p = poly4.astype(np.float32)
    # 上下边长度（假设顺时针 p0,p1,p2,p3）
    e_top = np.linalg.norm(p[1]-p[0])
    e_bot = np.linalg.norm(p[2]-p[3])
    h_body = 0.5*(e_top + e_bot)          # 本体高度：上下边均值
    h_vert = float(np.max(p[:,1]) - np.min(p[:,1]))  # 全局竖直投影高度

    # minAreaRect 的短边
    rect = cv2.minAreaRect(p)
    w, h = rect[1]
    h_minrect = min(w, h)
    return float(h_minrect), float(h_body), float(h_vert)

def order_clockwise(pts: np.ndarray):
    """将 4 点按顺时针且从 (x+y) 最小的点开始排序"""
    pts = pts.astype(np.float32)
    start = np.argmin(pts.sum(axis=1))
    return np.roll(pts, -int(start), axis=0)

# ---- 用 CRAFT 得到热力图，然后在字符热力图上做连通域取字符 ----
def craft_char_boxes(
    image_path: str,
    out_dir: str = None,
    text_threshold: float = 0.7,
    link_threshold: float = 0.4,
    low_text: float = 0.4,
    long_size: int = 1280,
    cuda: bool = True,
    char_thresh: float = 0.5,     # 对字符热力图（region score）二值阈值
    min_area: int = 9,            # 最小连通域面积（像素）
    max_area_ratio: float = 0.5,  # 过滤超大连通域：面积 < 0.5*图像面积
):
    # 1) CRAFT 推理（自动下载权重；返回框、热力图等）
    from craft_text_detector import Craft  # pip 包装好的 CRAFT 接口
    craft = Craft(
        output_dir=out_dir,
        rectify=True,
        export_extra=True,            # 导出可视化 & 热力图
        text_threshold=text_threshold,
        link_threshold=link_threshold,
        low_text=low_text,
        cuda=cuda,
        long_size=long_size,
        refiner=True,                 # 启用 link refiner
        crop_type="poly",
    )
    result = craft.detect_text(image_path)  # 见其返回结构说明
    # result["heatmaps"] 里包含字符/连通热力图（region/link）
    # 注：该库的 API 会返回 boxes/polys、heatmaps 和导出路径等。:contentReference[oaicite:2]{index=2}

    # 2) 取出“字符区域热力图”（region score），做阈值与连通域
    heatmaps = result.get("heatmaps", {})
    # 兼容不同键名（版本可能略有不同）
    textmap = (
        heatmaps.get("text_score_heatmap", None)
        if isinstance(heatmaps, dict) else None
    )
    if textmap is None:
        raise RuntimeError("未从 CRAFT 结果中拿到字符热力图(text_score_heatmap)。")

    # 归一化到 0~255 的 uint8，显式阈值化得到字符像素
    tmin, tmax = float(textmap.min()), float(textmap.max())
    if tmax - tmin < 1e-6:
        raise RuntimeError("字符热力图几乎是常数，无法阈值化。")
    textmap_u8 = ((textmap - tmin) / (tmax - tmin) * 255.0).astype(np.uint8)
    th = int(round(char_thresh * 255))
    _, binmap = cv2.threshold(textmap_u8, th, 255, cv2.THRESH_BINARY)

    # 3) 轻度形态学去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    binmap = cv2.morphologyEx(binmap, cv2.MORPH_OPEN, kernel, iterations=1)

    H, W = binmap.shape[:2]
    max_area = max(4, int(max_area_ratio * H * W))

    # 4) 连通域 -> 轮廓 -> 旋转矩形 -> 4 点
    contours, _ = cv2.findContours(binmap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    records, quads = [], []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue

        rect = cv2.minAreaRect(cnt)               # ((cx,cy),(w,h),angle)
        (cx, cy), (rw, rh), angle = rect
        if rw < 1 or rh < 1:
            continue

        box = cv2.boxPoints(rect)                 # (4,2) float
        box = order_clockwise(box)
        h_minrect, h_body, h_vert = heights_from_quad(box)

        records.append({
            "cx": float(cx), "cy": float(cy),
            "w": float(rw), "h": float(rh), "angle": float(angle),
            "area": float(area),
            "height_minRect": h_minrect,
            "height_bodyAvg": h_body,
            "height_vertical": h_vert,
            "quad": box.tolist(),
        })
        quads.append(box)

    # 5) 叠加可视化 & 导出 CSV
    vis = cv2.imread(image_path)
    if vis is None:
        raise RuntimeError(f"读取图像失败：{image_path}")
    for i, q in enumerate(quads, 1):
        qint = q.astype(np.int32)
        cv2.polylines(vis, [qint], True, (0,255,0), 2)
        cv2.putText(vis, str(int(round(records[i-1]["height_minRect"]))),
                    (int(q[0,0]), int(q[0,1])), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255,0,0), 1, cv2.LINE_AA)

    os.makedirs(out_dir, exist_ok=True)
    overlay_path = os.path.join(out_dir, "craft_char_heights_overlay.png")
    csv_path = os.path.join(out_dir, "craft_char_heights.csv")
    cv2.imwrite(overlay_path, vis)

    df = pd.DataFrame.from_records(records)
    df = df.sort_values(by=["cy","cx"]).reset_index(drop=True)
    df.to_csv(csv_path, index=False)

    # 也把参数与路径简单记录一下
    meta = {
        "image": os.path.abspath(image_path),
        "overlay": os.path.abspath(overlay_path),
        "csv": os.path.abspath(csv_path),
        "text_threshold": text_threshold,
        "link_threshold": link_threshold,
        "low_text": low_text,
        "long_size": long_size,
        "char_thresh": char_thresh,
        "num_chars": len(records),
    }
    with open(os.path.join(out_dir, "craft_run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta, df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True, help="输入图片路径")
    ap.add_argument("--out", default="out_craft", help="输出目录")
    ap.add_argument("--cpu", action="store_true", help="强制用 CPU")
    ap.add_argument("--char_thresh", type=float, default=0.5, help="字符热力图二值阈值(0-1)")
    args = ap.parse_args()

    meta, df = craft_char_boxes(
        args.img, out_dir=args.out, cuda=(not args.cpu),
        char_thresh=args.char_thresh
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"已检测字符数: {len(df)}")
    print(f"CSV: {meta['csv']}\nOverlay: {meta['overlay']}")

if __name__ == "__main__":
    main()
