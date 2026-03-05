#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
焊缝底片方向矫正示例脚本

演示如何使用 weld_correction 工具模块独立处理图像
"""

import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.weld_correction import WeldOrientationCorrector
import cv2


def main():
    """主函数"""
    
    # 配置
    model_path = "weight/weld_orientation_model.pth"
    test_image = "test.png"  # 修改为你的测试图像路径
    output_dir = Path("corrected_output")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("焊缝底片方向矫正示例")
    print("=" * 60)
    
    # 初始化矫正器
    print(f"\n1. 加载模型: {model_path}")
    corrector = WeldOrientationCorrector(
        model_path=model_path,
        model_type='resnet50'
    )
    print("   ✓ 模型加载成功")
    
    # 处理图像
    print(f"\n2. 处理图像: {test_image}")
    
    # 方法1: 从文件路径直接处理
    if Path(test_image).exists():
        corrected_image, info = corrector.correct_image_path(
            test_image, 
            verbose=True
        )
        
        # 显示结果
        print(f"\n3. 处理结果:")
        print(f"   - 检测状态: {info['status']}")
        print(f"   - 置信度: {info['confidence']:.4f}")
        print(f"   - 是否矫正: {'是' if info['corrected'] else '否'}")
        if info['corrected']:
            print(f"   - 矫正操作: {info['actions']}")
        
        # 保存结果
        output_path = output_dir / f"corrected_{Path(test_image).name}"
        cv2.imwrite(str(output_path), corrected_image)
        print(f"\n4. 保存矫正图像: {output_path}")
    else:
        print(f"   ✗ 图像文件不存在: {test_image}")
        print("\n提示: 请修改脚本中的 test_image 变量为实际图像路径")
        
        # 演示方法2: 从内存中的图像处理
        print("\n演示: 从内存处理图像")
        print("```python")
        print("# 读取图像")
        print("image = cv2.imread('your_image.png')")
        print("")
        print("# 矫正图像")
        print("corrected, info = corrector.correct_image(image, verbose=True)")
        print("")
        print("# 使用矫正后的图像")
        print("cv2.imwrite('corrected.png', corrected)")
        print("```")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
