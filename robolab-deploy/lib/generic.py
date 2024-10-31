#!/usr/bin/env python3

import os
import subprocess
import tempfile
import shutil
import io
import os.path
import socket
import uuid
from tarfile import TarFile
from pathlib import Path

SERVER_HOST = "localhost"
SERVER_PORT = 3838


def should_ignore(name):
    """
    Returns True if the given name (directory or file) should not be copied.
    :param name: String
    :return: bool
    """

    # Ignore python virtual envs or the python cache
    if name in ["venv", "__pycache__"]:
        return True

    # Ignore bytecode files
    if name.endswith(".pyc"):
        return True

    # Copy everything else
    return False


class Generic:
    """
    Generic parts of the deploy class that apply to all systems
    """

    def __init__(self, configure, base_path, bin_path, settings, exam):
        """
        Initializes deploy class and runs setup if necessary
        :param configure: bool
        :param base_path: Pathlib
        :param bin_path: Pathlib
        :param settings: Dict
        :param exam: bool
        """
        # Variables setup
        self.base_path = base_path
        self.bin_path = bin_path
        self.settings = settings
        self.ssh_key = bin_path.joinpath('brick_id_rsa')
        self.ssh_pub = bin_path.joinpath('brick_id_rsa.pub')

        self.tempdir = tempfile.TemporaryDirectory()
        self.tempdir_ssh_key = Path(self.tempdir.name) / "brick_id_rsa"
        self.tempdir_ssh_pub = Path(self.tempdir.name) / "brick_id_rsa.pub"
        self.tempdir_src = Path(self.tempdir.name) / "src"
        self.tempdir_trigger = Path(self.tempdir.name) / ".trigger"

        # Path setup
        self.src_path = self.base_path.joinpath(self.base_path.parent, 'src')
        self.log_path = self.base_path.joinpath(self.base_path.parent, 'logs')

        if configure or not self.ssh_key.exists():
            self.__setup_deploy()

        # The RoboLab project location might not have full permission support (NTFS mounted on linux, WSL, ...),
        # but SSH requires that the keys are not readable by other users
        # To get around this, we create a temporary directory which should ensure that permissions work as expected
        self.__init_tempdir()

        # Settings for Exam mode
        self.exam = exam
        self.src_prefix = "" if not self.exam else str(uuid.uuid4())

    def __init_tempdir(self):
        """
        Initializes a temporary directory for handling SSH keys and file permissions
        :return: void
        """
        shutil.copy(str(self.ssh_key), str(self.tempdir_ssh_key))
        shutil.copy(str(self.ssh_pub), str(self.tempdir_ssh_pub))

        os.chmod(str(self.tempdir_ssh_key), 0o600)
        os.chmod(str(self.tempdir_ssh_pub), 0o600)

        self.tempdir_trigger.touch()

    def __setup_deploy(self):
        """
        Generates and copies the SSH key to the brick
        :return: void
        """

        if not self.ssh_key.exists():
            subprocess.run(['ssh-keygen',
                            '-b', '4096',
                            '-t', 'rsa',
                            '-f', str(self.ssh_key),
                            '-q', '-N', ''
                            ])
            os.chmod(str(self.ssh_key), 0o600)
            os.chmod(str(self.ssh_pub), 0o600)
        print('Please enter the password if asked.')

        with self.ssh_pub.open("r") as f:
            ssh_pub_data = f.read()

        # do not use ssh-copy-id here, because on Windows git-bash,
        # ssh-copy-id is simply a bash shell script which subprocess.run of course cannot
        # start since it is not a windows executable (subprocess.run for ssh-copy-id produces
        # WinError 2 in that situation)
        subprocess.run([
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'IdentitiesOnly=yes',
            'robot@{}'.format(self.settings['ip']),
            "( cat ~/.ssh/authorized_keys; echo '{}' ) | sort -u > ~/.ssh/authorized_keys.$$ && mv ~/.ssh/authorized_keys.$$ ~/.ssh/authorized_keys".format(
                ssh_pub_data),
        ])
        print('Try to log into the brick:')
        print('\tssh -i {} robot@{}'.format(str(self.ssh_key), self.settings['ip']))

    def backup(self):
        """
        Backup existing files on the brick
        :return: void
        """
        print('Backing up old files...')

        # Connect with SSH-PubKey and execute backup script
        subprocess.run(
            ['ssh',
             '-i', str(self.tempdir_ssh_key),
             '-o', 'StrictHostKeyChecking=no',
             'robot@{}'.format(self.settings['ip']),
             'robolab-backup'
             ])

        print('Done.')

    def copy_files(self):
        """
        Copy local files to brick
        :return: void
        """
        print('Copying new files...')

        def filter(src, names):
            """
            Filter overwrite
            :param src: String
            :param names: String
            :return: List
            """
            return [name for name in names if should_ignore(name)]

        # Copy files into temporary directory first
        shutil.copytree(str(self.src_path), str(self.tempdir_src), ignore=filter)

        # Connect with SSH-PubKey and copy files
        subprocess.run(
            ['scp',
             '-i', str(self.tempdir_ssh_key),
             '-o', 'IdentitiesOnly=yes',
             '-o', 'StrictHostKeyChecking=no',
             '-r', "src",
             # this file must be copied last, it triggers the reloader on the brick
             ".trigger",
             'robot@{}:/home/robot/'.format(self.settings['ip'])
             ], cwd=str(self.tempdir.name), stdout=subprocess.DEVNULL)

        print('Done.')

    def copy_files_tar(self):
        """
        Copy local files to brick using tar
        :return: void
        """
        print('Copying new files with tar method...')
        out_stream = io.BytesIO(bytearray())
        tarfile = TarFile(fileobj=out_stream, mode="w")

        def filter(tar_info):
            """
            Filter overwrite
            :param tar_info: TarFile
            :return:
            """
            # set owner to robot user/group
            tar_info.uid = 1000
            tar_info.gid = 1000
            if should_ignore(os.path.basename(tar_info.name)):
                return None

            print(tar_info.name)
            return tar_info

        tarfile.add(self.src_path, "src", filter=filter)
        tarfile.close()

        try:
            with socket.socket() as s:
                s.connect((SERVER_HOST, SERVER_PORT))
                s.sendall(out_stream.getbuffer())
                s.close()
        except (ConnectionError, OSError):
            return False

        return True

    def sync_log(self):
        """"
        Sync tmux log files from the brick
        :return: void
        """
        print('Synchronizing log files...')

        # Recreate logs folder if not present
        if not os.path.exists(self.log_path):
            try:
                print('Recreate log folder...')
                os.mkdir(self.log_path)
            except:
                print('Something went wrong!')
                return

        # Connect with SSH-PubKey and synchronize files
        subprocess.run(
            ['scp',
             '-i', str(self.tempdir_ssh_key),
             '-o', 'IdentitiesOnly=yes',
             '-o', 'StrictHostKeyChecking=no',
             'robot@{}:/home/robot/logs/*.log'.format(self.settings['ip']),
             str(self.log_path)
             ])

        print('Done.')

    def start_session(self, port_forwarding=True):
        """
        Spawn or enter tmux session on brick
        :param port_forwarding: bool
        :return: void
        """
        print('Executing code by running main.run()...')
        print('This will open a tmux session...')
        print('Detach by pressing CTRL + B and then D')

        port_forwarding_args = [] if not port_forwarding else [
            "-L", "{port}:localhost:{port}".format(port=SERVER_PORT)
        ]

        exam_extra_command = ""
        if self.exam:
            exam_extra_command = "cp -r src src.$(date +'%s'); rm -rf src/*; cp -r {}/* src; ".format(self.src_prefix)

        # Connect with SSH-PubKey and execute tmux script
        subprocess.run(
            ['ssh',
             '-i', str(self.tempdir_ssh_key),
             ] + port_forwarding_args + [
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'IdentitiesOnly=yes',
                'robot@{}'.format(self.settings['ip']),
                '-t', '{}robolab-tmux'.format(exam_extra_command)
            ])

        print('Done.')

    def cleanup(self):
        self.tempdir.cleanup()
