#!/usr/bin/env python3
"""手臂舵机极简控制 — 无限制、直接发命令"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sts_sdk"))
from port_handler import *
from sts import *
import msvcrt

DEVICE = 'COM4'; BAUD = 1000000

ph = PortHandler(DEVICE); ph.openPort(); ph.setBaudRate(BAUD)
pkt = sts(ph)

IDS = [6,7,8,9,10,11,12,13]
SPEED = 2400; ACC = 50

print("初始化...")
for sid in IDS:
    pkt.write1ByteTxRx(sid, 33, 0)          # 位置模式
    pkt.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 1)
    pos, _, _ = pkt.ReadPos(sid)
    print(f"  ID:{sid:02d}  pos={pos:4d}")
    time.sleep(0.03)

cur = 9
print("""
1-8选舵机 | W/S ±500 | A/D ±100 | R读 | ESC退
""")

def rk():
    if not msvcrt.kbhit(): return None
    k = msvcrt.getch()
    if k == b'\xe0': k = msvcrt.getch(); return {b'H':'U',b'P':'D'}.get(k)
    try: return k.decode().lower()
    except: return None

pos = {}
for s in IDS:
    p,_,_ = pkt.ReadPos(s); pos[s] = p

try:
    while True:
        k = rk()
        if not k: time.sleep(0.02); continue
        while msvcrt.kbhit(): msvcrt.getch()

        if k in '12345678': cur = IDS[int(k)-1]; print(f"→ ID:{cur:02d}  pos={pos.get(cur,0):4d}")
        elif k == 'w':
            t = pos.get(cur,0) + 500
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.15)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  W +500 → 目标:{t:4d}  实际:{a:4d}")
        elif k == 's':
            t = pos.get(cur,0) - 500
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.15)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  S -500 → 目标:{t:4d}  实际:{a:4d}")
        elif k == 'd':
            t = pos.get(cur,0) + 100
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.1)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  D +100 → 目标:{t:4d}  实际:{a:4d}")
        elif k == 'a':
            t = pos.get(cur,0) - 100
            pkt.WritePosEx(cur, t, SPEED, ACC)
            time.sleep(0.1)
            a,_,_ = pkt.ReadPos(cur); pos[cur] = a
            print(f"  A -100 → 目标:{t:4d}  实际:{a:4d}")
        elif k == 'r':
            print("── 全部 ──")
            for s in IDS:
                p,_,_ = pkt.ReadPos(s); pos[s] = p
                print(f"  ID:{s:02d}  {p:4d}")
        elif k == chr(0x1b): break
finally:
    for s in IDS: pkt.write1ByteTxRx(s, STS_TORQUE_ENABLE, 0)
    ph.closePort(); print("\n退出")
