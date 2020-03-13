#!/bin/sh
OS_DIST=`awk -F= '$1=="ID" { print $2 ;}' /etc/os-release`
TEMP_DIR=$(mktemp -d -t ci-XXXXXXXX --tmpdir=/opt/openmotics)
env TMPDIR=$TEMP_DIR python /opt/openmotics/python/libs/pip.whl/pip install --upgrade --target /opt/openmotics/dist-packages --no-index /opt/openmotics/python/libs/$OS_DIST/*.whl
rm -rf $TEMP_DIR
