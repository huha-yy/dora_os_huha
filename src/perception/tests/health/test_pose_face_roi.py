"""pose_face_roi against the REAL state.py types.

This is the guard for the node<->pose glue. Two review-caught bugs live exactly here:
crop-normalized landmarks (mapped via the frame instead of the bbox) and
`BoundingBox.width`/`height` being @property (called as methods). Both are only caught
by exercising the real types, which this does.
"""

import pytest

from body_tracking.pose_face_roi import pose_face_roi
from body_tracking.state import BoundingBox, HumanLandmarks


class _LM:
    """A pose landmark: crop-normalized x/y + visibility (duck-types NormalizedLandmark)."""
    def __init__(self, x, y, visibility=0.99):
        self.x, self.y, self.visibility = x, y, visibility


class _Person:
    def __init__(self, bbox, landmarks):
        self.bounding_box = bbox
        self.landmarks = landmarks


class _Tracking:
    def __init__(self, *people):
        self.human_poses = list(people)


def _landmarks(nose, left_eye, right_eye):
    # POSE_LANDMARKS: nose=0, left_eye=2, right_eye=5 -> a 6+ element list
    lst = [_LM(0.5, 0.5) for _ in range(7)]
    lst[0], lst[2], lst[5] = nose, left_eye, right_eye
    return HumanLandmarks(landmarks=lst)


# Person on the RIGHT of the frame. Real BoundingBox -> .width is a @property (=160).
BBOX = BoundingBox(x1=400, y1=100, x2=560, y2=340)


def _person(bbox=BBOX):
    return _Person(bbox, _landmarks(_LM(0.5, 0.55), _LM(0.4, 0.35), _LM(0.6, 0.35)))


def test_extracts_roi_placed_inside_the_person_bbox():
    """Guards BOTH mapping bugs at once: uses the real BoundingBox (so .width being a
    property is exercised) and asserts the ROI lands inside the person box on the right
    of the frame -- a frame-normalized mapping would place it near x~320 on the
    background."""
    roi = pose_face_roi(_Tracking(_person()), frame_w=640, frame_h=480)

    assert roi is not None
    for (px, _py, pw, _ph) in roi.patches:
        centre = px + pw / 2
        assert 400 <= centre <= 560, f"patch at {centre} is outside the person bbox"


def test_multiple_people_withholds():
    """Ambiguous whose pulse -> withhold, matching the face-detector path. Otherwise a
    heart rate would be attributed to an arbitrary person in a crowd."""
    assert pose_face_roi(_Tracking(_person(), _person()), 640, 480) is None


def test_no_people_withholds():
    assert pose_face_roi(_Tracking(), 640, 480) is None
    assert pose_face_roi(None, 640, 480) is None


def test_occluded_landmark_withholds():
    p = _Person(BBOX, _landmarks(_LM(0.5, 0.55, 0.1), _LM(0.4, 0.35), _LM(0.6, 0.35)))
    assert pose_face_roi(_Tracking(p), 640, 480) is None


def test_malformed_person_withholds_not_crashes():
    class _Bad:
        pass
    assert pose_face_roi(_Tracking(_Bad()), 640, 480) is None
