# Pyinstaller build process

## prerequests

### Install qemu emulator on the host machine

* Make sure that the `make` command is installed
* On Debian based machines run:

  ``` bash
  apt-get update && \
      apt-get install -y \
      --no-install-recommends \
      qemu-user-static \
      binfmt-support
  update-binfmts --enable qemu-arm
  update-binfmts --display qemu-arm
  ```

This will install the qemu binary that is needed for the docker container and
will make sure that when the docker container is run that the emulator will be
used.

src:
https://matchboxdorry.gitbooks.io/matchboxblog/content/blogs/build_and_run_arm_images.html

### Building the docker container

* Go to the docker/pyinstaller directory
* run `make build-docker-zsh`
* test if the container has been correctly build by running the container as:
  `make run-docker-zsh` This should prompt you with a docker container with a
  shell:

    ``` bash
    ⇒  make run-docker-zsh 
    make: Entering directory '~/git/openmotics/gateway/docker/pyinstaller'
    docker run \
    --rm \
    -it \
    -v ~/git/openmotics/gateway/docker/pyinstaller:/app \
    -w /app -e TERM=xterm-256color \
    --user="1000:1000" \
    --hostname arm-qemu-test \
    --name arm-qemu-test_CONTAINER \
    --privileged \
    -e DISPLAY=:0 -v /tmp/.X11-unix:/tmp/.X11-unix \
    arm-qemu-test-zsh \
    zsh

    15:53:54 developer@arm-qemu-test /app ls
    Makefile  docker
    ```

### Running the docker container

The docker container can be run with the command that is shown by the make
command (in order to change the bind mount directory). The command is also in
the makefile, but the bind mount would also be in that directory

``` bash
$ docker run \
--rm \
-it \
-v ${pwd}:/app -w /app \
-e TERM=xterm-256color \
--user="${id -u}:${id -g}" \
--hostname arm-qemu-test \
--name arm-qemu-test_CONTAINER \
--privileged \
arm-qemu-test-zsh \
zsh

15:53:54 developer@arm-qemu-test /app
```

This will give you a docker that should run in ARM emulated mode, this can be
checked with uname -m:

``` bash
$ uname -m
armv7l
```


## building the pyinstaller package

### gateway service

* Run the docker container
* Go to the `gw-service` folder
* run `make venv` for the first time

  This will build a virtual python environment that will be used, and therefoe
  only needs to be done once

* Create a `dist-overlay` folder in the `gw-service` folder. This will contain
  all the nessesary files that are non code files.

  * Create the frontend static folder and place this under this `dist-overlay`
    folder

  * Create a `etc` folder inside the `dist-overlay` folder and place the known
    config files in there (openmotics.conf, certificates, etc)

  * Also, include a known gateway.db file in the `etc` folder since the
    migrations do not work at this point in time.

  * You should have a folder layout as follows:

    ``` bash
    ⇒  tree -L 1 dist-overlay 
    dist-overlay
    ├── etc
    └── static
    ```

* run `make package` to build the pyinstaller package.

  * Artifacts fo this process will be in the `dist` folder.

  * This process can take up some time.

* To make a Renson core packge, run the `ES-package-build.sh` script that is
  located in the `gw-service` folder.

  This will produce the nessesary files in the `package` directory inside
  `gw-service`. If everything goes well, you should see:

  ``` bash
  ⇒  tree -L 1 ./package 
  ./package
  ├── bin           # => Contains all the binary files that are created
  ├── clean.sh
  ├── package_info.txt  # => Contains all the package info for renson core package
  ├── upload.sh
  └── zip.sh

  1 directory, 4 files
  ```


* Now that all the needed files are in the `package` folder, go to the `package`
  folder and run the `zip.sh` and `upload.sh` script to respectivly zip and
  upload the package to an renson core enabled device.

  Note: 

  * Set the ip and the api secret first in the `upload.sh` script before
    uploading.
  * Import the gpg key that is needed to sign the package before uploading the
    package.


### vpn-service

* To build the vpn-service follow the gateway service steps as they are similar.
  The only differences are:
  * instead of working in the `gw-service` folder, use the `vpn-service` folder
  * Do not add the static folder in the `dist-overlay` folder