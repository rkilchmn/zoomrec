#!/bin/sh
vainfo --display drm --device /dev/dri/renderD128
ffmpeg -loglevel debug -init_hw_device vaapi=foo:/dev/dri/renderD128