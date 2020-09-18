#!/bin/bash -e

export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

pytest master_tests --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/master.xml
pytest master_core_tests --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/master_core.xml
pytest gateway_tests/mappers --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/gateway-mappers.xml
pytest gateway_tests/serializers --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/gateway-serializers.xml
pytest thermostat_tests --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/thermostats.xml

#echo "Running users tests"
#pytest gateway_tests/users_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayUsersTest.xml

#echo "Running scheduling tests"
#pytest gateway_tests/scheduling_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewaySchedulingTest.xml

#echo "Running shutter tests"
#pytest gateway_tests/shutter_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayShutterTest.xml

echo "Running power controller tests"
pytest power_tests/power_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerControllerTest.xml

#echo "Running power communicator tests"
#pytest power_tests/power_communicator_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerCommunicatorTest.xml

echo "Running time keeper tests"
pytest power_tests/time_keeper_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerTimeKeeperTest.xml

#echo "Running plugin base tests"
#pytest plugins_tests/base_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsBaseTest.xml

echo "Running plugin interfaces tests"
pytest plugins_tests/interfaces_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsInterfacesTest.xml

#echo "Running pulse counter controller tests"
#python3 gateway_tests/pulses_test.py

#echo "Running classic controller tests"
#python3 gateway_tests/hal/master_controller_classic_test.py

#echo "Running core controller tests"
#python3 gateway_tests/hal/master_controller_core_test.py

echo "Running frontpanel classic controller tests"
python3 gateway_tests/hal/frontpanel_controller_classic_test.py

echo "Running frontpanel core controller tests"
python3 gateway_tests/hal/frontpanel_controller_core_test.py

echo "Running output controller tests"
pytest gateway_tests/output_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/OutputControllerTest.xml

echo "Running input controller tests"
pytest gateway_tests/input_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/InputControllerTest.xml

echo "Running room controller tests"
pytest gateway_tests/room_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/RoomControllerTest.xml

echo "Running module controller tests"
pytest gateway_tests/module_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/ModuleControllerTest.xml

#echo "Running metrics tests"
#python3 gateway_tests/metrics_test.py

echo "Running master_tool.py tests"
pytest master_tool_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterToolTests.xml
