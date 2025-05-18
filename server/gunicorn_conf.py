import os
import constants

#wsgi_app = 'zoomrec_server_app:app'
bind = '0.0.0.0' + ':' + os.getenv("SERVER_PORT")
worker_class = 'sync'
loglevel = 'debug'
keepalive = 30  # seconds
timeout = 120 # seconds - give ESP enough time to download new firmware

LOG_DIR = os.path.join(os.getenv('ZOOMREC_HOME'), constants.LOG_DIR)
accesslog = os.path.join(LOG_DIR, constants.LOG_GUNICORN_ACCESS_LOG_FILENAME)
accesslogformat ="%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
errorlog =  os.path.join(LOG_DIR, constants.LOG_GUNICORN_ERROR_LOG_FILENAME)
errorlogformat ="%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
