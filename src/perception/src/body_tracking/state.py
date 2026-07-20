# perception/src/body_tracking/state.py
from enum import Enum
from dataclasses import dataclass
import math
import numpy as np
import logging
from mediapipe.tasks.python.components.containers import NormalizedLandmark
from .landmarks import POSE_LANDMARKS

logger = logging.getLogger(__name__)

# Configure logging format to include module name and line number at the beginning
if not logging.root.handlers:  # Only configure if logging hasn't been configured yet
    logging.basicConfig(
        level=logging.INFO, format="%(module)s:%(lineno)d - %(levelname)s - %(message)s"
    )

HORIZONTAL_ASPECT_RATIO_MAX = 1.0
UPRIGHT_ASPECT_RATIO_MIN = 1.2


class RawPose(Enum):
    UPRIGHT = "upright"
    TRANSITIONING = "transitioning"
    HORIZONTAL = "horizontal"
    UNKNOWN = "unknown"
    UNDETECTED = "undetected"


class BodyPose(Enum):
    STANDING = "standing"
    FALLING = "falling"
    SITTING = "sitting"
    LYING = "lying"
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    OTHER = "other"
    UNKNOWN = "unknown"
    UNDETECTED = "undetected"


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters for 3D projection"""
    fx: float  # Focal length in x (pixels)
    fy: float  # Focal length in y (pixels)
    cx: float  # Principal point x (pixels)
    cy: float  # Principal point y (pixels)
    width: int  # Image width
    height: int  # Image height


@dataclass
class Point3D:
    """3D point in camera frame (meters)"""
    x: float  # Right (positive = right)
    y: float  # Down (positive = down)
    z: float  # Forward (positive = forward/away from camera)
    
    @property
    def distance(self) -> float:
        """Euclidean distance from camera origin"""
        return np.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def to_tuple(self) -> tuple[float, float, float]:
        """Convert to tuple (x, y, z)"""
        return (self.x, self.y, self.z)


@dataclass
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> NormalizedLandmark:
        return NormalizedLandmark(
            x=(self.x1 + self.x2) / 2,
            y=(self.y1 + self.y2) / 2,
        )
    
    @property
    def center_x(self) -> int:
        """Center X coordinate (for depth sampling)"""
        return int((self.x1 + self.x2) / 2)
    
    @property
    def center_y(self) -> int:
        """Center Y coordinate (for depth sampling)"""
        return int((self.y1 + self.y2) / 2)

    @property
    def area(self) -> int:
        return self.width * self.height
    
    def is_valid(self, img_width: int, img_height: int) -> bool:
        """Check if bounding box is within image bounds"""
        return (0 <= self.x1 < self.x2 <= img_width and 
                0 <= self.y1 < self.y2 <= img_height)

    @property
    def aspect_ratio(self) -> float:
        return self.height / max(self.width, 1e-6)

    @property
    def is_square(self) -> bool:
        return self.aspect_ratio > 0.9 and self.aspect_ratio < 1.1

    def get_raw_pose(self) -> tuple[float, RawPose]:
        if self.aspect_ratio <= HORIZONTAL_ASPECT_RATIO_MAX:
            return self.aspect_ratio, RawPose.HORIZONTAL
        elif self.aspect_ratio >= UPRIGHT_ASPECT_RATIO_MIN:
            return self.aspect_ratio, RawPose.UPRIGHT
        else:
            return self.aspect_ratio, RawPose.TRANSITIONING

    @property
    def json(self) -> dict:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }

    @classmethod
    def from_json(cls, j: dict) -> "BoundingBox":
        return cls(x1=j["x1"], y1=j["y1"], x2=j["x2"], y2=j["y2"])

@dataclass
class HumanLandmarks:
    landmarks: list[NormalizedLandmark]

    def __getitem__(self, landmark_name: str) -> NormalizedLandmark:
        return self.landmarks[POSE_LANDMARKS[landmark_name]]

    def get_shoulder_center(self) -> NormalizedLandmark:
        return NormalizedLandmark(
            x=(self["left_shoulder"].x + self["right_shoulder"].x) / 2,
            y=(self["left_shoulder"].y + self["right_shoulder"].y) / 2,
        )

    def get_hip_center(self) -> NormalizedLandmark:
        return NormalizedLandmark(
            x=(self["left_hip"].x + self["right_hip"].x) / 2,
            y=(self["left_hip"].y + self["right_hip"].y) / 2,
        )

    def get_torso_angle(self) -> tuple[float, RawPose]:
        shoulder_center = self.get_shoulder_center()
        hip_center = self.get_hip_center()
        dy = shoulder_center.y - hip_center.y
        dx = shoulder_center.x - hip_center.x
        angle = math.degrees(math.atan2(dy, dx))
        torso_angle = abs(90 - abs(angle))
        if torso_angle < 20:
            return torso_angle, RawPose.UPRIGHT
        elif torso_angle > 60:
            return torso_angle, RawPose.HORIZONTAL
        else:
            return torso_angle, RawPose.TRANSITIONING
    
    @property
    def json(self) -> dict:
        return {
            "landmarks": [
                {
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": getattr(landmark, "z", 0.0),
                    "visibility": getattr(landmark, "visibility", 0.0),
                    "presence": getattr(landmark, "presence", 0.0),
                }
                for landmark in self.landmarks
            ],
        }
    
    @classmethod
    def from_json(cls, j: dict) -> "HumanLandmarks":
        landmarks = []
        for landmark_dict in j["landmarks"]:
            landmarks.append(
                NormalizedLandmark(
                    x=landmark_dict["x"],
                    y=landmark_dict["y"],
                    z=landmark_dict.get("z", 0.0),
                    visibility=landmark_dict.get("visibility", 0.0),
                    presence=landmark_dict.get("presence", 0.0),
                )
            )
        return cls(landmarks=landmarks)


@dataclass
class PoseDetectionResult:
    raw_pose: RawPose = RawPose.UNDETECTED
    pose: BodyPose = BodyPose.UNDETECTED
    torso_angle: float = -1.0
    mp_pose: RawPose = RawPose.UNDETECTED
    bbox_aspect_ratio: float = -1.0
    bbox_pose: RawPose = RawPose.UNDETECTED

    @classmethod
    def from_landmarks_and_bounding_box(
        cls, landmarks: HumanLandmarks, bounding_box: BoundingBox
    ) -> "PoseDetectionResult":
        torso_angle, mp_pose = landmarks.get_torso_angle()
        bbox_aspect_ratio, bbox_pose = bounding_box.get_raw_pose()
        result = cls(
            torso_angle=torso_angle,
            mp_pose=mp_pose,
            bbox_aspect_ratio=bbox_aspect_ratio,
            bbox_pose=bbox_pose,
        )
        result.calculate_raw_pose()
        return result

    def validate(self) -> bool:
        if self.torso_angle < 0 or self.torso_angle > 90:
            logger.warning(f"Torso angle: {self.torso_angle} is not valid")
            return False
        if self.bbox_aspect_ratio < 0:
            logger.warning(f"Bbox aspect ratio: {self.bbox_aspect_ratio} is not valid")
            return False
        if self.bbox_pose is RawPose.UNDETECTED:
            logger.warning(f"Bbox pose: {self.bbox_pose} is not valid")
            return False
        if self.mp_pose is RawPose.UNDETECTED:
            logger.warning(f"MP pose: {self.mp_pose} is not valid")
            return False
        return True

    def calculate_raw_pose(self) -> None:
        if not self.validate():
            logger.error("PoseDetectionResult is not valid, cannot calculate raw pose.")
            return
        if self.bbox_pose == RawPose.UPRIGHT and self.mp_pose == RawPose.UPRIGHT:
            self.raw_pose = RawPose.UPRIGHT
        elif (
            self.bbox_pose == RawPose.HORIZONTAL and self.mp_pose == RawPose.HORIZONTAL
        ):
            self.raw_pose = RawPose.HORIZONTAL
        elif (
            self.bbox_pose == RawPose.TRANSITIONING
            and self.mp_pose == RawPose.TRANSITIONING
        ):
            self.raw_pose = RawPose.TRANSITIONING
        else:
            self.raw_pose = RawPose.UNKNOWN
    
    @property
    def json(self) -> dict:
        return {
            "raw_pose": self.raw_pose.value,
            "pose": self.pose.value,
            "torso_angle": self.torso_angle,
            "mp_pose": self.mp_pose.value,
            "bbox_aspect_ratio": self.bbox_aspect_ratio,
            "bbox_pose": self.bbox_pose.value,
        }
    
    @classmethod
    def from_json(cls, j: dict) -> "PoseDetectionResult":
        return cls(
            raw_pose=RawPose(j["raw_pose"]),
            pose=BodyPose(j["pose"]),
            torso_angle=j["torso_angle"],
            mp_pose=RawPose(j["mp_pose"]),
            bbox_aspect_ratio=j["bbox_aspect_ratio"],
            bbox_pose=RawPose(j["bbox_pose"]),
        )


@dataclass
class HumanPose:
    bounding_box: BoundingBox
    landmarks: HumanLandmarks
    pose_detection_result: PoseDetectionResult
    person_id: int = 0  # id of the person in the frame

    @property
    def bbox_center(self) -> NormalizedLandmark:
        return self.bounding_box.center

    @property
    def raw_pose(self) -> RawPose:
        return self.pose_detection_result.raw_pose

    @property
    def pose(self) -> BodyPose:
        return self.pose_detection_result.pose

    @property
    def json(self) -> dict:
        return {
            "bounding_box": self.bounding_box.json,
            "landmarks":self.landmarks.json,
            "pose_detection_result": self.pose_detection_result.json,
            "person_id": self.person_id,
        }


    @classmethod
    def from_json(cls, j: dict) -> "HumanPose":
        return cls(
            bounding_box=BoundingBox.from_json(j["bounding_box"]),
            landmarks=HumanLandmarks.from_json(j["landmarks"]),
            pose_detection_result=PoseDetectionResult.from_json(j["pose_detection_result"]),
            person_id=j["person_id"],
        )

@dataclass
class FrameTrackingResult:
    human_poses: list[HumanPose]
    timestamp: float = 0.0
    debug_frame: np.ndarray | None = None
    vertical_speed: float = 0.0

    @classmethod
    def create_dummy(cls) -> "FrameTrackingResult":
        return cls(human_poses=[], timestamp=0.0, debug_frame=None)

    @property
    def has_human_poses(self) -> bool:
        return len(self.human_poses) > 0

    def get_person_by_id(self, person_id: int) -> HumanPose | None:
        if not self.has_human_poses:
            return None
        # TODO: implement
        return self.human_poses[0]
    
    @property
    def json(self) -> dict:
        return {
            "human_poses": [pose.json for pose in self.human_poses],
            "timestamp": self.timestamp,
            "debug_frame": self.debug_frame,
            "vertical_speed": self.vertical_speed,
        }

    @classmethod
    def from_json(cls, j: dict) -> "FrameTrackingResult":
        return cls(
            human_poses=[HumanPose.from_json(pose) for pose in j["human_poses"]],
            timestamp=j["timestamp"],
            debug_frame=j["debug_frame"],
            vertical_speed=j["vertical_speed"],
        )

@dataclass
class HumanStatus:
    tracking_result: FrameTrackingResult
    vertical_speed: float = 0.0
    timestamp: float = 0.0
    is_falling_candidate: bool = False
    is_fallen: bool = False
    last_upright_timestamp: float = 0.0
    first_laying_down_timestamp: float = 0.0
    is_dummy: bool = False

    @classmethod
    def create_dummy(cls) -> "HumanStatus":
        return cls(
            tracking_result=FrameTrackingResult.create_dummy(),
            vertical_speed=0.0,
            timestamp=0.0,
            is_dummy=True,
        )

    def get_raw_pose(self, person_id: int = 0) -> RawPose:
        person = self.tracking_result.get_person_by_id(person_id)
        if person is None:
            return RawPose.UNKNOWN
        return person.raw_pose
    
    @property
    def json(self) -> dict:
        return {
            "tracking_result": self.tracking_result.json,
            "vertical_speed": self.vertical_speed,
            "timestamp": self.timestamp,
            "is_falling_candidate": self.is_falling_candidate,
            "is_fallen": self.is_fallen,
            "last_upright_timestamp": self.last_upright_timestamp,
            "first_laying_down_timestamp": self.first_laying_down_timestamp,
            "is_dummy": self.is_dummy,
        }

    @classmethod
    def from_json(cls, j: dict) -> "HumanStatus":
        return cls(
            tracking_result=FrameTrackingResult.from_json(j["tracking_result"]),
            vertical_speed=j["vertical_speed"],
            timestamp=j["timestamp"],
            is_falling_candidate=j["is_falling_candidate"],
            is_fallen=j["is_fallen"],
            last_upright_timestamp=j["last_upright_timestamp"],
            first_laying_down_timestamp=j["first_laying_down_timestamp"],
            is_dummy=j["is_dummy"],
        )