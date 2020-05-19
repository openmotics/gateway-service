#!/bin/bash -e
export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

pytest . --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports/gateway.xml
