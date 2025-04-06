#!/bin/bash

source ~/.development.server.env

# Export all variables that are not already exported
for var in $(compgen -v); do
    export "$var"
done

# override variables because they are intended for docker scenarion
export DOCKER_SERVER_PORT=8081 # this needs to be the external server port as there is no docker
export DEBUG_MODULE="" # turn off remote debugging

# Start the zoomrec server application
python3 "zoomrec_server_app.py" 
