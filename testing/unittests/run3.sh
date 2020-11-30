#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# TODO install egglink instead
export PYTHONPATH=$PYTHONPATH:$PWD/src

pytest testing/unittests --log-level=DEBUG --durations=2 \
    --junit-xml testing/gw-unit-reports-3/gateway.xml
