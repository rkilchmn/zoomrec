#!/bin/bash

git pull

# possible values for GPU Acceleration
VAAPI="VAAPI"
NVIDIA="NVIDIA"

# Check if at least one parameter is passed
if [ $# -gt 1 ]; then
  echo "Error: Only 1 optional parameter is allowed."
  echo "Usage: $0 optional:GPU[VAAPI|NVIDIA]"
  exit 1
fi

if [ -n "$2" ]; then
  # Check if the provided GPU is either VAAPI or NVIDIA
  if [ "$1" != "$VAAPI" ] && [ "$1" != "$NVIDIA" ]; then
    echo "Error: Invalid GPU acceleration specified."
    echo "GPU must be either $VAAPI or $NVIDIA."
    exit 1
  fi
fi

if [ "$1" == "VAAPI" ]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  echo  "render=$RENDER_GROUPID"
  docker build --build-arg GPU_BUILD=$1 --build-arg RENDER_GROUPID=$RENDER_GROUPID -t rkilchmn/zoomrec .
else
  docker build --build-arg GPU_BUILD=$1 -t rkilchmn/zoomrec .
fi
