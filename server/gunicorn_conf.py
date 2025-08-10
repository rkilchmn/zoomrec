import os
from gunicorn import glogging  
from shared import constants

#wsgi_app = 'zoomrec_server_app:app'
bind = '0.0.0.0' + ':' + os.getenv("SERVER_PORT")
worker_class = 'sync'
loglevel = os.getenv("LOG_LEVEL", "INFO").lower()
keepalive = 30  # seconds
timeout = 300 # seconds - give ESP enough time to download new firmware

# logging setup
LOG_DIR = os.path.join(os.getenv('ZOOMREC_HOME'), constants.LOG_DIR)

# Reconfigure Gunicorn's access logger
accesslog = os.path.join(LOG_DIR, constants.LOG_GUNICORN_ACCESS_LOG_FILENAME)
# date format for access log is hardcoded in gunicorn to apache common log format %d/%b/%Y:%H:%M:%S %z
access_log_format = '%(t)s %(h)s %(l)s %(u)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Reconfigure Gunicorn's error logger
errorlog =  os.path.join(LOG_DIR, constants.LOG_GUNICORN_ERROR_LOG_FILENAME)
glogging.Logger.datefmt = constants.DATETIME_FORMAT_LOG