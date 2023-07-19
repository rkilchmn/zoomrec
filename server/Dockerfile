# Use the official Python 3.8.10-slim base image
FROM python:3.8.10-slim

# Set an environment variable 
ENV HOME=/home/zoomrec \
    TZ=Europe/Berlin \
    API_PORT=8080 \
    API_USERNAME="myuser" \
	API_PASSWORD="mypassword"

# Set the working directory in the container
WORKDIR ${HOME}

# Copy the requirements.txt file to the container
COPY server/requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files to the container
COPY zoomrec_server.py . \
    zoomrec_server_app.py . \
    gunicorn_conf.py . \
    telegram_bot.py . \
    imap_bot.py . \
    events.py .

# Expose the specified port
EXPOSE $API_PORT

# Set the entrypoint to run the Python application with the specified port
ENTRYPOINT ["python"]

# Set the default command to run your application's main file with the specified port
CMD ["zoomrec_server.py"]
