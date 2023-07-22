import os

#wsgi_app = 'zoomrec_server_app:app'
bind = '0.0.0.0' +  ':' + os.getenv("API_PORT", "8080")
worker_class = 'sync'
loglevel = 'debug'
accesslog = os.path.join(os.getenv('HOME'),'gunicorn_access_log')
acceslogformat ="%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
errorlog =  os.path.join(os.getenv('HOME'),'gunicorn_error_log')