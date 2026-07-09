"""
头颈舵机语音控制 Skill (通过 ROS2 /head_cmd 话题)
- 加载 YAML 配置（关键词 → 动作映射）
- 匹配语音文本 → 发布 /head_cmd 话题
- 与 chassis_ros_node 共享串口, 无需直接打开 /dev/ttyACM0
"""

import os
import subprocess
import shlex
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from loguru import logger

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"

ROS2_SETUP = "/opt/ros/humble/setup.bash"


class ServoControlSkill:
    def __init__(self):
        self.actions: List[dict] = []
        self.keyword_map: dict = {}
        self._load_config()

    def _load_config(self):
        if not _CONFIG_PATH.is_file():
            logger.warning(f"[ServoSkill] Config not found: {_CONFIG_PATH}")
            return

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "actions" not in config:
            logger.warning("[ServoSkill] No actions defined in config")
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
                        f"[ServoSkill] "
                        f"'{kw}' "
                        f"'{dup['name']}' 和 '{action['name']}' "
                    )
                self.keyword_map[kw] = action
        logger.info(f"[ServoSkill] 已加载 {len(self.actions)} 个动作, "
                     f"{len(self.keyword_map)} 个关键词")

    def _validate(self):
        for action in self.actions:
            name = action.get("name", "?")
            atype = action.get("type", "?")
            if atype != "servo":
                raise ValueError(f"[ServoSkill] 动作 '{name}' type 无效: {atype}")
            if not action.get("action"):
                raise ValueError(f"[ServoSkill] 动作 '{name}' 未配置 action")
            if not action.get("keywords"):
                raise ValueError(f"[ServoSkill] 动作 '{name}' 未配置关键词")

    def init_center(self) -> Tuple[bool, str]:
        """开机自动回零: 通过 /head_cmd 话题发送 center_all"""
        return self._publish_head_cmd("center_all")

    def match(self, text: str) -> Optional[dict]:
        for kw, action in self.keyword_map.items():
            if kw in text:
                logger.info(f"[ServoSkill] 匹配关键词 '{kw}' → 动作 '{action['name']}'")
                return action
        return None

    def execute(self, action: dict) -> Tuple[bool, str]:
        name = action.get("name", "")
        action_id = action.get("action", "")
        logger.info(f"[ServoSkill] 执行动作 '{name}': {action_id}")
        return self._publish_head_cmd(action_id)

    def _publish_head_cmd(self, action: str) -> Tuple[bool, str]:
        """通过 ros2 topic pub 发送 /head_cmd"""
        cmd = (
            f"bash -c '"
            f"source {shlex.quote(ROS2_SETUP)} && "
            f"ros2 topic pub --once /head_cmd std_msgs/msg/String "
            f"\"{{data: '{action}'}}\" 2>&1'"
        )
        logger.info(f"[ServoSkill] 发布 /head_cmd: {action}")

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
                logger.info(f"[ServoSkill] 动作 '{action}' 已发送")
                return True, f"已执行 {action}"
            else:
                logger.error(f"[ServoSkill] 发送失败 '{action}': {output}")
                return False, f"{action} 发送失败: {output}"
        except subprocess.TimeoutExpired:
            return False, f"{action} 超时"
        except Exception as e:
            logger.error(f"[ServoSkill] 异常 '{action}': {e}")
            return False, f"{action} 异常: {e}"
