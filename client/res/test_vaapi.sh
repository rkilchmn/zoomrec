#!/bin/sh
vainfo --display drm --device /dev/dri/$LIBVA_RENDER_NODE
ffmpeg -loglevel debug -init_hw_device vaapi=foo:/dev/dri/$LIBVA_RENDER_NODE