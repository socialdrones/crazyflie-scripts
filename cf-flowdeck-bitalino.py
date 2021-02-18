# Reads a value from the Bitalino (r)evolution board and continuously sets
# the height of the Crazyflie (with Flow Deck) based on the value.

import logging
import numpy
import time
from threading import Thread

from bitalino import BITalino

import cflib.crtp
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander

# Fns

def remap(val, inMin=0, inMax=1024, outMin=0.5, outMax=1.5):
    if val < inMin:
        val = inMin
    if val > inMax:
        val = inMax
    return outMin + (val - inMin) * (outMax - outMin) / (inMax - inMin)


# Bitalino Settings
bt_macAddress = "98:D3:71:FD:63:15"
bt_batteryThreshold = 30
bt_acqChannels = [0]
bt_samplingRate = 100
bt_nSamples = 16
bt_timeout = 2
bt_respSensorMin = 0
bt_respSensorMax = 1024

# Crazyflie Settings
cf_uri = 'radio://0/80/2M'
cf_zMin = 0.5
cf_zMax = 1.2
cf_ledMin = 0
cf_ledMax = 100

# Run for a finite number of seconds
running_time = 16

# Init Crazyflie
cflib.crtp.init_drivers(enable_debug_driver=False)

with SyncCrazyflie(cf_uri) as scf:
    cf = scf.cf
    cf.param.set_value('ring.effect', '0')
    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')

    # Connect to BITalino
    print("Connecting to Bitalino " + bt_macAddress)
    for i in range(0,10):
        cf.param.set_value('ring.effect', '1')
        try:
            bt = BITalino(bt_macAddress, timeout=bt_timeout)
        except OSError:
            print("Connection " + str(i+1) + "/10 failed! Retrying...")
            cf.param.set_value('ring.effect', '9')
            time.sleep(0.1)
            cf.param.set_value('ring.effect', '0')
            time.sleep(0.1)
            cf.param.set_value('ring.effect', '9')
            time.sleep(0.1)
            cf.param.set_value('ring.effect', '0')
            time.sleep(0.1)
            continue
        finally:
            print("Connected to Bitalino " + bt_macAddress)
        break

    # Set battery threshold
    bt.battery(bt_batteryThreshold)
        
    # Start Acquisition
    bt.start(bt_samplingRate, bt_acqChannels)

    start = time.time()
    end = time.time()

    # Lift-off warning
    cf.param.set_value('ring.effect', '6')
    time.sleep(2)

    # Lift-off
    cf.commander.send_hover_setpoint(0, 0, 0, 0.5)

    # Set solid color effect
    cf.param.set_value('ring.effect', '7')

    # It's on
    while (end - start) < running_time:
        # Read respiration sensor at A0
        dataAcquired = bt.read(bt_nSamples)
        for sample in range(bt_nSamples):
            resp = dataAcquired[sample, 5]
            # Set z
            if sample in set([0]):
                print("Resp: " + str(int(resp)))
                z = remap(resp, bt_respSensorMin, bt_respSensorMax, cf_zMin, cf_zMax)
                print("z:    " + str(y))
                cf.commander.send_hover_setpoint(0, 0, 0, z)
            # Set light
            if sample in set([0, 4, 8, 12]):
                print("Resp:  " + str(int(resp)))
                led_r = int(remap(resp, bt_respSensorMin, bt_respSensorMax, cf_ledMin, cf_ledMax))
                led_g = 0
                led_b = int(cf_ledMax - led_r)
                print("z:     " + str(z))
                print("led_r: " + str(led_r))
                cf.param.set_value('ring.solidBlue', str(led_b))
                cf.param.set_value('ring.solidRed', str(led_r))
                cf.param.set_value('ring.solidGreen', str(led_g))
            time.sleep(0.01)
        end = time.time()
    
    # Land Crazyflie smoothly
    while (z > 0):
        z -= 0.05
        cf.commander.send_hover_setpoint(0, 0, 0, z)
        time.sleep(0.1)
    cf.param.set_value('ring.effect', '0')

        
    # Stop acquisition
    bt.stop()
        
    # Close connection
    bt.close()