"""
Simple example that connects to the first Crazyflie found, ramps up/down
the motors and disconnects.
"""
import logging
import time
from threading import Thread
from threading import Timer
import random

import cflib
import cflib.crtp  # noqa
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander

import sys
sys.path.append('.')
from gesture_detection import MovementVector
DEFAULT_HEIGHT = 0.8
TURN_RADIUS = 0.1
LIMITS = [1, 1, 0.3]


logging.basicConfig(level=logging.ERROR)

class DroneMotion:
    """Example that connects to a Crazyflie and ramps the motors up/down and
    the disconnects"""

    def __init__(self, link_uri, return_to_start=False, rubber_band=False, leash=False):
        """ Initialize and run the example with the specified link_uri """

        self._cf = Crazyflie(rw_cache='./cache')

        self._cf.connected.add_callback(self._connected)
        self._cf.disconnected.add_callback(self._disconnected)
        self._cf.connection_failed.add_callback(self._connection_failed)
        self._cf.connection_lost.add_callback(self._connection_lost)

        self._cf.open_link(link_uri)
        self.return_to_start = return_to_start
        self.rubber_band = rubber_band
        self.leash = leash


        print('Connecting to %s' % link_uri)
        self.is_connected = True 
        self._param_check_list = []
        self._param_groups = []

    def hover(self):
        with MotionCommander(self._cf, default_height=DEFAULT_HEIGHT):
            time.sleep(2)
        print("heeeee")

    @classmethod
    def reachedLimit(cls, x_vector, y_vector, z_vector, distance_traveled):
        x_traveled, y_traveled, z_traveled = distance_traveled
        x_limit, y_limit, z_limit = LIMITS

        if x_traveled + x_vector > x_limit or x_traveled + x_vector < -x_limit:
            x_vector = 0
        if y_traveled + y_vector > y_limit or y_traveled + y_vector < -y_limit:
            y_vector = 0
        if z_traveled + z_vector > z_limit or z_traveled + z_vector < -z_limit:
            z_vector = 0

        return x_vector, y_vector, z_vector

    def _connected(self, link_uri):
        """ This callback is called form the Crazyflie API when a Crazyflie
        has been connected and the TOCs have been downloaded."""
        print('Connected to %s' % link_uri)
        self._ramp_motors()

    def _a_propTest_callback(self, name, value):
        """Callback for pid_attitude.pitch_kd"""
        print('Readback: {0}={1}'.format(name, value))

    def _stab_log_error(self, logconf, msg):
        """Callback from the log API when an error occurs"""
        print('Error when logging %s: %s' % (logconf.name, msg))

    def _stab_log_data(self, timestamp, data, logconf):
        """Callback froma the log API when data arrives"""
        print('[%d][%s]: %s' % (timestamp, logconf.name, data), flush=True)
    def _connection_failed(self, link_uri, msg):
        """Callback when connection initial connection fails (i.e no Crazyflie
        at the specified address)"""
        print('Connection to %s failed: %s' % (link_uri, msg))

    def _connection_lost(self, link_uri, msg):
        """Callback when disconnected after a connection has been made (i.e
        Crazyflie moves out of range)"""
        print('Connection to %s lost: %s' % (link_uri, msg))

    def _disconnected(self, link_uri):
        """Callback when the Crazyflie is disconnected (called in all cases)"""
        print('Disconnected from %s' % link_uri)

    def _ramp_motors(self):
        print("ramp")

        thrust_mult = 1
        thrust_step = 100
        thrust_dstep = 10
        thrust = 30
        pitch = 0
        roll = 0
        last_x = 325
        last_y = 250
        last_z = -50
        yawrate = 0
        start_height = 0.1
        target_height = 0.3 

        num_prev_vectors = 0
        hover_on = 1
        roll = 0
        pitch = 0
        yaw = 0
        cnt = 0
        error = (-1000, -1000, -1000)

        x = y = z = 0
        distance_traveled = [x, y, z]
        iterations = 0
        last_command = time.time()
        first = True
        with MotionCommander(self._cf, default_height=DEFAULT_HEIGHT) as mc:
            while hover_on:

                vectors = MovementVector.query.all()
                num_vectors = len(vectors)
                if not num_prev_vectors or num_vectors > num_prev_vectors:
                    for i in range(num_prev_vectors, num_vectors):
                        
                        vector = vectors[i]
                        if time.time() - float(vector.timestamp) < 0.4:
                            x_vector, y_vector, z_vector, turn_vector = float(vector.x_vector), float(vector.y_vector), float(vector.z_vector), float(vector.turn_vector)
                            
                            if 0:
                                pass
                            else:
                                last_command = time.time()
                                if (x_vector, y_vector, z_vector) == error:
                                    print(f"x_vector: {x_vector}, y_vector: {y_vector}, z_vector: {z_vector} {i}")
                                    hover_on = 0
                                    break
                                elif turn_vector == 1:
                                    mc.start_circle_left(self, TURN_RADIUS, velocity=0.3)
                                    time.sleep(0.5)
                                elif turn_vector == -1:
                                    mc.start_circle_right(self, TURN_RADIUS, velocity=0.3)
                                    time.sleep(0.5)
                                elif self.rubber_band:
                                    mc.move_distance(x_vector, y_vector, z_vector, velocity=0.2)
                                    time.sleep(0.5)
                                    mc.move_distance(-x_vector, -y_vector, -z_vector, velocity=0.2)
                                    time.sleep(0.5)
                                elif self.leash:
                                    x_vector, y_vector, z_vector = DroneMotion.reachedLimit(x_vector, y_vector, z_vector, distance_traveled)
                                    mc.move_distance(x_vector, y_vector, z_vector, velocity=0.1)
                                else:
                                    mc.move_distance(x_vector, y_vector, z_vector, velocity=0.2)
                                    time.sleep(0.15)

                            print(f"x_vector: {x_vector}, y_vector: {y_vector}, z_vector: {z_vector} {i}, turn_vector: {turn_vector}")
                            x += x_vector
                            y += y_vector
                            z += z_vector
                            distance_traveled = [x, y, z]


                    num_prev_vectors = num_vectors

            if self.return_to_start:
                if x:
                    mc.move_distance(x, 0, 0, velocity=0.1)
                    time.sleep(0.3)
                if y:
                    mc.move_distance(0, y, 0, velocity=0.1)
                    time.sleep(0.3)
                if z:
                    mc.move_distance(0, 0, z, velocity=0.1)
                    time.sleep(0.3)

        print('end', flush=True)
        self._cf.close_link()


if __name__ == '__main__':
    print("start")
    # Initialize the low-level drivers (don't list the debug drivers)
    cflib.crtp.init_drivers(enable_debug_driver=False)
    # Scan for Crazyflies and use the first one found
    print('Scanning interfaces for Crazyflies...')
    available = cflib.crtp.scan_interfaces()
    print('Crazyflies found:')
    for i in available:
        print(i[0])

    if len(available) > 0:
        length = len(sys.argv)
        return_to_start = rubber_band = leash = False
        
        for arg in sys.argv:
            if arg == "return":
                return_to_start = True
            elif arg == "rubber_band":
                rubber_band = True
            elif arg == "leash":
                leash = True

        print(return_to_start, rubber_band, leash)
        DroneMotion(available[0][0], return_to_start=return_to_start, rubber_band=rubber_band, leash=leash)

    else:
        print('No Crazyflies found, cannot run example')
        sys.exit(0)
