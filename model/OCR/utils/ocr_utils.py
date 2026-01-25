# ocr_utils.py - OCR识别通用工具模块
"""
焊缝X光底片OCR识别通用工具函数
包含图像处理、文本分类、标注绘制等通用功能
"""

import re
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import Dict, List, Tuple, Optional, Union


def classify_text(text: str) -> Dict:
    """
    根据文本内容分类并映射到对应字段

    Args:
        text: 待分类的文本

    Returns:
        包含分类结果的字典
    """
    # 基于正则表达式的字段分类
    patterns = {
        '检测部件代号': r'\d+[SR]\d+',  # 匹配 4S9 或 4R11
        '焊道号_片号': r'\d*[+-]\d+[A-Z]?',  # 如 66+2Y，28+3
        '像质计灵敏度': r'[FE]\s*(\d{2})\s*[JB]',  # 匹配 F13J, E12B 等，捕获中间的2位数字
        '管道规格': r'\d+[Xx×]\d+',  # 如 57X12, 57×12
    }

    # 清理文本（去除多余空格但保留必要的）
    clean_text = text.strip()

    # 存储所有匹配到的字段
    matched_fields = []

    for field, pattern in patterns.items():
        if field == '像质计灵敏度':
            # 特殊处理像质计灵敏度，需要提取捕获组
            matches = re.finditer(pattern, clean_text.upper())
            for match_obj in matches:
                field_info = {
                    '字段类型': field,
                    '匹配内容': match_obj.group(0),
                    '灵敏度值': match_obj.group(1)  # 直接获取捕获的2位数字
                }
                matched_fields.append(field_info)
        else:
            # 其他字段使用findall
            matches = re.findall(pattern, clean_text.upper())

            for match in matches:
                field_info = {'字段类型': field, '匹配内容': match}

                if field == '焊道号_片号':
                    # 进一步解析焊道号和片号（支持 + 或 - 分隔）
                    sep = '+' if '+' in match else '-' if '-' in match else None
                    if sep:
                        parts = match.split(sep)
                        if len(parts) >= 2:
                            field_info['焊道号'] = parts[0]
                            field_info['片号'] = parts[1]

                elif field == '管道规格':
                    # 解析管道规格 - 支持X和×分隔符
                    specs = re.split(r'[Xx×]', match)
                    if len(specs) == 2:
                        field_info['外径'] = specs[0][-2:] if len(specs[0]) >= 2 else specs[0]
                        field_info['壁厚'] = specs[1][0]

                elif field == '检测部件代号':
                    field_info['值'] = match

                matched_fields.append(field_info)

    # 返回结果
    if matched_fields:
        return {
            '原始文本': text,
            '匹配字段': matched_fields
        }
    else:
        return {
            '原始文本': text,
            '匹配字段': [],
            '字段类型': '未分类'
        }


def process_image_for_ocr(img_path: str, max_size: int = 1920) -> Tuple[np.ndarray, Image.Image, float]:
    """
    预处理图片用于OCR识别

    Args:
        img_path: 图片路径
        max_size: 最大边长限制

    Returns:
        (numpy数组, PIL图像对象, 缩放比例)
    """
    # 检查文件存在
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"文件不存在: {img_path}")

    # 使用PIL读取
    img = Image.open(img_path)

    # 确保是RGB模式
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # 获取尺寸
    w, h = img.size

    # 判断是否需要resize
    max_edge = max(w, h)
    if max_edge > max_size:
        scale = max_size / max_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        scale = 1.0

    # 转换为numpy数组
    img_array = np.array(img)

    return img_array, img, scale


def draw_annotations(image: Image.Image,
                     ocr_results: List[Dict],
                     classified_results: List[Dict],
                     scale: float = 1.0,
                     font_path: Optional[str] = None) -> Image.Image:
    """
    在图片上绘制半透明标注

    Args:
        image: PIL图片对象
        ocr_results: OCR识别结果
        classified_results: 分类结果
        scale: 图片缩放比例
        font_path: 字体文件路径（可选）

    Returns:
        标注后的图片
    """
    # 创建RGBA图像用于半透明绘制
    img_rgba = image.convert('RGBA')

    # 创建透明图层
    overlay = Image.new('RGBA', img_rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text_overlay = Image.new('RGBA', img_rgba.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_overlay)

    # 动态调整字体大小和线宽
    img_width, img_height = img_rgba.size
    img_size = max(img_width, img_height)

    font_size_large = max(16, int(img_size * 0.02))
    font_size_small = max(12, int(img_size * 0.015))
    line_width = max(2, int(img_size * 0.003))

    # 加载字体
    if font_path and os.path.exists(font_path):
        try:
            font = ImageFont.truetype(font_path, size=font_size_large)
            font_small = ImageFont.truetype(font_path, size=font_size_small)
        except:
            font = ImageFont.load_default()
            font_small = font
    else:
        # 尝试常见中文字体路径
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "simhei.ttf"
        ]

        font_loaded = False
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size=font_size_large)
                    font_small = ImageFont.truetype(path, size=font_size_small)
                    font_loaded = True
                    break
                except:
                    continue

        if not font_loaded:
            font = ImageFont.load_default()
            font_small = font

    # 颜色方案
    colors = {
        '检测部件代号': (255, 0, 0),  # 红色
        '焊道号_片号': (0, 255, 0),  # 绿色
        '像质计灵敏度': (0, 0, 255),  # 蓝色
        '管道规格': (255, 255, 0),  # 黄色
        '未分类': (128, 128, 128)  # 灰色
    }

    text_colors = {
        '检测部件代号': (255, 100, 100),  # 浅红色
        '焊道号_片号': (100, 255, 100),  # 浅绿色
        '像质计灵敏度': (100, 100, 255),  # 浅蓝色
        '管道规格': (255, 255, 100),  # 浅黄色
        '未分类': (200, 200, 200)  # 浅灰色
    }

    # PaddleOCR list format support
    # ocr_results is [[ [box, (text, score)], ... ]]
    if ocr_results and len(ocr_results) > 0 and ocr_results[0]:
        lines = ocr_results[0]
        for i, line in enumerate(lines):
            if i >= len(classified_results):
                break
            
            # line structure: [box, (text, score)]
            # box is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            poly = line[0]
            text = line[1][0]
            # score = line[1][1]

            classification = classified_results[i]

            # 获取矩形框顶点
            points = [(int(p[0]), int(p[1])) for p in poly]

            # 确定字段类型和颜色
            if classification.get('字段类型') == '未分类':
                field_type = '未分类'
                color = colors['未分类']
                text_color = text_colors['未分类']
            elif classification['匹配字段']:
                field_type = classification['匹配字段'][0]['字段类型']
                color = colors.get(field_type, colors['未分类'])
                text_color = text_colors.get(field_type, text_colors['未分类'])
            else:
                field_type = '未分类'
                color = colors['未分类']
                text_color = text_colors['未分类']

            # 绘制矩形框
            draw.polygon(points, outline=color + (255,), width=line_width)

            # 准备标注文本
            label_lines = [f"原文: {text}"]

            if classification['匹配字段']:
                for field in classification['匹配字段']:
                    field_label = f"{field['字段类型']}: "
                    if field['字段类型'] == '焊道号_片号':
                        field_label += f"焊道{field.get('焊道号', '')}/片{field.get('片号', '')}"
                    elif field['字段类型'] == '像质计灵敏度':
                        field_label += f"值={field.get('灵敏度值', '')}"
                    elif field['字段类型'] == '管道规格':
                        field_label += f"外径{field.get('外径', '')}/壁厚{field.get('壁厚', '')}"
                    elif field['字段类型'] == '检测部件代号':
                        field_label += field.get('值', '')
                    label_lines.append(field_label)
            else:
                label_lines.append("未分类")

            # 计算文本位置
            text_x = min([p[0] for p in points])
            text_y = min([p[1] for p in points]) - int(img_size * 0.005)

            if text_y < 0:
                text_y = max([p[1] for p in points]) + int(img_size * 0.005)

            # 绘制半透明文本
            y_offset = 0
            for line in label_lines:
                bbox = text_draw.textbbox((text_x, text_y + y_offset), line, font=font_small)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                padding = max(2, int(font_size_small * 0.1))

                if text_x + text_width + padding > img_width:
                    text_x = img_width - text_width - padding

                # 半透明背景
                text_draw.rectangle(
                    [text_x - padding, text_y + y_offset - padding,
                     text_x + text_width + padding, text_y + y_offset + text_height + padding],
                    fill=(0, 0, 0, 80)
                )

                # 半透明文本
                text_draw.text((text_x, text_y + y_offset), line,
                               fill=text_color + (200,), font=font_small)

                y_offset += text_height + padding * 2

    # 合并图层
    img_with_annotations = Image.alpha_composite(img_rgba, overlay)
    img_with_annotations = Image.alpha_composite(img_with_annotations, text_overlay)

    return img_with_annotations.convert('RGB')


def extract_field_statistics(classified_results: List[Dict]) -> Dict[str, List[str]]:
    """
    提取并统计识别结果中的各类字段

    Args:
        classified_results: 分类结果列表

    Returns:
        各字段类型及其匹配内容的字典
    """
    field_stats = {
        '检测部件代号': [],
        '焊道号_片号': [],
        '像质计灵敏度': [],
        '管道规格': []
    }

    for classification in classified_results:
        for field in classification.get('匹配字段', []):
            field_type = field['字段类型']
            if field_type not in field_stats:
                continue

            if field_type == '焊道号_片号':
                weld_no = field.get('焊道号', '')
                film_no = field.get('片号', '')
                value = f"焊道{weld_no}/片{film_no}" if (weld_no or film_no) else field.get('匹配内容', '')
            elif field_type == '管道规格':
                outer = field.get('外径', '')
                thick = field.get('壁厚', '')
                value = f"外径{outer}/壁厚{thick}" if (outer or thick) else field.get('匹配内容', '')
            elif field_type == '像质计灵敏度':
                sens = field.get('灵敏度值', '')
                value = f"值={sens}" if sens else field.get('匹配内容', '')
            elif field_type == '检测部件代号':
                value = field.get('值', '') or field.get('匹配内容', '')
            else:
                value = field.get('匹配内容', '')

            field_stats[field_type].append(value)

    return field_stats


def print_classification_results(classified_results: List[Dict], verbose: bool = True):
    """
    打印分类结果

    Args:
        classified_results: 分类结果列表
        verbose: 是否打印详细信息
    """
    print("=" * 50)
    print("分类结果:")
    print("=" * 50)

    for i, classification in enumerate(classified_results, 1):
        print(f"\n{i}. 原始文本: '{classification['原始文本']}'")

        if classification.get('字段类型') == '未分类':
            print(f"   字段类型: 未分类")
        elif classification['匹配字段']:
            print(f"   匹配到 {len(classification['匹配字段'])} 个字段:")

            if verbose:
                for j, field in enumerate(classification['匹配字段'], 1):
                    print(f"\n   字段{j}:")
                    print(f"     类型: {field['字段类型']}")
                    print(f"     匹配内容: {field['匹配内容']}")

                    # 打印详细信息
                    if field['字段类型'] == '焊道号_片号':
                        print(f"     焊道号: {field.get('焊道号', '')}")
                        print(f"     片号: {field.get('片号', '')}")
                    elif field['字段类型'] == '像质计灵敏度':
                        print(f"     灵敏度值: {field.get('灵敏度值', '')}")
                    elif field['字段类型'] == '管道规格':
                        print(f"     外径: {field.get('外径', '')}")
                        print(f"     壁厚: {field.get('壁厚', '')}")
                    elif field['字段类型'] == '检测部件代号':
                        print(f"     值: {field.get('值', '')}")
        else:
            print(f"   未匹配到任何字段")
