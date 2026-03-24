#!/usr/bin/env python3
"""IQI marker parsing, general OCR field extraction, and grade fusion rules."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_ALLOWED_NUMBERS = frozenset({6, 10, 11, 12, 13, 14, 15})
DEFAULT_ALLOWED_NUMBERS_SPEC = "6,10-15"

RESULT_CODE_TABLE: Dict[int, Tuple[str, str]] = {
    0: ("success", "识别成功"),
    1001: ("image_read_failed", "图像读取失败"),
    1101: ("roi_not_found", "像质计区域识别失败"),
    1102: ("roi_invalid", "像质计区域裁剪失败"),
    2001: ("ocr_no_text", "像质计标识识别失败：ROI 内未检测到文本"),
    2002: ("marker_missing_jb", "像质计标识识别失败：未识别到 J / JB"),
    2003: ("marker_format_invalid", "像质计标识识别失败：无法组成合法标识"),
    2004: ("marker_type_unknown", "像质计标识识别失败：类型既不是 FE 也不是 NI"),
    2005: ("marker_number_missing", "像质计标识识别失败：未解析出两位数字"),
    2006: ("marker_ambiguous", "像质计标识识别失败：存在多个冲突候选"),
    2007: ("marker_number_out_of_range", "像质计标识识别失败：数字不在允许范围内"),
    3001: ("wire_infer_failed", "像质丝识别失败"),
    3002: ("wire_count_missing", "像质丝识别失败：未得到有效丝数"),
    3003: ("wire_count_insufficient_uniform", "均匀像质计等级无效：像质丝数量必须大于 2"),
    3004: ("wire_count_insufficient_gradient", "渐变像质计等级无效：像质丝数量必须大于等于 1"),
    3005: ("grade_out_of_range", "像质计等级计算结果越界"),
    9001: ("internal_error", "内部异常"),
}

MARKER_ERROR_CODES = {2001, 2002, 2003, 2004, 2005, 2006, 2007}
WIRE_ERROR_CODES = {3001, 3002, 3003, 3004, 3005}
ROI_ERROR_CODES = {1101, 1102}

_COMPONENT_CODE_PATTERN = re.compile(r"\d+[SR]\d+")
_WELD_FILM_PATTERN = re.compile(r"(\d*)\s*([+-])\s*(\d+[A-Z]?)")
_PIPE_SPEC_PATTERN = re.compile(r"(\d+)\s*[Xx×]\s*(\d+)")


@dataclass(frozen=True)
class PlateCandidate:
    code: str
    iqi_type: str
    number: int
    corrections: Tuple[str, ...]
    source_text: str


@dataclass(frozen=True)
class TypeEvidence:
    iqi_type: str
    standard_prefix: str
    corrections: Tuple[str, ...]
    raw_marker: str
    position: int
    exact: bool


@dataclass(frozen=True)
class NumberEvidence:
    number: int
    corrections: Tuple[str, ...]


def build_result_status(code: int, message: Optional[str] = None) -> Dict[str, Any]:
    name, default_message = RESULT_CODE_TABLE.get(int(code), ("unknown_error", "未知错误"))
    return {
        "ok": int(code) == 0,
        "result_code": int(code),
        "result_name": name,
        "result_message": default_message if message is None else str(message),
    }


def normalize_text(text: Any) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def normalize_field_text(text: Any) -> str:
    return re.sub(r"\s+", "", str(text).upper())


def parse_allowed_numbers_spec(spec: Optional[str]) -> frozenset[int]:
    if spec is None or not str(spec).strip():
        return DEFAULT_ALLOWED_NUMBERS
    values = set()
    for raw_part in str(spec).split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if end < start:
                raise ValueError(f"Invalid allowed number range: {part}")
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    if not values:
        raise ValueError("Allowed number spec produced an empty set.")
    return frozenset(sorted(values))


def format_allowed_numbers_spec(numbers: Sequence[int]) -> str:
    ordered = sorted({int(x) for x in numbers})
    if not ordered:
        return ""
    chunks: List[str] = []
    start = ordered[0]
    prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        chunks.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = value
    chunks.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(chunks)


def is_allowed_number(value: int, allowed_numbers: Optional[Sequence[int]] = None) -> bool:
    allowed = DEFAULT_ALLOWED_NUMBERS if allowed_numbers is None else frozenset(int(x) for x in allowed_numbers)
    return int(value) in allowed


def _box_center(item: Dict[str, Any]) -> Tuple[float, float]:
    box = item.get("box")
    if not isinstance(box, list) or not box:
        return 0.0, 0.0
    xs = [float(pt[0]) for pt in box if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    ys = [float(pt[1]) for pt in box if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if not xs or not ys:
        return 0.0, 0.0
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _sort_items_yx(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (_box_center(item)[1], _box_center(item)[0]))


def _sort_items_xy(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (_box_center(item)[0], _box_center(item)[1]))


def _dedupe_preserve(items: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _build_text_sequences(texts: Sequence[str]) -> List[str]:
    return _dedupe_preserve(normalize_text(text) for text in texts if normalize_text(text))


def _text_sequences_from_items(items: Sequence[Dict[str, Any]]) -> List[str]:
    return _dedupe_preserve(
        normalize_text(item.get("text", ""))
        for item in items
        if normalize_text(item.get("text", ""))
    )


def _iter_usable_ocr_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        item
        for item in items
        if str(item.get("text", "")).strip() and item.get("status") != "error" and item.get("accepted_by_score", True)
    ]


def _base_field_record(item: Dict[str, Any], match_text: str) -> Dict[str, Any]:
    return {
        "text": str(item.get("text", "")),
        "match_text": str(match_text),
        "score": item.get("score"),
        "box": item.get("box"),
        "crop_index": item.get("crop_index"),
    }


def _dedupe_records(records: Sequence[Dict[str, Any]], key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def extract_component_codes_from_ocr_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in _iter_usable_ocr_items(items):
        cleaned = normalize_field_text(item.get("text", ""))
        for match in _COMPONENT_CODE_PATTERN.finditer(cleaned):
            value = match.group(0)
            record = _base_field_record(item, value)
            record["value"] = value
            records.append(record)
    return _dedupe_records(records, ("value",))


def extract_weld_film_from_ocr_items(items: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    pair_records: List[Dict[str, Any]] = []
    weld_records: List[Dict[str, Any]] = []
    film_records: List[Dict[str, Any]] = []

    for item in _iter_usable_ocr_items(items):
        cleaned = normalize_field_text(item.get("text", ""))
        for match in _WELD_FILM_PATTERN.finditer(cleaned):
            full = match.group(0)
            weld_no = match.group(1) or ""
            separator = match.group(2)
            film_no = match.group(3)

            pair_record = _base_field_record(item, full)
            pair_record.update(
                {
                    "weld_no": weld_no,
                    "film_no": film_no,
                    "separator": separator,
                }
            )
            pair_records.append(pair_record)

            if weld_no:
                weld_record = _base_field_record(item, full)
                weld_record["value"] = weld_no
                weld_records.append(weld_record)

            film_record = _base_field_record(item, full)
            film_record["value"] = film_no
            film_records.append(film_record)

    return {
        "weld_film_pairs": _dedupe_records(pair_records, ("weld_no", "film_no")),
        "weld_numbers": _dedupe_records(weld_records, ("value",)),
        "film_numbers": _dedupe_records(film_records, ("value",)),
    }


def extract_pipe_specs_from_ocr_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in _iter_usable_ocr_items(items):
        cleaned = normalize_field_text(item.get("text", ""))
        for match in _PIPE_SPEC_PATTERN.finditer(cleaned):
            outer = match.group(1)
            wall = match.group(2)
            normalized = f"{outer}X{wall}"
            record = _base_field_record(item, match.group(0))
            record.update(
                {
                    "value": normalized,
                    "outer_diameter": outer,
                    "wall_thickness": wall,
                }
            )
            records.append(record)
    return _dedupe_records(records, ("value",))


def extract_general_fields_from_ocr_items(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    component_codes = extract_component_codes_from_ocr_items(items)
    weld_film = extract_weld_film_from_ocr_items(items)
    pipe_specs = extract_pipe_specs_from_ocr_items(items)
    fields = {
        "component_codes": component_codes,
        "weld_film_pairs": weld_film["weld_film_pairs"],
        "weld_numbers": weld_film["weld_numbers"],
        "film_numbers": weld_film["film_numbers"],
        "pipe_specs": pipe_specs,
    }
    field_statistics = {
        "component_code_count": len(component_codes),
        "weld_film_pair_count": len(weld_film["weld_film_pairs"]),
        "weld_number_count": len(weld_film["weld_numbers"]),
        "film_number_count": len(weld_film["film_numbers"]),
        "pipe_spec_count": len(pipe_specs),
        "general_fields_found": any(len(value) > 0 for value in fields.values()),
    }
    return {
        "fields": fields,
        "field_statistics": field_statistics,
    }


def _parse_digit_char(ch: str, allow_i: bool) -> Tuple[Optional[str], Optional[str]]:
    if ch.isdigit():
        return ch, None
    if ch == "O":
        return "0", "O->0"
    if ch == "L":
        return "1", "L->1"
    if allow_i and ch == "I":
        return "1", "I->1"
    return None, None


def _parse_digit_token(token: str, allow_i: bool) -> Optional[NumberEvidence]:
    if len(token) not in {1, 2}:
        return None
    mapped: List[str] = []
    corrections: List[str] = []
    for idx, ch in enumerate(token):
        digit, correction = _parse_digit_char(ch, allow_i=allow_i)
        if digit is None:
            return None
        mapped.append(digit)
        if correction is not None:
            corrections.append(f"{ch}@{idx}->{digit}")
    return NumberEvidence(number=int("".join(mapped)), corrections=tuple(corrections))


def _find_type_evidences(sequence: str, require_jb: bool) -> List[TypeEvidence]:
    seq = normalize_text(sequence)
    evidences: List[TypeEvidence] = []

    def add_exact(raw_marker: str, iqi_type: str, standard_prefix: str, corrections: Sequence[str]) -> None:
        start = 0
        while True:
            idx = seq.find(raw_marker, start)
            if idx < 0:
                break
            evidences.append(
                TypeEvidence(
                    iqi_type=iqi_type,
                    standard_prefix=standard_prefix,
                    corrections=tuple(corrections),
                    raw_marker=raw_marker,
                    position=idx,
                    exact=True,
                )
            )
            start = idx + 1

    add_exact("FE", "uniform", "FE", [])
    add_exact("NI", "gradient", "NI", [])
    add_exact("EE", "uniform", "FE", ["EE->FE"])
    add_exact("N1", "gradient", "NI", ["N1->NI"])
    add_exact("NL", "gradient", "NI", ["NL->NI"])

    if "J" in seq:
        if "E" in seq:
            evidences.append(
                TypeEvidence(
                    iqi_type="uniform",
                    standard_prefix="FE",
                    corrections=("E+J->FE",),
                    raw_marker="",
                    position=-1,
                    exact=False,
                )
            )
        if "I" in seq:
            evidences.append(
                TypeEvidence(
                    iqi_type="gradient",
                    standard_prefix="NI",
                    corrections=("I+J->NI",),
                    raw_marker="",
                    position=-1,
                    exact=False,
                )
            )
    elif require_jb:
        return []

    unique: Dict[Tuple[str, str, Tuple[str, ...], str, int, bool], TypeEvidence] = {}
    for evidence in evidences:
        key = (
            evidence.iqi_type,
            evidence.standard_prefix,
            evidence.corrections,
            evidence.raw_marker,
            evidence.position,
            evidence.exact,
        )
        unique[key] = evidence
    return list(unique.values())


def _collect_preferred_numbers(sequence: str, evidences: Sequence[TypeEvidence]) -> List[NumberEvidence]:
    seq = normalize_text(sequence)
    outputs: Dict[int, NumberEvidence] = {}
    for evidence in evidences:
        if not evidence.exact or not evidence.raw_marker:
            continue

        start = evidence.position + len(evidence.raw_marker)
        for token in (seq[start:start + 2], seq[start:start + 1]):
            parsed = _parse_digit_token(token, allow_i=True)
            if parsed is not None:
                outputs.setdefault(parsed.number, parsed)

        before_end = evidence.position
        for token in (seq[max(0, before_end - 2):before_end], seq[max(0, before_end - 1):before_end]):
            parsed = _parse_digit_token(token, allow_i=True)
            if parsed is not None:
                outputs.setdefault(parsed.number, parsed)
    return list(outputs.values())


def _collect_generic_numbers(sequence: str) -> List[NumberEvidence]:
    seq = normalize_text(sequence)
    outputs: Dict[int, NumberEvidence] = {}
    for idx in range(0, max(len(seq) - 1, 0)):
        pair = seq[idx:idx + 2]
        parsed = _parse_digit_token(pair, allow_i=False)
        if parsed is None:
            continue
        outputs.setdefault(parsed.number, parsed)

    for idx, ch in enumerate(seq):
        if not ch.isdigit():
            continue
        prev_is_digit = idx > 0 and seq[idx - 1].isdigit()
        next_is_digit = idx + 1 < len(seq) and seq[idx + 1].isdigit()
        if prev_is_digit or next_is_digit:
            continue
        parsed = _parse_digit_token(ch, allow_i=False)
        if parsed is not None:
            outputs.setdefault(parsed.number, parsed)
    return list(outputs.values())


def _build_candidates_from_sequence(
    sequence: str,
    require_jb: bool,
    allowed_numbers: Optional[Sequence[int]] = None,
) -> Tuple[List[PlateCandidate], List[int]]:
    seq = normalize_text(sequence)
    if not seq:
        return [], []
    if require_jb and "J" not in seq:
        return [], [2002]

    type_evidences = _find_type_evidences(seq, require_jb=require_jb)
    if not type_evidences:
        return [], [2004 if "J" in seq or not require_jb else 2002]

    preferred_numbers = _collect_preferred_numbers(seq, type_evidences)
    number_evidences = preferred_numbers if preferred_numbers else _collect_generic_numbers(seq)
    if not number_evidences:
        return [], [2005]

    valid_numbers = [entry for entry in number_evidences if is_allowed_number(entry.number, allowed_numbers)]
    if not valid_numbers:
        return [], [2007]

    candidates: List[PlateCandidate] = []
    for evidence in type_evidences:
        for number_entry in valid_numbers:
            code = f"{evidence.standard_prefix}{number_entry.number:02d}JB" if require_jb else f"{evidence.standard_prefix}{number_entry.number:02d}"
            candidates.append(
                PlateCandidate(
                    code=code,
                    iqi_type=evidence.iqi_type,
                    number=number_entry.number,
                    corrections=tuple(list(evidence.corrections) + list(number_entry.corrections)),
                    source_text=seq,
                )
            )
    return candidates, []


def infer_plate_from_texts(
    texts: Sequence[str],
    require_jb: bool = False,
    allowed_numbers: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    raw_texts = [str(text) for text in texts if str(text).strip()]
    normalized_texts = [normalize_text(text) for text in raw_texts]
    normalized_texts = [text for text in normalized_texts if text]

    if not normalized_texts:
        return {
            **build_result_status(2001),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": raw_texts,
            "normalized_texts": normalized_texts,
            "candidate_codes": [],
            "corrections": [],
        }

    sequences = _build_text_sequences(normalized_texts)
    all_candidates: List[PlateCandidate] = []
    error_codes: List[int] = []
    for sequence in sequences:
        candidates, seq_errors = _build_candidates_from_sequence(
            sequence,
            require_jb=require_jb,
            allowed_numbers=allowed_numbers,
        )
        all_candidates.extend(candidates)
        error_codes.extend(seq_errors)

    if not all_candidates:
        if require_jb and not any("J" in seq for seq in sequences):
            code = 2002
        elif 2007 in error_codes:
            code = 2007
        elif 2004 in error_codes:
            code = 2004
        elif 2005 in error_codes:
            code = 2005
        else:
            code = 2003
        return {
            **build_result_status(code),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": raw_texts,
            "normalized_texts": normalized_texts,
            "candidate_codes": [],
            "corrections": [],
        }

    unique_codes = _dedupe_preserve(candidate.code for candidate in all_candidates)
    if len(unique_codes) > 1:
        return {
            **build_result_status(2006),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": raw_texts,
            "normalized_texts": normalized_texts,
            "candidate_codes": unique_codes,
            "corrections": sorted({corr for candidate in all_candidates for corr in candidate.corrections}),
        }

    chosen = next(candidate for candidate in all_candidates if candidate.code == unique_codes[0])
    return {
        **build_result_status(0),
        "iqi_type": chosen.iqi_type,
        "number": chosen.number,
        "plate_code": chosen.code,
        "raw_texts": raw_texts,
        "normalized_texts": normalized_texts,
        "candidate_codes": unique_codes,
        "corrections": list(chosen.corrections),
    }


def infer_plate_from_ocr_items(
    items: Sequence[Dict[str, Any]],
    require_jb: bool = True,
    allowed_numbers: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    usable_items = _iter_usable_ocr_items(items)
    raw_texts = [str(item.get("text", "")) for item in usable_items]
    normalized_texts = [normalize_text(text) for text in raw_texts]
    sequences = _text_sequences_from_items(usable_items)
    if not usable_items:
        return {
            **build_result_status(2001),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": [],
            "normalized_texts": [],
            "candidate_codes": [],
            "corrections": [],
            "sequence_candidates": [],
        }

    all_candidates: List[PlateCandidate] = []
    error_codes: List[int] = []
    for sequence in sequences:
        candidates, seq_errors = _build_candidates_from_sequence(
            sequence,
            require_jb=require_jb,
            allowed_numbers=allowed_numbers,
        )
        all_candidates.extend(candidates)
        error_codes.extend(seq_errors)

    if not all_candidates:
        if require_jb and not any("J" in sequence for sequence in sequences):
            code = 2002
        elif 2007 in error_codes:
            code = 2007
        elif 2004 in error_codes:
            code = 2004
        elif 2005 in error_codes:
            code = 2005
        else:
            code = 2003
        return {
            **build_result_status(code),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": raw_texts,
            "normalized_texts": normalized_texts,
            "candidate_codes": [],
            "corrections": [],
            "sequence_candidates": sequences,
        }

    unique_codes = _dedupe_preserve(candidate.code for candidate in all_candidates)
    if len(unique_codes) > 1:
        return {
            **build_result_status(2006),
            "iqi_type": None,
            "number": None,
            "plate_code": None,
            "raw_texts": raw_texts,
            "normalized_texts": normalized_texts,
            "candidate_codes": unique_codes,
            "corrections": sorted({corr for candidate in all_candidates for corr in candidate.corrections}),
            "sequence_candidates": sequences,
        }

    chosen = next(candidate for candidate in all_candidates if candidate.code == unique_codes[0])
    return {
        **build_result_status(0),
        "iqi_type": chosen.iqi_type,
        "number": chosen.number,
        "plate_code": chosen.code,
        "raw_texts": raw_texts,
        "normalized_texts": normalized_texts,
        "candidate_codes": unique_codes,
        "corrections": list(chosen.corrections),
        "sequence_candidates": sequences,
    }


def compute_iqi_grade(
    iqi_type: Optional[str],
    number: Optional[int],
    wire_count: Optional[int],
    allowed_numbers: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    if iqi_type not in {"uniform", "gradient"} or number is None:
        return {
            **build_result_status(2003 if number is not None else 2005),
            "grade": 0,
            "wire_count": wire_count,
        }

    if not is_allowed_number(int(number), allowed_numbers):
        return {
            **build_result_status(2007),
            "grade": 0,
            "wire_count": wire_count,
        }

    if wire_count is None:
        return {
            **build_result_status(3002),
            "grade": 0,
            "wire_count": None,
        }

    if iqi_type == "uniform":
        if wire_count > 2:
            grade = int(number)
            code = 0
        else:
            grade = 0
            code = 3003
    else:
        if wire_count >= 1:
            grade = int(number) + int(wire_count) - 1
            code = 0
        else:
            grade = 0
            code = 3004

    if code == 0 and not (0 <= int(grade) <= 99):
        return {
            **build_result_status(3005),
            "grade": 0,
            "wire_count": int(wire_count),
        }

    return {
        **build_result_status(code),
        "grade": int(grade),
        "wire_count": int(wire_count),
    }


def choose_primary_result_code(codes: Sequence[int]) -> int:
    codes = [int(code) for code in codes if int(code) != 0]
    if not codes:
        return 0
    for code in codes:
        if code in ROI_ERROR_CODES:
            return code
    for code in codes:
        if code in MARKER_ERROR_CODES:
            return code
    for code in codes:
        if code in WIRE_ERROR_CODES:
            return code
    return codes[0]


def summarize_result_codes(records: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter()
    for record in records:
        counter[str(int(record.get("result_code", 9001)))] += 1
    return {key: int(value) for key, value in sorted(counter.items(), key=lambda item: int(item[0]))}


def summarize_result_codes_named(records: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter()
    for record in records:
        code = int(record.get("result_code", 9001))
        name = RESULT_CODE_TABLE.get(code, ("unknown_error",))[0]
        counter[f"{code}({name})"] += 1
    return {
        key: int(value)
        for key, value in sorted(counter.items(), key=lambda item: int(item[0].split("(", 1)[0]))
    }
