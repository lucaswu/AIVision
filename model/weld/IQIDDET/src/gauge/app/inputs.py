#!/usr/bin/env python3
"""Image input collection utilities for the IQI inference delivery layer."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from gauge.imaging.preprocess import collect_images


def collect_input_images(
    image_path: Optional[str] = None,
    image_dir: Optional[str] = None,
    image_list: Optional[str] = None,
    max_images: Optional[int] = None,
) -> List[Path]:
    """Resolve image paths from a single path, directory, or list file."""
    if image_path:
        paths = [Path(image_path).resolve()]
    else:
        paths = collect_images(
            Path(image_dir).resolve() if image_dir else None,
            Path(image_list).resolve() if image_list else None,
            max_images=max_images,
        )
    if max_images is not None:
        paths = paths[:max_images]
    return paths
