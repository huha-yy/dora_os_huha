#!/usr/bin/env python3
"""
Full Mapping System Launch File

Launches all components for complete mapping system:
- RealSense camera
- RTAB-Map SLAM (optional)
- Map Generator (optional)
- Map Manager
- RViz2 for visualization
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )
    
    launch_realsense_arg = DeclareLaunchArgument(
        'launch_realsense',
        default_value='true',
        description='Launch RealSense camera'
    )
    
    launch_rtabmap_arg = DeclareLaunchArgument(
        'launch_rtabmap',
        default_value='true',
        description='Launch RTAB-Map SLAM'
    )
    
    launch_map_generator_arg = DeclareLaunchArgument(
        'launch_map_generator',
        default_value='false',
        description='Launch custom map generator (alternative to RTAB-Map mapping)'
    )
    
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='true',
        description='Launch RViz2 for visualization'
    )
    
    align_depth_arg = DeclareLaunchArgument(
        'align_depth',
        default_value='true',
        description='Enable depth alignment in RealSense'
    )
    
    # RealSense camera launch
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('realsense2_camera'),
                'launch',
                'rs_launch.py'
            ])
        ]),
        launch_arguments={
            'align_depth.enable': LaunchConfiguration('align_depth'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('launch_realsense'))
    )
    
    # RTAB-Map SLAM launch
    rtabmap_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('rtabmap_launch'),
                'launch',
                'rtabmap.launch.py'
            ])
        ]),
        launch_arguments={
            'rgb_topic': '/camera/camera/color/image_raw',
            'depth_topic': '/camera/camera/aligned_depth_to_color/image_raw',
            'camera_info_topic': '/camera/camera/color/camera_info',
            'approx_sync': 'true',
            'frame_id': 'camera_link',
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('launch_rtabmap'))
    )
    
    # Map Generator node (alternative to RTAB-Map)
    map_generator_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('nav'),
                'launch',
                'map_generator.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('launch_map_generator'))
    )
    
    # Map Manager node
    map_manager_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('nav'),
                'launch',
                'map_manager.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items()
    )
    
    # RViz2 for visualization
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', PathJoinSubstitution([
            FindPackageShare('nav'),
            'config',
            'mapping.rviz'
        ])],
        condition=IfCondition(LaunchConfiguration('launch_rviz')),
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}]
    )
    
    return LaunchDescription([
        # Arguments
        use_sim_time_arg,
        launch_realsense_arg,
        launch_rtabmap_arg,
        launch_map_generator_arg,
        launch_rviz_arg,
        align_depth_arg,
        
        # Info
        LogInfo(msg='========================================'),
        LogInfo(msg='   Dorabot Mapping System Starting'),
        LogInfo(msg='========================================'),
        
        # Launches
        realsense_launch,
        rtabmap_launch,
        map_generator_launch,
        map_manager_launch,
        rviz_node,
        
        LogInfo(msg='All mapping components launched'),
    ])
