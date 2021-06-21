#!/usr/bin/env bash

set -e

# General script variables
SCRIPT_DIR_NAME=$(dirname $(realpath $0))
GATEWAY_ROOT_DIR=$SCRIPT_DIR_NAME/../../

GATEWAY_CONFIG_DIR="$SCRIPT_DIR_NAME/config"
GATEWAY_CONFIG_DIR_DOCKER='/app/docker/runner/config'

# docker image definition
DOCKER_IMG_NAME='gateway-runner'
DOCKER_CONT_NAME='gateway-runner-container'

DOCKER_HOSTNAME=$DOCKER_IMG_NAME

# docker run command options
DOCKER_BASE_CMD='docker run'
DOCKER_RM_CMD='--rm'
DOCKER_INTERACTIVE='-it'
DOCKER_DAEMON='-d'

DOCKER_OPTIONS='
-v '$GATEWAY_ROOT_DIR':/app
-v '$GATEWAY_CONFIG_DIR/openvpn':/etc/openvpn/client
-w /app
-e TERM=xterm-color
--hostname '$DOCKER_HOSTNAME'
--name '$DOCKER_CONT_NAME'
'

DOCKER_OPTIONS_PUBLISH='
-p 8088:8088
-p 8443:8443'

DOCKER_OPTIONS_USER='--user='$(id -u):$(id -g)
DOCKER_OPTIONS_XORG='-e DISPLAY=$(DISPLAY) -v /tmp/.X11-unix:/tmp/.X11-unix'
DOCKER_OPTIONS_PRIVILEGED='--privileged'

DOCKER_RUN_CMD="$DOCKER_BASE_CMD
	$DOCKER_RM_CMD
	$DOCKER_INTERACTIVE
	$DOCKER_OPTIONS
	$DOCKER_OPTIONS_PUBLISH
	$DOCKER_OPTIONS_PRIVILEGED
	$DOCKER_IMG_NAME"

VENV_NAME=gw_venv
VENV_FOLDER="$SCRIPT_DIR_NAME/$VENV_NAME"

if [ $(uname -s) == 'Darwin' ]
then
    SED_CMD="gsed"  # You need gnu-sed
else
    SED_CMD="sed"
fi


# create the venv
create_venv () {
    $DOCKER_RUN_CMD \
    bash -c "
        cd /app/docker/runner &&
        python3 -m virtualenv $VENV_NAME &&
        source $VENV_NAME/bin/activate &&
        pip install -r /app/requirements-py3.txt"
}


# Build the container
build () {
    echo "-------------------------------------"
    echo "Building docker container"
    echo "-------------------------------------"
    echo " * Building the docker container..."
    docker build -t $DOCKER_IMG_NAME $SCRIPT_DIR_NAME
    echo "   => Done"
    echo " * Building the venv"
    create_venv
    echo "   => Done"
    echo "Done!"
}

# initialize the certificates
setup_config () {
    echo "-------------------------------------"
    echo "Setting up the config folder"
    echo "-------------------------------------"
    CLIENT_TARBALL=$GATEWAY_CONFIG_DIR/client.tar.gz

    echo " * Checking if the client.tar.gz file is present"
    if [ ! -f $CLIENT_TARBALL ]; then
        echo "DOES NOT EXISTS, QUITING"
        return
    fi
    echo "   => OK"

    echo " * extracting the tarball"
    tar -xz -f $CLIENT_TARBALL --directory $GATEWAY_CONFIG_DIR
    CLIENT_UNPACKED=$GATEWAY_CONFIG_DIR/client
    echo "   => Done"

    echo " * Setting files to the correct location"
    mkdir -p $GATEWAY_CONFIG_DIR/etc
    mkdir -p $GATEWAY_CONFIG_DIR/openvpn
    cp $CLIENT_UNPACKED/openmotics.conf $CLIENT_UNPACKED/https.crt $CLIENT_UNPACKED/https.key $GATEWAY_CONFIG_DIR/etc
    cp $CLIENT_UNPACKED/vpn.conf $CLIENT_UNPACKED/ca.crt $CLIENT_UNPACKED/ta.key $CLIENT_UNPACKED/client.crt $CLIENT_UNPACKED/client.key $GATEWAY_CONFIG_DIR/openvpn
    echo "   => Done"

    echo " * Changing the openmotics.config file to the correct spec"
    $SED_CMD -i '/controller_serial/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '/passthrough_serial/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '/cli_serial/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '/power_serial/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '/leds_i2c_address/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '/platform/d' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '6 a platform=DUMMY' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '7 a http_port=8088' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '8 a https_port=8443' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    $SED_CMD -i '9 a vpn_supervisor=False' $GATEWAY_CONFIG_DIR/etc/openmotics.conf
    echo "   => Done"

    echo " * Remove artifacts"
    rm -rf $CLIENT_UNPACKED
    echo "   => Done"

    echo "Done!"
}


# Running a bash shell, can be used for debugging puroses
run_shell () {
    echo "-------------------------------------"
    echo "Running docker shell"
    echo "-------------------------------------"
	$DOCKER_RUN_CMD \
    bash
    echo "Done!"
}


# Run the openmotics gateway
run_gw_in_docker () {
    echo "-------------------------------------"
    echo "Running docker gateway"
    echo "-------------------------------------"
	$DOCKER_RUN_CMD \
	bash -c "
        mkdir -p $GATEWAY_CONFIG_DIR_DOCKER/etc &&
        source /app/docker/runner/$VENV_NAME/bin/activate &&
        export OPENMOTICS_PREFIX=$GATEWAY_CONFIG_DIR_DOCKER;
        echo 'running vpn serivce';
        python3 src/vpn_service.py &
        echo 'running openmotics serivce';
        python3 src/openmotics_service.py"
    echo "Done!"
}

clean () {
    echo "-------------------------------------"
    echo "Clean artifacts created by this script"
    echo "-------------------------------------"
    rm -rf $VENV_FOLDER
    rm -rf $GATEWAY_CONFIG_DIR/*
    docker container rm $DOCKER_CONT_NAME
    echo "Done!"
}


# Expose the commands via args to the cli, other functions are used by the script itself
while [ $# -gt 0 ]
do
    key="$1"

    case $key in
        build)
            build
            shift
        ;;
        setup_config)
            setup_config
            shift
        ;;
        shell)
            run_shell
            shift
        ;;
        venv)
            create_venv
            shift
        ;;
        run)
            run_gw_in_docker
            shift
        ;;
        clean)
            clean
            shift
        ;;
        *)
            echo "ERROR: Unknown argument passed: $1"
            shift
        ;;
    esac
done
