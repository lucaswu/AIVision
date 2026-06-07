#!/usr/bin/env python3
"""Pipeline orchestration: PipelineRunner."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gauge.config import PipelineConfig
from gauge.exceptions import IQIError, IQIStageSkipped
from gauge.models.record import IQIRecord
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)
from gauge.pipeline.stages.correction import CorrectionStage
from gauge.pipeline.stages.full_image_ocr import FullImageOCRStage
from gauge.pipeline.stages.grade_fusion import GradeFusionStage
from gauge.pipeline.stages.image_load import ImageLoadStage
from gauge.pipeline.stages.roi_detect import ROIDetectStage
from gauge.pipeline.stages.roi_ocr import ROIOCRStage
from gauge.pipeline.stages.wire_detect import WireDetectStage


class PipelineRunner:
    """Orchestrate the execution of pipeline stages."""

    def __init__(
        self,
        config: PipelineConfig,
        stages: List[PipelineStage],
        services: Optional[Dict[str, Any]] = None,
    ):
        self.config = config
        self.stages = stages
        self.services = services or {}

    def run(
        self,
        image_path: Path,
        return_debug_artifacts: bool = False,
        debug_timer: bool = False,
    ) -> IQIRecord:
        """Run the full pipeline for a single image path."""
        ctx = StageContext(
            image_path=str(image_path),
            config=self.config,
        )
        if return_debug_artifacts:
            ctx.debug_artifacts = {}

        for stage in self.stages:
            try:
                if not stage.should_run(ctx):
                    logger.debug("stage_skipped", extra={"stage": stage.name, "image": str(image_path)})
                    continue
                ctx = stage.run(ctx)
            except IQIStageSkipped:
                logger.debug("stage_skipped", extra={"stage": stage.name, "image": str(image_path)})
                continue
            except IQIError as exc:
                logger.warning(
                    "stage_error",
                    extra={
                        "stage": stage.name,
                        "result_code": exc.result_code,
                        "result_name": exc.result_name,
                        "result_message": str(exc),
                    },
                )
                ctx.record_errors.append(
                    {
                        "stage": stage.name,
                        "result_code": exc.result_code,
                        "result_name": exc.result_name,
                        "result_message": str(exc),
                    }
                )
            except Exception as exc:
                logger.error(
                    "stage_crashed",
                    extra={"stage": stage.name, "error": str(exc)},
                )
                return IQIRecord.create_error(
                    9001,
                    f"{stage.name}: {str(exc)}",
                    image_path=str(image_path),
                )

        return ctx.to_record()

    @classmethod
    def from_config(
        cls,
        config: PipelineConfig,
        services: Optional[Dict[str, Any]] = None,
    ) -> "PipelineRunner":
        """Factory: build a PipelineRunner from config with all standard stages."""
        services = services or {}
        stages: List[PipelineStage] = [
            ImageLoadStage(config, services),
            CorrectionStage(config, services),
            FullImageOCRStage(config, services),
            ROIDetectStage(config, services),
            ROIOCRStage(config, services),
            WireDetectStage(config, services),
            GradeFusionStage(config, services),
        ]
        return cls(config, stages, services)
