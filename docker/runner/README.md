# Runner docker container

## Setup

Some setup is required to run a local gateway. These steps described below should only be runned once to setup the local gateway.

### Docker container

From `docker/runner`, the docker container can be build with the command:

``` shell
./container.sh build
```

> Note: on macOS this requires a few dependencies, which can be installed using
> ``` shell
> brew install coreutils gnu-sed
> ```


### Credentials

The local runner requires a set of certificates to be able to connect to the cloud. These credentials are provided in a tarball named `client.tar.gz` from OpenMotics. To be able to run on your local dev-setup, download the ones for your gateway from the staging admin portal.

To setup the credentials place this tarball file in the config folder of this directory. Afterwards, run the setup_config command with the container.sh script:

``` shell
./container.sh setup_config
```

This will setup the basic credentials and config file in the right format to be run in a local docker container.

To be able to run to your local dev-setup, modify following files:
  - config/openvpn/vpn.conf:
    ```
    remote host.docker.internal 1194
    ```
  - config/etc/openmotics.conf:
    ```
    uuid=YOUR-REGISTRATION-KEY
    vpn_check_url=http://host.docker.internal:9000/portal/check_vpn/?uuid=%%s
    cloud_user=YOUR-GATEWAY-USERNAME
    cloud_pass=YOUR-GATEWAY-PASSWORD
    ```

> Note: those config changes have only been tested on macOS. For Linux, please look at: https://stackoverflow.com/questions/24319662

### Virtualenv

The gateway has a set of python dependencies and will be installed in a virtualenv. This is part of the `build` command. To do separately, run the following command:

``` shell
./container.sh venv
```

## Web frontend

1. Create a `static` directory in the `config` directory.
2. Download the gateway-frontend tgz file from https://github.com/openmotics/frontend/releases/latest
3. Extract the tgz-file in the `static` directory

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

If required, the artifacts can be cleaned up with the clean command:

``` shell
./container.sh clean
```

This command will clean all the artifacts:

* docker container
* virtualenv
* config folder contents
