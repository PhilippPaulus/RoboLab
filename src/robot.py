import os
from time import sleep
import ev3dev.ev3 as ev3
import math
from typing import List, Tuple
from odometry import Odometry, Node
from planet import Direction

def grayscale(color: Tuple[int, int, int]):
    # weights: 30% red, 60% green, 10% blue
    return 0.3 * color[0] + 0.6 * color[1] + 0.1 * color[2]

def color_average(color1: Tuple[int, int, int], color2: Tuple[int, int, int]):
    return ((color1[0] + color2[0]) / 2, (color1[1] + color2[1]) / 2, (color1[2] + color2[2]) / 2)

def euclidian_diff(color1: Tuple[int, int, int], color2: Tuple[int, int, int]):
    return math.sqrt((color1[0] - color2[0])**2 + (color1[1] - color2[1])**2 + (color1[2] - color2[2])**2)

class Robot:

    def __init__(self):
        """
        Initializes robot module
        """
        
        self.K_PROPORTIONAL = 4.5 / 6
        self.K_DERIVATIVE = 0
        self.K_INTEGRAL = 0.11 / 6

        self.TACHO_PER_DEGREE = 2.03
        self.SENSOR_AXIS_DISTANCE = 6
        self.AXIS_LENGTH = 11.6
        self.WHEEL_DIAMETER = 5.6
        self.COLOR_ERROR = 50
        self.SPEED = 200

        # temp hardcode
        self.RED_NODE_COLOR = (126, 29, 55)#(165, 55, 75)
        self.BLUE_NODE_COLOR = (28, 100, 212)#(20, 88, 223)
        self.PATH_COLOR = (115, 161, 267)

        self.left_motor = ev3.Motor(ev3.OUTPUT_B)
        self.left_motor.reset()
        self.right_motor = ev3.Motor(ev3.OUTPUT_A)
        self.right_motor.reset()
        self.ultrasonic = ev3.UltrasonicSensor(ev3.INPUT_2)
        self.ultrasonic.mode = ev3.UltrasonicSensor.MODE_US_DIST_CM
        self.color_sensor = ev3.ColorSensor(ev3.INPUT_4)
        self.color_sensor.mode = ev3.ColorSensor.MODE_RGB_RAW
        self.wings = ev3.Motor(ev3.OUTPUT_C)
        self.wings.stop_action = ev3.Motor.STOP_ACTION_HOLD

        self.odometry = Odometry(self.WHEEL_DIAMETER, self.AXIS_LENGTH,
            self.left_motor.count_per_rot, self.right_motor.count_per_rot)
        
        self.PATH_COLOR_GRAYSCALE = grayscale(self.PATH_COLOR)

        # 0=left, 1=right
        self.led_brightness("0:green", 0)
        self.led_brightness("1:green", 0)
        self.led_brightness("0:red", 255)
        self.led_brightness("1:red", 255)

    def get_position(self):
        return self.odometry.position

    def set_position(self, position: Tuple[Tuple[int, int], Direction]):
        self.odometry.position = position

    def set_first_node(self, position: Tuple[int, int], node: Node):
        self.odometry.first_node = position, node

    def calibrate(self):
        answer = input("scan? (y/n)")
        if answer != "y":
            return

        input("place on red, confirm to scan")
        self.RED_NODE = self.scan_color(); print(f"red: {self.RED_NODE}")
        input("place on blue, confirm to scan")
        self.BLUE_NODE = self.scan_color(); print(f"blue: {self.BLUE_NODE}")
        input("place on white, confirm to scan")
        white = self.scan_color(); print(f"white: {white}")
        input("place on black/line, confirm to scan")
        black = self.scan_color(); print(f"black: {black}")
        self.PATH_COLOR = color_average(white, black)
        self.PATH_COLOR_GRAYSCALE = grayscale(self.PATH_COLOR)

    # own implmentation of wait_until_not_moving because if speed is already 0 wait_until_not_moving does not return
    def wait_for_stop(self, motors: List[ev3.Motor]):
        sleep(0.1)
        while True:
            for motor in motors:
                if motor.speed != 0:
                    break
            else:
                return
        
    def rotate(self, degrees: int, turn_left_side: bool = False, factor: float = 1):
        if turn_left_side:
            degrees = degrees % 360

        degrees *= factor

        # higher precision than with timing
        relative_position = degrees * self.TACHO_PER_DEGREE

        self.left_motor.run_to_rel_pos(speed_sp=self.SPEED, position_sp=relative_position)
        self.right_motor.run_to_rel_pos(speed_sp=self.SPEED, position_sp=-relative_position)

    def axis_correction(self, offset: float = 0, collect_data: bool = True):
        wheel_rotation = (self.SENSOR_AXIS_DISTANCE + offset) / (self.WHEEL_DIAMETER * math.pi)
        self.left_motor.run_to_rel_pos(speed_sp=self.SPEED, position_sp=-wheel_rotation*self.left_motor.count_per_rot)
        self.right_motor.run_to_rel_pos(speed_sp=self.SPEED, position_sp=-wheel_rotation*self.right_motor.count_per_rot)
        self.wait_for_stop([self.left_motor, self.right_motor])

        if collect_data:
            self.odometry.add_motor_data(self.left_motor, self.right_motor)

    def obstacle_signal(self):
        self.wings.run_to_rel_pos(speed_sp=700, position_sp=self.wings.count_per_rot*3)
        self.wait_for_stop([self.wings])

    def explore_path(self, direction: Direction) -> Node:
        print(f"explore: init dir: {int(self.odometry.get_direction())}, new dir: {int(direction)}")
        self.rotate(int(self.odometry.get_direction()) - int(direction), True, 0.85)
        self.wait_for_stop([self.left_motor, self.right_motor])

        self.align_line()

        self.odometry.set_direction(direction)

        # handle edge case: obstacle near node
        if self.ultrasonic.distance_centimeters <= 25:
            self.obstacle_signal()
            self.rotate(170)
            self.odometry.set_direction(Direction((int(self.odometry.get_direction()) - 180) % 360))
            return Node.INVALID

        return self.follow_line()

    def scan_directions(self):
        # prevent scanning of current line
        self.rotate(-45)
        self.wait_for_stop([self.left_motor, self.right_motor])

        direction_data = {}

        for i in range(len(Direction)):
            current_direction = Direction((int(self.odometry.get_direction()) - i * 90) % 360)
            direction_data[current_direction] = self.scan_line(90)

        # undo setup rotation
        self.rotate(45)
        self.wait_for_stop([self.left_motor, self.right_motor])

        return direction_data

    def scan_color(self) -> Tuple[int, int, int]:
        return self.color_sensor.bin_data("hhh")

    def scan_line(self, range_in_degrees: int):
        self.rotate(range_in_degrees)

        sleep(0.1)

        while True:
            if grayscale(self.scan_color()) <= 100:
                self.wait_for_stop([self.left_motor, self.right_motor])
                return True

            if self.left_motor.speed == 0 or self.right_motor.speed == 0:
                return False

    def detect_node(self, color = None) -> Node:
        if color == None:
            color = self.scan_color()

        red_diff = euclidian_diff(self.RED_NODE_COLOR, color)
        if red_diff <= self.COLOR_ERROR:
            return Node.RED
        
        blue_diff = euclidian_diff(self.BLUE_NODE_COLOR, color)
        if blue_diff <= self.COLOR_ERROR:
            return Node.BLUE

        return Node.INVALID

    def align_line(self):
        while True:
            color = self.scan_color()

            gray_value = grayscale(color)
            error = gray_value - self.PATH_COLOR_GRAYSCALE

            turn = error * self.K_PROPORTIONAL
            speed_left = turn
            speed_right = -turn

            self.left_motor.run_forever(speed_sp=speed_left)
            self.right_motor.run_forever(speed_sp=speed_right)

            if abs(turn) <= 2:
                break
    
    def find_lost_line(self):
        self.left_motor.stop()
        self.right_motor.stop()
        self.odometry.add_motor_data(self.left_motor, self.right_motor)

        self.rotate(-120)
        self.wait_for_stop([self.left_motor, self.right_motor])
        self.odometry.add_motor_data(self.left_motor, self.right_motor)

        self.align_line()
        self.odometry.add_motor_data(self.left_motor, self.right_motor)

    def follow_line(self, collect_data: bool = True) -> Node:
        """
        Follows the current line, returns RED or BLUE if successful,
        returns INVALID and returns to last node if path was blocked.
        """

        last_error = 0
        last_errors = [0]*50
        integral = 0

        huge_error_count = 0

        while True:
            if collect_data:
                self.odometry.add_motor_data(self.left_motor, self.right_motor)

            color = self.scan_color()

            gray_value = grayscale(color)
            error = gray_value - self.PATH_COLOR_GRAYSCALE
            derivate = error - last_error
            # integral = sum(last 50 errors)
            integral += -last_errors[0] + error
            last_errors.pop(0)
            last_errors.append(error)

            turn = error * self.K_PROPORTIONAL + derivate * self.K_DERIVATIVE + integral * self.K_INTEGRAL
            speed_left = -self.SPEED + turn
            speed_right = -self.SPEED - turn

            self.left_motor.run_forever(speed_sp=speed_left)
            self.right_motor.run_forever(speed_sp=speed_right)

            if abs(error) > 100:
                huge_error_count += 1

            # if there were 30 huge errors robot probably lost contact to the line
            if huge_error_count == 30:
                huge_error_count = 0
                self.find_lost_line()
                continue

            if abs(error) < 50:
                huge_error_count = 0

            if self.ultrasonic.distance_centimeters <= 10:
                self.left_motor.stop()
                self.right_motor.stop()

                self.obstacle_signal()

                self.rotate(90)
                self.wait_for_stop([self.left_motor, self.right_motor])
                self.align_line()
                self.follow_line()

                node = Node.INVALID
                break

            node = self.detect_node(color)

            if node != Node.INVALID:
                self.left_motor.stop()
                self.right_motor.stop()

                if node == Node.RED:
                    self.axis_correction(1.8, collect_data)
                elif node == Node.BLUE:
                    self.axis_correction(1.65, collect_data)

                if collect_data:
                    self.odometry.calculate(node)

                break
            
            last_error = error

        return node
    
    def com_end_signal(self):
        count = 0

        # 2 sec's
        while count < 10:
            self.led_brightness("0:red", (count % 2) * 255)
            self.led_brightness("1:red", (1 - (count % 2)) * 255)

            count += 1

            sleep(0.2)

        self.led_brightness("0:green", 0)
        self.led_brightness("1:green", 0)
        self.led_brightness("0:red", 255)
        self.led_brightness("1:red", 255)

    def victory_dance(self):
        self.wings.run_forever(speed_sp=700)
        self.left_motor.run_forever(speed_sp=300)
        self.right_motor.run_forever(speed_sp=-300)

        self.led_brightness("0:red", 0)
        self.led_brightness("1:red", 0)

        count = 0

         # 5 sec's
        while count < 25:
            self.led_brightness("0:green", (count % 2) * 255)
            self.led_brightness("1:green", (1 - (count % 2)) * 255)

            count += 1

            sleep(0.2)

        self.wings.stop()
        self.left_motor.stop()
        self.right_motor.stop()

    def led_brightness(self, name: str, brightness: int):
        try:
            handle = os.open(os.path.join(f"/sys/class/leds/led{name}:brick-status/brightness"), os.O_RDWR)
            os.write(handle, str(brightness).encode())
            os.lseek(handle, 0, os.SEEK_SET)
        except OSError as e:
            #print(e.strerror)
            return
