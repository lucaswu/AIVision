#!/usr/bin/env python3
"""Pipeline stage: optional weld orientation correction."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class CorrectionStage(PipelineStage):
    """Apply optional weld-orientation correction to the image."""

    name = "correction"

    def __init__(self, config, services=None):
        super().__init__(config, services)
        self.corrector = (services or {}).get("corrector")

    def should_run(self, ctx: StageContext) -> bool:
        return self.corrector is not None

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})

        corrector = self.corrector
        correction_info: Dict[str, Any] = {
            "label": 0,
            "confidence": None,
            "status": "disabled",
            "corrected": False,
            "actions": None,
        }

        image, correction_info = corrector.correct_image(
            ctx.image, verbose=self.config.correction.verbose
        )
        height, width = image.shape[:2]

        ctx.image = image
        ctx.height = int(height)
        ctx.width = int(width)
        ctx.correction_info = correction_info

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["image"] = image

        logger.info(
            "stage_done",
            extra={
                "stage": self.name,
                "label": correction_info.get("label"),
                "corrected": correction_info.get("corrected"),
                "confidence": correction_info.get("confidence"),
            },
        )
        return ctx
