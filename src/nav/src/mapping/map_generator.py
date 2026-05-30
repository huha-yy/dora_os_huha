#!/usr/bin/env python3
"""
Map Generator Node for Dorabot

This node handles real-time map generation from RealSense camera input.
It subscribes to depth and RGB images, processes them to create a 2D occupancy grid map,
and publishes the map for navigation purposes.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import Image, PointCloud2, CameraInfo
from nav_msgs.msg import OccupancyGrid, MapMetaData
from geometry_msgs.msg import Pose, Point, Quaternion
from std_srvs.srv import Empty
import numpy as np
from cv_bridge import CvBridge
import cv2
from collections import deque
import time


class MapGenerator(Node):
    """
    Map Generator Node
    
    Subscribes to RealSense camera topics and generates 2D occupancy grid maps
    suitable for navigation.
    """
    
    def __init__(self):
        super().__init__('map_generator')
        
        # Declare parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('map_resolution', 0.05),  # meters per pixel
                ('map_width', 10.0),       # meters
                ('map_height', 10.0),      # meters
                ('min_obstacle_height', 0.1),  # meters
                ('max_obstacle_height', 2.0),  # meters
                ('depth_max_range', 5.0),      # meters
                ('depth_min_range', 0.3),      # meters
                ('update_rate', 2.0),          # Hz
                ('occupancy_threshold', 0.65),  # 0-1
                ('free_threshold', 0.35),       # 0-1
                ('rgb_topic', '/camera/camera/color/image_raw'),
                ('depth_topic', '/camera/camera/aligned_depth_to_color/image_raw'),
                ('camera_info_topic', '/camera/camera/color/camera_info'),
                ('enable_visualization', True),
            ]
        )
        
        # Get parameters
        self.map_resolution = self.get_parameter('map_resolution').value
        self.map_width = self.get_parameter('map_width').value
        self.map_height = self.get_parameter('map_height').value
        self.min_obstacle_height = self.get_parameter('min_obstacle_height').value
        self.max_obstacle_height = self.get_parameter('max_obstacle_height').value
        self.depth_max_range = self.get_parameter('depth_max_range').value
        self.depth_min_range = self.get_parameter('depth_min_range').value
        self.update_rate = self.get_parameter('update_rate').value
        self.occupancy_threshold = self.get_parameter('occupancy_threshold').value
        self.free_threshold = self.get_parameter('free_threshold').value
        self.rgb_topic = self.get_parameter('rgb_topic').value
        self.depth_topic = self.get_parameter('depth_topic').value
        self.camera_info_topic = self.get_parameter('camera_info_topic').value
        self.enable_visualization = self.get_parameter('enable_visualization').value
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Initialize map
        self.grid_width = int(self.map_width / self.map_resolution)
        self.grid_height = int(self.map_height / self.map_resolution)
        self.occupancy_grid = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
        self.observation_count = np.zeros((self.grid_height, self.grid_width), dtype=np.int32)
        
        # Camera intrinsics
        self.camera_matrix = None
        self.camera_info_received = False
        
        # Data buffers
        self.latest_depth = None
        self.latest_rgb = None
        self.depth_timestamp = None
        self.rgb_timestamp = None
        
        # QoS profile for sensor data
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # QoS profile for map data
        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        
        # Subscribers
        self.depth_sub = self.create_subscription(
            Image,
            self.depth_topic,
            self.depth_callback,
            sensor_qos
        )
        
        self.rgb_sub = self.create_subscription(
            Image,
            self.rgb_topic,
            self.rgb_callback,
            sensor_qos
        )
        
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            sensor_qos
        )
        
        # Publishers
        self.map_pub = self.create_publisher(
            OccupancyGrid,
            '/map_generator/occupancy_grid',
            map_qos
        )
        
        self.map_metadata_pub = self.create_publisher(
            MapMetaData,
            '/map_generator/map_metadata',
            10
        )
        
        # Services
        self.reset_map_srv = self.create_service(
            Empty,
            '~/reset_map',
            self.reset_map_callback
        )
        
        # Timer for map updates
        self.map_timer = self.create_timer(
            1.0 / self.update_rate,
            self.update_map_callback
        )
        
        self.get_logger().info('Map Generator Node initialized')
        self.get_logger().info(f'Map size: {self.map_width}x{self.map_height}m, Resolution: {self.map_resolution}m/pixel')
        self.get_logger().info(f'Grid size: {self.grid_width}x{self.grid_height} cells')
        
    def camera_info_callback(self, msg):
        """Process camera intrinsics."""
        if not self.camera_info_received:
            self.camera_matrix = np.array(msg.k).reshape(3, 3)
            self.camera_info_received = True
            self.get_logger().info('Camera intrinsics received')
            
    def depth_callback(self, msg):
        """Store latest depth image."""
        try:
            # Convert ROS Image to OpenCV format
            self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            self.depth_timestamp = msg.header.stamp
        except Exception as e:
            self.get_logger().error(f'Error processing depth image: {e}')
            
    def rgb_callback(self, msg):
        """Store latest RGB image."""
        try:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.rgb_timestamp = msg.header.stamp
        except Exception as e:
            self.get_logger().error(f'Error processing RGB image: {e}')
            
    def update_map_callback(self):
        """Main map update loop."""
        if self.latest_depth is None or not self.camera_info_received:
            return
            
        try:
            # Process depth image to update occupancy grid
            self.process_depth_image(self.latest_depth)
            
            # Publish the map
            self.publish_map()
            
        except Exception as e:
            self.get_logger().error(f'Error updating map: {e}')
            
    def process_depth_image(self, depth_image):
        """
        Process depth image and update occupancy grid.
        
        Args:
            depth_image: Depth image from camera (in mm or m depending on camera)
        """
        if self.camera_matrix is None:
            return
            
        # Convert depth to meters if needed (RealSense typically provides mm)
        if depth_image.max() > 100:  # Likely in mm
            depth_m = depth_image.astype(np.float32) / 1000.0
        else:
            depth_m = depth_image.astype(np.float32)
            
        # Get valid depth points
        valid_mask = (depth_m > self.depth_min_range) & (depth_m < self.depth_max_range)
        
        # Create point cloud from depth
        height, width = depth_m.shape
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        cx = self.camera_matrix[0, 2]
        cy = self.camera_matrix[1, 2]
        
        # Generate pixel coordinates
        u = np.arange(width)
        v = np.arange(height)
        u, v = np.meshgrid(u, v)
        
        # Convert to 3D points (camera frame)
        z = depth_m
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        
        # Apply valid mask
        x = x[valid_mask]
        y = y[valid_mask]
        z = z[valid_mask]
        
        # Filter by height (y is typically up/down in camera frame)
        # Assuming camera is tilted or mounted on robot, adjust as needed
        # For floor obstacles: filter points at certain height range
        height_mask = (y > -self.max_obstacle_height) & (y < -self.min_obstacle_height)
        
        x_filtered = x[height_mask]
        z_filtered = z[height_mask]  # z is forward distance
        
        # Project to 2D grid (top-down view)
        # Map center is at grid center
        grid_x = ((x_filtered + self.map_width / 2) / self.map_resolution).astype(np.int32)
        grid_y = ((z_filtered) / self.map_resolution).astype(np.int32)
        
        # Keep only points within grid bounds
        valid_grid = (grid_x >= 0) & (grid_x < self.grid_width) & \
                     (grid_y >= 0) & (grid_y < self.grid_height)
        
        grid_x = grid_x[valid_grid]
        grid_y = grid_y[valid_grid]
        
        # Update occupancy grid using log-odds
        for gx, gy in zip(grid_x, grid_y):
            self.occupancy_grid[gy, gx] += 0.1  # Occupied
            self.observation_count[gy, gx] += 1
            
        # Mark free space (ray tracing from camera to obstacles)
        # Simplified: mark nearby cells as free
        camera_grid_x = self.grid_width // 2
        camera_grid_y = 0
        
        for gx, gy in zip(grid_x[:100:10], grid_y[:100:10]):  # Sample points
            # Bresenham line from camera to obstacle
            points = self.bresenham_line(camera_grid_x, camera_grid_y, gx, gy)
            for px, py in points[:-1]:  # All points except the obstacle
                if 0 <= px < self.grid_width and 0 <= py < self.grid_height:
                    self.occupancy_grid[py, px] -= 0.05  # Free space
                    self.observation_count[py, px] += 1
                    
        # Clamp values
        self.occupancy_grid = np.clip(self.occupancy_grid, -2.0, 2.0)
        
    def bresenham_line(self, x0, y0, x1, y1):
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
        
    def publish_map(self):
        """Publish the current occupancy grid."""
        # Convert log-odds to probability and then to occupancy value
        prob = 1.0 / (1.0 + np.exp(-self.occupancy_grid))
        
        # Convert to occupancy grid format (-1 unknown, 0-100 occupied probability)
        occupancy = np.full_like(prob, -1, dtype=np.int8)
        
        # Set values where we have observations
        observed_mask = self.observation_count > 0
        occupancy[observed_mask] = (prob[observed_mask] * 100).astype(np.int8)
        
        # Create OccupancyGrid message
        map_msg = OccupancyGrid()
        map_msg.header.stamp = self.get_clock().now().to_msg()
        map_msg.header.frame_id = 'map'
        
        map_msg.info.resolution = self.map_resolution
        map_msg.info.width = self.grid_width
        map_msg.info.height = self.grid_height
        
        # Origin is at bottom-left corner
        map_msg.info.origin.position.x = -self.map_width / 2
        map_msg.info.origin.position.y = 0.0
        map_msg.info.origin.position.z = 0.0
        map_msg.info.origin.orientation.w = 1.0
        
        # Flatten and convert to list (row-major order)
        map_msg.data = occupancy.flatten().tolist()
        
        self.map_pub.publish(map_msg)
        
        # Publish metadata
        self.map_metadata_pub.publish(map_msg.info)
        
    def reset_map_callback(self, request, response):
        """Reset the map to empty state."""
        self.occupancy_grid.fill(0.0)
        self.observation_count.fill(0)
        self.get_logger().info('Map reset')
        return response


def main(args=None):
    rclpy.init(args=args)
    node = MapGenerator()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
