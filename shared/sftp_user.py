import syslog
import subprocess
import os

from pathlib import Path
from .constants import RECORDINGS_DIR, SFTP_DATA_PATH 

# Get the directory where this module is located
SCRIPT_DIR = Path(__file__).parent.absolute()
ZOOMREC_USER_GID = os.getenv('ZOOMREC_USER_GID')

def create_sftp_user( username):
    # execute script to create user
    command = [
        "sudo", f"{SCRIPT_DIR}/sftp_user_create.sh",
        f"{username}:::{ZOOMREC_USER_GID}:{RECORDINGS_DIR}", SFTP_DATA_PATH
    ]
    if  subprocess.call(command):
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_ERR, f"[{__name__}] Failed to create sftp user {username}")
        return False
    else:
        return True