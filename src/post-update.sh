#!/bin/sh
set -e

OS_DIST=`awk -F= '$1=="ID" { print $2 ;}' /etc/os-release`
if [ "$OS_DIST" != "buildroot" ]; then
  TEMP_DIR=$(mktemp -d -t pip-XXXXXXXX -p /opt/openmotics)
  env TMPDIR=$TEMP_DIR PYTHONUSERBASE=/opt/openmotics/python-deps python /opt/openmotics/python/libs/pip.whl/pip install --no-index --user /opt/openmotics/python/libs/$OS_DIST/*.whl
  rm -rf $TEMP_DIR
fi
