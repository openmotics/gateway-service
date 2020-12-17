# docker image definition
DOCKER_IMG_NAME ?= arm-qemu-test
DOCKER_CONT_NAME ?= $(DOCKER_IMG_NAME)_CONTAINER

DOCKER_HOSTNAME ?= $(DOCKER_IMG_NAME)

# docker run command options
DOCKER_BASE_CMD := docker run
DOCKER_RM_CMD := --rm
DOCKER_INTERACTIVE := -it
DOCKER_DAEMON := -d

DOCKER_OPTIONS += -v $(shell pwd):/app
DOCKER_OPTIONS += -w /app
DOCKER_OPTIONS += -e TERM=xterm-256color
DOCKER_OPTIONS += --user="$(shell id -u):$(shell id -g)"
DOCKER_OPTIONS += --hostname $(DOCKER_HOSTNAME)
DOCKER_OPTIONS += --name $(DOCKER_CONT_NAME)


DOCKER_OPTIONS_XORG += -e DISPLAY=$(DISPLAY) -v /tmp/.X11-unix:/tmp/.X11-unix
DOCKER_OPTIONS_PRIVILEGED += --privileged

DOCKER_OPTIONS_QEMU += -v /usr/bin/qemu-arm-static:/usr/bin/qemu-arm-static

.PHONY: docker-build docker-run docker-build-remote

build-docker:
	docker build \
		-t $(DOCKER_IMG_NAME)-zsh \
		-f docker/Dockerfile-zsh \
		docker

run-docker:
	$(DOCKER_BASE_CMD) \
	$(DOCKER_RM_CMD) \
	$(DOCKER_INTERACTIVE) \
	$(DOCKER_OPTIONS) \
	$(DOCKER_OPTIONS_PRIVILEGED) \
	$(DOCKER_OPTIONS_XORG) \
	$(DOCKER_IMG_NAME)-zsh \
	zsh
