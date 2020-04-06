#!/bin/bash -e
export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

echo "Running master api tests"
python3 master_tests/master_api_tests.py

echo "Running master command tests"
python3 master_tests/master_command_tests.py

