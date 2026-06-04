"""Double-wire IQI contrast analysis.

Functions for analyzing double-wire (BAM) IQI strip profiles:
peak/valley detection, film-type determination, background fitting,
wire pairing, dip computation, and first-unresolved-group finding.

Split from profile.py on 2026-06-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import find_peaks, savgol_filter

from gauge.imaging.profile import detect_peaks_valleys

# JBT 7902-2025 表2 标准双丝型像质计 D1~D13 丝径/间距 (mm)
_DEFAULT_WIRE_SPACINGS: Tuple[float, ...] = (
    0.80, 0.63, 0.50, 0.40, 0.32, 0.25, 0.20, 0.16, 0.13, 0.10, 0.08, 0.063, 0.05,
)


@dataclass
class ComputeContrastResult:
    """Result of :func:`compute_contrast`.

    Attributes:
        dips: Dip (modulation depth) for each wire pair, in percent [0, 100].
        pairs: Detected (wire_a_idx, gap_idx, wire_b_idx) triplets.
            The tuple uses neutral wire/gap semantics independent of film type.
        background: Quadratic background fit values, same length as the input
            profile.
        film_type: ``"positive"`` or ``"negative"``.
    """
    dips: List[float]
    pairs: List[Tuple[int, int, int]]
    background: np.ndarray
    film_type: str


def _detect_film_type(
    profile: np.ndarray,
    valleys: np.ndarray,
    peaks: np.ndarray,
) -> str:
    """Determine film type from raw peak/valley positions.

    Works by finding the alternating triple (v-p-v or p-v-p) with the
    largest amplitude swing.  The dominant wire pair produces the largest
    swing, and its pattern reveals the film type:

    - p-v-p with tall peaks   -> positive film (wires are bright peaks)
    - v-p-v with deep valleys -> negative film (wires are dark valleys)

    Args:
        profile: 1D band-averaged gray profile.
        valleys: Valley index array (positions of profile minima).
        peaks: Peak index array (positions of profile maxima).

    Returns:
        ``"positive"`` or ``"negative"``.  Defaults to ``"positive"`` when
        no reliable alternating triple is found.
    """
    if len(valleys) < 1 or len(peaks) < 1:
        return "positive"

    # Merge extrema in position order
    extrema: List[Tuple[str, int]] = []
    vi = pi = 0
    while vi < len(valleys) or pi < len(peaks):
        if pi >= len(peaks) or (vi < len(valleys) and int(valleys[vi]) < int(peaks[pi])):
            extrema.append(("v", int(valleys[vi])))
            vi += 1
        else:
            extrema.append(("p", int(peaks[pi])))
            pi += 1

    # Find the alternating triple with the largest total swing
    best_type: Optional[str] = None
    best_swing = -1.0
    for i in range(len(extrema) - 2):
        t1, p1 = extrema[i]
        t2, p2 = extrema[i + 1]
        t3, p3 = extrema[i + 2]
        if t1 == t3 and t1 != t2:
            swing = abs(float(profile[p1]) - float(profile[p2])) + abs(
                float(profile[p2]) - float(profile[p3])
            )
            if swing > best_swing:
                best_swing = swing
                best_type = t1

    if best_type == "p":
        return "positive"
    if best_type == "v":
        return "negative"
    return "positive"


def _fit_quadratic_background(
    profile: np.ndarray,
    wire_indices: np.ndarray,
    *,
    inverted: bool = False,
) -> np.ndarray:
    """Estimate a smoothly-varying background via Savitzky-Golay low-pass filter.

    Unlike a single quadratic fit (which can overshoot in regions of strong
    wire modulation), the Savitzky-Golay filter with a wide window acts as a
    local low-pass estimator that naturally follows the gap-region baseline
    while ignoring narrow wire features.  This fixes the dip inversion seen
    when ``C >> A, B`` for coarse pairs (RC-4).

    The *wire_indices* and *inverted* parameters are kept for API
    compatibility with the ctsimu-toolbox-inspired interface; they are not
    used by this implementation.

    Args:
        profile: 1D band-averaged gray profile.
        wire_indices: Unused -- kept for caller compatibility.
        inverted: Unused -- kept for caller compatibility.

    Returns:
        1D ndarray of background values, same length as *profile*.
    """
    n = len(profile)
    # Wide window captures only the low-frequency trend (gap baseline)
    window = min(n // 8 * 2 + 1, 201)  # odd, <= 201
    if window < 9:
        window = 9
    if window % 2 == 0:
        window += 1
    if window > n:
        window = n if n % 2 == 1 else n - 1
        if window < 5:
            # Profile too short for meaningful low-pass -- return the mean
            return np.full(n, float(np.mean(profile)), dtype=np.float64)
    bg = savgol_filter(profile.astype(np.float64), window, 2, mode='mirror')
    return bg.astype(np.float64)


def _compute_dip(
    profile: np.ndarray,
    wire_a: int,
    gap_c: int,
    wire_b: int,
    background: np.ndarray,
    half_w: int,
) -> float:
    """Compute the modulation depth (dip) for a single wire pair.

    The dip is defined as ``100 * (A + B - 2*C) / (A + B)`` where *A*, *B*
    are the absolute deviations of the two wires from the background and *C*
    is the absolute deviation of the gap from the background.  Each value is
    taken as the neighbourhood mean of width ``2*half_w+1`` around the
    detected position.

    Args:
        profile: 1D band-averaged gray profile.
        wire_a: Index of the first wire.
        gap_c: Index of the gap between the two wires.
        wire_b: Index of the second wire.
        background: Background fit values (same length as *profile*).
        half_w: Half-width of the neighbourhood window.

    Returns:
        Dip value in percent [0, 100].  Returns 0 when the denominator is
        negligible (fully merged pair).
    """
    L = len(profile)

    def _region_mean(center: int) -> float:
        lo = max(0, center - half_w)
        hi = min(L - 1, center + half_w)
        return float(profile[lo:hi + 1].mean())

    a_mean = _region_mean(wire_a)
    c_mean = _region_mean(gap_c)
    b_mean = _region_mean(wire_b)

    A = abs(float(background[wire_a]) - a_mean)
    B = abs(float(background[wire_b]) - b_mean)
    C = abs(float(background[gap_c]) - c_mean)

    denom = A + B
    if denom < 1e-10:
        return 0.0
    dip = 100.0 * (A + B - 2.0 * C) / denom
    return max(0.0, dip)


def _pair_wires_and_compute_dips(
    profile: np.ndarray,
    wire_positions: np.ndarray,
    gap_positions: np.ndarray,
    background: np.ndarray,
    half_w: int,
    *,
    dist_factor: float = 1.05,
    film_type: str = "positive",
) -> Tuple[List[float], List[Tuple[int, int, int]]]:
    """Pair adjacent wires into wire-pair groups and compute each dip.

    Two adjacent wire positions are paired when their distance does not
    exceed ``dist_factor * dist_between_first_two``.  The gap (the profile
    extremum between the two wires) is located in a film-type-aware manner,
    and the dip for the pair is computed via :func:`_compute_dip`.

    Args:
        profile: 1D band-averaged gray profile.
        wire_positions: Sorted indices of wire positions (peaks for
            positive film, valleys for negative).
        gap_positions: Sorted indices of gap positions (valleys for positive,
            peaks for negative).
        background: Quadratic background fit, same length as *profile*.
        half_w: Half-window for neighbourhood-averaged dip computation.
        dist_factor: Maximum allowed multiple of the first-pair spacing
            for two wires to be considered a pair.
        film_type: ``"positive"`` or ``"negative"``.

    Returns:
        ``(dips, pairs)`` where *dips* is a list of float percentages and
        *pairs* is the corresponding list of ``(wire_a, gap, wire_b)``
        index triplets.
    """
    dips: List[float] = []
    pairs: List[Tuple[int, int, int]] = []

    if len(wire_positions) < 2:
        return dips, pairs

    dist = wire_positions[1:] - wire_positions[:-1]
    # Use median of the first few inter-wire distances as reference,
    # which is robust against a single spurious leading pair (RC-3).
    k = min(5, len(dist))
    ref_dist = float(np.median(dist[:k]))
    if ref_dist < 1.0:
        ref_dist = float(dist[0])
    dist_max = dist_factor * ref_dist

    i = 0
    while i < len(wire_positions) - 1:
        if dist[i] <= dist_max:
            w1 = int(wire_positions[i])
            w2 = int(wire_positions[i + 1])
            gap_mask = (gap_positions > w1) & (gap_positions < w2)
            gaps_between = gap_positions[gap_mask]
            if len(gaps_between) >= 1:
                if film_type == "positive":
                    c = int(gaps_between[np.argmin(profile[gaps_between])])
                else:
                    c = int(gaps_between[np.argmax(profile[gaps_between])])
                pairs.append((w1, c, w2))
                dip = _compute_dip(profile, w1, c, w2, background, half_w)
                dips.append(dip)
        i += 1

    return dips, pairs


def _trim_pairs_to_stable_center_prefix(
    pairs: Sequence[Tuple[int, int, int]],
) -> List[Tuple[int, int, int]]:
    """Keep the physically ordered prefix before a large center-spacing jump."""
    if len(pairs) <= 2:
        return list(pairs)

    kept = [pairs[0]]
    center_gaps: List[int] = []
    prev_center = pairs[0][1]

    for pair in pairs[1:]:
        center = pair[1]
        delta = center - prev_center
        if center_gaps:
            ref = float(np.median(center_gaps))
            if delta > max(ref * 1.8, ref + 20.0):
                break
        center_gaps.append(delta)
        kept.append(pair)
        prev_center = center

    return kept


def _remove_overlapping_pairs(
    pairs: List[Tuple[int, int, int]],
    profile: np.ndarray,
    *,
    film_type: str,
) -> List[Tuple[int, int, int]]:
    """Remove spurious pairs that share a wire position with a neighbour.

    When two consecutive candidate pairs share the same wire index (the
    first pair's wire_b equals the second pair's wire_a), one of them is
    a spurious detection.  The pair with the stronger gap--wire contrast
    (more likely to be a real wire pair) is kept.
    """
    if len(pairs) <= 1:
        return list(pairs)

    keep = [True] * len(pairs)
    for i in range(len(pairs) - 1):
        if not keep[i]:
            continue
        _, _, w1_b = pairs[i]
        w2_a, _, _ = pairs[i + 1]
        if w1_b != w2_a:
            continue

        # Compute contrast score: gap--wire deviation per the film type.
        w1_a, w1_g, _ = pairs[i]
        _, w2_g, w2_b = pairs[i + 1]
        if film_type == "positive":
            s1 = min(
                float(profile[w1_a]) - float(profile[w1_g]),
                float(profile[w1_b]) - float(profile[w1_g]),
            )
            s2 = min(
                float(profile[w2_a]) - float(profile[w2_g]),
                float(profile[w2_b]) - float(profile[w2_g]),
            )
        else:
            s1 = min(
                float(profile[w1_g]) - float(profile[w1_a]),
                float(profile[w1_g]) - float(profile[w1_b]),
            )
            s2 = min(
                float(profile[w2_g]) - float(profile[w2_a]),
                float(profile[w2_g]) - float(profile[w2_b]),
            )
        if s1 >= s2:
            keep[i + 1] = False
        else:
            keep[i] = False

    return [p for i, p in enumerate(pairs) if keep[i]]


def _pair_direction_scores(
    profile: np.ndarray,
    pairs: Sequence[Tuple[int, int, int]],
    *,
    film_type: str,
) -> List[float]:
    """Return per-pair contrast direction scores for film-type selection."""
    scores: List[float] = []
    for w1, gap, w2 in pairs:
        if film_type == "positive":
            score = min(float(profile[w1] - profile[gap]), float(profile[w2] - profile[gap]))
        else:
            score = min(float(profile[gap] - profile[w1]), float(profile[gap] - profile[w2]))
        scores.append(score)
    return scores


def _recover_tail_pair(
    profile: np.ndarray,
    pairs: List[Tuple[int, int, int]],
    background: np.ndarray,
    half_w: int,
    *,
    film_type: str,
) -> List[Tuple[int, int, int]]:
    """Try to recover the finest wire pair missing after the last detected one.

    The fine-prominence extrema detection can miss the very last (finest)
    wire pair because its modulation is too shallow to meet the prominence
    threshold.  When the last detected pair is far enough from the profile
    end, this function scans the tail region with relaxed criteria to
    recover the missing pair.
    """
    if len(pairs) < 2:
        return pairs

    last_w1, last_gap, last_w2 = pairs[-1]

    # Estimate expected next-pair position from the centre-spacing trend.
    centers = [p[1] for p in pairs]
    if len(centers) >= 3:
        # Use the median of the last three centre spacings
        recent_deltas = [centers[i + 1] - centers[i] for i in range(len(centers) - 3, len(centers) - 1)]
        expected_delta = float(np.median(recent_deltas)) if recent_deltas else 30.0
    else:
        expected_delta = float(centers[-1] - centers[-2])

    search_start = last_w2 + 3
    search_end = min(len(profile), centers[-1] + int(expected_delta * 1.5))

    if search_end - search_start < 5:
        return pairs

    # In the tail region, find all local extrema with minimal filtering.
    tail = profile[search_start:search_end]
    tail_range = float(tail.max() - tail.min())
    if tail_range < 1e-10:
        return pairs

    # Use a very low prominence threshold restricted to the tail.
    tail_peaks, _ = find_peaks(tail, distance=1, prominence=tail_range * 0.01)
    tail_valleys, _ = find_peaks(-tail, distance=1, prominence=tail_range * 0.01)

    if len(tail_peaks) == 0 or len(tail_valleys) == 0:
        return pairs

    # Map back to global indices
    tail_peaks_g = np.asarray([int(p) + search_start for p in tail_peaks], dtype=int)
    tail_valleys_g = np.asarray([int(v) + search_start for v in tail_valleys], dtype=int)

    # Build candidate triplets from adjacent wires.
    if film_type == "negative":
        wire_pos = tail_valleys_g
        gap_pos = tail_peaks_g
    else:
        wire_pos = tail_peaks_g
        gap_pos = tail_valleys_g

    best_pair = None
    best_score = -1.0
    for i in range(len(wire_pos) - 1):
        w1 = int(wire_pos[i])
        w2 = int(wire_pos[i + 1])
        gaps = gap_pos[(gap_pos > w1) & (gap_pos < w2)]
        if len(gaps) == 0:
            continue

        if film_type == "positive":
            gap = int(gaps[np.argmin(profile[gaps])])
            if not (profile[gap] < profile[w1] and profile[gap] < profile[w2]):
                continue
            score = min(float(profile[w1] - profile[gap]), float(profile[w2] - profile[gap]))
        else:
            gap = int(gaps[np.argmax(profile[gaps])])
            if not (profile[gap] > profile[w1] and profile[gap] > profile[w2]):
                continue
            score = min(float(profile[gap] - profile[w1]), float(profile[gap] - profile[w2]))

        # Prefer the pair closest to the expected centre position with
        # reasonable spacing.
        center = gap
        pos_score = -abs(center - (centers[-1] + expected_delta))
        combined = score + 0.1 * pos_score
        if combined > best_score:
            best_score = combined
            best_pair = (w1, gap, w2)

    if best_pair is not None:
        # Verify the new pair is a plausible successor.
        new_center = best_pair[1]
        expected_center = centers[-1] + expected_delta
        if new_center > pairs[-1][1] and abs(new_center - expected_center) <= expected_delta * 0.6:
            w1, gap, w2 = best_pair
            dip = _compute_dip(profile, w1, gap, w2, background, half_w)
            # The dip should be lower than (or close to) the last real
            # pair's dip -- finer wire pairs have less modulation, so a
            # large upward jump indicates a spurious detection.
            last_dip = _compute_dip(
                profile, pairs[-1][0], pairs[-1][1], pairs[-1][2],
                background, half_w,
            )
            if dip >= 2.0 and dip <= last_dip * 1.2:
                pairs.append(best_pair)

    return pairs


def _pair_adjacent_wires_with_gaps(
    profile: np.ndarray,
    wire_positions: np.ndarray,
    gap_positions: np.ndarray,
    background: np.ndarray,
    half_w: int,
    *,
    film_type: str,
    dist_factor: float = 1.05,
) -> Tuple[List[float], List[Tuple[int, int, int]]]:
    """Pair adjacent wire extrema using the BAM first-spacing rule.

    Positive film uses bright adjacent peaks with the darkest valley between
    them. Negative film uses dark adjacent valleys with the brightest peak
    between them.
    """
    if len(wire_positions) < 2 or len(gap_positions) == 0:
        return [], []

    wire_positions = np.asarray(sorted(int(v) for v in wire_positions), dtype=int)
    gap_positions = np.asarray(sorted(int(v) for v in gap_positions), dtype=int)

    candidates: List[Tuple[int, int, int]] = []
    candidate_dists: List[int] = []
    for idx in range(len(wire_positions) - 1):
        w1 = int(wire_positions[idx])
        w2 = int(wire_positions[idx + 1])
        gaps_between = gap_positions[(gap_positions > w1) & (gap_positions < w2)]
        if len(gaps_between) == 0:
            continue

        if film_type == "positive":
            gap = int(gaps_between[np.argmin(profile[gaps_between])])
            if not (profile[gap] < profile[w1] and profile[gap] < profile[w2]):
                continue
        else:
            gap = int(gaps_between[np.argmax(profile[gaps_between])])
            if not (profile[gap] > profile[w1] and profile[gap] > profile[w2]):
                continue

        candidates.append((w1, gap, w2))
        candidate_dists.append(w2 - w1)

    if not candidates:
        return [], []

    ref_dist = float(candidate_dists[0])
    dist_max = max(2.0, ref_dist * dist_factor)
    filtered = [
        pair for pair, dist in zip(candidates, candidate_dists)
        if dist <= dist_max
    ]
    filtered = _trim_pairs_to_stable_center_prefix(filtered)

    dips = [
        _compute_dip(profile, w1, gap, w2, background, half_w)
        for w1, gap, w2 in filtered
    ]
    return dips, filtered


def _cleanup_dips_monotonic(
    dips: Sequence[float],
    spacings: Sequence[float],
) -> Tuple[List[float], List[float]]:
    """Enforce monotonic decrease of dips from coarse (D1) to fine pairs.

    A dip that is more than 5 percentage points deeper than its
    predecessor is considered a detection anomaly; the shallower
    predecessor is removed.  This matches the ctsimu-toolbox monotonicity
    check.

    Args:
        dips: Dip values (percent) per wire pair, from coarse to fine.
        spacings: Nominal wire-pair spacings (mm), same length as *dips*.

    Returns:
        ``(cleaned_dips, cleaned_spacings)`` as new lists.
    """
    d = list(dips)
    s = list(spacings)
    i = 1
    while i < len(d):
        if (d[i] - d[i - 1]) > 5.0:
            del d[i - 1]
            del s[i - 1]
            i -= 1
        i += 1
    return d, s


def _find_crossing_group(
    dips: Sequence[float],
    spacings: Sequence[float],
    threshold: float,
    min_dip: float,
) -> Optional[int]:
    """Find the first wire-pair group whose dip falls below *threshold*.

    Performs discrete traversal (coarse -> fine) with optional quadratic
    interpolation refinement around the crossing point.

    Groups whose dip is below *min_dip* are excluded from the
    interpolation neighbourhood.

    Args:
        dips: Dip values (percent) per wire pair, D1 -> Dn.
        spacings: Nominal wire-pair spacings (mm), same length as *dips*.
        threshold: Dip percentage below which a pair is considered
            unresolved (typically 20).
        min_dip: Minimum dip (percent) for a group to be included in the
            interpolation neighbourhood (typically 1.5).

    Returns:
        1-indexed group number of the first unresolved pair, or *None*
        if all pairs are resolved.
    """
    n = len(dips)
    if n == 0:
        return None

    crossing_i = None
    for i in range(n):
        if dips[i] < threshold:
            crossing_i = i
            break

    if crossing_i is None:
        return None
    if crossing_i == 0:
        return 1

    lo = max(0, crossing_i - 1)
    hi = min(n, crossing_i + 3)

    sel_dips = list(dips[lo:hi])
    sel_spacings = list(spacings[lo:hi])

    keep = [j for j in range(len(sel_dips)) if sel_dips[j] >= min_dip]
    if len(keep) < 2:
        return crossing_i + 1

    sel_dips = [sel_dips[j] for j in keep]
    sel_spacings = [sel_spacings[j] for j in keep]

    if len(sel_spacings) < 2:
        return crossing_i + 1

    try:
        coeffs = np.polyfit(sel_spacings, sel_dips, 2)
    except (np.linalg.LinAlgError, ValueError):
        return crossing_i + 1

    a, b, c_coeff = coeffs
    roots = np.roots([a, b, c_coeff - threshold])
    valid = roots[np.isreal(roots) &
                  (roots >= min(sel_spacings)) &
                  (roots <= max(sel_spacings))].real
    if len(valid) == 0:
        return crossing_i + 1

    crossing_spacing = float(np.max(valid) if a >= 0 else np.min(valid))

    for idx, s in enumerate(spacings):
        if s <= crossing_spacing:
            return idx + 1

    return crossing_i + 1


def compute_contrast(
    profile: np.ndarray,
    wire_spacings: Optional[Sequence[float]] = None,
    window_half_width: int = 3,
    film_type: str = "auto",
    min_distance: int = 10,
    prominence: float = 0.05,
) -> ComputeContrastResult:
    """Compute the modulation depth (dip) for every wire pair in a profile.

    Orchestrates: peak/valley detection -> film-type determination ->
    quadratic background fitting -> wire pairing -> per-pair dip calculation.

    The input *profile* is expected to be the output of
    :func:`extract_profile_band`, i.e. already band-averaged across
    >= 21 pixel rows to satisfy JBT 7902.

    Args:
        profile: 1D band-averaged gray profile.  Each element is the
            column-wise mean of >= 21 pixel rows perpendicular to the
            profile direction.
        wire_spacings: Nominal spacings (mm) of the wire pairs, e.g. the
            JBT 7902 D1-D13 sequence.  Accepted for forward compatibility;
            not used internally by this function.
        window_half_width: Accepted for API compatibility.  The current BAM
            pairing path computes dips from single extrema points
            (``half_w=0``) to avoid smearing fine wire pairs.
        film_type: ``"positive"``, ``"negative"``, or ``"auto"``.  When
            ``"auto"`` the type is detected from the first wire pair.
        min_distance: Minimum pixel distance between adjacent peaks,
            forwarded to :func:`detect_peaks_valleys`.
        prominence: Relative peak prominence, forwarded to
            :func:`detect_peaks_valleys`.

    Returns:
        :class:`ComputeContrastResult` with dips, pairs, background, and
        film_type.
    """
    n = len(profile)
    if n < 3:
        return ComputeContrastResult(
            dips=[], pairs=[],
            background=np.array([], dtype=np.float64),
            film_type=film_type if film_type != "auto" else "positive",
        )

    # 1. Detrend profile for robust peak/valley detection.
    #    A quadratic polynomial fit captures the global background
    #    curvature (heel effect) without the edge artifacts of wide-
    #    kernel Savitzky-Golay filtering.  Subtracting it flattens the
    #    baseline so that local wire/gap extrema are unambiguous.
    x = np.arange(n, dtype=np.float64)
    coeffs = np.polyfit(x, profile.astype(np.float64), 2)
    trend = np.polyval(coeffs, x)
    detrended = profile.astype(np.float64) - trend

    peaks, valleys = detect_peaks_valleys(
        detrended, min_distance=min_distance, prominence=prominence,
    )

    if len(peaks) == 0 and len(valleys) == 0:
        return ComputeContrastResult(
            dips=[], pairs=[],
            background=np.zeros(n, dtype=np.float64),
            film_type=film_type if film_type != "auto" else "positive",
        )

    # 2. Film-type determination.  Build both positive and negative
    #    candidates using fine extrema, then pick the direction whose
    #    median per-pair contrast score is higher.  This replaces the
    #    old positive-only threshold check which was too permissive and
    #    overrode correct negative detections (RC-5).
    fine_peaks, fine_valleys = detect_peaks_valleys(
        detrended,
        min_distance=1,
        prominence=max(0.005, prominence * 0.5),
    )
    dip_half_w = 0

    # Positive candidate: bright wires (peaks), dark gaps (valleys)
    pos_bg = _fit_quadratic_background(profile, fine_peaks, inverted=False)
    pos_dips, pos_pairs = _pair_adjacent_wires_with_gaps(
        profile, fine_peaks, fine_valleys, pos_bg,
        half_w=dip_half_w, film_type="positive",
    )

    # Negative candidate: dark wires (valleys), bright gaps (peaks)
    neg_bg = _fit_quadratic_background(profile, fine_valleys, inverted=True)
    neg_dips, neg_pairs = _pair_adjacent_wires_with_gaps(
        profile, fine_valleys, fine_peaks, neg_bg,
        half_w=dip_half_w, film_type="negative",
    )

    if film_type == "auto":
        pos_scores = _pair_direction_scores(profile, pos_pairs, film_type="positive")
        neg_scores = _pair_direction_scores(profile, neg_pairs, film_type="negative")
        pos_med = float(np.median(pos_scores)) if pos_scores else 0.0
        neg_med = float(np.median(neg_scores)) if neg_scores else 0.0

        profile_range = float(np.max(profile) - np.min(profile))
        norm_mean = (
            float((np.mean(profile) - np.min(profile)) / profile_range)
            if profile_range > 1e-10 else 0.5
        )

        # Pick the pairing direction.  When one direction produces very
        # few pairs compared to the other its median score is unreliable
        # -- a handful of spurious pairs on a steep background slope can
        # produce deceptively high contrast scores (RC-6).
        if len(pos_pairs) >= 3 and len(neg_pairs) < 3:
            pairing_ft = "positive"
        elif len(neg_pairs) >= 3 and len(pos_pairs) < 3:
            pairing_ft = "negative"
        elif neg_med > pos_med:
            pairing_ft = "negative"
        elif pos_med > neg_med:
            pairing_ft = "positive"
        else:
            # Tie: use the global intensity distribution to disambiguate.
            pairing_ft = "negative" if norm_mean >= 0.5 else "positive"

        # Determine the reported film_type label.  Photometric inversion
        # (e.g. saved inverted-profile artifacts) can make a negative film
        # look like a positive one on the profile.  When norm_mean <= 0.38
        # the image is dark overall, indicating an inverted negative film
        # whose wires appear as bright peaks despite the physical film
        # being negative.
        if pairing_ft == "positive" and norm_mean <= 0.38:
            ft = "negative"
        else:
            ft = pairing_ft
    else:
        ft = film_type
        pairing_ft = ft

    # 3. Select the results for the chosen pairing direction
    if pairing_ft == "positive":
        dips, pairs = pos_dips, pos_pairs
        background = pos_bg
    else:
        dips, pairs = neg_dips, neg_pairs
        background = neg_bg

    # 4. Remove spurious overlapping pairs (pairs that share a wire
    #    position with a neighbour -- one of them is a noise artefact).
    pairs = _remove_overlapping_pairs(pairs, profile, film_type=pairing_ft)

    # 5. Try to recover the finest wire pair that may have been missed
    #    because its modulation is below the fine prominence threshold.
    pairs = _recover_tail_pair(
        profile, pairs, background, dip_half_w, film_type=pairing_ft,
    )

    # Recompute dips for the cleaned pair list
    dips = [
        _compute_dip(profile, w1, gap, w2, background, dip_half_w)
        for w1, gap, w2 in pairs
    ]

    return ComputeContrastResult(
        dips=dips,
        pairs=pairs,
        background=background,
        film_type=ft,
    )


def find_first_unresolved_group(
    dips: Sequence[float],
    wire_spacings: Optional[Sequence[float]] = None,
    dip_threshold: float = 20.0,
    min_dip_pct: float = 1.5,
) -> Optional[int]:
    """Find the first (coarsest) wire-pair group whose dip is below the
    resolution threshold.

    Applies monotonicity cleanup to the dip sequence, excludes very-low-dip
    neighbours from interpolation, and returns the 1-indexed group number
    of the first unresolved pair.

    Args:
        dips: Dip values (percent) per wire pair, from coarse (D1) to fine.
            Typically obtained from :func:`compute_contrast`.
        wire_spacings: Nominal wire-pair spacings (mm) matching the IQI
            model.  Defaults to the JBT 7902 D1-D13 sequence.  Must have
            at least as many entries as *dips*.
        dip_threshold: Dip percentage below which a pair is considered
            unresolved (default 20 %).
        min_dip_pct: Minimum dip (percent) for a group to participate in
            the interpolation neighbourhood (default 1.5 %).

    Returns:
        1-indexed group number, or *None* if all pairs are resolved.
    """
    if len(dips) == 0:
        return None

    if wire_spacings is None:
        spacings = list(_DEFAULT_WIRE_SPACINGS[:len(dips)])
    else:
        spacings = list(wire_spacings[:len(dips)])

    clean_dips, clean_spacings = _cleanup_dips_monotonic(dips, spacings)

    if len(clean_dips) == 0:
        return None

    result = _find_crossing_group(
        clean_dips, clean_spacings,
        threshold=dip_threshold,
        min_dip=min_dip_pct,
    )

    # Map cleaned index back to original group number since cleanup may have
    # removed entries, shifting the index-based numbering.
    if result is not None:
        crossing_val = clean_spacings[result - 1]
        return spacings.index(crossing_val) + 1

    return None


def bam_pair_marker_indices(
    pairs: list[tuple[int, int, int]] | list[list[int]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Return BAM wire and gap marker indices for profile plotting.

    Args:
        pairs: List of (wire_a_idx, gap_idx, wire_b_idx) triplets.

    Returns:
        (wire_indices, gap_indices) as sorted numpy arrays.
    """
    if not pairs:
        return np.array([], dtype=int), np.array([], dtype=int)
    wire_indices: list[int] = []
    gap_indices: list[int] = []
    for w1, gap, w2 in pairs:
        wire_indices.extend([int(w1), int(w2)])
        gap_indices.append(int(gap))
    return np.array(sorted(set(wire_indices)), dtype=int), np.array(gap_indices, dtype=int)


def pair_wire_markers(
    profile_values: np.ndarray,
    wire_markers: list[dict],
    gap_markers: list[dict],
    *,
    wire_type: str,
) -> list[dict]:
    """Pair adjacent wire markers and choose the strongest gap between them.

    Args:
        profile_values: 1-D profile grayscale values.
        wire_markers: List of ``{"idx": int, "type": "peak"|"valley"}`` dicts.
        gap_markers: List of ``{"idx": int, "type": "peak"|"valley"}`` dicts.
        wire_type: ``"peak"`` for positive film (bright wires), ``"valley"``
            for negative film (dark wires).

    Returns:
        List of wire-pair dicts with keys ``group``, ``wire_a_idx``,
        ``gap_idx``, ``wire_b_idx``, ``wire_a_gray``, ``gap_gray``,
        ``wire_b_gray``.
    """
    wire_markers = sorted(wire_markers, key=lambda m: m["idx"])
    gap_markers = sorted(gap_markers, key=lambda m: m["idx"])

    wire_pairs = []
    for i in range(len(wire_markers) - 1):
        w1 = wire_markers[i]
        w2 = wire_markers[i + 1]
        between = [g for g in gap_markers if w1["idx"] < g["idx"] < w2["idx"]]
        if not between:
            continue

        if wire_type == "peak":
            gap_idx = min(between, key=lambda g: profile_values[g["idx"]])["idx"]
        else:
            gap_idx = max(between, key=lambda g: profile_values[g["idx"]])["idx"]

        wire_pairs.append({
            "group": len(wire_pairs) + 1,
            "wire_a_idx": int(w1["idx"]),
            "gap_idx": int(gap_idx),
            "wire_b_idx": int(w2["idx"]),
            "wire_a_gray": float(profile_values[w1["idx"]]),
            "gap_gray": float(profile_values[gap_idx]),
            "wire_b_gray": float(profile_values[w2["idx"]]),
        })

    return wire_pairs


def build_groundtruth_payload(
    profile_values: np.ndarray,
    markers: list[dict],
    *,
    source_profile: str,
    band_width: int,
    film_type: str | None = None,
) -> dict:
    """Build neutral wire/gap ground-truth payload from manual markers.

    Positive film uses bright wires around a dark gap (peak-valley-peak).
    Negative film uses dark wires around a bright gap (valley-peak-valley).

    Args:
        profile_values: 1-D profile grayscale values.
        markers: List of ``{"type": "peak"|"valley", "idx": int}`` dicts.
        source_profile: Path to the source profile JSON (for provenance).
        band_width: Band width used when extracting the profile.
        film_type: ``"positive"``, ``"negative"``, or ``None`` (auto-detect).
            Auto selects the type that produces more pairs.

    Returns:
        Ground-truth payload dict.
    """
    from datetime import datetime, timezone

    profile_values = np.asarray(profile_values, dtype=np.float64)
    peaks = sorted([m for m in markers if m["type"] == "peak"], key=lambda m: m["idx"])
    valleys = sorted([m for m in markers if m["type"] == "valley"], key=lambda m: m["idx"])

    positive_pairs = pair_wire_markers(
        profile_values, peaks, valleys, wire_type="peak",
    )
    negative_pairs = pair_wire_markers(
        profile_values, valleys, peaks, wire_type="valley",
    )

    if film_type is None or film_type == "auto":
        if len(positive_pairs) >= len(negative_pairs) and positive_pairs:
            film_type = "positive"
            wire_pairs = positive_pairs
        elif negative_pairs:
            film_type = "negative"
            wire_pairs = negative_pairs
        else:
            film_type = "unknown"
            wire_pairs = []
    elif film_type == "positive":
        wire_pairs = positive_pairs
    elif film_type == "negative":
        wire_pairs = negative_pairs
    else:
        raise ValueError(f"Unsupported film_type: {film_type}")

    return {
        "source_profile": str(source_profile),
        "band_width": band_width,
        "film_type": film_type,
        "num_wire_pairs": len(wire_pairs),
        "wire_pairs": wire_pairs,
        "all_peaks": [{"idx": int(m["idx"]), "gray": float(profile_values[m["idx"]])}
                      for m in peaks],
        "all_valleys": [{"idx": int(m["idx"]), "gray": float(profile_values[m["idx"]])}
                        for m in valleys],
        "annotated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------


@dataclass
class DoubleWireResult:
    """Complete result of analyze_double_wire().

    pairs stores (wire_a, gap, wire_b) index triplets -- compatible with
    bam_pair_marker_indices and Annotator.load_bam_baseline.
    Call pairs_as_dicts() for JSON-friendly dict form.
    """
    strip_shape: tuple
    profile: np.ndarray
    peaks: list
    valleys: list
    pairs: list  # List[Tuple[int, int, int]]
    dips: list  # List[float]
    film_type: str
    background: np.ndarray
    first_unresolved_group: Optional[int]

    def pairs_as_dicts(self):
        """Convert pairs to JSON-friendly dict form with gray values."""
        return [
            {
                "group": i + 1,
                "wire_a_idx": int(w1),
                "gap_idx": int(gap),
                "wire_b_idx": int(w2),
                "wire_a_gray": float(self.profile[w1]),
                "gap_gray": float(self.profile[gap]),
                "wire_b_gray": float(self.profile[w2]),
                "dip_percent": float(dip),
            }
            for i, ((w1, gap, w2), dip) in enumerate(zip(self.pairs, self.dips))
        ]


def analyze_double_wire(strip, *, min_distance=5, prominence=0.03):
    """Analyze a double-wire IQI strip image.

    Column-averages 2D strip -> 1D profile, delegates to compute_contrast()
    and find_first_unresolved_group().

    Args:
        strip: 2D float64 array of shape (band_height, num_samples).
        min_distance: Min pixel distance between adjacent peaks.
        prominence: Relative peak prominence.

    Returns: DoubleWireResult
    """
    if strip.ndim != 2 or strip.shape[0] < 1 or strip.shape[1] < 3:
        return DoubleWireResult(
            strip_shape=(0, 0) if strip.ndim != 2 else strip.shape,
            profile=np.array([], dtype=np.float64),
            peaks=[], valleys=[], pairs=[], dips=[],
            film_type="positive",
            background=np.array([], dtype=np.float64),
            first_unresolved_group=None,
        )

    profile = strip.mean(axis=0).astype(np.float64)

    result = compute_contrast(
        profile, film_type="auto",
        min_distance=min_distance, prominence=prominence,
    )
    unresolved = find_first_unresolved_group(result.dips)

    peaks_idx, valleys_idx = detect_peaks_valleys(
        profile, min_distance=min_distance, prominence=prominence,
    )
    peaks = [{"idx": int(p), "gray": float(profile[p])} for p in peaks_idx]
    valleys = [{"idx": int(v), "gray": float(profile[v])} for v in valleys_idx]

    return DoubleWireResult(
        strip_shape=strip.shape,
        profile=profile,
        peaks=peaks, valleys=valleys,
        pairs=result.pairs, dips=result.dips,
        film_type=result.film_type,
        background=result.background,
        first_unresolved_group=unresolved,
    )
