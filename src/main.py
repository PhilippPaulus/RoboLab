#!/usr/bin/env python3

from typing import Tuple
import ev3dev.ev3 as ev3
import logging
import os
import paho.mqtt.client as mqtt
import uuid
import signal
from time import sleep

from communication import Communication
from odometry import Odometry, Node
from planet import Direction, Planet, Weight
from robot import Robot

client = None  # DO NOT EDIT

def run():
    # DO NOT CHANGE THESE VARIABLES
    #
    # The deploy-script uses the variable "client" to stop the mqtt-client after your program stops or crashes.
    # Your script isn't able to close the client after crashing.
    global client

    client_id = '022-' + str(uuid.uuid4())  # Replace YOURGROUPID with your group ID
    client = mqtt.Client(client_id=client_id,  # Unique Client-ID to recognize our program
                         clean_session=True,  # We want a clean session after disconnect or abort/crash
                         protocol=mqtt.MQTTv311  # Define MQTT protocol version
                         )
    log_file = os.path.realpath(__file__) + '/../../logs/project.log'
    logging.basicConfig(filename=log_file,  # Define log file
                        level=logging.DEBUG,  # Define default mode
                        format='%(asctime)s: %(message)s'  # Define default logging format
                        )
    logger = logging.getLogger('RoboLab')

    # THE EXECUTION OF ALL CODE SHALL BE STARTED FROM WITHIN THIS FUNCTION.
    # ADD YOUR OWN IMPLEMENTATION HEREAFTER.

    # initialize objects
    robot = Robot()
    robot.calibrate()
    planet = Planet()

    com = Communication(client, logger)
    #com.send_testplanet()

    # find first node and do routine
    node = robot.follow_line(False)
    com.send_ready()

    for _ in range(6):
        if com.ready_msg_rcv:
            com.ready_msg_rcv = False
            break
        sleep(0.5)

    print(f"initial pos: {com.start_pos}")
    robot.set_position(com.start_pos)

    first_node_coords, _ = com.start_pos
    robot.set_first_node(first_node_coords, node)

    coords, direction = robot.get_position()
    planet.add_node_scan(coords, robot.scan_directions())
    planet.add_explored_node(coords)
    planet.remove_direct(coords, Direction((int(direction) - 180) % 360))

    best_direction = planet.smartest_direction(coords)
    com.send_pathSelect((coords, best_direction))

    # TODO: use predicates to make wait loops redundant
    for _ in range(6):
        if com.pathSel_msg_rcv:
            com.pathSel_msg_rcv = False
            _, best_direction = com.start_pos
            break
        sleep(0.5)

    # main routine
    while True:
        print("\n")

        old_coords, old_direction = robot.get_position()
        old_direction = best_direction

        node = robot.explore_path(best_direction)

        new_coords, new_direction = robot.get_position()

        if old_coords in planet.get_paths().keys():
            if best_direction in planet.get_paths()[old_coords].keys():
                known_path = planet.get_paths()[old_coords][best_direction]
                new_coords, new_direction, _ = known_path
                new_direction = Direction((int(new_direction) - 180) % 360)

        path_status = "blocked" if node == Node.INVALID else "free"

        com.send_path((old_coords, old_direction), (new_coords, Direction((int(new_direction) - 180) % 360)), path_status)

        sleep(3)
        
        com.path_msg_rcv = False

        new_coords, new_direction = com.end_pos

        planet.add_path((old_coords, old_direction), (new_coords, new_direction), com.path_weight)
        robot.set_position((new_coords, Direction((int(new_direction) - 180) % 360)))

        if com.unv_paths:
            for unv_path in com.unv_paths:
                start_pos, end_pos, _, weight = unv_path
                start_coords, _ = start_pos
                end_coords, _ = end_pos

                planet.add_unveiled_node(start_coords)
                planet.add_unveiled_node(end_coords)
                planet.remove_unexplored_path(start_pos, end_pos)
                planet.add_path(start_pos, end_pos, weight)

            com.unv_paths.clear()

        if com.target_msg_rcv:
            com.target_msg_rcv = False
            planet.target = com.target_pos

        if planet.should_scan(new_coords):
            planet.add_node_scan(new_coords, robot.scan_directions())

        planet.add_explored_node(new_coords)
        planet.remove_unexplored_path((old_coords, old_direction), (new_coords, new_direction))

        best_direction = planet.smartest_direction(new_coords)
        print(f"smartest direction: {best_direction}")
        if best_direction is None:
            break

        com.send_pathSelect((new_coords, best_direction))
        for _ in range(6):
            if com.pathSel_msg_rcv:
                com.pathSel_msg_rcv = False
                _, best_direction = com.start_pos
                break
            sleep(0.5)
        
        robot.com_end_signal()

    # check reason for main loop break

    done = False

    if planet.on_target(new_coords):
        com.send_targetReached()
        for _ in range(6):
            if com.done_msg_rcv:
                com.done_msg_rcv = False
                done = True
                break
            sleep(0.5)

    if not done and planet.exploration_completed(new_coords):
        com.send_explorationCompleted()
        for _ in range(6):
            if com.done_msg_rcv:
                com.done_msg_rcv = False
                done = True
                break
            sleep(0.5)

    if not done:
        print("Seems like there was an error...")
        return

    # celebrates finished exploration
    print("Exploration completed!")
    robot.victory_dance()

# DO NOT EDIT
def signal_handler(sig=None, frame=None, raise_interrupt=True):
    if client and client.is_connected():
        client.disconnect()
    if raise_interrupt:
        raise KeyboardInterrupt()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    try:
        run()
        signal_handler(raise_interrupt=False)
    except Exception as e:
        signal_handler(raise_interrupt=False)
        raise e