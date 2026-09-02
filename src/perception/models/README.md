# 感知模块模型文件

代码从本目录加载模型（见 `src/perception/src/body_tracking/body_detector.py`），
缺文件时 **不会自动下载**，必须放在这里。

| 文件 | 用途 | 默认配置 |
|------|------|---------|
| `yolov8n.pt` | YOLO 人体检测（CPU，PyTorch） | `config.yaml` 当前默认 |
| `yolo11n.pt` | YOLO 人体检测（CPU，更新一代，备用） | 手动切换用 |
| `pose_landmarker_lite.task` | MediaPipe 姿态 33 关键点（跌倒检测依赖） | 必需，缺了节点崩溃 |

切换检测模型：改 `configs/orchestrator/config.yaml` 的 `detection_model_name`。

> 许可：yolov8n.pt / yolo11n.pt 为 AGPL-3.0（ultralytics），仅限内部私有仓库使用。
> 本目录不要放 `.rknn` 模型——那是 RK3588 专用格式，已随换板作废。
