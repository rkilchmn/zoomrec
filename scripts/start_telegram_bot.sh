#!/bin/bash

source ~/.development.server.env

# Export all variables that are not already exported
for var in $(compgen -v); do
    export "$var"
done

# Get the project root directory
PROJECT_ROOT="$(dirname "$0")/.."

# Start the telegram bot
cd "$PROJECT_ROOT/server" || exit 1

# Add project root to PYTHONPATH and run the bot
PYTHONPATH="$PROJECT_ROOT" python3 -m telegram_bot
