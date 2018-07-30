import numpy as np

from Realsense import Realsense
from ATC import Tower
from mrrdt_vision.obj_detect.roomba_cnn import RoombaDetector
from timeit import default_timer as timer
from sklearn.preprocessing import normalize
import math

class SimpleDroneAI():
    # camera fov
    CAMERA_FIELD_OF_VIEW = 64.9
    # altitude to hover at after takeoff in meters
    TAKEOFF_HEIGHT = 2
    # roomba speed (m/s)
    ROOMBA_SPEED = .33
    # speed to follow roombas at normally
    ROOMBA_TRACKING_SPEED = .4
    # hover if drone goes beyond this speed
    DRONE_HARD_SPEED_LIMIT = 1.5*ROOMBA_TRACKING_SPEED
    # stop when we are this many meters away from the roomba
    ROOMBA_DISTANCE_THRESHOLD = .1
    # hover after losing the roomba for this much time in seconds
    MAX_LOST_TARGET_TIME = 10
    # roomba detector threshold
    ROOMBA_DETECTOR_THRESHOLD = .7

    def __init__(self):
        self._roomba_detector = RoombaDetector(threshold=self.ROOMBA_DETECTOR_THRESHOLD)
        self._tower = Tower(in_simulator=False)
        self._time_since_last_roomba = 0

    def is_drone_above_speed_limit(self):
        return self._tower.speed > self.DRONE_HARD_SPEED_LIMIT

    def get_meters_per_pixel(self, img):
        image_width = img.shape[1]
        image_width_in_meters = 2*math.tan(math.radians(self.CAMERA_FIELD_OF_VIEW/2.)) * self.get_altitude()
        return image_width_in_meters / image_width

    def get_velocity_vector2d(self, img, start, goal, speed):
        dist = float(np.sqrt(np.sum((goal-start)**2)))*self.get_meters_per_pixel(img)
        x_vel, y_vel = min(dist if dist > self.ROOMBA_DISTANCE_THRESHOLD else 0, speed)*normalize((goal-start).reshape(-1, 1), axis=1)
        yaw_angle = t.vehicle.attitude.yaw
        cos, sine = (math.cos(yaw_angle),math.sin(yaw_angle))
	x_vel, y_vel = (x_vel*cos - y*sin, y_vel*cos + x_vel*sin)
        return np.array([y_vel,-x_vel, 0])

    def follow_nearest_roomba(self, img):
        h, w = img.shape[:2]
        drone_midpoint = np.asarray([w/2, h/2])
        roombas = self._roomba_detector.detect(img)

        if self.is_drone_above_speed_limit():
            self._tower.hover()
        
        if roombas:
            roomba_midpoints = np.asarray([roomba.center for roomba in roombas])
            target_idx = np.argmin(np.sum((roomba_midpoints-drone_midpoint)**2, axis=1))
            target = roombas[target_idx]
            velocity = self.get_velocity_vector2d(img, drone_midpoint, roomba_midpoints[target_idx], self.ROOMBA_TRACKING_SPEED)
            self._tower.fly(velocity)
            self._time_since_last_roomba = timer()
        elif timer() - self._time_since_last_roomba >= self.MAX_LOST_TARGET_TIME:
            self._tower.hover()

    def run(self):
        with Realsense((640, 480)) as realsense:
            try:
                self._tower.connected.wait()
                print("Taking off")
                self._tower.takeoff(self.TAKEOFF_HEIGHT)
                self._tower.takeoff_completed.wait()
                print("Done taking off")
                while True:
                    status, color, depth = realsense.next()
                    if status:
                        self.follow_nearest_roomba(color)
            except KeyboardInterrupt as e:
                print('Quitting...')

if __name__ == '__main__':
    ai = SimpleDroneAI()
    ai.run()
