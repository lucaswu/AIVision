import os
import sys
import cv2
import shutil
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Union
from tqdm import tqdm
from ultralytics import YOLO

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

current_script_path = os.path.abspath(__file__)
pj_dir = os.path.dirname(current_script_path)
convert_dir = os.path.dirname(pj_dir)
dataprocess_dir = os.path.dirname(convert_dir)
# 将 dataprocess 目录添加到 Python 搜索路径
sys.path.append(dataprocess_dir)

from utils import (
    read_yolo_labels,
    save_yolo_labels,
    denormalize_bbox,
    normalize_bbox,
    clip_polygon_to_window,
    create_directory_structure,
    read_dataset_yaml,
    update_dataset_yaml
)
from utils.trt_backend import load_yolo_model


ImageSource = Union[str, Path, np.ndarray]


class WeldROIDetector:
    """可复用的焊缝ROI检测器，封装YOLO推理和padding逻辑"""

    def __init__(self,
                 model_path: str,
                 roi_conf_threshold: float = 0.25,
                 roi_iou_threshold: float = 0.45,
                 padding_ratio: float = 0.1):
        self.model_path = model_path
        self.roi_conf_threshold = roi_conf_threshold
        self.roi_iou_threshold = roi_iou_threshold
        self.padding_ratio = padding_ratio

        print(f"加载ROI模型: {model_path}")
        self.model = load_yolo_model(model_path)

    def detect_boxes(self, image_source: ImageSource) -> List[Tuple[int, int, int, int]]:
        """
        运行YOLO模型检测ROI区域

        Args:
            image_source: 图像路径或numpy数组

        Returns:
            ROI边界框列表（x1, y1, x2, y2）
        """
        results = self.model(
            image_source,
            conf=self.roi_conf_threshold,
            iou=self.roi_iou_threshold,
            verbose=False
        )

        roi_boxes = []
        for result in results:
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                for box in boxes:
                    x1, y1, x2, y2 = box
                    roi_boxes.append((int(x1), int(y1), int(x2), int(y2)))

        return roi_boxes

    def apply_padding(self, x1: int, y1: int, x2: int, y2: int,
                      img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """
        为ROI区域添加padding并限制在图像范围内
        """
        if self.padding_ratio <= 0:
            return x1, y1, x2, y2

        width = x2 - x1
        height = y2 - y1

        pad_x = int(width * self.padding_ratio)
        pad_y = int(height * self.padding_ratio)

        x1_padded = max(0, x1 - pad_x)
        y1_padded = max(0, y1 - pad_y)
        x2_padded = min(img_width, x2 + pad_x)
        y2_padded = min(img_height, y2 + pad_y)

        return x1_padded, y1_padded, x2_padded, y2_padded

    def detect_with_padding(self, image_source: ImageSource,
                            image_shape: Optional[Tuple[int, int]] = None) -> List[Tuple[int, int, int, int]]:
        """
        检测ROI并应用padding

        Args:
            image_source: 图像路径或numpy数组
            image_shape: (height, width)，当image_source为路径时需要指定
        """
        boxes = self.detect_boxes(image_source)
        if not boxes:
            return boxes

        if image_shape is None:
            if isinstance(image_source, np.ndarray):
                img_height, img_width = image_source.shape[:2]
            else:
                raise ValueError("当 image_source 为路径时，必须提供 image_shape 以应用padding")
        else:
            img_height, img_width = image_shape

        return [
            self.apply_padding(x1, y1, x2, y2, img_width, img_height)
            for (x1, y1, x2, y2) in boxes
        ]


class YOLOROIExtractor:
    """YOLO ROI区域提取器（简化版：NOROI文件夹）"""

    def __init__(self,
                 input_dir: str,
                 output_dir: str,
                 model_path: str,
                 mode: str = 'det',
                 roi_conf_threshold: float = 0.25,
                 roi_iou_threshold: float = 0.45,
                 padding_ratio: float = 0.1):
        """
        初始化ROI提取器

        Args:
            input_dir: 输入YOLO数据集目录
            output_dir: 输出YOLO数据集目录
            model_path: YOLO模型权重路径
            mode: 'det'(检测) 或 'seg'(分割)
            roi_conf_threshold: ROI检测置信度阈值
            roi_iou_threshold: ROI检测IOU阈值
            padding_ratio: ROI区域padding比例
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_path = model_path
        self.mode = mode
        self.roi_conf_threshold = roi_conf_threshold
        self.roi_iou_threshold = roi_iou_threshold
        self.padding_ratio = padding_ratio

        # 加载YOLO模型（复用可独立调用的WeldROIDetector）
        self.roi_detector = WeldROIDetector(
            model_path=model_path,
            roi_conf_threshold=roi_conf_threshold,
            roi_iou_threshold=roi_iou_threshold,
            padding_ratio=padding_ratio
        )
        self.model = self.roi_detector.model  # 向后兼容

        # 创建输出目录结构
        create_directory_structure(self.output_dir)

        # 创建NOROI文件夹（简化：直接存放图像）
        self.no_roi_dir = self.output_dir / "NOROI"
        self.no_roi_dir.mkdir(parents=True, exist_ok=True)
        print(f"  - 未检测到ROI目录: {self.no_roi_dir}")

        # 统计信息
        self.total_processed = 0
        self.total_roi_found = 0
        self.total_labels_adjusted = 0
        self.total_no_roi_images = 0  # 未检测到ROI的图片数量
        self.no_roi_files = []  # 记录未检测到ROI的文件名列表

        print(f"YOLO ROI提取器初始化:")
        print(f"  - 输入目录: {input_dir}")
        print(f"  - 输出目录: {output_dir}")
        print(f"  - 模式: {mode}")
        print(f"  - ROI置信度阈值: {roi_conf_threshold}")
        print(f"  - ROI IOU阈值: {roi_iou_threshold}")
        print(f"  - Padding比例: {padding_ratio}")

    def _detect_roi(self, image_path: str) -> List[Tuple[int, int, int, int]]:
        """
        使用YOLO模型检测ROI区域

        Args:
            image_path: 图像路径

        Returns:
            ROI边界框列表 [(x1, y1, x2, y2), ...]
        """
        return self.roi_detector.detect_boxes(image_path)

    def _add_padding(self, x1: int, y1: int, x2: int, y2: int,
                    img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """
        为ROI区域添加padding

        Args:
            x1, y1, x2, y2: ROI边界框
            img_width, img_height: 图像尺寸

        Returns:
            添加padding后的边界框
        """
        return self.roi_detector.apply_padding(x1, y1, x2, y2, img_width, img_height)

    def _process_detection_label(self, label: list, roi_x1: int, roi_y1: int,
                                roi_x2: int, roi_y2: int,
                                img_width: int, img_height: int,
                                cropped_width: int, cropped_height: int) -> Optional[list]:
        """
        处理检测模式的标签

        Args:
            label: [class_id, x_center, y_center, width, height]
            roi_*: ROI区域像素坐标
            img_*: 原始图像尺寸
            cropped_*: 裁剪后图像尺寸

        Returns:
            调整后的标签或None
        """
        class_id = int(label[0])

        # 转换为像素坐标
        x1, y1, x2, y2 = denormalize_bbox(
            label[1], label[2], label[3], label[4],
            img_width, img_height
        )

        # 计算与ROI的交集
        intersect_x1 = max(x1, roi_x1)
        intersect_y1 = max(y1, roi_y1)
        intersect_x2 = min(x2, roi_x2)
        intersect_y2 = min(y2, roi_y2)

        # 如果没有交集
        if intersect_x1 >= intersect_x2 or intersect_y1 >= intersect_y2:
            return None

        # 转换为相对于裁剪图像的坐标
        new_x1 = max(0, intersect_x1 - roi_x1)
        new_y1 = max(0, intersect_y1 - roi_y1)
        new_x2 = min(cropped_width, intersect_x2 - roi_x1)
        new_y2 = min(cropped_height, intersect_y2 - roi_y1)

        # 转换回归一化坐标
        new_x_center, new_y_center, new_width, new_height = normalize_bbox(
            new_x1, new_y1, new_x2, new_y2, cropped_width, cropped_height
        )

        # 过滤太小的边界框
        if new_width <= 0.01 or new_height <= 0.01:
            return None

        return [class_id, new_x_center, new_y_center, new_width, new_height]

    def _process_segmentation_label(self, label: list, roi_x1: int, roi_y1: int,
                                   roi_x2: int, roi_y2: int,
                                   img_width: int, img_height: int,
                                   cropped_width: int, cropped_height: int) -> Optional[list]:
        """
        处理分割模式的标签

        Args:
            label: [class_id, x1, y1, x2, y2, ...]
            roi_*: ROI区域像素坐标
            img_*: 原始图像尺寸
            cropped_*: 裁剪后图像尺寸

        Returns:
            调整后的标签或None
        """
        class_id = int(label[0])
        points = label[1:]

        # 转换为像素坐标并调整到ROI区域
        new_points = []
        for i in range(0, len(points), 2):
            if i + 1 < len(points):
                x = points[i] * img_width
                y = points[i + 1] * img_height

                # 调整到ROI区域坐标系
                x_adjusted = x - roi_x1
                y_adjusted = y - roi_y1

                # 归一化到裁剪图像
                new_x = x_adjusted / cropped_width
                new_y = y_adjusted / cropped_height

                new_points.extend([new_x, new_y])

        # 裁剪多边形到窗口内
        clipped_points = clip_polygon_to_window(new_points, (0.0, 0.0, 1.0, 1.0))

        # 检查是否有效
        if len(clipped_points) < 6:  # 至少3个点
            return None

        # 计算多边形面积，过滤太小的
        x_coords = clipped_points[::2]
        y_coords = clipped_points[1::2]

        if not x_coords or not y_coords:
            return None

        poly_width = max(x_coords) - min(x_coords)
        poly_height = max(y_coords) - min(y_coords)

        if poly_width <= 0.01 or poly_height <= 0.01:
            return None

        return [class_id] + clipped_points

    def _save_no_roi_image(self, image_path: Path):
        """
        保存未检测到ROI的图片到NOROI文件夹（简化版）

        Args:
            image_path: 原始图像路径
        """
        # 目标路径（直接放在NOROI文件夹下）
        target_image_path = self.no_roi_dir / image_path.name

        # 复制图像
        shutil.copy2(str(image_path), str(target_image_path))

        # 更新统计
        self.total_no_roi_images += 1
        self.no_roi_files.append(image_path.name)

        print(f"  → 未检测到ROI，已保存到: NOROI/{image_path.name}")

    def _process_single_image(self, image_path: Path, label_path: Path,
                            split_type: str):
        """
        处理单张图像

        Args:
            image_path: 图像路径
            label_path: 标签路径
            split_type: 'train' 或 'val'
        """
        # 读取图像
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"警告: 无法读取图像 {image_path}")
            return

        img_height, img_width = img.shape[:2]

        # 检测ROI区域
        roi_boxes = self._detect_roi(str(image_path))

        # 如果没有检测到ROI，保存到NOROI文件夹
        if not roi_boxes:
            self._save_no_roi_image(image_path)
            return

        self.total_roi_found += len(roi_boxes)

        # 读取原始标签
        if label_path.exists():
            original_labels = read_yolo_labels(str(label_path), self.mode)
        else:
            original_labels = []

        # 处理每个ROI区域
        base_name = image_path.stem
        for roi_idx, (roi_x1, roi_y1, roi_x2, roi_y2) in enumerate(roi_boxes):
            # 添加padding
            roi_x1, roi_y1, roi_x2, roi_y2 = self._add_padding(
                roi_x1, roi_y1, roi_x2, roi_y2, img_width, img_height
            )

            # 裁剪图像
            cropped_img = img[roi_y1:roi_y2, roi_x1:roi_x2]
            cropped_height, cropped_width = cropped_img.shape[:2]

            # 生成新文件名
            new_img_name = f"{base_name}_roi_{roi_idx}.jpg"
            new_label_name = f"{base_name}_roi_{roi_idx}.txt"

            # 保存裁剪后的图像
            output_img_path = self.output_dir / 'images' / split_type / new_img_name
            cv2.imwrite(str(output_img_path), cropped_img,
                       [cv2.IMWRITE_JPEG_QUALITY, 95])

            # 处理标签
            new_labels = []
            for label in original_labels:
                if self.mode == 'det':
                    new_label = self._process_detection_label(
                        label, roi_x1, roi_y1, roi_x2, roi_y2,
                        img_width, img_height, cropped_width, cropped_height
                    )
                else:  # seg mode
                    new_label = self._process_segmentation_label(
                        label, roi_x1, roi_y1, roi_x2, roi_y2,
                        img_width, img_height, cropped_width, cropped_height
                    )

                if new_label is not None:
                    new_labels.append(new_label)
                    self.total_labels_adjusted += 1

            # 保存新的标签文件
            output_label_path = self.output_dir / 'labels' / split_type / new_label_name
            save_yolo_labels(new_labels, str(output_label_path), self.mode)

        self.total_processed += 1

    def process_dataset(self):
        """处理整个数据集"""
        print(f"开始处理数据集...")

        # 处理训练集和验证集
        for split_type in ['train', 'val']:
            image_dir = self.input_dir / 'images' / split_type
            label_dir = self.input_dir / 'labels' / split_type

            if not image_dir.exists():
                print(f"跳过{split_type}（不存在）")
                continue

            # 获取所有图像文件
            image_files = list(image_dir.glob('*.jpg')) + \
                         list(image_dir.glob('*.jpeg')) + \
                         list(image_dir.glob('*.png')) + \
                         list(image_dir.glob('*.tif')) + \
                         list(image_dir.glob('*.bmp'))

            print(f"\n处理{split_type}集: {len(image_files)}张图像")

            # 处理每张图像
            for image_path in tqdm(image_files, desc=f"处理{split_type}"):
                # 构造对应的标签文件路径
                label_path = label_dir / f"{image_path.stem}.txt"

                self._process_single_image(image_path, label_path, split_type)

        # 复制并更新dataset.yaml
        self._update_dataset_yaml()

        # 为未检测到ROI的图片创建简单的说明文件
        self._create_no_roi_readme()

        # 打印统计信息
        self._print_statistics()

    def _create_no_roi_readme(self):
        """创建NOROI目录的说明文件（简化版）"""
        if self.total_no_roi_images > 0:
            readme_path = self.no_roi_dir / "README.txt"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write("未检测到ROI的图片\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"总计: {self.total_no_roi_images} 张图片\n\n")
                f.write("检测参数:\n")
                f.write(f"  - 模型: {self.model_path}\n")
                f.write(f"  - 置信度阈值: {self.roi_conf_threshold}\n")
                f.write(f"  - IOU阈值: {self.roi_iou_threshold}\n\n")
                f.write("文件列表:\n")
                for idx, filename in enumerate(self.no_roi_files, 1):
                    f.write(f"  {idx}. {filename}\n")

    def _update_dataset_yaml(self):
        """更新dataset.yaml文件"""
        input_yaml = self.input_dir / 'dataset.yaml'
        output_yaml = self.output_dir / 'dataset.yaml'

        if input_yaml.exists():
            yaml_data = read_dataset_yaml(str(input_yaml))

            # 更新路径
            yaml_data['train'] = str(self.output_dir / 'images' / 'train')
            yaml_data['val'] = str(self.output_dir / 'images' / 'val')

            # 添加ROI提取信息
            yaml_data['roi_extraction'] = {
                'model_path': str(self.model_path),
                'conf_threshold': self.roi_conf_threshold,
                'iou_threshold': self.roi_iou_threshold,
                'padding_ratio': self.padding_ratio,
                'no_roi_images': self.total_no_roi_images
            }

            # 保存更新后的yaml
            update_dataset_yaml(str(output_yaml), yaml_data)

            print(f"dataset.yaml已保存到: {output_yaml}")
        else:
            print(f"警告: 未找到{input_yaml}")

    def _print_statistics(self):
        """打印统计信息"""
        print(f"\n{'='*60}")
        print(f"✅ ROI提取完成！")
        print(f"📊 统计信息:")
        print(f"  - 处理图像数: {self.total_processed}")
        print(f"  - 检测到ROI的图像数: {self.total_processed - self.total_no_roi_images}")
        print(f"  - 未检测到ROI的图像数: {self.total_no_roi_images}")
        print(f"  - 检测到的ROI总数: {self.total_roi_found}")
        print(f"  - 调整的标签数: {self.total_labels_adjusted}")
        if self.total_processed > 0:
            detection_rate = (self.total_processed - self.total_no_roi_images) / self.total_processed * 100
            print(f"  - ROI检测率: {detection_rate:.1f}%")
            if self.total_processed - self.total_no_roi_images > 0:
                avg_roi = self.total_roi_found / (self.total_processed - self.total_no_roi_images)
                print(f"  - 平均每张图像ROI数（仅计算有ROI的）: {avg_roi:.2f}")
        print(f"  - 输出目录: {self.output_dir}")
        if self.total_no_roi_images > 0:
            print(f"  - 未检测到ROI的图片保存在: {self.no_roi_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='使用YOLO模型从数据集中提取ROI区域（简化版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本使用（检测模式）
  python yolo_roi_extractor_simplified.py --input_dir ./dataset --output_dir ./roi_dataset --model_path ./weights/best.pt
  
  # 分割模式
  python yolo_roi_extractor_simplified.py --input_dir ./dataset --output_dir ./roi_dataset --model_path ./weights/best.pt --mode seg
  
  # 调整ROI检测阈值
  python yolo_roi_extractor_simplified.py --input_dir ./dataset --output_dir ./roi_dataset --model_path ./weights/best.pt --roi_conf 0.5 --roi_iou 0.7
  
  # 增加ROI区域padding（20%）
  python yolo_roi_extractor_simplified.py --input_dir ./dataset --output_dir ./roi_dataset --model_path ./weights/best.pt --padding 0.2

注意：
  - 未检测到ROI的图片会被直接保存到输出目录下的"NOROI"文件夹中
  - 只保存原始图像，不保存标签文件
  - 不区分train/val，所有未检测到ROI的图片都放在同一个文件夹
  - 包含一个README.txt文件列出所有未检测到ROI的图片文件名
        """
    )

    parser.add_argument('--input_dir', type=str, required=True,
                       help='输入YOLO数据集目录')
    parser.add_argument('--output_dir', type=str, required=True,
                       help='输出ROI数据集目录')
    parser.add_argument('--model_path', type=str, required=True,
                       help='YOLO模型权重路径（.pt文件）')
    parser.add_argument('--mode', type=str, choices=['det', 'seg'], default='det',
                       help='数据集模式: det(检测) 或 seg(分割) (默认: det)')
    parser.add_argument('--roi_conf', type=float, default=0.25,
                       help='ROI检测置信度阈值 (默认: 0.25)')
    parser.add_argument('--roi_iou', type=float, default=0.45,
                       help='ROI检测IOU阈值 (默认: 0.45)')
    parser.add_argument('--padding', type=float, default=0.1,
                       help='ROI区域padding比例 (默认: 0.1)')

    args = parser.parse_args()

    # 创建ROI提取器
    extractor = YOLOROIExtractor(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model_path=args.model_path,
        mode=args.mode,
        roi_conf_threshold=args.roi_conf,
        roi_iou_threshold=args.roi_iou,
        padding_ratio=args.padding
    )

    # 处理数据集
    extractor.process_dataset()


if __name__ == '__main__':
    main()
