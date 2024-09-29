#!/bin/bash

# Help message function
print_help() {
    echo "Usage: $0 input_file [device]"
    echo "  input_file: Path to the input video file"
    echo "  device (optional): Specify 'GPU' or 'CPU' (default: GPU)"
    echo "Example: $0 audio.mp3 CPU"
}

write_stats() {
    local elapsed_time=$1
    local audio_length=$2
    local x_factor=$3
    local stats_file=$4

    # Format stats string
    local stats_string="Processing statistics:\nElapsed time: ${elapsed_time} seconds\nAudio length: ${audio_length} seconds\nX factor: ${x_factor}\n"

    # Print stats to console
    echo -e "$stats_string"

    # Write stats to the file
    echo -e "$stats_string" > "$stats_file"

    echo "Statistics written to $stats_file"
}

# Check if no arguments are passed, then print help message
if [ "$#" -eq 0 ]; then
    print_help
    exit 1
fi

# Start time
start_time=$(date +%s)

# Extract input file name and directory
input_file="$1"
input_dir=$(dirname "$input_file")

# Define the stats file path
stats_file="${input_file%.*}.stats"

# Check if a corresponding stats file already exists
if [ -f "$stats_file" ]; then
    echo "Stats file $stats_file already exists. Skipping processing."
    exit 0
fi

# Extract audio file name
audio_file="${input_file%.*}.wav"

# Extract optional parameter for device (default is GPU)
# for whisper.cpp OpenVino
device="${2:-GPU}"

# Extract audio using ffmpeg
# ffmpeg -hide_banner -loglevel error -stats -y -i "$input_file" -vn -acodec copy "$audio_file"
ffmpeg -hide_banner -loglevel error -stats -y -i "$input_file" -vn -acodec pcm_s16le -ar 16000 "$audio_file"

# Transcribe and store output file in the same directory as input file
# whisper "$audio_file" --model small --language English -o  "$input_dir"
# ./whisper.cpp/main -m whisper.cpp/models/ggml-small.bin -f "$audio_file" -oved "$device"
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib
# whisper-ctranslate2 --model small "$audio_file"
whisper-ctranslate2-remote-api "$audio_file" --output_dir "$input_dir" --faster_whisper_api_base_url http://broadwell-server.local:9876/api/v0


# Delete source audio file
rm "$audio_file"

# End time
end_time=$(date +%s)

# Calculate elapsed time
elapsed_time=$((end_time - start_time))

# Get audio length in seconds
audio_length=$(ffmpeg -i "$audio_file" 2>&1 | grep "Duration" | cut -   ed s/,// | awk -F: '{print ($1 * 3600) + ($2 * 60) + $3}')

# Calculate x factor
x_factor=$(bc <<< "scale=2; $audio_length / $elapsed_time")

# Call the write_stats function to print and write the stats
write_stats "$elapsed_time" "$audio_length" "$x_factor" "$stats_file"