from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FaceRoi:
    patches: List[Tuple[int, int, int, int]]  # (x, y, w, h) full-frame pixels
    face_px: int


def _clip_patch(
    x: float, y: float, w: float, h: float, frame_w: int, frame_h: int
) -> Tuple[int, int, int, int]:
    x = int(max(0, min(x, frame_w - 1)))
    y = int(max(0, min(y, frame_h - 1)))
    w = int(max(0, min(w, frame_w - x)))
    h = int(max(0, min(h, frame_h - y)))
    return (x, y, w, h)


def roi_from_pose(
    nose_xy: Tuple[float, float],
    left_eye_xy: Tuple[float, float],
    right_eye_xy: Tuple[float, float],
    frame_w: int,
    frame_h: int,
) -> Optional[FaceRoi]:
    (nx, ny) = nose_xy
    (lx, ly) = left_eye_xy
    (rx, ry) = right_eye_xy
    eye_dx = abs(rx - lx)
    eye_dy = abs(ry - ly)
    eye_dist = (eye_dx ** 2 + eye_dy ** 2) ** 0.5
    if eye_dist < 5.0:
        return None
    face_px = int(eye_dist * 2.2)  # rough face width from eye spacing
    patch = max(6, int(eye_dist * 0.5))
    eye_cx = (lx + rx) / 2.0
    eye_cy = (ly + ry) / 2.0
    forehead = _clip_patch(eye_cx - patch / 2, eye_cy - eye_dist * 1.1, patch, patch, frame_w, frame_h)
    left_cheek = _clip_patch(lx - patch, ny - patch / 2, patch, patch, frame_w, frame_h)
    right_cheek = _clip_patch(rx, ny - patch / 2, patch, patch, frame_w, frame_h)
    patches = [p for p in (forehead, left_cheek, right_cheek) if p[2] > 0 and p[3] > 0]
    if len(patches) < 2:
        return None
    return FaceRoi(patches=patches, face_px=face_px)


MIN_POSE_VISIBILITY = 0.5


def roi_from_pose_landmarks(
    nose: Tuple[float, float, float],
    left_eye: Tuple[float, float, float],
    right_eye: Tuple[float, float, float],
    person_bbox: Tuple[int, int, int, int],
    frame_w: int,
    frame_h: int,
    min_visibility: float = MIN_POSE_VISIBILITY,
) -> Optional[FaceRoi]:
    """Face ROI from POSE landmarks (the FPS-budget fallback for the face detector).

    Each landmark is ``(x, y, visibility)``. CRITICAL: x, y are normalized to the
    PERSON CROP, not the full frame -- MediaPipe Pose runs on ``frame[y1:y2, x1:x2]``.
    So they must be mapped back through ``person_bbox`` = ``(x1, y1, width, height)`` in
    full-frame pixels:  ``px = x1 + x*width``. Multiplying by the frame size instead
    would place the ROI wherever the person happens to sit in normalized frame space --
    i.e. on the background -- and feed the estimator wrong-skin pixels silently. Fall
    detection never hit this because it uses crop-relative angles, not absolute position.

    Reuses ``roi_from_pose``'s geometry once the points are in full-frame pixels; the
    point of the whole path is that these landmarks are ALREADY computed for fall
    detection, so no second (expensive) MediaPipe face graph runs.

    Fails CLOSED: if any of the three landmarks is below ``min_visibility``, return None.
    A face ROI placed off an unsure landmark would sample the wrong pixels.
    """
    if min(nose[2], left_eye[2], right_eye[2]) < min_visibility:
        return None
    x1, y1, bw, bh = person_bbox
    if bw <= 0 or bh <= 0:
        return None

    def to_frame_px(lm: Tuple[float, float, float]) -> Tuple[float, float]:
        return (x1 + lm[0] * bw, y1 + lm[1] * bh)

    return roi_from_pose(
        to_frame_px(nose),
        to_frame_px(left_eye),
        to_frame_px(right_eye),
        frame_w,
        frame_h,
    )


def _iter_valid_patches(
    patches: List[Tuple[int, int, int, int]], frame_w: int, frame_h: int
) -> Iterator[Tuple[int, int, int, int]]:
    """Yield only patches that are fully in-bounds and non-degenerate.

    This is the single source of truth for patch validity, shared by
    `sample_mean_rgb` and `roi_pixel_count`, so the reported pixel count and
    the pixels actually sampled can never disagree. A patch is rejected (not
    clipped) if it has a negative origin, non-positive size, or extends past
    the frame edges -- negative indices must never reach a numpy slice here,
    since `frame[y:y+h, x:x+w]` silently wraps around for negative `x`/`y`
    instead of raising, which would otherwise sample pixels from the opposite
    edge of the frame.
    """
    for (x, y, w, h) in patches:
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            continue
        if x + w > frame_w or y + h > frame_h:
            continue
        yield (x, y, w, h)


def sample_mean_rgb(frame_bgr: np.ndarray, roi: FaceRoi) -> Optional[Tuple[float, float, float]]:
    b_vals, g_vals, r_vals = [], [], []
    h_frame, w_frame = frame_bgr.shape[:2]
    for (x, y, w, h) in _iter_valid_patches(roi.patches, w_frame, h_frame):
        crop = frame_bgr[y:y + h, x:x + w].reshape(-1, 3).astype(float)
        b_vals.append(crop[:, 0])
        g_vals.append(crop[:, 1])
        r_vals.append(crop[:, 2])
    if not r_vals:
        return None
    r = float(np.concatenate(r_vals).mean())
    g = float(np.concatenate(g_vals).mean())
    b = float(np.concatenate(b_vals).mean())
    return (r, g, b)


def roi_centroid(roi: FaceRoi) -> Optional[Tuple[float, float]]:
    """Area-weighted centre of the ROI patches, in full-frame pixels.

    This is the position the motion metric tracks across the window. Weighting by
    patch area keeps the centre stable when one patch is clipped at a frame edge.
    """
    valid = [(x, y, w, h) for (x, y, w, h) in roi.patches if w > 0 and h > 0]
    total = sum(w * h for (_, _, w, h) in valid)
    if total <= 0:
        return None
    cx = sum((x + w / 2.0) * w * h for (x, _, w, h) in valid) / total
    cy = sum((y + h / 2.0) * w * h for (_, y, w, h) in valid) / total
    return (cx, cy)


def roi_pixel_count(frame_bgr: np.ndarray, roi: FaceRoi) -> int:
    h_frame, w_frame = frame_bgr.shape[:2]
    return int(sum(w * h for (_, _, w, h) in _iter_valid_patches(roi.patches, w_frame, h_frame)))
