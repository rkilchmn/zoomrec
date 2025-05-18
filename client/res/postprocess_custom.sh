#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <filename> [options]"

    exit 1
fi

FILENAME=$1

# Example postprocessing (modify as needed)
MSG="Custom postprocessing completed successfully for $FILENAME with options: $@"
echo "$MSG" >> "$FILENAME.txt"
echo "$MSG" 