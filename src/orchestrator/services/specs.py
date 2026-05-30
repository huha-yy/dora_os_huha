# orchestrator/services/specs.py
import os
import sys
from typing import List
from .manager import Service


def _wrap_ros2_command(command_parts: List[str], workspace_root: str) -> List[str]:
    """
    Wraps a ROS2 command to run in a shell with the workspace environment sourced.
    
    Args:
        command_parts: The ROS2 command parts (e.g., ["ros2", "run", "nav", "map_generator"])
        workspace_root: The workspace root directory
        
    Returns:
        List containing bash command to source environment and run the command
    """
    # Build the command string
    cmd_str = " ".join(command_parts)
    
    # Create a bash command that sources the workspace and runs the command
    bash_cmd = f"source {workspace_root}/install/setup.bash && {cmd_str}"
    
    return ["bash", "-c", bash_cmd]


def build_services(config) -> List[Service]:
    """
    Builds the list of services based on configuration.
    
    Args:
        config: OrchestratorConfig object
        
    Returns:
        List of Service objects to be managed
    """
    workspace_root = os.getcwd()
    services = []
    
    # AI Agent
    if config.services.ai_agent:
        services.append(
            Service(
                name="ai_agent",
                command=[sys.executable, "src/ai_agent/run_server.py", "--lang", config.language],
                cwd=workspace_root,
            )
        )
    
    # RealSense Camera
    if config.services.realsense_camera:
        camera_cmd = [
            "ros2",
            "launch",
            "realsense2_camera",
            "rs_launch.py",
        ]
        
        if config.camera.align_depth:
            camera_cmd.append("align_depth.enable:=true")
        
        services.append(
            Service(
                name="realsense_d415",
                command=_wrap_ros2_command(camera_cmd, workspace_root),
                use_process_group=True,
            )
        )
    
    # Perception System
    if config.services.perception:
        perception_cmd = [sys.executable, "src/perception/main.py"]
        
        if config.perception.debug_video_path:
            perception_cmd.extend(["--debug-video-path", config.perception.debug_video_path])
        
        if config.perception.print_fps:
            perception_cmd.append("--print-fps")
        
        services.append(
            Service(
                name="perception",
                command=perception_cmd,
                cwd=workspace_root,
            )
        )
    
    # Map Generator
    if config.services.map_generator:
        map_gen_cmd = [
            "ros2", "run", "nav", "map_generator",
            "--ros-args",
            "--params-file", config.mapping.config_file,
        ]
        services.append(
            Service(
                name="map_generator",
                command=_wrap_ros2_command(map_gen_cmd, workspace_root),
                cwd=workspace_root,
                use_process_group=True,
            )
        )
        
        # Static TF Publisher for map frame
        # Publishes transform from 'map' to 'camera_link' so RViz2 can display the map
        static_tf_cmd = [
            "ros2", "run", "tf2_ros", "static_transform_publisher",
            "0", "0", "0", "0", "0", "0", "map", "camera_link"
        ]
        services.append(
            Service(
                name="static_tf_map_camera",
                command=_wrap_ros2_command(static_tf_cmd, workspace_root),
                use_process_group=True,
            )
        )
    
    # Map Manager
    if config.services.map_manager:
        map_mgr_cmd = [
            "ros2", "run", "nav", "map_manager",
            "--ros-args",
            "--params-file", config.map_manager.config_file,
        ]
        services.append(
            Service(
                name="map_manager",
                command=_wrap_ros2_command(map_mgr_cmd, workspace_root),
                cwd=workspace_root,
                use_process_group=True,
            )
        )
    
    # RTAB-Map SLAM
    if config.services.rtabmap_slam:
        rtabmap_cmd = [
            "ros2", "launch", "rtabmap_launch", "rtabmap.launch.py",
            f"rgb_topic:={config.rtabmap.rgb_topic}",
            f"depth_topic:={config.rtabmap.depth_topic}",
            f"camera_info_topic:={config.rtabmap.camera_info_topic}",
            f"approx_sync:={'true' if config.rtabmap.approx_sync else 'false'}",
            f"frame_id:={config.rtabmap.frame_id}",
        ]
        services.append(
            Service(
                name="rtabmap_slam",
                command=_wrap_ros2_command(rtabmap_cmd, workspace_root),
                use_process_group=True,
            )
        )
    
    # Nav2 Navigation
    if config.services.nav2_navigation:
        nav2_cmd = [
            "ros2", "launch", "nav", "navigation.launch.py",
        ]
        services.append(
            Service(
                name="nav2_navigation",
                command=_wrap_ros2_command(nav2_cmd, workspace_root),
                cwd=workspace_root,
                use_process_group=True,
            )
        )
    
    return services
