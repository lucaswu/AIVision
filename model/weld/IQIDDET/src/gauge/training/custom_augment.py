"""Custom augmentation helpers for gauge training."""

from __future__ import annotations

import math
import random
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Tuple

import cv2
import numpy as np


CUSTOM_AUGMENT_KEY = "custom_aug"
QUADRANTAL_ROTATION_KEY = "quadrantal_rotation"


def split_augment_config(augment: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split Ultralytics kwargs from project-local custom augmentation config."""
    augment_cfg = dict(augment or {})
    custom_cfg = augment_cfg.pop(CUSTOM_AUGMENT_KEY, {}) or {}
    if not isinstance(custom_cfg, dict):
        raise ValueError(f"{CUSTOM_AUGMENT_KEY} must be a mapping if provided.")
    return augment_cfg, custom_cfg


def _normalize_quadrantal_rotation(config: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not config:
        return None
    if not isinstance(config, dict):
        raise ValueError(f"{QUADRANTAL_ROTATION_KEY} must be a mapping if provided.")
    if not config.get("enabled", False):
        return None

    base_angles = config.get("base_angles", [0, 90, 180, 270])
    if not isinstance(base_angles, list) or not base_angles:
        raise ValueError(f"{QUADRANTAL_ROTATION_KEY}.base_angles must be a non-empty list.")
    try:
        normalized_angles = [float(angle) for angle in base_angles]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{QUADRANTAL_ROTATION_KEY}.base_angles must contain numbers.") from exc

    try:
        jitter = float(config.get("jitter", 15.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{QUADRANTAL_ROTATION_KEY}.jitter must be numeric.") from exc
    if jitter < 0:
        raise ValueError(f"{QUADRANTAL_ROTATION_KEY}.jitter must be >= 0.")

    return {"base_angles": normalized_angles, "jitter": jitter}


@contextmanager
def patch_random_perspective_rotation(custom_augment: Dict[str, Any]) -> Iterator[None]:
    """Patch Ultralytics RandomPerspective to sample around fixed quadrantal angles."""
    rotation_cfg = _normalize_quadrantal_rotation(custom_augment.get(QUADRANTAL_ROTATION_KEY))
    if not rotation_cfg:
        yield
        return

    from ultralytics.data.augment import RandomPerspective

    original_affine_transform = RandomPerspective.affine_transform
    base_angles = rotation_cfg["base_angles"]
    jitter = rotation_cfg["jitter"]

    def affine_transform(self, img: np.ndarray, border: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, float]:
        # Keep the original Ultralytics affine pipeline, but replace the angle sampler.
        C = np.eye(3, dtype=np.float32)
        C[0, 2] = -img.shape[1] / 2
        C[1, 2] = -img.shape[0] / 2

        P = np.eye(3, dtype=np.float32)
        P[2, 0] = random.uniform(-self.perspective, self.perspective)
        P[2, 1] = random.uniform(-self.perspective, self.perspective)

        R = np.eye(3, dtype=np.float32)
        angle = random.choice(base_angles) + random.uniform(-jitter, jitter)
        scale = random.uniform(1 - self.scale, 1 + self.scale)
        R[:2] = cv2.getRotationMatrix2D(angle=angle, center=(0, 0), scale=scale)

        S = np.eye(3, dtype=np.float32)
        S[0, 1] = math.tan(random.uniform(-self.shear, self.shear) * math.pi / 180)
        S[1, 0] = math.tan(random.uniform(-self.shear, self.shear) * math.pi / 180)

        T = np.eye(3, dtype=np.float32)
        T[0, 2] = random.uniform(0.5 - self.translate, 0.5 + self.translate) * self.size[0]
        T[1, 2] = random.uniform(0.5 - self.translate, 0.5 + self.translate) * self.size[1]

        M = T @ S @ R @ P @ C
        if (border[0] != 0) or (border[1] != 0) or (M != np.eye(3)).any():
            if self.perspective:
                img = cv2.warpPerspective(img, M, dsize=self.size, borderValue=(114, 114, 114))
            else:
                img = cv2.warpAffine(img, M[:2], dsize=self.size, borderValue=(114, 114, 114))
            if img.ndim == 2:
                img = img[..., None]
        return img, M, scale

    RandomPerspective.affine_transform = affine_transform
    try:
        yield
    finally:
        RandomPerspective.affine_transform = original_affine_transform
