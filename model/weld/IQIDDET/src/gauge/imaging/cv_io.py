"""Unicode-path-safe image IO (mirror of weld/utils/cv_io.py; IQIDDET is vendored separately).

``cv2.imread`` / ``cv2.imwrite`` go through the ANSI code page on Windows and
silently fail for non-ASCII paths (e.g. Chinese directory names). Going through
numpy file IO + ``imdecode``/``imencode`` works the same on every platform.
"""

from pathlib import Path
from typing import Optional, Sequence, Union

import cv2
import numpy as np

PathLike = Union[str, Path]


def imread(path: PathLike, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """Drop-in for cv2.imread: returns None when the file cannot be decoded."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite(path: PathLike, image: np.ndarray, params: Optional[Sequence[int]] = None) -> bool:
    """Drop-in for cv2.imwrite: returns False on failure instead of raising."""
    ext = Path(path).suffix or ".png"
    try:
        ok, buf = cv2.imencode(ext, image, list(params) if params else [])
        if not ok:
            return False
        buf.tofile(str(path))
        return True
    except (cv2.error, OSError):
        return False
