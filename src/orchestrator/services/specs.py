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
    
    # AI Agent / Chatbot
    # Runs the new standalone chatbot (src/chatbot) using ITS OWN virtualenv,
    # which carries its ASR/TTS/LLM/VAD dependencies and config.json (port 8000).
    if config.services.ai_agent:
        chatbot_dir = os.path.join(workspace_root, "src", "chatbot")
        chatbot_python = os.path.join(chatbot_dir, ".venv", "bin", "python")
        # Fall back to the current interpreter if the chatbot venv is missing.
        if not os.path.exists(chatbot_python):
            chatbot_python = sys.executable
        services.append(
            Service(
                name="chatbot",
                command=[chatbot_python, "main.py", "--log-level", "INFO"],
                cwd=chatbot_dir,
                # Clear ROS 2's PYTHONPATH/AMENT entries so they don't shadow the
                # chatbot venv's own packages (e.g. numpy) when the orchestrator
                # is launched with ROS 2 sourced.
                env={"PYTHONPATH": "", "AMENT_PREFIX_PATH": ""},
            )
        )
    
    # RealSense Camera
    # Lightweight pyrealsense2-backed ROS publisher (replaces realsense2_camera,
    # which has no arm64 apt binary). Publishes /camera/camera/color/image_raw.
    if config.services.realsense_camera:
        camera_cmd = [sys.executable, "src/perception/run_camera.py"]
        camera_cmd.extend([
            "--width", str(config.camera.width),
            "--height", str(config.camera.height),
            "--fps", str(config.camera.fps),
        ])
        # Depth alignment is required for mapping/SLAM; auto-enable when those run.
        need_depth = (
            config.camera.align_depth
            or config.services.map_generator
            or config.services.rtabmap_slam
        )
        if need_depth:
            camera_cmd.append("--enable-depth")
        if config.camera.flip_180:
            camera_cmd.append("--flip-180")
        services.append(
            Service(
                name="realsense_d415",
                command=camera_cmd,
                cwd=workspace_root,
                use_process_group=True,
            )
        )
        # Correct 3D / point-cloud frames when the camera is mounted upside down.
        if config.camera.flip_180:
            c = config.camera
            mount_tf_cmd = [
                "ros2", "run", "tf2_ros", "static_transform_publisher",
                str(c.mount_tf_x),
                str(c.mount_tf_y),
                str(c.mount_tf_z),
                str(c.mount_tf_yaw),
                str(c.mount_tf_pitch),
                str(c.mount_tf_roll),
                c.mount_tf_parent,
                c.mount_tf_child,
            ]
            services.append(
                Service(
                    name="camera_mount_tf",
                    command=mount_tf_cmd,
                    cwd=workspace_root,
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

        if config.perception.process_every_n > 1:
            perception_cmd.extend([
                "--process-every-n", str(config.perception.process_every_n),
            ])

        perception_cmd.extend([
            "--detection_model_name", config.perception.detection_model_name,
        ])
        
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
