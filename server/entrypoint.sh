#!/bin/bash
set -e  # Exit on any error

# This command will run inetutils-syslogd in the background and start logging.
/etc/init.d/inetutils-syslogd start

# Configure SSH port (cant be done in docker as its runtime)
sed -i "s/#Port 22/Port ${DOCKER_SSH_PORT}/" /etc/ssh/sshd_config
service ssh start 

# ./create-sftp-user.sh sftpuser1

# within docker container this is the url   
SERVER_URL="http://localhost:${DOCKER_SERVER_PORT}"
export SERVER_URL

# Write environment variables to /etc/environment
# for executuon of pam_sftp.py these env vars need to be stored
# Ensure /etc/environment is writable
touch /etc/environment
echo "SERVER_URL=${SERVER_URL}" >> /etc/environment
echo "SERVER_USERNAME=${SERVER_USERNAME}" >> /etc/environment
echo "SERVER_PASSWORD=${SERVER_PASSWORD}" >> /etc/environment

# Start the main application with the application as user "zoomrec"
exec su zoomrec -p -c "source ${PYTHON_VENV_PATH}/bin/activate && python3 ${HOME}/zoomrec_server.py"