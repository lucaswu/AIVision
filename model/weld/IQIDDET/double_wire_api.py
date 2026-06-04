#!/usr/bin/env python3
"""Root-level import facade for the double-wire analysis API."""

from gauge.app.double_wire_api import (
    DoubleWireRequest,
    DoubleWireResponse,
    close_double_wire_api,
    compute_double_wire,
    get_double_wire_service,
    init_double_wire_api,
)
from gauge.services.double_wire.service import DoubleWireService

__all__ = [
    "DoubleWireRequest",
    "DoubleWireResponse",
    "DoubleWireService",
    "close_double_wire_api",
    "compute_double_wire",
    "get_double_wire_service",
    "init_double_wire_api",
]
