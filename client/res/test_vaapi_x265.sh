#!/bin/sh
# for vaapi under wls2 with intel xe integrated gpu
vainfo --display drm
ffmpeg -hwaccel vaapi -hwaccel_output_format vaapi -init_hw_device vaapi=foo:/dev/dri/$LIBVA_RENDER_NODE -i ~/recordings/test.mkv -map 0:v:0 -c:v hevc_vaapi ~/recordings/test_vaapi_h265.mkv
