#!/bin/bash
# Check if at least one parameter is passed
if [ $# -lt 1 ]; then
  echo "Error: At least one parameter is required."
  echo "Usage: $0 config_file"
  exit 1
fi

# Load configuration from file  
source $1

# environment variables used inside docker for internal API port
# SERVER_PORT=8080
# SSH_PORT=22

# defaults
docker stop zoomrec_server
docker rm $(docker ps -aqf "name=zoomrec_server")

docker run -d --restart unless-stopped --env-file $1 --name zoomrec_server \
    -v $ZOOMREC_HOME/zoomrec_server_db:/home/zoomrec/zoomrec_server_db \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -v $ZOOMREC_HOME/logs:/home/zoomrec/logs \
    -v $ZOOMREC_HOME/firmware:/home/zoomrec/firmware \
    -v /root/sftp-data:/root/sftp-data \
    -p $SERVER_PORT_EXPOSED:$SERVER_PORT \
    -p $SERVER_PORT_EXPOSED:$SERVER_PORT \
    -p $DEBUG_PORT:$DEBUG_PORT \
    rkilchmn/zoomrec_server:latest

    # docker run -d --restart unless-stopped --env-file $1 --name zoomrec_server \
    # -e DEBUG="$DEBUG" \
    # -e LOG_LEVEL="$LOG_LEVEL" \
    # -e TZ="$TZ" \
    # -e SERVER_PORT=$SERVER_PORT \
    # -e SERVER_USERNAME="$SERVER_USERNAME" \
    # -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    # -e IMAP_SERVER="$IMAP_SERVER" \
    # -e IMAP_PORT="$IMAP_PORT" \
    # -e IMAP_USERNAME="$IMAP_USERNAME" \
    # -e IMAP_PASSWORD="$IMAP_PASSWORD" \
    # -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    # -e TELEGRAM_BOT_ADMIN_USERIDS="$TELEGRAM_BOT_ADMIN_USERIDS" \
    # -v $ZOOMREC_HOME/zoomrec_server_db:/home/zoomrec/zoomrec_server_db \
    # -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    # -v $ZOOMREC_HOME/logs:/home/zoomrec/logs \
    # -v $ZOOMREC_HOME/firmware:/home/zoomrec/firmware \
    # -v /root/sftp-data:/root/sftp-data \
    # -p $SERVER_PORT_EXPOSED:$SERVER_PORT \
    # -p $SERVER_PORT_EXPOSED:22 \
    # -p 5679:5679 \
    # rkilchmn/zoomrec_server:latest