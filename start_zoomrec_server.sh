#!/bin/bash
# Check if at least one parameter is passed
if [ $# -lt 1 ]; then
  echo "Error: At least one parameter is required."
  echo "Usage: $0 config_file"
  exit 1
fi

# Load configuration from file
source $1

# environment variables used inside docker
DOCKER_API_PORT=8080
LOG_SUBDIR=logs
FIRMWARE_SUBDIR=firmware

docker stop zoomrec_server
docker rm $(docker ps -aqf "name=zoomrec_server")

docker run -d --restart unless-stopped --name zoomrec_server \
    -e DOCKER_API_PORT=$DOCKER_API_PORT \
    -e SERVER_USERNAME=$SERVER_USERNAME \
    -e SERVER_PASSWORD=$SERVER_PASSWORD \
    -e LOG_SUBDIR=$LOG_SUBDIR \
    -e FIRMWARE_SUBDIR=$FIRMWARE_SUBDIR \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e TZ="$TZ" \
    -e IMAP_SERVER="$IMAP_SERVER" \
    -e IMAP_PORT="$IMAP_PORT" \
    -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
    -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
    -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -v $ZOOMREC_HOME/$LOG_SUBDIR:/home/zoomrec/$LOG_SUBDIR \
    -v $ZOOMREC_HOME/$FIRMWARE_SUBDIR:/home/zoomrec/$FIRMWARE_SUBDIR \
    -p 8080:$DOCKER_API_PORT \
    rkilchmn/zoomrec_server:latest
