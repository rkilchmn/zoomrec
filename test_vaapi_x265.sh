#!/bin/sh
# for vaapi under wls2 with intel xe integrated gpu
vainfo --display drm
ffmpeg -hwaccel vaapi -hwaccel_output_format vaapi -hwaccel_device /dev/dri/card0 -i ~/zoomrec_home/recordings/test5min.mkv -map 0:v:0 -c:v hevc_vaapi ~/test_vaapi_h265.mkv
