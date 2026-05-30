# orchestrator/main.py
import os
import sys
import threading
from pathlib import Path
from typing import Optional

# Add src to path to enable absolute imports when running as script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click
import uvicorn

from orchestrator.services.manager import ServiceManager
from orchestrator.services.specs import build_services
from orchestrator.web_server.app import create_app
from orchestrator.ros_node import start_ros_node, stop_ros_node
from orchestrator.config_loader import load_config, get_default_config_path, list_available_configs



def print_config_summary(config) -> None:
    """Print configuration summary."""
    print("\n" + "="*60)
    print("         Dorabot Orchestrator Configuration")
    print("="*60)
    print(f"  Language: {config.language}")
    print(f"  Port: {config.orchestrator_port}")
    print("\n  Core Services:")
    print(f"    - AI Agent: {'✓' if config.services.ai_agent else '✗'}")
    print(f"    - RealSense Camera: {'✓' if config.services.realsense_camera else '✗'}")
    print(f"    - Perception: {'✓' if config.services.perception else '✗'}")
    
    # Show venv status if set
    if os.environ.get('VIRTUAL_ENV'):
        print(f"\n  Virtual Environment: {os.environ['VIRTUAL_ENV']}")
    
    nav_enabled = any([
        config.services.map_generator,
        config.services.map_manager,
        config.services.rtabmap_slam,
        config.services.nav2_navigation
    ])
    
    if nav_enabled:
        print("\n  Navigation Services:")
        print(f"    - Map Generator: {'✓' if config.services.map_generator else '✗'}")
        print(f"    - Map Manager: {'✓' if config.services.map_manager else '✗'}")
        print(f"    - RTAB-Map SLAM: {'✓' if config.services.rtabmap_slam else '✗'}")
        print(f"    - Nav2 Navigation: {'✓' if config.services.nav2_navigation else '✗'}")
    else:
        print("\n  Navigation Services: ✗ Disabled")
    
    print("="*60 + "\n")


@click.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True),
    help="Path to configuration file (default: configs/orchestrator/config.yaml)"
)
@click.option(
    "--list-configs",
    is_flag=True,
    help="List available configuration files and exit"
)
@click.option(
    "--skip-sub-services",
    is_flag=True,
    help="Skip starting sub-services (API server only)",
    default=False
)
def main(
    config: Optional[str],
    list_configs: bool,
    skip_sub_services: bool,
) -> None:
    """
    Entry point for Dorabot Orchestrator.
    
    The orchestrator uses configuration files to determine which services to start.
    Use --config to specify a custom config file, or use one of the presets:
    
    - config.yaml: Basic mode (core services only)
    - config_mapping.yaml: With custom mapping
    - config_slam.yaml: With RTAB-Map SLAM
    - config_full.yaml: Full navigation suite
    
    Examples:
        # Default configuration (basic mode)
        python src/orchestrator/main.py
        
        # With mapping
        python src/orchestrator/main.py -c configs/orchestrator/config_mapping.yaml
        
        # With SLAM
        python src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml
        
        # Full suite
        python src/orchestrator/main.py -c configs/orchestrator/config_full.yaml
        
        # List available configs
        python src/orchestrator/main.py --list-configs
    """
    # List available configs and exit
    if list_configs:
        print("\nAvailable configuration files:")
        for cfg in list_available_configs():
            print(f"  - {cfg}")
        print("\nUse with: python src/orchestrator/main.py -c <config_file>")
        print("Example: python src/orchestrator/main.py -c configs/orchestrator/config_full.yaml")
        return
    
    # Load configuration
    if config is None:
        try:
            config_path = get_default_config_path()
            print(f"[orchestrator] Using default configuration: {config_path}")
        except FileNotFoundError:
            print("[orchestrator] Error: No default configuration found!")
            print("[orchestrator] Please specify a config file with --config")
            sys.exit(1)
    else:
        config_path = config
        print(f"[orchestrator] Loading configuration: {config_path}")
    
    try:
        cfg = load_config(config_path)
    except Exception as e:
        print(f"[orchestrator] Error loading configuration: {e}")
        sys.exit(1)
    
    if not skip_sub_services:
        # Print configuration summary
        print_config_summary(cfg)
        
        # 1) Build and start services
        services = build_services(cfg)
        service_manager = ServiceManager(services)

        service_manager.start_all()

        # 2) Start monitoring loop in background thread
        monitor_thread = threading.Thread(
            target=service_manager.run_forever, daemon=True
        )
        monitor_thread.start()
    else:
        print(
            "[orchestrator] Sub-services not started. As --skip-sub-services flag is set."
        )
        service_manager = None

    # 3) Run HTTP server (FastAPI) in main thread
    #    Import app directly to avoid import path conflicts with standard library 'http' module
    ros_node = None
    ros_thread = None
    try:
        # 4) Start ROS node in background thread
        ros_node, ros_thread = start_ros_node()

        # Load config for port (if not already loaded)
        if 'cfg' not in locals():
            cfg = load_config(get_default_config_path())
        
        app = create_app()
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=cfg.orchestrator_port,
            reload=False,
        )
    finally:
        # When HTTP server stops (Ctrl+C), stop all services and ROS node.
        stop_ros_node(ros_node)
        if service_manager is not None:
            service_manager.stop_all()


if __name__ == "__main__":
    main()
