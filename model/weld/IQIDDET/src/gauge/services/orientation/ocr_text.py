#!/usr/bin/env python3
"""Text-crop orientation correction utility for OCR recognition."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

from gauge.services.orientation.base import BaseOrientationCorrector


class SquarePadResize:
    """Resize while preserving aspect ratio, then pad to a square canvas."""

    def __init__(self, size: int = 224):
        self.size = int(size)

    def __call__(self, img: Image.Image) -> Image.Image:
        width, height = img.size
        if width <= 0 or height <= 0:
            return Image.new("RGB", (self.size, self.size), (0, 0, 0))

        ratio = self.size / float(max(width, height))
        new_size = (
            max(1, int(round(width * ratio))),
            max(1, int(round(height * ratio))),
        )
        resized = img.resize(new_size, Image.BILINEAR)
        canvas = Image.new("RGB", (self.size, self.size), (0, 0, 0))
        offset = ((self.size - new_size[0]) // 2, (self.size - new_size[1]) // 2)
        canvas.paste(resized, offset)
        return canvas


class OCRTextOrientationCorrector(BaseOrientationCorrector):
    """Detect and restore text-crop orientation across 8 direction classes."""

    def __init__(
        self,
        model_path: Union[str, Path],
        device: Optional[str] = None,
        model_type: str = "resnet34",
    ):
        super().__init__(model_path, model_type, device, num_classes=8, use_adaptive_processor=False)

    def _get_model_architecture(self) -> nn.Module:
        if self.model_type == "resnet18":
            model = models.resnet18(weights=None)
        elif self.model_type == "resnet34":
            model = models.resnet34(weights=None)
        elif self.model_type == "resnet50":
            model = models.resnet50(weights=None)
        else:
            raise ValueError(f"Unsupported OCR orientation model type: {self.model_type}")

        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, self.num_classes)
        return model

    def _get_preprocess(self) -> transforms.Compose:
        return transforms.Compose(
            [
                SquarePadResize(224),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

    def _prepare_pil_image(self, image: np.ndarray) -> Image.Image:
        from gauge.imaging.adaptive import AdaptiveImageProcessor

        processor = AdaptiveImageProcessor(use_negative=True)
        processed = processor.process_image(image)
        return Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB))
