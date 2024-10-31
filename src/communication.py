#!/usr/bin/env python3

# Attention: Do not import the ev3dev.ev3 module in this file
from dataclasses import dataclass
import json
import platform
import ssl
from typing import Tuple
from xmlrpc import client
import logging
import time

# make mqtt available
import paho.mqtt.client as mqtt

from planet import Direction

# Fix: SSL certificate problem on macOS
if all(platform.mac_ver()):
    from OpenSSL import SSL

class Communication:
    """
    Class to hold the MQTT client communication
    Feel free to add functions and update the constructor to satisfy your requirements and
    thereby solve the task according to the specifications
    """

    def __init__(self, mqtt_client, logger):
        """
        Initializes communication module, connect to server, subscribe, etc.
        :param mqtt_client: paho.mqtt.client.Client
        :param logger: logging.Logger
        """
        # DO NOT CHANGE THE SETUP HERE
        self.client = mqtt_client
        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        self.client.on_message = self.safe_on_message_handler
        # Add your client setup here
        
        # from example code with own data
        self.client.username_pw_set('022', password='y9DTnkXeHX')
        self.client.connect('mothership.inf.tu-dresden.de', port=8883)
        self.client.subscribe('explorer/022', qos=2)
        self.client.subscribe('controller/022', qos=2)
        self.client.subscribe('comtest/022', qos=2)

        # start the listening
        self.client.loop_start()

        # bind logger?
        self.logger = logger

        # prepare the data to be used
        self.planet_name = "" #= input('Please enter the name of your planet: ')

        # check variable for receiving msg
        self.ready_msg_rcv = False
        self.path_msg_rcv = False
        self.path_msg_rcv = False
        self.pathSel_msg_rcv = False
        self.pathUnv_msg_rcv = False
        self.target_msg_rcv = False
        self.done_msg_rcv = False
        self.path_status = "free"
        self.path_weight = 0
        self.unv_path_status = "free"
        self.unv_path_weight = 0

        # make position tuples available
        self.start_pos: Tuple[Tuple[int, int], Direction]
        self.end_pos: Tuple[Tuple[int, int], Direction]
        self.unv_start_pos: Tuple[Tuple[int, int], Direction]
        self.unv_end_pos: Tuple[Tuple[int, int], Direction]
        self.target_pos: Tuple[int, int]

        self.unv_paths = []

    # DO NOT EDIT THE METHOD SIGNATURE
    def on_message(self, client, data, message):
        """
        Handles the callback if any message arrived
        :param client: paho.mqtt.client.Client
        :param data: Object
        :param message: Object
        :return: void
        """
        data = json.loads(message.payload.decode('utf-8'))
        self.logger.debug(json.dumps(data, indent=2))

        #print('Got message with topic "{}":'.format(message.topic))

        # make data accessible
        self.data = data

        # check for which message is received and call respective function
        if self.data["from"] == "server":

            payload = self.data["payload"]

            if self.data["type"] == "planet":
                #print('Got a message for the testplanet. \n')
                self.planet_name = payload["planetName"]
                self.start_pos = (payload["startX"], payload["startY"]), payload["startOrientation"]
                self.client.subscribe('planet/{}/022'.format(self.planet_name))
                print(f"[COM] first node pos: {self.start_pos}")
                self.ready_msg_rcv = True

            elif data["type"] == "path":
                #print('Got a message for an updated path. \n')
                self.start_pos = (payload["startX"], payload["startY"]), payload["startDirection"]
                self.end_pos = (payload["endX"], payload["endY"]), payload["endDirection"]
                self.path_status = payload["pathStatus"]
                self.path_weight = payload["pathWeight"]
                print(f"[COM] path: start:{self.start_pos}, end:{self.end_pos}, status:{self.path_status}, weight: {self.path_weight}")
                self.path_msg_rcv = True

            elif data["type"] == "pathSelect":
                #print('got a message for pathselection. \n')
                start_coords, _ = self.start_pos
                self.start_pos = start_coords, payload["startDirection"]
                print(f"[COM] pathSelect: start: {self.start_pos}")
                self.pathSel_msg_rcv = True

            elif data["type"] == "pathUnveiled":
                #print('got a message for pathcorrection. \n')
                self.unv_start_pos = (payload["startX"],payload["startY"]), payload["startDirection"]
                self.unv_end_pos = (payload["endX"], payload["endY"]), payload["endDirection"]
                self.unv_path_status = payload["pathStatus"]
                self.unv_path_weight = payload["pathWeight"]

                self.unv_paths.append((self.unv_start_pos, self.unv_end_pos, self.unv_path_status, self.unv_path_weight))

                print(f"[COM] pathUnv: start:{self.unv_start_pos}, end:{self.unv_end_pos}, status:{self.unv_path_status}, weight: {self.unv_path_weight}")
                self.pathUnv_msg_rcv = True

            elif data["type"] == "target":
                #print('Finally a goal in life. \n')
                self.target_pos = payload["targetX"], payload["targetY"]
                print(f"NEW TARGET: {self.target_pos}")
                self.target_msg_rcv = True

            elif data["type"] == "done":
                print("[COM] finale has been confirmed.")
                print(payload["message"])
                self.done_msg_rcv = True

            elif data["type"] == "error":
                print("[COM] debug: {}".format(self.data["debug"]))
                print(payload["errors"])
        
        elif data["from"] == "debug":
            
            if data["type"] == "notice":
                print('active planet is actually {}.'.format(self.planet_name))
            
            elif data["type"] == "syntax":
                if self.data["message"] == "Correct":
                    print('all good!')
                    self.send_ready()
                else:
                    print(payload["errors"])
        elif data["from"] == "client":
            pass
        else:
            print('not set yet, go away \n' )

    # functions for generating messages
    def create_payload(self, **content):
        payload = {}

        for content_name, info in content.items():
            payload[content_name] = info

        return payload

    def create_message(self, topic, payload):
        message = {
            "from": "client",
            "type": topic,
            "payload" : payload
        }
        message = json.dumps(message)
        return message

    # DO NOT EDIT THE METHOD SIGNATURE
    #
    # In order to keep the logging working you must provide a topic string and
    # an already encoded JSON-Object as message.
    def send_message(self, topic, message):
        """
        Sends given message to specified channel
        :param topic: String
        :param message: Object
        :return: void
        """
        self.logger.debug('Send to: ' + topic)
        self.logger.debug(json.dumps(message, indent=2))

        # visualize what happens
        #print('Sending message with topic "{}".'.format(topic))
        print(f"[SEND] {message}")

        #actually send message
        self.client.publish(topic, payload = message, qos=2)

    # DO NOT EDIT THE METHOD SIGNATURE OR BODY
    #
    # This helper method encapsulated the original "on_message" method and handles
    # exceptions thrown by threads spawned by "paho-mqtt"
    def safe_on_message_handler(self, client, data, message):
        """
        Handle exceptions thrown by the paho library
        :param client: paho.mqtt.client.Client
        :param data: Object
        :param message: Object
        :return: void
        """
        try:
            self.on_message(client, data, message)
        except:
            import traceback
            traceback.print_exc()
            raise

    def send_testplanet(self):
        print("We're lost on a planet.")
        self.send_message("explorer/022", message = self.create_message("testplanet", payload = self.create_payload(planetName = self.planet_name))) 

    def send_ready(self):
        msgReady = {
            "from": "client",
            "type": "ready"
        }
        msgReady = json.dumps(msgReady)
        # send the ready message
        #print("We're ready to go!")
        self.send_message("explorer/022", msgReady)

    def send_path(self, start_pos, end_pos, path_status):
        # send the path message
        #print("We've come a long way.")
        # prepare data
        (start_x, start_y), start_direction = start_pos
        (end_x, end_y), end_direction = end_pos
        # actually send
        self.send_message("planet/{}/022".format(self.planet_name), 
        self.create_message("path", 
        self.create_payload(startX = start_x, startY = start_y, startDirection = start_direction, endX = end_x, endY = end_y, endDirection = end_direction, pathStatus = path_status)))

    def send_pathSelect(self, start_pos):
        # send the robo's select
        #print("The decision has been made.")
        # prepare data
        (start_x, start_y), start_direction = start_pos
        # actually send
        self.send_message("planet/{}/022".format(self.planet_name),
        self.create_message("pathSelect",
        self.create_payload(startX = start_x, startY = start_y, startDirection = start_direction)))

    def send_targetReached(self):
        # send notice, if target has been reached
        #print('Target has been reached.')
        self.send_message("explorer/022",
        self.create_message("targetReached",
        self.create_payload(message = "Found it!")))

    def send_explorationCompleted(self):
        # send notice, that all available paths have been scanned
        #print('100{} exploration progress.'.format('%'))
        self.send_message("explorer/022",
        self.create_message("explorationCompleted",
        self.create_payload(message = "I have all the Knowledge")))