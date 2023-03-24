#!/bin/bash
docker run -d --restart unless-stopped --name zoomrec \
  -e TELEGRAM_BOT_TOKEN="mytoken" \
  -e TELEGRAM_CHAT_ID="mychatid" \
  -e TZ=Australia/Sydney \
  -e DISPLAY_NAME="Monica" \
  -e FFMPEG_INPUT_PARAMS="-hwaccel cuvid" \
  -e FFMPEG_OUTPUT_PARAMS="-c:v hevc_nvenc -b:v 1M -gpu 0 -preset slow -acodec aac -b:a 128k" \
  -e SAMBA_USER=testuser \
  -e SAMBA_PASS=test123  \
  -e IMAP_SERVER="imap.myemailprovider.com" \
	-e IMAP_PORT="143"\
	-e EMAIL_ADDRESS="zoomrec@myemailprovider.com" \
	-e EMAIL_PASSWORD="mypassword" \
  -v /home/roger/zoomrec/recordings:/home/zoomrec/recordings \
  -v /home/roger/zoomrec/audio:/home/zoomrec/audio \
  -v /home/roger/zoomrec/meetings.csv:/home/zoomrec/meetings.csv \
  -p 5901:5901 \
  -p 137-139:137-139 \
  -p 445:445 \
  --security-opt seccomp:unconfined \
  --gpus all \
  rkilchmn/zoomrec:latest
