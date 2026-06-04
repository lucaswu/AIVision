#!/usr/bin/env python3
"""Weld film orientation correction utility."""

from __future__ import annotations

from typing import Optional, Union

import torch.nn as nn
from pathlib import Path
from torchvision import models, transforms

from gauge.services.orientation.base import BaseOrientationCorrector


class WeldOrientationCorrector(BaseOrientationCorrector):
    """Detect and restore weld film orientation across 8 direction classes."""

    def __init__(
        self,
        model_path: Union[str, Path],
        device: Optional[str] = None,
    ):
        super().__init__(model_path, "weld", device, num_classes=8, use_adaptive_processor=True)

    def _get_model_architecture(self) -> nn.Module:
        model = models.resnet50(weights=None)
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, self.num_classes)
        return model

    def _get_preprocess(self) -> transforms.Compose:
        return transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
