import torch
import cv2
import numpy as np
import os
import glob
import importlib.util
from torchvision import models, transforms
from PIL import Image
import torch.nn as nn

# ================= 配置 =================
# 确保这里和训练时的设置一致
MODEL_PATH = 'weld_orientation_model.pth'
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CLASSES = 8

# 模型选择配置 - 必须与训练时使用的模型类型一致
# 可选: 'resnet50', 'resnet101', 'resnet152', 'resnext50_32x4d', 'wide_resnet50_2'
MODEL_TYPE = 'resnet50'  # 默认使用 ResNet50，与训练代码一致
print(f"Using device: {DEVICE}")
print(f"Using model type: {MODEL_TYPE}")

# ================= 加载自适应预处理器（与训练保持一致）=================
def load_processor(filepath="adaptive-image-processor.py"):
    if not os.path.exists(filepath):
        filepath_cwd = os.path.join(os.getcwd(), filepath)
        if os.path.exists(filepath_cwd):
            filepath = filepath_cwd
        else:
            raise FileNotFoundError(f"找不到预处理脚本: {filepath}")
    spec = importlib.util.spec_from_file_location("adaptive_image_processor", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AdaptiveImageProcessor

print(">>> 正在初始化图像处理器...")
try:
    AdaptiveImageProcessor = load_processor("adaptive-image-processor.py")
    adaptive_processor = AdaptiveImageProcessor(use_negative=True)
    print(">>> 图像处理器加载成功（窗口化 + 负片模式）")
except FileNotFoundError as e:
    print(f"警告: {e}，将跳过自适应预处理。")
    adaptive_processor = None

# ================= 1. 加载模型 =================
def get_model_architecture(model_type='resnet50'):
    """
    获取指定类型的模型架构（不加载预训练权重）
    
    Args:
        model_type: 模型类型，支持 'resnet50', 'resnet101', 'resnet152', 'resnext50_32x4d', 'wide_resnet50_2'
    
    Returns:
        model: 模型架构（最后一层已修改为8分类）
    """
    print(f"正在初始化 {model_type} 模型架构...")
    
    # 根据模型类型选择对应的模型架构
    if model_type == 'resnet50':
        model = models.resnet50(weights=None)
    elif model_type == 'resnet101':
        model = models.resnet101(weights=None)
    elif model_type == 'resnet152':
        model = models.resnet152(weights=None)
    elif model_type == 'resnext50_32x4d':
        model = models.resnext50_32x4d(weights=None)
    elif model_type == 'wide_resnet50_2':
        model = models.wide_resnet50_2(weights=None)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    # 修改最后一层为8分类
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, CLASSES)
    
    print(f"模型架构初始化成功，全连接层输入特征数: {num_ftrs}")
    return model

def load_trained_model():
    print(f"Loading model from {MODEL_PATH}...")
    
    # 初始化模型架构（使用与训练时相同的模型类型）
    model = get_model_architecture(MODEL_TYPE)
    
    # 加载训练好的权重
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False))
    model.to(DEVICE)
    model.eval()  # 切换到评估模式
    
    print(f"模型权重加载成功！")
    return model


# ================= 2. 定义逆向还原逻辑 =================
def restore_image(cv2_img, label_idx):
    """
    根据模型预测的错误姿态，执行逆操作来还原图片。
    
    训练时的变换逻辑 (Genimi_train.py):
    0: 原图
    1: 顺时针 90
    2: 180
    3: 逆时针 90 (270)
    4: 镜像
    5: 镜像 + 顺时针 90
    6: 镜像 + 180
    7: 镜像 + 逆时针 90
    """
    img = cv2_img.copy()
    
    # --- 第一步：处理旋转的逆操作 ---
    # 我们需要把转过去的角度“转回来”
    
    # 获取旋转状态 (0-3)
    rot_state = label_idx % 4
    
    if rot_state == 1:
        # 预测是：顺时针90 (比如竖变横)
        # 还原：逆时针90
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        action_rot = "Rotate -90 (CCW)"
    elif rot_state == 2:
        # 预测是：180
        # 还原：180
        img = cv2.rotate(img, cv2.ROTATE_180)
        action_rot = "Rotate 180"
    elif rot_state == 3:
        # 预测是：逆时针90 (270)
        # 还原：顺时针90
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        action_rot = "Rotate +90 (CW)"
    else:
        action_rot = "No Rotation"

    # --- 第二步：处理镜像的逆操作 ---
    # 如果 label >= 4，说明训练时叠加了镜像。
    # 还原：再做一次镜像翻转。
    is_mirrored = label_idx >= 4
    if is_mirrored:
        img = cv2.flip(img, 1)
        action_mirror = "Mirror Flip"
    else:
        action_mirror = "No Mirror"
        
    return img, f"{action_rot} + {action_mirror}"

# ================= 3. 推理主函数 =================
def predict_one_image(model, image_path):
    # 预处理：必须与训练时完全一致 (Resize 224, Normalize)
    preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    # 读取原始图片（支持中文路径）
    cv2_src = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if cv2_src is None:
        print(f"Error: Cannot read {image_path}")
        return None

    # ------------------------------------------------------------------
    # 模型输入：与训练一致，先做自适应预处理再 Resize+Normalize
    # 仅用于帮助模型判断方向，不影响保存的图片内容
    # ------------------------------------------------------------------
    if adaptive_processor is not None:
        processed = adaptive_processor.process_image(cv2_src)  # 灰度 uint8
        pil_for_model = Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB))
    else:
        pil_for_model = Image.fromarray(cv2.cvtColor(cv2_src, cv2.COLOR_BGR2RGB))

    input_tensor = preprocess(pil_for_model).unsqueeze(0).to(DEVICE)
    
    # 推理
    with torch.no_grad():
        outputs = model(input_tensor)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)
        score, preds = torch.max(probabilities, 1)
        
        label_idx = preds.item()
        confidence = score.item()
    
    # 打印诊断结果
    status_map = {
        0: "Normal (OK)", 
        1: "Rotated 90 CW", 
        2: "Upside Down (180)", 
        3: "Rotated 90 CCW",
        4: "Mirrored", 
        5: "Mirrored + 90 CW", 
        6: "Mirrored + 180", 
        7: "Mirrored + 90 CCW"
    }
    
    print(f"\nFile: {os.path.basename(image_path)}")
    print(f"  Diagnosis: [{label_idx}] {status_map[label_idx]} (Conf: {confidence:.4f})")
    
    # 只有当不是 0 (Normal) 时才修复
    if label_idx != 0:
        corrected_img, actions = restore_image(cv2_src, label_idx)
        print(f"  Fix Actions: {actions}")
        return corrected_img
    else:
        print("  Image is already correct.")
        return cv2_src

# ================= 4. 批量测试入口 =================
if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        print(f"请等待训练完成，生成 {MODEL_PATH} 后再运行此脚本。")
    else:
        model = load_trained_model()
        
        # ===在此处修改你要测试的图片路径===
        # 支持测试单张，或测试一个文件夹
        # test_target = "corrected_image_3.png"  # 换成你的测试图片
        # test_target =  '/media/lucas/新加卷1/项目/缺陷检测/数据集/2cj/merge/merge/yolo/images/val'
        # test_target ='/home/lucas/项目/data'
        # test_target='c:\\Users\\wcj06\\Desktop\\218'
        # test_target='/media/lucas/code5/项目/缺陷检测/数据集/2cj/merge/merge/yolo/images/val'
        test_target='/home/lucas/Desktop/218'
        
        if os.path.isfile(test_target):
            res = predict_one_image(model, test_target)
            if res is not None:
                cv2.imwrite("fixed_" + os.path.basename(test_target), res)
                print(f"已保存修复结果: fixed_{os.path.basename(test_target)}")
                
        elif os.path.isdir(test_target):
            # 批量处理文件夹
            images = glob.glob(os.path.join(test_target, "*.png")) + glob.glob(os.path.join(test_target, "*.bmp"))
            for img_p in images:
                res = predict_one_image(model, img_p)
                if res is not None:
                    save_name = os.path.join(test_target, "fixed_" + os.path.basename(img_p))
                    cv2.imwrite(save_name, res)
                    print(save_name)