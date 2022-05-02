# OpenMotics Gateway (backend)

This project is the OpenMotics Gateway backend. It provides an API used by the frontend, by the Cloud and by third party applications. 

It is the glue between the OpenMotics Master (microcontroller) and the rest of the world.

## Running locally

Some parts of the code can be run locally using a dummy master implementation.

### Installing the requirements
To run localy, it is easy to use direnv.

```sh
sudo apt-get install direnv
```

Then, add the direnv hooks to your .bashrc in your home (when using bash)
```
eval "$(direnv hook bash)"
```
or, when using zsh, add this to .zshr
```
eval "$(direnv hook zsh)"
```

### Environment: create .envrc & .env
Next, create the .envrc file in the gateway folder which will be used by direnv

```
dotenv
use nix
layout python python3
```

The openmotics service loads a config file from `$OPENMOTICS_PREFIX/etc`
where settings like the platform and ports can be overridden. This means that this environment variable
must be set before starting the service.

Add this to the .env file in the gateway root folder.
```
OPENMOTICS_PREFIX=/some/directory/pointing/to/openmotics/gateway
```

### Install requirements

Install the python dependencies the first time:
```
pip install -r requirements-py3.txt
```

### Add local fixtures
Copy the configuration/fixture files and generate self-signed certificates:

```sh
mkdir -p etc static
cd etc
# copy the example config file, it can be further customized
cp ../example/openmotics.conf .
# Copy the fixtures, they can be further customized
cp ../example/master_fixture.json .
# generate self signed certificate
openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout https.key -out https.crt -subj '/CN=om-developer'
```


### Dummy master

The local running gateway will use a dummy master. The example master fixtures make a virtual input, relay and 0/1-10V module available for futher configuration.

While it behaves like a Brain(+) master, only a very limited set of features is available. The goal is not to
emulate a real device, but give a user at least something to start with. The implemented features:
* Some status calls can be executed (e.g. it will report a version & a time)
* Everything can be configured just as normal (the full configuration space is available)
* It is possible to link an input to an output
* It is possible to turn on/off, toggle & dim outputs
* It is possible to configure group actions. The only supported actions are turning on/off, toggling & dimming outputs
* It is possible to configure an input to execute a group action on press and/or release

The implementation supports a persistent eeprom state (by default only the fixtures will be available when the service is (re)started).
To enable this, add `dummy_eeprom_persistence = true` under the `OpenMotics` section in `openmotics.conf`. When enabled, the configuration
state is stored inside `etc/master_eeprom.json`. This is a raw-format file and is not meant for manual manipulation. 


On startup, and after the optional eeprom state is restored, he fixtures inside `master_fixture.json` are loaded if this file is present. 
These fixtures represent the master ORM data format, and are designed to be manually specified.


### Local frontend (optional) 

Extracting the [frontend build](https://github.com/openmotics/frontend/releases) to `./static` also gives access to the local portal interface.
Download the latest frontend release (.tgz) manually and put it in the static folder.

```sh
tar -xf *.tgz
```


### Type checking (optional)

For type checking during development mypy is used, this requires python3 as well as
some extra dependencies in order to function properly:

```sh
pip install mypy types-all sqlalchemy-stubs
```


## Running the code

Starting the necessary services using foreman
```
foreman start
```

### Local user
The gateway locally does not require authentication.
However, to log in the frontend, you can use the user "admin", pwd "admin".


## License

This project is licensed under the AGPLv3 License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Thanks to everybody testing this code and providing feedback.
