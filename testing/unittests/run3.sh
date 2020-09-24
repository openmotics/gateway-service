#!/bin/bash -e

export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

declare -a blacklist=(
    gateway_tests/hal/master_controller_classic_test.py
    gateway_tests/metrics_test.py
    gateway_tests/scheduling_test.py
    gateway_tests/shutter_test.py
    gateway_tests/users_test.py
    gateway_tests/webservice_test.py
    plugins_tests/base_test.py
    plugins_tests/runner_test.py
    power_tests/power_communicator_test.py
)

find . -name '*_test.py' | while read -r f; do
    f=${f#./*}
    if [[ "${blacklist[*]}" =~ "$f" ]]; then
        echo "Skipping $f..." >&2
        continue
    fi
    out=${f//\//_}
    echo "Testing $f..." >&2
    pytest "$f" --log-level=DEBUG --durations=2 --junit-xml "../gw-unit-reports-3/$out.xml" || true
done
