#!/usr/bin/env python3
"""
Launch file for Map Manager node

Starts the map persistence and management system.
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
            'map_manager.yaml'
        ]),
        description='Path to map manager configuration file'
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
    
    # Map Manager node
    map_manager_node = Node(
        package='nav',
        executable='map_manager',
        name='map_manager',
        output='screen',
        parameters=[
            LaunchConfiguration('config_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')}
        ],
        arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
    )
    
    return LaunchDescription([
        config_file_arg,
        use_sim_time_arg,
        log_level_arg,
        LogInfo(msg='Starting Map Manager node...'),
        map_manager_node,
    ])
