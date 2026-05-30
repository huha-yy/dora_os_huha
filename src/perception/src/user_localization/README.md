# User Localization Module

Detects and localizes users in 3D space using RealSense depth camera and YOLO person detection.

## Data Structures

All dataclasses (`BoundingBox`, `CameraIntrinsics`, `Point3D`) are defined in `body_tracking/state.py` and re-exported by this module for convenience. This centralizes all state-related data structures in one location.

## Components

### 1. DepthTo3DConverter ✅

Converts 2D bounding boxes + depth image → 3D positions in camera frame.

**Status:** Complete and tested

**Features:**
- Pinhole camera model with camera intrinsics
- Robust depth sampling (median filter around bbox center)
- Configurable depth range filtering
- Batch conversion support
- Built-in testing utilities

**Usage:**

```python
from user_localization import DepthTo3DConverter, BoundingBox, CameraIntrinsics

# Initialize with camera intrinsics
intrinsics = CameraIntrinsics(
    fx=615.0, fy=615.0,
    cx=320.0, cy=240.0,
    width=640, height=480
)
converter = DepthTo3DConverter(intrinsics)

# Or set from ROS CameraInfo message
converter.set_intrinsics_from_camera_info(camera_info_msg)

# Convert bbox + depth → 3D point
bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)
point_3d = converter.bbox_to_3d_position(bbox, depth_image)

if point_3d:
    print(f"Person at: x={point_3d.x:.2f}, y={point_3d.y:.2f}, z={point_3d.z:.2f}")
    print(f"Distance: {point_3d.distance:.2f} m")
```

**Coordinate System (Camera Frame):**
- `X`: Right (positive = to the right)
- `Y`: Down (positive = downward)
- `Z`: Forward (positive = away from camera)

**Configuration:**
- `depth_sampling_radius`: Pixels to sample around bbox center (default: 5)
- `min_valid_depth`: Minimum valid depth in meters (default: 0.3m)
- `max_valid_depth`: Maximum valid depth in meters (default: 10.0m)
- `min_valid_samples`: Minimum valid depth samples needed (default: 3)

**Testing:**

```bash
# Run built-in test
cd /home/frank/dorabot_ws
python3 src/perception/src/user_localization/depth_to_3d.py
```

---

### 2. CoordinateTransformer (Coming Next)

Transforms points from camera frame → map frame using TF2.

**Status:** Planned

---

### 3. UserTracker (Coming Next)

Smooths user tracking with Kalman filter and handles lost detections.

**Status:** Planned

---

### 4. PersonSelector (Coming Next)

Selects primary person when multiple people detected.

**Status:** Planned

---

## Integration with Body Tracking Node

The `DepthTo3DConverter` will be integrated into `body_tracking_node.py` to:

1. Subscribe to aligned depth image
2. Get bounding boxes from YOLO detection
3. Convert to 3D positions
4. Transform to map frame
5. Publish user position

---

## Requirements

```
numpy
sensor_msgs (ROS2)
geometry_msgs (ROS2)
```

For tracking (future):
```
filterpy  # Kalman filter
```

---

**Created:** 2026-01-19  
**Last Updated:** 2026-01-19

