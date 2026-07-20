# 机械臂语音控制 Skill

## 概述

通过语音关键词控制 OpenARM 机械臂执行预录制的运动轨迹。

**工作链路：** 语音 → ASR 转写 → **关键词匹配** → ROS2 执行轨迹 → TTS 反馈

## 文件结构

```
skills/arm_control/
├── config.yaml    # 动作配置（关键词 ←→ 轨迹文件映射）
├── skill.py       # 匹配逻辑 + 执行引擎
└── README.md      # 本文档
```

## 如何添加新动作

### 1. 准备轨迹文件

将 `.json` 轨迹文件放入 `~/action/` 目录。

### 2. 编辑 config.yaml

在 `actions:` 列表末尾添加：

```yaml
  - name: "动作名称"          # 唯一标识，用于反馈提示
    keywords:                  # 关键词列表，任意一个命中即可触发
      - 关键词1
      - 关键词2
      - 关键词3
    type: trajectory           # trajectory（播放轨迹）或 home（归零）
    files:                     # type=trajectory 时必填
      - ~/action/xxx.json      # 单个文件 = 单文件播放
    speed: 1.0                 # 可选，播放速度倍率，默认 1.0
```

### 3. 多文件连播

```yaml
    files:
      - ~/action/step1.json
      - ~/action/step2.json
      - ~/action/step3.json
    # 自动按顺序依次播放
```

### 4. 归零动作

```yaml
  - name: "归零"
    keywords: [归零, 复位]
    type: home                  # 不需要 files 字段
```

### 5. 验证

启动服务时会自动校验：
- 所有关键词是否唯一（重复会报错并列出冲突）
- 轨迹文件是否存在
- type 参数是否有效

## 完整示例

```yaml
actions:
  - name: "抬手"
    keywords: [抬手, 举手, 抬起手, 抬胳膊]
    type: trajectory
    files:
      - ~/action/tai_shou_R.json

  - name: "挥手"
    keywords: [挥手, 摇手, 摆摆手]
    type: trajectory
    files:
      - ~/action/wave_L.json
      - ~/action/wave_R.json

  - name: "归零"
    keywords: [回原点, 机械臂复位, 全部归位]
    type: home
```

## 关键词规则

1. **不区分大小写**（中文无需考虑）
2. **子串匹配**：语音含「把手抬起来」时，如果关键词是「抬手」也会匹配
3. **每个关键词只能属于一个动作**，提交前系统自动检测重复
4. **建议每个动作 8-15 个关键词**，覆盖常用说法和方言习惯

## 依赖脚本

| 脚本 | 路径 |
|------|------|
| 轨迹播放 | `~/ros2_ws/src/openarm_teleop/script/play_joint_trajectory.py` |
| 机械臂归零 | `~/ros2_ws/src/openarm_teleop/script/goto_home.py` |

## 调试

```bash
# 启动 chatbot 服务，动作匹配日志会输出到 chatbot 日志
tail -f ~/logs/chatbot.log | grep ArmSkill

# 独立测试 Skill
cd ~/dorabot_ws/src/chatbot
python3 skills/arm_control/skill.py
# 输入关键词测试匹配
```
