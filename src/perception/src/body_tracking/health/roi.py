from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FaceRoi:
    patches: List[Tuple[int, int, int, int]]  # (x, y, w, h) full-frame pixels
    face_px: int


def _clip_patch(x, y, w, h, frame_w, frame_h):
    x = int(max(0, min(x, frame_w - 1)))
    y = int(max(0, min(y, frame_h - 1)))
    w = int(max(0, min(w, frame_w - x)))
    h = int(max(0, min(h, frame_h - y)))
    return (x, y, w, h)


def roi_from_pose(nose_xy, left_eye_xy, right_eye_xy, frame_w, frame_h) -> Optional[FaceRoi]:
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


def sample_mean_rgb(frame_bgr: np.ndarray, roi: FaceRoi) -> Tuple[float, float, float]:
    b_vals, g_vals, r_vals = [], [], []
    h_frame, w_frame = frame_bgr.shape[:2]
    for (x, y, w, h) in roi.patches:
        if w <= 0 or h <= 0 or x + w > w_frame or y + h > h_frame:
            continue
        crop = frame_bgr[y:y + h, x:x + w].reshape(-1, 3).astype(float)
        b_vals.append(crop[:, 0])
        g_vals.append(crop[:, 1])
        r_vals.append(crop[:, 2])
    if not r_vals:
        return (0.0, 0.0, 0.0)
    r = float(np.concatenate(r_vals).mean())
    g = float(np.concatenate(g_vals).mean())
    b = float(np.concatenate(b_vals).mean())
    return (r, g, b)


def roi_pixel_count(roi: FaceRoi) -> int:
    return int(sum(w * h for (_, _, w, h) in roi.patches))
