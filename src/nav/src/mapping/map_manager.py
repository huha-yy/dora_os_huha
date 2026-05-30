#!/usr/bin/env python3
"""
Map Manager Node for Dorabot

Handles saving, loading, and managing navigation maps.
Provides services for map persistence and retrieval.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid
from nav_msgs.srv import GetMap
from std_srvs.srv import Empty, Trigger
import numpy as np
import yaml
import cv2
import os
from datetime import datetime
from pathlib import Path


class MapManager(Node):
    """
    Map Manager Node
    
    Manages map storage, retrieval, and metadata.
    Provides services for saving and loading maps.
    """
    
    def __init__(self):
        super().__init__('map_manager')
        
        # Declare parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('map_directory', '~/dorabot_ws/maps'),
                ('default_map_name', 'home'),
                ('auto_save_interval', 300.0),  # seconds (5 min)
                ('enable_auto_save', False),
                ('map_format', 'pgm'),  # pgm or png
                ('subscribe_to_rtabmap', True),
                ('subscribe_to_map_generator', True),
            ]
        )
        
        # Get parameters
        map_dir = self.get_parameter('map_directory').value
        self.map_directory = Path(os.path.expanduser(map_dir))
        self.default_map_name = self.get_parameter('default_map_name').value
        self.auto_save_interval = self.get_parameter('auto_save_interval').value
        self.enable_auto_save = self.get_parameter('enable_auto_save').value
        self.map_format = self.get_parameter('map_format').value
        self.subscribe_to_rtabmap = self.get_parameter('subscribe_to_rtabmap').value
        self.subscribe_to_map_generator = self.get_parameter('subscribe_to_map_generator').value
        
        # Create map directory if it doesn't exist
        self.map_directory.mkdir(parents=True, exist_ok=True)
        
        # Current map
        self.current_map = None
        self.map_metadata = {}
        
        # QoS profile for map data
        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        
        # Subscribers
        if self.subscribe_to_rtabmap:
            self.rtabmap_map_sub = self.create_subscription(
                OccupancyGrid,
                '/rtabmap/map',
                self.rtabmap_map_callback,
                map_qos
            )
            
        if self.subscribe_to_map_generator:
            self.generator_map_sub = self.create_subscription(
                OccupancyGrid,
                '/map_generator/occupancy_grid',
                self.generator_map_callback,
                map_qos
            )
        
        # Publishers
        self.map_pub = self.create_publisher(
            OccupancyGrid,
            '/map',
            map_qos
        )
        
        # Services
        self.save_map_srv = self.create_service(
            Trigger,
            '~/save_map',
            self.save_map_callback
        )
        
        self.load_map_srv = self.create_service(
            Trigger,
            '~/load_map',
            self.load_map_callback
        )
        
        self.get_map_srv = self.create_service(
            GetMap,
            '~/get_map',
            self.get_map_callback
        )
        
        self.list_maps_srv = self.create_service(
            Trigger,
            '~/list_maps',
            self.list_maps_callback
        )
        
        # Auto-save timer
        if self.enable_auto_save:
            self.auto_save_timer = self.create_timer(
                self.auto_save_interval,
                self.auto_save_callback
            )
            
        self.get_logger().info('Map Manager Node initialized')
        self.get_logger().info(f'Map directory: {self.map_directory}')
        
    def rtabmap_map_callback(self, msg):
        """Store map from RTAB-Map."""
        self.current_map = msg
        self.map_metadata['source'] = 'rtabmap'
        self.map_metadata['timestamp'] = self.get_clock().now().to_msg()
        
        # Republish on /map topic
        self.map_pub.publish(msg)
        
    def generator_map_callback(self, msg):
        """Store map from map generator."""
        if self.current_map is None or not self.subscribe_to_rtabmap:
            self.current_map = msg
            self.map_metadata['source'] = 'map_generator'
            self.map_metadata['timestamp'] = self.get_clock().now().to_msg()
            
            # Republish on /map topic
            self.map_pub.publish(msg)
            
    def save_map_callback(self, request, response):
        """Save the current map to disk."""
        if self.current_map is None:
            response.success = False
            response.message = 'No map available to save'
            return response
            
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            map_name = f"{self.default_map_name}_{timestamp}"
            
            # Save map
            self.save_map_to_disk(self.current_map, map_name)
            
            response.success = True
            response.message = f'Map saved as {map_name}'
            self.get_logger().info(response.message)
            
        except Exception as e:
            response.success = False
            response.message = f'Failed to save map: {str(e)}'
            self.get_logger().error(response.message)
            
        return response
        
    def load_map_callback(self, request, response):
        """Load a map from disk."""
        try:
            # Load default map
            map_name = self.default_map_name
            loaded_map = self.load_map_from_disk(map_name)
            
            if loaded_map is not None:
                self.current_map = loaded_map
                self.map_pub.publish(loaded_map)
                
                response.success = True
                response.message = f'Map {map_name} loaded successfully'
                self.get_logger().info(response.message)
            else:
                response.success = False
                response.message = f'Map {map_name} not found'
                self.get_logger().error(response.message)
                
        except Exception as e:
            response.success = False
            response.message = f'Failed to load map: {str(e)}'
            self.get_logger().error(response.message)
            
        return response
        
    def get_map_callback(self, request, response):
        """Return the current map."""
        if self.current_map is not None:
            response.map = self.current_map
        else:
            self.get_logger().warn('No map available')
            
        return response
        
    def list_maps_callback(self, request, response):
        """List all available maps."""
        try:
            maps = []
            for file_path in self.map_directory.glob(f'*.{self.map_format}'):
                map_name = file_path.stem
                yaml_path = file_path.with_suffix('.yaml')
                
                if yaml_path.exists():
                    with open(yaml_path, 'r') as f:
                        metadata = yaml.safe_load(f)
                        maps.append(f"{map_name}: {metadata.get('resolution', 'N/A')}m/px")
                else:
                    maps.append(map_name)
                    
            response.success = True
            response.message = '\n'.join(maps) if maps else 'No maps found'
            
        except Exception as e:
            response.success = False
            response.message = f'Failed to list maps: {str(e)}'
            
        return response
        
    def auto_save_callback(self):
        """Automatically save map at regular intervals."""
        if self.current_map is not None:
            try:
                self.save_map_to_disk(self.current_map, self.default_map_name)
                self.get_logger().info('Auto-saved map')
            except Exception as e:
                self.get_logger().error(f'Auto-save failed: {e}')
                
    def save_map_to_disk(self, map_msg: OccupancyGrid, map_name: str):
        """
        Save occupancy grid map to disk in ROS map format.
        
        Args:
            map_msg: OccupancyGrid message
            map_name: Name for the map files (without extension)
        """
        # Extract map data
        width = map_msg.info.width
        height = map_msg.info.height
        resolution = map_msg.info.resolution
        origin = map_msg.info.origin
        
        # Convert occupancy data to numpy array
        data = np.array(map_msg.data).reshape((height, width))
        
        # Create image: 0=black (occupied), 255=white (free), 128=gray (unknown)
        image = np.zeros((height, width), dtype=np.uint8)
        image[data == -1] = 205  # Unknown (gray)
        image[data == 0] = 254   # Free (white)
        image[data == 100] = 0   # Occupied (black)
        
        # For intermediate values, scale proportionally
        mask = (data > 0) & (data < 100)
        image[mask] = (254 - (data[mask] * 254 / 100)).astype(np.uint8)
        
        # Flip vertically (ROS convention)
        image = np.flipud(image)
        
        # Save image
        image_path = self.map_directory / f"{map_name}.{self.map_format}"
        cv2.imwrite(str(image_path), image)
        
        # Create YAML metadata
        yaml_data = {
            'image': f"{map_name}.{self.map_format}",
            'resolution': float(resolution),
            'origin': [
                float(origin.position.x),
                float(origin.position.y),
                float(origin.position.z)
            ],
            'negate': 0,
            'occupied_thresh': 0.65,
            'free_thresh': 0.196,
            'created_at': datetime.now().isoformat(),
            'width': int(width),
            'height': int(height)
        }
        
        # Save YAML
        yaml_path = self.map_directory / f"{map_name}.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False)
            
        self.get_logger().info(f'Saved map to {image_path}')
        
    def load_map_from_disk(self, map_name: str) -> OccupancyGrid:
        """
        Load occupancy grid map from disk.
        
        Args:
            map_name: Name of the map (without extension)
            
        Returns:
            OccupancyGrid message or None if not found
        """
        yaml_path = self.map_directory / f"{map_name}.yaml"
        
        if not yaml_path.exists():
            self.get_logger().error(f'Map YAML not found: {yaml_path}')
            return None
            
        # Load YAML metadata
        with open(yaml_path, 'r') as f:
            metadata = yaml.safe_load(f)
            
        # Load image
        image_path = self.map_directory / metadata['image']
        if not image_path.exists():
            self.get_logger().error(f'Map image not found: {image_path}')
            return None
            
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        
        # Flip vertically (ROS convention)
        image = np.flipud(image)
        
        # Convert image to occupancy data
        height, width = image.shape
        data = np.zeros((height, width), dtype=np.int8)
        
        # Unknown (gray)
        data[image > 250] = 0    # Free (white)
        data[image < 10] = 100   # Occupied (black)
        data[(image >= 10) & (image <= 250)] = -1  # Unknown
        
        # Create OccupancyGrid message
        map_msg = OccupancyGrid()
        map_msg.header.stamp = self.get_clock().now().to_msg()
        map_msg.header.frame_id = 'map'
        
        map_msg.info.resolution = float(metadata['resolution'])
        map_msg.info.width = width
        map_msg.info.height = height
        
        map_msg.info.origin.position.x = float(metadata['origin'][0])
        map_msg.info.origin.position.y = float(metadata['origin'][1])
        map_msg.info.origin.position.z = float(metadata['origin'][2])
        map_msg.info.origin.orientation.w = 1.0
        
        map_msg.data = data.flatten().tolist()
        
        self.get_logger().info(f'Loaded map from {image_path}')
        return map_msg


def main(args=None):
    rclpy.init(args=args)
    node = MapManager()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
