#!/usr/bin/env python3
"""
使用PaddleOCR进行字符高度精确测量
通过字符分割技术实现单个字符的高度测量

安装依赖：
pip install paddlepaddle paddleocr opencv-python matplotlib numpy Pillow
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path


class CharHeightDetector:
    def __init__(self, use_angle_cls=True, lang='ch', use_gpu=False):
        """
        初始化检测器

        Args:
            use_angle_cls: 是否使用角度分类
            lang: 语言 'ch'中文, 'en'英文
            use_gpu: 是否使用GPU
        """
        self.ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=lang,
            det_db_thresh=0.3,  # 检测阈值
            det_db_box_thresh=0.5,
            det_db_unclip_ratio=1.5  # 减小扩张比例
        )

    def extract_single_chars(self, img, text_box, text_content):
        """
        从文本框中提取单个字符的高度

        Args:
            img: 原始图片
            text_box: 文本框坐标
            text_content: 识别的文本内容

        Returns:
            char_heights: 每个字符的高度列表
        """
        # 获取文本框的最小外接矩形
        pts = np.array(text_box, dtype=np.float32)
        rect = cv2.minAreaRect(pts)
        box = cv2.boxPoints(rect)
        box = np.int0(box)

        # 计算旋转角度
        width = int(rect[1][0])
        height = int(rect[1][1])
        angle = rect[2]

        if width < height:
            angle = angle - 90
            width, height = height, width

        # 获取旋转矩阵并矫正图像
        center = (int(rect[0][0]), int(rect[0][1]))
        M = cv2.getRotationMatrix2D(center, angle, 1)

        # 应用旋转
        rotated = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]))

        # 裁剪文本区域
        cropped = cv2.getRectSubPix(rotated, (width, height), center)

        # 预处理图像
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        # 使用OTSU二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 使用连通组件分析分割字符
        char_data = self.segment_characters_by_components(binary, text_content)

        return char_data, cropped, binary

    def segment_characters_by_components(self, binary_img, text_content):
        """
        使用连通组件分析分割字符

        Args:
            binary_img: 二值化图像
            text_content: 文本内容

        Returns:
            char_data: 字符数据列表
        """
        # 连通组件分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary_img, connectivity=8
        )

        char_data = []
        valid_components = []

        # 过滤有效的字符组件
        img_height, img_width = binary_img.shape
        for i in range(1, num_labels):  # 跳过背景
            x, y, w, h, area = stats[i]

            # 过滤条件：面积、宽高比等
            if area > 20 and h > 5 and w > 2:  # 调整阈值以适应你的图片
                if h < img_height * 0.95:  # 排除整行的组件
                    valid_components.append({
                        'id': len(valid_components) + 1,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'area': area,
                        'centroid': centroids[i]
                    })

        # 按x坐标排序（从左到右）
        valid_components.sort(key=lambda c: c['x'])

        # 尝试匹配字符
        if len(valid_components) > 0 and text_content:
            chars = list(text_content)
            # 简单匹配：假设组件数量与字符数量相近
            for i, comp in enumerate(valid_components):
                if i < len(chars):
                    comp['text'] = chars[i]
                else:
                    comp['text'] = '?'
                char_data.append(comp)
        else:
            char_data = valid_components

        return char_data

    def detect_and_measure(self, image_path):
        """
        检测并测量字符高度

        Args:
            image_path: 图片路径

        Returns:
            all_char_data: 所有字符的数据
        """
        # 读取图片
        img = cv2.imread(image_path)

        # OCR检测
        result = self.ocr.predict(image_path)

        all_char_data = []
        line_data = []

        if result and result[0]:
            for idx, line in enumerate(result[0]):
                bbox = line[0]
                text = line[1][0]
                confidence = line[1][1]

                # 提取单个字符
                char_data, cropped, binary = self.extract_single_chars(img, bbox, text)

                # 保存行信息
                line_info = {
                    'line_id': idx + 1,
                    'bbox': bbox,
                    'text': text,
                    'confidence': confidence,
                    'char_data': char_data,
                    'cropped_img': cropped,
                    'binary_img': binary
                }
                line_data.append(line_info)

                # 收集所有字符数据
                for char in char_data:
                    char['line_id'] = idx + 1
                    all_char_data.append(char)

        return all_char_data, line_data, result


def visualize_results(image_path, all_char_data, line_data, save_dir='output'):
    """
    可视化检测结果
    """
    # 创建输出目录
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # 读取原图
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 创建主图
    fig = plt.figure(figsize=(20, 12))

    # 1. 原图
    ax1 = plt.subplot(2, 3, 1)
    ax1.imshow(img_rgb)
    ax1.set_title('原始图片', fontsize=12)
    ax1.axis('off')

    # 2. 带标注的原图
    ax2 = plt.subplot(2, 3, 2)
    img_annotated = img_rgb.copy()

    # 在原图上绘制文本框
    for line in line_data:
        bbox = np.array(line['bbox'], np.int32)
        cv2.polylines(img_annotated, [bbox], True, (0, 255, 0), 2)

        # 标注行号
        x, y = bbox[0]
        cv2.putText(img_annotated, f"Line {line['line_id']}",
                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    ax2.imshow(img_annotated)
    ax2.set_title(f'检测到 {len(line_data)} 行文本', fontsize=12)
    ax2.axis('off')

    # 3. 字符高度分布
    ax3 = plt.subplot(2, 3, 3)
    if all_char_data:
        heights = [c['height'] for c in all_char_data]
        ax3.hist(heights, bins=30, edgecolor='black', alpha=0.7, color='blue')
        ax3.axvline(np.mean(heights), color='red', linestyle='--',
                    label=f'平均: {np.mean(heights):.1f}px')
        ax3.axvline(np.median(heights), color='green', linestyle='--',
                    label=f'中位数: {np.median(heights):.1f}px')
        ax3.set_xlabel('字符高度 (像素)')
        ax3.set_ylabel('频次')
        ax3.set_title(f'字符高度分布 (共{len(all_char_data)}个字符)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    # 4-6. 显示前三行的字符分割结果
    for i in range(min(3, len(line_data))):
        ax = plt.subplot(2, 3, 4 + i)
        line = line_data[i]

        # 创建可视化图像
        vis_img = cv2.cvtColor(line['binary_img'], cv2.COLOR_GRAY2RGB)

        # 在二值图上绘制字符边界框
        for char in line['char_data']:
            x, y, w, h = char['x'], char['y'], char['width'], char['height']
            cv2.rectangle(vis_img, (x, y), (x + w, y + h), (0, 255, 0), 1)

            # 标注字符和高度
            label = f"{char.get('text', '?')}:{h}px"
            cv2.putText(vis_img, label, (x, y - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)

        ax.imshow(vis_img)
        ax.set_title(f"行{line['line_id']}: {line['text'][:15]}...", fontsize=10)
        ax.axis('off')

    plt.tight_layout()

    # 保存图表
    save_path = os.path.join(save_dir, 'analysis_result.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"分析图表已保存到: {save_path}")

    plt.show()


def create_detailed_report(image_path, all_char_data, line_data, save_dir='output'):
    """
    创建详细的字符高度报告
    """
    # 创建输出目录
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # 读取原图
    img = cv2.imread(image_path)
    height, width = img.shape[:2]

    # 生成详细标注图
    img_detailed = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 为每个字符生成唯一颜色
    colors = plt.cm.rainbow(np.linspace(0, 1, len(all_char_data)))
    colors = (colors[:, :3] * 255).astype(int)

    # 在原图上标注每个字符
    char_id = 0
    for line in line_data:
        # 先画整行的边界框
        bbox = np.array(line['bbox'], np.int32)
        cv2.polylines(img_detailed, [bbox], True, (0, 0, 255), 1)

        # 获取该行的变换矩阵（用于将字符坐标映射回原图）
        pts = np.array(line['bbox'], dtype=np.float32)
        rect = cv2.minAreaRect(pts)
        angle = rect[2]
        center = (int(rect[0][0]), int(rect[0][1]))

        # 在每个字符位置标注高度
        for char in line['char_data']:
            if char_id < len(colors):
                # 简单标注字符高度值
                text = f"{char['height']:.0f}"
                pos = (int(bbox[0][0] + char['x'] * 0.3),
                       int(bbox[0][1] - 5))

                cv2.putText(img_detailed, text, pos,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                            colors[char_id].tolist(), 1)
                char_id += 1

    # 保存详细标注图
    detail_path = os.path.join(save_dir, 'detailed_annotation.jpg')
    cv2.imwrite(detail_path, cv2.cvtColor(img_detailed, cv2.COLOR_RGB2BGR))
    print(f"详细标注图已保存到: {detail_path}")

    # 生成统计报告
    report_path = os.path.join(save_dir, 'height_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("字符高度检测报告\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"图片信息:\n")
        f.write(f"  文件: {image_path}\n")
        f.write(f"  尺寸: {width} x {height} 像素\n\n")

        f.write(f"检测结果:\n")
        f.write(f"  检测到文本行数: {len(line_data)}\n")
        f.write(f"  检测到字符总数: {len(all_char_data)}\n\n")

        if all_char_data:
            heights = [c['height'] for c in all_char_data]
            f.write(f"字符高度统计:\n")
            f.write(f"  最小高度: {min(heights):.2f} px\n")
            f.write(f"  最大高度: {max(heights):.2f} px\n")
            f.write(f"  平均高度: {np.mean(heights):.2f} px\n")
            f.write(f"  中位数: {np.median(heights):.2f} px\n")
            f.write(f"  标准差: {np.std(heights):.2f} px\n\n")

            # 按行统计
            f.write("按行统计:\n")
            for line in line_data:
                if line['char_data']:
                    line_heights = [c['height'] for c in line['char_data']]
                    f.write(f"  行{line['line_id']}: {line['text'][:20]}...\n")
                    f.write(f"    字符数: {len(line['char_data'])}\n")
                    f.write(f"    平均高度: {np.mean(line_heights):.2f} px\n")
                    f.write(f"    高度范围: {min(line_heights):.0f}-{max(line_heights):.0f} px\n")

            # 详细字符信息
            f.write("\n" + "=" * 60 + "\n")
            f.write("字符详细信息:\n")
            f.write("=" * 60 + "\n")
            f.write(f"{'行号':<6} {'字符':<8} {'高度(px)':<10} {'宽度(px)':<10}\n")
            f.write("-" * 40 + "\n")

            for char in all_char_data:
                f.write(f"{char['line_id']:<6} "
                        f"{char.get('text', '?'):<8} "
                        f"{char['height']:<10.1f} "
                        f"{char['width']:<10.1f}\n")

    print(f"检测报告已保存到: {report_path}")


def main():
    """
    主函数
    """
    # 配置参数
    image_path = "../data/input/img_2.png"  # 修改为你的图片路径
    output_dir = "../output"
    use_gpu = False

    # 检查图片
    if not os.path.exists(image_path):
        print(f"错误: 找不到图片 - {image_path}")
        return

    print("=" * 60)
    print("PaddleOCR 字符高度精确测量工具")
    print("=" * 60)

    try:
        # 初始化检测器
        print("初始化检测器...")
        detector = CharHeightDetector(
            use_angle_cls=True,
            lang='ch',  # 中文，如果是英文改为'en'
            use_gpu=use_gpu
        )

        # 执行检测
        print("正在检测和测量字符...")
        all_char_data, line_data, ocr_result = detector.detect_and_measure(image_path)

        if not line_data:
            print("未检测到文本")
            return

        print(f"检测完成!")
        print(f"  - 检测到 {len(line_data)} 行文本")
        print(f"  - 共分割出 {len(all_char_data)} 个字符")

        if all_char_data:
            heights = [c['height'] for c in all_char_data]
            print(f"  - 平均字符高度: {np.mean(heights):.2f} px")
            print(f"  - 高度范围: {min(heights):.0f}-{max(heights):.0f} px")

        # 可视化结果
        print("\n生成可视化结果...")
        visualize_results(image_path, all_char_data, line_data, output_dir)

        # 生成详细报告
        print("生成详细报告...")
        create_detailed_report(image_path, all_char_data, line_data, output_dir)

        print(f"\n所有结果已保存到 '{output_dir}' 目录")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()