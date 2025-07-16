#!/bin/bash
usage="Usage: $0 <meeting-base-name> <sftp-url> <user-login>"

if [ "$#" -ne 3 ]; then
    echo "$usage"
    exit 1
fi

docker exec -u zoomrec zoomrec_client /home/zoomrec/client/sftp_upload.sh \
  "'/home/zoomrec/recordings/$1'" \
  "'$2'" \
  '/home/zoomrec/.ssh/id_rsa' \
  "'$3/recordings'" \
  False