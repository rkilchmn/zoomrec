#!/usr/bin/python3
import os
from shared.users_api import UserAPI
from shared.users import UserField
from shared import constants
from shared.sftp_user import create_sftp_user

# Get this is run as a subprocess from zoomrec_server and ZOOMREC_HOME is set

SERVER_URL       = os.getenv('SERVER_URL')
SERVER_USERNAME  = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD  = os.getenv('SERVER_PASSWORD')

def create_sftp_users():
    create_sftp_user(constants.SFTP_ADMIN_USERNAME)

    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
        sftp_users = user_api.get(filters=[[UserField.SFTP_USERNAME.value, '!=', '']])
    for sftp_user in sftp_users:
        create_sftp_user(sftp_user[UserField.SFTP_USERNAME.value])

if __name__ == '__main__':
    create_sftp_users()