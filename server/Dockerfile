# Use the official Python 3.8.10-slim base image
FROM python:3.8.10-slim

# Set an environment variable 
ENV HOME=/home/zoomrec \
    TZ=Europe/Berlin \
    DOCKER_API_PORT=8080 \
    SERVER_USERNAME="myuser" \
	SERVER_PASSWORD="mypassword" \
	FILENAME_MEETINGS_CSV="meetings_server.csv"

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
COPY zoomrec_server.yaml ${HOME}/


# Expose the specified port
EXPOSE $DOCKER_API_PORT

# Set the entrypoint to run the Python application with the specified port
ENTRYPOINT ["python"]

# Set the default command to run your application's main file with the specified port
CMD ["zoomrec_server.py"]
