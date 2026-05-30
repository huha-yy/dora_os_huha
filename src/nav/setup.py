from setuptools import find_packages, setup
from glob import glob
import os

package_name = "nav"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="frank",
    maintainer_email="frank123111@gmail.com",
    description="Dorabot navigation package",
    license="Proprietary",
    data_files=[
        # This registers the package with ROS2 so `ros2 run` can find it
        (
            "share/ament_index/resource_index/packages",
            [os.path.join("resource", package_name)],
        ),
        ("share/" + package_name, ["package.xml"]),
        # Install ament_prefix_path hooks so ROS2 can find this package
        (os.path.join("share", package_name, "hook"), glob("hook/ament_prefix_path.*")),
        (os.path.join("share", package_name), ["hook/package.dsv"]),
        # Install launch/config files into share/nav/...
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*")),
        (os.path.join("share", package_name, "params"), glob("params/*")),
    ],
    entry_points={
        "console_scripts": [
            "dorabot_autonomy = orchestrator.autonomy_node:main",
            "map_generator = mapping.map_generator:main",
            "map_manager = mapping.map_manager:main",
        ],
    },
)
