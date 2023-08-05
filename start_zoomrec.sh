#!/bin/bash
# Check if at least one parameter is passed
if [ $# -lt 1 ]; then
  echo "Error: At least one parameter is required."
  echo "Usage: $0 config_file GPU (AMD|INTEL|NVIDIA)"
  exit 1
fi

# Load configuration from file
source $1

docker stop zoomrec
docker rm $(docker ps -aqf "name=zoomrec")

if [[ "$2" == "AMD" ]]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  VIDEO_GROUPID=$(getent group video | cut -d':' -f3)

  docker run -d --restart unless-stopped --name zoomrec \
    -e DEBUG="$DEBUG" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e TZ="$TZ" \
    -e DISPLAY_NAME="$DISPLAY_NAME" \
    -e SAMBA_USER="$SAMBA_USER" \
    -e SAMBA_PASS="$SAMBA_PASS" \
    -e IMAP_SERVER="$IMAP_SERVER" \
    -e IMAP_PORT="$IMAP_PORT" \
    -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
    -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
    -e FFMPEG_OUTPUT_PARAMS="-acodec aac -b:a 128k -vaapi_device /dev/dri/renderD128 -vf 'hwupload,scale_vaapi=format=nv12' -c:v hevc_vaapi -b:v 1M" \
    -e LIBVA_DRIVER_NAME=radeonsi \
    -e SERVER_USERNAME="$SERVER_USERNAME" \
    -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    -e SERVER_URL="$SERVER_URL" \
    -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
    -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
    -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
    -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
    -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -p 5901:5901 \
    -p 137-139:137-139 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    --group-add="$VIDEO_GROUPID" \
    --group-add="$RENDER_GROUPID" \
    --device /dev/dri:/dev/dri \
    rkilchmn/zoomrec:latest

elif [[ "$2" == "INTEL" ]]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  VIDEO_GROUPID=$(getent group video | cut -d':' -f3)

  docker run -d --restart unless-stopped --name zoomrec \
    -e DEBUG="$DEBUG" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e TZ="$TZ" \
    -e DISPLAY_NAME="$DISPLAY_NAME" \
    -e SAMBA_USER="$SAMBA_USER" \
    -e SAMBA_PASS="$SAMBA_PASS" \
    -e IMAP_SERVER="$IMAP_SERVER" \
    -e IMAP_PORT="$IMAP_PORT" \
    -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
    -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
    -e FFMPEG_ENCODE="-acodec aac -b:a 128k -vaapi_device /dev/dri/renderD128 -vf 'hwupload,scale_vaapi=format=nv12' -c:v h264_vaapi -qp 24" \
    -e LIBVA_DRIVER_NAME=i965 \
    -e SERVER_USERNAME="$SERVER_USERNAME" \
    -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    -e SERVER_URL="$SERVER_URL" \
    -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
    -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
    -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
    -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
    -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -p 5901:5901 \
    --security-opt seccomp:unconfined \
    --group-add="$VIDEO_GROUPID" \
    --group-add="$RENDER_GROUPID" \
    --device /dev/dri/renderD128:/dev/dri/renderD128 \
    --device /dev/dri/card0:/dev/dri/card0 \
    rkilchmn/zoomrec:latest

elif [[ "$2" == "NVIDIA" ]]; then
  docker run -d --restart unless-stopped --name zoomrec \
    -e DEBUG="$DEBUG" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e TZ="$TZ" \
    -e DISPLAY_NAME="$DISPLAY_NAME" \
    -e SAMBA_USER="$SAMBA_USER" \
    -e SAMBA_PASS="$SAMBA_PASS" \
    -e IMAP_SERVER="$IMAP_SERVER" \
    -e IMAP_PORT="$IMAP_PORT" \
    -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
    -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
    -e FFMPEG_INPUT_PARAMS="-hwaccel cuvid" \
    -e FFMPEG_OUTPUT_PARAMS="-c:v hevc_nvenc -b:v 1M -gpu 0 -preset slow -acodec aac -b:a 128k" \
    -e SERVER_USERNAME="$SERVER_USERNAME" \
    -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    -e SERVER_URL="$SERVER_URL" \
    -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
    -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
    -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
    -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
    -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -p 5901:5901 \
    -p 137-139:137-139 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    --gpus all \
    rkilchmn/zoomrec:latest
else
  docker run -d --restart unless-stopped --name zoomrec \
    -e DEBUG="$DEBUG" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e TZ="$TZ" \
    -e DISPLAY_NAME="$DISPLAY_NAME" \
    -e SAMBA_USER="$SAMBA_USER" \
    -e SAMBA_PASS="$SAMBA_PASS" \
    -e IMAP_SERVER="$IMAP_SERVER" \
    -e IMAP_PORT="$IMAP_PORT" \
    -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
    -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
    -e SERVER_USERNAME="$SERVER_USERNAME" \
    -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    -e SERVER_URL="$SERVER_URL" \
    -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
    -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
    -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
    -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
    -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
    -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
    -p 5901:5901 \
    -p 137-139:137-139 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    rkilchmn/zoomrec:latest
fi
