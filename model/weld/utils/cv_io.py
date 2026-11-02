"""Unicode-path-safe image IO.

``cv2.imread`` / ``cv2.imwrite`` go through the ANSI code page on Windows and
silently fail for non-ASCII paths (e.g. Chinese directory names). Going through
numpy file IO + ``imdecode``/``imencode`` works the same on every platform.
"""

from pathlib import Path
from typing import Optional, Sequence, Union

import cv2
import numpy as np

PathLike = Union[str, Path]
_DICOM_EXTS = {".dcm", ".dicom", ".dic", ".diconde"}


def _read_dicom(path: PathLike, flags: int) -> Optional[np.ndarray]:
    try:
        import pydicom
    except ImportError:
        return None
    try:
        ds = pydicom.dcmread(str(path), force=True)
        if not hasattr(ds, "PixelData"):
            return None
        arr = ds.pixel_array
        samples_per_pixel = int(getattr(ds, "SamplesPerPixel", 1) or 1)
        if arr.ndim == 4:
            arr = arr[0]
        if arr.ndim == 3 and samples_per_pixel == 1:
            arr = arr[0]
        arr = arr.astype(np.float32)
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        if samples_per_pixel == 1:
            arr = arr * slope + intercept
        invert = str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1"
        low, high = float(np.min(arr)), float(np.max(arr))
        if high <= low:
            out = np.zeros(arr.shape[:2] if arr.ndim == 3 else arr.shape, dtype=np.uint8)
        else:
            arr = np.clip(arr, low, high)
            arr = (arr - low) / (high - low) * 255.0
            if invert:
                arr = 255.0 - arr
            out = arr.astype(np.uint8)
        if flags not in (cv2.IMREAD_UNCHANGED, cv2.IMREAD_GRAYSCALE) and out.ndim == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        return out
    except Exception:
        return None


def imread(path: PathLike, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """Drop-in for cv2.imread: returns None when the file cannot be decoded."""
    p = Path(path)
    if p.suffix.lower() in _DICOM_EXTS:
        img = _read_dicom(p, flags)
        if img is not None:
            return img
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
