# batch_ocr_processor.py - 批量OCR处理主程序
"""
焊缝X光底片批量OCR识别程序
支持单张图片和批量图片处理
"""

import os
import json
from typing import Dict, List, Optional
import argparse

from paddleocr import PaddleOCR
import pandas as pd

# 导入自定义工具模块
from utils.ocr_utils import (
    classify_text,
    process_image_for_ocr,
    draw_annotations,
    extract_field_statistics,
    print_classification_results
)


class BatchOCRProcessor:
    """批量OCR处理器类"""

    def __init__(self,
                 output_dir: Optional[str] = None,
                 max_image_size: int = 1920,
                 save_annotations: bool = True,
                 verbose: bool = True):
        """
        初始化批量OCR处理器

        Args:
            output_dir: 输出目录路径
            max_image_size: 最大图片尺寸
            save_annotations: 是否保存标注图片
            verbose: 是否打印详细信息
        """
        self.output_dir = output_dir
        self.max_image_size = max_image_size
        self.save_annotations = save_annotations
        self.verbose = verbose

        # 初始化PaddleOCR
        print("初始化PaddleOCR...")
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True
        )

        # 统计信息
        self.statistics = []

    def process_single_image(self, img_path: str, save_path: Optional[str] = None) -> Dict:
        """
        处理单张图片

        Args:
            img_path: 图片路径
            save_path: 标注图片保存路径（可选）

        Returns:
            处理结果字典
        """
        print(f"\n处理图片: {img_path}")

        # 检查文件是否存在
        if not os.path.exists(img_path):
            print(f"错误：文件 {img_path} 不存在")
            return None

        try:
            # 1. 预处理图片
            img_array, original_img, scale = process_image_for_ocr(img_path, self.max_image_size)

            # 2. OCR识别
            results = self.ocr.predict(input=img_array)

            # 3. 解析结果
            if not results or not results[0]:
                print("未识别到任何文本")
                return {
                    'image_path': img_path,
                    'image_name': os.path.basename(img_path),
                    'recognized_texts': [],
                    'classified_results': [],
                    'field_statistics': {},
                    'error': '未识别到文本'
                }

            result = results[0]
            rec_texts = result.get('rec_texts', [])

            if not rec_texts:
                print("未识别到任何文本")
                return {
                    'image_path': img_path,
                    'image_name': os.path.basename(img_path),
                    'recognized_texts': [],
                    'classified_results': [],
                    'field_statistics': {},
                    'error': '未识别到文本'
                }

            if self.verbose:
                print(f"识别到的原始文本: {rec_texts}")

            # 4. 文本分类
            classified_results = []
            for text in rec_texts:
                classification = classify_text(text)
                classified_results.append(classification)

            # 5. 打印分类结果（如果verbose）
            if self.verbose:
                print_classification_results(classified_results, verbose=True)

            # 6. 提取字段统计
            field_stats = extract_field_statistics(classified_results)

            # 7. 保存标注图片（如果需要）
            if self.save_annotations and save_path:
                annotated_img = draw_annotations(original_img, results, classified_results, scale)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                annotated_img.save(save_path, quality=95)
                if self.verbose:
                    print(f"标注图片已保存至: {save_path}")

            # 8. 返回结果
            return {
                'image_path': img_path,
                'image_name': os.path.basename(img_path),
                'recognized_texts': rec_texts,
                'classified_results': classified_results,
                'field_statistics': field_stats,
                'error': None
            }

        except Exception as e:
            print(f"处理图片时出错: {e}")
            return {
                'image_path': img_path,
                'image_name': os.path.basename(img_path),
                'recognized_texts': [],
                'classified_results': [],
                'field_statistics': {},
                'error': str(e)
            }

    def process_batch(self, input_path: str, output_dir: Optional[str] = None) -> List[Dict]:
        """
        批量处理图片

        Args:
            input_path: 输入路径（文件或文件夹）
            output_dir: 输出目录（可选，默认使用初始化时的值）

        Returns:
            所有处理结果的列表
        """
        # 确定输出目录
        if output_dir:
            self.output_dir = output_dir

        # 收集待处理的图片文件
        image_files = []
        supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')

        if os.path.isfile(input_path):
            # 单个文件
            if input_path.lower().endswith(supported_formats):
                image_files.append(input_path)
                # 设置默认输出目录
                if not self.output_dir:
                    self.output_dir = os.path.join(os.path.dirname(input_path), 'OCRresult_single')
        elif os.path.isdir(input_path):
            # 文件夹
            for file in os.listdir(input_path):
                if file.lower().endswith(supported_formats):
                    image_files.append(os.path.join(input_path, file))
            # 设置默认输出目录
            if not self.output_dir:
                folder_name = os.path.basename(os.path.normpath(input_path))
                self.output_dir = os.path.join(os.path.dirname(input_path), f'OCRresult_{folder_name}')
        else:
            print(f"错误：路径 {input_path} 不存在")
            return []

        if not image_files:
            print("未找到支持的图片文件")
            return []

        print(f"找到 {len(image_files)} 个图片文件")
        print(f"输出目录: {self.output_dir}")

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        annotated_dir = os.path.join(self.output_dir, 'annotated_images')
        if self.save_annotations:
            os.makedirs(annotated_dir, exist_ok=True)

        # 处理每张图片
        results = []
        for i, img_path in enumerate(image_files, 1):
            print(f"\n[{i}/{len(image_files)}] ", end='')

            # 设置标注图片保存路径
            if self.save_annotations:
                img_name = os.path.splitext(os.path.basename(img_path))[0]
                save_path = os.path.join(annotated_dir, f'{img_name}_annotated.jpg')
            else:
                save_path = None

            # 处理图片
            result = self.process_single_image(img_path, save_path)
            if result:
                results.append(result)
                self.statistics.append(self._extract_statistics(result))

        # 保存统计结果
        self._save_statistics()

        # 保存详细结果（JSON格式）
        self._save_detailed_results(results)

        return results

    def _extract_statistics(self, result: Dict) -> Dict:
        """
        从单个结果中提取统计信息

        Args:
            result: 单张图片的处理结果

        Returns:
            统计信息字典
        """
        # 收集拆分后的字段内容
        weld_no_list: List[str] = []
        film_no_list: List[str] = []
        outer_diameter_list: List[str] = []
        wall_thickness_list: List[str] = []

        for classification in result.get('classified_results', []):
            for field in classification.get('匹配字段', []):
                field_type = field.get('字段类型')
                if field_type == '焊道号_片号':
                    weld_no = field.get('焊道号')
                    film_no = field.get('片号')
                    if weld_no:
                        weld_no_list.append(str(weld_no))
                    if film_no:
                        film_no_list.append(str(film_no))
                elif field_type == '管道规格':
                    outer = field.get('外径')
                    thick = field.get('壁厚')
                    if outer:
                        outer_diameter_list.append(str(outer))
                    if thick:
                        wall_thickness_list.append(str(thick))

        # 判断是否完全识别（四类字段都有匹配）
        is_complete = all([
            len(result['field_statistics'].get('检测部件代号', [])) > 0,
            len(result['field_statistics'].get('焊道号_片号', [])) > 0,
            len(result['field_statistics'].get('像质计灵敏度', [])) > 0,
            len(result['field_statistics'].get('管道规格', [])) > 0
        ])

        stats = {
            '图片名称': result['image_name'],
            '识别文本数': len(result['recognized_texts']),
            '检测部件代号': len(result['field_statistics'].get('检测部件代号', [])),
            '焊道号_片号': len(result['field_statistics'].get('焊道号_片号', [])),
            '像质计灵敏度': len(result['field_statistics'].get('像质计灵敏度', [])),
            '管道规格': len(result['field_statistics'].get('管道规格', [])),
            '未分类数': sum(1 for c in result['classified_results'] if c.get('字段类型') == '未分类'),
            '完全识别': '是' if is_complete else '否'
        }

        # 添加具体匹配内容
        stats['检测部件代号_内容'] = ', '.join(result['field_statistics'].get('检测部件代号', [])) or '无'
        stats['像质计灵敏度_内容'] = ', '.join(result['field_statistics'].get('像质计灵敏度', [])) or '无'
        stats['焊道号_内容'] = ', '.join(weld_no_list) if weld_no_list else '无'
        stats['片号_内容'] = ', '.join(film_no_list) if film_no_list else '无'
        stats['管道外径_内容'] = ', '.join(outer_diameter_list) if outer_diameter_list else '无'
        stats['管道壁厚_内容'] = ', '.join(wall_thickness_list) if wall_thickness_list else '无'

        return stats

    def _save_statistics(self):
        """保存统计结果到CSV文件"""
        if not self.statistics:
            return

        csv_path = os.path.join(self.output_dir, 'ocr_statistics.csv')
        df = pd.DataFrame(self.statistics)

        # 统计完全识别的数量
        complete_count = len(df[df['完全识别'] == '是'])
        incomplete_count = len(df[df['完全识别'] == '否'])

        # 添加汇总行
        summary = {
            '图片名称': '汇总',
            '识别文本数': df['识别文本数'].sum(),
            '检测部件代号': df['检测部件代号'].sum(),
            '焊道号_片号': df['焊道号_片号'].sum(),
            '像质计灵敏度': df['像质计灵敏度'].sum(),
            '管道规格': df['管道规格'].sum(),
            '未分类数': df['未分类数'].sum(),
            '完全识别': f"是: {complete_count}, 否: {incomplete_count}",
            '检测部件代号_内容': '-',
            '像质计灵敏度_内容': '-',
            '焊道号_内容': '-',
            '片号_内容': '-',
            '管道外径_内容': '-',
            '管道壁厚_内容': '-'
        }

        df = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)

        # 保存到CSV
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n统计结果已保存至: {csv_path}")

        # 打印汇总信息
        print("\n" + "=" * 60)
        print("批量处理汇总:")
        print("=" * 60)
        print(f"处理图片总数: {len(self.statistics)}")
        print(f"完全识别: {complete_count} 张 ({complete_count / len(self.statistics) * 100:.1f}%)")
        print(f"不完全识别: {incomplete_count} 张 ({incomplete_count / len(self.statistics) * 100:.1f}%)")
        print(f"识别文本总数: {summary['识别文本数']}")
        print(f"各字段识别数量:")
        print(f"  - 检测部件代号: {summary['检测部件代号']}")
        print(f"  - 焊道号_片号: {summary['焊道号_片号']}")
        print(f"  - 像质计灵敏度: {summary['像质计灵敏度']}")
        print(f"  - 管道规格: {summary['管道规格']}")
        print(f"  - 未分类: {summary['未分类数']}")

    def _save_detailed_results(self, results: List[Dict]):
        """保存详细结果到JSON文件"""
        json_path = os.path.join(self.output_dir, 'ocr_detailed_results.json')

        # 转换为可序列化的格式
        serializable_results = []
        for result in results:
            serializable_result = {
                'image_name': result['image_name'],
                'image_path': result['image_path'],
                'recognized_texts': result['recognized_texts'],
                'field_statistics': result['field_statistics'],
                'error': result['error'],
                'classified_results': []
            }

            # 处理分类结果
            for classification in result['classified_results']:
                serializable_result['classified_results'].append({
                    '原始文本': classification['原始文本'],
                    '匹配字段': classification.get('匹配字段', []),
                    '字段类型': classification.get('字段类型', '')
                })

            serializable_results.append(serializable_result)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)

        print(f"详细结果已保存至: {json_path}")


SUPPORTED_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')


def collect_images(image_dir: Optional[str], file_list_path: Optional[str], max_images: Optional[int] = None) -> List[str]:
    """
    收集待处理的图像文件列表

    Args:
        image_dir: 图像目录路径
        file_list_path: 包含图像绝对路径的文本文件路径
        max_images: 最多处理的图像数

    Returns:
        图像文件路径列表
    """
    image_paths = []

    # Priority 1: File list (Docker 服务化场景)
    if file_list_path:
        if not os.path.exists(file_list_path):
            raise FileNotFoundError(f"未找到文件列表: {file_list_path}")
        with open(file_list_path, 'r', encoding='utf-8') as f:
            for line in f:
                path_str = line.strip()
                if not path_str:
                    continue
                if path_str.lower().endswith(SUPPORTED_IMAGE_EXTS) and os.path.isfile(path_str):
                    image_paths.append(path_str)
        if not image_paths:
            raise FileNotFoundError(f"文件列表 {file_list_path} 中未包含有效的图像文件")

    # Priority 2: Image directory (本地命令行场景)
    elif image_dir:
        if not os.path.exists(image_dir):
            raise FileNotFoundError(f"输入目录不存在: {image_dir}")
        if os.path.isfile(image_dir):
            # 单个文件
            if image_dir.lower().endswith(SUPPORTED_IMAGE_EXTS):
                image_paths.append(image_dir)
        else:
            # 目录
            for file in sorted(os.listdir(image_dir)):
                if file.lower().endswith(SUPPORTED_IMAGE_EXTS):
                    image_paths.append(os.path.join(image_dir, file))
        if not image_paths:
            raise FileNotFoundError(f"未在 {image_dir} 中找到支持的图像文件")
    else:
        raise ValueError("必须提供 --image-dir 或 --file-list 其中之一")

    if max_images is not None:
        image_paths = image_paths[:max_images]

    return image_paths


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='焊缝X光底片批量OCR识别程序')
    parser.add_argument('--image-dir', help='输入图片路径或文件夹路径（如果提供了 --file-list 则忽略）')
    parser.add_argument('--file-list', help='包含待处理图像绝对路径的文本文件（每行一个路径）')
    parser.add_argument('-o', '--output-dir', help='输出目录路径', default='ocr_outputs')
    parser.add_argument('--results-json', default='ocr_results.json',
                        help='结果JSON文件名（相对output_dir）')
    parser.add_argument('--max-images', type=int, help='最多处理的图像数')
    parser.add_argument('--max-size', type=int, default=1920, help='图片最大尺寸（默认1920）')
    parser.add_argument('--no-annotation', action='store_true', help='不保存标注图片')
    parser.add_argument('--quiet', action='store_true', help='减少输出信息')

    args = parser.parse_args()

    # 收集图像文件
    image_paths = collect_images(args.image_dir, args.file_list, args.max_images)
    print(f"找到 {len(image_paths)} 个图片文件")

    # 确定输出目录
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    print(f"输出目录: {output_dir}")

    # 创建处理器
    processor = BatchOCRProcessor(
        output_dir=output_dir,
        max_image_size=args.max_size,
        save_annotations=not args.no_annotation,
        verbose=not args.quiet
    )

    # 处理每张图片
    annotated_dir = os.path.join(output_dir, 'annotated_images')
    if not args.no_annotation:
        os.makedirs(annotated_dir, exist_ok=True)

    results = []
    for i, img_path in enumerate(image_paths, 1):
        print(f"\n[{i}/{len(image_paths)}] ", end='')

        # 设置标注图片保存路径
        if not args.no_annotation:
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            save_path = os.path.join(annotated_dir, f'{img_name}_annotated.jpg')
        else:
            save_path = None

        # 处理图片
        result = processor.process_single_image(img_path, save_path)
        if result:
            results.append(result)
            processor.statistics.append(processor._extract_statistics(result))

    # 保存统计结果
    processor._save_statistics()

    # 保存详细结果（JSON格式）
    processor._save_detailed_results(results)

    # 保存简化的结果JSON（与 weld 推理脚本格式一致）
    results_path = os.path.join(output_dir, args.results_json)
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({'mode': 'ocr', 'results': results}, f, indent=2, ensure_ascii=False)

    print(f"\n处理完成！共处理 {len(results)} 个文件")
    print(f"结果JSON: {results_path}")


def test_single_image():
    """测试单张图片处理"""
    # 测试路径
    img_path = r"E:\CODE\datasets\第二第三批样本\1\SrcImage\第二批_4R12_te_0.bmp"

    # 创建处理器
    processor = BatchOCRProcessor(
        output_dir="output/test",
        save_annotations=True,
        verbose=True
    )

    # 处理单张图片
    result = processor.process_single_image(
        img_path,
        save_path="output/test/annotated_test.jpg"
    )

    if result:
        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)
        print(f"识别到 {len(result['recognized_texts'])} 个文本")
        print(f"字段统计:")
        for field_type, matches in result['field_statistics'].items():
            if matches:
                print(f"  {field_type}: {matches}")


if __name__ == "__main__":
    # 如果没有命令行参数，运行测试
    import sys

    if len(sys.argv) == 1:
        print("运行测试模式...")
        test_single_image()
    else:
        main()
