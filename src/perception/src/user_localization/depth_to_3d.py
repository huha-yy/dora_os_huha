"""
Depth to 3D Converter

Converts 2D bounding boxes + depth image to 3D positions in camera frame.
Uses pinhole camera model with camera intrinsics.
"""

import numpy as np
from typing import Optional, Tuple

# Import dataclasses from body_tracking.state
from body_tracking.state import BoundingBox, CameraIntrinsics, Point3D


class DepthTo3DConverter:
    """
    Converts 2D bounding box + depth image to 3D position in camera frame.
    
    Uses the pinhole camera model:
        X = (u - cx) * Z / fx
        Y = (v - cy) * Z / fy
        Z = depth
    
    where (u, v) is pixel coordinate and Z is depth in meters.
    """
    
    def __init__(self, intrinsics: Optional[CameraIntrinsics] = None):
        """
        Initialize converter with camera intrinsics.
        
        Args:
            intrinsics: Camera intrinsic parameters. If None, will need to be
                       set later with set_intrinsics()
        """
        self.intrinsics = intrinsics
        
        # Configuration
        self.depth_sampling_radius = 5  # pixels to sample around center
        self.min_valid_depth = 0.3      # meters (30cm minimum)
        self.max_valid_depth = 10.0     # meters (10m maximum)
        self.min_valid_samples = 3      # minimum valid depth samples needed
        
    def set_intrinsics(self, intrinsics: CameraIntrinsics):
        """Set camera intrinsics after initialization"""
        self.intrinsics = intrinsics
    
    def set_intrinsics_from_camera_info(self, camera_info):
        """
        Set camera intrinsics from ROS CameraInfo message.
        
        Args:
            camera_info: sensor_msgs/CameraInfo message
        """
        self.intrinsics = CameraIntrinsics(
            fx=camera_info.k[0],
            fy=camera_info.k[4],
            cx=camera_info.k[2],
            cy=camera_info.k[5],
            width=camera_info.width,
            height=camera_info.height
        )
    
    def bbox_to_3d_position(
        self,
        bbox: BoundingBox,
        depth_image: np.ndarray,
        use_median: bool = True
    ) -> Optional[Point3D]:
        """
        Convert bounding box center + depth to 3D position.
        
        Args:
            bbox: 2D bounding box in pixel coordinates
            depth_image: Aligned depth image (HxW) in millimeters (uint16)
            use_median: If True, use median depth. If False, use mean.
        
        Returns:
            Point3D in camera frame (meters), or None if conversion fails
        """
        if self.intrinsics is None:
            raise ValueError("Camera intrinsics not set. Call set_intrinsics() first.")
        
        # Validate bounding box
        if not bbox.is_valid(self.intrinsics.width, self.intrinsics.height):
            return None
        
        # Get depth at bounding box center region
        depth_m = self._sample_depth(bbox, depth_image, use_median)
        
        if depth_m is None:
            return None
        
        # Validate depth range
        if not (self.min_valid_depth <= depth_m <= self.max_valid_depth):
            return None
        
        # Back-project to 3D using pinhole camera model
        x, y, z = self._backproject_to_3d(
            bbox.center_x,
            bbox.center_y,
            depth_m
        )
        
        return Point3D(x=x, y=y, z=z)
    
    def _sample_depth(
        self,
        bbox: BoundingBox,
        depth_image: np.ndarray,
        use_median: bool
    ) -> Optional[float]:
        """
        Sample depth around bounding box center.
        
        Uses a small region around the center to be robust to noise
        and missing depth pixels.
        
        Args:
            bbox: Bounding box
            depth_image: Depth image in millimeters
            use_median: Use median (robust) vs mean (smooth)
        
        Returns:
            Depth in meters, or None if insufficient valid samples
        """
        center_x = bbox.center_x
        center_y = bbox.center_y
        radius = self.depth_sampling_radius
        
        # Define sampling region (clipped to image bounds)
        y_min = max(0, center_y - radius)
        y_max = min(depth_image.shape[0], center_y + radius)
        x_min = max(0, center_x - radius)
        x_max = min(depth_image.shape[1], center_x + radius)
        
        # Extract depth region
        depth_region = depth_image[y_min:y_max, x_min:x_max]
        
        # Filter valid depths (non-zero, within range)
        # Depth is in millimeters, convert to meters
        valid_depths_mm = depth_region[depth_region > 0]
        
        if len(valid_depths_mm) < self.min_valid_samples:
            return None
        
        valid_depths_m = valid_depths_mm / 1000.0  # mm → m
        
        # Filter by valid range
        valid_depths_m = valid_depths_m[
            (valid_depths_m >= self.min_valid_depth) &
            (valid_depths_m <= self.max_valid_depth)
        ]
        
        if len(valid_depths_m) < self.min_valid_samples:
            return None
        
        # Return median or mean
        if use_median:
            return float(np.median(valid_depths_m))
        else:
            return float(np.mean(valid_depths_m))
    
    def _backproject_to_3d(
        self,
        pixel_x: int,
        pixel_y: int,
        depth_m: float
    ) -> Tuple[float, float, float]:
        """
        Back-project pixel + depth to 3D point using pinhole model.
        
        Args:
            pixel_x: X pixel coordinate
            pixel_y: Y pixel coordinate
            depth_m: Depth in meters
        
        Returns:
            (x, y, z) in camera frame (meters)
        """
        # Pinhole camera model (OpenCV/ROS convention)
        x = (pixel_x - self.intrinsics.cx) * depth_m / self.intrinsics.fx
        y = (pixel_y - self.intrinsics.cy) * depth_m / self.intrinsics.fy
        z = depth_m
        
        return (x, y, z)
    
    def batch_convert(
        self,
        bboxes: list[BoundingBox],
        depth_image: np.ndarray
    ) -> list[Optional[Point3D]]:
        """
        Convert multiple bounding boxes to 3D positions.
        
        Args:
            bboxes: List of bounding boxes
            depth_image: Depth image
        
        Returns:
            List of Point3D (or None for failed conversions)
        """
        return [
            self.bbox_to_3d_position(bbox, depth_image)
            for bbox in bboxes
        ]
    
    def get_info(self) -> dict:
        """Get converter configuration info"""
        return {
            'intrinsics': {
                'fx': self.intrinsics.fx if self.intrinsics else None,
                'fy': self.intrinsics.fy if self.intrinsics else None,
                'cx': self.intrinsics.cx if self.intrinsics else None,
                'cy': self.intrinsics.cy if self.intrinsics else None,
                'width': self.intrinsics.width if self.intrinsics else None,
                'height': self.intrinsics.height if self.intrinsics else None,
            },
            'config': {
                'depth_sampling_radius': self.depth_sampling_radius,
                'min_valid_depth': self.min_valid_depth,
                'max_valid_depth': self.max_valid_depth,
                'min_valid_samples': self.min_valid_samples,
            }
        }


# Utility functions for testing and debugging

def create_test_depth_image(
    width: int = 640,
    height: int = 480,
    distance: float = 2.0
) -> np.ndarray:
    """
    Create a synthetic depth image for testing.
    
    Args:
        width: Image width
        height: Image height
        distance: Constant depth value in meters
    
    Returns:
        Depth image (uint16) in millimeters
    """
    depth_mm = int(distance * 1000)
    return np.full((height, width), depth_mm, dtype=np.uint16)


def create_realsense_intrinsics() -> CameraIntrinsics:
    """
    Create typical RealSense D415 camera intrinsics for testing.
    
    Returns:
        CameraIntrinsics with typical D415 values
    """
    return CameraIntrinsics(
        fx=615.0,  # Typical for D415
        fy=615.0,
        cx=320.0,  # Center of 640x480
        cy=240.0,
        width=640,
        height=480
    )


if __name__ == "__main__":
    # Simple test/demo
    print("DepthTo3DConverter Test")
    print("=" * 50)
    
    # Create converter with test intrinsics
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    print(f"Camera Intrinsics:")
    print(f"  fx={intrinsics.fx}, fy={intrinsics.fy}")
    print(f"  cx={intrinsics.cx}, cy={intrinsics.cy}")
    print(f"  size={intrinsics.width}x{intrinsics.height}")
    print()
    
    # Create test depth image (person at 2 meters)
    depth_image = create_test_depth_image(distance=2.0)
    
    # Create bounding box at image center
    bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)
    print(f"Bounding Box:")
    print(f"  Position: ({bbox.x1}, {bbox.y1}) → ({bbox.x2}, {bbox.y2})")
    print(f"  Center: ({bbox.center_x}, {bbox.center_y})")
    print(f"  Size: {bbox.width}x{bbox.height}")
    print()
    
    # Convert to 3D
    point_3d = converter.bbox_to_3d_position(bbox, depth_image)
    
    if point_3d:
        print(f"3D Position (camera frame):")
        print(f"  X (right): {point_3d.x:.3f} m")
        print(f"  Y (down):  {point_3d.y:.3f} m")
        print(f"  Z (fwd):   {point_3d.z:.3f} m")
        print(f"  Distance:  {point_3d.distance:.3f} m")
        print()
        print("✓ Conversion successful!")
    else:
        print("✗ Conversion failed")

