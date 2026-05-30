#!/usr/bin/env python3
"""
Launch file for Map Generator node

Starts the real-time map generation from RealSense camera.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('nav'),
            'config',
            'map_generator.yaml'
        ]),
        description='Path to map generator configuration file'
    )
    
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )
    
    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='Log level (debug, info, warn, error)'
    )
    
    # Map Generator node
    map_generator_node = Node(
        package='nav',
        executable='map_generator',
        name='map_generator',
        output='screen',
        parameters=[
            LaunchConfiguration('config_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')}
        ],
        arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
        remappings=[
            ('/camera/camera/color/image_raw', '/camera/camera/color/image_raw'),
            ('/camera/camera/aligned_depth_to_color/image_raw', '/camera/camera/aligned_depth_to_color/image_raw'),
            ('/camera/camera/color/camera_info', '/camera/camera/color/camera_info'),
        ]
    )
    
    return LaunchDescription([
        config_file_arg,
        use_sim_time_arg,
        log_level_arg,
        LogInfo(msg='Starting Map Generator node...'),
        map_generator_node,
    ])
