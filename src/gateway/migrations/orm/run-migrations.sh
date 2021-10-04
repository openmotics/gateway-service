#!/bin/sh

export PYTHONPATH=../../../../src

echo "Migrate ORM manually"

FILES=$(ls -- [0-9][0-9][0-9]_*.py)

wait_for_input () {
	read -p "tap any key to proceed..." input
}

for file in $FILES
do
	file_cut=$(basename $file .py)
	echo "Migrating: $file_cut"
	wait_for_input
	pw_migrate migrate --verbose --database sqlite:///../../../../etc/gateway.db --directory ./ --name $file_cut
	echo "DONE!"
	echo ""
done

