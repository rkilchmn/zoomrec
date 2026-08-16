#!/bin/sh
# for vaapi under wls2 with intel xe integrated gpu
vainfo --display drm
ffmpeg -hwaccel vaapi -hwaccel_output_format vaapi -init_hw_device vaapi=foo:/dev/dri/$LIBVA_RENDER_NODE -i ~/zoomrec_home/recordings/test5min.mkv -map 0:v:0 -c:v av1_vaapi -qp 30 -profile:v 0 ~/test_vaapi_h265.mkv
