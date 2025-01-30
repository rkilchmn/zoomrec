# Use the official Python 3.8.10-slim base image
FROM python:3.8.10-slim

# this is the port within docker for the app server - can be mapped to different server on docker host 
ENV DOCKER_API_PORT=8000

# Set an environment variable 
ENV HOME=/home/zoomrec \
    TZ=Europe/Berlin \
    LOG_SUBDIR=log \
    SERVER_USERNAME="myuser" \
	SERVER_PASSWORD="mypassword" 

# Set the working directory in the container
WORKDIR ${HOME}

# Copy the requirements.txt file to the container
COPY server/requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files to the container
COPY zoomrec_server.py ${HOME}/ 
COPY zoomrec_server_app.py ${HOME}/
COPY gunicorn_conf.py ${HOME}/
COPY telegram_bot.py ${HOME}/
COPY imap_bot.py ${HOME}/
COPY events.py ${HOME}/
COPY events_api.py ${HOME}/
COPY users.py ${HOME}/
COPY users_api.py ${HOME}/
COPY msg_telegram.py ${HOME}/
COPY constants.py ${HOME}/
COPY zoomrec_server_app.yaml ${HOME}/


# Expose the specified port
EXPOSE $DOCKER_API_PORT

# Set the entrypoint to run the Python application with the specified port
ENTRYPOINT ["python"]

# Set the default command to run your application's main file with the specified port
CMD ["zoomrec_server.py"]
