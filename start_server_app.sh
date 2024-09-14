#!/bin/bash

source ~/zoomrec_home/config_server_test.txt

# Export all variables that are not already exported
for var in $(compgen -v); do
    export "$var"
done

# Start the zoomrec server application
python3 "zoomrec_server_app.py" 
