FROM ubuntu:24.04

ARG PYTHON_VENV_PATH="/python/venv"

ENV DEBIAN_FRONTEND=noninteractive

# this is the port within docker for the app server - can be mapped to different server on docker host 
ENV DOCKER_API_PORT=8000

# Set an environment variable 
ENV HOME=/home/zoomrec \
    ZOOMREC_HOME=/home/zoomrec \
    TZ=Etc/UTC \
    SERVER_USERNAME="myuser" \
	SERVER_PASSWORD="mypassword" 

# Install Python and pip
RUN apt update && apt install -y python3-full

RUN mkdir -p ${PYTHON_VENV_PATH} && \
    python3 -m venv ${PYTHON_VENV_PATH}

ENV PATH=${PYTHON_VENV_PATH}/bin:$PATH

# Set the working directory in the container
WORKDIR ${HOME}

# Copy the requirements.txt file to the container
COPY server/requirements.txt ${HOME}/

# Install the Python dependencies
RUN cd ${PYTHON_VENV_PATH}/bin && \
    pip install --no-cache-dir -r ${HOME}/requirements.txt

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
COPY password.py ${HOME}/
COPY zoomrec_server_app.yaml ${HOME}/

# Copy and set up the startup script
COPY server/entrypoint.sh ${HOME}/
RUN chmod +x ${HOME}/entrypoint.sh

# Expose the specified port
EXPOSE $DOCKER_API_PORT

# Set the entrypoint to run the startup script
CMD ${HOME}/entrypoint.sh
