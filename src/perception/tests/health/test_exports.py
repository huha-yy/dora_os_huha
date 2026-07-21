import numpy as np


def test_public_exports_are_importable():
    from body_tracking.health import (
        RPPGEstimator, HealthConfig, ScanController, build_metrics, describe_complexion,
    )
    assert RPPGEstimator and HealthConfig and ScanController and build_metrics and describe_complexion


def test_face_extractor_returns_none_on_black_frame():
    from body_tracking.health.roi_detector import FaceRoiExtractor
    ext = FaceRoiExtractor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert ext.update(frame) is None
