"""
手臂舵机语音控制 Skill (通过 robot_bus 直接发布 /arm_cmd)
"""

from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from loguru import logger

from robot_bus import publish_arm_cmd

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"


class ArmServoSkill:
    def __init__(self):
        self.actions: List[dict] = []
        self.keyword_map: dict = {}
        self._load_config()

    def _load_config(self):
        if not _CONFIG_PATH.is_file():
            logger.warning(f"[ArmServoSkill] Config not found: {_CONFIG_PATH}")
            return

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "actions" not in config:
            logger.warning("[ArmServoSkill] No actions defined in config")
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
                        f"[ArmServoSkill] 关键词冲突: "
                        f"'{kw}' 同时出现在 '{dup['name']}' 和 '{action['name']}'"
                    )
                self.keyword_map[kw] = action
        logger.info(f"[ArmServoSkill] 已加载 {len(self.actions)} 个动作, "
                     f"{len(self.keyword_map)} 个关键词")

    def _validate(self):
        for action in self.actions:
            name = action.get("name", "?")
            atype = action.get("type", "?")
            if atype != "arm_preset":
                raise ValueError(f"[ArmServoSkill] 动作 '{name}' type 无效: {atype}")
            if not action.get("preset"):
                raise ValueError(f"[ArmServoSkill] 动作 '{name}' 未配置 preset")
            if not action.get("keywords"):
                raise ValueError(f"[ArmServoSkill] 动作 '{name}' 未配置关键词")

    def match(self, text: str) -> Optional[dict]:
        for kw, action in self.keyword_map.items():
            if kw in text:
                logger.info(f"[ArmServoSkill] 匹配关键词 '{kw}' → 动作 '{action['name']}'")
                return action
        return None

    def execute(self, action: dict) -> Tuple[bool, str]:
        name = action.get("name", "")
        preset = action.get("preset", "")
        logger.info(f"[ArmServoSkill] 执行 '{name}': preset={preset}")
        publish_arm_cmd(preset)
        return True, f"已执行 {name}"
