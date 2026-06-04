"""FClipInferencer — Torch-based FClip inferencer for wire count and line endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np

from gauge.services.fclip.line_records import resolve_torch_device, _ensure_gray, build_line_records
from gauge.models.wire import WireResult


class FClipInferencer:
    """Torch-based FClip inferencer for wire count and line endpoints."""

    def __init__(
        self,
        ckpt_path: str,
        device: Optional[str] = None,
        model_config: str = "config/model.yaml",
        params_file: str = "params.yaml",
        threshold: Optional[float] = None,
    ):
        import torch
        from FClip.config import M
        from FClip.infer_utils import (
            build_infer_model,
            get_count_pred,
            infer_heatmaps,
            load_config_from_yaml,
            parse_lines_1d,
            preprocess_gray_image,
            scale_lines,
        )

        self._torch = torch
        self._get_count_pred = get_count_pred
        self._infer_heatmaps = infer_heatmaps
        self._parse_lines_1d = parse_lines_1d
        self._preprocess_gray_image = preprocess_gray_image
        self._scale_lines = scale_lines
        self.ckpt_path = str(Path(ckpt_path).resolve())
        self.model_config = str(Path(model_config).resolve())
        self.params_file = str(Path(params_file).resolve())
        self.device = resolve_torch_device(device)
        load_config_from_yaml(self.model_config, params_yaml=self.params_file, ckpt=self.ckpt_path)
        self.model = build_infer_model(self.device)
        self.threshold = float(getattr(M, "delta", 0.8) if threshold is None else threshold)
        self.nlines = int(getattr(M, "nlines", 7))
        self.resolution = int(getattr(M, "resolution", 64))
        self.ang_type = str(getattr(M, "ang_type", "radian"))
        self.input_resolution = (
            int(getattr(M, "input_resolution_w", self.resolution * 4)),
            int(getattr(M, "input_resolution_h", self.resolution * 4)),
        )
        image_cfg = getattr(M, "image", None)
        self.mean = float(image_cfg.mean[0]) if image_cfg is not None else 125.67842
        self.std = float(image_cfg.stddev[0]) if image_cfg is not None else 65.406591

    def infer(
        self,
        roi_image: np.ndarray,
        crop_inverse_matrix: Optional[np.ndarray] = None,
        pre_rotate_size: Optional[Sequence[int]] = None,
        rotated: bool = False,
    ) -> Dict[str, Any]:
        try:
            roi_gray = _ensure_gray(roi_image)
            image_tensor = self._preprocess_gray_image(
                roi_gray,
                input_resolution=self.input_resolution,
                mean=self.mean,
                std=self.std,
                device=self.device,
            )
            heatmaps = self._infer_heatmaps(self.model, image_tensor)
            count_pred = self._get_count_pred(heatmaps)
            if count_pred is None:
                return WireResult(
                    status="error",
                    error="FClip outputs missing count head.",
                ).model_dump()

            wire_count = int(count_pred[0].item())
            lcmap = heatmaps["lcmap"][0]
            lcoff = heatmaps["lcoff"][0]
            angle = heatmaps["angle"][0]
            lines_t, scores_t = self._parse_lines_1d(
                lcmap=lcmap,
                lcoff=lcoff,
                angle=angle,
                threshold=self.threshold,
                nlines=self.nlines,
                resolution=self.resolution,
                ang_type=self.ang_type,
                count_pred=wire_count,
            )
            if isinstance(lines_t, self._torch.Tensor):
                lines_scaled = lines_t.clone()
            else:
                lines_scaled = self._torch.as_tensor(lines_t).clone()
            lines_scaled = self._scale_lines(lines_scaled, self.resolution, roi_gray.shape)
            lines_np = lines_scaled.detach().cpu().numpy() if isinstance(lines_scaled, self._torch.Tensor) else np.asarray(lines_scaled)
            scores_np = scores_t.detach().cpu().numpy() if isinstance(scores_t, self._torch.Tensor) else np.asarray(scores_t)
            line_records = build_line_records(
                lines_yx=lines_np,
                scores=scores_np.tolist(),
                crop_inverse_matrix=crop_inverse_matrix,
                pre_rotate_size=pre_rotate_size,
                rotated=rotated,
            )
            warnings: List[str] = []
            if wire_count != len(line_records):
                warnings.append(
                    f"wire_count={wire_count} 与 parsed_line_count={len(line_records)} 不一致，等级计算以 wire_count 为准"
                )
            return WireResult(
                status="ok",
                wire_count=wire_count,
                parsed_line_count=int(len(line_records)),
                lines=line_records,
                warnings=warnings,
            ).model_dump()
        except Exception as exc:
            return WireResult(
                status="error",
                error=str(exc),
            ).model_dump()
