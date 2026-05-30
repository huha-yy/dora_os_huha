#!/usr/bin/env python3
"""
Map Processing Utilities for Dorabot

Provides utilities for processing point clouds, depth images,
and converting them to 2D occupancy grids for navigation.
"""

import numpy as np
import cv2
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class CameraIntrinsics:
    """Camera intrinsics parameters."""
    fx: float  # Focal length x
    fy: float  # Focal length y
    cx: float  # Principal point x
    cy: float  # Principal point y
    width: int
    height: int


class PointCloudProcessor:
    """Process 3D point clouds for mapping."""
    
    def __init__(self, intrinsics: CameraIntrinsics):
        self.intrinsics = intrinsics
        
    def depth_to_pointcloud(
        self, 
        depth_image: np.ndarray,
        color_image: Optional[np.ndarray] = None,
        depth_scale: float = 0.001
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Convert depth image to 3D point cloud.
        
        Args:
            depth_image: Depth image (H x W)
            color_image: Optional RGB image (H x W x 3)
            depth_scale: Scale factor to convert depth to meters
            
        Returns:
            points: (N x 3) array of 3D points [x, y, z]
            colors: (N x 3) array of RGB colors or None
        """
        height, width = depth_image.shape
        
        # Create meshgrid of pixel coordinates
        u = np.arange(width)
        v = np.arange(height)
        u, v = np.meshgrid(u, v)
        
        # Convert depth to meters
        z = depth_image.astype(np.float32) * depth_scale
        
        # Compute 3D coordinates
        x = (u - self.intrinsics.cx) * z / self.intrinsics.fx
        y = (v - self.intrinsics.cy) * z / self.intrinsics.fy
        
        # Stack to (H, W, 3)
        points_3d = np.stack([x, y, z], axis=-1)
        
        # Flatten to (N, 3)
        points = points_3d.reshape(-1, 3)
        
        # Process colors if provided
        colors = None
        if color_image is not None:
            colors = color_image.reshape(-1, 3)
            
        return points, colors
        
    def filter_by_depth(
        self,
        points: np.ndarray,
        min_depth: float = 0.3,
        max_depth: float = 5.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Filter points by depth range.
        
        Args:
            points: (N x 3) array of points
            min_depth: Minimum depth in meters
            max_depth: Maximum depth in meters
            
        Returns:
            filtered_points: Filtered points
            mask: Boolean mask of valid points
        """
        z = points[:, 2]
        mask = (z > min_depth) & (z < max_depth) & (z > 0)
        return points[mask], mask
        
    def filter_by_height(
        self,
        points: np.ndarray,
        min_height: float = -2.0,
        max_height: float = 2.0,
        height_axis: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Filter points by height range.
        
        Args:
            points: (N x 3) array of points
            min_height: Minimum height in meters
            max_height: Maximum height in meters
            height_axis: Axis representing height (0=x, 1=y, 2=z)
            
        Returns:
            filtered_points: Filtered points
            mask: Boolean mask of valid points
        """
        h = points[:, height_axis]
        mask = (h > min_height) & (h < max_height)
        return points[mask], mask
        
    def remove_outliers(
        self,
        points: np.ndarray,
        k_neighbors: int = 20,
        std_ratio: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Remove statistical outliers from point cloud.
        
        Args:
            points: (N x 3) array of points
            k_neighbors: Number of neighbors to consider
            std_ratio: Standard deviation threshold
            
        Returns:
            filtered_points: Filtered points
            mask: Boolean mask of inlier points
        """
        if len(points) < k_neighbors:
            return points, np.ones(len(points), dtype=bool)
            
        # Compute pairwise distances (simplified, not efficient for large clouds)
        # For production, use KDTree or similar
        distances = np.zeros(len(points))
        
        for i in range(len(points)):
            dists = np.linalg.norm(points - points[i], axis=1)
            # Get k nearest neighbors (excluding self)
            nearest = np.partition(dists, min(k_neighbors, len(dists)-1))[:k_neighbors]
            distances[i] = np.mean(nearest)
            
        # Compute statistics
        mean_dist = np.mean(distances)
        std_dist = np.std(distances)
        
        # Filter outliers
        threshold = mean_dist + std_ratio * std_dist
        mask = distances < threshold
        
        return points[mask], mask
        
    def downsample_voxel(
        self,
        points: np.ndarray,
        voxel_size: float = 0.05
    ) -> np.ndarray:
        """
        Downsample point cloud using voxel grid.
        
        Args:
            points: (N x 3) array of points
            voxel_size: Size of voxel in meters
            
        Returns:
            downsampled_points: Downsampled points
        """
        if len(points) == 0:
            return points
            
        # Compute voxel indices
        voxel_indices = np.floor(points / voxel_size).astype(np.int32)
        
        # Find unique voxels
        unique_voxels, inverse_indices = np.unique(
            voxel_indices, axis=0, return_inverse=True
        )
        
        # Compute centroid for each voxel
        downsampled = np.zeros((len(unique_voxels), 3))
        for i in range(len(unique_voxels)):
            mask = inverse_indices == i
            downsampled[i] = np.mean(points[mask], axis=0)
            
        return downsampled


class OccupancyGridMapper:
    """Convert 3D point cloud to 2D occupancy grid."""
    
    def __init__(
        self,
        resolution: float = 0.05,
        width: float = 10.0,
        height: float = 10.0,
        origin_x: float = 0.0,
        origin_y: float = 0.0
    ):
        """
        Initialize occupancy grid mapper.
        
        Args:
            resolution: Grid resolution in meters/cell
            width: Grid width in meters
            height: Grid height in meters
            origin_x: X coordinate of grid origin
            origin_y: Y coordinate of grid origin
        """
        self.resolution = resolution
        self.width = width
        self.height = height
        self.origin_x = origin_x
        self.origin_y = origin_y
        
        self.grid_width = int(width / resolution)
        self.grid_height = int(height / resolution)
        
        # Log-odds representation
        self.grid = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
        self.observation_count = np.zeros((self.grid_height, self.grid_width), dtype=np.int32)
        
        # Probabilities for updates
        self.prob_occupied = 0.7
        self.prob_free = 0.3
        
        # Convert to log-odds
        self.log_odds_occupied = np.log(self.prob_occupied / (1 - self.prob_occupied))
        self.log_odds_free = np.log(self.prob_free / (1 - self.prob_free))
        
    def world_to_grid(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert world coordinates to grid indices."""
        grid_x = ((x - self.origin_x) / self.resolution).astype(np.int32)
        grid_y = ((y - self.origin_y) / self.resolution).astype(np.int32)
        return grid_x, grid_y
        
    def grid_to_world(self, grid_x: np.ndarray, grid_y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert grid indices to world coordinates."""
        x = grid_x * self.resolution + self.origin_x
        y = grid_y * self.resolution + self.origin_y
        return x, y
        
    def is_valid_grid_index(self, grid_x: np.ndarray, grid_y: np.ndarray) -> np.ndarray:
        """Check if grid indices are within bounds."""
        return (grid_x >= 0) & (grid_x < self.grid_width) & \
               (grid_y >= 0) & (grid_y < self.grid_height)
               
    def update_from_points(
        self,
        points: np.ndarray,
        sensor_position: Tuple[float, float] = (0.0, 0.0),
        mark_free_space: bool = True
    ):
        """
        Update occupancy grid from 3D points.
        
        Args:
            points: (N x 3) array of 3D points [x, y, z]
            sensor_position: (x, y) position of sensor in world frame
            mark_free_space: Whether to mark free space using ray tracing
        """
        if len(points) == 0:
            return
            
        # Project points to 2D (x, z plane - assuming y is up)
        x = points[:, 0]
        z = points[:, 2]
        
        # Convert to grid coordinates
        grid_x, grid_y = self.world_to_grid(x, z)
        
        # Filter valid indices
        valid = self.is_valid_grid_index(grid_x, grid_y)
        grid_x = grid_x[valid]
        grid_y = grid_y[valid]
        
        # Update occupied cells
        for gx, gy in zip(grid_x, grid_y):
            self.grid[gy, gx] += self.log_odds_occupied
            self.observation_count[gy, gx] += 1
            
        # Mark free space using ray tracing
        if mark_free_space:
            sensor_grid_x, sensor_grid_y = self.world_to_grid(
                np.array([sensor_position[0]]),
                np.array([sensor_position[1]])
            )
            sensor_gx, sensor_gy = int(sensor_grid_x[0]), int(sensor_grid_y[0])
            
            # Sample subset of points for ray tracing (for performance)
            sample_size = min(100, len(grid_x))
            indices = np.random.choice(len(grid_x), sample_size, replace=False)
            
            for idx in indices:
                gx, gy = grid_x[idx], grid_y[idx]
                # Trace ray from sensor to obstacle
                ray_points = self.bresenham_line(sensor_gx, sensor_gy, gx, gy)
                
                # Mark all points except last (obstacle) as free
                for rx, ry in ray_points[:-1]:
                    if self.is_valid_grid_index(np.array([rx]), np.array([ry]))[0]:
                        self.grid[ry, rx] += self.log_odds_free
                        self.observation_count[ry, rx] += 1
                        
        # Clamp log-odds values
        self.grid = np.clip(self.grid, -5.0, 5.0)
        
    def bresenham_line(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Bresenham's line algorithm for ray tracing."""
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        while True:
            points.append((x, y))
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
                
        return points
        
    def get_occupancy_grid(self) -> np.ndarray:
        """
        Get occupancy grid as probability values [0-100].
        
        Returns:
            grid: (H x W) array with values -1 (unknown), 0-100 (occupied probability)
        """
        # Convert log-odds to probability
        prob = 1.0 / (1.0 + np.exp(-self.grid))
        
        # Create output grid
        occupancy = np.full((self.grid_height, self.grid_width), -1, dtype=np.int8)
        
        # Set values where we have observations
        observed_mask = self.observation_count > 0
        occupancy[observed_mask] = (prob[observed_mask] * 100).astype(np.int8)
        
        return occupancy
        
    def reset(self):
        """Reset the grid to empty state."""
        self.grid.fill(0.0)
        self.observation_count.fill(0)
        
    def apply_morphology(
        self,
        kernel_size: int = 3,
        operation: str = 'closing'
    ) -> np.ndarray:
        """
        Apply morphological operations to clean up the map.
        
        Args:
            kernel_size: Size of morphological kernel
            operation: 'closing', 'opening', 'dilation', 'erosion'
            
        Returns:
            processed_grid: Processed occupancy grid
        """
        occupancy = self.get_occupancy_grid()
        
        # Convert to binary (occupied/free)
        binary = np.zeros_like(occupancy, dtype=np.uint8)
        binary[occupancy > 50] = 255  # Occupied
        binary[occupancy >= 0] &= occupancy <= 50  # Free remains 0
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        
        if operation == 'closing':
            processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        elif operation == 'opening':
            processed = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        elif operation == 'dilation':
            processed = cv2.dilate(binary, kernel)
        elif operation == 'erosion':
            processed = cv2.erode(binary, kernel)
        else:
            processed = binary
            
        # Convert back to occupancy format
        result = np.full_like(occupancy, -1, dtype=np.int8)
        result[processed == 255] = 100  # Occupied
        result[processed == 0] = 0      # Free
        
        return result
        
    def inflate_obstacles(self, inflation_radius: float) -> np.ndarray:
        """
        Inflate obstacles for safe navigation.
        
        Args:
            inflation_radius: Inflation radius in meters
            
        Returns:
            inflated_grid: Grid with inflated obstacles
        """
        occupancy = self.get_occupancy_grid()
        
        # Convert inflation radius to cells
        inflation_cells = int(inflation_radius / self.resolution)
        
        # Create kernel for inflation
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (inflation_cells * 2 + 1, inflation_cells * 2 + 1)
        )
        
        # Binary occupied map
        occupied = (occupancy > 50).astype(np.uint8) * 255
        
        # Dilate obstacles
        inflated = cv2.dilate(occupied, kernel)
        
        # Convert back to occupancy format
        result = occupancy.copy()
        result[inflated == 255] = 100
        
        return result
