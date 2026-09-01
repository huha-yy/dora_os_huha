# scservo_sdk（飞特 FEETECH 舵机 SDK）— 仓库内置副本

飞特官方 SCServo SDK（SMS_STS / SCSCL 协议），驱动 ST3215（轮子）与 ST3250（头颈）舵机。

- **收编日期**：2026-09-01
- **来源**：团队调试副本 `D:\code\robot\底盘\scservo_sdk`（与 `手臂\scservo_sdk` 逐字节一致）
- **相对官方 2022 版的本地修改**：`port_handler.py`（2025-05）、`scservo_def.py`（2026-01）有团队改动，**以本目录为唯一事实源**，不要再从官网重新下载覆盖

## 加载方式

- `src/chassis/chassis_ros_node.py` 自动查找：优先仓库内 `board/ST32XX/`，找不到再退回机器人旧布局 `~/ST32XX`
- `board/ST32XX/*.py`（servo_action / dual_control）与 `tools/arm_debug/scan.py`、`change_id.py` 已配置为本目录
- 新板子部署：clone 仓库即可，无需手动拷贝 `~/ST32XX`；仅需系统装有 pyserial（回退通道用）
