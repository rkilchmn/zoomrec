#! /bin/bash
source $1
sudo gio trash $ZOOMREC_HOME/logs/*
sudo gio trash $ZOOMREC_HOME/recordings/*.mkv
sudo gio trash $ZOOMREC_HOME/recordings/screenshots/*