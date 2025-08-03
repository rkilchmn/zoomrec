DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
DATETIME_FORMAT = DATE_FORMAT + ' ' + TIME_FORMAT
DURATION_FORMAT = '%H:%M:%S'
TIME_FORMAT_LOG = "%Y-%m-%d_%H-%M-%S"

# config directories 
CONFIG_DIR = 'config' # client/server
ARDUINO_FIRMWARE_DIR = 'config/arduino/firmware' # arduino firmware (server only)
ARDUINO_CONFIG_DIR = 'config/arduino/config' # arduino config (server only)

# data directories 
RECORDINGS_DIR = 'data/recordings' # recordings (client only)
LOG_DIR = 'data/logs' # logs (client/server)

# imap bot config
EMAIL_CONFIG_FILE = 'config/email_types.yaml' # email types (server only)

# automation config (client only)
AUTOMATION_DIR = 'automation' # automation (client only)
CLIENT_AUTOMATION_CONFIG_FILENAME = 'automation.yaml'
IMG_DIR = 'img' # default images for automation (client only)
AUDIO_DIR = 'config/automation/audio' # audio for automation (client only)
SCREENSHOT_DIR = 'data/logs/screenshots' # debug (client only)

# log file names
LOG_CLIENT_FILENAME = 'client_log.txt'
LOG_SERVER_FILENAME = 'server_log.txt'
LOG_IMAP_BOT_FILENAME = 'imap_bot_log.txt'
LOG_TELEGRAM_BOT_FILENAME = 'telegram_bot_log.txt'
LOG_GUNICORN_ACCESS_LOG_FILENAME = 'gunicorn_access_log.txt'
LOG_GUNICORN_ERROR_LOG_FILENAME = 'gunicorn_error_log.txt'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# sftp
SFTP_CONFIG_DIR = 'config/sftp' # sftp config (client/server)
SFTP_DATA_PATH = '/root/sftp-data' # mounted sftp data directory from host 
SFTP_ADMIN_USERNAME = 'zoomrec_admin'
SFTP_ADMIN_USER_IDENTITY_FILE = 'config/sftp/zoomrec_admin_id'    
SFTP_HOST_KEY_FILE = 'config/sftp/sftp_host_key'
SFTP_KNOWN_HOSTS_FILE = 'config/sftp/known_hosts'
SFTP_RECORDINGS_DIR = 'recordings'

# recording
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


