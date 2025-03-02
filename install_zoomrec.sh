#!/bin/bash
mkdir $1
mkdir $1/recordings
mkdir $1/recordings/screenshots
mkdir $1/logs
cp -r example/audio $1
cp -r res/img $1
cp example/config_client_example.txt $1/config_client.txt
cp example/config_server_example.txt $1/config_server.txt
cp example/email_types_example.yaml $1/email_types.yaml
# create empty db if it does not exist
if [ ! -f "$1/zoomrec_server_db" ]; then
    touch $1/zoomrec_server_db
fi