#!/usr/bin/env python3
"""Pipeline stage: load image and record dimensions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from gauge.imaging.preprocess import load_image
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class ImageLoadStage(PipelineStage):
    """Load the input image and record its dimensions."""

    name = "image_load"

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})

        image = load_image(Path(ctx.image_path))
        height, width = image.shape[:2]

        ctx.image = image
        ctx.height = int(height)
        ctx.width = int(width)

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["image"] = image

        logger.info("stage_done", extra={"stage": self.name, "height": height, "width": width})
        return ctx
