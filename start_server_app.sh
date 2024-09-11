#!/bin/bash

# Set environment variables
export HOME="/home/roger/zoomrec_home"
export LOG_SUBDIR="logs"
export FIRMWARE_SUBDIR="firmware"
export TELEGRAM_BOT_TOKEN="5640653916:AAH2R49kkJWWoYbHKCZ-ztrOS2HtYVpYLz0"
export TELEGRAM_CHAT_ID="356350585"
export TZ="Australia/Sydney"
export IMAP_SERVER="mail.kilchenmann.net"
export IMAP_PORT="143"
export EMAIL_ADDRESS="zoomrec@kilchenmann.net"
export EMAIL_PASSWORD="VnDa4pogb5Qk6bHyU26i"
export DOCKER_API_PORT="8081"
export SERVER_USERNAME="myuser"
export SERVER_PASSWORD="mypassword"
export FILENAME_MEETINGS_CSV="meetings_server.csv"

# Start the zoomrec server application
python3 "zoomrec_server_app.py" 
