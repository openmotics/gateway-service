# Runner docker container

## Setup

some setup is required to run a local gateway. These steps described below should only be runned once to setup the local gateway.

### Docker container

The docker container can be build with the command:

``` shell
./container.sh build
```

### Credentials

The local runner requires a set of certificates to be able to connect to the cloud. These credentials are provided in a tarball named `client.tar.gz` from OpenMotics.

To setup the credentials place this tarball file in the config folder of this directory. Afterwards, run the setup_config command with the container.sh script:

``` shell
./container.sh setup_config
```

This will setup the basic credentials and config file in the right format to be run in a local docker container.

### Virtualenv

The gateway has a set of python dependencies and will be installed in a virtualenv. To do so, run the followig command:

``` shell
./container.sh venv
```

## Running

When the steps in section [Setup](#setup) are completed, the gateway can be run by the following command:

``` shell
./container.sh run
```

## Debugging

The docker container can be runned in a shell mode for debuggign purposes:

``` shell
./container.sh shell
```

## Cleanup

If required, the artifacts can be cleaned up with teh clean command:

``` shell
./container.sh clean
```

This command will clean all the artifacts:

* docker container
* virtualenv
* config folder contents
