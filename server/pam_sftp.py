#!/usr/bin/python3
import syslog
import pam
import os
import sys
# PAM module needs to be able to import users_api and password
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from users_api import UserAPI
from password import verify_password
from users import UserField

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
        username = pamh.get(None)
        password = pamh.conversation(pamh.Message(pamh.PAM_PROMPT_ECHO_OFF, 'SSH client is conversation handler and asking for password')).resp

        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            sftp_user = user_api.get(filters=[[UserField.SFTP_USERNAME.value, '=', username]])[0]
        if sftp_user and verify_password(password, sftp_user[UserField.PASSWORD.value]):
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Authentication successful for {username}")
            return pam.PAM_SUCCESS
        else:
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Authentication failed for {username}")
            return pam.PAM_AUTH_ERR

    except Exception as e:
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"PAM[{__name__}] Error: {str(e)}")
        return pam.PAM_AUTH_ERR

def pam_sm_open_session(pamh, flags, argv):
    # creating user is too late her - it is checked before calling PAM
    username = pamh.get(None)
    syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Open session successful for {username}")

    return pamh.PAM_SUCCESS

def pam_sm_close_session(pamh, flags, argv):
    return pamh.PAM_SUCCESS

def pam_sm_setcred(pamh, flags, argv):
    return pamh.PAM_SUCCESS

def pam_sm_acct_mgmt(pamh, flags, argv):
    username = pamh.get(None)
    syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, f"PAM[{__name__}] Account management successful for {username}")
    return pamh.PAM_SUCCESS

def pam_sm_chauthtok(pamh, flags, argv):
    return pamh.PAM_SUCCESS