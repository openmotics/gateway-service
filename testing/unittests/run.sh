#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# TODO install egglink instead
export PYTHONPATH=$PYTHONPATH:$PWD/src

pytest testing/unittests --log-level=DEBUG --durations=2 \
    --junit-xml testing/gw-unit-reports/gateway.xml \
    --cov-report xml --cov-fail-under=50 \
    --cov=bus --cov=gateway --cov=ioc --cov=master --cov=serial_utils --cov=toolbox
