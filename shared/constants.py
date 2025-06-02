DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
DATETIME_FORMAT = DATE_FORMAT + ' ' + TIME_FORMAT
DURATION_FORMAT = '%H:%M:%S'
TIME_FORMAT_LOG = "%Y-%m-%d_%H-%M-%S"

# directories 
SFTP_DATA_PATH = '/root/sftp-data'
RECORDINGS_DIR = 'recordings'
AUDIO_DIR = 'audio'
IMG_DIR = 'img'
LOG_DIR = 'logs'
DEBUG_DIR = 'screenshots'
FIRMWARE_DIR = 'firmware'

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
ZOOMREC_DB_FILENAME = 'zoomrec_server_db'

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

# server routes
ROUTE_EVENT = "/event"
ROUTE_EVENT_NEXT = "next"
ROUTE_USER = "/user"
ROUTE_FIRMWARE = "/firmware"
ROUTE_LOG = "/log"

# stale event thresholds in seconds
STALE_EVENT_THRESHOLD_SECS = 60 * 60 * 2 # 2h 


