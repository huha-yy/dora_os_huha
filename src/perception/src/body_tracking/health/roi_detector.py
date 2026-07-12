import logging
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from .roi import FaceRoi, _clip_patch

logger = logging.getLogger(__name__)


class FaceRoiExtractor:
    def __init__(self, model_asset_path: Optional[str] = None, min_confidence: float = 0.6) -> None:
        self._min_conf = min_confidence
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=min_confidence
        )

    def update(self, frame_bgr: np.ndarray) -> Optional[FaceRoi]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.detections:
            return None
        if len(result.detections) > 1:
            return None
        det = result.detections[0]
        box = det.location_data.relative_bounding_box
        fx, fy = int(box.xmin * w), int(box.ymin * h)
        fw, fh = int(box.width * w), int(box.height * h)
        if fw <= 0 or fh <= 0:
            return None
        patch = max(6, int(fw * 0.25))
        forehead = _clip_patch(fx + fw // 2 - patch // 2, fy + int(fh * 0.08), patch, patch, w, h)
        left_cheek = _clip_patch(fx + int(fw * 0.12), fy + int(fh * 0.55), patch, patch, w, h)
        right_cheek = _clip_patch(fx + fw - int(fw * 0.12) - patch, fy + int(fh * 0.55), patch, patch, w, h)
        patches = [p for p in (forehead, left_cheek, right_cheek) if p[2] > 0 and p[3] > 0]
        if len(patches) < 2:
            return None
        return FaceRoi(patches=patches, face_px=fw)
