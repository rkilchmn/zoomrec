#!/bin/bash

source ~/.server.env

# Export all variables that are not already exported
for var in $(compgen -v); do
    export "$var"
done

# override variables because they are intended for docker scenarion
export SERVER_PORT=8081 # this needs to be the external server port as there is no docker
export SERVER_URL="http://localhost:8081"
export DEBUG_MODULE="" # turn off remote debugging
export ZOOMREC_HOME="${HOME}"

python3 server/zoomrec_server.py
