#!/usr/bin/python3
import syslog
import pam
import subprocess
import os
import sys
# PAM module needs to be able to import users_api and password
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from users_api import get_user_api
from password import verify_password
from users import UserField
import constants

# # Sample user database (can be replaced with a DB or API call)
# USER_DB = {
#     "sftpuser1": "password123",
#     "zoomrec_admin": "admin123"
# }

# Get this is run as a subprocess from zoomrec_server and ZOOMREC_HOME is set

def load_env_variables():
    env_file = "/etc/environment"
    with open(env_file, "r") as f:
        for line in f:
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip()

load_env_variables()
SERVER_URL  = os.getenv('SERVER_URL')
SERVER_USERNAME  = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD  = os.getenv('SERVER_PASSWORD')

def pam_sm_authenticate(pamh, flags, argv):
    try:
        username = pamh.get_user(None)
        password = pamh.conversation(pamh.Message(pamh.PAM_PROMPT_ECHO_OFF, 'SSH client is conversation handler and asking for password')).resp

        sftp_user = get_user_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, filters=[[UserField.SFTP_USERNAME.value, '=', username]])[0]
        if sftp_user and verify_password(password, sftp_user[UserField.PASSWORD.value]):
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Authentication successful for {username}")
            return pam.PAM_SUCCESS
        else:
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Authentication failed for {username}")
            return pam.PAM_AUTH_ERR

        # creating user is too late her - it is checked before calling PAM
        # # execute script to create user
        # if subprocess.call(["/home/zoomrec/create-sftp-user.sh", username]):
        #     syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Failed to create user {username}")
        #     return pam.PAM_AUTH_ERR

        # # Validate credentials
        # if username in USER_DB and USER_DB[username] == password:
        #     syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Authentication successful for {username}")
        #     return pam.PAM_SUCCESS
        # else:
        #     syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Authentication failed for {username}")
        #     return pam.PAM_AUTH_ERR``
    except Exception as e:
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Error: {str(e)}")
        return pam.PAM_AUTH_ERR

def pam_sm_open_session(pamh, flags, argv):
    # creating user is too late her - it is checked before calling PAM
    username = pamh.get_user(None)
    syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Open session successful for {username}")

    return pamh.PAM_SUCCESS

def pam_sm_close_session(pamh, flags, argv):
    return pamh.PAM_SUCCESS

def pam_sm_setcred(pamh, flags, argv):
    return pamh.PAM_SUCCESS

def pam_sm_acct_mgmt(pamh, flags, argv):
    username = pamh.get_user(None)
    syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Account management successful for {username}")
    return pamh.PAM_SUCCESS

def pam_sm_chauthtok(pamh, flags, argv):
    return pamh.PAM_SUCCESS

def create_sftp_user( username):
    # execute script to create user
    # 1999 is the GID if the "zoomrec" group
    command = [
        "sudo", "/home/zoomrec/create-sftp-user.sh",
        f"{username}:::1999:recordings", constants.SFTP_DATA_PATH
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