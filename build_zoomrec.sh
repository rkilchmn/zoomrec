#!/bin/bash

git pull

if [[ "$1" == "AMD" || "$1" == "INTEL" ]]; then
  RENDER_GROUPID=$(getent group render | cut -d':' -f3)
  echo  "render=$RENDER_GROUPID"
  docker build --build-arg GPU_BUILD=$1 --build-arg RENDER_GROUPID=$RENDER_GROUPID -t rkilchmn/zoomrec .
else
  docker build --build-arg GPU_BUILD=$1 -t rkilchmn/zoomrec .
fi
