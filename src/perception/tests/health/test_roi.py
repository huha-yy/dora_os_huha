import numpy as np
import pytest

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
    assert roi_pixel_count(frame, roi) == 400


def test_roi_from_pose_clips_patches_near_top_left_corner():
    # Face close to the top-left corner forces both the forehead (y) and the
    # left cheek (x) patches to run off-frame, so _clip_patch must actually
    # clip rather than pass coordinates through untouched.
    roi = roi_from_pose(
        nose_xy=(15, 15), left_eye_xy=(5, 10), right_eye_xy=(25, 10),
        frame_w=640, frame_h=480,
    )
    assert roi is not None
    for (x, y, w, h) in roi.patches:
        assert x >= 0 and y >= 0 and x + w <= 640 and y + h <= 480 and w > 0 and h > 0
    # At least one patch must have been pulled back to the frame edge --
    # proves clipping engaged, not merely that the geometry happened to fit.
    assert any(x == 0 for (x, _, _, _) in roi.patches) or any(y == 0 for (_, y, _, _) in roi.patches)


def test_roi_from_pose_clips_patches_near_bottom_right_corner():
    # Mirror case at the opposite edge: patches must be pulled back to
    # frame_w / frame_h, not left protruding past them.
    roi = roi_from_pose(
        nose_xy=(625, 465), left_eye_xy=(615, 460), right_eye_xy=(635, 460),
        frame_w=640, frame_h=480,
    )
    assert roi is not None
    for (x, y, w, h) in roi.patches:
        assert x >= 0 and y >= 0 and x + w <= 640 and y + h <= 480 and w > 0 and h > 0
    assert any(x + w == 640 for (x, _, w, _) in roi.patches) or any(
        y + h == 480 for (_, y, _, h) in roi.patches
    )


def test_sample_mean_rgb_rejects_negative_origin_without_wraparound():
    # Regression test for the critical wraparound bug: frame[y:y+h, -5:-2]
    # used to resolve to columns 635:638 (numpy negative-index wraparound)
    # and silently return real pixels from the opposite edge of the frame
    # instead of being rejected. Mark the wrap-target region distinctly so a
    # wraparound sample would be caught immediately.
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:103, 635:640, 2] = 9  # would-be wraparound target, red channel

    roi = FaceRoi(patches=[(-5, 100, 3, 3)], face_px=40)

    assert sample_mean_rgb(frame, roi) is None
    assert roi_pixel_count(frame, roi) == 0


def test_sample_mean_rgb_rejects_patch_past_bottom_right_edge():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    roi = FaceRoi(patches=[(0, -4, 5, 5), (638, 0, 5, 5)], face_px=40)

    assert sample_mean_rgb(frame, roi) is None
    assert roi_pixel_count(frame, roi) == 0


def test_sample_mean_rgb_and_roi_pixel_count_agree_on_mixed_patches():
    # One valid patch and one invalid (negative-origin) patch. The invalid
    # patch must not inflate roi_pixel_count relative to what was actually
    # sampled -- otherwise the min_roi_px quality gate could pass on
    # accounting for pixels that were never read.
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:110, 100:110, 2] = 200
    frame[100:110, 100:110, 1] = 100
    frame[100:110, 100:110, 0] = 50

    valid_patch = (100, 100, 10, 10)
    invalid_patch = (-5, 100, 3, 3)
    roi = FaceRoi(patches=[valid_patch, invalid_patch], face_px=40)

    result = sample_mean_rgb(frame, roi)
    assert result is not None
    r, g, b = result
    assert (round(r), round(g), round(b)) == (200, 100, 50)
    # Count must reflect only the valid patch (10*10), not both.
    assert roi_pixel_count(frame, roi) == 100


def test_sample_mean_rgb_returns_none_when_no_valid_patches():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    roi = FaceRoi(patches=[(-1, -1, 5, 5)], face_px=40)
    assert sample_mean_rgb(frame, roi) is None


def test_sample_mean_rgb_distinguishes_dark_roi_from_failure():
    # A genuinely dark (all-zero) but valid ROI must return real zeros, not
    # the None failure sentinel -- the two cases must stay distinguishable.
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    roi = FaceRoi(patches=[(100, 100, 10, 10)], face_px=40)
    result = sample_mean_rgb(frame, roi)
    assert result == (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# roi_from_pose_landmarks -- the pose-only ROI fallback (Task 16b)
#
# The on-device FPS test showed the per-frame MediaPipe FACE detector drops
# fall-detection FPS ~19-34% (over the 15% budget). This path derives the face ROI
# from the pose landmarks the node ALREADY computes (nose/eyes), so no second detector
# runs. Inputs are normalized [0,1] with a visibility score; fail closed on low
# visibility (a guessed ROI off an unsure landmark would sample the wrong pixels).
# --------------------------------------------------------------------------

from body_tracking.health.roi import roi_from_pose_landmarks, MIN_POSE_VISIBILITY

W, H = 640, 480


def _lm(x, y, vis=0.99):
    return (x, y, vis)


# A person occupying the right-hand side of the frame. Landmarks are normalized to THIS
# crop, so crop-x 0.5 maps to full-frame pixel 400 + 0.5*160 = 480, NOT 0.5*640 = 320.
BBOX = (400, 100, 160, 240)   # x1, y1, width, height (full-frame pixels)


def test_visible_face_landmarks_give_an_roi():
    roi = roi_from_pose_landmarks(
        nose=_lm(0.50, 0.55), left_eye=_lm(0.40, 0.35), right_eye=_lm(0.60, 0.35),
        person_bbox=BBOX, frame_w=W, frame_h=H)
    assert roi is not None
    assert len(roi.patches) >= 2
    assert roi.face_px > 0


def test_landmarks_are_mapped_through_the_bbox_not_the_frame():
    """THE bug Codex caught. Pose landmarks are crop-normalized, so they must be mapped
    via the person bbox, not the frame. With the person on the right side of the frame,
    every ROI patch must fall inside the bbox's x-range -- a frame-normalized mapping
    would place them near the frame centre (x~320), on the background."""
    roi = roi_from_pose_landmarks(
        nose=_lm(0.50, 0.55), left_eye=_lm(0.40, 0.35), right_eye=_lm(0.60, 0.35),
        person_bbox=BBOX, frame_w=W, frame_h=H)
    assert roi is not None
    x1, _, bw, _ = BBOX
    for (px, _py, pw, _ph) in roi.patches:
        centre = px + pw / 2
        assert x1 <= centre <= x1 + bw, (
            f"patch centre {centre} is outside the person bbox [{x1}, {x1+bw}] -- "
            f"landmarks were mapped to the frame instead of the crop"
        )


def test_eye_spacing_scales_with_the_bbox():
    # eyes 0.20 of the crop apart, bbox width 160 -> 32px -> face_px = int(32*2.2) = 70
    roi = roi_from_pose_landmarks(
        nose=_lm(0.50, 0.55), left_eye=_lm(0.40, 0.35), right_eye=_lm(0.60, 0.35),
        person_bbox=BBOX, frame_w=W, frame_h=H)
    assert roi is not None
    assert roi.face_px == int((0.20 * 160) * 2.2)


@pytest.mark.parametrize("bad", ["nose", "left_eye", "right_eye"])
def test_low_visibility_on_any_landmark_withholds(bad):
    pts = {"nose": _lm(0.50, 0.55), "left_eye": _lm(0.40, 0.35), "right_eye": _lm(0.60, 0.35)}
    pts[bad] = (pts[bad][0], pts[bad][1], MIN_POSE_VISIBILITY - 0.01)
    assert roi_from_pose_landmarks(person_bbox=BBOX, frame_w=W, frame_h=H, **pts) is None


def test_degenerate_bbox_withholds():
    assert roi_from_pose_landmarks(
        nose=_lm(0.5, 0.55), left_eye=_lm(0.4, 0.35), right_eye=_lm(0.6, 0.35),
        person_bbox=(400, 100, 0, 240), frame_w=W, frame_h=H) is None


def test_eyes_too_close_withholds():
    roi = roi_from_pose_landmarks(
        nose=_lm(0.500, 0.55), left_eye=_lm(0.499, 0.35), right_eye=_lm(0.501, 0.35),
        person_bbox=BBOX, frame_w=W, frame_h=H)
    assert roi is None


def test_at_frame_boundary_stays_in_bounds():
    roi = roi_from_pose_landmarks(
        nose=_lm(0.5, 0.5), left_eye=_lm(0.2, 0.2), right_eye=_lm(0.8, 0.2),
        person_bbox=(0, 0, 60, 80), frame_w=W, frame_h=H)
    if roi is not None:
        for (x, y, pw, ph) in roi.patches:
            assert x >= 0 and y >= 0 and x + pw <= W and y + ph <= H
