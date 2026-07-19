"""Adapter: HumanPose (pose landmarks) -> face ROI for the rPPG fallback.

Kept ROS-free and separate from the node so it can be unit-tested against the real
`state.py` types. Two bugs were caught here in review -- pose landmarks being
crop-normalized (not frame-normalized) and `BoundingBox.width`/`height` being
properties rather than methods -- both of which a test against the real types catches.
"""

from typing import Optional

from .health.roi import FaceRoi, roi_from_pose_landmarks


def pose_face_roi(tracking_result, frame_w: int, frame_h: int) -> Optional[FaceRoi]:
    """Face ROI from the tracking result's pose landmarks, or None to withhold.

    Withholds unless EXACTLY ONE person is present. Zero -> nobody to read. More than one
    -> ambiguous whose pulse it is; publishing person-0's reading would silently
    attribute a heart rate to an arbitrary person. This matches the MediaPipe face path,
    which returns None on multiple detections. `single_target` in the gate is derived
    from whether an ROI came back, so enforcing it here keeps that gate honest.

    The single person is a HumanPose: `.landmarks` (indexable by
    "nose"/"left_eye"/"right_eye") and `.bounding_box` (BoundingBox with `.x1`, `.y1`,
    `.width`, `.height`). Landmarks are normalized to the person crop;
    roi_from_pose_landmarks maps them back through the bbox. Any missing/occluded
    landmark or degenerate bbox -> None.
    """
    if tracking_result is None:
        return None
    people = getattr(tracking_result, "human_poses", None)
    if not people or len(people) != 1:
        return None
    person = people[0]
    try:
        lm = person.landmarks
        nose, left_eye, right_eye = lm["nose"], lm["left_eye"], lm["right_eye"]
        bbox = person.bounding_box
        person_bbox = (bbox.x1, bbox.y1, bbox.width, bbox.height)  # width/height are @property
    except (KeyError, IndexError, AttributeError, TypeError):
        return None
    return roi_from_pose_landmarks(
        (nose.x, nose.y, getattr(nose, "visibility", 1.0)),
        (left_eye.x, left_eye.y, getattr(left_eye, "visibility", 1.0)),
        (right_eye.x, right_eye.y, getattr(right_eye, "visibility", 1.0)),
        person_bbox, frame_w, frame_h,
    )
