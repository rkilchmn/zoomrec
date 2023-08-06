#!/bin/bash
git pull
docker build -f server/Dockerfile -t rkilchmn/zoomrec_server .