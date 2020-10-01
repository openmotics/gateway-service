#!/usr/bin/env bash
set -e

# TODO install egglink instead
export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

pytest . --log-level=DEBUG --durations=2 \
    --junit-xml ../gw-unit-reports-3/gateway.xml
