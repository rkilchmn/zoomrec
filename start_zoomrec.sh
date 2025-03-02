#!/bin/sh
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <server config> <client config> [optional: <GPU Acceleration>]"
    exit 1
fi

./build_zoomrec_server.sh 
./start_zoomrec_server.sh $1

./build_zoomrec_client.sh $3
./start_zoomrec_client.sh $2 $3