#!/bin/sh
# Start Generation Here
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <GPU Acceleration> <server config> <client config>"
    exit 1
fi
# End Generation Here

./build_zoomrec_client.sh $1
./build_zoomrec_server.sh 
./start_zoomrec_server.sh $2
./start_zoomrec_client.sh $3 $1

