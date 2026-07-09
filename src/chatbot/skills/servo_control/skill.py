"""
头颈舵机语音控制 Skill (通过 robot_bus 直接发布 /head_cmd)
- 加载 YAML 配置（关键词 → 动作映射）
- 匹配语音文本 → robot_bus.publish_head_cmd()
- 持久 ROS2 publisher, 无 subprocess 开销
"""

from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from loguru import logger

from robot_bus import publish_head_cmd

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"


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
        """开机自动回零: 通过 robot_bus 发布 /head_cmd"""
        logger.info("[ServoSkill] 开机自动回零...")
        publish_head_cmd("center_all")
        return True, "舵机已回零"

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
        publish_head_cmd(action_id)
        return True, f"已执行 {name}"
