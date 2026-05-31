#!/usr/bin/env bash
# =============================================================================
# Install ROS 2 Humble + perception ROS dependencies on Orange Pi 5 (RK3588S)
# Ubuntu 22.04 (jammy), arm64.
#
# RUN THIS ON THE ROBOT with a sudo-capable user (it will prompt for password):
#
#     bash ~/dorabot_ws/scripts/install_ros2_humble.sh
#
# It is idempotent: safe to re-run. It does NOT build librealsense or the
# realsense2_camera ROS wrapper (no arm64 apt binaries exist for them and the
# source build is heavy). Instead the camera is published to ROS by a small
# pyrealsense2-backed node (see src/perception/.../realsense_publisher_node.py),
# whose Python deps are installed by scripts/setup_perception_env.sh.
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[install]${NC} $*"; }
warn() { echo -e "${YELLOW}[install]${NC} $*"; }
err()  { echo -e "${RED}[install]${NC} $*" >&2; }

if [[ "${EUID}" -eq 0 ]]; then
    err "Do NOT run this as root/sudo directly. Run as your normal user; it calls sudo itself."
    exit 1
fi

# --- sanity checks ----------------------------------------------------------
. /etc/os-release
CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
ARCH="$(dpkg --print-architecture)"
log "Detected Ubuntu '${CODENAME}' on '${ARCH}'."
if [[ "${CODENAME}" != "jammy" ]]; then
    warn "Expected jammy (22.04). Continuing anyway, but ROS 2 Humble targets jammy."
fi

ROS_DISTRO=humble
# Set INSTALL_DESKTOP=1 to also get rviz2 + demos (heavier). Default: ros-base.
INSTALL_DESKTOP="${INSTALL_DESKTOP:-0}"

log "Updating apt and base prerequisites..."
sudo apt-get update
sudo apt-get install -y software-properties-common curl gnupg lsb-release ca-certificates
sudo add-apt-repository -y universe

# --- ROS 2 apt repository (new ros2-apt-source deb method) -------------------
if ! dpkg -s ros2-apt-source >/dev/null 2>&1; then
    log "Installing ros2-apt-source repository package..."
    ROS_APT_SOURCE_VERSION="$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
        | grep -F 'tag_name' | awk -F'"' '{print $4}')"
    if [[ -z "${ROS_APT_SOURCE_VERSION}" ]]; then
        err "Could not determine ros-apt-source latest version (network/GitHub API issue)."
        exit 1
    fi
    log "  ros-apt-source version: ${ROS_APT_SOURCE_VERSION}"
    curl -L -o /tmp/ros2-apt-source.deb \
        "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${CODENAME}_all.deb"
    sudo dpkg -i /tmp/ros2-apt-source.deb
else
    log "ros2-apt-source already installed; skipping."
fi

log "Updating apt with ROS repo enabled..."
sudo apt-get update

# --- ROS 2 packages ----------------------------------------------------------
PKGS=(
    "ros-${ROS_DISTRO}-ros-base"
    "ros-${ROS_DISTRO}-cv-bridge"
    "ros-${ROS_DISTRO}-image-transport"
    "ros-${ROS_DISTRO}-vision-msgs"
    "ros-dev-tools"
    "python3-colcon-common-extensions"
    "python3-rosdep"
    "build-essential"
)
if [[ "${INSTALL_DESKTOP}" == "1" ]]; then
    log "INSTALL_DESKTOP=1 -> adding ros-${ROS_DISTRO}-desktop (rviz2, demos)."
    PKGS+=("ros-${ROS_DISTRO}-desktop")
fi

log "Installing: ${PKGS[*]}"
sudo apt-get install -y "${PKGS[@]}"

# --- rosdep ------------------------------------------------------------------
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
    log "Initializing rosdep..."
    sudo rosdep init
fi
log "Updating rosdep database (as normal user)..."
rosdep update || warn "rosdep update failed (non-fatal); you can re-run it later."

# --- shell convenience -------------------------------------------------------
SETUP_LINE="source /opt/ros/${ROS_DISTRO}/setup.bash"
if ! grep -qF "${SETUP_LINE}" "${HOME}/.bashrc" 2>/dev/null; then
    log "Adding ROS 2 sourcing to ~/.bashrc"
    {
        echo ""
        echo "# ROS 2 ${ROS_DISTRO} (added by install_ros2_humble.sh)"
        echo "${SETUP_LINE}"
    } >> "${HOME}/.bashrc"
else
    log "~/.bashrc already sources ROS 2; skipping."
fi

# --- verify ------------------------------------------------------------------
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO}/setup.bash"
log "ROS 2 installed. ros2 version:"
ros2 --version || true

cat <<EOF

${GREEN}=============================================================${NC}
 ROS 2 ${ROS_DISTRO} base install complete.
${GREEN}=============================================================${NC}

 Next steps (no sudo needed):

   1) Open a NEW terminal (so ROS 2 is sourced), or run:
        source /opt/ros/${ROS_DISTRO}/setup.bash

   2) Create the perception/orchestrator Python env:
        bash ~/dorabot_ws/scripts/setup_perception_env.sh

   3) Sanity check rclpy is visible:
        python3 -c "import rclpy; print('rclpy OK')"

EOF
