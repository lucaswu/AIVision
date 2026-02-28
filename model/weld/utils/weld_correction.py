#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld Film Orientation Correction Utility

This module provides functionality to detect and correct weld film orientation
using a trained deep learning model. It can detect 8 different orientations:
- 0: Normal (no correction needed)
- 1: Rotated 90° clockwise
- 2: Rotated 180°
- 3: Rotated 90° counter-clockwise
- 4: Mirrored
- 5: Mirrored + 90° clockwise
- 6: Mirrored + 180°
- 7: Mirrored + 90° counter-clockwise
"""

import os
import importlib.util
import torch
import cv2
import numpy as np
from pathlib import Path
from typing import Union, Optional, Tuple
from torchvision import models, transforms
from PIL import Image
import torch.nn as nn


class WeldOrientationCorrector:
    """
    Weld film orientation detector and corrector.
    
    This class loads a trained model and provides methods to detect and correct
    the orientation of weld film images.
    """
    
    # Orientation status descriptions
    STATUS_MAP = {
        0: "Normal (OK)",
        1: "Rotated 90 CW",
        2: "Upside Down (180)",
        3: "Rotated 90 CCW",
        4: "Mirrored",
        5: "Mirrored + 90 CW",
        6: "Mirrored + 180",
        7: "Mirrored + 90 CCW"
    }
    
    def __init__(self, 
                 model_path: Union[str, Path],
                 model_type: str = 'resnet50',
                 device: Optional[str] = None,
                 num_classes: int = 8,
                 adaptive_processor_path: Optional[str] = None):
        """
        Initialize the weld orientation corrector.
        
        Args:
            model_path: Path to the trained model weights (.pth file)
            model_type: Model architecture type (default: 'resnet50')
            device: Device to run inference on (default: auto-detect CUDA)
            num_classes: Number of orientation classes (default: 8)
            adaptive_processor_path: Path to adaptive-image-processor.py.
                If None, will search relative to this file and cwd.
        """
        self.model_path = Path(model_path)
        self.model_type = model_type
        self.num_classes = num_classes
        
        # Setup device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        # Load AdaptiveImageProcessor (must match training preprocessing)
        self.adaptive_processor = self._load_adaptive_processor(adaptive_processor_path)
        
        # Load model
        self.model = self._load_model()
        
        # Define preprocessing transform (must match training)
        self.preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    
    def _load_adaptive_processor(self, filepath: Optional[str] = None):
        """
        Load the AdaptiveImageProcessor from adaptive-image-processor.py.
        Searches in: provided path → directory of this file's parent → cwd.
        
        Returns:
            AdaptiveImageProcessor instance (use_negative=True), or None if not found.
        """
        search_paths = []
        if filepath:
            search_paths.append(filepath)
        # Relative to model/weld/ directory (parent of utils/)
        search_paths.append(str(Path(__file__).parent.parent / "adaptive-image-processor.py"))
        # cwd fallback
        search_paths.append(os.path.join(os.getcwd(), "adaptive-image-processor.py"))
        
        for path in search_paths:
            if os.path.exists(path):
                try:
                    spec = importlib.util.spec_from_file_location("adaptive_image_processor", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    processor = module.AdaptiveImageProcessor(use_negative=True)
                    print(f">>> AdaptiveImageProcessor loaded from: {path}")
                    return processor
                except Exception as e:
                    print(f"警告: 加载 AdaptiveImageProcessor 失败 ({path}): {e}")
        
        print("警告: 未找到 adaptive-image-processor.py，将跳过自适应预处理（推理精度可能下降）。")
        return None
    
    def _get_model_architecture(self) -> nn.Module:
        """
        Get the model architecture based on model_type.
        
        Returns:
            Model architecture with modified final layer for classification
        """
        # Select model architecture
        if self.model_type == 'resnet50':
            model = models.resnet50(weights=None)
        elif self.model_type == 'resnet101':
            model = models.resnet101(weights=None)
        elif self.model_type == 'resnet152':
            model = models.resnet152(weights=None)
        elif self.model_type == 'resnext50_32x4d':
            model = models.resnext50_32x4d(weights=None)
        elif self.model_type == 'wide_resnet50_2':
            model = models.wide_resnet50_2(weights=None)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
        
        # Modify final layer for orientation classification
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, self.num_classes)
        
        return model
    
    def _load_model(self) -> nn.Module:
        """
        Load the trained model from disk.
        
        Returns:
            Loaded model in evaluation mode
        """
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        # Initialize model architecture
        model = self._get_model_architecture()
        
        # Load trained weights
        model.load_state_dict(torch.load(self.model_path, map_location=self.device, weights_only=False))
        model.to(self.device)
        model.eval()
        
        return model
    
    def _restore_image(self, image: np.ndarray, label_idx: int) -> Tuple[np.ndarray, str]:
        """
        Restore image to correct orientation based on predicted label.
        
        The restoration applies inverse transformations:
        - First: Undo rotation
        - Second: Undo mirroring (if applicable)
        
        Args:
            image: Input image as numpy array (BGR format)
            label_idx: Predicted orientation label (0-7)
        
        Returns:
            Tuple of (corrected_image, action_description)
        """
        img = image.copy()
        
        # Step 1: Handle rotation (inverse operation)
        rot_state = label_idx % 4
        
        if rot_state == 1:
            # Was rotated 90° CW → rotate 90° CCW to restore
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            action_rot = "Rotate -90 (CCW)"
        elif rot_state == 2:
            # Was rotated 180° → rotate 180° to restore
            img = cv2.rotate(img, cv2.ROTATE_180)
            action_rot = "Rotate 180"
        elif rot_state == 3:
            # Was rotated 90° CCW → rotate 90° CW to restore
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            action_rot = "Rotate +90 (CW)"
        else:
            action_rot = "No Rotation"
        
        # Step 2: Handle mirroring (inverse operation)
        # If label >= 4, it was mirrored → flip again to restore
        is_mirrored = label_idx >= 4
        if is_mirrored:
            img = cv2.flip(img, 1)  # Horizontal flip
            action_mirror = "Mirror Flip"
        else:
            action_mirror = "No Mirror"
        
        action_desc = f"{action_rot} + {action_mirror}"
        return img, action_desc
    
    def predict_orientation(self, image: np.ndarray) -> Tuple[int, float]:
        """
        Predict the orientation of a weld film image.
        
        The model input is preprocessed with AdaptiveImageProcessor to match
        training-time preprocessing. The original image is NOT modified.
        
        Args:
            image: Input image as numpy array (BGR format from cv2)
        
        Returns:
            Tuple of (label_index, confidence_score)
        """
        # Apply adaptive preprocessing for model input (matches training pipeline)
        # This converts to windowed grayscale + optional negative, same as training
        if self.adaptive_processor is not None:
            processed = self.adaptive_processor.process_image(image)  # grayscale uint8
            pil_img = Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB))
        else:
            # Fallback: direct BGR→RGB conversion (reduced accuracy)
            pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # Apply transform and run inference
        input_tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, prediction = torch.max(probabilities, 1)
            
            label_idx = prediction.item()
            conf_score = confidence.item()
        
        return label_idx, conf_score
    
    def correct_image(self, 
                     image: np.ndarray, 
                     verbose: bool = False) -> Tuple[np.ndarray, dict]:
        """
        Detect and correct the orientation of a weld film image.
        
        Args:
            image: Input image as numpy array (BGR format from cv2)
            verbose: If True, print diagnostic information
        
        Returns:
            Tuple of (corrected_image, info_dict)
            info_dict contains:
                - 'label': predicted label index
                - 'confidence': confidence score
                - 'status': orientation status description
                - 'corrected': whether correction was applied
                - 'actions': correction actions taken
        """
        # Predict orientation
        label_idx, confidence = self.predict_orientation(image)
        
        # Prepare info dict
        info = {
            'label': label_idx,
            'confidence': confidence,
            'status': self.STATUS_MAP.get(label_idx, "Unknown"),
            'corrected': False,
            'actions': None
        }
        
        if verbose:
            print(f"  Diagnosis: [{label_idx}] {info['status']} (Conf: {confidence:.4f})")
        
        # Apply correction if needed (label != 0 means not normal)
        if label_idx != 0:
            corrected_img, actions = self._restore_image(image, label_idx)
            info['corrected'] = True
            info['actions'] = actions
            
            if verbose:
                print(f"  Fix Actions: {actions}")
            
            return corrected_img, info
        else:
            if verbose:
                print("  Image is already correct.")
            return image.copy(), info
    
    def correct_image_path(self, 
                          image_path: Union[str, Path],
                          verbose: bool = False) -> Tuple[np.ndarray, dict]:
        """
        Load an image from path and correct its orientation.
        
        Uses cv2.imdecode(np.fromfile(...)) to support non-ASCII (e.g. Chinese)
        file paths, consistent with genimi_predict.py.
        
        Args:
            image_path: Path to the image file (supports non-ASCII/Chinese paths)
            verbose: If True, print diagnostic information
        
        Returns:
            Tuple of (corrected_image, info_dict)
        """
        image_path = Path(image_path)
        
        if verbose:
            print(f"\nProcessing: {image_path.name}")
        
        # Use np.fromfile to support non-ASCII (Chinese) paths
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        # Correct orientation
        return self.correct_image(image, verbose=verbose)


def create_corrector(model_path: Union[str, Path] = None,
                     **kwargs) -> WeldOrientationCorrector:
    """
    Factory function to create a WeldOrientationCorrector instance.
    
    Args:
        model_path: Path to model weights. If None, uses default path.
        **kwargs: Additional arguments passed to WeldOrientationCorrector
    
    Returns:
        WeldOrientationCorrector instance
    """
    if model_path is None:
        # Default model path relative to this file
        current_dir = Path(__file__).parent.parent
        model_path = current_dir / "weight" / "weld_orientation_model.pth"
    
    return WeldOrientationCorrector(model_path=model_path, **kwargs)


# Convenience function for single image correction
def correct_weld_image(image: np.ndarray,
                       model_path: Union[str, Path] = None,
                       verbose: bool = False) -> Tuple[np.ndarray, dict]:
    """
    Convenience function to correct a single weld image.
    
    Args:
        image: Input image as numpy array (BGR format)
        model_path: Path to model weights (uses default if None)
        verbose: If True, print diagnostic information
    
    Returns:
        Tuple of (corrected_image, info_dict)
    """
    corrector = create_corrector(model_path)
    return corrector.correct_image(image, verbose=verbose)
