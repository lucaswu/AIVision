import cv2
import os
import json
import numpy as np
import importlib.util
from pathlib import Path
from ultralytics import YOLO
import torch
import argparse
import sys

# ================= 配置区域 (默认值) =================
DEFAULT_INPUT_FOLDER = "data/img"        # 默认原始图片路径
DEFAULT_MODEL_PATH = "runs/train/weld_pose_processed/weights/best.pt"
DEFAULT_OUTPUT_FOLDER = "inference_results_processed"
DEFAULT_CONF_THRESHOLD = 0.6            # 默认置信度阈值
# ===========================================

# --- 1. 修复 PyTorch 2.6+ 兼容性 ---
_original_load = torch.load
def safe_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = safe_load

# --- 2. 动态加载预处理模块 ---
def load_processor(filepath="adaptive-image-processor.py"):
    if not os.path.exists(filepath):
        # 尝试在当前目录查找
        if os.path.exists(os.path.join(os.getcwd(), filepath)):
             filepath = os.path.join(os.getcwd(), filepath)
        else:
             raise FileNotFoundError(f"找不到预处理脚本: {filepath}")
    
    spec = importlib.util.spec_from_file_location("adaptive_image_processor", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AdaptiveImageProcessor

def collect_images(image_dir, file_list_path):
    """
    收集待处理的图像文件路径
    """
    image_paths = []
    valid_suffixes = {'.bmp', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}

    # 1. 从文件列表读取
    if file_list_path:
        if not os.path.exists(file_list_path):
            print(f"[错误] 文件列表不存在: {file_list_path}")
            return []
        
        with open(file_list_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                path = line.strip()
                if path and os.path.exists(path):
                     if Path(path).suffix.lower() in valid_suffixes:
                        image_paths.append(path)
                     else:
                        print(f"[警告] 跳过不支持的文件格式: {path}")
                elif path:
                    print(f"[警告] 文件不存在: {path}")
        print(f"从文件列表加载了 {len(image_paths)} 张图片")

    # 2. 从文件夹读取 (如果未提供文件列表或需补充)
    if image_dir and os.path.isdir(image_dir):
        input_path = Path(image_dir)
        dir_images = [str(f) for f in input_path.iterdir() if f.suffix.lower() in valid_suffixes]
        
        # 如果已经有文件列表，可以选择合并或者忽略文件夹（这里选择合并并去重）
        current_set = set(image_paths)
        for img_path in dir_images:
            if img_path not in current_set:
                image_paths.append(img_path)
        
        if not file_list_path:
             print(f"从文件夹加载了 {len(dir_images)} 张图片")

    return image_paths

def process_and_predict(args):
    input_dir = args.image_dir
    file_list = args.file_list
    output_dir = args.output_dir
    model_path = args.model_path
    conf_threshold = args.conf_threshold

    # 初始化输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 加载预处理器
    print(">>> 正在加载图像处理器...")
    try:
        AdaptiveImageProcessor = load_processor()
        # ⚠️ 必须与训练配置一致
        processor = AdaptiveImageProcessor(use_negative=True)
    except Exception as e:
        print(f"错误: 无法加载或初始化 adaptive-image-processor.py: {e}")
        return

    # 加载模型
    if not os.path.exists(model_path):
        print(f"错误: 模型文件不存在 {model_path}")
        return
        
    print(f">>> 正在加载模型: {model_path} ...")
    model = YOLO(model_path)
    names = model.names

    # 收集图片
    image_files = collect_images(input_dir, file_list)
    
    if not image_files:
        print(f"未找到待处理的图片。请检查 --image-dir 或 --file-list 参数。")
        return

    print(f">>> 开始处理 {len(image_files)} 张图片...")

    count = 0
    for img_path_str in image_files:
        img_file = Path(img_path_str)
        try:
            # 1. 读取原始图片
            # cv2.imdecode 读取支持中文路径
            raw_img = cv2.imdecode(np.fromfile(str(img_file), dtype=np.uint8), cv2.IMREAD_COLOR)
            if raw_img is None: 
                print(f"[警告] 无法读取图片: {img_file.name}")
                continue

            # 2. 预处理
            processed_img = processor.process_image(raw_img)

            # 3. 维度修正 (转 BGR)
            if len(processed_img.shape) == 2:
                processed_img_bgr = cv2.cvtColor(processed_img, cv2.COLOR_GRAY2BGR)
            else:
                processed_img_bgr = processed_img

            # 4. 推理
            results = model.predict(processed_img_bgr, conf=conf_threshold, verbose=False)[0]

            if len(results.boxes) == 0:
                print(f"[未检测到目标] {img_file.name}")
                continue

            # 准备保存 JSON 数据
            image_result = {
                "image_name": img_file.name,
                "file_path": str(img_file),
                "width": raw_img.shape[1],
                "height": raw_img.shape[0],
                "detections": []
            }

            # 5. 绘制结果 & 提取数据
            annotated_img = processed_img_bgr.copy()
            
            for box, keypoints, cls_id in zip(results.boxes, results.keypoints, results.boxes.cls):
                class_name = names[int(cls_id)]
                # 获取关键点坐标 (x, y)
                pts = keypoints.xy[0].cpu().numpy()

                # --- 垂直焊缝拉直逻辑 ---
                if class_name == 'vertical':
                    valid_pts = pts[pts[:, 0] > 0]
                    if len(valid_pts) > 0:
                        center_x = np.mean(valid_pts[:, 0])
                        mask = pts[:, 0] > 0
                        pts[mask, 0] = center_x

                # 收集 JSON 数据
                detection_data = {
                    "class": class_name,
                    "confidence": float(box.conf[0]),
                    "bbox": [int(x) for x in box.xyxy[0].tolist()],  # [x1, y1, x2, y2]
                    "keypoints": []
                }

                # 提取 12 个关键点
                for i, (px, py) in enumerate(pts):
                    point_data = {
                        "id": i + 1,  # 1-12
                        "x": float(px),
                        "y": float(py),
                        "visible": bool(px > 1 and py > 1) # 简单判断可见性
                    }
                    detection_data["keypoints"].append(point_data)

                image_result["detections"].append(detection_data)

                # --- 绘制逻辑 ---
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                color = (0, 255, 0) if class_name == 'ellipse' else (0, 165, 255)
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 2)
                label_text = f"{class_name} {box.conf[0]:.2f}"
                cv2.putText(annotated_img, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                for i, (px, py) in enumerate(pts):
                    if px > 1 and py > 1:
                        cv2.circle(annotated_img, (int(px), int(py)), 3, (0, 0, 255), -1)
                        cv2.putText(annotated_img, str(i+1), (int(px)+5, int(py)-5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            # 6. 保存图片结果
            save_img_path = output_path / f"res_{img_file.stem}.png"
            cv2.imencode('.png', annotated_img)[1].tofile(str(save_img_path))

            # 7. 保存 JSON 结果
            save_json_path = output_path / f"res_{img_file.stem}.json"
            with open(save_json_path, 'w', encoding='utf-8') as f:
                json.dump(image_result, f, indent=4, ensure_ascii=False)

            print(f"[检测成功] {img_file.name} -> {len(results.boxes)} 个目标 | JSON 已保存")
            count += 1

        except Exception as e:
            print(f"[错误] 处理 {img_file.name} 时发生异常: {e}")

    print(f"\n>>> 处理完成！共处理 {count} 张图片。")
    print(f">>> 结果已保存至: {output_path.absolute()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8 焊缝关键点检测推理程序")
    
    # 输入参数 (二选一或混合使用)
    parser.add_argument('--image-dir', type=str, default=None,
                        help='输入图片文件夹路径')
    parser.add_argument('--file-list', type=str, default=None,
                        help='包含待处理图像绝对路径的文本文件（每行一个路径）')
    
    # 模型与输出参数
    parser.add_argument('--model-path', type=str, default=DEFAULT_MODEL_PATH,
                        help=f'模型路径 (默认: {DEFAULT_MODEL_PATH})')
    parser.add_argument('-o', '--output-dir', type=str, default=DEFAULT_OUTPUT_FOLDER,
                        help=f'输出目录路径 (默认: {DEFAULT_OUTPUT_FOLDER})')
    parser.add_argument('--conf-threshold', type=float, default=DEFAULT_CONF_THRESHOLD,
                        help=f'置信度阈值 (默认: {DEFAULT_CONF_THRESHOLD})')

    args = parser.parse_args()

    # 检查是否至少提供了一个输入源
    if not args.image_dir and not args.file_list:
        # 如果未指定任何参数，尝试使用脚本内定义的默认文件夹（兼容旧用法）
        print(f"未指定输入源，尝试使用默认文件夹: {DEFAULT_INPUT_FOLDER}")
        if os.path.exists(DEFAULT_INPUT_FOLDER):
            args.image_dir = DEFAULT_INPUT_FOLDER
        else:
            print("错误: 请提供 --image-dir 或 --file-list 参数")
            sys.exit(1)

    process_and_predict(args)