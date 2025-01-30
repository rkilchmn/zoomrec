import os

#wsgi_app = 'zoomrec_server_app:app'
bind = '0.0.0.0' +  ':' + os.getenv("DOCKER_API_PORT", "8080")
worker_class = 'sync'
loglevel = 'debug'
LOG_DIR = os.path.join(os.getenv('ZOOMREC_HOME'), os.getenv('LOG_SUBDIR'))
accesslog = os.path.join(LOG_DIR,'gunicorn_access_log')
acceslogformat ="%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
errorlog =  os.path.join(LOG_DIR,'gunicorn_error_log')