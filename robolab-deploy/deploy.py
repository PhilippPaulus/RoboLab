#!/usr/bin/env python3

import argparse
import ipaddress
import json
import os
from pathlib import Path
import platform
import time

from lib.unix import Unix
from lib.windows import Windows


class Deploy:
    """
    Base class for RoboLab Deploy-Script
    """

    def __init__(self, configure=False, execute_only=True, backup=False, sync_log=False, start_session=True, tar=False,
                 exam=False):
        """
        Initializes Deploy-Script, creates all necessary folders and files, loads environment defaults
        :param configure: bool
        :param execute_only: bool
        :param backup: bool
        :param sync_log: bool
        :param start_session: bool
        :param tar: bool
        :param exam: bool
        """
        # Flags and variables setup
        self.configure = configure
        self.execute_only = execute_only
        self.backup = backup
        self.sync_log = sync_log
        self.start_session = start_session
        self.tar = tar
        self.exam = exam
        self.settings = dict()

        # Path and File setup
        self.base_path = Path(os.path.dirname(os.path.abspath(__file__)))
        self.bin_path = self.base_path.joinpath('.bin')
        self.bin_path.mkdir(mode=0o700, exist_ok=True)
        self.settings_file = self.bin_path.joinpath('settings.json')

        # Start re-configuration or create new one
        if self.configure or not self.settings_file.exists():
            self.__setup_deploy()
        # Load configuration
        with self.settings_file.open() as file:
            self.settings = json.load(file)

    def routine(self):
        """
        Handle flags and starts tmux session
        :return: void
        """
        if self.settings['os'] == 'Windows':
            system = Windows(self.configure,
                             self.base_path,
                             self.bin_path,
                             self.settings,
                             self.exam)
        else:
            system = Unix(self.configure,
                          self.base_path,
                          self.bin_path,
                          self.settings,
                          self.exam)

        try:
            if self.backup:
                system.backup()
                return

            if self.sync_log:
                system.sync_log()
                return

            if self.execute_only:
                if not self.tar or not system.copy_files_tar():
                    system.copy_files()

            if self.start_session:
                system.start_session()
        finally:
            system.cleanup()

        return

    def __setup_deploy(self):
        """
        Creates or updates Deploy-Script configuration
        :return: void
        """
        init_dict = dict()

        # Fetch and store platform
        init_dict['os'] = platform.system()
        # Fetch, validate and store target ip address
        while True:
            address = input('Please enter the IP address: ')
            try:
                ipaddress.ip_address(address)
                init_dict['ip'] = address
                break
            except Exception as error:
                print('Error: ', error)

        # Dump data into file
        self.settings_file.touch()
        with self.settings_file.open('w') as file:
            json.dump(init_dict, file, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--configure', help='Create new or reset current configuration', action='store_true')
    parser.add_argument(
        '-e', '--execute-only', help='Execute only without copying new files', action='store_false', default=True)
    parser.add_argument(
        '-b', '--backup', help='Create a remote backup of your files on the brick', action='store_true', default=False)
    parser.add_argument(
        '-s', '--sync-log', help='Synchronize log files from the brick', action='store_true', default=False)
    parser.add_argument(
        '-r', '--reload', help='Only copy files / reload, but do not start a new session', action="store_true",
        default=False)
    parser.add_argument(
        "-t", "--tar", help='Use the tar method to copy files (implies -r)', action='store_true', default=False)
    parser.add_argument(
        '-E', '--exam', help='Run in exam mode (clean src before executing)', action='store_true', default=False)
    args = parser.parse_args()

    print("Starting deploy at " + str(time.time()))

    try:
        print('If you need to change the IP address or your underlying OS, please run\n\t./deploy.py -c')
        deploy = Deploy(args.configure, args.execute_only, args.backup, args.sync_log, not args.reload and not args.tar,
                        args.tar, args.exam)
        deploy.routine()
    except Exception as e:
        print(e)
        raise
