#!/bin/bash

# create zoomrec user
useradd -s /usr/sbin/nologin -d $1 -u 1991 zoomrec

mkdir $1
mkdir $1/recordings
mkdir $1/logs
mkdir $1/logs/screenshots

chown -R zoomrec:zoomrec $1
chmod -R 755 $1

# sftp data dir 
mkdir $1/sftp-data
# needs to be owned by root becasue if sftp using chroot jail
sudo chown root:root $1/sftp-data
chmod 755 $1/sftp-data

cp -r example/audio $1
cp -r res/img $1
cp example/config_client_example.txt $1/config_client.txt
cp example/config_server_example.txt $1/config_server.txt
cp example/email_types_example.yaml $1/email_types.yaml
# create empty db if it does not exist
if [ ! -f "$1/zoomrec_server_db" ]; then
    touch $1/zoomrec_server_db
fi