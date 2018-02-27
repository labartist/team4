#! /usr/bin/env python

import rospy
import driver
import copy
import arm_controller
import perceptor
import wait_for_time
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Pose
from std_msgs.msg import Header

# Note: Brain handles all conversions
# milestone 1 - no backpack

BASKET_POSITION = PoseStamped()

# TODO milestone 1
# find location behind target so that input
def get_position_offset_target(target_pose):
    return target_pose

def main():
    rospy.init_node('brain')
    wait_for_time()

    my_driver = driver.Driver()
    my_arm = arm_controller.ArmController()
    my_perceptor = perceptor.Perceptor()

    while True:
        my_arm.tuck_arm()
        ball_position = my_perceptor.get_closest_ball_location() # from perceptor node
        # TODO milestone 2: move head if no ball seen
        # TODO milestone 3: move base if no ball seen
        if ball_position is not None:
            print "Ball Found!"
            print ball_position
            target = get_position_offset_target(ball_position)
            my_driver.go_to(ball_position) # handle offset (go behind ball)
            # TODO milestone 3: check if ball still there
            my_arm.pick_up_ball(ball_position)
            # assume for milestone 1 that basket is marked on map
            driver.go_to(BASKET_POSITION)
            my_arm.drop_ball_in_basket()
            driver.return_to_default_position()
            continue

        print "No ball found!"


    rospy.spin()


if __name__ == '__main__':
    main()
