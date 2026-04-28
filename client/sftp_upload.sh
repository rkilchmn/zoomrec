#!/bin/bash

# Base filename without extension
BASE_NAME="$1"
SSH_SERVER_URL="$2"
IDENTITY_FILE="$3"
TARGET_DIR="$4"
DELETE_SOURCE_FILES="$5"
FILE_FILTER="$6"

# Ensure all parameters are provided
if [[ -z "$BASE_NAME" || -z "$SSH_SERVER_URL" || -z "$IDENTITY_FILE" || -z "$TARGET_DIR" ]]; then
    echo "Usage: $0 <base_filename_without_extension> <ssh_server_url> <identity_file> <target_directory> [delete source files true/false] [file_filter_regex]"
    exit 1
fi

# If no delete flag is provided, default to 'no'
if [[ -z "$DELETE_SOURCE_FILES" ]]; then
    DELETE_SOURCE_FILES="no"
fi

# Find matching files
shopt -s nullglob  # Avoids error when no files match

if [[ -n "$FILE_FILTER" ]]; then
    # Use regex filter if provided
    FILE_LIST=( "${BASE_NAME}"* )
    # Filter files using regex
    FILTERED_LIST=()
    for file in "${FILE_LIST[@]}"; do
        if [[ "$(basename "$file")" =~ $FILE_FILTER ]]; then
            FILTERED_LIST+=("$file")
        fi
    done
    FILE_LIST=("${FILTERED_LIST[@]}")
else
    # No filter, use all matching files
    FILE_LIST=( "${BASE_NAME}"* )
fi

# Check if there are matching files
if [[ ${#FILE_LIST[@]} -lt 1 ]]; then
    echo "No matching files found for $BASE_NAME*"
    exit 0
fi

# SFTP transfer with retry logic
MAX_RETRIES=3
RETRY_DELAY=5  # seconds

for file in "${FILE_LIST[@]}"; do
    echo "Transferring $file to $SSH_SERVER_URL:$TARGET_DIR..."
    
    for ((retry=1; retry<=$MAX_RETRIES; retry++)); do
        # Run SFTP with connection timeout and batch mode
        if sftp -o BatchMode=yes -o ConnectTimeout=10 \
                -o StrictHostKeyChecking=yes \
                -o UserKnownHostsFile=/home/zoomrec/config/sftp/known_hosts \
                -i "/home/zoomrec/config/sftp/zoomrec_admin_id" \
                "sftp://$SSH_SERVER_URL" <<EOF
cd "$TARGET_DIR"
put "$file"
EOF
        then
            echo "Successfully transferred $file"
            break  # Success, exit the retry loop
        else
            if [ $retry -eq $MAX_RETRIES ]; then
                echo "Error: Failed to transfer $file after $MAX_RETRIES attempts"
                exit 1
            fi
            echo "Attempt $retry failed. Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    done
done

echo "File transfer complete."

# Optionally delete source files if specified
if [[ "${DELETE_SOURCE_FILES,,}" == "true" ]]; then
    echo "Deleting source files..."
    rm -f "${FILE_LIST[@]}"
fi
