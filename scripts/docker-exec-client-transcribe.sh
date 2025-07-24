#!/bin/bash
usage="Usage: $0 <meeting-base-name>"

if [ "$#" -ne 1 ]; then
    echo "$usage"
    exit 1
fi

docker exec  -u zoomrec zoomrec_client /home/zoomrec/client/transcribe_video.sh transcribe /home/zoomrec/data/recordings/$1.mkv