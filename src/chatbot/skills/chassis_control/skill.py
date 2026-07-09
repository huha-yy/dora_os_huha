"""
底盘语音控制 Skill (通过 robot_bus 直接发布 /cmd_vel)
- 加载 YAML 配置（关键词 → 动作映射）
- 匹配语音文本 → robot_bus.publish_cmd_vel()
- 持久 ROS2 publisher, 无 subprocess 开销
"""

import time
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from loguru import logger

from robot_bus import publish_cmd_vel

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"


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

        logger.info(f"[ChassisSkill] '{name}': vx={vx}, vy={vy}, wz={wz}, 持续{duration}s")

        # 直接调用持久 publisher (无 subprocess 开销)
        publish_cmd_vel(vx, vy, wz)

        if duration > 0:
            time.sleep(duration)
            publish_cmd_vel(0.0, 0.0, 0.0)  # 自动停止
            return True, f"已完成 {name}"
        else:
            return True, f"已执行 {name}"
