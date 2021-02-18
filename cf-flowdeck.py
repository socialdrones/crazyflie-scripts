# A simple test for the Flow Deck, moves Crazyflie up and down

import logging
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander

URI = 'radio://0/80/2M'

# Only output errors from the logging framework
logging.basicConfig(level=logging.ERROR)


if __name__ == '__main__':
    # Initialize the low-level drivers (don't list the debug drivers)
    cflib.crtp.init_drivers(enable_debug_driver=False)

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        cf.param.set_value('kalman.resetEstimation', '1')
        time.sleep(0.1)
        cf.param.set_value('kalman.resetEstimation', '0')
        time.sleep(2)

        for y in range(5):
            cf.commander.send_hover_setpoint(0, 0, 0, 0.2)
            time.sleep(1)

        for _ in range(5):
            cf.commander.send_hover_setpoint(0, 0, 0, 0.5)
            time.sleep(1)

        for i in range(5):
            y =  0.5 - 0.1 * i
            cf.commander.send_hover_setpoint(0, 0, 0, y)
            time.sleep(0.5)        

        # for _ in range(50):
        #     cf.commander.send_hover_setpoint(0.5, 0, 36 * 2, 0.4)
        #     time.sleep(0.1)

        # for _ in range(50):
        #     cf.commander.send_hover_setpoint(0.5, 0, -36 * 2, 0.4)
        #     time.sleep(0.1)

        # for _ in range(20):
        #     cf.commander.send_hover_setpoint(0, 0, 0, 0.4)
        #     time.sleep(0.1)

        # for y in range(10):
        #     cf.commander.send_hover_setpoint(0, 0, 0, (10 - y) / 25)
        #     time.sleep(0.1)

        cf.commander.send_stop_setpoint()