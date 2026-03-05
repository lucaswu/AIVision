# scripts/21_inference_yolo_detection_v2.py
"""
YOLO检测 + OCR识别 + 原点计算
集成自适应图像预处理（窗口化 + 负片变换），与训练保持一致
"""

from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
import argparse
import json
import importlib.util
try:
    from paddleocr import PaddleOCR
    HAS_PADDLEOCR = True
except ImportError:
    HAS_PADDLEOCR = False
    print("警告: 未安装paddleocr，将无法进行OCR识别")
    print("安装(GPU): pip install paddleocr paddlepaddle-gpu")
    print("安装(CPU): pip install paddleocr paddlepaddle")


# ==================== 加载预处理器 ====================

def load_adaptive_processor(filepath="adaptive-image-processor.py"):
    """动态加载自适应图像预处理器（与训练脚本保持一致）"""
    possible_paths = [
        Path(filepath),
        Path.cwd() / filepath,
        Path(__file__).parent / filepath,
        Path(__file__).parent.parent / filepath,
    ]
    for path in possible_paths:
        if path.exists():
            try:
                spec = importlib.util.spec_from_file_location("adaptive_image_processor", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                print(f"✓ 已加载预处理器: {path}")
                return module.AdaptiveImageProcessor
            except Exception as e:
                print(f"  加载失败 {path}: {e}")
    print("⚠ 未找到 adaptive-image-processor.py，跳过自适应预处理")
    return None

class YOLODetectionInference:
    """YOLO检测 + OCR推理器"""
    
    def __init__(self, model_path, conf=0.25, use_ocr=True, use_adaptive_preprocessing=True):
        self.model = YOLO(model_path)
        self.conf = conf
        self.use_ocr = use_ocr

        self.class_names = [
            'center_mark',
            'letter_left',
            'letter_right',
            'number_left',
            'number_right'
        ]

        # 初始化自适应预处理器
        self.processor = None
        if use_adaptive_preprocessing:
            AdaptiveImageProcessor = load_adaptive_processor()
            if AdaptiveImageProcessor is not None:
                self.processor = AdaptiveImageProcessor(use_negative=True)

        # 初始化PaddleOCR
        self.reader = None
        if self.use_ocr and HAS_PADDLEOCR:
            print("初始化PaddleOCR引擎...")
            # use_angle_cls: 开启方向分类，应对倒置/旋转文字
            # lang='en': 英文字母+数字识别
            # show_log=False: 抑制冗余日志
            self.reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            print("✓ PaddleOCR引擎就绪")
        elif self.use_ocr:
            print("⚠ PaddleOCR不可用，将跳过OCR识别")

        print(f"✓ 模型加载: {model_path}")
        print(f"✓ 置信度阈值: {conf}")
        print(f"✓ 自适应预处理: {'开启' if self.processor else '关闭'}")

    def _preprocess(self, img_bgr: np.ndarray) -> np.ndarray:
        """
        自适应预处理：灰度化 → 骨骼/金属窗口化 → 负片变换 → 转回BGR
        与训练时 preprocess_dataset 流程完全一致。
        若预处理器不可用，直接返回原图。
        """
        if self.processor is None:
            return img_bgr
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        processed_gray = self.processor.process_image(gray_bgr)  # 返回 uint8 灰度图

        # 自适应锐化（白底黑字场景）
        # 用高斯模糊估计局部低频，然后按局部对比度自适应增强边缘
        blurred = cv2.GaussianBlur(processed_gray, (0, 0), sigmaX=2.0)
        local_contrast = processed_gray.astype(np.float32) - blurred.astype(np.float32)
        # 局部标准差衡量区域复杂度，复杂区域（文字边缘）增益大，平坦区域增益小
        local_std = cv2.GaussianBlur(
            (local_contrast ** 2).astype(np.float32), (0, 0), sigmaX=10.0
        ) ** 0.5
        # 归一化增益：std越大→文字边缘区域→增益越强，最大1.5倍
        gain = 1.0 + 0.5 * (local_std / (local_std.max() + 1e-6))
        sharpened = np.clip(
            processed_gray.astype(np.float32) + gain * local_contrast, 0, 255
        ).astype(np.uint8)

        return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

    def extract_text_from_bbox(self, image, bbox):
        """
        从检测框中提取文字
        
        Args:
            image: 原始图像
            bbox: [x1, y1, x2, y2]
        
        Returns:
            text: 识别的文字
        """
        x1, y1, x2, y2 = map(int, bbox)
        img_h, img_w = image.shape[:2]

        # 外扩10%
        pad_x = int((x2 - x1) * 0.5)
        pad_y = int((y2 - y1) * 0.5)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(img_w, x2 + pad_x)
        y2 = min(img_h, y2 + pad_y)

        # 裁剪ROI
        roi = image[y1:y2, x1:x2]
        
        if roi.size == 0:
            return None
        
        if self.reader is None:
            return None

        try:
            # PaddleOCR 推理
            # 输入：numpy BGR图像；返回：[[[box, (text, score)], ...]]
            ocr_result = self.reader.ocr(roi, cls=True)
            print('ocr_result',ocr_result)

            if not ocr_result or not ocr_result[0]:
                return None

            # 收集所有识别文本，按置信度降序排列
            candidates = []
            for line in ocr_result[0]:
                text_info = line[1]          # (text, confidence)
                text_raw  = text_info[0]
                score     = text_info[1]
                # 只保留字母和数字
                cleaned = ''.join(c for c in text_raw if c.isalnum()).upper()
                if cleaned:
                    candidates.append((cleaned, score))

            if not candidates:
                return None

            # 取置信度最高的结果
            best_text, best_score = max(candidates, key=lambda x: x[1])
            return best_text

        except Exception as e:
            print(f"    OCR失败: {e}")
            return None
    
    def compare_marks(self, left_value, right_value, left_type, right_type):
        """
        比较左右标记，判断原点位置
        
        Args:
            left_value: 左侧标记的值（如 'A', '4'）
            right_value: 右侧标记的值（如 'B', '1'）
            left_type: 左侧类型（'letter' 或 'number'）
            right_type: 右侧类型（'letter' 或 'number'）
        
        Returns:
            'left' 或 'right'
        """
        # 如果双侧均无法识别，默认左侧为原点
        if not left_value and not right_value:
            print(f"    ⚠ 双侧均无法识别标记值，默认左侧为原点")
            return 'left'

        # 只有一侧识别到值，根据识别值判断原点
        if not left_value or not right_value:
            recognized_side = 'right' if not left_value else 'left'
            recognized_value = right_value if not left_value else left_value
            recognized_type = right_type if not left_value else left_type
            other_side = 'left' if recognized_side == 'right' else 'right'

            if recognized_type == 'letter':
                letter = next((c for c in recognized_value if c.isalpha()), None)
                if letter == 'A':
                    print(f"    → 仅{recognized_side}侧识别到字母'{letter}'(起始标记)，原点在{recognized_side}侧")
                    return recognized_side
                elif letter:
                    print(f"    → 仅{recognized_side}侧识别到字母'{letter}'(非起始)，原点在{other_side}侧")
                    return other_side
            else:  # number
                try:
                    num = int(''.join(c for c in recognized_value if c.isdigit()))
                    if num == 1:
                        print(f"    → 仅{recognized_side}侧识别到数字'{num}'(起始标记)，原点在{recognized_side}侧")
                        return recognized_side
                    else:
                        print(f"    → 仅{recognized_side}侧识别到数字'{num}'(非起始)，原点在{other_side}侧")
                        return other_side
                except ValueError:
                    pass

            print(f"    ⚠ 仅{recognized_side}侧有识别结果，使用{recognized_side}侧为原点")
            return recognized_side

        # 类型必须相同才能比较
        if left_type != right_type:
            print(f"    ⚠ 左右标记类型不同: {left_type} vs {right_type}，默认左侧")
            return 'left'
        
        if left_type == 'letter':
            left_letter = next((c for c in left_value if c.isalpha()), None)
            right_letter = next((c for c in right_value if c.isalpha()), None)

            # 一侧无法提取字母（OCR误读为数字等），退化为单侧逻辑
            if not left_letter or not right_letter:
                recognized_side = 'right' if not left_letter else 'left'
                letter = right_letter if not left_letter else left_letter
                other_side = 'left' if recognized_side == 'right' else 'right'
                if letter == 'A':
                    print(f"    → 仅{recognized_side}侧识别到有效字母'{letter}'(起始标记)，原点在{recognized_side}侧")
                    return recognized_side
                else:
                    print(f"    → 仅{recognized_side}侧识别到有效字母'{letter}'(非起始)，原点在{other_side}侧")
                    return other_side

            print(f"    字母比较: {left_letter} vs {right_letter}")
            if left_letter < right_letter:
                return 'left'   # A < B，左侧起始
            else:
                return 'right'  # B > A，右侧起始

        else:  # number
            left_digits = ''.join(c for c in left_value if c.isdigit())
            right_digits = ''.join(c for c in right_value if c.isdigit())

            # 一侧无法提取数字，退化为单侧逻辑
            if not left_digits or not right_digits:
                recognized_side = 'right' if not left_digits else 'left'
                digits = right_digits if not left_digits else left_digits
                other_side = 'left' if recognized_side == 'right' else 'right'
                try:
                    num = int(digits)
                    if num == 1:
                        print(f"    → 仅{recognized_side}侧识别到有效数字'{num}'(起始标记)，原点在{recognized_side}侧")
                        return recognized_side
                    else:
                        print(f"    → 仅{recognized_side}侧识别到有效数字'{num}'(非起始)，原点在{other_side}侧")
                        return other_side
                except ValueError:
                    pass
                print(f"    ⚠ 双侧均无法提取有效数字，默认左侧")
                return 'left'

            left_num, right_num = int(left_digits), int(right_digits)
            print(f"    数字比较: {left_num} vs {right_num}")
            if left_num < right_num:
                return 'left'   # 1 < 4，左侧起始
            else:
                return 'right'  # 4 > 1，右侧起始
    
    def predict(self, image_path):
        """预测并计算原点"""
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"无法读取: {image_path}")

        img_height, img_width = img.shape[:2]

        # 自适应预处理（与训练保持一致）
        img_processed = self._preprocess(img)

        # YOLO检测（输入预处理后的图像）
        results = self.model(img_processed, conf=self.conf, verbose=False)
        
        result = results[0]

        if len(result.boxes) == 0:
            return {
                'image_path': str(image_path),
                'image_width': img_width,
                'image_height': img_height,
                'detected': False,
                'detections': [],
                'original_image': img,
                'preprocessed_image': img_processed
            }

        # 解析检测结果
        detections = []
        for i in range(len(result.boxes)):
            class_id = int(result.boxes.cls[i])
            conf = float(result.boxes.conf[i])
            bbox = result.boxes.xyxy[i].cpu().numpy()

            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2

            # OCR识别标记内容（使用预处理图，对比度更高，识别更准）
            text = None
            if class_id != 0:  # 不是中心标记
                text = self.extract_text_from_bbox(img_processed, bbox)

            detections.append({
                'class_id': class_id,
                'class_name': self.class_names[class_id],
                'confidence': conf,
                'bbox': bbox.tolist(),
                'center_x': float(center_x),
                'center_y': float(center_y),
                'text': text
            })

        # 计算原点
        origin_x, origin_y, positioning_type = self.calculate_origin(detections)

        return {
            'image_path': str(image_path),
            'image_width': img_width,
            'image_height': img_height,
            'detected': origin_x is not None,
            'positioning_type': positioning_type,
            'origin_x': origin_x,
            'origin_y': origin_y,
            'detections': detections,
            'original_image': img,          # 可视化用原图（未经预处理）
            'preprocessed_image': img_processed
        }
    
    def calculate_origin(self, detections):
        """
        从检测结果计算原点
        
        Returns:
            origin_x, origin_y, positioning_type
        """
        # 检查是否有中心标记
        center_marks = [d for d in detections if d['class_id'] == 0]
        if center_marks:
            # 情况1: 中心定位
            best = max(center_marks, key=lambda x: x['confidence'])
            print(f"  → 检测到中心标记")
            return best['center_x'], best['center_y'], 0
        
        # 检查边缘标记
        left_marks = [d for d in detections if d['class_id'] in [1, 3]]
        right_marks = [d for d in detections if d['class_id'] in [2, 4]]
        
        if left_marks and right_marks:
            # 情况2: 两侧都有标记
            best_left = max(left_marks, key=lambda x: x['confidence'])
            best_right = max(right_marks, key=lambda x: x['confidence'])
            
            # 确定类型
            left_type = 'letter' if best_left['class_id'] == 1 else 'number'
            right_type = 'letter' if best_right['class_id'] == 2 else 'number'
            
            print(f"  → 检测到边缘标记:")
            print(f"    左侧: {left_type} = '{best_left['text']}'")
            print(f"    右侧: {right_type} = '{best_right['text']}'")
            
            # 比较大小
            origin_side = self.compare_marks(
                best_left['text'],
                best_right['text'],
                left_type,
                right_type
            )
            
            print(f"    原点位置: {origin_side}")
            
            if origin_side == 'left':
                return best_left['center_x'], best_left['center_y'], 1
            else:
                return best_right['center_x'], best_right['center_y'], 1
        
        elif left_marks:
            # 只有左侧
            best = max(left_marks, key=lambda x: x['confidence'])
            print(f"  → 只检测到左侧标记")
            return best['center_x'], best['center_y'], 1
        
        elif right_marks:
            # 只有右侧
            best = max(right_marks, key=lambda x: x['confidence'])
            print(f"  → 只检测到右侧标记")
            return best['center_x'], best['center_y'], 1
        
        return None, None, None
    
    def visualize_result(self, result, save_path=None):
        """可视化"""
        if not result['detected']:
            print("  ✗ 未检测到原点")
            return
        
        img = result['original_image'].copy()
        
        # 绘制检测框和OCR结果
        for det in result['detections']:
            bbox = det['bbox']
            x1, y1, x2, y2 = map(int, bbox)
            
            # 不同类别不同颜色
            color = (0, 255, 0) if det['class_id'] == 0 else (255, 100, 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            
            # 标签
            label = f"{det['class_name']}"
            if det['text']:
                label += f" '{det['text']}'"
            label += f" {det['confidence']:.2f}"
            
            cv2.putText(img, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 绘制原点
        origin_x = int(result['origin_x'])
        origin_y = int(result['origin_y'])
        
        cv2.drawMarker(img, (origin_x, origin_y), (0, 0, 255), 
                      cv2.MARKER_CROSS, 50, 3)
        cv2.circle(img, (origin_x, origin_y), 30, (0, 255, 0), 2)
        
        # 坐标轴
        img_height, img_width = img.shape[:2]
        cv2.arrowedLine(img, (origin_x, origin_y), 
                       (min(origin_x + 200, img_width - 10), origin_y),
                       (0, 0, 255), 2, tipLength=0.1)
        cv2.arrowedLine(img, (origin_x, origin_y),
                       (origin_x, max(origin_y - 200, 10)),
                       (0, 255, 0), 2, tipLength=0.1)
        
        # 文字
        info = f"Type: {result['positioning_type']}, Origin: ({origin_x}, {origin_y})"
        cv2.putText(img, info, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        if save_path:
            cv2.imwrite(str(save_path), img)
    
    def predict_batch(self, image_dir, output_dir=None):
        """批量推理"""
        image_dir = Path(image_dir)
        print(f"\n批量推理目录: {image_dir}")
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
        image_files = []
        for ext in image_extensions:
            image_files.extend(image_dir.glob(f'*{ext}'))
            image_files.extend(image_dir.glob(f'*{ext.upper()}'))
        
        print(f"\n找到 {len(image_files)} 张图像")
        print("="*60)
        
        results = []
        success_count = 0
        
        for i, image_file in enumerate(image_files, 1):
            try:
                print(f"\n[{i}/{len(image_files)}] {image_file.name}")
                
                result = self.predict(image_file)
                results.append(result)
                
                if output_dir:
                    pre_path = output_dir / f"{image_file.stem}_preprocessed.png"
                    cv2.imwrite(str(pre_path), result['preprocessed_image'])

                if result['detected']:
                    print(f"  ✓ 类型: {result['positioning_type']}")
                    print(f"  ✓ 原点: ({result['origin_x']:.1f}, {result['origin_y']:.1f})")

                    if output_dir:
                        vis_path = output_dir / f"{image_file.stem}_result.png"
                        self.visualize_result(result, save_path=vis_path)

                    success_count += 1
                else:
                    print(f"  ✗ 未检测到")
                
            except Exception as e:
                print(f"  ✗ 失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 保存JSON
        if output_dir:
            json_path = output_dir / 'results.json'
            json_results = []
            for r in results:
                r_copy = r.copy()
                r_copy.pop('original_image', None)
                r_copy.pop('preprocessed_image', None)
                json_results.append(r_copy)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_results, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*60)
        print(f"成功: {success_count}/{len(image_files)}")
        print("="*60)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, required=True)
    parser.add_argument('--image', type=str)
    parser.add_argument('--image-dir', type=str)
    parser.add_argument('--output-dir', type=str)
    parser.add_argument('--conf', type=float, default=0.25)
    parser.add_argument('--no-ocr', action='store_true', help='禁用OCR')
    parser.add_argument('--no-preprocess', action='store_true', help='禁用自适应预处理（默认开启）')
    
    args = parser.parse_args()
    
    if not args.image and not args.image_dir:
        print("错误: 需要指定 --image 或 --image-dir")
        return
    
    print("="*60)
    print("YOLO检测 + OCR识别 + 原点计算")
    print("="*60)
    
    inference = YOLODetectionInference(
        args.model,
        args.conf,
        use_ocr=not args.no_ocr,
        use_adaptive_preprocessing=not args.no_preprocess
    )
    
    if args.image:
        result = inference.predict(args.image)
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            pre_path = output_dir / f"{Path(args.image).stem}_preprocessed.png"
            cv2.imwrite(str(pre_path), result['preprocessed_image'])
        if result['detected']:
            print(f"\n✓ 原点: ({result['origin_x']:.1f}, {result['origin_y']:.1f})")
            if args.output_dir:
                save_path = output_dir / f"{Path(args.image).stem}_result.png"
                inference.visualize_result(result, save_path=save_path)
        else:
            print("\n✗ 未检测到")
    
    elif args.image_dir:
        inference.predict_batch(args.image_dir, args.output_dir or './yolo_ocr_results')

if __name__ == '__main__':
    main()