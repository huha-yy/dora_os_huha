#!/usr/bin/env python3

import os
import sys
import tty
import termios

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scservo_sdk import *

# ===== 舵机配置 =====
# 舵机1 (头部左右): 限位 ±90°, ID=4
SERVO1_ID       = 4
SERVO1_CENTER   = 2459
SERVO1_LIMIT    = 1024
# 舵机2 (头部俯仰): 抬头28° / 低头25°, ID=5
SERVO2_ID       = 5
SERVO2_CENTER   = 2150
SERVO2_LIMIT_UP = 319     # 28°
SERVO2_LIMIT_DOWN = 284   # 25°

SPEED  = 2400
ACC    = 50
DEVICE = '/dev/ttyACM0'
BAUD   = 1000000

positions_1 = [SERVO1_CENTER - SERVO1_LIMIT, SERVO1_CENTER, SERVO1_CENTER + SERVO1_LIMIT, SERVO1_CENTER]
positions_2 = [SERVO2_CENTER - SERVO2_LIMIT_DOWN, SERVO2_CENTER, SERVO2_CENTER + SERVO2_LIMIT_UP, SERVO2_CENTER]
idx1 = 0
idx2 = 0

portHandler = PortHandler(DEVICE)
packetHandler = sms_sts(portHandler)

if not portHandler.openPort():
    print("Failed to open port %s" % DEVICE)
    sys.exit(1)
print("Port opened: %s" % DEVICE)

if not portHandler.setBaudRate(BAUD):
    print("Failed to set baudrate %d" % BAUD)
    portHandler.closePort()
    sys.exit(1)
print("Baudrate: %d" % BAUD)

print("[开机回零] 双舵机回中...")
packetHandler.WritePosEx(SERVO1_ID, SERVO1_CENTER, SPEED, ACC)
packetHandler.WritePosEx(SERVO2_ID, SERVO2_CENTER, SPEED, ACC)
print("[开机回零] OK")

def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

print("\n===== ST3250 双舵机控制 =====")
print("  q/w : 舵机1 左/右")
print("  a/s : 舵机2 左/右")
print("  r   : 双舵机回中")
print("  空格: 双舵机归位(左极限)")
print("  ESC : 退出")
print("==============================\n")

try:
    while True:
        ch = getch()
        if ch == '\x1b':
            break
        elif ch == 'q':
            idx1 = 0
            print("[舵机1] -> 左90° pos=%d" % positions_1[0])
            packetHandler.WritePosEx(SERVO1_ID, positions_1[0], SPEED, ACC)
        elif ch == 'w':
            idx1 = 2
            print("[舵机1] -> 右90° pos=%d" % positions_1[2])
            packetHandler.WritePosEx(SERVO1_ID, positions_1[2], SPEED, ACC)
        elif ch == 'a':
            idx2 = 0
            print("[舵机2] -> 低头25° pos=%d" % positions_2[0])
            packetHandler.WritePosEx(SERVO2_ID, positions_2[0], SPEED, ACC)
        elif ch == 's':
            idx2 = 2
            print("[舵机2] -> 抬头28° pos=%d" % positions_2[2])
            packetHandler.WritePosEx(SERVO2_ID, positions_2[2], SPEED, ACC)
        elif ch == 'r':
            idx1 = 1
            idx2 = 1
            print("[双舵机] -> 回中")
            packetHandler.WritePosEx(SERVO1_ID, SERVO1_CENTER, SPEED, ACC)
            packetHandler.WritePosEx(SERVO2_ID, SERVO2_CENTER, SPEED, ACC)
        elif ch == ' ':
            idx1 = 0
            idx2 = 0
            print("[双舵机] -> 归位(左极限)")
            packetHandler.WritePosEx(SERVO1_ID, positions_1[0], SPEED, ACC)
            packetHandler.WritePosEx(SERVO2_ID, positions_2[0], SPEED, ACC)
finally:
    portHandler.closePort()
    print("Port closed.")
