#!/usr/bin/python3
import syslog
import subprocess
import os
from users_api import get_user_api
from users import UserField
import constants

# Get this is run as a subprocess from zoomrec_server and ZOOMREC_HOME is set

SERVER_URL       = os.getenv('SERVER_URL')
SERVER_USERNAME  = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD  = os.getenv('SERVER_PASSWORD')

def create_sftp_user( username):
    # execute script to create user
    # 1999 is the GID if the "zoomrec" group
    command = [
        "sudo", "/home/zoomrec/create-sftp-user.sh",
        f"{username}:::1999:{constants.RECORDINGS_DIR}", constants.SFTP_DATA_PATH
    ]
    if  subprocess.call(command):
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"[{__name__}] Failed to create sftp user {username}")
        return False
    else:
        return True

def create_sftp_users():
    create_sftp_user(constants.SFTP_ADMIN_USERNAME)

    sftp_users = get_user_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, filters=[[UserField.SFTP_USERNAME.value, '!=', '']])
    for sftp_user in sftp_users:
        create_sftp_user(sftp_user[UserField.SFTP_USERNAME.value])

if __name__ == '__main__':
    create_sftp_users()