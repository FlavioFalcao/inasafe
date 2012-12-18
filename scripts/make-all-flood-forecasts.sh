#!/bin/bash

export QGIS_DEBUG=0
export QGIS_LOG_FILE=/tmp/inasafe/realtime/logs/qgis.log
export QGIS_DEBUG_FILE=/tmp/inasafe/realtime/logs/qgis-debug.log
export QGIS_PREFIX_PATH=/usr/local/qgis-master/
export PYTHONPATH=/usr/local/qgis-master/share/qgis/python/:`pwd`
export LD_LIBRARY_PATH=/usr/local/qgis-master/lib
# need to be updated
# export INASAFE_WORK_DIR=/home/flood/forecast
export INASAFE_WORK_DIR=~/Documents/inasafe/inasafe_real_flood
export INASAFE_RW_JKT_PATH=/home/flood/data_input/rw_jakarta.shp
export INASAFE_LOCALE=id
cd /home/sunnii/Documents/inasafe/inasafe-dev/
xvfb-run -a --server-args="-screen 0, 1024x768x24" python realtime/make_flood_forecast.py --run-all