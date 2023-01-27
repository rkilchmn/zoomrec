#!/bin/bash
docker run -d --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="mytoken" \
  -e TELEGRAM_CHAT_ID="mychatid" \
  -e TZ=Australia/Sydney \
  -e DISPLAY_NAME="Monica" \
  -e FFMPEG_ENCODE="-acodec aac -b:a 128k -vaapi_device /dev/dri/renderD128 -vf 'hwupload,scale_vaapi=format=nv12' -c:v h264_vaapi -qp 24" \
  -v /home/roger/zoomrec/recordings:/home/zoomrec/recordings \
  -v /home/roger/zoomrec/audio:/home/zoomrec/audio \
  -v /home/roger/zoomrec/meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
  --security-opt seccomp:unconfined \
  --gpus all \
  rkilchmn/zoomrec:latest
