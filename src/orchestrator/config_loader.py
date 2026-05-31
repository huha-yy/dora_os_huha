# orchestrator/config_loader.py
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    """Service enable/disable flags."""
    ai_agent: bool = True
    realsense_camera: bool = True
    perception: bool = True
    map_generator: bool = False
    map_manager: bool = False
    rtabmap_slam: bool = False
    nav2_navigation: bool = False


@dataclass
class PerceptionConfig:
    """Perception service configuration."""
    debug_video_path: Optional[str] = None
    print_fps: bool = False
    # Run YOLO + pose every N-th camera frame (1 = every frame).
    process_every_n: int = 1
    # RKNN model dir under src/perception/models/, or a .pt file for CPU fallback.
    detection_model_name: str = "yolo11n_rknn_model"


@dataclass
class CameraConfig:
    """Camera configuration."""
    align_depth: bool = True
    width: int = 640
    height: int = 480
    fps: int = 30
    # D415 mounted upside down: rotate images 180° and publish a mount TF.
    flip_180: bool = True
    mount_tf_parent: str = "base_link"
    mount_tf_child: str = "camera_link"
    # static_transform_publisher args: x y z yaw pitch roll (radians)
    mount_tf_x: float = 0.0
    mount_tf_y: float = 0.0
    mount_tf_z: float = 0.0
    mount_tf_yaw: float = 3.14159
    mount_tf_pitch: float = 0.0
    mount_tf_roll: float = 0.0


@dataclass
class MappingConfig:
    """Mapping service configuration."""
    config_file: str = "src/nav/config/map_generator.yaml"


@dataclass
class MapManagerConfig:
    """Map manager configuration."""
    config_file: str = "src/nav/config/map_manager.yaml"


@dataclass
class RTABMapConfig:
    """RTAB-Map SLAM configuration."""
    rgb_topic: str = "/camera/camera/color/image_raw"
    depth_topic: str = "/camera/camera/aligned_depth_to_color/image_raw"
    camera_info_topic: str = "/camera/camera/color/camera_info"
    approx_sync: bool = True
    frame_id: str = "camera_link"


@dataclass
class OrchestratorConfig:
    """Complete orchestrator configuration."""
    language: str = "zh"
    orchestrator_port: int = 8080
    services: ServiceConfig = field(default_factory=ServiceConfig)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    map_manager: MapManagerConfig = field(default_factory=MapManagerConfig)
    rtabmap: RTABMapConfig = field(default_factory=RTABMapConfig)


def load_config(config_path: str) -> OrchestratorConfig:
    """
    Load orchestrator configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        OrchestratorConfig object
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        yaml_data = yaml.safe_load(f)
    
    if yaml_data is None:
        yaml_data = {}
    
    # Parse service configuration
    services_data = yaml_data.get('services', {})
    services = ServiceConfig(
        ai_agent=services_data.get('ai_agent', True),
        realsense_camera=services_data.get('realsense_camera', True),
        perception=services_data.get('perception', True),
        map_generator=services_data.get('map_generator', False),
        map_manager=services_data.get('map_manager', False),
        rtabmap_slam=services_data.get('rtabmap_slam', False),
        nav2_navigation=services_data.get('nav2_navigation', False),
    )
    
    # Parse perception configuration
    perception_data = yaml_data.get('perception', {})
    perception = PerceptionConfig(
        debug_video_path=perception_data.get('debug_video_path'),
        print_fps=perception_data.get('print_fps', False),
        process_every_n=int(perception_data.get('process_every_n', 1)),
        detection_model_name=perception_data.get(
            'detection_model_name', 'yolo11n_rknn_model'
        ),
    )
    
    # Parse camera configuration
    camera_data = yaml_data.get('camera', {})
    camera = CameraConfig(
        align_depth=camera_data.get('align_depth', True),
        width=int(camera_data.get('width', 640)),
        height=int(camera_data.get('height', 480)),
        fps=int(camera_data.get('fps', 30)),
        flip_180=camera_data.get('flip_180', True),
        mount_tf_parent=camera_data.get('mount_tf_parent', 'base_link'),
        mount_tf_child=camera_data.get('mount_tf_child', 'camera_link'),
        mount_tf_x=float(camera_data.get('mount_tf_x', 0.0)),
        mount_tf_y=float(camera_data.get('mount_tf_y', 0.0)),
        mount_tf_z=float(camera_data.get('mount_tf_z', 0.0)),
        mount_tf_yaw=float(camera_data.get('mount_tf_yaw', 3.14159)),
        mount_tf_pitch=float(camera_data.get('mount_tf_pitch', 0.0)),
        mount_tf_roll=float(camera_data.get('mount_tf_roll', 0.0)),
    )
    
    # Parse mapping configuration
    mapping_data = yaml_data.get('mapping', {})
    mapping = MappingConfig(
        config_file=mapping_data.get('config_file', 'src/nav/config/map_generator.yaml'),
    )
    
    # Parse map manager configuration
    map_manager_data = yaml_data.get('map_manager', {})
    map_manager = MapManagerConfig(
        config_file=map_manager_data.get('config_file', 'src/nav/config/map_manager.yaml'),
    )
    
    # Parse RTAB-Map configuration
    rtabmap_data = yaml_data.get('rtabmap', {})
    rtabmap = RTABMapConfig(
        rgb_topic=rtabmap_data.get('rgb_topic', '/camera/camera/color/image_raw'),
        depth_topic=rtabmap_data.get('depth_topic', '/camera/camera/aligned_depth_to_color/image_raw'),
        camera_info_topic=rtabmap_data.get('camera_info_topic', '/camera/camera/color/camera_info'),
        approx_sync=rtabmap_data.get('approx_sync', True),
        frame_id=rtabmap_data.get('frame_id', 'camera_link'),
    )
    
    # Create complete configuration
    config = OrchestratorConfig(
        language=yaml_data.get('language', 'zh'),
        orchestrator_port=yaml_data.get('orchestrator_port', 8080),
        services=services,
        perception=perception,
        camera=camera,
        mapping=mapping,
        map_manager=map_manager,
        rtabmap=rtabmap,
    )
    
    return config


def get_default_config_path() -> str:
    """Get the default configuration file path."""
    # Get absolute path and work from there
    script_dir = Path(__file__).parent.resolve()
    
    # Try new location: configs/orchestrator/config.yaml
    # Navigate up from src/orchestrator to workspace root
    workspace_root = script_dir.parent.parent
    new_config = workspace_root / "configs" / "orchestrator" / "config.yaml"
    
    if new_config.exists():
        return str(new_config)
    
    # Fall back to old location for backward compatibility
    old_config = script_dir / "config.yaml"
    
    if old_config.exists():
        return str(old_config)
    
    raise FileNotFoundError(
        "No default configuration file found. "
        "Expected: configs/orchestrator/config.yaml or src/orchestrator/config.yaml"
    )


def list_available_configs() -> list[str]:
    """List all available configuration files."""
    # Get absolute path and work from there
    script_dir = Path(__file__).parent.resolve()
    
    # Look in configs directory first (new location)
    # Navigate up from src/orchestrator to workspace root
    workspace_root = script_dir.parent.parent
    configs_dir = workspace_root / "configs" / "orchestrator"
    
    if configs_dir.exists() and configs_dir.is_dir():
        configs = list(configs_dir.glob("config*.yaml"))
        if configs:
            return [f"configs/orchestrator/{c.name}" for c in sorted(configs)]
    
    # Fall back to old location
    configs = list(script_dir.glob("config*.yaml"))
    return [f"src/orchestrator/{c.name}" for c in sorted(configs)]
