#!/bin/bash
usage="Usage: $1 <meeting-base-name>"

if [ "$#" -ne 1 ]; then
    echo "$usage"
    exit 1
fi

docker exec zoomrec_client /home/zoomrec/client/transcribe_video.sh transcribe /home/zoomrec/recordings/$1.mkv