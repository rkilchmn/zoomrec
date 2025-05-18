#!/bin/bash

# Base filename without extension
BASE_NAME="$1"
EXTENSION="$2"
DELETE_SOURCE_FILES="$3"

# Ensure a base filename and extension are provided
if [[ -z "$BASE_NAME" || -z "$EXTENSION" ]]; then
    echo "Usage: $0 <base_filename_without_extension> <extension> [delete_source_files]"
    exit 1
fi

# Find matching files
shopt -s nullglob  # Avoids error when no files match
FILE_LIST=( "${BASE_NAME}"*.${EXTENSION} )

# Check if there are multiple matching files
if [[ ${#FILE_LIST[@]} -lt 2 ]]; then
    echo "No need to concatenate. Found: ${#FILE_LIST[@]}"
    exit 0
fi

# Check if a file with exactly the basename.extension exists
EXACT_MATCH="${BASE_NAME}.${EXTENSION}"
if [[ -f "$EXACT_MATCH" ]]; then
    NEW_NAME="${BASE_NAME}_0.${EXTENSION}"
    if [[ -f "$NEW_NAME" ]]; then
        echo "File $NEW_NAME already exists. Cannot rename $EXACT_MATCH to this name. Aborting."
        exit 2
    fi
    echo "Renaming $EXACT_MATCH to $NEW_NAME"
    mv "$EXACT_MATCH" "$NEW_NAME"
fi

# Find matching files (again after renaming)
shopt -s nullglob  # Avoids error when no files match
FILE_LIST=( "${BASE_NAME}"*.${EXTENSION} )

# Create input list file for ffmpeg
INPUT_FILE="input.txt"
echo "Creating input file list: $INPUT_FILE"
rm -f "$INPUT_FILE"
for file in "${FILE_LIST[@]}"; do
    echo "file '$file'" >> "$INPUT_FILE"
done

# Output file name
OUTPUT_FILE="${BASE_NAME}.${EXTENSION}"

# Run ffmpeg to concatenate
ffmpeg -f concat -safe 0 -i "$INPUT_FILE" -c copy "$OUTPUT_FILE"

# Cleanup
rm -f "$INPUT_FILE"

# Optionally delete source files if specified
if [[ "$DELETE_SOURCE_FILES" == "yes" ]]; then
    echo "Deleting source files..."
    rm -f "${FILE_LIST[@]}"
fi

echo "Concatenation complete: $OUTPUT_FILE"
