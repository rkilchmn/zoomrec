import os

wsgi_app = 'zoomrec_server_app:app'
host = '0.0.0.0'
port = os.getenv("API_PORT", "8080")
worker_class = 'sync'
loglevel = 'debug'
accesslog = 'gunicorn_access_log'
acceslogformat ="%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
errorlog =  'gunicorn_error_log'