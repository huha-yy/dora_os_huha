#!/usr/bin/env python3

import os
import sys
import time
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scservo_sdk import *

SERVO1_ID       = 4   # 头部左右
SERVO1_CENTER   = 2459
SERVO1_LIMIT    = 1024

SERVO2_ID       = 5   # 头部俯仰
SERVO2_CENTER   = 2150
SERVO2_LIMIT_UP = 319     # 28°
SERVO2_LIMIT_DOWN = 284   # 25°

SPEED  = 2400
ACC    = 50
DEVICE = '/dev/ttyACM0'
BAUD   = 1000000

ACTIONS = {
    'head_left':      (SERVO1_ID, SERVO1_CENTER - SERVO1_LIMIT),
    'head_right':     (SERVO1_ID, SERVO1_CENTER + SERVO1_LIMIT),
    'head_up':        (SERVO2_ID, SERVO2_CENTER + SERVO2_LIMIT_UP),
    'head_down':      (SERVO2_ID, SERVO2_CENTER - SERVO2_LIMIT_DOWN),
    'head_center_h':  (SERVO1_ID, SERVO1_CENTER),
    'head_center_v':  (SERVO2_ID, SERVO2_CENTER),
}


def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--action', required=True,
                        choices=list(ACTIONS.keys()) + ['center_all'],
                        help='')
    args = parser.parse_args()

    portHandler = PortHandler(DEVICE)
    packetHandler = sms_sts(portHandler)

    if not portHandler.openPort():
        print(f'Failed to open port {DEVICE}')
        sys.exit(1)

    if not portHandler.setBaudRate(BAUD):
        print(f'Failed to set baudrate {BAUD}')
        portHandler.closePort()
        sys.exit(1)

    if args.action == 'center_all':
        packetHandler.WritePosEx(SERVO1_ID, SERVO1_CENTER, SPEED, ACC)
        time.sleep(0.05)
        packetHandler.WritePosEx(SERVO2_ID, SERVO2_CENTER, SPEED, ACC)
        print('[center_all] 双舵机已回零 OK')
    else:
        servo_id, position = ACTIONS[args.action]
        packetHandler.WritePosEx(servo_id, position, SPEED, ACC)
        print(f'[{args.action}] OK')

    portHandler.closePort()


if __name__ == '__main__':
    main()
