"""
机械臂语音控制 Skill
- 加载 YAML 配置文件（关键词 → 动作映射）
- 自动校验关键词去重
- 匹配语音文本 → 执行 ROS2 轨迹播放 / 归零命令
- 通过 stdout 消息判定执行完成，不等进程退出
"""

import os
import signal
import subprocess
import threading
import shlex
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from loguru import logger

_SKILL_DIR = Path(__file__).parent
_CONFIG_PATH = _SKILL_DIR / "config.yaml"
_HOME_SCRIPT = os.path.expanduser("~/ros2_ws/src/openarm_teleop/script/goto_home.py")
_PLAY_SCRIPT = os.path.expanduser("~/ros2_ws/src/openarm_teleop/script/play_joint_trajectory.py")

ROS2_SETUP = "/opt/ros/humble/setup.bash"
WS_SETUP = os.path.expanduser("~/ros2_ws/install/setup.bash")


def _resolve_path(path_str: str) -> str:
    return os.path.expanduser(path_str)


class ArmControlSkill:
    def __init__(self):
        self.actions: List[dict] = []
        self.keyword_map: Dict[str, dict] = {}
        self._last_process: Optional[subprocess.Popen] = None
        self._last_node_name: Optional[str] = None
        self._process_lock = threading.Lock()
        self._load_config()

    def _load_config(self):
        if not _CONFIG_PATH.is_file():
            logger.warning(f"[ArmSkill] Config not found: {_CONFIG_PATH}")
            return

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "actions" not in config:
            logger.warning("[ArmSkill] No actions defined in config")
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
                        f"[ArmSkill] 关键词冲突: "
                        f"'{kw}' 同时出现在动作 '{dup['name']}' 和 '{action['name']}' 中"
                    )
                self.keyword_map[kw] = action
        logger.info(f"[ArmSkill] 已加载 {len(self.actions)} 个动作, "
                     f"{len(self.keyword_map)} 个关键词")

    def _validate(self):
        for action in self.actions:
            name = action.get("name", "?")
            atype = action.get("type", "?")
            if atype not in ("trajectory", "home"):
                raise ValueError(f"[ArmSkill] 动作 '{name}' type 无效: {atype}")
            if atype == "trajectory":
                files = action.get("files", [])
                if not files:
                    raise ValueError(f"[ArmSkill] 动作 '{name}' type=trajectory 但未配置 files")
                for f in files:
                    resolved = _resolve_path(f)
                    if not Path(resolved).is_file():
                        raise FileNotFoundError(
                            f"[ArmSkill] 动作 '{name}' 文件不存在: {resolved}"
                        )
            if not action.get("keywords"):
                raise ValueError(f"[ArmSkill] 动作 '{name}' 未配置关键词")

    def match(self, text: str) -> Optional[dict]:
        for kw, action in self.keyword_map.items():
            if kw in text:
                logger.info(f"[ArmSkill] 匹配关键词 '{kw}' → 动作 '{action['name']}'")
                return action
        return None

    def execute(self, action: dict) -> Tuple[bool, str]:
        name = action.get("name", "")
        atype = action.get("type", "")

        if atype == "home":
            return self._exec_home(name)
        elif atype == "trajectory":
            return self._exec_trajectory(name, action.get("files", []),
                                         action.get("speed", 1.0),
                                         action.get("start_time", 0.0))
        else:
            return False, f"未知动作类型: {atype}"

    def _exec_home(self, name: str) -> Tuple[bool, str]:
        if not Path(_HOME_SCRIPT).is_file():
            return False, f"归零脚本不存在: {_HOME_SCRIPT}"

        cmd = (
            f"bash -c '"
            f"source {shlex.quote(ROS2_SETUP)} && "
            f"source {shlex.quote(WS_SETUP)} && "
            f"python3 {shlex.quote(_HOME_SCRIPT)} --no-hold'"
        )
        return self._run_command(cmd, name, "goto_home")

    def _exec_trajectory(self, name: str, files: List[str],
                         speed: float, start_time: float = 0.0) -> Tuple[bool, str]:
        if not files:
            return False, f"动作 '{name}' 未配置轨迹文件"

        ok, msg = self._exec_home("自动归零")
        if not ok:
            return False, f"归零失败: {msg}"

        resolved_files = [_resolve_path(f) for f in files]
        for f in resolved_files:
            if not Path(f).is_file():
                return False, f"轨迹文件不存在: {f}"

        files_arg = " ".join(shlex.quote(f) for f in resolved_files)
        start_arg = f"--start-time {start_time}" if start_time > 0 else ""

        cmd = (
            f"bash -c '"
            f"source {shlex.quote(ROS2_SETUP)} && "
            f"source {shlex.quote(WS_SETUP)} && "
            f"python3 {shlex.quote(_PLAY_SCRIPT)} "
            f"--input {files_arg} --speed {speed} {start_arg} --no-hold'"
        )
        return self._run_command(cmd, name, "joint_trajectory_player")

    def _kill_last_process(self):
        proc = None
        node_name = None
        with self._process_lock:
            proc = self._last_process
            node_name = self._last_node_name
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        pass
            self._last_process = None
            self._last_node_name = None

        if node_name:
            self._wait_nodes_gone([node_name])

    def _run_command(self, cmd: str, name: str, node_name: str) -> Tuple[bool, str]:
        self._kill_last_process()

        logger.info(f"[ArmSkill] 执行动作 '{name}': {cmd[:120]}...")

        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,
            )
            with self._process_lock:
                self._last_process = proc
                self._last_node_name = node_name

            completed = False
            error_msg = ""

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                logger.debug(f"[ArmSkill] [{name}] {line[:200]}")

                if "播放完成" in line or "已到位" in line:
                    completed = True
                    break

                if line.startswith("❌") or "Error" in line or "error" in line:
                    error_msg = line[:200]

            if completed:
                logger.info(f"[ArmSkill] 动作 '{name}' 完成")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                self._wait_nodes_gone([node_name])
                return True, f"已执行 {name}"

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

            if error_msg:
                logger.error(f"[ArmSkill] 动作 '{name}' 失败: {error_msg}")
                return False, f"{name} 执行失败: {error_msg}"
            else:
                return False, f"{name} 未检测到完成信号"

        except Exception as e:
            logger.error(f"[ArmSkill] 动作 '{name}' 异常: {e}")
            return False, f"{name} 异常: {e}"

    def _ros2_node_list(self) -> List[str]:
        cmd = (
            f"bash -c '"
            f"source {shlex.quote(ROS2_SETUP)} && "
            f"ros2 node list 2>/dev/null'"
        )
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=5
            )
            return [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
        except Exception:
            return []

    def _wait_nodes_gone(self, node_names: List[str], timeout_limit: float = 10.0) -> bool:
        remaining = set(node_names)
        deadline = time.time() + timeout_limit
        while remaining and time.time() < deadline:
            current = self._ros2_node_list()
            still_alive = set()
            for node in remaining:
                if any(node in cn for cn in current):
                    still_alive.add(node)
            remaining = still_alive
            if remaining:
                logger.debug(f"[ArmSkill] 等待节点消失: {remaining}")
                time.sleep(1)
        if remaining:
            logger.warning(f"[ArmSkill] 节点超时未消失: {remaining}")
            return False
        return True


def validate_config(path: Optional[str] = None) -> Tuple[bool, str]:
    """独立校验 config.yaml, 供命令行工具使用"""
    config_path = Path(path) if path else _CONFIG_PATH
    try:
        ArmControlSkill()
        return True, "配置校验通过"
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    skill = ArmControlSkill()
    print(f"已加载 {len(skill.actions)} 个动作, {len(skill.keyword_map)} 个关键词")
    # 交互测试
    while True:
        try:
            text = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        action = skill.match(text)
        if action:
            print(f"  → 匹配: {action['name']}")
            ok, msg = skill.execute(action)
            print(f"  → 结果: {msg}")
        else:
            print("  → 未匹配")
