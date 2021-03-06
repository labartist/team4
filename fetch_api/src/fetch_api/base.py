#! /usr/bin/env python

import rospy

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import tf.transformations as tft
import numpy as np

import copy
import math


class Base(object):
    """Base controls the mobile base portion of the Fetch robot.

    Sample usage:
        base = fetch_api.Base()
        while CONDITION:
            base.move(0.2, 0)
        base.stop()
    """

    def __init__(self):
        # Publish stuff
        self.pub = rospy.Publisher('cmd_vel', Twist, queue_size=10)
        # Subscribe to odometry info
        self._odom_sub = rospy.Subscriber('odom', Odometry, callback=self._odom_callback)
        self.has_received_odom_msg = False
        pass

    def move(self, linear_speed, angular_speed):
        """Moves the base instantaneously at given linear and angular speeds.

        "Instantaneously" means that this method must be called continuously in
        a loop for the robot to move.

        Args:
            linear_speed: The forward/backward speed, in meters/second. A
                positive value means the robot should move forward.
            angular_speed: The rotation speed, in radians/second. A positive
                value means the robot should rotate clockwise.
        """
        # Create Twist msg
        newMsg = Twist()
        # Fill out msg
        newMsg.linear.x = linear_speed
        newMsg.linear.y = 0.0
        newMsg.linear.z = 0.0
        newMsg.angular.x = 0.0
        newMsg.angular.y = 0.0
        newMsg.angular.z = angular_speed
        # Publish msg
        self.pub.publish(newMsg)

    def stop(self):
        """Stops the mobile base from moving.
        """
        # Publish 0 velocity
        newMsg = Twist()
        newMsg.linear.x = 0.0
        newMsg.linear.y = 0.0
        newMsg.linear.z = 0.0
        newMsg.angular.x = 0.0
        newMsg.angular.y = 0.0
        newMsg.angular.z = 0.0
        self.pub.publish(newMsg)

    def _odom_callback(self, msg):
        """
        :param msg: nav_msgs/Odometry Message
        """
        self.has_received_odom_msg = True
        self.last_position = msg.pose.pose  # contains 'position' and 'orientation'

    def go_forward(self, distance, speed=0.1):
        """Moves the robot a certain distance.

        It's recommended that the robot move slowly. If the robot moves too
        quickly, it may overshoot the target. Note also that this method does
        not know if the robot's path is perturbed (e.g., by teleop). It stops
        once the distance traveled is equal to the given distance or more.

        Args:
            distance: The distance, in meters, to move. A positive value
                means forward, negative means backward.
            speed: The speed to travel, in meters/second.
        """
        # rospy.sleep until the base has received at least one message on /odom
        while not self.has_received_odom_msg:
            rospy.sleep(0.5)

        # record start position, use Python's copy.deepcopy
        start_pos = copy.deepcopy(self.last_position.position)
        rate = rospy.Rate(10)
        current_position = copy.deepcopy(self.last_position.position)
        traveled_distance = math.sqrt(math.pow((current_position.x - start_pos.x), 2) +
                                      math.pow((current_position.y - start_pos.y), 2) +
                                      math.pow((current_position.z - start_pos.z), 2))
        while not rospy.is_shutdown() and traveled_distance < math.fabs(distance):
            current_position = copy.deepcopy(self.last_position.position)
            traveled_distance = math.sqrt(math.pow((current_position.x - start_pos.x), 2) +
                                          math.pow((current_position.y - start_pos.y), 2) +
                                          math.pow((current_position.z - start_pos.z), 2))
            direction = -1 if distance < 0 else 1
            speed = max(0.05, min(0.5, distance - traveled_distance))  # scale based on remaining distance
            self.move(direction * speed, 0)
            if traveled_distance >= math.fabs(distance):
                break
            rate.sleep()

    def turn(self, angle, angular_speed=0.5):
        """Rotates the robot a certain angle.
        Args:
            angle: The angle, in radians, to rotate. A positive
                value rotates counter-clockwise.
            speed: The angular speed to rotate, in radians/second.
        """

        while not self.has_received_odom_msg:
            rospy.sleep(0.5)

        direction = -1 if angle < 0 else 1
        # record start position, add pi to make it be between 0 and 2*pi
        start_rads = self.quaternion_to_yaw(self.last_position.orientation) + math.pi
        # regularize angle to be between 0 and 2*pi
        angle = (angle * direction + (2 * math.pi) + .0001) % (math.pi * 2)
        current_rads = self.quaternion_to_yaw(self.last_position.orientation) + math.pi
        rads_traveled = ((current_rads - start_rads) * direction + (2 * math.pi) + .0001) % (2 * math.pi)
        rate = rospy.Rate(10)
        # check if the robot has rotated the desired amount
        while not rospy.is_shutdown() and rads_traveled < abs(angle):
            self.move(0, direction * angular_speed)
            rate.sleep()
            current_rads = self.quaternion_to_yaw(self.last_position.orientation) + math.pi
            rads_traveled = ((current_rads - start_rads) * direction + (2 * math.pi) + .0001) % (2 * math.pi)

    def quaternion_to_yaw(self, q):
        rotation_matrix = tft.quaternion_matrix([q.x, q.y, q.z, q.w])
        x = rotation_matrix[0, 0]
        y = rotation_matrix[1, 0]
        theta_rads = math.atan2(y, x)
        return theta_rads
