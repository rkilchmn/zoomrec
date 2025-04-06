#!/bin/bash

source ~/.development.server.env

# Export all variables that are not already exported
for var in $(compgen -v); do
    export "$var"
done

# Start the zoomrec server application
python3 "telegram_bot.py" 
