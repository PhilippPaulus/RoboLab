# !/usr/bin/env python3

from enum import IntEnum, unique
import math
from typing import List, Tuple
import ev3dev.ev3 as ev3
from time import sleep, time
from planet import Direction

@unique
class Node(IntEnum):
    INVALID = -1
    RED = 0
    BLUE = 1

def distance_2d(vec1: Tuple[float, float], vec2: Tuple[float, float]):
    return math.sqrt((vec2[0] - vec1[0])**2 + (vec2[1] - vec1[1])**2)

class Odometry:

    def __init__(self, wheel_diameter: float, axis_length: float, count_per_rot_left: int, count_per_rot_right: int):
        """
        Initializes odometry module
        """

        self.position: Tuple[Tuple[int, int], Direction]
        self.first_node: Tuple[Tuple[int, int], Node]
        self.data: List[Tuple[int, int]] = []

        self.wheel_diameter = wheel_diameter
        self.axis_length = axis_length
        self.count_per_rot_left = count_per_rot_left
        self.count_per_rot_right = count_per_rot_right

    def get_direction(self):
        _, direction = self.position
        return direction

    def set_direction(self, direction: Direction):
        coords, _ = self.position
        self.position = coords, direction

    def add_motor_data(self, left_motor: ev3.Motor, right_motor: ev3.Motor):
        self.data.append((-left_motor.position, -right_motor.position))

    def round_by_node_grid(self, x: float, y: float, node: Node):
        first_node_coords, first_node = self.first_node

        # node type defined by x+y being even or uneven
        def get_node_type(node_coords: Tuple[int, int]):
            x, y = node_coords
            return (x + y) % 2
        
        first_node_type = get_node_type(first_node_coords)
        node_type = first_node_type if first_node == node else 1 - first_node_type

        # find same color nodes nearby
        nearby_nodes = [nearby_node for nearby_node in [(math.floor(x), math.floor(y)),
            (math.floor(x), math.ceil(y)), (math.ceil(x), math.floor(y)), (math.ceil(x), math.ceil(y))]
            if get_node_type(nearby_node) == node_type]

        return (nearby_nodes[0] if distance_2d(nearby_nodes[0], (x, y)) < distance_2d(nearby_nodes[1], (x, y))
            else nearby_nodes[1])

    def calculate(self, node: Node):
        (x, y), direction = self.position

        # Motor.count_per_rot = 360 by default, to be measured if inaccurate
        cm_per_degree_left = self.wheel_diameter * math.pi / self.count_per_rot_left
        cm_per_degree_right = self.wheel_diameter * math.pi / self.count_per_rot_right

        view_angle = math.radians(int(direction))
        delta_x: float = 0
        delta_y: float = 0

        for i in range(1, len(self.data)):
            prev_left_pos, prev_right_pos = self.data[i - 1]
            left_pos, right_pos = self.data[i]

            # delta_motor_pos * deg * cm/deg = distance * cm
            distance_left = (left_pos - prev_left_pos) * (self.count_per_rot_left / 360) * cm_per_degree_left
            distance_right = (right_pos - prev_right_pos) * (self.count_per_rot_right / 360) * cm_per_degree_right

            alpha = (distance_right - distance_left) / self.axis_length
            beta = alpha / 2

            s = (distance_left + distance_right) / -alpha * math.sin(-beta) if alpha != 0 else (distance_left + distance_right) / 2

            delta_x += math.sin(view_angle - beta) * s
            delta_y += math.cos(view_angle - beta) * s
            view_angle -= alpha

        self.data.clear()

        delta_x /= 50
        delta_y /= 50
        print(f"[ODOMETRY] moved approx. by ({delta_x}, {delta_y})")

        x += delta_x
        y += delta_y
        
        new_coords = self.round_by_node_grid(x, y, node)
        
        direction = math.degrees(view_angle) % 360
        direction = (round(direction / 90) * 90) % 360

        self.position = new_coords, Direction(direction)

        print(f"[ODOMETRY] new position: [{new_coords}, heading: {Direction(direction)}]")