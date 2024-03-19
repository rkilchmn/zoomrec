#!/bin/bash

git pull

# Check if at least one parameter is passed
if [ $# -lt 1 ]; then
  echo "Error: At least one parameter is required."
  echo "Usage: $0 GPU (VAAPI|NVIDIA)"
  exit 1
fi

if [ "$1" == "VAAPI" ]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  echo  "render=$RENDER_GROUPID"
  docker build --build-arg GPU_BUILD=$1 --build-arg RENDER_GROUPID=$RENDER_GROUPID -t rkilchmn/zoomrec .
else
  docker build --build-arg GPU_BUILD=$1 -t rkilchmn/zoomrec .
fi
