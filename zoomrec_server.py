import logging
import os
import signal
import subprocess
import atexit
import debugpy
import time
from constants import LOG_SERVER_FILENAME
from utilities import start_logging

DEBUG = True if os.getenv('DEBUG','') == 'zoomrec_server' else False

if DEBUG:
    debugpy.listen(("0.0.0.0", 5679))
    print("Waiting for debugger attach")
    debugpy.wait_for_client()
    print("Debugger attached")

start_logging(LOG_SERVER_FILENAME)
logging.info("Starting Zoomrec Server")

def start_telegram_bot():
    
    command = ["python3", "telegram_bot.py"]
    telegram_bot = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        telegram_bot.pid), signal.SIGQUIT)  
    
    logging.info("Telegram bot process started")
    
def start_imap_bot():

    command = ["python3", "imap_bot.py"]
    imap_bot = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        imap_bot.pid), signal.SIGQUIT)
    
    logging.info("IMAP email bot process started")

def start_api_server():
    # Define the Gunicorn command   
    gunicorn_command = [
        'gunicorn',
        '-c',
        'gunicorn_conf.py',  # gunicorn config
        'zoomrec_server_app:app'
    ]

    # Start Gunicorn using the subprocess module
    # subprocess.call(gunicorn_command)
    api_server = subprocess.Popen(gunicorn_command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        api_server.pid), signal.SIGQUIT)
    
    logging.info("Gunicorn API server process started")

def create_sftp_users():
    command = ["python3", "pam_sftp.py"]
    create_sftp_users = subprocess.Popen(command, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        create_sftp_users.pid), signal.SIGQUIT)
    
    logging.info("SFTP users process started")

def main():

    # this is the url in the server to access API - no done in entrypoint.sh
    # os.environ['SERVER_URL'] = f"http://localhost:{os.getenv('DOCKER_API_PORT')}"
    # logging.info(f"Setting environment variable SERVER_URL to '{os.getenv('SERVER_URL')}'")

    # start bots
    start_imap_bot()
    start_telegram_bot()

    # start flask API app / blocking - needs to be last
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
