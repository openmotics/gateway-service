# OpenMotics Gateway (backend)

[![Build Status](https://travis-ci.org/openmotics/gateway.svg?branch=develop)](https://travis-ci.org/openmotics/gateway)

This project is the OpenMotics Gateway backend. It provides an API used by the frontend, by the Cloud and by third party applications. 

It is the glue between the OpenMotics Master (microcontroller) and the rest of the world.

## Git workflow

We use [git-flow](https://github.com/petervanderdoes/gitflow-avh) which implements [Vincent Driessen](http://nvie.com/posts/a-successful-git-branching-model/)'s
branching model. This means our default branch is `develop`, and `master` contains production releases.

When working on this repository, we advice to use following git-flow config:

```
Branch name for production releases: master
Branch name for "next release" development: develop
Feature branch prefix: feature/
Bugfix branch prefix: bugfix/
Release branch prefix: release/
Hotfix branch prefix: hotfix/
Support branch prefix: support/
Version tag prefix: v
```

To set these configuration parameters:

```
git config gitflow.branch.master master
git config gitflow.branch.develop develop
git config gitflow.prefix.feature feature/
git config gitflow.prefix.bugfix bugfix/
git config gitflow.prefix.release release/
git config gitflow.prefix.hotfix hotfix/
git config gitflow.prefix.support support/
git config gitflow.prefix.versiontag v
```

## Running locally

Some parts of the code can be run locally using a dummy master implementation.

The openmotics service loads a config file from `./etc` or `$OPENMOTICS_PREFIX/etc`,
where settings like the platform and ports can be overridden.

```sh
mkdir -p etc static
cp example/openmotics.conf etc
python openmotics_service.py
```

Extracting a frontend build to `./static` also gives access to the local protal interface.

## Built With

* [CherryPy](http://cherrypy.org/) - A Minimalist Python Web Framework
* [Requests](http://docs.python-requests.org/en/master/) - HTTP for Humans

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the tags on this repository

## Authors

* *Frederick Ryckbosch* - GitHub user: [fryckbos](https://github.com/fryckbos)
* *Kenneth Henderick* - GitHub user: [khenderick](https://github.com/khenderick)

## License

This project is licensed under the AGPLv3 License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Thanks to everybody testing this code and providing feedback.
