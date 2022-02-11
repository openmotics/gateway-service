# OpenMotics Gateway (backend)

This project is the OpenMotics Gateway backend. It provides an API used by the frontend, by the Cloud and by third party applications. 

It is the glue between the OpenMotics Master (microcontroller) and the rest of the world.


## Running locally

Some parts of the code can be run locally using a dummy master implementation.

The openmotics service loads a config file from `$OPENMOTICS_PREFIX/etc`,
where settings like the platform and ports can be overridden. You can specify the env variables in a .env file:
```
OPENMOTICS_PREFIX=/some/directory/pointing/to/openmotics/gateway
```

Using the following .envrc direnv can be used to setup all the dependencies in your shell. (equivalent to nix-shell + creating and activating a virtualenv)
```
dotenv
use nix
layout python python3
```

Installing python dependencies is done as normal
```
pip install -r requirements-py3.txt
```

Copy the configuration files and generate self signed certificates
```sh
mkdir -p etc static
cd etc
# copy the example config file, it can be further customized
cp ../example/openmotics.conf etc
# generate self signed certificate
openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout https.key -out https.crt -subj '/CN=om-developer'
```

Starting the necessary services using foreman
```
foreman start
```

**[OPTIONAL]** 

Extracting the [frontend build](https://github.com/openmotics/frontend/releases/download/v1.13.5/gateway-frontend_1.13.5.tgz) to `./static` also gives access to the local protal interface.


## License

This project is licensed under the AGPLv3 License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Thanks to everybody testing this code and providing feedback.
