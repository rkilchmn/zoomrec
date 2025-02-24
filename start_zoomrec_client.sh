#!/bin/bash

# possible values for GPU Acceleration
VAAPI="VAAPI"
NVIDIA="NVIDIA"

# Check if at least one parameter is passed
if [ $# -lt 1 ]; then
  echo "Error: At least one parameter is required."
  echo "Usage: $0 config_file $VAAPI|$NVIDIA"
  exit 1
fi

if [ -n "$2" ]; then
  # Check if the provided GPU is either VAAPI or NVIDIA
  if [ "$2" != "$VAAPI" ] && [ "$2" != "$NVIDIA" ]; then
    echo "Error: Invalid GPU acceleration specified."
    echo "GPU must be either $VAAPI or $NVIDIA."
    exit 1
  fi
fi

# Load configuration from file
source $1

docker stop zoomrec_client
docker rm $(docker ps -aqf "name=zoomrec_client")

if [[ "$2" == "$VAAPI" ]]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  VIDEO_GROUPID=$(getent group video | cut -d':' -f3)

  docker run -d --restart unless-stopped --name zoomrec_client \
    -e CLIENT_ID="$CLIENT_ID" \
    -e DEBUG="$DEBUG" \
    -e LOG_LEVEL="$LOG_LEVEL" \
    -e TZ="$TZ" \
    -e DISPLAY_NAME="$DISPLAY_NAME" \
    -e SAMBA_USER="$SAMBA_USER" \
    -e SAMBA_PASS="$SAMBA_PASS" \
    -e FFMPEG_INPUT_PARAMS="-vaapi_device /dev/dri/renderD128" \
    -e FFMPEG_OUTPUT_PARAMS="-acodec aac -b:a 128k -vf 'hwupload,scale_vaapi=format=nv12' -c:v hevc_vaapi -b:v 1M" \
    -e LIBVA_DRIVER_NAME="$LIBVA_DRIVER_NAME" \
    -e SERVER_USERNAME="$SERVER_USERNAME" \
    -e SERVER_PASSWORD="$SERVER_PASSWORD" \
    -e SERVER_URL="$SERVER_URL" \
    -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
    -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
    -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
    -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
    -p 5678:5678 \
    -p 5901:5901 \
    -p 137-138:137-138 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    --group-add="$VIDEO_GROUPID" \
    --group-add="$RENDER_GROUPID" \
    -v /mnt/wslg:/mnt/wslg \
    --device /dev/dri:/dev/dri \
    -v /usr/lib/wsl:/usr/lib/wsl \
    --device=/dev/dxg \
    -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
    --add-host=host.docker.internal:host-gateway \
    rkilchmn/zoomrec_client:latest

# if [[ "$2" == "AMD" ]]; then
#   RENDER_GROUPID=$(getent group render | cut -d':' -f3)
#   VIDEO_GROUPID=$(getent group video | cut -d':' -f3)

#   docker run -d --restart unless-stopped --name zoomrec_client \
#     -e DEBUG="$DEBUG" \
#     -e LOG_LEVEL="$LOG_LEVEL" \
#     -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
#     -e TZ="$TZ" \
#     -e DISPLAY_NAME="$DISPLAY_NAME" \
#     -e SAMBA_USER="$SAMBA_USER" \
#     -e SAMBA_PASS="$SAMBA_PASS" \
#     -e IMAP_SERVER="$IMAP_SERVER" \
#     -e IMAP_PORT="$IMAP_PORT" \
#     -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
#     -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
#     -e FFMPEG_OUTPUT_PARAMS="-acodec aac -b:a 128k -vaapi_device /dev/dri/renderD128 -vf 'hwupload,scale_vaapi=format=nv12' -c:v hevc_vaapi -b:v 1M" \
#     -e LIBVA_DRIVER_NAME=radeonsi \
#     -e SERVER_USERNAME="$SERVER_USERNAME" \
#     -e SERVER_PASSWORD="$SERVER_PASSWORD" \
#     -e SERVER_URL="$SERVER_URL" \
#     -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
#     -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
#     -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
#     -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
#     -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
#     -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
#     -p 5901:5901 \
#     -p 137-139:137-139 \
#     -p 445:445 \
#     --security-opt seccomp:unconfined \
#     --group-add="$VIDEO_GROUPID" \
#     --group-add="$RENDER_GROUPID" \
#     --device /dev/dri:/dev/dri \
#     rkilchmn/zoomrec_client:latest

# elif [[ "$2" == "INTEL" ]]; then
#   RENDER_GROUPID=$(getent group render | cut -d':' -f3)
#   VIDEO_GROUPID=$(getent group video | cut -d':' -f3)

#   docker run -d --restart unless-stopped --name zoomrec_client \
#     -e DEBUG="$DEBUG" \
#     -e LOG_LEVEL="$LOG_LEVEL" \
#     -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
#     -e TZ="$TZ" \
#     -e DISPLAY_NAME="$DISPLAY_NAME" \
#     -e SAMBA_USER="$SAMBA_USER" \
#     -e SAMBA_PASS="$SAMBA_PASS" \
#     -e IMAP_SERVER="$IMAP_SERVER" \
#     -e IMAP_PORT="$IMAP_PORT" \
#     -e EMAIL_ADDRESS="$EMAIL_ADDRESS" \
#     -e EMAIL_PASSWORD="$EMAIL_PASSWORD" \
#     -e FFMPEG_INPUT_PARAMS="-vaapi_device /dev/dri/renderD128" \
# 		-e FFMPEG_OUTPUT_PARAMS="-vf 'hwupload,scale_vaapi=format=nv12' -acodec aac -b:a 128k -c:v h264_vaapi -qp 24" \
#     -e LIBVA_DRIVER_NAME="$LIBVA_DRIVER_NAME" \
#     -e SERVER_USERNAME="$SERVER_USERNAME" \
#     -e SERVER_PASSWORD="$SERVER_PASSWORD" \
#     -e SERVER_URL="$SERVER_URL" \
#     -e LEAD_TIME_SEC="$LEAD_TIME_SEC" \
#     -e TRAIL_TIME_SEC="$TRAIL_TIME_SEC" \
#     -v $ZOOMREC_HOME/recordings:/home/zoomrec/recordings \
#     -v $ZOOMREC_HOME/audio:/home/zoomrec/audio \
#     -v $ZOOMREC_HOME/meetings.csv:/home/zoomrec/meetings.csv \
#     -v $ZOOMREC_HOME/email_types.yaml:/home/zoomrec/email_types.yaml:ro \
#     -p 5901:5901 \
#     --security-opt seccomp:unconfined \
#     --group-add="$VIDEO_GROUPID" \
#     --group-add="$RENDER_GROUPID" \
#     --device /dev/dri/renderD128:/dev/dri/renderD128 \
#     --device /dev/dri/card0:/dev/dri/card0 \
#     rkilchmn/zoomrec_client:latest

elif [[ "$2" == "$NVIDIA" ]]; then
  docker run -d --restart unless-stopped --name zoomrec_client \
    -e CLIENT_ID="$CLIENT_ID" \
    -e DEBUG="$DEBUG" \
    -e LOG_LEVEL="$LOG_LEVEL" \
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
    -p 5678:5678 \
    -p 5901:5901 \
    -p 137-139:137-139 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    --gpus all \
    rkilchmn/zoomrec_client:latest
else
  docker run -d --restart unless-stopped --name zoomrec_client \
    -e CLIENT_ID="$CLIENT_ID" \
    -e DEBUG="$DEBUG" \
    -e LOG_LEVEL="$LOG_LEVEL" \
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
    -p 5678:5678 \
    -p 5901:5901 \
    -p 137-139:137-139 \
    -p 445:445 \
    --security-opt seccomp:unconfined \
    rkilchmn/zoomrec_client:latest
fi
