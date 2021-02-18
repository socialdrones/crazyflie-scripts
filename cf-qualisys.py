# -*- coding: utf-8 -*-
"""
Basic Crazyflie + Qualisys mocap integration
Light modification on example script from Bitcraze repo

Set the uri to the radio settings of the Crazyflie and modify the
ridgid_body_name to match the name of the Crazyflie in QTM.

Limitations: This script does not support full pose and the Crazyflie
must be started facing positive X.
"""
import asyncio
import math
import time
import xml.etree.cElementTree as ET
from threading import Thread

import qtm

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.mem import MemoryElement
from cflib.crazyflie.mem import Poly4D
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger

from cflib.positioning.position_hl_commander import PositionHlCommander



# URI to the Crazyflie to connect to
uri = 'radio://0/80/2M'

# The name of the rigid body in QTM that represents the Crazyflie
ridgid_body_name = 'crazyflie'

# QTM IP
qtm_ip = "127.0.0.1"

class QtmWrapper(Thread):
    def __init__(self, body_name):
        Thread.__init__(self)

        self.body_name = body_name
        self.on_pose = None
        self.connection = None
        self.qtm_6DoF_labels = []
        self._stay_open = True

        self.start()

    def close(self):
        self._stay_open = False
        self.join()

    def run(self):
        asyncio.run(self._life_cycle())

    async def _life_cycle(self): 
        await self._connect()
        while(self._stay_open):
            await asyncio.sleep(1)
        await self._close()

    async def _connect(self):
        host = qtm_ip
        print('Connecting to QTM on ' + host)
        self.connection = await qtm.connect(host)

        params = await self.connection.get_parameters(parameters=['6d'])
        xml = ET.fromstring(params)
        self.qtm_6DoF_labels = [label.text for label in xml.iter('Name')]
        print(self.qtm_6DoF_labels)

        await self.connection.stream_frames(
            components=['6D'],
            on_packet=self._on_packet)

    def _on_packet(self, packet):
        header, bodies = packet.get_6d()

        if bodies is None:
            return

        if self.body_name not in self.qtm_6DoF_labels:
            print('Body ' + self.body_name + ' not found.')
        else:
            index = self.qtm_6DoF_labels.index(self.body_name)
            temp_cf_pos = bodies[index]
            x = temp_cf_pos[0][0] / 1000
            y = temp_cf_pos[0][1] / 1000
            z = temp_cf_pos[0][2] / 1000

            r = temp_cf_pos[1].matrix
            rot = [
                [r[0], r[3], r[6]],
                [r[1], r[4], r[7]],
                [r[2], r[5], r[8]],
            ]

            if self.on_pose:
                # Make sure we got a position
                if math.isnan(x):
                    return

                self.on_pose([x, y, z, rot])

    async def _close(self):
        await self.connection.stream_frames_stop()
        self.connection.disconnect()

def wait_for_position_estimator(scf):
    print('Waiting for estimator to find position...')

    log_config = LogConfig(name='Kalman Variance', period_in_ms=500)
    log_config.add_variable('kalman.varPX', 'float')
    log_config.add_variable('kalman.varPY', 'float')
    log_config.add_variable('kalman.varPZ', 'float')

    var_y_history = [1000] * 10
    var_x_history = [1000] * 10
    var_z_history = [1000] * 10

    threshold = 0.001

    with SyncLogger(scf, log_config) as logger:
        for log_entry in logger:
            data = log_entry[1]

            var_x_history.append(data['kalman.varPX'])
            var_x_history.pop(0)
            var_y_history.append(data['kalman.varPY'])
            var_y_history.pop(0)
            var_z_history.append(data['kalman.varPZ'])
            var_z_history.pop(0)

            min_x = min(var_x_history)
            max_x = max(var_x_history)
            min_y = min(var_y_history)
            max_y = max(var_y_history)
            min_z = min(var_z_history)
            max_z = max(var_z_history)

            # print("{} {} {}".
            #       format(max_x - min_x, max_y - min_y, max_z - min_z))

            if (max_x - min_x) < threshold and (
                    max_y - min_y) < threshold and (
                    max_z - min_z) < threshold:
                break


def _sqrt(a):
    """
    There might be rounding errors making 'a' slightly negative.
    Make sure we don't throw an exception.
    """
    if a < 0.0:
        return 0.0
    return math.sqrt(a)


def send_extpose_rot_matrix(cf, x, y, z, rot):
    """
    Send the current Crazyflie X, Y, Z position and attitude as a (3x3)
    rotaton matrix. This is going to be forwarded to the Crazyflie's
    position estimator.
    """
    qw = _sqrt(1 + rot[0][0] + rot[1][1] + rot[2][2]) / 2
    qx = _sqrt(1 + rot[0][0] - rot[1][1] - rot[2][2]) / 2
    qy = _sqrt(1 - rot[0][0] + rot[1][1] - rot[2][2]) / 2
    qz = _sqrt(1 - rot[0][0] - rot[1][1] + rot[2][2]) / 2

    # Normalize the quaternion
    ql = math.sqrt(qx ** 2 + qy ** 2 + qz ** 2 + qw ** 2)

    cf.extpos.send_extpose(x, y, z, qx / ql, qy / ql, qz / ql, qw / ql)


def reset_estimator(cf):
    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')

    # time.sleep(1)
    wait_for_position_estimator(cf)


def activate_kalman_estimator(cf):
    cf.param.set_value('stabilizer.estimator', '2')

    # Set the std deviation for the quaternion data pushed into the
    # kalman filter. The default value seems to be a bit too low.
    cf.param.set_value('locSrv.extQuatStdDev', 0.06)


def activate_high_level_commander(cf):
    cf.param.set_value('commander.enHighLevel', '1')


def activate_mellinger_controller(cf):
    cf.param.set_value('stabilizer.controller', '2')


cflib.crtp.init_drivers(enable_debug_driver=False)

# Connect to QTM
qtm_wrapper = QtmWrapper(ridgid_body_name)

with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
    cf = scf.cf

    # Set up a callback to handle data from QTM
    qtm_wrapper.on_pose = lambda pose: send_extpose_rot_matrix(
        cf, pose[0], pose[1], pose[2], pose[3])

    activate_kalman_estimator(cf)
    activate_high_level_commander(cf)
    activate_mellinger_controller(cf)
    reset_estimator(cf)


    commander = cf.high_level_commander

    commander.takeoff(1.0, 5.0)
    time.sleep(5.0)

    with PositionHlCommander(scf) as pc:
            pc.go_to( 0.0,  0.0, 1.0)
            pc.go_to( 0.6,  0.0, 1.0)
            pc.go_to(-0.6,  0.0, 1.0)
            pc.go_to( 0.0,  0.6, 1.0)
            pc.go_to( 0.0, -0.6, 1.0)
            pc.go_to( 0.0, 0.0, 0.8)
            pc.go_to( 0.0, 0.0, 1.2)
            pc.go_to( 0.0, 0.0, 0.6)

    commander.land(0.0, 5.0)
    time.sleep(2)
    commander.stop()



qtm_wrapper.close()