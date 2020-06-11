#!/bin/bash

POSITIONAL=()
while [[ $# -gt 0 ]]
do
key="$1"

case $key in
    -p|--push)
    PUSH=true
    shift # past argument
    ;;
    *)    # unknown option
    POSITIONAL+=("$1") # save it in an array for later
    shift # past argument
    ;;
esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters

FIRST_TAG=${1:-latest}
LOCAL_TAG=openmotics/gateway:$FIRST_TAG
cp ../src/requirements.txt .
(cd .. && tar czf src.tgz src)
mv ../src.tgz .
docker build -t $LOCAL_TAG .
rm src.tgz
rm requirements.txt
