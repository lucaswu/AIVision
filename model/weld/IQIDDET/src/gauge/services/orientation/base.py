#!/usr/bin/env python3
"""Base class for orientation correction (8-class rotation/mirror detection)."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Union
import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms


class BaseOrientationCorrector(ABC):
    """Detect and restore image orientation across 8 direction classes."""

    STATUS_MAP = {
        0: "Normal (OK)",
        1: "Rotated 90 CW",
        2: "Upside Down (180)",
        3: "Rotated 90 CCW",
        4: "Mirrored",
        5: "Mirrored + 90 CW",
        6: "Mirrored + 180",
        7: "Mirrored + 90 CCW",
    }

    def __init__(
        self,
        model_path: Union[str, Path],
        model_type: str,
        device: Optional[str] = None,
        num_classes: int = 8,
        use_adaptive_processor: bool = True,
    ):
        self.model_path = Path(model_path)
        self.model_type = str(model_type)
        self.num_classes = int(num_classes)
        self.device = (
            torch.device(device)
            if device
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        from gauge.imaging.adaptive import AdaptiveImageProcessor
        self.adaptive_processor = (
            AdaptiveImageProcessor(use_negative=True) if use_adaptive_processor else None
        )
        self.model = self._load_model()
        self.preprocess = self._get_preprocess()

    # --- Subclass hooks ---

    @abstractmethod
    def _get_model_architecture(self) -> nn.Module:
        """Build the ResNet variant + Linear(num_classes) head."""
        ...

    @abstractmethod
    def _get_preprocess(self) -> transforms.Compose:
        """Return torchvision transforms pipeline."""
        ...

    def _prepare_pil_image(self, image: np.ndarray) -> Image.Image:
        """Convert np.ndarray to PIL Image. Override for custom preprocessing."""
        if self.adaptive_processor is not None:
            processed = self.adaptive_processor.process_image(image)
            return Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB))
        if image.ndim == 2:
            return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_GRAY2RGB))
        if image.ndim == 3 and image.shape[2] == 1:
            return Image.fromarray(cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2RGB))
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    # --- Shared logic ---

    def _load_model(self) -> nn.Module:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        model = self._get_model_architecture()
        model.load_state_dict(
            torch.load(self.model_path, map_location=self.device, weights_only=False)
        )
        model.to(self.device)
        model.eval()
        return model

    def predict_orientation(self, image: np.ndarray) -> Tuple[int, float]:
        pil_img = self._prepare_pil_image(image)
        input_tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, prediction = torch.max(probabilities, 1)
        return prediction.item(), confidence.item()

    def correct_image(self, image: np.ndarray, verbose: bool = False) -> Tuple[np.ndarray, dict]:
        label_idx, confidence = self.predict_orientation(image)
        info = {
            "label": label_idx,
            "confidence": confidence,
            "status": self.STATUS_MAP.get(label_idx, "Unknown"),
            "corrected": False,
            "actions": None,
        }
        if verbose:
            print(f"  Orientation: [{label_idx}] {info['status']} (Conf: {confidence:.4f})")
        if label_idx == 0:
            if verbose:
                print("  Image is already correct.")
            return image.copy(), info
        corrected_img, actions = self.restore_image(image, label_idx)
        info["corrected"] = True
        info["actions"] = actions
        if verbose:
            print(f"  Fix Actions: {actions}")
        return corrected_img, info

    @staticmethod
    def restore_image(image: np.ndarray, label_idx: int) -> Tuple[np.ndarray, str]:
        img = image.copy()
        label_idx = int(label_idx)
        rot_state = label_idx % 4
        if rot_state == 1:
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            action_rot = "Rotate -90 (CCW)"
        elif rot_state == 2:
            img = cv2.rotate(img, cv2.ROTATE_180)
            action_rot = "Rotate 180"
        elif rot_state == 3:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            action_rot = "Rotate +90 (CW)"
        else:
            action_rot = "No Rotation"
        if label_idx >= 4:
            img = cv2.flip(img, 1)
            action_mirror = "Mirror Flip"
        else:
            action_mirror = "No Mirror"
        return img, f"{action_rot} + {action_mirror}"
