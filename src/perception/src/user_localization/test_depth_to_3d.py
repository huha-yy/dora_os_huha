"""
Unit tests for DepthTo3DConverter

Run with: python3 test_depth_to_3d.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import body_tracking
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from user_localization.depth_to_3d import (
    DepthTo3DConverter,
    create_test_depth_image,
    create_realsense_intrinsics
)
from body_tracking.state import BoundingBox, CameraIntrinsics, Point3D


def test_bbox_center():
    """Test bounding box center calculation"""
    bbox = BoundingBox(x1=100, y1=100, x2=200, y2=200)
    assert bbox.center_x == 150
    assert bbox.center_y == 150
    assert bbox.width == 100
    assert bbox.height == 100
    print("✓ Bounding box center test passed")


def test_bbox_validation():
    """Test bounding box validation"""
    # Valid bbox
    bbox_valid = BoundingBox(x1=100, y1=100, x2=200, y2=200)
    assert bbox_valid.is_valid(640, 480) == True
    
    # Out of bounds
    bbox_invalid = BoundingBox(x1=100, y1=100, x2=700, y2=200)
    assert bbox_invalid.is_valid(640, 480) == False
    
    # Negative coordinates
    bbox_negative = BoundingBox(x1=-10, y1=100, x2=200, y2=200)
    assert bbox_negative.is_valid(640, 480) == False
    
    print("✓ Bounding box validation test passed")


def test_point3d_distance():
    """Test 3D point distance calculation"""
    point = Point3D(x=3.0, y=0.0, z=4.0)
    assert abs(point.distance - 5.0) < 0.001  # 3-4-5 triangle
    print("✓ Point3D distance test passed")


def test_center_person_2m():
    """Test person at center of image, 2 meters away"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    # Person at center, 2m depth
    depth_image = create_test_depth_image(distance=2.0)
    bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)  # Center
    
    point = converter.bbox_to_3d_position(bbox, depth_image)
    
    assert point is not None
    assert abs(point.x) < 0.01  # Should be near 0 (center)
    assert abs(point.y) < 0.01  # Should be near 0 (center)
    assert abs(point.z - 2.0) < 0.01  # Should be 2m
    
    print("✓ Center person at 2m test passed")


def test_offset_person():
    """Test person offset from center"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    # Person to the right, 2m depth
    depth_image = create_test_depth_image(distance=2.0)
    bbox = BoundingBox(x1=420, y1=190, x2=520, y2=290)  # Right side
    
    point = converter.bbox_to_3d_position(bbox, depth_image)
    
    assert point is not None
    assert point.x > 0.2  # Should be positive (to the right)
    assert abs(point.z - 2.0) < 0.01
    
    print(f"  Person at right: x={point.x:.2f}m, z={point.z:.2f}m")
    print("✓ Offset person test passed")


def test_invalid_depth():
    """Test handling of invalid depth values"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    # All zero depth (no valid data)
    depth_image = np.zeros((480, 640), dtype=np.uint16)
    bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)
    
    point = converter.bbox_to_3d_position(bbox, depth_image)
    
    assert point is None  # Should fail gracefully
    
    print("✓ Invalid depth handling test passed")


def test_depth_range_filtering():
    """Test depth range filtering"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)
    
    # Too close (< 0.3m default minimum)
    depth_too_close = create_test_depth_image(distance=0.1)
    point = converter.bbox_to_3d_position(bbox, depth_too_close)
    assert point is None
    
    # Too far (> 10m default maximum)
    depth_too_far = create_test_depth_image(distance=15.0)
    point = converter.bbox_to_3d_position(bbox, depth_too_far)
    assert point is None
    
    # Valid range
    depth_valid = create_test_depth_image(distance=2.0)
    point = converter.bbox_to_3d_position(bbox, depth_valid)
    assert point is not None
    
    print("✓ Depth range filtering test passed")


def test_batch_conversion():
    """Test batch conversion of multiple bounding boxes"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    depth_image = create_test_depth_image(distance=2.0)
    
    bboxes = [
        BoundingBox(x1=270, y1=190, x2=370, y2=290),  # Center
        BoundingBox(x1=420, y1=190, x2=520, y2=290),  # Right
        BoundingBox(x1=120, y1=190, x2=220, y2=290),  # Left
    ]
    
    points = converter.batch_convert(bboxes, depth_image)
    
    assert len(points) == 3
    assert all(p is not None for p in points)
    assert points[0].x < points[1].x  # Right person should have higher X
    assert points[2].x < points[0].x  # Left person should have lower X
    
    print("✓ Batch conversion test passed")


def test_median_vs_mean():
    """Test median vs mean depth sampling"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    # Create depth image with some noise
    depth_image = create_test_depth_image(distance=2.0)
    # Add some outliers
    depth_image[240:250, 320:330] = 5000  # 5m outlier
    
    bbox = BoundingBox(x1=270, y1=190, x2=370, y2=290)
    
    # Median should be robust to outliers
    point_median = converter.bbox_to_3d_position(bbox, depth_image, use_median=True)
    point_mean = converter.bbox_to_3d_position(bbox, depth_image, use_median=False)
    
    assert point_median is not None
    assert point_mean is not None
    # Median should be closer to 2.0 (robust to outliers)
    assert abs(point_median.z - 2.0) < abs(point_mean.z - 2.0)
    
    print(f"  Median depth: {point_median.z:.3f}m")
    print(f"  Mean depth:   {point_mean.z:.3f}m")
    print("✓ Median vs mean test passed")


def test_out_of_bounds_bbox():
    """Test handling of out-of-bounds bounding boxes"""
    intrinsics = create_realsense_intrinsics()
    converter = DepthTo3DConverter(intrinsics)
    
    depth_image = create_test_depth_image(distance=2.0)
    
    # Partially out of bounds
    bbox_oob = BoundingBox(x1=600, y1=190, x2=700, y2=290)
    point = converter.bbox_to_3d_position(bbox_oob, depth_image)
    
    assert point is None  # Should reject invalid bbox
    
    print("✓ Out of bounds bbox test passed")


def run_all_tests():
    """Run all unit tests"""
    print("="*60)
    print("Running DepthTo3DConverter Unit Tests")
    print("="*60)
    print()
    
    tests = [
        test_bbox_center,
        test_bbox_validation,
        test_point3d_distance,
        test_center_person_2m,
        test_offset_person,
        test_invalid_depth,
        test_depth_range_filtering,
        test_batch_conversion,
        test_median_vs_mean,
        test_out_of_bounds_bbox,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print()
    print("="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(run_all_tests())

