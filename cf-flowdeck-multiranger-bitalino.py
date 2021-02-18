#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2017 Bitcraze AB
#
#  Crazyflie Python Library
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA  02110-1301, USA.
"""
Example scripts that allows a user to "push" the Crazyflie 2.0 around
using your hands while it's hovering.

This examples uses the Flow and Multi-ranger decks to measure distances
in all directions and tries to keep away from anything that comes closer
than 0.2m by setting a velocity in the opposite direction.

The demo is ended by either pressing Ctrl-C or by holding your hand above the
Crazyflie.

For the example to run the following hardware is needed:
 * Crazyflie 2.0
 * Crazyradio PA
 * Flow deck
 * Multiranger deck
"""
import logging
import sys
import time

from bitalino import BITalino

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.mem import MemoryElement
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils.multiranger import Multiranger

# Bitalino Settings
bt_macAddress = "98:D3:71:FD:63:15"
bt_batteryThreshold = 30
bt_acqChannels = [0]
bt_samplingRate = 100
bt_nSamples = 16
bt_timeout = 2
bt_respSensorMin = 0
bt_respSensorMax = 1024

#Crazyflie Settings
cf_uri = 'radio://0/80/2M'
cf_minDistance = 0.8  # m
cf_maxSpeed = 0.8 # m/s
cf_zSpeed = 0.1 # m
cf_zMin = 0.5
cf_zMax = 1.2

# Run for a finite number of seconds
running_time = 16


def is_close(range):
    if range is None:
        return False
    else:
        return range < MIN_DISTANCE


def remap(val, inMin=0.0, inMax=1.5, outMin=60.0, outMax=0.0):
    if val < inMin:
        val = inMin
    if val > inMax:
        val = inMax
    return outMin + (val - inMin) * (outMax - outMin) / (inMax - inMin)


cflib.crtp.init_drivers(enable_debug_driver=False)

with SyncCrazyflie(cf_uri) as scf:

    cf = scf.cf

    # Start LED Deck with effect 1 = White Spinner
    cf.param.set_value('ring.effect', '1')

    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')
    time.sleep(2)

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

    with Multiranger(scf) as mr:

        # Set LED Deck effect param to 13 = N/A
        # To write to individual LEDs
        # cf.param.set_value('ring.effect', '13')
        # mem = cf.mem.get_mems(MemoryElement.TYPE_DRIVER_LED)

        # Lift-off warning
        cf.param.set_value('ring.effect', '6')
        time.sleep(2)

        # Lift-off
        cf.commander.send_hover_setpoint(0, 0, 0, 0.5)

        # Set solid color effect
        cf.param.set_value('ring.effect', '7')


        while (end - start) < running_time:
            
            # Avoid obstacles
            vx = 0.0
            vy = 0.0

            if mr.front is not None:
                dvx = remap(mr.front, 0.0, cf_minDistance, cf_maxSpeed, 0.0)
                vx -= dvx
                # print("FRONT: " + str(mr.front) + " --> " + str(dvx))
            if mr.back is not None:
                dvx = remap(mr.back,  0.0, cf_minDistance, cf_maxSpeed, 0.0)
                vx += dvx
                # print("BACK: " + str(mr.back) + " --> " + str(dvx))
            if mr.left is not None:
                dvy = remap(mr.left,  0.0, cf_minDistance, cf_maxSpeed, 0.0)
                vy -= dvy
                # print("LEFT: " + str(mr.left) + " --> " + str(dvy))
            if mr.right is not None:
                dvy = remap(mr.right, 0.0, cf_minDistance, cf_maxSpeed, 0.0)
                vy += dvy
                # print("RIGHT: " + str(mr.right) + " --> " + str(dvy))

            # Read respiration sensor at A0
            dataAcquired = bt.read(bt_nSamples)
            for sample in range(bt_nSamples):
                resp = dataAcquired[sample, 5]
                # Set z
                if sample in set([0]):
                    print("Resp: " + str(int(resp)))
                    z = remap(resp, bt_respSensorMin, bt_respSensorMax, cf_zMin, cf_zMax)
                    print("z:    " + str(y))
                    cf.commander.send_hover_setpoint(x, y, 0, z)
                # # Set light
                # if sample in set([0, 4, 8, 12]):
                #     print("Resp:  " + str(int(resp)))
                #     led_r = int(remap(resp, bt_respSensorMin, bt_respSensorMax, cf_ledMin, cf_ledMax))
                #     led_g = 0
                #     led_b = int(cf_ledMax - led_r)
                #     print("z:     " + str(z))
                #     print("led_r: " + str(led_r))
                #     cf.param.set_value('ring.solidBlue', str(led_b))
                #     cf.param.set_value('ring.solidRed', str(led_r))
                #     cf.param.set_value('ring.solidGreen', str(led_g))
                time.sleep(0.01)
            end = time.time()

            
            # if multiranger.front is not None:
            #     mem[0].leds[ 0].set(r=remap(multiranger.front), g=0, b=0)
            #     mem[0].leds[ 1].set(r=remap(multiranger.front), g=0, b=0)
            #     mem[0].leds[11].set(r=remap(multiranger.front), g=0, b=0)
            # if multiranger.right is not None:
            #     mem[0].leds[ 2].set(r=remap(multiranger.right), g=0, b=0)
            #     mem[0].leds[ 3].set(r=remap(multiranger.right), g=0, b=0)
            #     mem[0].leds[ 4].set(r=remap(multiranger.right), g=0, b=0)
            # if multiranger.back is not None:
            #     mem[0].leds[ 5].set(r=remap(multiranger.back), g=0, b=0)
            #     mem[0].leds[ 6].set(r=remap(multiranger.back), g=0, b=0)
            #     mem[0].leds[ 7].set(r=remap(multiranger.back), g=0, b=0)
            # if multiranger.left is not None:
            #     mem[0].leds[ 8].set(r=remap(multiranger.left), g=0, b=0)
            #     mem[0].leds[ 9].set(r=remap(multiranger.left), g=0, b=0)
            #     mem[0].leds[10].set(r=remap(multiranger.left), g=0, b=0)
            # if multiranger.up is not None:
            #     mem[0].leds[ 1].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[ 2].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[ 4].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[ 5].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[ 7].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[ 8].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[10].set(r=0, g=0, b=remap(multiranger.up))
            #     mem[0].leds[11].set(r=0, g=0, b=remap(multiranger.up))
            # mem[0].write_data(None)
            
            # yawrate = 0 # deg / sec
            
            # cf.commander.send_hover_setpoint(vx, vy, yawrate, z)

            # time.sleep(0.1)
        
        while (z > 0):
            z -= 0.05
            cf.commander.send_hover_setpoint(0, 0, 0, z)
            time.sleep(0.1)
        #  cf.param.set_value('ring.effect', '0')

        # Stop acquisition
        bt.stop()
            
        # Close connection
        bt.close()

    print('Demo terminated!')