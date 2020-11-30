ARG TAG=2.7-stretch
FROM python:$TAG

WORKDIR /app

RUN if command -v virtualenv; then\
    virtualenv venv;\
  else\
    python3 -m venv venv;\
    venv/bin/pip install mypy lxml;\
  fi

COPY requirements.txt requirements-py3.txt /app/

RUN if command -v virtualenv; then\
    venv/bin/pip install -r requirements.txt;\
  else\
    venv/bin/pip install -r requirements-py3.txt;\
  fi

ENV PATH="/app/venv/bin:${PATH}"
