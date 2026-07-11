import numpy as np

from body_tracking.health.roi import roi_from_pose, sample_mean_rgb, roi_pixel_count, FaceRoi


def test_roi_from_pose_builds_patches_in_bounds():
    roi = roi_from_pose(
        nose_xy=(320, 250), left_eye_xy=(300, 235), right_eye_xy=(340, 235),
        frame_w=640, frame_h=480,
    )
    assert roi is not None
    assert len(roi.patches) >= 2
    for (x, y, w, h) in roi.patches:
        assert x >= 0 and y >= 0 and x + w <= 640 and y + h <= 480 and w > 0 and h > 0
    assert roi.face_px > 0


def test_roi_from_pose_none_when_eyes_coincide():
    roi = roi_from_pose((10, 10), (10, 10), (10, 10), 640, 480)
    assert roi is None


def test_sample_mean_rgb_reads_bgr_frame_as_rgb():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :, 2] = 200  # red channel (BGR index 2)
    frame[:, :, 1] = 100  # green
    frame[:, :, 0] = 50   # blue
    roi = FaceRoi(patches=[(100, 100, 20, 20)], face_px=40)
    r, g, b = sample_mean_rgb(frame, roi)
    assert (round(r), round(g), round(b)) == (200, 100, 50)
    assert roi_pixel_count(roi) == 400
