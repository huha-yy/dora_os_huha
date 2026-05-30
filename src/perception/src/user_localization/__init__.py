"""
User Localization Module

Provides functionality for detecting and localizing users in 3D space
and projecting their positions onto 2D maps.
"""

from .depth_to_3d import DepthTo3DConverter

# Re-export dataclasses from body_tracking.state for convenience
from body_tracking.state import BoundingBox, CameraIntrinsics, Point3D

__all__ = [
    'DepthTo3DConverter',
    'BoundingBox',
    'CameraIntrinsics', 
    'Point3D'
]

