DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
DATETIME_FORMAT = DATE_FORMAT + ' ' + TIME_FORMAT
DURATION_FORMAT = '%H:%M:%S'
TIME_FORMAT_LOG = "%Y-%m-%d_%H-%M-%S"

# directories 
SFTP_DATA_PATH = '/root/sftp-data' # mounted sftp data directory from host 
RECORDINGS_DIR = 'data/recordings' # mounted recordings directory from host 
AUDIO_DIR = 'config/audio' # mounted audio directory from host 
IMG_DIR = 'img' # main image directory from docker image 
CONFIG_IMG_DIR = 'config/img' # mounted image directory from host 
LOG_DIR = 'data/logs' # mounted log directory from host 
DEBUG_DIR = 'data/logs/screenshots' # mounted debug directory from host 
ARDUINO_FIRMWARE_DIR = 'config/arduino/firmware' # mounted arduino firmware directory from host 
ARDUINO_CONFIG_DIR = 'config/arduino/config' # mounted arduino config directory from host 

# imap bot config
EMAIL_CONFIG_FILE = 'config/email_types.yaml'

# client automation config
CLIENT_AUTOMATION_CONFIG_DIR = 'config'
CLIENT_AUTOMATION_CONFIG_FILENAME = 'zoom_auto.yaml'

# log file names
LOG_CLIENT_FILENAME = 'client_log.txt'
LOG_SERVER_FILENAME = 'server_log.txt'
LOG_IMAP_BOT_FILENAME = 'imap_bot_log.txt'
LOG_TELEGRAM_BOT_FILENAME = 'telegram_bot_log.txt'
LOG_GUNICORN_ACCESS_LOG_FILENAME = 'gunicorn_access_log.txt'
LOG_GUNICORN_ERROR_LOG_FILENAME = 'gunicorn_error_log.txt'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# OTHER
SFTP_ADMIN_USERNAME = 'zoomrec_admin'
SSH_IDENTITY_FILE = '.ssh/id_rsa'
VIDEO_EXTENSION = 'mkv'

# gunicorn api server
ZOOMREC_DB_FILENAME = 'data/zoomrec_server_db'

# debugging
DEBUG_MODULE_ZOOMREC_SERVER_APP = 'zoomrec_server_app'
DEBUG_MODULE_ZOOMREC_CLIENT = 'zoomrec_client'
DEBUG_MODULE_IMAP_BOT = 'imap_bot'
DEBUG_MODULE_TELEGRAM_BOT = 'telegram_bot'
DEBUG_MODULE_ZOOMREC_SERVER = 'zoomrec_server'

# terminal dimensions
TERMINAL_WIDTH = 85
TERMINAL_HEIGHT = 7

# intervals in seconds
INTERVAL_CHECK_NEXT_EVENT = 15
INTERVAL_CHECK_MEETING_ONGOING = 5

# arduino 
ARDUINO_CONFIG_EXTENSION = '.json'
ARDUINO_FIRMWARE_EXTENSION = '.ino.bin'

# server routes
ROUTE_EVENT = "/event"
ROUTE_EVENT_NEXT = "next"
ROUTE_USER = "/user"
ROUTE_FIRMWARE = "/firmware"
ROUTE_LOG = "/log"
ROUTE_CONFIG = "/config"

# stale event thresholds in seconds
STALE_EVENT_THRESHOLD_SECS = 60 * 60 * 2 # 2h 

# environment variables to suppress sftp user creation for debugging in non docker environment
SKIP_SFTP_USER_CREATION = 'SKIP_SFTP_USER_CREATION'


