import syslog
import subprocess
import constants

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