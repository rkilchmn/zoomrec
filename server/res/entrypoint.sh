#!/bin/bash
set -e  # Exit on any error

# This command will run inetutils-syslogd in the background and start logging.
/etc/init.d/inetutils-syslogd start

# Configure SSH port (cant be done in docker as its runtime)
sed -i "s/#Port 22/Port ${SSH_PORT}/" /etc/ssh/sshd_config
service ssh start 

# within docker container this is the url   
SERVER_URL="http://localhost:${SERVER_PORT}"
export SERVER_URL

# Write environment variables to /etc/environment
# for executuon of pam_sftp.py these env vars need to be stored
# Ensure /etc/environment is writable
touch /etc/environment
echo "SERVER_URL=${SERVER_URL}" >> /etc/environment
echo "SERVER_USERNAME=${SERVER_USERNAME}" >> /etc/environment
echo "SERVER_PASSWORD=${SERVER_PASSWORD}" >> /etc/environment

# Start temporal server with db backend --ui-ip 0.0.0.0 is to expose UI outside docker for debugging
/home/zoomrec/.temporalio/bin/temporal server start-dev \
  --search-attribute Event_Key=Keyword \
  --search-attribute Event_Title=Text \
  --search-attribute Event_Start=Datetime \
  --search-attribute Event_Start_Instance=Datetime \
  --search-attribute Event_Filename=Text \
  --ui-ip 0.0.0.0 \
  --db-filename ${HOME}/data/temporaldb-server \
  >> ${HOME}/data/logs/temporal-server_log.txt 2>&1 &

# Start the main application with the application as user "zoomrec"
exec su zoomrec -p -c "source ${PYTHON_VENV_PATH}/bin/activate && python3 ${HOME}/server/zoomrec_server.py"