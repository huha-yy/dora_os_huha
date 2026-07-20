#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手臂舵机调试 — STS 协议, SPEED=2400"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sts_sdk"))
from port_handler import *
from sts import *
import msvcrt

DEVICE   = 'COM4'; BAUDRATE = 1000000
SPEED    = 2400; ACC = 50
STEP_BIG = 100; STEP_SMALL = 20

SERVO_SPEC = {
    6:(360,"右手"),10:(360,"左手"),7:(90,"右腕"),11:(90,"左腕"),
    8:(180,"右臂"),12:(180,"左臂"),9:(360,"右肩"),13:(360,"左肩"),
}
# 初始位置
HOME_POS = {6:1,7:4000,8:2680,9:1389,10:3764,11:1088,12:2656,13:1551}
IDS = [6,7,8,9,10,11,12,13]

# 限位
LIMITS = {
    6:(30,4065),7:(3000,4050),8:(0,4095),9:(30,4065),
    10:(30,4065),11:(1140,2105),12:(706,2626),13:(30,4065),
}

def clamp(sid, val):
    lo, hi = LIMITS.get(sid, (0,4095))
    return max(lo, min(hi, val))

# ── 连接 ──
ph = PortHandler(DEVICE); ph.openPort(); ph.setBaudRate(BAUDRATE)
pkt = sts(ph)
print(f"串口 {DEVICE} OK")

# ── 初始化 ──
pos = {}
for sid in IDS:
    pkt.write1ByteTxRx(sid, 33, 0)            # 位置模式
    pkt.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 1)
    time.sleep(0.03)
    p,_,_ = pkt.ReadPos(sid)
    pos[sid] = p if p else 2048
    lo, hi = LIMITS.get(sid, (0,4095))
    label = SERVO_SPEC[sid][1]
    print(f"[ID:{sid:02d}] {label:<6s} {SERVO_SPEC[sid][0]:3d}°  当前:{pos[sid]:4d}  范围:{lo}~{hi}")
    time.sleep(0.02)

cur = 9
def rk():
    if not msvcrt.kbhit(): return None
    k = msvcrt.getch()
    if k == b'\xe0': k = msvcrt.getch(); return {b'H':'U',b'P':'D'}.get(k)
    try: return k.decode().lower()
    except: return None

def wait_up():
    while msvcrt.kbhit(): msvcrt.getch()
    time.sleep(0.05)

print("""
╔══════════════════════════════════════╗
║  1-8 选舵机  W/S ±100  A/D ±20     ║
║  Q 回零位    R 读全部  E 归零      ║
║  T 拥抱      Y 抬右手  U 抬左手    ║
║  Z 急停      ESC 退出              ║
╚══════════════════════════════════════╝
""")

try:
    while True:
        k = rk()
        if not k: time.sleep(0.02); continue
        wait_up()

        if k in '12345678':
            cur = IDS[int(k)-1]
            print(f"→ ID:{cur:02d} {SERVO_SPEC[cur][1]} pos={pos.get(cur,2048):4d}")

        elif k == 'w':
            t = clamp(cur, pos.get(cur,2048) + STEP_BIG)
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.15)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  W +{STEP_BIG} → 目标:{t:4d}  实际:{a:4d}")

        elif k == 's':
            t = clamp(cur, pos.get(cur,2048) - STEP_BIG)
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.15)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  S -{STEP_BIG} → 目标:{t:4d}  实际:{a:4d}")

        elif k == 'd':
            t = clamp(cur, pos.get(cur,2048) + STEP_SMALL)
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.1)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  D +{STEP_SMALL} → {t:4d}  实际:{a:4d}")

        elif k == 'a':
            t = clamp(cur, pos.get(cur,2048) - STEP_SMALL)
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.1)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  A -{STEP_SMALL} → {t:4d}  实际:{a:4d}")

        elif k == 'q':
            t = HOME_POS.get(cur, 2048)
            pkt.WritePosEx(cur, t, SPEED, ACC)
            pos[cur] = t
            print(f"  Q 回零 → {t:4d}")

        elif k == 'r':
            print("── 全部 ──")
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                lo, hi = LIMITS.get(s,(0,4095))
                label = SERVO_SPEC[s][1]
                print(f"  ID:{s:02d} {label:<6s} {p:4d}  [{lo}~{hi}]")

        elif k == 'e':
            print("[E] 归零...", flush=True)
            for s in IDS:
                t = HOME_POS.get(s, 2048)
                lo, hi = LIMITS.get(s,(0,4095))
                pkt.WritePosEx(s, max(lo,min(hi,t)), SPEED, ACC)
                time.sleep(0.05)
            time.sleep(0.5)
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                print(f"  ID:{s:02d} → {pos[s]:4d}")
            print("完成")

        # ── 预设动作 ──
        elif k == 't':  # 拥抱
            preset = {6:231,7:3409,8:2790,9:196,10:3766,11:1873,12:2529,13:2770}
            print("[T] 拥抱...", flush=True)
            for s in IDS:
                pkt.WritePosEx(s, preset.get(s,2048), SPEED, ACC); time.sleep(0.05)
            time.sleep(0.5)
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                print(f"  ID:{s:02d} → {pos[s]:4d}")
            print("完成")

        elif k == 'y':  # 抬右手(逆时针)
            preset = {6:230,7:3402,8:2683,9:43,10:3765,11:2133,12:2656,13:1651}
            print("[Y] 抬右手...", flush=True)
            for s in IDS:
                pkt.WritePosEx(s, preset.get(s,2048), SPEED, ACC); time.sleep(0.05)
            time.sleep(0.5)
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                print(f"  ID:{s:02d} → {pos[s]:4d}")
            print("完成")

        elif k == 'u':  # 抬左手
            preset = {6:232,7:3037,8:2685,9:1340,10:3765,11:1605,12:2658,13:2675}
            print("[U] 抬左手...", flush=True)
            for s in IDS:
                pkt.WritePosEx(s, preset.get(s,2048), SPEED, ACC); time.sleep(0.05)
            time.sleep(0.5)
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                print(f"  ID:{s:02d} → {pos[s]:4d}")
            print("完成")

        elif k == 'z':
            for s in IDS: pkt.write1ByteTxRx(s, STS_TORQUE_ENABLE, 0)
            print("急停!")

        elif k == chr(0x1b): break

finally:
    for s in IDS: pkt.write1ByteTxRx(s, STS_TORQUE_ENABLE, 0)
    ph.closePort(); print("\n退出")
