FROM arm32v7/python:2.7.16-stretch
MAINTAINER Sander Van Schoote <sander@openmotics.com>

# System packages installation
RUN apt-get _update && apt-get upgrade -y && \
     apt-get install -y supervisor sudo wget netcat less nano vim openvpn && \
     rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

COPY src.tgz /src.tgz
RUN cd / && \
    tar xzf src.tgz && \
    mv src /opt/openmotics && \
    rm src.tgz

COPY entrypoint.sh /entrypoint.sh
WORKDIR /opt/openmotics
CMD ["/entrypoint.sh"]
