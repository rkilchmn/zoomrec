#!/bin/bash
docker run -d --restart unless-stopped --name zoomrec \
  -e TELEGRAM_BOT_TOKEN="mytoken" \
  -e TELEGRAM_CHAT_ID="mychatid" \
  -e TZ=Australia/Sydney \
  -e DISPLAY_NAME="Monica" \
  -e FFMPEG_OUTPUT_PARAMS="-acodec aac -b:a 128k -vaapi_device /dev/dri/renderD128 -vf 'hwupload,scale_vaapi=format=nv12' -c:v h264_vaapi -qp 24" \
  -e LIBVA_DRIVER_NAME=i965 \
  -e SAMBA_USER=testuser \
  -e SAMBA_PASS=test123 \
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
  --group-add="44" \
  --group-add="110" \
  --device /dev/dri:/dev/dri \
  rkilchmn/zoomrec:latest
