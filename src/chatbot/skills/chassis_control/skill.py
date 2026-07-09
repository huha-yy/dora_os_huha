"""
底盘语音控制 Skill (通过 ROS2 /cmd_vel 话题)
- 加载 YAML 配置（关键词 → 动作映射）
- 匹配语音文本 → 发布 /cmd_vel 话题
- 短暂移动后自动停止 (安全设计: 不会一直走)
"""

import subprocess
import shlex
import time
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from loguru import logger

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"

ROS2_SETUP = "/opt/ros/humble/setup.bash"


class ChassisControlSkill:
    def __init__(self):
        self.actions: List[dict] = []
        self.keyword_map: dict = {}
        self._load_config()

    def _load_config(self):
        if not _CONFIG_PATH.is_file():
            logger.warning(f"[ChassisSkill] Config not found: {_CONFIG_PATH}")
            return

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "actions" not in config:
            logger.warning("[ChassisSkill] No actions defined in config")
            return

        self.actions = config["actions"]
        self._build_keyword_map()
        self._validate()

    def _build_keyword_map(self):
        self.keyword_map.clear()
        for action in self.actions:
            for kw in action.get("keywords", []):
                if kw in self.keyword_map:
                    dup = self.keyword_map[kw]
                    raise ValueError(
                        f"[ChassisSkill] 关键词冲突: "
                        f"'{kw}' 同时出现在 '{dup['name']}' 和 '{action['name']}'"
                    )
                self.keyword_map[kw] = action
        logger.info(f"[ChassisSkill] 已加载 {len(self.actions)} 个动作, "
                     f"{len(self.keyword_map)} 个关键词")

    def _validate(self):
        for action in self.actions:
            name = action.get("name", "?")
            atype = action.get("type", "?")
            if atype != "chassis_move":
                raise ValueError(f"[ChassisSkill] 动作 '{name}' type 无效: {atype}")
            if not action.get("keywords"):
                raise ValueError(f"[ChassisSkill] 动作 '{name}' 未配置关键词")

    def match(self, text: str) -> Optional[dict]:
        for kw, action in self.keyword_map.items():
            if kw in text:
                logger.info(f"[ChassisSkill] 匹配关键词 '{kw}' → 动作 '{action['name']}'")
                return action
        return None

    def execute(self, action: dict) -> Tuple[bool, str]:
        name = action.get("name", "")
        vx = action.get("linear_x", 0.0)
        vy = action.get("linear_y", 0.0)
        wz = action.get("angular_z", 0.0)
        duration = action.get("duration_sec", 0.0)

        twist_json = f"{{linear: {{x: {vx}, y: {vy}}}, angular: {{z: {wz}}}}}"

        if duration > 0:
            logger.info(f"[ChassisSkill] '{name}': vx={vx}, vy={vy}, wz={wz}, 持续{duration}s")
            # 发送移动指令
            ok, msg = self._publish_cmd_vel(twist_json, f"{name}(开始)")
            if not ok:
                return False, msg
            # 等待指定时间
            time.sleep(duration)
            # 自动停止
            stop_json = "{linear: {x: 0.0, y: 0.0}, angular: {z: 0.0}}"
            self._publish_cmd_vel(stop_json, f"{name}(停止)")
            return True, f"已完成 {name}"
        else:
            # 停止指令就直接停
            stop_json = "{linear: {x: 0.0, y: 0.0}, angular: {z: 0.0}}"
            return self._publish_cmd_vel(stop_json, name)

    def _publish_cmd_vel(self, twist_json: str, label: str) -> Tuple[bool, str]:
        """通过 ros2 topic pub 发送 /cmd_vel"""
        cmd = (
            f"bash -c '"
            f"source {shlex.quote(ROS2_SETUP)} && "
            f"ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "
            f"\"{twist_json}\" 2>&1'"
        )
        logger.info(f"[ChassisSkill] 发布 /cmd_vel: {label}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.strip()
            if result.returncode == 0:
                return True, f"已发送 {label}"
            else:
                logger.error(f"[ChassisSkill] 发送失败 '{label}': {output}")
                return False, f"{label} 发送失败: {output}"
        except subprocess.TimeoutExpired:
            return False, f"{label} 超时"
        except Exception as e:
            logger.error(f"[ChassisSkill] 异常 '{label}': {e}")
            return False, f"{label} 异常: {e}"
