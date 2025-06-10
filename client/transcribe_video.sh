#!/bin/bash

# Help message function
print_help() {
    echo "Usage: $0 task input_file"
    echo "  task: transcribe, translate, or transcribe=<lang>/translate=<lang> (e.g., transcribe=en, translate=fr)"
    echo "  input_file: Path to the input video file"
    echo "Examples:"
    echo "  $0 transcribe myvideo.mp4"
    echo "  $0 translate=en myvideo.mp4"
}

# Check if less than 2 arguments are passed, then print help message
if [ "$#" -lt 2 ]; then
    print_help
    exit 1
fi

# Start time
# start_time=$(date +%s)

# Extract task and input file name
TASK_ARG="$1"
input_file="$2"
input_dir=$(dirname "$input_file")

# Extract task and optional language from task argument (e.g., 'translate=en')
if [ -n "$TASK_ARG" ]; then
    TASK="${TASK_ARG%%=*}"
    if [[ "$TASK_ARG" == *"="* ]]; then
        LANGUAGE="${TASK_ARG#*=}"
    else
        LANGUAGE=""
    fi
else
    TASK="transcribe"
    LANGUAGE=""
fi

# Extract audio file name
audio_file="${input_file%.*}.mp3"

# Extract audio mp3 using ffmpeg
# ffmpeg -hide_banner -loglevel error -stats -y -i "$input_file" -vn -acodec copy "$audio_file"
ffmpeg -hide_banner -loglevel quiet -y -i "$input_file" -vn -acodec libmp3lame "$audio_file"

API_ARGS=(--verbose false "$audio_file" --output_dir "$input_dir" --faster_whisper_api_base_url "$WHISPER_API_URL" --task "$TASK")
if [ -n "$LANGUAGE" ]; then
    API_ARGS+=(--language "$LANGUAGE")
fi

echo "whisper-ctranslate2-remote-api ${API_ARGS[@]}"
python3 -m src.whisper_ctranslate2.whisper_ctranslate2 "${API_ARGS[@]}"

# Delete source audio file
rm "$audio_file"