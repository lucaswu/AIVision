#!/usr/bin/env python3
"""Base class for IQI pipeline stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from gauge.config import PipelineConfig

# Import StageContext from the shared context module
from gauge.pipeline.context import StageContext


class PipelineStage(ABC):
    """Base class for a single pipeline stage."""

    name: str = "unnamed"

    def __init__(self, config: PipelineConfig, services: Optional[Dict[str, Any]] = None):
        self.config = config
        self.services = services or {}

    def should_run(self, ctx: StageContext) -> bool:
        """Return False to skip this stage."""
        return True

    @abstractmethod
    def run(self, ctx: StageContext) -> StageContext:
        """Execute the stage, mutating and returning the context."""
        ...
