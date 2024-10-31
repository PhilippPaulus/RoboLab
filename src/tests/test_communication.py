#!/usr/bin/env python3

import unittest.mock
import paho.mqtt.client as mqtt
import uuid

from communication import Communication


class TestRoboLabCommunication(unittest.TestCase):
    @unittest.mock.patch('logging.Logger')
    def setUp(self, mock_logger):
        """
        Instantiates the communication class
        """
        client_id = '022-' + str(uuid.uuid4())  # Replace YOURGROUPID with your group ID
        client = mqtt.Client(client_id=client_id,  # Unique Client-ID to recognize our program
                             clean_session=False,  # We want to be remembered
                             protocol=mqtt.MQTTv311  # Define MQTT protocol version
                             )

        # Initialize your data structure here
        self.communication = Communication(client, mock_logger)

    def test_message_ready(self):
        """
        This test should check the syntax of the message type "ready"
        """
        self.communication.send_ready()

    def test_message_path(self):
        """
        This test should check the syntax of the message type "path"
        """
        # set example positions
        self.communication.start_pos.x = 1
        self.communication.start_pos.y = 1
        self.communication.start_pos.direction = 0
        self.communication.end_pos.x = 2
        self.communication.end_pos.y = 2
        self.communication.end_pos.direction = 90
        self.communication.path_status = "free"
        self.communication.send_path(start_pos = self.communication.start_pos, end_pos = self.communication.end_pos, path_status =self.communication.path_status)


    def test_message_path_invalid(self):
        """
        This test should check the syntax of the message type "path" with errors/invalid data
        """
        self.communication.send_path(start_pos = self.communication.start_pos, end_pos = self.communication.end_pos, path_status =self.communication.path_status)


    def test_message_select(self):
        """
        This test should check the syntax of the message type "pathSelect"
        """
        self.communication.start_pos.x = 1
        self.communication.start_pos.y = 1
        self.communication.start_pos.direction = 0
        self.communication.send_pathSelect(start_pos = self.communication.start_pos)


    def test_message_complete(self):
        """
        This test should check the syntax of the message type "explorationCompleted" or "targetReached"
        """
        self.communication.send_targetReached()
        self.communication.send_explorationCompleted()



if __name__ == "__main__":
    unittest.main()
