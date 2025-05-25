import logging
import os
import sys
import signal
import subprocess
import atexit
import time
from pathlib import Path

# Now import from the shared package
from shared.constants import LOG_SERVER_FILENAME, DEBUG_MODULE_ZOOMREC_SERVER
from shared.utilities import start_logging, start_debug

start_logging(LOG_SERVER_FILENAME)
start_debug(DEBUG_MODULE_ZOOMREC_SERVER, os.getenv('DEBUG_PORT'))

SCRIPT_DIR = Path(__file__).parent.absolute()

def start_telegram_bot():
    
    command = ["python3", f"{SCRIPT_DIR}/telegram_bot.py"]
    telegram_bot = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        telegram_bot.pid), signal.SIGQUIT)  
    
    logging.info("Telegram bot process started")
    
def start_imap_bot():

    command = ["python3", f"{SCRIPT_DIR}/imap_bot.py"]
    imap_bot = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        imap_bot.pid), signal.SIGQUIT)
    
    logging.info("IMAP email bot process started")

def start_api_server():
    # Define the Gunicorn command   
    gunicorn_command = [
        'gunicorn',
        '-c',
        f"{SCRIPT_DIR}/gunicorn_conf.py",  # gunicorn config
        "server.zoomrec_server_app:app" # app module and app name
    ]

    # Start Gunicorn using the subprocess module
    # subprocess.call(gunicorn_command)
    api_server = subprocess.Popen(gunicorn_command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        api_server.pid), signal.SIGQUIT)
    
    logging.info("Gunicorn API server process started")

def create_sftp_users():
    command = ["python3", f"{SCRIPT_DIR}/create_sftp_users.py"]
    create_sftp_users = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        create_sftp_users.pid), signal.SIGQUIT)
    
    logging.info("SFTP users process started")

def main():

    # start bots
    start_imap_bot()
    start_telegram_bot()

    # start flask API app 
    start_api_server()

    # create sftp users
    time.sleep(3) # give time for API server to start
    create_sftp_users()
    
    # Run the bot until the user presses Ctrl-C
    while True:
        try:
            time.sleep(1)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                # Exit the program if the exception is a KeyboardInterrupt
                raise e

if __name__ == '__main__':
    main()
