#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 STS3215 舵机的角度限位 (EEPROM)
STS 协议专用: STservo_sdk
"""
import sys, os, time
from port_handler import *
from sts import *

DEVICE   = 'COM4'
BAUDRATE = 1000000
SID      = 13

portHandler = PortHandler(DEVICE)
packetHandler = sts(portHandler)

if not portHandler.openPort():
    print("打开串口失败")
    quit()
portHandler.setBaudRate(BAUDRATE)
print(f"连接 OK, 读取舵机 ID:{SID} EEPROM...")

# ── 读 EEPROM 关键寄存器 ──
regs = {
    "MODEL":           (3, 2),       # 型号 2字节
    "ID":              (5, 1),       # ID
    "BAUD":            (6, 1),       # 波特率
    "MIN_ANGLE_LIMIT": (9, 2),       # 最小角度限位 ⚠️
    "MAX_ANGLE_LIMIT": (11, 2),      # 最大角度限位 ⚠️
    "CW_DEAD":         (26, 1),      # 顺时针死区
    "CCW_DEAD":        (27, 1),      # 逆时针死区
    "MID_OFFSET_L":    (31, 1),      # 中点偏移
    "MID_OFFSET_H":    (32, 1),      # 中点偏移
    "MODE":            (33, 1),      # 模式 (0=位置, 1=轮子)
}

print(f"\n{'寄存器':<20s} {'地址':<8s} {'值(dec)':<10s} {'值(hex)':<10s} {'角度(度)':<10s}")
print("-" * 65)

for name, (addr, length) in regs.items():
    if length == 1:
        val, result, error = packetHandler.read1ByteTxRx(SID, addr)
    else:
        raw, result, error = packetHandler.read2ByteTxRx(SID, addr)
        val = packetHandler.sts_tohost(raw, 15)  # 15bit 有符号

    if result == COMM_SUCCESS:
        deg = val / 4096 * 360
        print(f"  {name:<18s}  {addr:3d}     {val:<10d}  {val:#06x}      {deg:.1f}")
    else:
        print(f"  {name:<18s}  {addr:3d}     读取失败")

# ── 判断问题 ──
print("\n=== 诊断 ===")
min_raw, _, _ = packetHandler.read2ByteTxRx(SID, 9)
max_raw, _, _ = packetHandler.read2ByteTxRx(SID, 11)
min_val = packetHandler.sts_tohost(min_raw, 15)
max_val = packetHandler.sts_tohost(max_raw, 15)
print(f"角度限位: {min_val} ~ {max_val}  ({min_val/4096*360:.0f}° ~ {max_val/4096*360:.0f}°)")

if min_val > 0 or max_val < 4095:
    print(f"⚠️  限位被锁! 舵机被限制在 {min_val}~{max_val} 之间")
    print(f"   这就是卡死的根因——代码发 1337 或 2040, 但硬限位阻止了移动")
    print(f"\n   修复命令: 按 Y 清除限位 (设为 0~4095)")

    import msvcrt
    print("   [Y] 清除限位   [N] 退出")
    k = msvcrt.getch().decode().lower()
    if k == 'y':
        print("\n正在清除角度限位...")
        # 解锁 EEPROM
        packetHandler.unLockEprom(SID)
        time.sleep(0.05)
        # 写最小角度 = 0
        min_bytes = packetHandler.sts_toscs(0, 15)
        packetHandler.write2ByteTxRx(SID, STS_MIN_ANGLE_LIMIT_L, min_bytes)
        time.sleep(0.05)
        # 写最大角度 = 4095
        max_bytes = packetHandler.sts_toscs(4095, 15)
        packetHandler.write2ByteTxRx(SID, STS_MAX_ANGLE_LIMIT_L, max_bytes)
        time.sleep(0.05)
        # 锁定 EEPROM
        packetHandler.LockEprom(SID)
        print("限位已清除, 重新上电生效! 断电重启舵机后再测试。")
else:
    print("✓ 限位正常 (0~4095), 不是限位问题")

portHandler.closePort()
