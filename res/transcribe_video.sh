#!/bin/bash

# Help message function
print_help() {
    echo "Usage: $0 input_file"
    echo "  input_file: Path to the input video file"
    echo "Example: $0 audio.mp3"
}

# Check if no arguments are passed, then print help message
if [ "$#" -eq 0 ]; then
    print_help
    exit 1
fi

# Start time
# start_time=$(date +%s)

# Extract input file name and directory
input_file="$1"
input_dir=$(dirname "$input_file")

# Extract audio file name
audio_file="${input_file%.*}.mp3"

# Extract audio mp3 using ffmpeg
# ffmpeg -hide_banner -loglevel error -stats -y -i "$input_file" -vn -acodec copy "$audio_file"
ffmpeg -hide_banner -loglevel quiet -y -i "$input_file" -vn -acodec libmp3lame "$audio_file"

whisper-ctranslate2-remote-api --verbose false "$audio_file" --output_dir "$input_dir" --faster_whisper_api_base_url http://host.docker.internal:9876/api/v0

# Delete source audio file
rm "$audio_file"