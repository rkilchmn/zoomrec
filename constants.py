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
ZOOMREC_SERVER_APP_CONFIG_FILENAME = 'zoomrec_server_app.yaml'

# debugging
DEBUG_MODULE_ZOOMREC_SERVER_APP = 'zoomrec_server_app'
DEBUG_MODULE_ZOOMREC_CLIENT = 'zoomrec'
DEBUG_MODULE_IMAP_BOT = 'imap_bot'
DEBUG_MODULE_TELEGRAM_BOT = 'telegram_bot'
DEBUG_MODULE_ZOOMREC_SERVER = 'zoomrec_server'