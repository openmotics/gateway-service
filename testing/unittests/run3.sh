#!/bin/bash -e
export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

echo "Running master api tests"
pytest master_tests/master_api_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterApiTest.xml

echo "Running master command tests"
pytest master_tests/master_command_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCommandTest.xml

echo "Running thermostat tests"
pytest thermostat_tests/gateway_mapping_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayThermostatMappingTest.xml
