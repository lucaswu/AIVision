#!/usr/bin/env python3
"""Unified exception hierarchy for IQI pipeline."""


class IQIError(Exception):
    """Base for all IQI pipeline business errors."""
    result_code: int = 9001
    result_name: str = "internal_error"


class IQIStageSkipped(Exception):
    """Control-flow signal: stage was skipped (not an error)."""


class ImageReadError(IQIError):
    result_code = 1001
    result_name = "image_read_failed"


class ROINotFoundError(IQIError):
    result_code = 1101
    result_name = "roi_not_found"


class ROIInvalidError(IQIError):
    result_code = 1102
    result_name = "roi_invalid"


class MarkerError(IQIError):
    result_code = 2003
    result_name = "marker_format_invalid"


class MarkerMissingJBError(MarkerError):
    result_code = 2002
    result_name = "marker_missing_jb"


class MarkerAmbiguousError(MarkerError):
    result_code = 2006
    result_name = "marker_ambiguous"


class MarkerNumberOutOfRangeError(MarkerError):
    result_code = 2007
    result_name = "marker_number_out_of_range"


class WireInferenceError(IQIError):
    result_code = 3001
    result_name = "wire_infer_failed"


class WireCountMissingError(IQIError):
    result_code = 3002
    result_name = "wire_count_missing"


class GradeError(IQIError):
    result_code = 3005
    result_name = "grade_out_of_range"
