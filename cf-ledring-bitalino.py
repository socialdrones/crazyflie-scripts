# -*- coding: utf-8 -*-

import time

from bitalino import BITalino


# Bitalino Settings

bt_macAddress = "98:D3:71:FD:63:15" # MAC address for Windows
bt_vcp = "/dev/tty.BITalino-63-15-DevB" ## Virtual COM port for Mac
bt_batteryThreshold = 30
bt_acqChannels = [0]
bt_samplingRate = 10
bt_nSamples = 1
bt_timeout = 2
bt_respSensorMin = 100
bt_respSensorMax = 900



# Run for a finite number of seconds
running_time = 60


def remap(val, inMin=0.0, inMax=1.5, outMin=60.0, outMax=0.0):
    if val < inMin:
        val = inMin
    if val > inMax:
        val = inMax
    return outMin + (val - inMin) * (outMax - outMin) / (inMax - inMin)


# Connect to BITalino
print("Connecting to Bitalino " + bt_macAddress)
for i in range(0,10):
    try:
        bt = BITalino(bt_vcp, timeout=bt_timeout)
    except OSError or UnicodeDecodeError:
        print("Connection " + str(i+1) + "/10 failed! Retrying...")
        continue
    finally:
        print("Connected to Bitalino " + bt_vcp)
    break

# Set battery threshold
bt.battery(bt_batteryThreshold)
    
# Start Acquisition
bt.start(bt_samplingRate, bt_acqChannels)

start = time.time()
end = time.time()

while (end - start) < running_time:

    time.sleep(0.1)

    # Read respiration sensor at A0
    dataAcquired = bt.read(bt_nSamples)
    resp = dataAcquired[0, 5]
    # print("Resp: " + str(int(resp)))
    pzt = -((resp/1023.0) - (1.0/2.0)) * 100.0
    print("PZT:  " + str(int(pzt)))

    end = time.time()

# Stop acquisition & close connection
bt.stop()
bt.close()
print('Terminated!')
