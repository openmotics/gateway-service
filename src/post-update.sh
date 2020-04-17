#!/bin/sh
set -e

OS_DIST=`awk -F= '$1=="ID" { print $2 ;}' /etc/os-release`
DATE=`date +%Y%m%d%H%M%S`
TEMP_DIR="/opt/openmotics/tmp_$DATE"
mkdir $TEMP_DIR
env TMPDIR=$TEMP_DIR PYTHONUSERBASE=/opt/openmotics/python-deps python2 /opt/openmotics/python/libs/pip.whl/pip install --no-index --user /opt/openmotics/python/libs/$OS_DIST/*.whl
rm -rf $TEMP_DIR
