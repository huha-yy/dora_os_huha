import sys, os
sys.path.append("..")
from scservo_sdk import *

DEVICENAME = 'COM4'    # 改成你的 COM 口
BAUDRATE   = 1000000

portHandler = PortHandler(DEVICENAME)
packetHandler = sms_sts(portHandler)

if not portHandler.openPort():
    print("Failed to open port")
    quit()
if not portHandler.setBaudRate(BAUDRATE):
    print("Failed to set baudrate")
    quit()

print("Scanning IDs 1-253...")
found = False
for scs_id in range(1, 254):
    model, result, error = packetHandler.ping(scs_id)
    if result == COMM_SUCCESS:
        print("[ID:%03d] Found! Model: %d" % (scs_id, model))
        found = True
    elif result == COMM_RX_TIMEOUT:
        pass  # no servo at this ID
    else:
        print("[ID:%03d] Error: %s" % (scs_id, packetHandler.getTxRxResult(result)))

if not found:
    print("No servo found. Check power and wiring.")

portHandler.closePort()
