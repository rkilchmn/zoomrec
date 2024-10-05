#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <command> <filename>"
    echo "Valid Command:"
    echo "  transcribe - transcribe video"

    exit 1
fi

POSTPROCESS_COMMAND=$1
FILENAME=$2

# Example postprocessing command (modify as needed)
case $POSTPROCESS_COMMAND in
    "transcribe")
        transcribe_video.sh "$FILENAME"
        ;;
    "test")
        # just for testing
        sleep 120
        echo "done" >> "$FILENAME.txt"
        ;;
    *)
        echo "Unknown postprocessing command: $POSTPROCESS_COMMAND"
        exit 1
        ;;
esac

echo "Postprocessing completed for $FILENAME"