#! /usr/bin/env python

import actionlib
import rospy
from .arm_joints import ArmJoints
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from .moveit_goal_builder import MoveItGoalBuilder
from moveit_msgs.msg import MoveItErrorCodes, MoveGroupAction
from moveit_msgs.srv import GetPositionIK, GetPositionIKRequest
from geometry_msgs.msg import Pose, Quaternion, Point
import tf
from tf.listener import TransformListener

TIME_FROM_START = 5


def moveit_error_string(val):
    """Returns a string associated with a MoveItErrorCode.

    Args:
        val: The val field from moveit_msgs/MoveItErrorCodes.msg

    Returns: The string associated with the error value, 'UNKNOWN_ERROR_CODE'
        if the value is invalid.
    """
    if val == MoveItErrorCodes.SUCCESS:
        return 'SUCCESS'
    elif val == MoveItErrorCodes.FAILURE:
        return 'FAILURE'
    elif val == MoveItErrorCodes.PLANNING_FAILED:
        return 'PLANNING_FAILED'
    elif val == MoveItErrorCodes.INVALID_MOTION_PLAN:
        return 'INVALID_MOTION_PLAN'
    elif val == MoveItErrorCodes.MOTION_PLAN_INVALIDATED_BY_ENVIRONMENT_CHANGE:
        return 'MOTION_PLAN_INVALIDATED_BY_ENVIRONMENT_CHANGE'
    elif val == MoveItErrorCodes.CONTROL_FAILED:
        return 'CONTROL_FAILED'
    elif val == MoveItErrorCodes.UNABLE_TO_AQUIRE_SENSOR_DATA:
        return 'UNABLE_TO_AQUIRE_SENSOR_DATA'
    elif val == MoveItErrorCodes.TIMED_OUT:
        return 'TIMED_OUT'
    elif val == MoveItErrorCodes.PREEMPTED:
        return 'PREEMPTED'
    elif val == MoveItErrorCodes.START_STATE_IN_COLLISION:
        return 'START_STATE_IN_COLLISION'
    elif val == MoveItErrorCodes.START_STATE_VIOLATES_PATH_CONSTRAINTS:
        return 'START_STATE_VIOLATES_PATH_CONSTRAINTS'
    elif val == MoveItErrorCodes.GOAL_IN_COLLISION:
        return 'GOAL_IN_COLLISION'
    elif val == MoveItErrorCodes.GOAL_VIOLATES_PATH_CONSTRAINTS:
        return 'GOAL_VIOLATES_PATH_CONSTRAINTS'
    elif val == MoveItErrorCodes.GOAL_CONSTRAINTS_VIOLATED:
        return 'GOAL_CONSTRAINTS_VIOLATED'
    elif val == MoveItErrorCodes.INVALID_GROUP_NAME:
        return 'INVALID_GROUP_NAME'
    elif val == MoveItErrorCodes.INVALID_GOAL_CONSTRAINTS:
        return 'INVALID_GOAL_CONSTRAINTS'
    elif val == MoveItErrorCodes.INVALID_ROBOT_STATE:
        return 'INVALID_ROBOT_STATE'
    elif val == MoveItErrorCodes.INVALID_LINK_NAME:
        return 'INVALID_LINK_NAME'
    elif val == MoveItErrorCodes.INVALID_OBJECT_NAME:
        return 'INVALID_OBJECT_NAME'
    elif val == MoveItErrorCodes.FRAME_TRANSFORM_FAILURE:
        return 'FRAME_TRANSFORM_FAILURE'
    elif val == MoveItErrorCodes.COLLISION_CHECKING_UNAVAILABLE:
        return 'COLLISION_CHECKING_UNAVAILABLE'
    elif val == MoveItErrorCodes.ROBOT_STATE_STALE:
        return 'ROBOT_STATE_STALE'
    elif val == MoveItErrorCodes.SENSOR_INFO_STALE:
        return 'SENSOR_INFO_STALE'
    elif val == MoveItErrorCodes.NO_IK_SOLUTION:
        return 'NO_IK_SOLUTION'
    else:
        return 'UNKNOWN_ERROR_CODE'


class Arm(object):
    """Arm controls the robot's arm.

    Joint space control:
        joints = ArmJoints()
        # Fill out joint states
        arm = fetch_api.Arm()
        arm.move_to_joints(joints)
    """

    def __init__(self):
        # Create actionlib client
        self.client = actionlib.SimpleActionClient('arm_controller/follow_joint_trajectory',
                                                   FollowJointTrajectoryAction)
        self.moveClient = actionlib.SimpleActionClient('move_group', MoveGroupAction)
        self._compute_ik = rospy.ServiceProxy('compute_ik', GetPositionIK)
        self._tf_listener = TransformListener()
        # Wait for server
        self.client.wait_for_server()
        pass

    def check_pose(self,
                   pose_stamped,
                   allowed_planning_time=10.0,
                   group_name='arm',
                   tolerance=0.01):
        return self.move_to_pose(
            pose_stamped,
            allowed_planning_time=allowed_planning_time,
            group_name=group_name,
            tolerance=tolerance,
            plan_only=True)

    def move_to_pose(self,
                     pose_stamped,
                     allowed_planning_time=10.0,
                     execution_timeout=15.0,
                     group_name='arm',
                     num_planning_attempts=5,
                     plan_only=False,
                     replan=True,
                     replan_attempts=5,
                     tolerance=0.01,
                     orientation_constraint=None):
        """Moves the end-effector to a pose, using motion planning.

        Args:
            pose: geometry_msgs/PoseStamped. The goal pose for the gripper.
            allowed_planning_time: float. The maximum duration to wait for a
                planning result, in seconds.
            execution_timeout: float. The maximum duration to wait for
                an arm motion to execute (or for planning to fail completely),
                in seconds.
            group_name: string. Either 'arm' or 'arm_with_torso'.
            num_planning_attempts: int. The number of times to compute the same
                plan. The shortest path is ultimately used. For random
                planners, this can help get shorter, less weird paths.
            plan_only: bool. If True, then this method does not execute the
                plan on the robot. Useful for determining whether this is
                likely to succeed.
            replan: bool. If True, then if an execution fails (while the arm is
                moving), then come up with a new plan and execute it.
            replan_attempts: int. How many times to replan if the execution
                fails.
            tolerance: float. The goal tolerance, in meters.

        Returns:
            string describing the error if an error occurred, else None.
        """
        goal_builder = MoveItGoalBuilder()
        goal_builder.set_pose_goal(pose_stamped)
        goal_builder.allowed_planning_time = allowed_planning_time
        goal_builder.num_planning_attempts = num_planning_attempts
        goal_builder.plan_only = plan_only
        goal_builder.replan = replan
        goal_builder.replan_attempts = replan_attempts
        goal_builder.tolerance = tolerance
        if (orientation_constraint is not None):
            goal_builder.add_path_orientation_constraint(orientation_constraint)
        goal = goal_builder.build()

        # print "moving arm"
        self.moveClient.send_goal_and_wait(goal, rospy.Duration(execution_timeout))
        # print "arm moved"

        result = self.moveClient.get_result()

        if result.error_code.val == MoveItErrorCodes.SUCCESS:
            return None
        else:
            return moveit_error_string(result.error_code.val)

    def straight_move_to_pose(self,
                              group,
                              pose_stamped,
                              ee_step=0.025,
                              jump_threshold=2.0,
                              avoid_collisions=True):
        """Moves the end-effector to a pose in a straight line.
        Args:
          group: moveit_commander.MoveGroupCommander. The planning group for
            the arm.
          pose_stamped: geometry_msgs/PoseStamped. The goal pose for the
            gripper.
          ee_step: float. The distance in meters to interpolate the path.
          jump_threshold: float. The maximum allowable distance in the arm's
            configuration space allowed between two poses in the path. Used to
            prevent "jumps" in the IK solution.
          avoid_collisions: bool. Whether to check for obstacles or not.
        Returns:
            string describing the error if an error occurred, else None.
        """
        # Transform pose into planning frame
        self._tf_listener.waitForTransform(pose_stamped.header.frame_id,
                                           group.get_planning_frame(),
                                           rospy.Time.now(),
                                           rospy.Duration(1.0))
        try:
            pose_transformed = self._tf_listener.transformPose(
                group.get_planning_frame(), pose_stamped)
        except (tf.LookupException, tf.ConnectivityException):
            rospy.logerr('Unable to transform pose from frame {} to {}'.format(
                pose_stamped.header.frame_id, group.get_planning_frame()))
            return moveit_error_string(
                MoveItErrorCodes.FRAME_TRANSFORM_FAILURE)

        # Compute path
        plan, fraction = group.compute_cartesian_path(
            [group.get_current_pose().pose,
             pose_transformed.pose], ee_step, jump_threshold, avoid_collisions)
        if fraction < 1 and fraction > 0:
            rospy.logerr(
                'Only able to compute {}% of the path'.format(fraction * 100))
        if fraction == 0:
            return moveit_error_string(MoveItErrorCodes.PLANNING_FAILED)

        # Execute path
        result = group.execute(plan, wait=True)
        if not result:
            return moveit_error_string(MoveItErrorCodes.INVALID_MOTION_PLAN)
        else:
            return None

    def cancel_all_goals(self):
        self.client.cancel_all_goals()  # Your action client from Lab 7
        self.moveClient.cancel_all_goals()  # From this lab

    def move_to_joints(self, arm_joints):
        """Moves the robot's arm to the given joints.

        Args:
            arm_joints: An ArmJoints object that specifies the joint values for
                the arm.
        """
        # Create a trajectory point
        message = JointTrajectory()
        # Set position of trajectory point
        point = JointTrajectoryPoint()
        point.positions = arm_joints.values()
        # Set time of trajectory point
        point.time_from_start = rospy.Duration(TIME_FROM_START)
        message.points = [point]
        # Create goal
        goal = FollowJointTrajectoryGoal()
        # Add joint name to list
        message.joint_names = arm_joints.names()
        # Add the trajectory point created above to trajectory
        goal.trajectory = message

        # Send goal
        self.client.send_goal(goal)
        # Wait for result
        self.client.wait_for_result()

    def compute_ik(self, pose_stamped, timeout=rospy.Duration(5)):
        """Computes inverse kinematics for the given pose.

        Note: if you are interested in returning the IK solutions, we have
            shown how to access them.

        Args:
            pose_stamped: geometry_msgs/PoseStamped.
            timeout: rospy.Duration. How long to wait before giving up on the
                IK solution.

        Returns: True if the inverse kinematics were found, False otherwise.
        """
        request = GetPositionIKRequest()
        request.ik_request.pose_stamped = pose_stamped
        request.ik_request.group_name = 'arm'
        request.ik_request.timeout = timeout
        response = self._compute_ik(request)
        error_str = moveit_error_string(response.error_code.val)
        success = error_str == 'SUCCESS'
        if not success:
            return False
        joint_state = response.solution.joint_state
        for name, position in zip(joint_state.name, joint_state.position):
            if name in ArmJoints.names():
                rospy.loginfo('{}: {}'.format(name, position))
        return True

    def get_pose(self):
        listener = tf.TransformListener()
        listener.waitForTransform('base_link', 'wrist_roll_link', rospy.Time(), rospy.Duration(4.0))
        (p, q) = listener.lookupTransform('base_link', 'wrist_roll_link', rospy.Time(0))
        pose = Pose()
        pose.position = Point(p[0], p[1], p[2])
        pose.orientation = Quaternion(q[0], q[1], q[2], q[3])
        return pose
