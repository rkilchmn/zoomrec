import logging
import os
import signal
import subprocess
import atexit
from datetime import datetime
import debugpy

DEBUG = True if os.getenv('DEBUG') == 'True' else False

if DEBUG:
    debugpy.listen(("0.0.0.0", 5679))
    print("Waiting for debugger attach")
    debugpy.wait_for_client()
    print("Debugger attached")

# Get vars
BASE_PATH = os.getenv('ZOOMREC_HOME')

# Get the current date and time
now = datetime.now()

# Format the date and time in the desired format
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

# Create the log file name with the timestamp
LOG_DIR = os.path.join(BASE_PATH, os.getenv('LOG_SUBDIR'))
log_file = os.path.join(LOG_DIR, "{}.log".format(timestamp))

# Configure the logging
logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def start_telegram_bot():
    bot_log_file = open(f"{log_file}.telegram_bot", "w")
    
    command = f"python3 telegram_bot.py"
    telegram_bot = subprocess.Popen(
        command, stdout=bot_log_file, stderr=bot_log_file, shell=True, preexec_fn=os.setsid, universal_newlines=True, bufsize=1)

    atexit.register(os.killpg, os.getpgid(
        telegram_bot.pid), signal.SIGQUIT)  
    
    logging.info("Telegram bot started!")
    
def start_imap_bot():
    bot_log_file = open(f"{log_file}.imap_bot", "w")

    command = f"python3 imap_bot.py"
    imap_bot = subprocess.Popen(
        command, stdout=bot_log_file, stderr=bot_log_file, shell=True, preexec_fn=os.setsid, universal_newlines=True, bufsize=1)

    atexit.register(os.killpg, os.getpgid(
        imap_bot.pid), signal.SIGQUIT)
    
    logging.info("IMAP email bot started!")

def start_api_server():
    # Define the Gunicorn command   
    gunicorn_command = [
        'gunicorn',
        '-c',
        'gunicorn_conf.py',  # gunicorn config
        'zoomrec_server_app:app'
    ]

    # Start Gunicorn using the subprocess module
    subprocess.call(gunicorn_command)

def main():

    # this is the url in the server to access API
    os.environ['SERVER_URL'] = f"http://localhost:{os.getenv('DOCKER_API_PORT')}"
    logging.info(f"Setting environment variable SERVER_URL to '{os.getenv('SERVER_URL')}'")

    # start bots
    start_imap_bot()
    start_telegram_bot()

    # start flask API app / blocking - needs to be last
    start_api_server()

if __name__ == '__main__':
    main()
