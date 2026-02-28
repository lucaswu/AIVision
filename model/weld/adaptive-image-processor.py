import numpy as np
import cv2
import matplotlib.pyplot as plt
from typing import Tuple, Dict, Optional
import os
import platform
import argparse
import sys
from pathlib import Path

def imread_universal(file_path, flags=cv2.IMREAD_COLOR):
    """跨平台读取图片函数，支持不同的读取模式"""
    if platform.system() == "Windows":
        # Windows下使用numpy+imdecode方式
        with open(file_path, 'rb') as f:
            img_data = f.read()
        img_array = np.frombuffer(img_data, np.uint8)
        return cv2.imdecode(img_array, flags)
    else:
        # Linux/Mac下直接使用cv2.imread
        return cv2.imread(file_path, flags)

class AdaptiveImageProcessor:
    """
    自适应图像处理器
    集成窗口化、智能亮度调整、自适应增强和负片处理功能
    特别适用于焊缝检测和医学影像处理
    """
    
    def __init__(self, use_negative: bool = True):
        """
        初始化处理器
        
        Args:
            use_negative: 是否启用负片处理
        """
        self.use_negative = use_negative
        self.image_stats = None
        
    def analyze_image(self, image: np.ndarray) -> Dict:
        """
        分析图像统计特征
        
        Args:
            image: 输入图像 (灰度图)
            
        Returns:
            包含图像统计信息的字典
        """
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        # 基本统计
        mean = np.mean(gray)
        std = np.std(gray)
        min_val = np.min(gray)
        max_val = np.max(gray)
        
        # 计算百分位数
        percentiles = {
            'p1': np.percentile(gray, 1),
            'p5': np.percentile(gray, 5),
            'p25': np.percentile(gray, 25),
            'p75': np.percentile(gray, 75),
            'p95': np.percentile(gray, 95),
            'p99': np.percentile(gray, 99)
        }
        
        # 图像特征判断
        features = {
            'dynamic_range': max_val - min_val,
            'contrast': std / mean if mean > 0 else 0,
            'brightness': mean,
            'is_dark': mean < 85,
            'is_bright': mean > 170,
            'is_low_contrast': std < 30,
            'is_high_contrast': std > 80
        }
        
        self.image_stats = {
            'mean': mean,
            'std': std,
            'min': min_val,
            'max': max_val,
            'percentiles': percentiles,
            'features': features
        }
        
        return self.image_stats
    
    def auto_set_bone_metal_window(self) -> Tuple[int, int]:
        """
        自动设置骨骼/金属窗口参数
        适合高密度材料，如X光片中的骨骼或焊缝金属
        
        Returns:
            (window_center, window_width) 窗口中心和窗口宽度
        """
        if not self.image_stats:
            return 128, 256
            
        stats = self.image_stats
        
        # 骨骼/金属窗口：适合高密度材料
        # 使用较高的窗口中心和较宽的窗口宽度
        center = int(round(stats['mean'] + stats['std']))
        width = int(round(stats['std'] * 6))
        
        # 确保参数在有效范围内
        center = max(0, min(255, center))
        width = max(100, min(512, width))
        
        return center, width
    
    def apply_windowing(self, image: np.ndarray, window_center: int, window_width: int) -> np.ndarray:
        """
        应用窗口化处理
        
        Args:
            image: 输入图像
            window_center: 窗口中心
            window_width: 窗口宽度
            
        Returns:
            窗口化处理后的图像
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)
            
        min_value = window_center - window_width / 2
        max_value = window_center + window_width / 2
        
        # 应用窗口化
        windowed = np.where(gray <= min_value, 0,
                           np.where(gray >= max_value, 255,
                                   ((gray - min_value) / window_width) * 255))
        
        return windowed.astype(np.uint8)
    
    def apply_negative_transform(self, image: np.ndarray) -> np.ndarray:
        """
        应用负片变换
        
        Args:
            image: 输入图像
            
        Returns:
            负片处理后的图像
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        negative = 255 - gray
        return negative.astype(np.uint8)
    
    def process_image(self, image: np.ndarray, apply_negative: bool = None) -> np.ndarray:
        """
        完整的图像处理流程
        保留现有逻辑：分析 -> 骨骼/金属窗口 -> 负片变换
        
        Args:
            image: 输入图像
            apply_negative: 是否应用负片处理，None时使用初始化设置
            
        Returns:
            处理后的图像
        """
        if apply_negative is None:
            apply_negative = self.use_negative
            
        # 1. 分析图像
        self.analyze_image(image)
        
        # 2. 自动设置骨骼/金属窗口
        window_center, window_width = self.auto_set_bone_metal_window()
        
        # 3. 应用窗口化
        windowed = self.apply_windowing(image, window_center, window_width)
        
        # 4. 应用负片变换（如果启用）
        if apply_negative:
            final_result = self.apply_negative_transform(windowed)
        else:
            final_result = windowed
            
        return final_result
    
    def process_directory(self, input_dir: str, output_dir: str, 
                         image_extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')):
        """
        批量处理目录中的所有图片
        
        Args:
            input_dir: 输入图片目录
            output_dir: 输出目录
            image_extensions: 支持的图片格式
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        # 检查输入目录是否存在
        if not input_path.exists():
            print(f"错误: 输入目录不存在 - {input_dir}")
            return False
        
        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 获取所有图片文件
        image_files = []
        for ext in image_extensions:
            image_files.extend(input_path.glob(f"*{ext}"))
            image_files.extend(input_path.glob(f"*{ext.upper()}"))
        
        if not image_files:
            print(f"在目录 {input_dir} 中未找到支持的图片文件")
            print(f"支持的格式: {image_extensions}")
            return False
        
        print(f"找到 {len(image_files)} 个图片文件")
        print("=" * 60)
        
        success_count = 0
        error_count = 0
        
        for i, image_file in enumerate(image_files, 1):
            try:
                print(f"处理第 {i}/{len(image_files)} 个图片: {image_file.name}")
                
                # 读取图像
                original = imread_universal(str(image_file), cv2.IMREAD_GRAYSCALE)
                if original is None:
                    print(f"  错误: 无法读取图片 {image_file.name}")
                    error_count += 1
                    continue
                
                # 处理图像
                processed = self.process_image(original)
                
                # 保存原图和处理后的图像到同一目录
                base_name = image_file.stem
                
                # 保存原图
                original_save_path = output_path / f"{base_name}_src.png"
                cv2.imwrite(str(original_save_path), original)
                
                # 保存处理后的图像
                processed_save_path = output_path / f"{base_name}_process.png"
                cv2.imwrite(str(processed_save_path), processed)
                
                # 输出处理信息
                if self.image_stats:
                    stats = self.image_stats
                    print(f"  图像信息: 均值={stats['mean']:.1f}, 标准差={stats['std']:.1f}")
                    window_center, window_width = self.auto_set_bone_metal_window()
                    print(f"  处理参数: 窗口中心={window_center}, 窗口宽度={window_width}")
                
                print(f"  ✓ 已保存: {original_save_path.name} 和 {processed_save_path.name}")
                success_count += 1
                
            except Exception as e:
                print(f"  错误: 处理图片 {image_file.name} 时发生异常: {str(e)}")
                error_count += 1
            
            print("-" * 60)
        
        # 输出处理结果摘要
        print("=" * 60)
        print("批量处理完成!")
        print(f"总计: {len(image_files)} 个文件")
        print(f"成功: {success_count} 个")
        print(f"失败: {error_count} 个")
        print(f"输出目录: {output_path}")
        print(f"文件命名规则:")
        print(f"  - 原图: [文件名]_原图.png")
        print(f"  - 处理后: [文件名]_处理后.png")
        
        # 生成处理报告
        self.generate_report(output_path, len(image_files), success_count, error_count)
        
        return success_count > 0
    
    def generate_report(self, output_dir: Path, total: int, success: int, error: int):
        """
        生成处理报告
        
        Args:
            output_dir: 输出目录
            total: 总文件数
            success: 成功处理数
            error: 处理失败数
        """
        report_path = output_dir / "处理报告.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("图像处理批量处理报告\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"处理时间: {str(np.datetime64('now'))}\n")
            f.write(f"总文件数: {total}\n")
            f.write(f"成功处理: {success}\n")
            f.write(f"处理失败: {error}\n")
            f.write(f"成功率: {success/total*100:.1f}%\n\n")
            
            f.write("处理设置:\n")
            f.write(f"- 负片处理: {'开启' if self.use_negative else '关闭'}\n")
            f.write("- 窗口化: 骨骼/金属模式\n")
            f.write("- 自适应参数: 基于图像统计自动设置\n\n")
            
            f.write("文件命名规则:\n")
            f.write("- [文件名]_原图.png : 原始图像副本\n")
            f.write("- [文件名]_处理后.png : 窗口化+负片处理后的图像\n")
        
        print(f"处理报告已保存: {report_path}")


def main():
    """
    主函数 - 支持命令行参数
    """
    parser = argparse.ArgumentParser(description='自适应图像处理器 - 批量处理模式')
    parser.add_argument('input_dir', help='输入图片目录路径')
    parser.add_argument('output_dir', help='输出目录路径')
    parser.add_argument('--no-negative', action='store_true', help='禁用负片处理')
    
    # 如果没有命令行参数，使用交互模式
    if len(sys.argv) == 1:
        print("自适应图像处理器 - 批量处理模式")
        print("=" * 50)
        
        # 交互式获取参数
        input_dir = input("请输入图片所在目录路径: ").strip()
        if not input_dir:
            print("未指定输入目录，程序退出")
            return
        
        output_dir = input("请输入输出目录路径 (默认: ./output): ").strip()
        if not output_dir:
            output_dir = "./output"
        
        use_negative = input("是否启用负片处理? (y/n, 默认: y): ").strip().lower()
        use_negative = use_negative != 'n'
        
    else:
        # 命令行模式
        args = parser.parse_args()
        input_dir = args.input_dir
        output_dir = args.output_dir
        use_negative = not args.no_negative
    
    # 创建处理器
    processor = AdaptiveImageProcessor(use_negative=use_negative)
    
    print(f"\n处理设置:")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"负片处理: {'开启' if use_negative else '关闭'}")
    
    # 确认开始处理（仅交互模式）
    if len(sys.argv) == 1:
        confirm = input("\n开始批量处理? (y/n): ").strip().lower()
        if confirm != 'y':
            print("用户取消，程序退出")
            return
    
    # 开始批量处理
    success = processor.process_directory(input_dir, output_dir)
    
    if success:
        print("\n✅ 批量处理成功完成!")
    else:
        print("\n❌ 批量处理失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()