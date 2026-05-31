import sys
import numpy as np
import pyrealsense2 as rs

ctx = rs.context()
devs = ctx.query_devices()
print(f"devices found: {len(devs)}")
for d in devs:
    print("  -", d.get_info(rs.camera_info.name), d.get_info(rs.camera_info.serial_number))

if len(devs) == 0:
    print("NO DEVICE")
    sys.exit(2)

pipe = rs.pipeline()
cfg = rs.config()
cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
profile = pipe.start(cfg)
print("pipeline started")
for i in range(5):
    frames = pipe.wait_for_frames(5000)
    color = frames.get_color_frame()
    depth = frames.get_depth_frame()
    img = np.asanyarray(color.get_data())
    print(f"frame {i}: color shape={img.shape} dtype={img.dtype}, depth={depth.get_width()}x{depth.get_height()}, mean_px={img.mean():.1f}")
pipe.stop()
print("OK_CAMERA_STREAM")
